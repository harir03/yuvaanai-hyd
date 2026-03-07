"""
Intelli-Credit — Contradiction Detector: RPT Concealment Detection

T1.2: Compares Related Party Transactions (RPTs) approved in Board Minutes (W6)
against RPTs disclosed in the Annual Report (W1).

Detection logic:
- Count mismatch: Board Minutes show N RPTs, AR discloses fewer
- Amount mismatch: Total RPT amounts significantly differ
- Missing counterparties: Specific parties in Board Minutes but not in AR disclosure

Concealment triggers a CRITICAL ThinkingEvent and HIGH/CRITICAL severity ticket.
Scoring impact: -35 points in CHARACTER module.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RPTEntry:
    """A single Related Party Transaction."""
    party: str
    amount: float  # In lakhs
    nature: str  # e.g. "purchases", "services", "donations"


@dataclass
class RPTConcealmentResult:
    """Result of RPT concealment analysis."""
    concealment_detected: bool
    board_minutes_count: int
    annual_report_count: int
    count_mismatch: int  # How many RPTs missing from AR
    board_minutes_total: float  # Total amount in Board Minutes (lakhs)
    annual_report_total: float  # Total amount in AR (lakhs)
    concealed_amount: float  # Amount not disclosed (lakhs)
    missing_parties: List[str]  # Counterparties in BM but not in AR
    severity: str  # "none", "moderate", "high", "critical"
    detail: str  # Human-readable summary


def detect_rpt_concealment(
    w1_data: Optional[Dict[str, Any]],
    w6_data: Optional[Dict[str, Any]],
) -> RPTConcealmentResult:
    """
    Cross-reference RPTs from Board Minutes (W6) against Annual Report (W1).

    Board Minutes record RPT *approvals* — the definitive list of what was
    approved by the board. The Annual Report's RPT disclosure (AS-18 / Ind AS 24)
    must list AT LEAST as many RPTs as were approved. If it lists fewer, that's
    active concealment.

    Args:
        w1_data: Extracted data from Worker W1 (Annual Report)
        w6_data: Extracted data from Worker W6 (Board Minutes)

    Returns:
        RPTConcealmentResult with full analysis
    """
    # Default: no analysis possible if either source missing
    if not w1_data or not w6_data:
        return RPTConcealmentResult(
            concealment_detected=False,
            board_minutes_count=0,
            annual_report_count=0,
            count_mismatch=0,
            board_minutes_total=0.0,
            annual_report_total=0.0,
            concealed_amount=0.0,
            missing_parties=[],
            severity="none",
            detail="Cannot perform RPT cross-check — missing W1 or W6 data",
        )

    # Extract RPT data from Annual Report (W1)
    ar_rpts = w1_data.get("rpts", {})
    ar_count = ar_rpts.get("count", 0)
    ar_total = float(ar_rpts.get("total_amount", 0))
    ar_transactions = ar_rpts.get("transactions", [])

    # Extract RPT approvals from Board Minutes (W6)
    bm_rpt_approvals = w6_data.get("rpt_approvals", {})
    bm_count = bm_rpt_approvals.get("count", 0)
    bm_total = float(bm_rpt_approvals.get("total_amount", 0))
    bm_transactions = bm_rpt_approvals.get("transactions", [])

    # If Board Minutes has no RPT data, we can't cross-check
    if bm_count == 0 and ar_count == 0:
        return RPTConcealmentResult(
            concealment_detected=False,
            board_minutes_count=0,
            annual_report_count=0,
            count_mismatch=0,
            board_minutes_total=0.0,
            annual_report_total=0.0,
            concealed_amount=0.0,
            missing_parties=[],
            severity="none",
            detail="No RPTs in either Board Minutes or Annual Report",
        )

    if bm_count == 0:
        return RPTConcealmentResult(
            concealment_detected=False,
            board_minutes_count=0,
            annual_report_count=ar_count,
            count_mismatch=0,
            board_minutes_total=0.0,
            annual_report_total=ar_total,
            concealed_amount=0.0,
            missing_parties=[],
            severity="none",
            detail="No RPT approvals in Board Minutes — cannot cross-verify",
        )

    # ── Count comparison ──
    count_mismatch = bm_count - ar_count  # Positive = RPTs missing from AR

    # ── Amount comparison ──
    concealed_amount = max(0.0, bm_total - ar_total)

    # ── Counterparty matching ──
    # Normalize party names for fuzzy matching
    ar_parties_normalized = {
        _normalize_party_name(t.get("party", ""))
        for t in ar_transactions
        if t.get("party")
    }
    bm_parties_normalized = {}
    for t in bm_transactions:
        party = t.get("party", "")
        if party:
            bm_parties_normalized[_normalize_party_name(party)] = party

    # Find parties in Board Minutes but not in Annual Report
    missing_parties = []
    for norm_name, original_name in bm_parties_normalized.items():
        if norm_name not in ar_parties_normalized:
            missing_parties.append(original_name)

    # ── Determine concealment severity ──
    concealment_detected = False
    severity = "none"

    if count_mismatch > 0 or len(missing_parties) > 0:
        concealment_detected = True
        # Severity based on magnitude
        if count_mismatch >= 3 or concealed_amount > 1000:
            severity = "critical"
        elif count_mismatch >= 2 or concealed_amount > 500:
            severity = "high"
        elif count_mismatch >= 1:
            severity = "moderate"

    # Also check for significant amount mismatch even if count matches
    if not concealment_detected and bm_total > 0:
        amount_diff_pct = abs(bm_total - ar_total) / bm_total * 100
        if amount_diff_pct > 20 and bm_total > ar_total:
            concealment_detected = True
            severity = "moderate" if amount_diff_pct <= 40 else "high"

    # Build detail message
    if concealment_detected:
        parts = []
        if count_mismatch > 0:
            parts.append(
                f"Board Minutes record {bm_count} RPT approvals but AR discloses only {ar_count} "
                f"({count_mismatch} concealed)"
            )
        if concealed_amount > 0:
            parts.append(
                f"BM total ₹{bm_total:.1f}L vs AR disclosed ₹{ar_total:.1f}L "
                f"(₹{concealed_amount:.1f}L undisclosed)"
            )
        if missing_parties:
            parts.append(f"Missing counterparties: {', '.join(missing_parties)}")
        detail = ". ".join(parts)
    else:
        detail = (
            f"RPT disclosure consistent — BM: {bm_count} RPTs (₹{bm_total:.1f}L), "
            f"AR: {ar_count} RPTs (₹{ar_total:.1f}L)"
        )

    return RPTConcealmentResult(
        concealment_detected=concealment_detected,
        board_minutes_count=bm_count,
        annual_report_count=ar_count,
        count_mismatch=max(0, count_mismatch),
        board_minutes_total=bm_total,
        annual_report_total=ar_total,
        concealed_amount=concealed_amount,
        missing_parties=missing_parties,
        severity=severity,
        detail=detail,
    )


def _normalize_party_name(name: str) -> str:
    """
    Normalize a party name for fuzzy matching.

    Removes common suffixes (Pvt, Ltd, Private, Limited),
    extra whitespace, and lowercases.
    """
    if not name:
        return ""
    normalized = name.lower().strip()
    # Remove common corporate suffixes
    for suffix in [
        " private limited", " pvt ltd", " pvt. ltd.", " pvt. ltd",
        " limited", " ltd", " ltd.", " llp",
    ]:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    # Remove parenthetical descriptions like "(promoter entity)"
    if "(" in normalized:
        normalized = normalized[: normalized.index("(")].strip()
    return normalized
