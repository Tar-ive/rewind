"""
Embedding generation using sentence-transformers.

Loads all-MiniLM-L6-v2 (384-dim) and provides batch embedding helpers.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config.settings import EMBEDDING_DIM, EMBEDDING_MODEL

# Lazy singleton so the model is only loaded once.
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Strip the "sentence-transformers/" prefix if present —
        # SentenceTransformer accepts the short name directly.
        model_name = EMBEDDING_MODEL.replace("sentence-transformers/", "")
        _model = SentenceTransformer(model_name)
    return _model


def embed_texts(texts: Sequence[str], batch_size: int = 64) -> np.ndarray:
    """Embed a batch of strings.

    Returns
    -------
    np.ndarray of shape (len(texts), EMBEDDING_DIM) with float32 values.
    """
    model = _get_model()
    embeddings = model.encode(
        list(texts),
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    # Ensure correct dtype
    arr = np.asarray(embeddings, dtype=np.float32)
    assert arr.shape == (len(texts), EMBEDDING_DIM), (
        f"Expected shape ({len(texts)}, {EMBEDDING_DIM}), got {arr.shape}"
    )
    return arr


def embed_single(text: str) -> np.ndarray:
    """Embed a single string. Returns shape (EMBEDDING_DIM,)."""
    return embed_texts([text])[0]
