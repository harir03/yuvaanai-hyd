"""
T1.8 — Validator Node

Tests:
  Section 1: Core validation (happy path / failure path)
    1. Happy path — all mandatory docs, 3yr revenue, 12mo bank → passes
    2. No raw_data_package → fails with critical error
    3. Missing mandatory Annual Report → fails
    4. Missing mandatory Bank Statement → fails
    5. Missing mandatory ITR → fails
    6. All mandatory missing → 3 errors

  Section 2: 3-year financial data check
    7. 3+ years revenue → accepted
    8. 2 years revenue → warning (partial)
    9. No revenue_3yr field → warning

  Section 3: Bank statement coverage
   10. 12 months inflows → accepted
   11. 8 months inflows → warning
   12. 4 months inflows → error (below 6-month minimum)

  Section 4: Required field checks
   13. Annual Report all fields present → accepted
   14. Annual Report missing ebitda, pat → warnings
   15. Bank Statement missing monthly_outflows → warning

  Section 5: Worker confidence check
   16. All workers above threshold → no flag
   17. Worker below MIN_CONFIDENCE → flagged

  Section 6: Cross-verification conflicts
   18. All verifications passed → accepted
   19. Conflicting cross-verification → flagged warning

  Section 7: Optional documents
   20. Optional documents missing → warnings, but still passes

  Section 8: ThinkingEvents
   21. Events emitted: READ, ACCEPTED, CONCLUDING (happy path)
   22. Events emitted: CRITICAL for failures
   23. Events emitted: FLAGGED for warnings

  Section 9: Pipeline stage update
   24. Passes → stage COMPLETED
   25. Fails → stage FAILED

  Section 10: Integration-level
   26. Empty worker_outputs + no mandatory → fails with 3 errors
   27. Full valid state → passes with 0 errors
   28. Passes with warnings → validation_passed=True but warnings in errors list
"""

import asyncio
import pytest

from backend.graph.state import (
    CreditAppraisalState,
    WorkerOutput,
    RawDataPackage,
    CrossVerificationResult,
)
from backend.models.schemas import (
    DocumentType,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    ThinkingEvent,
    EventType,
)
from backend.graph.nodes.validator_node import (
    validator_node,
    MANDATORY_DOCUMENTS,
    OPTIONAL_DOCUMENTS,
    MIN_CONFIDENCE,
    AR_REQUIRED_FIELDS,
    BS_REQUIRED_FIELDS,
)


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _worker(doc_type: str, confidence: float = 0.85, extracted_data: dict = None) -> WorkerOutput:
    return WorkerOutput(
        worker_id=f"W-{doc_type}",
        document_type=doc_type,
        status="completed",
        extracted_data=extracted_data or {},
        confidence=confidence,
        pages_processed=10,
    )


def _full_ar_data() -> dict:
    """Annual Report extracted data with all required fields + 3yr revenue."""
    return {
        "revenue": 500_00_00_000,
        "ebitda": 80_00_00_000,
        "pat": 40_00_00_000,
        "total_debt": 200_00_00_000,
        "net_worth": 300_00_00_000,
        "revenue_3yr": [400_00_00_000, 450_00_00_000, 500_00_00_000],
    }


def _full_bs_data() -> dict:
    """Bank Statement extracted data with 12-month coverage."""
    return {
        "monthly_inflows": [10_00_000] * 12,
        "monthly_outflows": [8_00_000] * 12,
    }


def _full_itr_data() -> dict:
    return {"taxable_income": 35_00_00_000, "total_income": 50_00_00_000}


