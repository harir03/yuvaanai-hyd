"""
Intelli-Credit — Five Cs Mapper (Agent 1.5 sub-module)

Maps raw consolidated data from worker outputs to the 5 Cs framework:
  - Capacity: Revenue, EBITDA, PAT, cash flow, repayment ability
  - Character: Promoter track record, RPT disclosure, governance
  - Capital: Net worth, debt, equity, leverage
  - Collateral: Coverage ratio, asset quality, lien status
  - Conditions: Order book, sector outlook, regulatory environment
"""

import logging
from typing import Dict, Any, Optional

from backend.graph.state import (
    FiveCsMapping,
    NormalizedField,
    WorkerOutput,
)

logger = logging.getLogger(__name__)


def map_to_five_cs(
    worker_outputs: Dict[str, WorkerOutput],
    raw_data: Optional[Dict[str, Any]] = None,
) -> FiveCsMapping:
    """
    Map all worker-extracted data to the 5 Cs framework.

    Each data point is tagged with source document, page, excerpt, confidence.
    """
    mapping = FiveCsMapping()

    # Extract data safely from workers
    w1 = _get_extracted(worker_outputs, "W1")  # Annual Report
    w2 = _get_extracted(worker_outputs, "W2")  # Bank Statement
    w3 = _get_extracted(worker_outputs, "W3")  # GST Returns
    w4 = _get_extracted(worker_outputs, "W4")  # ITR
    w5 = _get_extracted(worker_outputs, "W5")  # Legal Notice
    w6 = _get_extracted(worker_outputs, "W6")  # Board Minutes
    w7 = _get_extracted(worker_outputs, "W7")  # Shareholding
    w8 = _get_extracted(worker_outputs, "W8")  # Rating Report

    # ── CAPACITY ──
    _map_capacity(mapping, w1, w2, w3, w4, worker_outputs)

    # ── CHARACTER ──
    _map_character(mapping, w1, w5, w6, w7, w8, worker_outputs)

    # ── CAPITAL ──
    _map_capital(mapping, w1, w4, worker_outputs)

    # ── COLLATERAL ──
    _map_collateral(mapping, w1, w2, worker_outputs)

    # ── CONDITIONS ──
    _map_conditions(mapping, w1, w8, worker_outputs)

    logger.info(
        f"[FiveCsMapper] Mapped: "
        f"Capacity={len(mapping.capacity)}, Character={len(mapping.character)}, "
        f"Capital={len(mapping.capital)}, Collateral={len(mapping.collateral)}, "
        f"Conditions={len(mapping.conditions)} fields"
    )

    return mapping


def _get_extracted(outputs: Dict[str, WorkerOutput], worker_id: str) -> Dict[str, Any]:
    """Safely extract data from a worker output."""
    wo = outputs.get(worker_id)
    if wo is None:
        return {}
    if hasattr(wo, "extracted_data"):
        return wo.extracted_data or {}
    if isinstance(wo, dict):
        return wo.get("extracted_data", wo)
    return {}


def _get_confidence(outputs: Dict[str, WorkerOutput], worker_id: str) -> float:
    """Get the confidence score for a worker."""
    wo = outputs.get(worker_id)
    if wo and hasattr(wo, "confidence"):
        return wo.confidence
    return 0.70  # default


def _nf(value: Any, source: str, confidence: float, page: Optional[int] = None,
         excerpt: Optional[str] = None, unit: Optional[str] = None) -> NormalizedField:
    """Shortcut to create NormalizedField."""
    return NormalizedField(
        value=value, source_document=source, source_page=page,
        source_excerpt=excerpt, confidence=confidence, unit=unit,
    )


def _map_capacity(mapping: FiveCsMapping, w1: dict, w2: dict, w3: dict, w4: dict,
                   outputs: Dict[str, WorkerOutput]):
    """Map Capacity (C1) — repayment ability, revenue, cash flow."""
    w1_conf = _get_confidence(outputs, "W1")
    w4_conf = _get_confidence(outputs, "W4")

    # Revenue
    if "revenue" in w1:
        mapping.capacity["revenue"] = _nf(w1["revenue"], "Annual Report", w1_conf, unit="₹ Cr")
    elif "revenue" in w4:
        mapping.capacity["revenue"] = _nf(w4["revenue"], "ITR", w4_conf, unit="₹ Cr")

    # EBITDA
    if "ebitda" in w1:
        mapping.capacity["ebitda"] = _nf(w1["ebitda"], "Annual Report", w1_conf, unit="₹ Cr")

    # PAT (Profit After Tax)
    if "pat" in w1:
        mapping.capacity["pat"] = _nf(w1["pat"], "Annual Report", w1_conf, unit="₹ Cr")

    # Interest expense
    if "interest_expense" in w1:
        mapping.capacity["interest_expense"] = _nf(
            w1["interest_expense"], "Annual Report", w1_conf, unit="₹ Cr")

    # Bank cash flow
    if "annual_inflow" in w2:
        mapping.capacity["bank_annual_inflow"] = _nf(
            w2["annual_inflow"], "Bank Statement", _get_confidence(outputs, "W2"), unit="₹ Cr")

    # GST turnover
    if "annual_turnover" in w3:
        mapping.capacity["gst_turnover"] = _nf(
            w3["annual_turnover"], "GST Returns", 1.0, unit="₹ Cr")  # govt source → 1.0

    # EMI regularity
    emi = w2.get("emi_regularity", {})
    if emi and isinstance(emi, dict):
        if "payment_regularity_pct" in emi:
            mapping.capacity["emi_regularity"] = _nf(
                emi["payment_regularity_pct"], "Bank Statement",
                _get_confidence(outputs, "W2"), unit="%")

    # Revenue history for CAGR
    for key in ["revenue_3yr", "revenue_history"]:
        if key in w1:
            mapping.capacity[key] = _nf(w1[key], "Annual Report", w1_conf)


