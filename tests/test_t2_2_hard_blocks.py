"""
Tests for T2.2 — Hard Block Detection.

Tests all 4 hard block triggers:
  wilful_defaulter     → capped at 200
  active_criminal_case → capped at 150
  dscr_below_1         → capped at 300
  nclt_active          → capped at 250

Tests:
1.  No hard blocks → empty list
2.  Wilful defaulter (director flag) → trigger + cap 200
3.  Wilful defaulter (company flag) → trigger + cap 200
4.  Active criminal case → trigger + cap 150
5.  DSCR < 1.0 → trigger + cap 300
6.  NCLT active → trigger + cap 250
7.  Multiple hard blocks → all detected
8.  Multiple blocks → lowest cap wins
9.  Non-criminal litigation → no hard block
10. DSCR exactly 1.0 → no hard block
11. DSCR > 1.0 → no hard block
12. NCLT resolved (not pending) → no hard block
13. Criminal case resolved → no hard block
14. Full pipeline with wilful defaulter → score capped at 200
15. Full pipeline with DSCR < 1.0 → score capped at 300
16. Hard block evidence fields populated correctly
"""

import asyncio
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.scoring import get_score_band, BASE_SCORE, HARD_BLOCK_RULES
from backend.graph.nodes.recommendation_node import (
    recommendation_node,
    _check_hard_blocks,
)
from backend.graph.state import (
    CreditAppraisalState,
    WorkerOutput,
    RawDataPackage,
    HardBlock,
)
from backend.models.schemas import (
    ScoreBand,
    AssessmentOutcome,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    CompanyInfo,
)
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.thinking.redis_publisher import reset_publisher


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _base_worker_data():
    """Clean worker data — no hard block triggers."""
    return {
        "W1": {
            "revenue": {"fy2023": 4850.0, "fy2022": 4200.0, "source_page": 45},
            "ebitda": {"fy2023": 825.0, "source_page": 45},
            "total_debt": {"fy2023": 1850.0, "source_page": 50},
            "net_worth": {"fy2023": 1280.0, "source_page": 50},
            "interest_expense": {"fy2023": 195.0, "source_page": 46},
            "auditor_qualifications": [],
            "rpts": {"count": 0, "total_amount": 0},
            "litigation_disclosure": {"cases": []},
            "directors": [
                {"name": "Vikram Mehta", "din": "00123456"},
            ],
        },
        "W2": {
            "bounces": {"count": 0, "total_amount": 0},
            "emi_regularity": {"regularity_pct": 96.0, "on_time": 11.5, "total_months": 12},
        },
        "W3": {
            "filing_compliance": {"regularity_pct": 100, "months_filed": 12},
        },
    }


def _build_state(worker_data=None):
    wd = worker_data or _base_worker_data()
    state = CreditAppraisalState(
        session_id="test-t2-2",
        company=CompanyInfo(
            name="XYZ Steel Limited",
            sector="Steel Manufacturing",
            loan_type="Working Capital",
            loan_amount="₹50,00,00,000",
            loan_amount_numeric=5000.0,
        ),
        pipeline_stages=[
            PipelineStage(
                stage=PipelineStageEnum.RECOMMENDATION,
                status=PipelineStageStatus.PENDING,
            ),
        ],
    )
    for wid, data in wd.items():
        state.worker_outputs[wid] = WorkerOutput(
            worker_id=wid,
            document_type=wid,
            status="completed",
            pages_processed=10,
            confidence=0.90,
            extracted_data=data,
        )
    state.raw_data_package = RawDataPackage(
        session_id="test-t2-2",
        cross_verifications=[],
        contradictions=[],
    )
    return state


# ──────────────────────────────────────────────
# Test 1: No hard blocks → empty list
# ──────────────────────────────────────────────

async def test_no_hard_blocks():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-none", "No Blocks")
    data = _base_worker_data()

    blocks = await _check_hard_blocks(data, emitter)
    assert blocks == [], f"Expected empty list, got {blocks}"


# ──────────────────────────────────────────────
# Test 2: Wilful defaulter (director flag) → cap 200
# ──────────────────────────────────────────────

async def test_wilful_defaulter_director():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-wd", "WD Director")
    data = _base_worker_data()
    data["W1"]["directors"][0]["wilful_defaulter"] = True

    blocks = await _check_hard_blocks(data, emitter)
    wd = [b for b in blocks if b.trigger == "wilful_defaulter"]
    assert len(wd) == 1
    assert wd[0].score_cap == 200
    assert "Vikram Mehta" in wd[0].evidence


