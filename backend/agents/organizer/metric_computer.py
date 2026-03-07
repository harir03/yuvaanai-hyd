"""
Intelli-Credit — Metric Computer (Agent 1.5 sub-module)

Computes all derived financial metrics from normalized 5 Cs data:
 - DSCR (Debt Service Coverage Ratio)
 - Current Ratio
 - D/E (Debt-to-Equity)
 - Working Capital Cycle (days)
 - Revenue CAGR 3yr
 - EBITDA Margin %
 - PAT Margin %
 - Interest Coverage Ratio
 - GST-Bank Divergence %
 - ITR-AR Divergence %
 - Promoter Pledge %
 - Promoter Holding %
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, List

from backend.graph.state import ComputedMetrics, FiveCsMapping, NormalizedField

logger = logging.getLogger(__name__)


def compute_metrics(
    five_cs: FiveCsMapping,
    worker_outputs: Optional[Dict] = None,
) -> ComputedMetrics:
    """
    Compute all derived metrics from the 5 Cs mapping.

    Returns ComputedMetrics with all fields populated.
    Missing data → None (not crash).
    """
    cap = five_cs.capacity   # shorthand
    capital = five_cs.capital
    char = five_cs.character

    metrics = ComputedMetrics()

    # ── DSCR ──
    metrics.dscr = _compute_dscr(cap, capital)

    # ── Current Ratio ──
    metrics.current_ratio = _safe_divide(
        _nf_val(capital.get("current_assets")),
        _nf_val(capital.get("current_liabilities")),
    )

    # ── D/E Ratio ──
    metrics.debt_equity_ratio = _safe_divide(
        _nf_val(capital.get("total_debt")),
        _nf_val(capital.get("net_worth")),
    )

    # ── Revenue CAGR 3yr ──
    metrics.revenue_cagr_3yr = _compute_revenue_cagr(cap)

    # ── EBITDA Margin ──
    metrics.ebitda_margin = _compute_margin(cap, "ebitda", "revenue")

    # ── PAT Margin ──
    metrics.pat_margin = _compute_margin(cap, "pat", "revenue")

    # ── Interest Coverage Ratio ──
    metrics.interest_coverage_ratio = _safe_divide(
        _nf_val(cap.get("ebitda")),
        _nf_val(cap.get("interest_expense")),
    )

    # ── Working Capital Cycle (days) ──
    wc = _compute_wc_cycle(five_cs)
    metrics.working_capital_cycle_days = int(wc) if wc is not None else None

    # ── GST-Bank Divergence % ──
    metrics.gst_bank_divergence_pct = _compute_divergence_pct(
        _nf_val(cap.get("gst_turnover")),
        _nf_val(cap.get("bank_annual_inflow")),
    )

    # ── ITR-AR Divergence % ──
    # need worker_outputs for ITR revenue
    itr_revenue = _get_itr_revenue(worker_outputs) if worker_outputs else None
    ar_revenue = _nf_val(cap.get("revenue"))
    metrics.itr_ar_divergence_pct = _compute_divergence_pct(itr_revenue, ar_revenue)

    # ── Promoter Pledge % ──
    pledge = _nf_val(char.get("promoter_pledge_pct"))
    metrics.promoter_pledge_pct = pledge

    # ── Promoter Holding % ──
    holding = _nf_val(char.get("promoter_holding_pct"))
    metrics.promoter_holding_pct = holding

    _log_metrics(metrics)
    return metrics


# ──────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────

def _nf_val(field: Optional[NormalizedField]) -> Optional[float]:
    """Extract numeric value from a NormalizedField, return None on failure."""
    if field is None:
        return None
    val = field.value
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Divide two values, returning None if impossible."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _compute_dscr(cap: Dict[str, NormalizedField], capital: Dict[str, NormalizedField]) -> Optional[float]:
    """
    DSCR = (EBITDA) / (Interest + Principal repayments).
    If principal repayment not available, use interest expense alone.
    """
    ebitda = _nf_val(cap.get("ebitda"))
    interest = _nf_val(cap.get("interest_expense"))

    if ebitda is None or interest is None:
        return None
    if interest == 0:
        return None

    # Use interest as proxy for total debt service (principal often missing)
    return round(ebitda / interest, 4)


def _compute_revenue_cagr(cap: Dict[str, NormalizedField]) -> Optional[float]:
    """
    Compute 3-year Revenue CAGR from revenue_3yr or revenue_history.

    revenue_3yr should be a list of 3+ annual values [oldest → newest].
    """
    hist_field = cap.get("revenue_3yr") or cap.get("revenue_history")
    if hist_field is None:
        return None

    values = hist_field.value
    if not isinstance(values, (list, tuple)) or len(values) < 2:
        return None

    try:
        oldest = float(values[0])
        newest = float(values[-1])
    except (TypeError, ValueError):
        return None

    if oldest <= 0:
        return None

    n = len(values) - 1
    cagr = (newest / oldest) ** (1.0 / n) - 1.0
    return round(cagr * 100, 2)  # percentage


def _compute_margin(cap: Dict[str, NormalizedField], numerator_key: str,
                     denominator_key: str) -> Optional[float]:
    """Compute a margin (e.g. EBITDA/Revenue) as a percentage."""
    num = _nf_val(cap.get(numerator_key))
    den = _nf_val(cap.get(denominator_key))
    if num is None or den is None or den == 0:
        return None
    return round((num / den) * 100, 2)


def _compute_wc_cycle(five_cs: FiveCsMapping) -> Optional[float]:
    """
    Working Capital Cycle (in days) = Inventory Days + Receivable Days - Payable Days.
    Approximation using annual revenue.
    """
    revenue = _nf_val(five_cs.capacity.get("revenue"))
    inventory = _nf_val(five_cs.collateral.get("inventory"))
    receivables = _nf_val(five_cs.collateral.get("receivables"))

    if revenue is None or revenue == 0:
        return None

    inv_days = (inventory / revenue * 365) if inventory else 0
    rec_days = (receivables / revenue * 365) if receivables else 0
    # Payable days omitted (no payables data typically) → just inv + rec
    cycle = inv_days + rec_days
    return round(cycle, 1) if cycle > 0 else None


def _compute_divergence_pct(
    source_a: Optional[float],
    source_b: Optional[float],
) -> Optional[float]:
    """
    Divergence % = abs(A - B) / max(A, B) * 100.
    Used for GST-Bank and ITR-AR checks.
    """
    if source_a is None or source_b is None:
        return None
    max_val = max(abs(source_a), abs(source_b))
    if max_val == 0:
        return 0.0
    return round(abs(source_a - source_b) / max_val * 100, 2)


def _get_itr_revenue(worker_outputs: Dict) -> Optional[float]:
    """Extract revenue from ITR worker (W4)."""
    w4 = worker_outputs.get("W4")
    if w4 is None:
        return None
    data = w4.extracted_data if hasattr(w4, "extracted_data") else (w4 if isinstance(w4, dict) else {})
    rev = data.get("revenue") or data.get("total_income")
    if rev is None:
        return None
    try:
        return float(rev)
    except (TypeError, ValueError):
        return None


def _log_metrics(m: ComputedMetrics):
    """Log computed metrics summary."""
    parts = []
    if m.dscr is not None:
        parts.append(f"DSCR={m.dscr}x")
    if m.current_ratio is not None:
        parts.append(f"CR={m.current_ratio}x")
    if m.debt_equity_ratio is not None:
        parts.append(f"D/E={m.debt_equity_ratio}")
    if m.ebitda_margin is not None:
        parts.append(f"EBITDA%={m.ebitda_margin}%")
    if m.revenue_cagr_3yr is not None:
        parts.append(f"CAGR={m.revenue_cagr_3yr}%")

    logger.info(f"[MetricComputer] {', '.join(parts) if parts else 'No metrics computed'}")
