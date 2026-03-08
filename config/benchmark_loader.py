"""
Intelli-Credit — Sector Benchmark Loader

Loads sector-specific financial benchmarks from JSON.
Used by the scoring modules to compare company metrics against
industry standards. Falls back to _default when sector not found.
"""

import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_BENCHMARKS_DIR = os.path.join(os.path.dirname(__file__), "benchmarks")
_BENCHMARKS_FILE = os.path.join(_BENCHMARKS_DIR, "sector_benchmarks.json")

# Cached in memory after first load
_benchmarks_cache: Optional[Dict[str, Any]] = None

# Sector name normalization map
_SECTOR_ALIASES = {
    "manufacturing": "manufacturing",
    "steel": "manufacturing",
    "chemicals": "manufacturing",
    "auto": "manufacturing",
    "auto components": "manufacturing",
    "it": "it_services",
    "it services": "it_services",
    "technology": "it_services",
    "software": "it_services",
    "saas": "it_services",
    "infrastructure": "infrastructure",
    "real estate": "infrastructure",
    "construction": "infrastructure",
    "power": "infrastructure",
    "pharma": "pharma",
    "pharmaceuticals": "pharma",
    "healthcare": "pharma",
    "biotech": "pharma",
    "fmcg": "fmcg",
    "consumer goods": "fmcg",
    "food & beverages": "fmcg",
    "textiles": "textiles",
    "garments": "textiles",
    "nbfc": "nbfc",
    "financial services": "nbfc",
    "microfinance": "nbfc",
    "housing finance": "nbfc",
    "metals": "metals_mining",
    "metals & mining": "metals_mining",
    "mining": "metals_mining",
}


def _load_benchmarks() -> Dict[str, Any]:
    """Load benchmarks from JSON file, with caching."""
    global _benchmarks_cache
    if _benchmarks_cache is not None:
        return _benchmarks_cache

    if not os.path.exists(_BENCHMARKS_FILE):
        logger.warning(f"[Benchmarks] File not found: {_BENCHMARKS_FILE}")
        _benchmarks_cache = {}
        return _benchmarks_cache

    with open(_BENCHMARKS_FILE, "r", encoding="utf-8") as f:
        _benchmarks_cache = json.load(f)

    logger.info(f"[Benchmarks] Loaded {len(_benchmarks_cache)} sectors")
    return _benchmarks_cache


def get_sector_benchmark(sector: str) -> Dict[str, Any]:
    """
    Get benchmarks for a sector.

    Args:
        sector: Sector name (case-insensitive, alias-resolved)

    Returns:
        Sector benchmark dict with metrics, risk_factors, etc.
        Falls back to _default if sector not found.
    """
    benchmarks = _load_benchmarks()

    # Normalize sector name
    normalized = _SECTOR_ALIASES.get(sector.lower().strip(), sector.lower().strip())

    if normalized in benchmarks:
        return benchmarks[normalized]

    # Fall back to default
    default = benchmarks.get("_default", {})
    if default:
        logger.info(f"[Benchmarks] No specific benchmarks for '{sector}', using defaults")
    return default


def get_metric_benchmark(sector: str, metric_name: str) -> Optional[Dict[str, Any]]:
    """
    Get benchmark for a specific metric in a sector.

    Args:
        sector: Sector name
        metric_name: Metric key (e.g. 'dscr', 'debt_equity_ratio')

    Returns:
        Dict with benchmark, excellent, poor, unit, lower_is_better
        or None if metric not found.
    """
    sector_data = get_sector_benchmark(sector)
    metrics = sector_data.get("metrics", {})
    return metrics.get(metric_name)


def get_all_sectors() -> list[str]:
    """Get list of all available sector keys (excluding _default)."""
    benchmarks = _load_benchmarks()
    return [k for k in benchmarks.keys() if not k.startswith("_")]


def compare_to_benchmark(sector: str, metric_name: str, value: float) -> str:
    """
    Compare a value to sector benchmark and return rating.

    Returns: "excellent", "good", "average", "below_average", "poor"
    """
    metric = get_metric_benchmark(sector, metric_name)
    if not metric:
        return "unknown"

    benchmark = metric["benchmark"]
    excellent = metric["excellent"]
    poor = metric["poor"]
    lower_is_better = metric.get("lower_is_better", False)

    if lower_is_better:
        if value <= excellent:
            return "excellent"
        elif value <= benchmark:
            return "good"
        elif value <= (benchmark + poor) / 2:
            return "average"
        elif value <= poor:
            return "below_average"
        else:
            return "poor"
    else:
        if value >= excellent:
            return "excellent"
        elif value >= benchmark:
            return "good"
        elif value >= (benchmark + poor) / 2:
            return "average"
        elif value >= poor:
            return "below_average"
        else:
            return "poor"


def clear_cache():
    """Clear the benchmarks cache (for testing)."""
    global _benchmarks_cache
    _benchmarks_cache = None
