"""
Intelli-Credit — Worker W3: GST Returns Parser

Extracts structured data from GST Returns:
- GSTR-3B monthly summary (outward + inward supplies)
- GSTR-2A vs 3B reconciliation (ITC claimed vs available)
- Monthly turnover from GST
- ITC reversal, late filing, nil returns

T0 implementation: Mock extraction for demo.
T1+ will integrate PDF/Excel parser + LLM extraction.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker

logger = logging.getLogger(__name__)


class GSTReturnsWorker(BaseDocumentWorker):
    """
    Worker W3 — GST Returns.

    Parses GSTR-3B and GSTR-2A returns to extract turnover data,
    ITC reconciliation, and compliance metrics.
    """

    worker_id = "W3"
    document_type = DocumentType.GST_RETURNS
    display_name = "W3 — GST Returns Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """
        Extract structured data from GST Returns.

        T0: Returns mock data simulating real extraction.

        Returns:
            (extracted_data, pages_processed, confidence)
        """
        filename = os.path.basename(self.file_path)

        await self.emitter.read(
            "Parsing GSTR-3B monthly returns (12 months)...",
            source_document=filename,
            source_page=1,
        )

        await self.emitter.found(
            "GSTIN: 27AABCX1234F1ZQ | XYZ Steel Industries Ltd",
            source_document=filename,
            source_page=1,
            confidence=0.97,
        )

        await self.emitter.read(
            "Extracting outward supplies and ITC data month-by-month...",
            source_document=filename,
            source_page=2,
        )

        await self.emitter.found(
            "Annual GST turnover: ₹139.8 crores (₹13,980 lakhs)",
            source_document=filename,
            source_page=3,
            confidence=0.94,
        )

        await self.emitter.read(
            "Reconciling GSTR-2A (supplier filed) vs GSTR-3B (self-claimed ITC)...",
            source_document=filename,
            source_page=8,
        )

        # ── Month-by-month ITC reconciliation (T1.1 enhancement) ──
        # GSTR-3B = company's self-declared ITC claims
        # GSTR-2A = auto-populated from suppliers' GSTR-1 filings
        monthly_3b_vs_2a = _reconcile_monthly_itc(
            gstr3b_monthly=[
                {"month": "Apr-22", "outward_taxable": 1080.0, "itc_claimed": 38.5},
                {"month": "May-22", "outward_taxable": 1120.0, "itc_claimed": 39.2},
                {"month": "Jun-22", "outward_taxable": 1050.0, "itc_claimed": 37.8},
                {"month": "Jul-22", "outward_taxable": 1210.0, "itc_claimed": 42.1},
                {"month": "Aug-22", "outward_taxable": 1140.0, "itc_claimed": 40.0},
                {"month": "Sep-22", "outward_taxable": 1080.0, "itc_claimed": 38.0},
                {"month": "Oct-22", "outward_taxable": 1200.0, "itc_claimed": 41.5},
                {"month": "Nov-22", "outward_taxable": 1250.0, "itc_claimed": 43.0},
                {"month": "Dec-22", "outward_taxable": 1100.0, "itc_claimed": 39.0},
                {"month": "Jan-23", "outward_taxable": 1170.0, "itc_claimed": 40.5},
                {"month": "Feb-23", "outward_taxable": 1060.0, "itc_claimed": 38.0},
                {"month": "Mar-23", "outward_taxable": 1220.0, "itc_claimed": 44.5},
            ],
            gstr2a_monthly=[
                {"month": "Apr-22", "itc_available": 35.0},
                {"month": "May-22", "itc_available": 36.1},
                {"month": "Jun-22", "itc_available": 34.2},
                {"month": "Jul-22", "itc_available": 37.8},
                {"month": "Aug-22", "itc_available": 36.5},
                {"month": "Sep-22", "itc_available": 35.0},
                {"month": "Oct-22", "itc_available": 37.0},
                {"month": "Nov-22", "itc_available": 38.5},
                {"month": "Dec-22", "itc_available": 35.8},
                {"month": "Jan-23", "itc_available": 36.8},
                {"month": "Feb-23", "itc_available": 34.5},
                {"month": "Mar-23", "itc_available": 33.8},
            ],
        )

        # Emit per-month flags for months with >15% excess
        high_excess_months = [m for m in monthly_3b_vs_2a if m["excess_pct"] > 15]
        moderate_excess_months = [m for m in monthly_3b_vs_2a if 5 < m["excess_pct"] <= 15]

        if high_excess_months:
            worst = max(high_excess_months, key=lambda m: m["excess_pct"])
            await self.emitter.flagged(
                f"High ITC over-claim in {len(high_excess_months)} months. "
                f"Worst: {worst['month']} — claimed ₹{worst['itc_claimed_3b']}L vs "
                f"₹{worst['itc_available_2a']}L available ({worst['excess_pct']:.1f}% excess)",
                source_document=filename,
                source_page=10,
                confidence=0.93,
            )

        if moderate_excess_months:
            await self.emitter.found(
                f"Moderate ITC excess in {len(moderate_excess_months)} months "
                f"(5-15% above GSTR-2A — may be timing differences)",
                source_document=filename,
                source_page=10,
                confidence=0.88,
            )

        # Aggregate reconciliation
        total_3b = sum(m["itc_claimed_3b"] for m in monthly_3b_vs_2a)
        total_2a = sum(m["itc_available_2a"] for m in monthly_3b_vs_2a)
        total_excess = total_3b - total_2a
        aggr_mismatch_pct = (total_excess / total_2a * 100) if total_2a > 0 else 0

        # Classify severity
        if aggr_mismatch_pct > 20:
            severity = "critical"
            severity_label = "CRITICAL — possible fake invoice fraud"
        elif aggr_mismatch_pct > 10:
            severity = "flagged"
            severity_label = "FLAGGED — above industry norm (3-5%)"
        elif aggr_mismatch_pct > 5:
            severity = "moderate"
            severity_label = "MODERATE — marginally above tolerance"
        else:
            severity = "normal"
            severity_label = "NORMAL — within industry tolerance"

        await self.emitter.flagged(
            f"ITC Reconciliation Summary: GSTR-3B claims ₹{total_3b:.1f}L, "
            f"GSTR-2A shows ₹{total_2a:.1f}L available. "
            f"Excess: ₹{total_excess:.1f}L ({aggr_mismatch_pct:.1f}%). "
            f"Severity: {severity_label}",
            source_document=filename,
            source_page=10,
            confidence=0.92,
        )

        await self.emitter.found(
            "Filing regularity: 12/12 months filed on time, no nil returns",
            source_document=filename,
            source_page=12,
            confidence=0.96,
        )

        # Mock extracted data — realistic for XYZ Steel
        extracted_data = {
            "gstin": "27AABCX1234F1ZQ",
            "company_name": "XYZ Steel Industries Ltd",
            "registration_status": "Active",
            "filing_period": {"from": "2022-04", "to": "2023-03"},
            "gstr3b_monthly": [m for m in monthly_3b_vs_2a],
            "aggregate": {
                "annual_turnover": 13680.0,  # lakhs (outward taxable)
                "total_itc_claimed": round(total_3b, 1),
                "total_tax_paid": 1025.0,
                "unit": "lakhs",
            },
            "gstr2a_reconciliation": {
                "itc_claimed_3b": round(total_3b, 1),
                "itc_available_2a": round(total_2a, 1),
                "excess_itc_claimed": round(total_excess, 1),
                "mismatch_pct": round(aggr_mismatch_pct, 1),
                "severity": severity,
                "status": severity,
                "note": f"Company claimed ₹{total_excess:.0f}L more ITC than supported by supplier filings",
                "monthly_detail": monthly_3b_vs_2a,
                "high_excess_months": len(high_excess_months),
                "moderate_excess_months": len(moderate_excess_months),
                "industry_avg_excess_pct": 3.5,
            },
            "filing_compliance": {
                "months_filed": 12,
                "months_late": 0,
                "nil_returns": 0,
                "regularity_pct": 100.0,
            },
            "revenue_from_gst": {
                "annual_turnover": 13680.0,  # lakhs
                "unit": "lakhs",
                "note": "Outward taxable value — used for cross-verification with AR/Bank/ITR",
            },
        }

        pages_processed = 14
        confidence = 0.93

        return extracted_data, pages_processed, confidence


def _reconcile_monthly_itc(
    gstr3b_monthly: list[Dict[str, Any]],
    gstr2a_monthly: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    """
    GSTR-2A vs 3B month-by-month reconciliation.

    For each month:
    - ITC claimed (from GSTR-3B, self-declared)
    - ITC available (from GSTR-2A, auto-populated from suppliers)
    - Excess = claimed - available
    - Excess % = (excess / available) * 100

    Industry norms:
    - ≤5% excess: Normal (timing differences between supplier filing and claim)
    - 5-15% excess: Moderate (requires explanation)
    - >15% excess: High (possible fake invoice / bogus ITC claim)
    - >25% excess: Critical (strong indicator of fake invoicing)
    """
    # Build lookup of 2A data by month
    lookup_2a = {m["month"]: m["itc_available"] for m in gstr2a_monthly}

    result = []
    for row_3b in gstr3b_monthly:
        month = row_3b["month"]
        claimed = row_3b["itc_claimed"]
        available = lookup_2a.get(month, 0)
        excess = claimed - available
        excess_pct = (excess / available * 100) if available > 0 else 0

        result.append({
            "month": month,
            "outward_taxable": row_3b.get("outward_taxable", 0),
            "itc_claimed_3b": claimed,
            "itc_available_2a": available,
            "excess": round(excess, 2),
            "excess_pct": round(excess_pct, 1),
            "flag": (
                "critical" if excess_pct > 25 else
                "high" if excess_pct > 15 else
                "moderate" if excess_pct > 5 else
                "normal"
            ),
        })

    return result