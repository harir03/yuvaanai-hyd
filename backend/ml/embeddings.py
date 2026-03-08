"""
Intelli-Credit — Embedding Generator

Wraps sentence-transformers (all-MiniLM-L6-v2) for 384-dim local embeddings.
Falls back to TF-IDF-style hash embeddings when sentence-transformers is unavailable.

Models loaded ONCE at startup (Section 17 performance rule).
"""

import logging
import hashlib
import math
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──
EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"

# ── Singleton model holder ──
_model = None
_mode: str = "uninitialized"  # "sbert" or "fallback"


def _init_model() -> None:
    """Load the embedding model once. Fall back to heuristic if unavailable."""
    global _model, _mode
    if _mode != "uninitialized":
        return

    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        _mode = "sbert"
        logger.info(f"[Embeddings] Loaded {MODEL_NAME} (sentence-transformers)")
    except ImportError:
        _model = None
        _mode = "fallback"
        logger.warning("[Embeddings] sentence-transformers not available — using hash fallback")
    except Exception as e:
        _model = None
        _mode = "fallback"
        logger.warning(f"[Embeddings] Failed to load {MODEL_NAME}: {e} — using hash fallback")


def _hash_embed(text: str) -> np.ndarray:
    """Deterministic hash-based embedding (fallback).

    Produces a stable 384-dim unit vector from text content.
    Not semantically meaningful, but consistent and fast.
    """
    # Build 384 floats from multiple hash rounds (SHA-384 gives 48 bytes each)
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    offset = 0
    round_idx = 0
    while offset < EMBEDDING_DIM:
        seed = f"{text}__r{round_idx}" if round_idx > 0 else text
        digest = hashlib.sha384(seed.encode("utf-8")).digest()
        chunk = np.array([b / 127.5 - 1.0 for b in digest], dtype=np.float32)
        end = min(offset + len(chunk), EMBEDDING_DIM)
        vec[offset:end] = chunk[: end - offset]
        offset = end
        round_idx += 1
    # Normalize to unit vector
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a batch of texts into 384-dim vectors.

    Args:
        texts: List of text strings to embed.

    Returns:
        numpy array of shape (len(texts), 384).
    """
    _init_model()

    if not texts:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)

    if _mode == "sbert" and _model is not None:
        return _model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    # Fallback: hash-based embeddings
    return np.array([_hash_embed(t) for t in texts], dtype=np.float32)


def embed_single(text: str) -> np.ndarray:
    """Embed a single text string into a 384-dim vector."""
    result = embed_texts([text])
    return result[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def get_mode() -> str:
    """Return current embedding mode ('sbert' or 'fallback')."""
    _init_model()
    return _mode


def reset() -> None:
    """Reset the singleton (for testing)."""
    global _model, _mode
    _model = None
    _mode = "uninitialized"
