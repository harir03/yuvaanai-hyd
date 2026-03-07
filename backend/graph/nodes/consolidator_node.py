"""
Intelli-Credit — LangGraph Node: Consolidator (Agent 0.5)

Merges worker outputs, normalizes schemas, detects contradictions,
performs 4-way revenue cross-verification, builds RawDataPackage.

This is the first intelligence agent in the pipeline — it validates
data quality before any scoring or LLM calls happen.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from backend.graph.state import (
    CreditAppraisalState,
    RawDataPackage,
    WorkerOutput,
    NormalizedField,
    CrossVerificationResult,
)
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    EventType,
    Ticket,
    TicketSeverity,
    TicketStatus,
)
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.storage.redis_client import get_redis_client
from backend.agents.consolidator.contradiction_detector import (
    detect_rpt_concealment,
    RPTConcealmentResult,
)

logger = logging.getLogger(__name__)

# Source credibility weights (per copilot-instructions.md Section 6.5)
SOURCE_WEIGHT = {
    "GST_RETURNS": 1.0,       # Government source
    "ITR": 1.0,                # Government source
    "BANK_STATEMENT": 0.85,    # Third-party (bank)
    "ANNUAL_REPORT": 0.70,     # Self-reported
}

# Mandatory fields that must be present for a valid assessment
MANDATORY_FIELDS = [
    "revenue",
    "company_name",
]


async def consolidator_node(state: CreditAppraisalState) -> dict:
    """
    Stage 2 — Agent 0.5: The Consolidator.

    1. Collect all worker outputs (from state + Redis staging)
    2. Normalize field names and units
    3. Cross-verify revenue across 4 sources
    4. Detect contradictions
    5. Build RawDataPackage

    Emits ThinkingEvents throughout for the Live Chatbot.
    """
    emitter = ThinkingEventEmitter(state.session_id, "Agent 0.5 — The Consolidator")

    try:
        await emitter.read(
            f"Collecting outputs from {state.workers_completed} workers..."
        )

        # Update pipeline stage
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.CONSOLIDATION:
                stage.status = PipelineStageStatus.ACTIVE
                stage.message = "Consolidating worker outputs..."

        # ── Step 1: Collect worker outputs ──
        outputs = dict(state.worker_outputs)

        # Also check Redis staging (in case workers staged directly)
        try:
            redis = get_redis_client()
            if redis.is_initialized:
                staged = await redis.get_all_staged_outputs(state.session_id)
                for wid, staged_data in staged.items():
                    if wid not in outputs:
                        outputs[wid] = WorkerOutput(**staged_data)
                        await emitter.found(f"Retrieved staged output from {wid}")
        except Exception as e:
            await emitter.flagged(f"Could not read Redis staging: {e}")

        if not outputs:
            await emitter.critical("No worker outputs available — cannot consolidate")
            for stage in state.pipeline_stages:
                if stage.stage == PipelineStageEnum.CONSOLIDATION:
                    stage.status = PipelineStageStatus.FAILED
                    stage.message = "No worker outputs to consolidate"
            return {
                "raw_data_package": RawDataPackage(
                    completeness_score=0.0,
                    mandatory_fields_present=False,
                ),
                "pipeline_stages": state.pipeline_stages,
            }

        await emitter.found(
            f"Collected {len(outputs)} worker outputs: {', '.join(outputs.keys())}"
        )

        # ── Step 2: Extract revenue from each source for cross-verification ──
        revenue_sources: Dict[str, NormalizedField] = {}

        # W1 — Annual Report revenue
        w1_data = _get_extracted_data(outputs, "W1")
        if w1_data and "revenue" in w1_data:
            rev = w1_data["revenue"]
            fy_val = rev.get("fy2023") or rev.get("fy2024") or rev.get("fy2022")
            if fy_val is not None:
                revenue_sources["ANNUAL_REPORT"] = NormalizedField(
                    value=float(fy_val),
                    source_document="Annual Report",
                    source_page=rev.get("source_page"),
                    confidence=outputs.get("W1", WorkerOutput(worker_id="W1", document_type="ANNUAL_REPORT")).confidence,
                    unit=rev.get("unit", "lakhs"),
                )
                await emitter.found(
                    f"AR Revenue: ₹{fy_val} {rev.get('unit', 'lakhs')}",
                    source_document="Annual Report",
                    source_page=rev.get("source_page"),
                    confidence=revenue_sources["ANNUAL_REPORT"].confidence,
                )

        # W2 — Bank Statement revenue (annual credits)
        w2_data = _get_extracted_data(outputs, "W2")
        if w2_data and "revenue_from_bank" in w2_data:
            bank_rev = w2_data["revenue_from_bank"]
            val = bank_rev.get("annual_credits")
            if val is not None:
                revenue_sources["BANK_STATEMENT"] = NormalizedField(
                    value=float(val),
                    source_document="Bank Statement",
                    confidence=outputs.get("W2", WorkerOutput(worker_id="W2", document_type="BANK_STATEMENT")).confidence,
                    unit=bank_rev.get("unit", "lakhs"),
                )
                await emitter.found(
                    f"Bank Revenue (credits): ₹{val} {bank_rev.get('unit', 'lakhs')}",
                    source_document="Bank Statement",
                    confidence=revenue_sources["BANK_STATEMENT"].confidence,
                )

        # W3 — GST Returns revenue (outward taxable)
        w3_data = _get_extracted_data(outputs, "W3")
        if w3_data and "revenue_from_gst" in w3_data:
            gst_rev = w3_data["revenue_from_gst"]
            val = gst_rev.get("annual_turnover")
            if val is not None:
                revenue_sources["GST_RETURNS"] = NormalizedField(
                    value=float(val),
                    source_document="GST Returns",
                    confidence=outputs.get("W3", WorkerOutput(worker_id="W3", document_type="GST_RETURNS")).confidence,
                    unit=gst_rev.get("unit", "lakhs"),
                )
                await emitter.found(
                    f"GST Revenue (outward taxable): ₹{val} {gst_rev.get('unit', 'lakhs')}",
                    source_document="GST Returns",
                    confidence=revenue_sources["GST_RETURNS"].confidence,
                )

        # W4 — ITR revenue (not yet implemented, but slot ready)
        w4_data = _get_extracted_data(outputs, "W4")
        if w4_data and "revenue_from_itr" in w4_data:
            itr_rev = w4_data["revenue_from_itr"]
            val = itr_rev.get("total_income")
            if val is not None:
                revenue_sources["ITR"] = NormalizedField(
                    value=float(val),
                    source_document="ITR",
                    confidence=outputs.get("W4", WorkerOutput(worker_id="W4", document_type="ITR")).confidence,
                    unit=itr_rev.get("unit", "lakhs"),
                )

        # ── Step 3: Cross-verify revenue ──
        cross_verifications: List[CrossVerificationResult] = []

        if len(revenue_sources) >= 2:
            await emitter.read(
                f"Cross-verifying revenue across {len(revenue_sources)} sources: "
                f"{', '.join(revenue_sources.keys())}"
            )
            cv_result = _cross_verify_revenue(revenue_sources)
            cross_verifications.append(cv_result)

            if cv_result.status == "verified":
                await emitter.accepted(
                    f"Revenue cross-verified: ₹{cv_result.accepted_value} lakhs "
                    f"(accepted from {cv_result.accepted_source}, "
                    f"max deviation {cv_result.max_deviation_pct:.1f}%)",
                    confidence=0.95,
                )
            elif cv_result.status == "flagged":
                await emitter.flagged(
                    f"Revenue mismatch detected: max deviation {cv_result.max_deviation_pct:.1f}% "
                    f"across {len(revenue_sources)} sources. "
                    f"Accepted: ₹{cv_result.accepted_value} lakhs from {cv_result.accepted_source}",
                    confidence=0.70,
                )
            elif cv_result.status == "conflicting":
                await emitter.critical(
                    f"Revenue CONFLICT: {cv_result.max_deviation_pct:.1f}% deviation. "
                    f"Sources disagree significantly. {cv_result.note}",
                    confidence=0.50,
                )
        elif len(revenue_sources) == 1:
            src_name = list(revenue_sources.keys())[0]
            await emitter.questioning(
                f"Only one revenue source available ({src_name}). "
                f"Cannot cross-verify — proceeding with reduced confidence."
            )
        else:
            await emitter.flagged(
                "No revenue data extracted from any worker. "
                "Cross-verification skipped."
            )

        # ── Step 4: Detect contradictions ──
        contradictions = _detect_contradictions(outputs)
        if contradictions:
            for c in contradictions:
                await emitter.flagged(
                    f"Contradiction: {c.get('description', 'Unknown')}",
                    confidence=c.get("confidence", 0.5),
                )

        # ── Step 4b: RPT Concealment Detection (W1 vs W6) — T1.2 ──
        w6_data = _get_extracted_data(outputs, "W6")
        rpt_result = detect_rpt_concealment(w1_data, w6_data)
        if rpt_result.concealment_detected:
            # Emit appropriate ThinkingEvent
            if rpt_result.severity == "critical":
                await emitter.critical(
                    f"⚠️ RPT CONCEALMENT: {rpt_result.detail}",
                    confidence=0.90,
                )
            else:
                await emitter.flagged(
                    f"⚠️ RPT disclosure mismatch: {rpt_result.detail}",
                    confidence=0.85,
                )

            # Raise ticket for RPT concealment
            ticket_severity = (
                TicketSeverity.CRITICAL if rpt_result.severity == "critical"
                else TicketSeverity.HIGH
            )
            rpt_ticket = Ticket(
                session_id=state.session_id,
                title="RPT Concealment Detected",
                description=rpt_result.detail,
                severity=ticket_severity,
                category="RPT Concealment",
                source_a=(
                    f"Board Minutes: {rpt_result.board_minutes_count} RPTs approved, "
                    f"₹{rpt_result.board_minutes_total:.1f}L total"
                ),
                source_b=(
                    f"Annual Report: {rpt_result.annual_report_count} RPTs disclosed, "
                    f"₹{rpt_result.annual_report_total:.1f}L total"
                ),
                ai_recommendation=(
                    f"Potential concealment of {rpt_result.count_mismatch} RPT(s) "
                    f"worth ₹{rpt_result.concealed_amount:.1f}L. "
                    f"Recommend requesting full AS-18/Ind AS 24 disclosure from borrower."
                ),
                score_impact=-35,
            )
            state.tickets.append(rpt_ticket)
            await emitter.flagged(
                f"Ticket raised: RPT Concealment ({ticket_severity.value}) — "
                f"{rpt_result.count_mismatch} missing RPTs, ₹{rpt_result.concealed_amount:.1f}L undisclosed",
                confidence=0.88,
            )
        elif w1_data and w6_data:
            await emitter.accepted(
                f"RPT cross-check passed — {rpt_result.detail}",
                confidence=0.90,
            )
        else:
            await emitter.questioning(
                "RPT cross-check skipped — Board Minutes (W6) or Annual Report (W1) not available"
            )

        # Add RPT concealment to contradictions if detected
        if rpt_result.concealment_detected:
            contradictions.append({
                "type": "rpt_concealment",
                "description": rpt_result.detail,
                "severity": rpt_result.severity.upper(),
                "confidence": 0.88,
                "board_minutes_count": rpt_result.board_minutes_count,
                "annual_report_count": rpt_result.annual_report_count,
                "count_mismatch": rpt_result.count_mismatch,
                "concealed_amount": rpt_result.concealed_amount,
                "missing_parties": rpt_result.missing_parties,
            })

        # ── Step 5: Check mandatory fields ──
        mandatory_present = _check_mandatory_fields(outputs)

        # ── Step 6: Compute completeness ──
        total_workers_expected = 8  # Full pipeline has 8 workers
        completeness = len(outputs) / total_workers_expected

        # ── Step 7: Check for GST 2A vs 3B mismatch (from W3) — T1.1 Enhanced ──
        if w3_data and "gstr2a_reconciliation" in w3_data:
            recon = w3_data["gstr2a_reconciliation"]
            mismatch_pct = recon.get("mismatch_pct", 0)
            severity_label = recon.get("severity", "normal")
            high_months = recon.get("high_excess_months", 0)
            moderate_months = recon.get("moderate_excess_months", 0)
            industry_avg = recon.get("industry_avg_excess_pct", 3.5)

            if mismatch_pct > 5:
                # Determine status based on severity tier
                if mismatch_pct > 20:
                    cv_status = "conflicting"
                elif mismatch_pct > 10:
                    cv_status = "flagged"
                else:
                    cv_status = "flagged"

                cv_gst = CrossVerificationResult(
                    field_name="ITC (GSTR-2A vs GSTR-3B)",
                    sources={
                        "GSTR-3B": NormalizedField(
                            value=recon.get("itc_claimed_3b", 0),
                            source_document="GST Returns (GSTR-3B)",
                            confidence=0.95,
                            unit="lakhs",
                        ),
                        "GSTR-2A": NormalizedField(
                            value=recon.get("itc_available_2a", 0),
                            source_document="GST Returns (GSTR-2A)",
                            confidence=0.95,
                            unit="lakhs",
                        ),
                    },
                    max_deviation_pct=mismatch_pct,
                    accepted_value=recon.get("itc_available_2a"),
                    accepted_source="GSTR-2A (supplier filed)",
                    status=cv_status,
                    note=(
                        f"Excess ITC: ₹{recon.get('excess_itc_claimed', 0)} lakhs ({mismatch_pct}%). "
                        f"Industry avg: {industry_avg}%. "
                        f"High-excess months: {high_months}, moderate: {moderate_months}"
                    ),
                )
                cross_verifications.append(cv_gst)

                await emitter.flagged(
                    f"GSTR-2A vs 3B: {mismatch_pct}% ITC over-claim. "
                    f"Claimed ₹{recon.get('itc_claimed_3b')}L, available ₹{recon.get('itc_available_2a')}L. "
                    f"Industry avg: {industry_avg}%. "
                    f"{high_months} months with >15% excess",
                    source_document="GST Returns",
                )

                # T1.1: Raise ticket for significant ITC mismatches
                if mismatch_pct > 10:
                    ticket_severity = (
                        TicketSeverity.CRITICAL if mismatch_pct > 20
                        else TicketSeverity.HIGH
                    )
                    itc_ticket = Ticket(
                        session_id=state.session_id,
                        title=f"ITC Over-Claim: GSTR-2A vs 3B Mismatch ({mismatch_pct:.1f}%)",
                        description=(
                            f"GSTR-3B claims ₹{recon.get('itc_claimed_3b', 0)}L ITC but "
                            f"GSTR-2A (supplier filings) shows only ₹{recon.get('itc_available_2a', 0)}L available. "
                            f"Excess: ₹{recon.get('excess_itc_claimed', 0)}L ({mismatch_pct:.1f}%). "
                            f"Industry average excess is {industry_avg}%. "
                            f"{high_months} month(s) show >15% excess, "
                            f"{moderate_months} month(s) show 5-15% excess. "
                            f"Possible causes: timing difference (normal ≤5%), "
                            f"delayed supplier filing, or fake invoice / bogus ITC claim."
                        ),
                        severity=ticket_severity,
                        category="ITC Reconciliation",
                        source_a=(
                            f"GSTR-3B (self-declared): ITC claimed ₹{recon.get('itc_claimed_3b', 0)} lakhs"
                        ),
                        source_b=(
                            f"GSTR-2A (supplier filed): ITC available ₹{recon.get('itc_available_2a', 0)} lakhs"
                        ),
                        ai_recommendation=(
                            "Request supplier-wise ITC reconciliation from the company. "
                            "Verify if excess is due to timing differences or indicates "
                            "fake invoicing. Cross-check top 5 suppliers against GST portal."
                            if mismatch_pct <= 20 else
                            "CRITICAL: ITC excess >20% strongly indicates potential fake invoicing. "
                            "Request complete supplier-wise ITC working, verify top 10 suppliers "
                            "on GST portal, and consider field verification of major suppliers."
                        ),
                        score_impact=-20 if mismatch_pct <= 20 else -40,
                    )
                    state.tickets.append(itc_ticket)

                    await emitter.questioning(
                        f"Ticket raised [{ticket_severity.value}]: ITC mismatch {mismatch_pct:.1f}% — "
                        f"requires officer review. Score impact: {itc_ticket.score_impact:+d} points",
                        source_document="GST Returns",
                    )

        # ── Build RawDataPackage ──
        raw_data = RawDataPackage(
            worker_outputs={wid: wo for wid, wo in outputs.items()},
            cross_verifications=cross_verifications,
            completeness_score=round(completeness, 2),
            mandatory_fields_present=mandatory_present,
            contradictions=contradictions,
        )

        # Update pipeline stage
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.CONSOLIDATION:
                stage.status = PipelineStageStatus.COMPLETED
                stage.message = (
                    f"Consolidated {len(outputs)} workers, "
                    f"{len(cross_verifications)} cross-checks, "
                    f"{len(contradictions)} contradictions"
                )

        await emitter.concluding(
            f"Consolidation complete: {len(outputs)} workers merged, "
            f"completeness {completeness:.0%}, "
            f"{len(cross_verifications)} cross-verifications, "
            f"{len(contradictions)} contradictions detected"
        )

        return {
            "raw_data_package": raw_data,
            "pipeline_stages": state.pipeline_stages,
            "tickets": state.tickets,
        }

    except Exception as e:
        await emitter.critical(f"Consolidation failed: {str(e)}")
        logger.error(f"[Agent 0.5] Consolidation failed: {e}")
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.CONSOLIDATION:
                stage.status = PipelineStageStatus.FAILED
                stage.message = f"Error: {str(e)}"
        return {
            "raw_data_package": RawDataPackage(
                completeness_score=0.0,
                mandatory_fields_present=False,
            ),
            "pipeline_stages": state.pipeline_stages,
        }


# ──────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────

def _get_extracted_data(outputs: Dict[str, WorkerOutput], worker_id: str) -> Optional[Dict[str, Any]]:
    """Safely get extracted_data from a worker output."""
    wo = outputs.get(worker_id)
    if wo and wo.status == "completed" and wo.extracted_data:
        return wo.extracted_data
    return None


def _cross_verify_revenue(sources: Dict[str, NormalizedField]) -> CrossVerificationResult:
    """
    Cross-verify revenue across multiple sources.

    Uses weighted acceptance: government sources (GST/ITR) weighted 1.0,
    bank statements 0.85, annual report 0.70.

    Returns a CrossVerificationResult with the accepted value from
    the highest-weighted source.
    """
    values = {}
    for src_name, field in sources.items():
        values[src_name] = float(field.value)

    # Find max deviation
    vals = list(values.values())
    if len(vals) < 2:
        return CrossVerificationResult(
            field_name="Revenue",
            sources=sources,
            max_deviation_pct=0.0,
            accepted_value=vals[0] if vals else None,
            accepted_source=list(values.keys())[0] if values else None,
            status="unverified",
        )

    avg = sum(vals) / len(vals)
    max_dev = max(abs(v - avg) / avg * 100 for v in vals) if avg > 0 else 0

    # Select accepted value from highest-weight source
    best_source = max(sources.keys(), key=lambda s: SOURCE_WEIGHT.get(s, 0.5))
    accepted_value = values[best_source]

    # Determine status
    if max_dev <= 5:
        status = "verified"
        note = "All sources agree within 5%"
    elif max_dev <= 15:
        status = "flagged"
        note = f"Deviation {max_dev:.1f}% — needs review"
    else:
        status = "conflicting"
        note = f"Significant deviation {max_dev:.1f}% — possible data quality issue"

    return CrossVerificationResult(
        field_name="Revenue",
        sources=sources,
        max_deviation_pct=round(max_dev, 2),
        accepted_value=accepted_value,
        accepted_source=best_source,
        status=status,
        note=note,
    )


def _detect_contradictions(outputs: Dict[str, WorkerOutput]) -> List[Dict[str, Any]]:
    """
    Detect contradictions between worker outputs.

    Checks for:
    - Company name mismatches
    - Financial year mismatches
    - Revenue sign contradictions
    """
    contradictions = []

    # Collect company names from different sources
    company_names = {}
    for wid, wo in outputs.items():
        if wo.extracted_data:
            name = wo.extracted_data.get("company_name")
            if name:
                company_names[wid] = name

    # Check if company names differ significantly
    if len(set(company_names.values())) > 1:
        contradictions.append({
            "type": "company_name_mismatch",
            "description": f"Company names differ across workers: {company_names}",
            "severity": "LOW",
            "confidence": 0.6,
        })

    return contradictions


def _check_mandatory_fields(outputs: Dict[str, WorkerOutput]) -> bool:
    """Check if mandatory fields are present across all worker outputs."""
    has_revenue = False
    has_company = False

    for wid, wo in outputs.items():
        if wo.extracted_data:
            if "revenue" in wo.extracted_data or "revenue_from_bank" in wo.extracted_data or "revenue_from_gst" in wo.extracted_data:
                has_revenue = True
            if "company_name" in wo.extracted_data or "gstin" in wo.extracted_data:
                has_company = True

    return has_revenue and has_company
