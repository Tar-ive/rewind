#!/usr/bin/env python3
"""
Seed Redis – full ingestion pipeline.

    parse  ->  classify  ->  embed  ->  store

Usage:
    python -m scripts.seed_redis
"""

from __future__ import annotations

import logging
import sys
import time

# Ensure project root is on sys.path when run as a script
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_pipeline.signals import build_all_signals
from src.data_pipeline.embeddings import embed_texts
from src.data_pipeline.redis_store import (
    create_indexes,
    store_explicit_signals,
    store_implicit_signals,
    search_explicit,
    search_implicit,
)
from src.data_pipeline.embeddings import embed_single

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("seed_redis")


def main() -> None:
    t0 = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Parse + classify
    # ------------------------------------------------------------------
    log.info("Parsing data sources and classifying signals ...")
    explicit, implicit = build_all_signals()
    log.info(
        "  -> %d explicit signals, %d implicit signals",
        len(explicit), len(implicit),
    )

    # ------------------------------------------------------------------
    # 2. Embed
    # ------------------------------------------------------------------
    log.info("Generating embeddings (all-MiniLM-L6-v2, dim=384) ...")
    explicit_texts = [s.text for s in explicit]
    implicit_texts = [s.description for s in implicit]

    t_embed = time.perf_counter()
    explicit_vecs = embed_texts(explicit_texts)
    implicit_vecs = embed_texts(implicit_texts)
    log.info(
        "  -> Embedded %d + %d texts in %.1fs",
        len(explicit_texts), len(implicit_texts),
        time.perf_counter() - t_embed,
    )

    # ------------------------------------------------------------------
    # 3. Create Redis indexes
    # ------------------------------------------------------------------
    log.info("Creating Redis FT indexes (drop_existing=True) ...")
    create_indexes(drop_existing=True)

    # ------------------------------------------------------------------
    # 4. Store
    # ------------------------------------------------------------------
    log.info("Storing signals in Redis ...")
    n_exp = store_explicit_signals(explicit, explicit_vecs)
    n_imp = store_implicit_signals(implicit, implicit_vecs)
    log.info("  -> Stored %d explicit + %d implicit documents", n_exp, n_imp)

    # ------------------------------------------------------------------
    # 5. Verification query
    # ------------------------------------------------------------------
    log.info("Running verification queries ...")

    q = "What are the user's most productive hours?"
    qvec = embed_single(q)

    log.info("  Query: %r", q)

    exp_results = search_explicit(qvec, top_k=3)
    log.info("  Explicit top-3:")
    for r in exp_results:
        log.info("    score=%s  source=%s  text=%s",
                 r.get("score", "?"), r.get("source", "?"),
                 (r.get("text") or r.get("description", ""))[:120])

    imp_results = search_implicit(qvec, top_k=3)
    log.info("  Implicit top-3:")
    for r in imp_results:
        log.info("    score=%s  source=%s  desc=%s",
                 r.get("score", "?"), r.get("source", "?"),
                 (r.get("description") or r.get("text", ""))[:120])

    elapsed = time.perf_counter() - t0
    log.info("Done! Total pipeline time: %.1fs", elapsed)


if __name__ == "__main__":
    main()