def _map_character(mapping: FiveCsMapping, w1: dict, w5: dict, w6: dict, w7: dict,
                    w8: dict, outputs: Dict[str, WorkerOutput]):
    """Map Character (C2) — promoter integrity, governance, track record."""
    w1_conf = _get_confidence(outputs, "W1")

    # Promoter holding percentage
    if "promoter_holding_pct" in w7:
        mapping.character["promoter_holding_pct"] = _nf(
            w7["promoter_holding_pct"], "Shareholding Pattern",
            _get_confidence(outputs, "W7"), unit="%")

    # Promoter pledge percentage
    if "promoter_pledge_pct" in w7:
        mapping.character["promoter_pledge_pct"] = _nf(
            w7["promoter_pledge_pct"], "Shareholding Pattern",
            _get_confidence(outputs, "W7"), unit="%")

    # RPT disclosure
    rpts = w1.get("rpts", {})
    if rpts:
        count = len(rpts.get("transactions", [])) if isinstance(rpts, dict) else 0
        mapping.character["rpt_count"] = _nf(count, "Annual Report", w1_conf)

    # Board minutes RPT approvals
    bm_rpts = w6.get("rpt_approvals", [])
    if bm_rpts:
        mapping.character["board_rpt_approvals"] = _nf(
            len(bm_rpts), "Board Minutes", _get_confidence(outputs, "W6"))

    # Litigation
    if "cases" in w5:
        mapping.character["pending_cases"] = _nf(
            len(w5["cases"]), "Legal Notice", _get_confidence(outputs, "W5"))

    # Auditor qualifications
    auditor = w1.get("auditor", {})
    if auditor and isinstance(auditor, dict):
        if "qualifications" in auditor:
            mapping.character["auditor_qualifications"] = _nf(
                len(auditor["qualifications"]), "Annual Report", w1_conf)

    # CFO changes (governance signal)
    if "cfo_changes" in w6:
        mapping.character["cfo_changes"] = _nf(
            w6["cfo_changes"], "Board Minutes", _get_confidence(outputs, "W6"))

    # Rating
    if "current_rating" in w8 or "rating" in w8:
        rating_val = w8.get("current_rating", w8.get("rating", ""))
        mapping.character["credit_rating"] = _nf(
            rating_val, "Rating Report", _get_confidence(outputs, "W8"))


def _map_capital(mapping: FiveCsMapping, w1: dict, w4: dict,
                  outputs: Dict[str, WorkerOutput]):
    """Map Capital (C3) — balance sheet strength, leverage."""
    w1_conf = _get_confidence(outputs, "W1")
    w4_conf = _get_confidence(outputs, "W4")

    # Net worth (prefer ITR as govt source)
    if "net_worth" in w4:
        mapping.capital["net_worth"] = _nf(w4["net_worth"], "ITR", w4_conf, unit="₹ Cr")
    elif "net_worth" in w1:
        mapping.capital["net_worth"] = _nf(w1["net_worth"], "Annual Report", w1_conf, unit="₹ Cr")

    # Total debt
    if "total_debt" in w1:
        mapping.capital["total_debt"] = _nf(w1["total_debt"], "Annual Report", w1_conf, unit="₹ Cr")
    elif "debt" in w1:
        mapping.capital["total_debt"] = _nf(w1["debt"], "Annual Report", w1_conf, unit="₹ Cr")

    # Equity
    if "equity" in w1:
        mapping.capital["equity"] = _nf(w1["equity"], "Annual Report", w1_conf, unit="₹ Cr")

    # Current assets / liabilities
    if "current_assets" in w1:
        mapping.capital["current_assets"] = _nf(
            w1["current_assets"], "Annual Report", w1_conf, unit="₹ Cr")
    if "current_liabilities" in w1:
        mapping.capital["current_liabilities"] = _nf(
            w1["current_liabilities"], "Annual Report", w1_conf, unit="₹ Cr")


def _map_collateral(mapping: FiveCsMapping, w1: dict, w2: dict,
                     outputs: Dict[str, WorkerOutput]):
    """Map Collateral (C4) — security, asset quality."""
    w1_conf = _get_confidence(outputs, "W1")

    # Fixed assets
    if "fixed_assets" in w1:
        mapping.collateral["fixed_assets"] = _nf(
            w1["fixed_assets"], "Annual Report", w1_conf, unit="₹ Cr")

    # Inventory
    if "inventory" in w1:
        mapping.collateral["inventory"] = _nf(
            w1["inventory"], "Annual Report", w1_conf, unit="₹ Cr")

    # Receivables
    if "receivables" in w1:
        mapping.collateral["receivables"] = _nf(
            w1["receivables"], "Annual Report", w1_conf, unit="₹ Cr")


def _map_conditions(mapping: FiveCsMapping, w1: dict, w8: dict,
                     outputs: Dict[str, WorkerOutput]):
    """Map Conditions (C5) — external factors, sector, regulatory."""
    # Order book
    if "order_book" in w1:
        mapping.conditions["order_book"] = _nf(
            w1["order_book"], "Annual Report", _get_confidence(outputs, "W1"), unit="₹ Cr")

    # Rating outlook
    if "outlook" in w8:
        mapping.conditions["rating_outlook"] = _nf(
            w8["outlook"], "Rating Report", _get_confidence(outputs, "W8"))

    # Sector mentioned in rating
    if "sector_outlook" in w8:
        mapping.conditions["sector_outlook"] = _nf(
            w8["sector_outlook"], "Rating Report", _get_confidence(outputs, "W8"))
