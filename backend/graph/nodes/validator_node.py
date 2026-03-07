"""
Intelli-Credit — LangGraph Node: Validator

Stage 3 — Enforces technical completeness between consolidation and organization.

Checks:
  1. Raw data package exists (from consolidator)
  2. Mandatory documents present (Annual Report, Bank Statement, ITR)
  3. 3-year financial data present (revenue_3yr in Annual Report)
  4. Bank statement 12-month coverage
  5. Key financial fields present and parseable
  6. Worker confidence thresholds
  7. Cross-verification results present

Does NOT make judgment calls — purely technical correctness.
"""

import logging
from typing import Dict, List, Any

from backend.graph.state import CreditAppraisalState, WorkerOutput
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    DocumentType,
    ThinkingEvent,
    EventType,
)

logger = logging.getLogger(__name__)

# Mandatory docs — assessment cannot proceed without these
MANDATORY_DOCUMENTS = {
    DocumentType.ANNUAL_REPORT.value,
    DocumentType.BANK_STATEMENT.value,
    DocumentType.ITR.value,
}

# Optional docs — assessment proceeds with reduced scope if missing
OPTIONAL_DOCUMENTS = {
    DocumentType.GST_RETURNS.value,
    DocumentType.LEGAL_NOTICE.value,
    DocumentType.BOARD_MINUTES.value,
    DocumentType.SHAREHOLDING_PATTERN.value,
    DocumentType.RATING_REPORT.value,
}

# Minimum worker confidence before flagging
MIN_CONFIDENCE = 0.3

# Key financial fields expected in Annual Report extraction
AR_REQUIRED_FIELDS = ["revenue", "ebitda", "pat", "total_debt", "net_worth"]

# Bank statement expected fields
BS_REQUIRED_FIELDS = ["monthly_inflows", "monthly_outflows"]