def _make_raw_data_package(
    include_ar=True,
    include_bs=True,
    include_itr=True,
    ar_data=None,
    bs_data=None,
    extra_workers=None,
    cross_verifications=None,
    ar_confidence=0.85,
    bs_confidence=0.85,
) -> RawDataPackage:
    outputs = {}
    if include_ar:
        outputs[DocumentType.ANNUAL_REPORT.value] = _worker(
            DocumentType.ANNUAL_REPORT.value,
            confidence=ar_confidence,
            extracted_data=ar_data if ar_data is not None else _full_ar_data(),
        )
    if include_bs:
        outputs[DocumentType.BANK_STATEMENT.value] = _worker(
            DocumentType.BANK_STATEMENT.value,
            confidence=bs_confidence,
            extracted_data=bs_data if bs_data is not None else _full_bs_data(),
        )
    if include_itr:
        outputs[DocumentType.ITR.value] = _worker(
            DocumentType.ITR.value,
            extracted_data=_full_itr_data(),
        )
    if extra_workers:
        outputs.update(extra_workers)
    return RawDataPackage(
        worker_outputs=outputs,
        cross_verifications=cross_verifications or [],
        completeness_score=0.8,
        mandatory_fields_present=True,
    )


def _state(raw_data_package=None, session_id="test-val-session") -> CreditAppraisalState:
    stages = [
        PipelineStage(stage=PipelineStageEnum.VALIDATION, status=PipelineStageStatus.PENDING),
    ]
    return CreditAppraisalState(
        session_id=session_id,
        raw_data_package=raw_data_package,
        pipeline_stages=stages,
    )


# ─────────────────────────────────────────
# Section 1: Core validation
# ─────────────────────────────────────────

class TestCoreValidation:

    def test_01_happy_path_all_mandatory(self):
        """All mandatory docs, 3yr revenue, 12mo bank → passes."""
        state = _state(raw_data_package=_make_raw_data_package())
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is True
        # No errors should start with "Mandatory"
        hard_errors = [e for e in result["validation_errors"] if "Mandatory" in e]
        assert len(hard_errors) == 0

    def test_02_no_raw_data_package(self):
        """Missing raw_data_package → fails."""
        state = _state(raw_data_package=None)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is False
        assert any("No raw data package" in e for e in result["validation_errors"])

    def test_03_missing_annual_report(self):
        """Missing Annual Report → fails."""
        rdp = _make_raw_data_package(include_ar=False)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is False
        assert any("ANNUAL_REPORT" in e for e in result["validation_errors"])

    def test_04_missing_bank_statement(self):
        """Missing Bank Statement → fails."""
        rdp = _make_raw_data_package(include_bs=False)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is False
        assert any("BANK_STATEMENT" in e for e in result["validation_errors"])

    def test_05_missing_itr(self):
        """Missing ITR → fails."""
        rdp = _make_raw_data_package(include_itr=False)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is False
        assert any("ITR" in e for e in result["validation_errors"])

    def test_06_all_mandatory_missing(self):
        """All mandatory missing → 3 errors."""
        rdp = _make_raw_data_package(include_ar=False, include_bs=False, include_itr=False)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is False
        mandatory_errors = [e for e in result["validation_errors"] if "Mandatory" in e]
        assert len(mandatory_errors) == 3


# ─────────────────────────────────────────
# Section 2: 3-year financial data check
# ─────────────────────────────────────────

class TestThreeYearData:

    def test_07_three_years_present(self):
        """3+ years revenue → accepted."""
        rdp = _make_raw_data_package()
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        events = result["thinking_events"]
        assert any("3-year revenue history present" in e.message for e in events)

    def test_08_two_years_revenue(self):
        """2 years revenue → warning."""
        ar_data = _full_ar_data()
        ar_data["revenue_3yr"] = [400, 500]  # only 2
        rdp = _make_raw_data_package(ar_data=ar_data)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        # Passes (it's a warning, not error)
        assert result["validation_passed"] is True
        assert any("2 year" in e for e in result["validation_errors"])

    def test_09_no_revenue_3yr(self):
        """No revenue_3yr field → warning."""
        ar_data = _full_ar_data()
        del ar_data["revenue_3yr"]
        rdp = _make_raw_data_package(ar_data=ar_data)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is True
        assert any("multi-year revenue" in e.lower() or "trend" in e.lower()
                    for e in result["validation_errors"])


# ─────────────────────────────────────────
# Section 3: Bank statement coverage
# ─────────────────────────────────────────

