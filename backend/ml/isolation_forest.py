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

# Sector-specific benchmarks: sector → { feature → (mean, std) }
# Overrides NORMAL_RANGES when sector is provided
SECTOR_BENCHMARKS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "steel": {
        "dscr":                     (1.3, 0.4),
        "current_ratio":            (1.1, 0.3),
        "debt_equity_ratio":        (1.8, 0.7),     # Capital-intensive
        "revenue_cagr_3yr":         (0.08, 0.06),
        "ebitda_margin":            (0.12, 0.05),    # Lower margins
        "pat_margin":               (0.05, 0.03),
        "interest_coverage_ratio":  (2.5, 1.2),
        "gst_bank_divergence_pct":  (5.0, 4.0),
        "itr_ar_divergence_pct":    (5.0, 4.0),
        "promoter_pledge_pct":      (20.0, 15.0),
    },
    "it": {
        "dscr":                     (2.0, 0.6),
        "current_ratio":            (2.0, 0.5),      # Asset-light, high liquidity
        "debt_equity_ratio":        (0.4, 0.3),      # Low leverage
        "revenue_cagr_3yr":         (0.15, 0.10),
        "ebitda_margin":            (0.22, 0.06),     # Higher margins
        "pat_margin":               (0.15, 0.05),
        "interest_coverage_ratio":  (5.0, 2.0),
        "gst_bank_divergence_pct":  (3.0, 3.0),
        "itr_ar_divergence_pct":    (3.0, 3.0),
        "promoter_pledge_pct":      (10.0, 10.0),
    },
    "pharma": {
        "dscr":                     (1.6, 0.5),
        "current_ratio":            (1.5, 0.4),
        "debt_equity_ratio":        (0.8, 0.4),
        "revenue_cagr_3yr":         (0.12, 0.08),
        "ebitda_margin":            (0.18, 0.06),
        "pat_margin":               (0.10, 0.04),
        "interest_coverage_ratio":  (4.0, 1.5),
        "gst_bank_divergence_pct":  (4.0, 3.5),
        "itr_ar_divergence_pct":    (4.0, 3.5),
        "promoter_pledge_pct":      (12.0, 12.0),
    },
    "infrastructure": {
        "dscr":                     (1.2, 0.3),
        "current_ratio":            (1.0, 0.3),
        "debt_equity_ratio":        (2.5, 0.8),      # Very capital-intensive
        "revenue_cagr_3yr":         (0.06, 0.05),
        "ebitda_margin":            (0.14, 0.05),
        "pat_margin":               (0.04, 0.03),
        "interest_coverage_ratio":  (2.0, 1.0),
        "gst_bank_divergence_pct":  (6.0, 5.0),
        "itr_ar_divergence_pct":    (6.0, 5.0),
        "promoter_pledge_pct":      (25.0, 18.0),
    },
    "fmcg": {
        "dscr":                     (1.8, 0.5),
        "current_ratio":            (1.4, 0.4),
        "debt_equity_ratio":        (0.6, 0.3),
        "revenue_cagr_3yr":         (0.12, 0.07),
        "ebitda_margin":            (0.16, 0.05),
        "pat_margin":               (0.10, 0.04),
        "interest_coverage_ratio":  (4.5, 1.5),
        "gst_bank_divergence_pct":  (4.0, 3.0),
        "itr_ar_divergence_pct":    (4.0, 3.0),
        "promoter_pledge_pct":      (10.0, 10.0),
    },
}

# Anomaly threshold for Z-score method
Z_SCORE_THRESHOLD = 2.0

# Sector-calibrated contamination rates for Isolation Forest
# Higher = more expected anomalies in that sector
SECTOR_CONTAMINATION: Dict[str, float] = {
    "steel": 0.12,           # Capital-intensive, higher fraud surface
    "it": 0.08,              # Asset-light, more transparent
    "pharma": 0.10,          # Moderate risk
    "infrastructure": 0.15,  # Highest fraud risk (land, contracts)
    "fmcg": 0.08,            # Consumer-facing, lower fraud
}
DEFAULT_CONTAMINATION = 0.10

# Time-series derived feature names (appended when historical data available)
DERIVED_FEATURE_NAMES = [
    "revenue_yoy_change",     # Year-over-year revenue change
    "margin_trend",           # EBITDA margin trend (improving/declining)
    "dscr_volatility",        # Std of DSCR over periods
    "leverage_acceleration",  # Rate of change of D/E ratio
]

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


def _get_ranges(sector: Optional[str] = None) -> Dict[str, Tuple[float, float]]:
    """Resolve feature ranges: sector-specific if available, else generic."""
    if sector:
        key = sector.lower().replace(" ", "_").replace("manufacturing", "").strip("_")
        # Try exact match, then keyword match
        if key in SECTOR_BENCHMARKS:
            return SECTOR_BENCHMARKS[key]
        for sector_key in SECTOR_BENCHMARKS:
            if sector_key in key or key in sector_key:
                return SECTOR_BENCHMARKS[sector_key]
    return NORMAL_RANGES