async def validator_node(state: CreditAppraisalState) -> dict:
    """
    Stage 3 — Validator.

    Enforces technical completeness between consolidation and organization.
    Does NOT make judgment calls — purely technical correctness.
    """
    logger.info(f"[Validator] Validating consolidated data for session {state.session_id}")

    events: List[ThinkingEvent] = list(state.thinking_events or [])
    errors: List[str] = []
    warnings: List[str] = []

    events.append(_event(state.session_id, EventType.READ,
                         "Starting technical validation of consolidated data"))

    # ── Check 1: Raw data package exists ──
    if not state.raw_data_package:
        errors.append("No raw data package from consolidation stage")
        events.append(_event(state.session_id, EventType.CRITICAL,
                             "No raw data package — consolidation may have failed"))
    else:
        worker_outputs = state.raw_data_package.worker_outputs
        events.append(_event(
            state.session_id, EventType.READ,
            f"Raw data package present with {len(worker_outputs)} worker outputs"
        ))

        # ── Check 2: Mandatory documents present ──
        present_types = set(worker_outputs.keys())
        missing_mandatory = MANDATORY_DOCUMENTS - present_types
        if missing_mandatory:
            for doc in sorted(missing_mandatory):
                errors.append(f"Mandatory document missing: {doc}")
            events.append(_event(
                state.session_id, EventType.CRITICAL,
                f"Missing mandatory documents: {', '.join(sorted(missing_mandatory))}"
            ))
        else:
            events.append(_event(
                state.session_id, EventType.ACCEPTED,
                f"All {len(MANDATORY_DOCUMENTS)} mandatory documents present"
            ))

        # Check optional docs
        missing_optional = OPTIONAL_DOCUMENTS - present_types
        if missing_optional:
            for doc in sorted(missing_optional):
                warnings.append(f"Optional document not provided: {doc}")
            events.append(_event(
                state.session_id, EventType.FLAGGED,
                f"{len(missing_optional)} optional document(s) missing — "
                f"assessment proceeds with reduced scope"
            ))

        # ── Check 3: 3-year financial data ──
        ar_output = worker_outputs.get(DocumentType.ANNUAL_REPORT.value)
        if ar_output:
            ar_data = ar_output.extracted_data
            revenue_3yr = ar_data.get("revenue_3yr")
            if isinstance(revenue_3yr, (list, tuple)) and len(revenue_3yr) >= 3:
                events.append(_event(
                    state.session_id, EventType.ACCEPTED,
                    f"3-year revenue history present: {len(revenue_3yr)} years"
                ))
            elif isinstance(revenue_3yr, (list, tuple)) and len(revenue_3yr) > 0:
                warnings.append(
                    f"Only {len(revenue_3yr)} year(s) of revenue data "
                    f"(3 required for CAGR calculation)"
                )
                events.append(_event(
                    state.session_id, EventType.FLAGGED,
                    f"Partial revenue history: {len(revenue_3yr)} year(s) "
                    f"instead of 3 — CAGR may be inaccurate"
                ))
            else:
                warnings.append("No multi-year revenue data in Annual Report")
                events.append(_event(
                    state.session_id, EventType.FLAGGED,
                    "No multi-year revenue data — trend analysis unavailable"
                ))

            # ── Check 5: Key financial fields present ──
            _check_required_fields(
                ar_data, AR_REQUIRED_FIELDS,
                "Annual Report", errors, warnings, events, state.session_id,
            )
        # (if ar_output is None, already caught in mandatory check)

        # ── Check 4: Bank statement 12-month coverage ──
        bs_output = worker_outputs.get(DocumentType.BANK_STATEMENT.value)
        if bs_output:
            bs_data = bs_output.extracted_data
            monthly_inflows = bs_data.get("monthly_inflows")
            if isinstance(monthly_inflows, (list, tuple)):
                months = len(monthly_inflows)
                if months >= 12:
                    events.append(_event(
                        state.session_id, EventType.ACCEPTED,
                        f"Bank statement covers {months} months (≥12 required)"
                    ))
                elif months >= 6:
                    warnings.append(
                        f"Bank statement covers only {months} months "
                        f"(12 recommended)"
                    )
                    events.append(_event(
                        state.session_id, EventType.FLAGGED,
                        f"Bank statement covers {months} months — "
                        f"seasonality analysis may be inaccurate"
                    ))
                else:
                    errors.append(
                        f"Bank statement covers only {months} months "
                        f"(minimum 6 required)"
                    )
                    events.append(_event(
                        state.session_id, EventType.CRITICAL,
                        f"Bank statement covers only {months} months — "
                        f"insufficient for cash flow analysis"
                    ))
            else:
                warnings.append("Bank statement missing monthly inflow data")

            _check_required_fields(
                bs_data, BS_REQUIRED_FIELDS,
                "Bank Statement", errors, warnings, events, state.session_id,
            )

        # ── Check 6: Worker confidence thresholds ──
        low_confidence_workers = []
        for doc_type, wo in worker_outputs.items():
            if wo.confidence < MIN_CONFIDENCE:
                low_confidence_workers.append(doc_type)

        if low_confidence_workers:
            for doc in low_confidence_workers:
                conf = worker_outputs[doc].confidence
                warnings.append(
                    f"Low confidence extraction for {doc}: {conf:.0%}"
                )
            events.append(_event(
                state.session_id, EventType.FLAGGED,
                f"{len(low_confidence_workers)} worker(s) below {MIN_CONFIDENCE:.0%} "
                f"confidence threshold"
            ))

        # ── Check 7: Cross-verification results ──
        cross_verifications = state.raw_data_package.cross_verifications
        if cross_verifications:
            conflicting = [cv for cv in cross_verifications if cv.status == "conflicting"]
            if conflicting:
                for cv in conflicting:
                    warnings.append(
                        f"Unresolved cross-verification conflict: {cv.field_name} "
                        f"(deviation: {cv.max_deviation_pct:.1f}%)"
                    )
                events.append(_event(
                    state.session_id, EventType.FLAGGED,
                    f"{len(conflicting)} cross-verification conflict(s) detected "
                    f"— tickets may be raised"
                ))
            else:
                events.append(_event(
                    state.session_id, EventType.ACCEPTED,
                    f"All {len(cross_verifications)} cross-verifications passed"
                ))

    # ── Summary ──
    validation_passed = len(errors) == 0

    if validation_passed and warnings:
        events.append(_event(
            state.session_id, EventType.CONCLUDING,
            f"Validation PASSED with {len(warnings)} warning(s) — "
            f"proceeding to organization"
        ))
    elif validation_passed:
        events.append(_event(
            state.session_id, EventType.CONCLUDING,
            "Validation PASSED — all checks clear, proceeding to organization"
        ))
    else:
        events.append(_event(
            state.session_id, EventType.CRITICAL,
            f"Validation FAILED — {len(errors)} error(s): "
            + "; ".join(errors[:3])
            + ("..." if len(errors) > 3 else "")
        ))

    # Update pipeline stage
    for stage in state.pipeline_stages:
        if stage.stage == PipelineStageEnum.VALIDATION:
            if validation_passed:
                stage.status = PipelineStageStatus.COMPLETED
                stage.message = (
                    f"Passed ({len(warnings)} warnings)"
                    if warnings else "All checks passed"
                )
            else:
                stage.status = PipelineStageStatus.FAILED
                stage.message = f"{len(errors)} validation error(s)"

    logger.info(
        f"[Validator] Session {state.session_id}: "
        f"{'PASSED' if validation_passed else 'FAILED'} "
        f"({len(errors)} errors, {len(warnings)} warnings)"
    )

    return {
        "validation_passed": validation_passed,
        "validation_errors": errors + warnings,
        "thinking_events": events,
        "pipeline_stages": state.pipeline_stages,
    }


def _check_required_fields(
    data: Dict[str, Any],
    required_fields: List[str],
    doc_label: str,
    errors: List[str],
    warnings: List[str],
    events: List[ThinkingEvent],
    session_id: str,
):
    """Check that required fields exist and have non-None values in extracted data."""
    missing = [f for f in required_fields if data.get(f) is None]
    if missing:
        for f in missing:
            warnings.append(f"{doc_label} missing field: {f}")
        events.append(_event(
            session_id, EventType.FLAGGED,
            f"{doc_label}: {len(missing)} expected field(s) missing — "
            f"{', '.join(missing)}"
        ))
    else:
        events.append(_event(
            session_id, EventType.ACCEPTED,
            f"{doc_label}: all {len(required_fields)} required fields present"
        ))


def _event(session_id: str, event_type: EventType, message: str) -> ThinkingEvent:
    """Create a ThinkingEvent for the Validator node."""
    return ThinkingEvent(
        session_id=session_id,
        agent="Validator",
        event_type=event_type,
        message=message,
    )
