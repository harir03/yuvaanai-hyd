"""
Intelli-Credit — ML Model Registry

Simple model versioning and metadata tracking for all ML components.
No external dependencies — uses JSON files for portability.

Tracks:
  - Model name, version, and mode (full / fallback)
  - Feature configuration (dimensions, feature names)
  - Evaluation metrics (from model_evaluation.py)
  - Configuration hashes for drift detection
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Registry file (JSON) stored alongside models
_REGISTRY_DIR = os.path.join(os.path.dirname(__file__), ".model_registry")


def _ensure_dir() -> str:
    os.makedirs(_REGISTRY_DIR, exist_ok=True)
    return _REGISTRY_DIR


def _registry_path() -> str:
    return os.path.join(_ensure_dir(), "registry.json")


def _load_registry() -> Dict[str, Any]:
    path = _registry_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"models": {}, "created_at": datetime.now(timezone.utc).isoformat()}


def _save_registry(data: Dict[str, Any]) -> None:
    path = _registry_path()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _config_hash(config: Dict[str, Any]) -> str:
    """Deterministic hash of a config dict for drift detection."""
    raw = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


# ── Public API ──


def register_model(
    name: str,
    version: str,
    mode: str,
    config: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Register or update a model entry.

    Args:
        name: Model identifier (e.g., "isolation_forest", "dominant_gnn", "finbert").
        version: Semantic version string (e.g., "2.0.0").
        mode: Runtime mode ("sklearn", "fallback", "pyg", "keyword_fallback", etc.).
        config: Model configuration dict (features, thresholds, hyperparams).
        metrics: Optional evaluation metrics from model_evaluation.py.
        notes: Optional human-readable notes about this version.

    Returns:
        The registered model entry.
    """
    reg = _load_registry()
    entry = {
        "name": name,
        "version": version,
        "mode": mode,
        "config": config,
        "config_hash": _config_hash(config),
        "metrics": metrics,
        "notes": notes,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }

    if name not in reg["models"]:
        reg["models"][name] = {"current": entry, "history": []}
    else:
        # Archive current version
        current = reg["models"][name].get("current")
        if current:
            reg["models"][name]["history"].append(current)
        reg["models"][name]["current"] = entry

    _save_registry(reg)
    logger.info(f"[ModelRegistry] Registered {name} v{version} (mode={mode})")
    return entry


def get_model_info(name: str) -> Optional[Dict[str, Any]]:
    """Get the current registered info for a model."""
    reg = _load_registry()
    model_data = reg.get("models", {}).get(name)
    if model_data:
        return model_data.get("current")
    return None


def get_model_history(name: str) -> List[Dict[str, Any]]:
    """Get version history for a model."""
    reg = _load_registry()
    model_data = reg.get("models", {}).get(name)
    if model_data:
        history = list(model_data.get("history", []))
        current = model_data.get("current")
        if current:
            history.append(current)
        return history
    return []


def list_models() -> Dict[str, Any]:
    """List all registered models with their current version."""
    reg = _load_registry()
    summary = {}
    for name, data in reg.get("models", {}).items():
        current = data.get("current", {})
        summary[name] = {
            "version": current.get("version", "unknown"),
            "mode": current.get("mode", "unknown"),
            "config_hash": current.get("config_hash", ""),
            "registered_at": current.get("registered_at", ""),
            "has_metrics": current.get("metrics") is not None,
        }
    return summary


def check_config_drift(name: str, current_config: Dict[str, Any]) -> Dict[str, Any]:
    """Check if model config has drifted from the registered version.

    Returns:
        Dict with 'drifted' (bool) and details.
    """
    info = get_model_info(name)
    if not info:
        return {"drifted": False, "reason": "model_not_registered"}

    registered_hash = info.get("config_hash", "")
    current_hash = _config_hash(current_config)

    return {
        "drifted": registered_hash != current_hash,
        "registered_hash": registered_hash,
        "current_hash": current_hash,
        "registered_version": info.get("version", "unknown"),
    }


def register_all_current() -> Dict[str, Any]:
    """Register all current ML models with their configs and evaluation metrics.

    Convenience function that captures the current state of all models.
    """
    from backend.ml.isolation_forest import (
        FEATURE_NAMES, Z_SCORE_THRESHOLD, SECTOR_CONTAMINATION,
        DEFAULT_CONTAMINATION, DERIVED_FEATURE_NAMES, get_mode as if_mode,
    )
    from backend.ml.dominant_gnn import (
        HIDDEN_DIM, NUM_EPOCHS, LEARNING_RATE, ANOMALY_THRESHOLD,
        ADAPTIVE_THRESHOLD_K, FEAT_DIM, get_mode as gnn_mode,
    )
    from backend.ml.finbert_model import (
        RISK_SEVERITY_THRESHOLD, get_mode as fb_mode,
    )
    from backend.ml.embeddings import (
        EMBEDDING_DIM, MODEL_NAME, get_mode as emb_mode,
    )

    # Run evaluations
    try:
        from backend.ml.model_evaluation import evaluate_all
        eval_results = evaluate_all()
    except Exception as e:
        logger.warning(f"[ModelRegistry] Evaluation failed: {e}")
        eval_results = {}

    results = {}

    # Isolation Forest
    results["isolation_forest"] = register_model(
        name="isolation_forest",
        version="2.0.0",
        mode=if_mode(),
        config={
            "features": FEATURE_NAMES,
            "derived_features": DERIVED_FEATURE_NAMES,
            "z_score_threshold": Z_SCORE_THRESHOLD,
            "sector_contamination": SECTOR_CONTAMINATION,
            "default_contamination": DEFAULT_CONTAMINATION,
        },
        metrics=eval_results.get("isolation_forest", {}).get("metrics"),
        notes="v2: sector-calibrated contamination, time-series features, feature importance",
    )

    # DOMINANT GNN
    results["dominant_gnn"] = register_model(
        name="dominant_gnn",
        version="2.0.0",
        mode=gnn_mode(),
        config={
            "hidden_dim": HIDDEN_DIM,
            "num_epochs": NUM_EPOCHS,
            "learning_rate": LEARNING_RATE,
            "anomaly_threshold": ANOMALY_THRESHOLD,
            "adaptive_threshold_k": ADAPTIVE_THRESHOLD_K,
            "feature_dim": FEAT_DIM,
        },
        metrics=eval_results.get("dominant_gnn", {}).get("node_detection_metrics"),
        notes="v2: 16-dim features, label propagation communities, reciprocity/concentration analysis, dual-objective DOMINANT autoencoder",
    )

    # FinBERT
    results["finbert"] = register_model(
        name="finbert",
        version="2.0.0",
        mode=fb_mode(),
        config={
            "risk_severity_threshold": RISK_SEVERITY_THRESHOLD,
            "scoring": "severity_weighted",
        },
        metrics=eval_results.get("finbert", {}).get("metrics"),
        notes="v2: severity-weighted risk scoring (CRITICAL/HIGH/MEDIUM/LOW), Indian regulatory keywords",
    )

    # Embeddings
    results["embeddings"] = register_model(
        name="embeddings",
        version="1.1.0",
        mode=emb_mode(),
        config={
            "model_name": MODEL_NAME,
            "embedding_dim": EMBEDDING_DIM,
        },
        notes="v1.1: added fallback mode documentation warnings",
    )

    return results
