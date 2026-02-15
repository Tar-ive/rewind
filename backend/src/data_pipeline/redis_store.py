"""
Redis Vector Store – create indexes and store signal documents with embeddings.

Uses the ``redis`` client directly with RediSearch FT commands to avoid
tight coupling to redisvl's high-level API (which can change across versions).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

import numpy as np
import redis
import yaml
from pathlib import Path

from src.config.settings import EMBEDDING_DIM, EXPLICIT_INDEX, IMPLICIT_INDEX, REDIS_URL
from src.data_pipeline.signals import ExplicitSignal, ImplicitSignal

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config" / "redis_schema.yaml"


def _get_redis() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=False)


def _load_schemas() -> dict[str, Any]:
    with open(_SCHEMA_PATH) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Index creation
# ---------------------------------------------------------------------------

def _build_ft_schema(fields: list[dict]) -> list:
    """Convert YAML field definitions into FT.CREATE schema arguments."""
    args: list = []
    for field_def in fields:
        name = field_def["name"]
        ftype = field_def["type"].upper()

        if ftype == "VECTOR":
            attrs = field_def.get("attrs", {})
            algo = attrs.get("algorithm", "HNSW").upper()
            dims = attrs.get("dims", EMBEDDING_DIM)
            dist = attrs.get("distance_metric", "COSINE").upper()
            vtype = attrs.get("type", "FLOAT32").upper()
            # VECTOR field: name VECTOR algo num_attrs [attr value ...]
            args += [
                name, "VECTOR", algo, "6",
                "TYPE", vtype,
                "DIM", str(dims),
                "DISTANCE_METRIC", dist,
            ]
        elif ftype == "TAG":
            args += [name, "TAG"]
        elif ftype == "TEXT":
            args += [name, "TEXT"]
        elif ftype == "NUMERIC":
            args += [name, "NUMERIC"]
        else:
            args += [name, "TEXT"]
    return args


def create_indexes(drop_existing: bool = True) -> None:
    """Create (or recreate) both FT indexes on Redis."""
    r = _get_redis()
    schemas = _load_schemas()

    for _key, schema_def in schemas.items():
        idx_cfg = schema_def["index"]
        idx_name = idx_cfg["name"]
        prefix = idx_cfg["prefix"]

        # Drop if requested
        if drop_existing:
            try:
                r.execute_command("FT.DROPINDEX", idx_name, "DD")
                logger.info("Dropped existing index: %s", idx_name)
            except redis.ResponseError:
                pass  # index didn't exist

        schema_args = _build_ft_schema(schema_def["fields"])

        cmd = [
            "FT.CREATE", idx_name,
            "ON", "HASH",
            "PREFIX", "1", prefix,
            "SCHEMA",
        ] + schema_args

        r.execute_command(*cmd)
        logger.info("Created index: %s (prefix=%s)", idx_name, prefix)


# ---------------------------------------------------------------------------
# Document storage
# ---------------------------------------------------------------------------

def store_explicit_signals(
    signals: Sequence[ExplicitSignal],
    embeddings: np.ndarray,
) -> int:
    """Store explicit signals as Redis hashes under the 'explicit:' prefix."""
    r = _get_redis()
    pipe = r.pipeline(transaction=False)

    for i, sig in enumerate(signals):
        key = f"explicit:{sig.signal_id}"
        vec_bytes = embeddings[i].astype(np.float32).tobytes()
        pipe.hset(key, mapping={
            "signal_id": sig.signal_id,
            "source": sig.source,
            "category": sig.category,
            "text": sig.text,
            "metadata": json.dumps(sig.metadata),
            "embedding": vec_bytes,
        })

    pipe.execute()
    logger.info("Stored %d explicit signals in Redis", len(signals))
    return len(signals)


def store_implicit_signals(
    signals: Sequence[ImplicitSignal],
    embeddings: np.ndarray,
) -> int:
    """Store implicit signals as Redis hashes under the 'implicit:' prefix."""
    r = _get_redis()
    pipe = r.pipeline(transaction=False)

    for i, sig in enumerate(signals):
        key = f"implicit:{sig.signal_id}"
        vec_bytes = embeddings[i].astype(np.float32).tobytes()
        pipe.hset(key, mapping={
            "signal_id": sig.signal_id,
            "source": sig.source,
            "pattern_type": sig.pattern_type,
            "description": sig.description,
            "metadata": json.dumps(sig.metadata),
            "embedding": vec_bytes,
        })

    pipe.execute()
    logger.info("Stored %d implicit signals in Redis", len(signals))
    return len(signals)


# ---------------------------------------------------------------------------
# Vector search helpers
# ---------------------------------------------------------------------------

def search_explicit(
    query_embedding: np.ndarray,
    top_k: int = 5,
    source_filter: str | None = None,
) -> list[dict[str, Any]]:
    """KNN vector search over explicit_signals."""
    return _vector_search(
        index_name=EXPLICIT_INDEX,
        query_embedding=query_embedding,
        top_k=top_k,
        tag_field="source",
        tag_value=source_filter,
        text_field="text",
    )


def search_implicit(
    query_embedding: np.ndarray,
    top_k: int = 5,
    source_filter: str | None = None,
) -> list[dict[str, Any]]:
    """KNN vector search over implicit_signals."""
    return _vector_search(
        index_name=IMPLICIT_INDEX,
        query_embedding=query_embedding,
        top_k=top_k,
        tag_field="source",
        tag_value=source_filter,
        text_field="description",
    )


def _vector_search(
    index_name: str,
    query_embedding: np.ndarray,
    top_k: int,
    tag_field: str,
    tag_value: str | None,
    text_field: str,
) -> list[dict[str, Any]]:
    """Low-level FT.SEARCH with KNN."""
    r = _get_redis()
    vec_bytes = query_embedding.astype(np.float32).tobytes()

    if tag_value:
        q = f"(@{tag_field}:{{{tag_value}}})=>[KNN {top_k} @embedding $vec AS score]"
    else:
        q = f"*=>[KNN {top_k} @embedding $vec AS score]"

    raw = r.execute_command(
        "FT.SEARCH", index_name, q,
        "PARAMS", "2", "vec", vec_bytes,
        "SORTBY", "score",
        "RETURN", "4", "signal_id", text_field, "source", "score",
        "DIALECT", "2",
    )

    results = _parse_ft_search(raw, text_field)
    return results


def _parse_ft_search(raw: list, text_field: str) -> list[dict[str, Any]]:
    """Parse the raw FT.SEARCH response into a list of dicts."""
    if not raw or raw[0] == 0:
        return []

    results: list[dict[str, Any]] = []
    # raw[0] = total count, then pairs of (key, [field, value, ...])
    i = 1
    while i < len(raw):
        _key = raw[i]
        fields = raw[i + 1] if i + 1 < len(raw) else []
        i += 2

        doc: dict[str, Any] = {}
        if isinstance(fields, list):
            it = iter(fields)
            for fname in it:
                val = next(it, None)
                fname_str = fname.decode() if isinstance(fname, bytes) else str(fname)
                val_str = val.decode() if isinstance(val, bytes) else str(val) if val else ""
                doc[fname_str] = val_str

        results.append(doc)

    return results