# ──────────────────────────────────────────────
# Test 3: Wilful defaulter (company flag) → cap 200
# ──────────────────────────────────────────────

async def test_wilful_defaulter_company():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-wdc", "WD Company")
    data = _base_worker_data()
    data["W1"]["wilful_defaulter"] = True

    blocks = await _check_hard_blocks(data, emitter)
    wd = [b for b in blocks if b.trigger == "wilful_defaulter"]
    assert len(wd) == 1
    assert wd[0].score_cap == 200


# ──────────────────────────────────────────────
# Test 4: Active criminal case → cap 150
# ──────────────────────────────────────────────

async def test_active_criminal_case():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-crim", "Criminal")
    data = _base_worker_data()
    data["W1"]["litigation_disclosure"]["cases"].append({
        "type": "Criminal",
        "forum": "Sessions Court",
        "amount": 500,
        "status": "pending",
    })

    blocks = await _check_hard_blocks(data, emitter)
    crim = [b for b in blocks if b.trigger == "active_criminal_case"]
    assert len(crim) == 1
    assert crim[0].score_cap == 150


# ──────────────────────────────────────────────
# Test 5: DSCR < 1.0 → cap 300
# ──────────────────────────────────────────────

async def test_dscr_below_1():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-dscr", "DSCR Block")
    data = _base_worker_data()
    # DSCR = 825 / 1000 = 0.825
    data["W1"]["interest_expense"]["fy2023"] = 1000.0

    blocks = await _check_hard_blocks(data, emitter)
    dscr = [b for b in blocks if b.trigger == "dscr_below_1"]
    assert len(dscr) == 1
    assert dscr[0].score_cap == 300
    assert "0.82" in dscr[0].evidence  # DSCR value in evidence


# ──────────────────────────────────────────────
# Test 6: NCLT active → cap 250
# ──────────────────────────────────────────────

async def test_nclt_active():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-nclt", "NCLT")
    data = _base_worker_data()
    data["W1"]["litigation_disclosure"]["cases"].append({
        "type": "Insolvency",
        "forum": "NCLT",
        "amount": 2500,
        "status": "pending",
    })

    blocks = await _check_hard_blocks(data, emitter)
    nclt = [b for b in blocks if b.trigger == "nclt_active"]
    assert len(nclt) == 1
    assert nclt[0].score_cap == 250


# ──────────────────────────────────────────────
# Test 7: Multiple hard blocks → all detected
# ──────────────────────────────────────────────

async def test_multiple_blocks():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-multi", "Multi Block")
    data = _base_worker_data()
    # Trigger all 4
    data["W1"]["directors"][0]["wilful_defaulter"] = True
    data["W1"]["litigation_disclosure"]["cases"] = [
        {"type": "Criminal", "forum": "Sessions Court", "amount": 100, "status": "pending"},
        {"type": "Insolvency", "forum": "NCLT", "amount": 2500, "status": "pending"},
    ]
    data["W1"]["interest_expense"]["fy2023"] = 1000.0  # DSCR < 1

    blocks = await _check_hard_blocks(data, emitter)

    triggers = {b.trigger for b in blocks}
    assert "wilful_defaulter" in triggers
    assert "active_criminal_case" in triggers
    assert "dscr_below_1" in triggers
    assert "nclt_active" in triggers
    assert len(blocks) == 4


# ──────────────────────────────────────────────
# Test 8: Multiple blocks → lowest cap wins
# ──────────────────────────────────────────────

async def test_lowest_cap_wins():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-low", "Lowest Cap")
    data = _base_worker_data()
    # Criminal (150) + NCLT (250) → min cap = 150
    data["W1"]["litigation_disclosure"]["cases"] = [
        {"type": "Criminal", "forum": "Sessions Court", "amount": 100, "status": "pending"},
        {"type": "Insolvency", "forum": "NCLT", "amount": 2500, "status": "pending"},
    ]

    blocks = await _check_hard_blocks(data, emitter)
    min_cap = min(b.score_cap for b in blocks)
    assert min_cap == 150


# ──────────────────────────────────────────────
# Test 9: Non-criminal litigation → no hard block
# ──────────────────────────────────────────────

async def test_civil_litigation_no_block():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-civil", "Civil No Block")
    data = _base_worker_data()
    data["W1"]["litigation_disclosure"]["cases"].append({
        "type": "Civil",
        "forum": "High Court",
        "amount": 500,
        "status": "pending",
    })

    blocks = await _check_hard_blocks(data, emitter)
    crim = [b for b in blocks if b.trigger == "active_criminal_case"]
    assert len(crim) == 0


