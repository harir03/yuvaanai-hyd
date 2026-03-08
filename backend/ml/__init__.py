"""
Intelli-Credit — ML Model Package

Provides 4 ML capabilities, each with graceful fallback when dependencies
are not installed:

- embeddings: sentence-transformers (all-MiniLM-L6-v2) → hash fallback
- isolation_forest: scikit-learn IsolationForest → Z-score fallback
- finbert_model: ProsusAI/finbert → keyword sentiment fallback
- dominant_gnn: PyTorch Geometric DOMINANT → heuristic graph fallback

All models are loaded ONCE as singletons (Section 17 performance rule).
"""

from backend.ml import embeddings
from backend.ml import isolation_forest
from backend.ml import finbert_model
from backend.ml import dominant_gnn

__all__ = [
    "embeddings",
    "isolation_forest",
    "finbert_model",
    "dominant_gnn",
]