class TestBankStatementCoverage:

    def test_10_twelve_months(self):
        """12 months → accepted."""
        rdp = _make_raw_data_package()
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        events = result["thinking_events"]
        assert any("12 months" in e.message and "Bank statement" in e.message for e in events)

    def test_11_eight_months(self):
        """8 months → warning."""
        bs_data = {"monthly_inflows": [10_00_000] * 8, "monthly_outflows": [8_00_000] * 8}
        rdp = _make_raw_data_package(bs_data=bs_data)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is True
        assert any("8 months" in e for e in result["validation_errors"])

    def test_12_four_months_error(self):
        """4 months → error (below 6-month minimum)."""
        bs_data = {"monthly_inflows": [10_00_000] * 4, "monthly_outflows": [8_00_000] * 4}
        rdp = _make_raw_data_package(bs_data=bs_data)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is False
        assert any("4 months" in e for e in result["validation_errors"])


# ─────────────────────────────────────────
# Section 4: Required field checks
# ─────────────────────────────────────────

class TestRequiredFields:

    def test_13_ar_all_fields_present(self):
        """Annual Report all fields present → accepted event."""
        rdp = _make_raw_data_package()
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        events = result["thinking_events"]
        assert any(
            "Annual Report" in e.message and "required fields present" in e.message
            for e in events
        )

    def test_14_ar_missing_fields(self):
        """Annual Report missing ebitda, pat → warnings."""
        ar_data = _full_ar_data()
        ar_data["ebitda"] = None
        ar_data["pat"] = None
        rdp = _make_raw_data_package(ar_data=ar_data)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is True  # warnings, not errors
        assert any("ebitda" in e for e in result["validation_errors"])
        assert any("pat" in e for e in result["validation_errors"])

    def test_15_bs_missing_field(self):
        """Bank Statement missing monthly_outflows → warning."""
        bs_data = {"monthly_inflows": [10_00_000] * 12}  # no monthly_outflows
        rdp = _make_raw_data_package(bs_data=bs_data)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is True
        assert any("monthly_outflows" in e for e in result["validation_errors"])


# ─────────────────────────────────────────
# Section 5: Worker confidence check
# ─────────────────────────────────────────

class TestWorkerConfidence:

    def test_16_all_above_threshold(self):
        """All workers above MIN_CONFIDENCE → no flag."""
        rdp = _make_raw_data_package(ar_confidence=0.85, bs_confidence=0.85)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert not any("confidence" in e.lower() for e in result["validation_errors"])

    def test_17_worker_below_threshold(self):
        """Worker below MIN_CONFIDENCE → flagged."""
        rdp = _make_raw_data_package(ar_confidence=0.1)  # below 0.3
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert any("Low confidence" in e for e in result["validation_errors"])


# ─────────────────────────────────────────
# Section 6: Cross-verification conflicts
# ─────────────────────────────────────────

class TestCrossVerification:

    def test_18_all_passed(self):
        """All verifications passed → accepted."""
        cvs = [
            CrossVerificationResult(
                field_name="revenue", status="verified",
                max_deviation_pct=2.0,
            ),
        ]
        rdp = _make_raw_data_package(cross_verifications=cvs)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        events = result["thinking_events"]
        assert any("cross-verifications passed" in e.message for e in events)

    def test_19_conflicting(self):
        """Conflicting cross-verification → flagged."""
        cvs = [
            CrossVerificationResult(
                field_name="revenue", status="conflicting",
                max_deviation_pct=25.0,
            ),
        ]
        rdp = _make_raw_data_package(cross_verifications=cvs)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        # Still passes (warning not error)
        assert result["validation_passed"] is True
        assert any("conflict" in e.lower() for e in result["validation_errors"])


# ─────────────────────────────────────────
# Section 7: Optional documents
# ─────────────────────────────────────────

class TestOptionalDocuments:

    def test_20_optional_missing_still_passes(self):
        """Missing optional docs → warnings only, still passes."""
        rdp = _make_raw_data_package()
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        # Should pass (only mandatory matters for pass/fail)
        assert result["validation_passed"] is True
        # But optional docs missing should generate warnings
        optional_warnings = [e for e in result["validation_errors"] if "Optional" in e]
        assert len(optional_warnings) > 0