# ──────────────────────────────────────────────
# Test 10: DSCR exactly 1.0 → no hard block
# ──────────────────────────────────────────────

async def test_dscr_exactly_1():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-dscr1", "DSCR 1.0")
    data = _base_worker_data()
    # DSCR = 825 / 825 = 1.0 exactly → NOT < 1.0
    data["W1"]["interest_expense"]["fy2023"] = 825.0

    blocks = await _check_hard_blocks(data, emitter)
    dscr = [b for b in blocks if b.trigger == "dscr_below_1"]
    assert len(dscr) == 0


# ──────────────────────────────────────────────
# Test 11: DSCR > 1.0 → no hard block
# ──────────────────────────────────────────────

async def test_dscr_above_1():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-dscr2", "DSCR Above")
    data = _base_worker_data()

    blocks = await _check_hard_blocks(data, emitter)
    dscr = [b for b in blocks if b.trigger == "dscr_below_1"]
    assert len(dscr) == 0


# ──────────────────────────────────────────────
# Test 12: NCLT resolved → no hard block
# ──────────────────────────────────────────────

async def test_nclt_resolved():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-nclt-r", "NCLT Resolved")
    data = _base_worker_data()
    data["W1"]["litigation_disclosure"]["cases"].append({
        "type": "Insolvency",
        "forum": "NCLT",
        "amount": 2500,
        "status": "resolved",
    })

    blocks = await _check_hard_blocks(data, emitter)
    nclt = [b for b in blocks if b.trigger == "nclt_active"]
    assert len(nclt) == 0


# ──────────────────────────────────────────────
# Test 13: Criminal case resolved → no hard block
# ──────────────────────────────────────────────

async def test_criminal_resolved():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-crim-r", "Criminal Resolved")
    data = _base_worker_data()
    data["W1"]["litigation_disclosure"]["cases"].append({
        "type": "Criminal",
        "forum": "Sessions Court",
        "amount": 100,
        "status": "resolved",
    })

    blocks = await _check_hard_blocks(data, emitter)
    crim = [b for b in blocks if b.trigger == "active_criminal_case"]
    assert len(crim) == 0


# ──────────────────────────────────────────────
# Test 14: Full pipeline with wilful defaulter → score capped at 200
# ──────────────────────────────────────────────

async def test_pipeline_wilful_defaulter_cap():
    reset_publisher()
    data = _base_worker_data()
    data["W1"]["directors"][0]["wilful_defaulter"] = True
    state = _build_state(data)

    result = await recommendation_node(state)

    assert result["score"] <= 200, f"Score {result['score']} should be capped at 200"
    hb_triggers = {b.trigger for b in result.get("hard_blocks", [])}
    assert "wilful_defaulter" in hb_triggers

    # Cleanup
    cam_dir = os.path.join("data", "output", state.session_id)
    if os.path.exists(cam_dir):
        shutil.rmtree(cam_dir)


# ──────────────────────────────────────────────
# Test 15: Full pipeline with DSCR < 1.0 → score capped at 300
# ──────────────────────────────────────────────

async def test_pipeline_dscr_cap():
    reset_publisher()
    data = _base_worker_data()
    data["W1"]["interest_expense"]["fy2023"] = 1000.0  # DSCR < 1
    state = _build_state(data)

    result = await recommendation_node(state)

    assert result["score"] <= 300, f"Score {result['score']} should be capped at 300"
    hb_triggers = {b.trigger for b in result.get("hard_blocks", [])}
    assert "dscr_below_1" in hb_triggers

    # Cleanup
    cam_dir = os.path.join("data", "output", state.session_id)
    if os.path.exists(cam_dir):
        shutil.rmtree(cam_dir)


# ──────────────────────────────────────────────
# Test 16: Hard block evidence populated
# ──────────────────────────────────────────────

async def test_hard_block_evidence():
    reset_publisher()
    emitter = ThinkingEventEmitter("test-hb-ev", "Evidence")
    data = _base_worker_data()
    data["W1"]["directors"][0]["wilful_defaulter"] = True
    data["W1"]["litigation_disclosure"]["cases"].append({
        "type": "Insolvency", "forum": "NCLT", "amount": 2500, "status": "pending",
    })

    blocks = await _check_hard_blocks(data, emitter)

    for b in blocks:
        assert b.trigger, "trigger should be set"
        assert b.score_cap > 0, "score_cap should be positive"
        assert b.evidence, "evidence should not be empty"
        assert b.source, "source should not be empty"
