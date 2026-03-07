"""
Intelli-Credit — LangGraph Node: Evidence Package Builder

Stage 7 — Organizes ALL findings into a structured, fully cited package.
Raises tickets for ambiguous or conflicting findings.
Agent 3 reads ONLY this package. It never touches raw documents,
Neo4j, or the Insight Store directly.
"""

import logging
from backend.graph.state import CreditAppraisalState
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    EventType,
    TicketSeverity,
)
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.agents.evidence.package_builder import build_evidence_package
from backend.agents.evidence.ticket_raiser import raise_tickets

logger = logging.getLogger(__name__)


async def evidence_node(state: CreditAppraisalState) -> dict:
    """
    Stage 7 — Evidence Package Builder + Ticket Raiser.

    1. Builds a complete EvidencePackage from all upstream data
    2. Categorizes findings as verified/uncertain/rejected/conflicting
    3. Raises tickets for ambiguity, contradictions, ML signals
    4. Sets tickets_blocking flag if HIGH/CRITICAL tickets exist
    """
    emitter = ThinkingEventEmitter(state.session_id, "Evidence Builder")

    try:
        # Update pipeline stage
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.EVIDENCE:
                stage.status = PipelineStageStatus.ACTIVE
                stage.message = "Building evidence package..."

        # ── Step 1: Build evidence package ──
        await emitter.emit(EventType.READ, "Collecting findings from all upstream stages...")

        evidence = build_evidence_package(state)

        await emitter.emit(
            EventType.FOUND,
            f"Evidence package assembled: "
            f"{len(evidence.verified_findings)} verified, "
            f"{len(evidence.uncertain_findings)} uncertain, "
            f"{len(evidence.rejected_findings)} rejected, "
            f"{len(evidence.conflicting_findings)} conflicting findings"
        )

        # ── Step 2: Emit details about cross-verifications ──
        for cv in evidence.cross_verifications:
            if cv.status == "verified":
                await emitter.emit(
                    EventType.ACCEPTED,
                    f"Cross-verified: {cv.field_name} — {cv.max_deviation_pct:.1f}% deviation ({len(cv.sources)} sources)"
                )
            elif cv.status == "flagged":
                await emitter.emit(
                    EventType.QUESTIONING,
                    f"Flagged: {cv.field_name} — {cv.max_deviation_pct:.1f}% deviation, needs review"
                )
            elif cv.status == "conflicting":
                await emitter.emit(
                    EventType.FLAGGED,
                    f"Conflicting: {cv.field_name} — {cv.max_deviation_pct:.1f}% deviation across sources"
                )

        # ── Step 3: Emit compound insight summary ──
        if evidence.compound_insights:
            critical = [i for i in evidence.compound_insights if i.severity == "CRITICAL"]
            high = [i for i in evidence.compound_insights if i.severity == "HIGH"]
            if critical:
                await emitter.emit(
                    EventType.CRITICAL,
                    f"{len(critical)} CRITICAL compound insights: "
                    + "; ".join(i.insight_type for i in critical[:3])
                )
            if high:
                await emitter.emit(
                    EventType.FLAGGED,
                    f"{len(high)} HIGH severity insights from graph reasoning"
                )

        # ── Step 4: Raise tickets ──
        await emitter.emit(EventType.READ, "Scanning for ticket-worthy conditions...")

        tickets = raise_tickets(state.session_id, evidence)

        # Record ticket IDs in evidence package
        evidence.tickets_raised = [t.id for t in tickets]

        # Determine if any blocking tickets exist
        blocking = any(
            t.severity in (TicketSeverity.HIGH, TicketSeverity.CRITICAL)
            for t in tickets
        )

        if tickets:
            for ticket in tickets:
                event_type = (
                    EventType.CRITICAL if ticket.severity == TicketSeverity.CRITICAL
                    else EventType.FLAGGED if ticket.severity == TicketSeverity.HIGH
                    else EventType.QUESTIONING
                )
                await emitter.emit(
                    event_type,
                    f"Ticket [{ticket.severity.value}]: {ticket.title} (impact: {ticket.score_impact:+d} pts)"
                )

            if blocking:
                await emitter.emit(
                    EventType.FLAGGED,
                    f"⚠️ {sum(1 for t in tickets if t.severity != TicketSeverity.LOW)} blocking ticket(s) — "
                    "pipeline will pause at Agent 3 until resolved"
                )
        else:
            await emitter.emit(
                EventType.ACCEPTED,
                "No tickets raised — evidence is clean, proceeding to scoring"
            )

        # ── Step 5: Conclude ──
        await emitter.emit(
            EventType.CONCLUDING,
            f"Evidence package complete. {len(evidence.verified_findings)} verified claims, "
            f"{len(tickets)} tickets raised. "
            f"{'Pipeline BLOCKED — resolve tickets before scoring.' if blocking else 'Ready for Agent 3.'}"
        )

        # Update pipeline stage
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.EVIDENCE:
                stage.status = PipelineStageStatus.COMPLETED
                stage.message = (
                    f"Evidence assembled: {len(evidence.verified_findings)} verified, {len(tickets)} tickets"
                )

        return {
            "evidence_package": evidence,
            "tickets": tickets,
            "tickets_blocking": blocking,
            "pipeline_stages": state.pipeline_stages,
        }

    except Exception as e:
        logger.error(f"[Evidence Builder] Failed: {e}")
        await emitter.emit(EventType.CRITICAL, f"Evidence package build failed: {str(e)}")

        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.EVIDENCE:
                stage.status = PipelineStageStatus.FAILED
                stage.message = f"Failed: {str(e)}"

        raise