# ─────────────────────────────────────────
# Section 8: ThinkingEvents
# ─────────────────────────────────────────

class TestThinkingEvents:

    def test_21_happy_path_events(self):
        """Happy path → READ, ACCEPTED, CONCLUDING."""
        rdp = _make_raw_data_package()
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        events = result["thinking_events"]
        types = {e.event_type for e in events}
        assert EventType.READ in types
        assert EventType.ACCEPTED in types
        assert EventType.CONCLUDING in types

    def test_22_failure_events(self):
        """Failure → CRITICAL event."""
        state = _state(raw_data_package=None)
        result = asyncio.run(validator_node(state))
        events = result["thinking_events"]
        assert any(e.event_type == EventType.CRITICAL for e in events)

    def test_23_warning_events(self):
        """Warnings → FLAGGED events."""
        bs_data = {"monthly_inflows": [10_00_000] * 8, "monthly_outflows": [8_00_000] * 8}
        rdp = _make_raw_data_package(bs_data=bs_data)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        events = result["thinking_events"]
        assert any(e.event_type == EventType.FLAGGED for e in events)


# ─────────────────────────────────────────
# Section 9: Pipeline stage update
# ─────────────────────────────────────────

class TestPipelineStage:

    def test_24_passes_stage_completed(self):
        """Validation passes → stage = COMPLETED."""
        rdp = _make_raw_data_package()
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        stages = result["pipeline_stages"]
        val_stage = next(s for s in stages if s.stage == PipelineStageEnum.VALIDATION)
        assert val_stage.status == PipelineStageStatus.COMPLETED

    def test_25_fails_stage_failed(self):
        """Validation fails → stage = FAILED."""
        state = _state(raw_data_package=None)
        result = asyncio.run(validator_node(state))
        stages = result["pipeline_stages"]
        val_stage = next(s for s in stages if s.stage == PipelineStageEnum.VALIDATION)
        assert val_stage.status == PipelineStageStatus.FAILED


# ─────────────────────────────────────────
# Section 10: Integration-level
# ─────────────────────────────────────────

class TestIntegration:

    def test_26_empty_workers_all_mandatory_missing(self):
        """Empty worker_outputs → all 3 mandatory missing."""
        rdp = RawDataPackage(worker_outputs={})
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is False
        mandatory_errors = [e for e in result["validation_errors"] if "Mandatory" in e]
        assert len(mandatory_errors) == 3

    def test_27_full_valid_state_zero_errors(self):
        """Full valid state with all docs → passes, 0 hard errors."""
        extra = {
            DocumentType.GST_RETURNS.value: _worker(DocumentType.GST_RETURNS.value),
            DocumentType.BOARD_MINUTES.value: _worker(DocumentType.BOARD_MINUTES.value),
            DocumentType.SHAREHOLDING_PATTERN.value: _worker(DocumentType.SHAREHOLDING_PATTERN.value),
            DocumentType.RATING_REPORT.value: _worker(DocumentType.RATING_REPORT.value),
            DocumentType.LEGAL_NOTICE.value: _worker(DocumentType.LEGAL_NOTICE.value),
        }
        rdp = _make_raw_data_package(extra_workers=extra)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is True
        # No hard errors (might have some field-level warnings from optional docs)
        mandatory_errors = [e for e in result["validation_errors"] if "Mandatory" in e]
        assert len(mandatory_errors) == 0

    def test_28_passes_with_warnings(self):
        """Passes with warnings → validation_passed=True, but warnings in errors list."""
        ar_data = _full_ar_data()
        ar_data["revenue_3yr"] = [400, 500]  # only 2 years → warning
        rdp = _make_raw_data_package(ar_data=ar_data)
        state = _state(raw_data_package=rdp)
        result = asyncio.run(validator_node(state))
        assert result["validation_passed"] is True
        # There should be warnings
        assert len(result["validation_errors"]) > 0
