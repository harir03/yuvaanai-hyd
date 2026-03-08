"""
Intelli-Credit — Isolation Forest Anomaly Detection

Detects tabular anomalies in financial metrics using scikit-learn's Isolation Forest.
Falls back to Z-score based outlier detection when sklearn is unavailable.

Models loaded ONCE at startup (Section 17 performance rule).
Input: Financial feature vectors (metrics from ComputedMetrics).
Output: Anomaly scores (higher = more anomalous), labels, and feature explanations.
"""

import logging
import math
from typing import List, Dict, Any, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──
# Feature names aligned with ComputedMetrics in state.py
FEATURE_NAMES = [
    "dscr",
    "current_ratio",
    "debt_equity_ratio",
    "revenue_cagr_3yr",
    "ebitda_margin",
    "pat_margin",
    "interest_coverage_ratio",
    "gst_bank_divergence_pct",
    "itr_ar_divergence_pct",
    "promoter_pledge_pct",
]

# Sector-agnostic "normal" ranges for Z-score fallback
# (mean, std) — empirical approximations for Indian mid-cap corporates
NORMAL_RANGES: Dict[str, Tuple[float, float]] = {
    "dscr":                     (1.5, 0.5),
    "current_ratio":            (1.3, 0.4),
    "debt_equity_ratio":        (1.2, 0.6),
    "revenue_cagr_3yr":         (0.10, 0.08),       # 10% ± 8%
    "ebitda_margin":            (0.15, 0.06),        # 15% ± 6%
    "pat_margin":               (0.08, 0.04),        # 8% ± 4%
    "interest_coverage_ratio":  (3.0, 1.5),
    "gst_bank_divergence_pct":  (5.0, 4.0),          # 5% ± 4%
    "itr_ar_divergence_pct":    (5.0, 4.0),
    "promoter_pledge_pct":      (15.0, 15.0),        # 15% ± 15%
}

# Anomaly threshold for Z-score method
Z_SCORE_THRESHOLD = 2.0

# ── Singleton model holder ──
_model = None
_mode: str = "uninitialized"  # "sklearn" or "fallback"
_is_fitted: bool = False


def _init_model() -> None:
    """Initialize the Isolation Forest model. Fall back to Z-score if sklearn unavailable."""
    global _model, _mode
    if _mode != "uninitialized":
        return

    try:
        from sklearn.ensemble import IsolationForest
        _model = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            random_state=42,
            n_jobs=1,
        )
        _mode = "sklearn"
        logger.info("[IsolationForest] Initialized sklearn IsolationForest")
    except ImportError:
        _model = None
        _mode = "fallback"
        logger.warning("[IsolationForest] sklearn not available — using Z-score fallback")
    except Exception as e:
        _model = None
        _mode = "fallback"
        logger.warning(f"[IsolationForest] Init failed: {e} — using Z-score fallback")


def extract_features(metrics: Dict[str, Any]) -> np.ndarray:
    """Extract a feature vector from ComputedMetrics dict.

    Missing values are replaced with NaN (handled during scoring).
    """
    vec = []
    for name in FEATURE_NAMES:
        val = metrics.get(name)
        if val is not None:
            try:
                vec.append(float(val))
            except (TypeError, ValueError):
                vec.append(np.nan)
        else:
            vec.append(np.nan)
    return np.array(vec, dtype=np.float64)


def _impute_nans(features: np.ndarray) -> np.ndarray:
    """Replace NaN with feature-mean (column-wise for matrices, or normal-range mean for single vectors)."""
    if features.ndim == 1:
        for i, name in enumerate(FEATURE_NAMES):
            if np.isnan(features[i]):
                features[i] = NORMAL_RANGES.get(name, (0.0, 1.0))[0]
        return features

    for col in range(features.shape[1]):
        col_data = features[:, col]
        nan_mask = np.isnan(col_data)
        if nan_mask.all():
            features[:, col] = NORMAL_RANGES.get(FEATURE_NAMES[col], (0.0, 1.0))[0]
        elif nan_mask.any():
            features[nan_mask, col] = np.nanmean(col_data)
    return features