def _get_contamination(sector: Optional[str] = None) -> float:
    """Get sector-calibrated contamination rate for Isolation Forest."""
    if sector:
        key = sector.lower().replace(" ", "_").replace("manufacturing", "").strip("_")
        if key in SECTOR_CONTAMINATION:
            return SECTOR_CONTAMINATION[key]
        for sector_key in SECTOR_CONTAMINATION:
            if sector_key in key or key in sector_key:
                return SECTOR_CONTAMINATION[sector_key]
    return DEFAULT_CONTAMINATION


def extract_time_series_features(
    current: Dict[str, Any],
    history: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Derive time-series features from historical metric snapshots.

    Args:
        current: Current period metrics dict.
        history: List of prior period metrics (oldest first).

    Returns:
        Dict of derived feature names to values.
    """
    derived: Dict[str, float] = {}
    all_periods = history + [current]

    # Revenue YoY change
    revenues = [float(p.get("revenue_cagr_3yr", 0) or 0) for p in all_periods]
    if len(revenues) >= 2 and revenues[-2] != 0:
        derived["revenue_yoy_change"] = (revenues[-1] - revenues[-2]) / abs(revenues[-2])
    else:
        derived["revenue_yoy_change"] = 0.0

    # EBITDA margin trend (linear slope)
    margins = [float(p.get("ebitda_margin", 0) or 0) for p in all_periods]
    if len(margins) >= 2:
        x = np.arange(len(margins), dtype=np.float64)
        y = np.array(margins, dtype=np.float64)
        if np.std(x) > 0:
            slope = float(np.corrcoef(x, y)[0, 1] * np.std(y) / np.std(x))
            derived["margin_trend"] = slope if np.isfinite(slope) else 0.0
        else:
            derived["margin_trend"] = 0.0
    else:
        derived["margin_trend"] = 0.0

    # DSCR volatility
    dscrs = [float(p.get("dscr", 0) or 0) for p in all_periods]
    derived["dscr_volatility"] = float(np.std(dscrs)) if len(dscrs) >= 2 else 0.0

    # Leverage acceleration (rate of change of D/E)
    des = [float(p.get("debt_equity_ratio", 0) or 0) for p in all_periods]
    if len(des) >= 2:
        derived["leverage_acceleration"] = des[-1] - des[-2]
    else:
        derived["leverage_acceleration"] = 0.0

    return derived


def _compute_feature_importance(
    features: np.ndarray,
    ranges: Dict[str, Tuple[float, float]],
) -> Dict[str, Dict[str, Any]]:
    """Compute per-feature importance/contribution to anomaly score.

    Returns dict: feature_name -> {contribution, direction, rank, z_score}
    """
    importances = {}
    z_scores = []

    for i, name in enumerate(FEATURE_NAMES):
        val = features[i]
        mean, std = ranges.get(name, (0.0, 1.0))
        if std == 0:
            std = 1.0
        if np.isnan(val):
            z = 0.0
        else:
            z = abs(val - mean) / std
        z_scores.append((name, z, val, mean, std))

    # Rank by Z-score (most anomalous first)
    z_scores.sort(key=lambda x: -x[1])
    total_z = sum(z for _, z, _, _, _ in z_scores)

    for rank, (name, z, val, mean, std) in enumerate(z_scores, 1):
        z_safe = z if np.isfinite(z) else 0.0
        contribution = z_safe / total_z if total_z > 0 and np.isfinite(total_z) else 0.0
        if np.isnan(val):
            direction = "unknown"
        elif val > mean:
            direction = "anomalous_high"
        elif val < mean:
            direction = "anomalous_low"
        else:
            direction = "normal"
        importances[name] = {
            "contribution": round(contribution, 4),
            "direction": direction,
            "rank": rank,
            "z_score": round(z, 2),
            "value": round(float(val), 4),
            "expected": round(mean, 4),
        }

    return importances


def _zscore_detect(features: np.ndarray, ranges: Optional[Dict[str, Tuple[float, float]]] = None) -> Dict[str, Any]:
    """Z-score based anomaly detection (fallback).

    Compares each feature against known normal ranges.
    Returns anomaly score (0 to 1) and per-feature explanations.
    """
    if ranges is None:
        ranges = NORMAL_RANGES

    z_scores = []
    anomalous_features = []

    for i, name in enumerate(FEATURE_NAMES):
        val = features[i]
        mean, std = ranges.get(name, (0.0, 1.0))
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


def detect_anomalies(
    metrics: Dict[str, Any],
    sector: Optional[str] = None,
    historical_metrics: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run anomaly detection on a single company's financial metrics.

    Args:
        metrics: Dict with keys matching FEATURE_NAMES (from ComputedMetrics).
        sector: Optional sector name for sector-specific thresholds.
        historical_metrics: Optional list of prior-period metrics for time-series features.

    Returns:
        Dict with keys:
            - anomaly_score (float, 0 to 1, higher = more anomalous)
            - is_anomaly (bool)
            - anomalous_features (list of dicts with explanations)
            - feature_importance (dict of per-feature contribution)
            - method ("sklearn" or "zscore_fallback")
    """
    _init_model()
    features = extract_features(metrics)
    features = _impute_nans(features)
    ranges = _get_ranges(sector)
    contamination = _get_contamination(sector)

    # Compute time-series derived features if historical data available
    ts_features: Dict[str, float] = {}
    ts_anomalies: List[Dict[str, Any]] = []
    if historical_metrics and len(historical_metrics) >= 1:
        ts_features = extract_time_series_features(metrics, historical_metrics)
        if ts_features.get("revenue_yoy_change", 0) < -0.20:
            ts_anomalies.append({
                "feature": "revenue_yoy_change",
                "value": round(ts_features["revenue_yoy_change"], 4),
                "direction": "low",
                "explanation": f"Revenue declined {abs(ts_features['revenue_yoy_change']):.0%} YoY — sudden reversal",
            })
        if ts_features.get("leverage_acceleration", 0) > 0.5:
            ts_anomalies.append({
                "feature": "leverage_acceleration",
                "value": round(ts_features["leverage_acceleration"], 4),
                "direction": "high",
                "explanation": f"D/E ratio increased by {ts_features['leverage_acceleration']:.2f} in one period — rapid leveraging",
            })
        if ts_features.get("dscr_volatility", 0) > 0.5:
            ts_anomalies.append({
                "feature": "dscr_volatility",
                "value": round(ts_features["dscr_volatility"], 4),
                "direction": "high",
                "explanation": f"DSCR volatility {ts_features['dscr_volatility']:.2f} — unstable debt servicing capacity",
            })

    # Compute feature importance
    importance = _compute_feature_importance(features, ranges)

    if _mode == "sklearn" and _model is not None:
        try:
            from sklearn.ensemble import IsolationForest
            # Sector-calibrated contamination
            model = IsolationForest(
                n_estimators=100,
                contamination=contamination,
                random_state=42,
                n_jobs=1,
            )

            # Generate sector-calibrated synthetic training data
            rng = np.random.RandomState(42)
            n_synthetic = 200
            synthetic = np.zeros((n_synthetic, len(FEATURE_NAMES)))
            for i, name in enumerate(FEATURE_NAMES):
                mean, std = ranges.get(name, (0.0, 1.0))
                synthetic[:, i] = rng.normal(mean, std, n_synthetic)

            model.fit(synthetic)
            sample = features.reshape(1, -1)
            pred = model.predict(sample)[0]      # -1 = anomaly, 1 = normal
            score_raw = model.score_samples(sample)[0]  # Lower = more anomalous

            # Normalize score_raw to [0, 1] where 1 = most anomalous
            anomaly_score = max(0.0, min(1.0, -score_raw))

            # Find anomalous features using Z-score as explanation
            anomalous_features = []
            for i, name in enumerate(FEATURE_NAMES):
                val = features[i]
                mean, std = ranges.get(name, (0.0, 1.0))
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

            anomalous_features.extend(ts_anomalies)

            return {
                "anomaly_score": round(float(anomaly_score), 4),
                "is_anomaly": pred == -1,
                "anomalous_features": anomalous_features,
                "feature_importance": importance,
                "time_series_features": ts_features if ts_features else None,
                "sector_contamination": contamination,
                "method": "sklearn",
                "raw_score": round(float(score_raw), 4),
            }
        except Exception as e:
            logger.warning(f"[IsolationForest] sklearn detection failed: {e} — falling back to Z-score")

    # Fallback: Z-score based
    result = _zscore_detect(features, ranges)
    result["feature_importance"] = importance
    result["time_series_features"] = ts_features if ts_features else None
    result["sector_contamination"] = contamination
    result["anomalous_features"] = result.get("anomalous_features", []) + ts_anomalies
    return result


def detect_batch(
    metrics_list: List[Dict[str, Any]],
    sectors: Optional[List[Optional[str]]] = None,
    historical_metrics_list: Optional[List[Optional[List[Dict[str, Any]]]]] = None,
) -> List[Dict[str, Any]]:
    """Run anomaly detection on multiple companies' metrics."""
    if sectors is None:
        sectors = [None] * len(metrics_list)
    if historical_metrics_list is None:
        historical_metrics_list = [None] * len(metrics_list)
    return [
        detect_anomalies(m, s, h)
        for m, s, h in zip(metrics_list, sectors, historical_metrics_list)
    ]


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