def _zscore_detect(features: np.ndarray) -> Dict[str, Any]:
    """Z-score based anomaly detection (fallback).

    Compares each feature against known normal ranges.
    Returns anomaly score (0 to 1) and per-feature explanations.
    """
    z_scores = []
    anomalous_features = []

    for i, name in enumerate(FEATURE_NAMES):
        val = features[i]
        mean, std = NORMAL_RANGES.get(name, (0.0, 1.0))
        if std == 0:
            std = 1.0
        z = abs(val - mean) / std
        z_scores.append(z)
        if z > Z_SCORE_THRESHOLD:
            direction = "high" if val > mean else "low"
            anomalous_features.append({
                "feature": name,
                "value": float(val),
                "z_score": round(float(z), 2),
                "expected_mean": mean,
                "direction": direction,
                "explanation": f"{name} is unusually {direction} ({val:.2f} vs expected {mean:.2f} ± {std:.2f})",
            })

    # Aggregate anomaly score: max Z-score normalized to [0, 1]
    max_z = max(z_scores) if z_scores else 0.0
    anomaly_score = min(max_z / 5.0, 1.0)  # Z=5 → score 1.0

    return {
        "anomaly_score": round(anomaly_score, 4),
        "is_anomaly": anomaly_score > 0.4,
        "anomalous_features": anomalous_features,
        "method": "zscore_fallback",
        "feature_z_scores": {name: round(float(z), 2) for name, z in zip(FEATURE_NAMES, z_scores)},
    }


def detect_anomalies(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Run anomaly detection on a single company's financial metrics.

    Args:
        metrics: Dict with keys matching FEATURE_NAMES (from ComputedMetrics).

    Returns:
        Dict with keys:
            - anomaly_score (float, 0 to 1, higher = more anomalous)
            - is_anomaly (bool)
            - anomalous_features (list of dicts with explanations)
            - method ("sklearn" or "zscore_fallback")
    """
    _init_model()
    features = extract_features(metrics)
    features = _impute_nans(features)

    if _mode == "sklearn" and _model is not None:
        try:
            # sklearn IsolationForest: fit on normal ranges + this sample
            # For single-sample detection, we generate synthetic "normal" training data
            rng = np.random.RandomState(42)
            n_synthetic = 200
            synthetic = np.zeros((n_synthetic, len(FEATURE_NAMES)))
            for i, name in enumerate(FEATURE_NAMES):
                mean, std = NORMAL_RANGES.get(name, (0.0, 1.0))
                synthetic[:, i] = rng.normal(mean, std, n_synthetic)

            _model.fit(synthetic)
            sample = features.reshape(1, -1)
            pred = _model.predict(sample)[0]      # -1 = anomaly, 1 = normal
            score_raw = _model.score_samples(sample)[0]  # Lower = more anomalous

            # Normalize score_raw to [0, 1] where 1 = most anomalous
            # IsolationForest scores typically range from -0.5 (anomaly) to 0.0 (normal)
            anomaly_score = max(0.0, min(1.0, -score_raw))

            # Find anomalous features using Z-score as explanation
            anomalous_features = []
            for i, name in enumerate(FEATURE_NAMES):
                val = features[i]
                mean, std = NORMAL_RANGES.get(name, (0.0, 1.0))
                if std == 0:
                    std = 1.0
                z = abs(val - mean) / std
                if z > Z_SCORE_THRESHOLD:
                    direction = "high" if val > mean else "low"
                    anomalous_features.append({
                        "feature": name,
                        "value": float(val),
                        "z_score": round(float(z), 2),
                        "expected_mean": mean,
                        "direction": direction,
                        "explanation": f"{name} is unusually {direction} ({val:.2f} vs expected {mean:.2f} ± {std:.2f})",
                    })

            return {
                "anomaly_score": round(float(anomaly_score), 4),
                "is_anomaly": pred == -1,
                "anomalous_features": anomalous_features,
                "method": "sklearn",
                "raw_score": round(float(score_raw), 4),
            }
        except Exception as e:
            logger.warning(f"[IsolationForest] sklearn detection failed: {e} — falling back to Z-score")

    # Fallback: Z-score based
    return _zscore_detect(features)


def detect_batch(metrics_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run anomaly detection on multiple companies' metrics."""
    return [detect_anomalies(m) for m in metrics_list]


def get_mode() -> str:
    """Return current detection mode ('sklearn' or 'fallback')."""
    _init_model()
    return _mode


def reset() -> None:
    """Reset singleton (for testing)."""
    global _model, _mode, _is_fitted
    _model = None
    _mode = "uninitialized"
    _is_fitted = False
