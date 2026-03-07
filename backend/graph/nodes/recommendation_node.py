"""
Intelli-Credit — LangGraph Node: Recommendation (Agent 3)

Scores the borrower on a 0–850 scale using the 5 Cs framework + Compound module.
Generates per-point tracing and a Credit Appraisal Memo (CAM).

Agent 3 reads ONLY from the EvidencePackage — it NEVER touches
raw documents, Neo4j, or the Insight Store directly.

Score Framework:
  Capacity:   +150 / -100
  Character:  +120 / -200
  Capital:    +80  / -80
  Collateral: +60  / -40
  Conditions: +50  / -50
  Compound:   +57  / -130
  Base:       350
  Range:      0–850
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from backend.graph.state import (
    CreditAppraisalState,
    EvidencePackage,
    WorkerOutput,
    NormalizedField,
    CrossVerificationResult,
    HardBlock,
)
from backend.models.schemas import (
    PipelineStageStatus,
    PipelineStageEnum,
    ScoreBand,
    ScoreModule,
    AssessmentOutcome,
    ScoreBreakdownEntry,
    ScoreModuleSummary,
    EventType,
)
from backend.thinking.event_emitter import ThinkingEventEmitter

logger = logging.getLogger(__name__)

# Base score — every assessment starts here
BASE_SCORE = 350

# Module score limits (per copilot-instructions.md Section 8)
MODULE_LIMITS = {
    ScoreModule.CAPACITY:   {"max_positive": 150, "max_negative": -100},
    ScoreModule.CHARACTER:  {"max_positive": 120, "max_negative": -200},
    ScoreModule.CAPITAL:    {"max_positive": 80,  "max_negative": -80},
    ScoreModule.COLLATERAL: {"max_positive": 60,  "max_negative": -40},
    ScoreModule.CONDITIONS: {"max_positive": 50,  "max_negative": -50},
    ScoreModule.COMPOUND:   {"max_positive": 57,  "max_negative": -130},
}

# Score band thresholds
SCORE_BANDS = [
    (750, ScoreBand.EXCELLENT, AssessmentOutcome.APPROVED, "Full amount, MCLR+1.5%"),
    (650, ScoreBand.GOOD, AssessmentOutcome.APPROVED, "85% amount, MCLR+2.5%"),
    (550, ScoreBand.FAIR, AssessmentOutcome.CONDITIONAL, "65% amount, MCLR+3.5%"),
    (450, ScoreBand.POOR, AssessmentOutcome.CONDITIONAL, "40% amount, MCLR+5.0%"),
    (350, ScoreBand.VERY_POOR, AssessmentOutcome.REJECTED, "Reject"),
    (0,   ScoreBand.DEFAULT_RISK, AssessmentOutcome.REJECTED, "Permanent reject"),
]

# Hard block triggers and their score caps
HARD_BLOCK_RULES = {
    "wilful_defaulter": 200,
    "active_criminal_case": 150,
    "dscr_below_1": 300,
    "nclt_active": 250,
}


def get_score_band(score: int) -> Tuple[ScoreBand, AssessmentOutcome, str]:
    """Return (ScoreBand, AssessmentOutcome, recommendation) for a given score."""
    for threshold, band, outcome, rec in SCORE_BANDS:
        if score >= threshold:
            return band, outcome, rec
    return ScoreBand.DEFAULT_RISK, AssessmentOutcome.REJECTED, "Permanent reject"


async def recommendation_node(state: CreditAppraisalState) -> dict:
    """
    Stage 9 — Agent 3: Scorer + CAM Writer.

    1. Read Evidence Package
    2. Check hard blocks
    3. Score each of the 6 modules
    4. Apply hard block caps
    5. Derive score band + outcome + loan terms
    6. Generate CAM
    7. Emit ThinkingEvents throughout
    """
    emitter = ThinkingEventEmitter(state.session_id, "Agent 3 — Scorer & CAM Writer")

    try:
        await emitter.read("Reading Evidence Package for final scoring...")

        # Update pipeline stage
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.RECOMMENDATION:
                stage.status = PipelineStageStatus.ACTIVE
                stage.message = "Scoring in progress..."

        # ── Step 1: Get evidence data ──
        # Agent 3 reads from EvidencePackage OR falls back to raw_data_package
        evidence = state.evidence_package
        raw_data = state.raw_data_package

        # Extract worker data for scoring
        worker_data = _collect_worker_data(state)

        # ── Step 2: Check hard blocks ──
        hard_blocks = await _check_hard_blocks(worker_data, emitter)

        # ── Step 3: Score each module ──
        all_entries: List[ScoreBreakdownEntry] = []
        module_summaries: List[ScoreModuleSummary] = []

        # Capacity Module
        cap_entries, cap_total = await _score_capacity(worker_data, emitter)
        all_entries.extend(cap_entries)
        module_summaries.append(ScoreModuleSummary(
            module=ScoreModule.CAPACITY,
            score=cap_total,
            max_positive=MODULE_LIMITS[ScoreModule.CAPACITY]["max_positive"],
            max_negative=MODULE_LIMITS[ScoreModule.CAPACITY]["max_negative"],
            metrics=cap_entries,
        ))

        # Character Module
        char_entries, char_total = await _score_character(worker_data, emitter, state)
        all_entries.extend(char_entries)
        module_summaries.append(ScoreModuleSummary(
            module=ScoreModule.CHARACTER,
            score=char_total,
            max_positive=MODULE_LIMITS[ScoreModule.CHARACTER]["max_positive"],
            max_negative=MODULE_LIMITS[ScoreModule.CHARACTER]["max_negative"],
            metrics=char_entries,
        ))

        # Capital Module
        cap2_entries, cap2_total = await _score_capital(worker_data, emitter)
        all_entries.extend(cap2_entries)
        module_summaries.append(ScoreModuleSummary(
            module=ScoreModule.CAPITAL,
            score=cap2_total,
            max_positive=MODULE_LIMITS[ScoreModule.CAPITAL]["max_positive"],
            max_negative=MODULE_LIMITS[ScoreModule.CAPITAL]["max_negative"],
            metrics=cap2_entries,
        ))

        # Collateral Module
        coll_entries, coll_total = await _score_collateral(worker_data, emitter)
        all_entries.extend(coll_entries)
        module_summaries.append(ScoreModuleSummary(
            module=ScoreModule.COLLATERAL,
            score=coll_total,
            max_positive=MODULE_LIMITS[ScoreModule.COLLATERAL]["max_positive"],
            max_negative=MODULE_LIMITS[ScoreModule.COLLATERAL]["max_negative"],
            metrics=coll_entries,
        ))

        # Conditions Module
        cond_entries, cond_total = await _score_conditions(worker_data, emitter)
        all_entries.extend(cond_entries)
        module_summaries.append(ScoreModuleSummary(
            module=ScoreModule.CONDITIONS,
            score=cond_total,
            max_positive=MODULE_LIMITS[ScoreModule.CONDITIONS]["max_positive"],
            max_negative=MODULE_LIMITS[ScoreModule.CONDITIONS]["max_negative"],
            metrics=cond_entries,
        ))

        # Compound Module (cross-verification signals, GST mismatch, etc.)
        comp_entries, comp_total = await _score_compound(worker_data, state, emitter)
        all_entries.extend(comp_entries)
        module_summaries.append(ScoreModuleSummary(
            module=ScoreModule.COMPOUND,
            score=comp_total,
            max_positive=MODULE_LIMITS[ScoreModule.COMPOUND]["max_positive"],
            max_negative=MODULE_LIMITS[ScoreModule.COMPOUND]["max_negative"],
            metrics=comp_entries,
        ))

        # ── Step 4: Calculate total score ──
        total_impact = sum(e.score_impact for e in all_entries)
        raw_score = BASE_SCORE + total_impact

        # Apply hard block caps
        effective_score = raw_score
        if hard_blocks:
            min_cap = min(hb.score_cap for hb in hard_blocks)
            if raw_score > min_cap:
                effective_score = min_cap
                await emitter.critical(
                    f"Hard block active: score capped from {raw_score} to {effective_score} "
                    f"due to {hard_blocks[0].trigger}"
                )

        # Clamp to 0-850
        final_score = max(0, min(850, effective_score))

        # ── Step 5: Derive band + outcome ──
        band, outcome, recommendation = get_score_band(final_score)

        await emitter.decided(
            f"Final Score: {final_score}/850 — {band.value} ({outcome.value}). "
            f"Base {BASE_SCORE} + adjustments {total_impact:+d} = {raw_score}"
            + (f" → capped to {effective_score}" if effective_score != raw_score else ""),
            confidence=0.92,
        )

        # ── Step 6: Generate CAM ──
        company_name = state.company.name if state.company else "Unknown Company"
        cam_path = await _generate_cam(
            session_id=state.session_id,
            company_name=company_name,
            score=final_score,
            band=band,
            outcome=outcome,
            recommendation=recommendation,
            module_summaries=module_summaries,
            all_entries=all_entries,
            hard_blocks=hard_blocks,
            worker_data=worker_data,
            emitter=emitter,
        )

        # ── Step 7: Update pipeline stage ──
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.RECOMMENDATION:
                stage.status = PipelineStageStatus.COMPLETED
                stage.message = f"Score: {final_score}/850 — {band.value}"

        await emitter.concluding(
            f"Scoring complete. {company_name}: {final_score}/850 ({band.value}). "
            f"Recommendation: {recommendation}. CAM generated."
        )

        return {
            "score": final_score,
            "score_band": band,
            "score_modules": module_summaries,
            "score_breakdown": all_entries,
            "outcome": outcome,
            "hard_blocks": hard_blocks,
            "cam_path": cam_path,
            "pipeline_stages": state.pipeline_stages,
        }

    except Exception as e:
        await emitter.critical(f"Scoring failed: {str(e)}")
        logger.error(f"[Agent 3] Scoring failed: {e}")
        for stage in state.pipeline_stages:
            if stage.stage == PipelineStageEnum.RECOMMENDATION:
                stage.status = PipelineStageStatus.FAILED
                stage.message = f"Error: {str(e)}"
        return {
            "score": 0,
            "score_band": ScoreBand.DEFAULT_RISK,
            "outcome": AssessmentOutcome.REJECTED,
            "error": str(e),
            "pipeline_stages": state.pipeline_stages,
        }


# ──────────────────────────────────────────────
# Data Collection
# ──────────────────────────────────────────────

def _collect_worker_data(state: CreditAppraisalState) -> Dict[str, Any]:
    """Collect all extracted data from worker outputs into a flat lookup."""
    data: Dict[str, Any] = {}
    for wid, wo in state.worker_outputs.items():
        if wo.status == "completed" and wo.extracted_data:
            data[wid] = wo.extracted_data
    return data


def _get_rpt_concealment(
    state: Optional[CreditAppraisalState],
) -> Optional[Dict[str, Any]]:
    """
    Extract RPT concealment finding from raw_data_package contradictions.

    T1.2: The consolidator stores rpt_concealment entries in contradictions.
    Returns the concealment dict if found, None otherwise.
    """
    if not state or not state.raw_data_package:
        return None
    for c in state.raw_data_package.contradictions:
        if c.get("type") == "rpt_concealment":
            return c
    return None


# ──────────────────────────────────────────────
# Hard Block Checks
# ──────────────────────────────────────────────

async def _check_hard_blocks(
    worker_data: Dict[str, Any],
    emitter: ThinkingEventEmitter,
) -> List[HardBlock]:
    """Check for hard block triggers that cap the score."""
    blocks = []

    # Check W1 (Annual Report) for litigation, auditor flags
    w1 = worker_data.get("W1", {})

    # Check litigation for NCLT proceedings
    lit = w1.get("litigation_disclosure", {})
    if lit:
        for case in lit.get("cases", []):
            if case.get("forum", "").upper() == "NCLT" and case.get("status") == "pending":
                blocks.append(HardBlock(
                    trigger="nclt_active",
                    score_cap=HARD_BLOCK_RULES["nclt_active"],
                    evidence=f"Active NCLT case: {case.get('type', 'unknown')} — ₹{case.get('amount', '?')}L",
                    source="Annual Report — Litigation Disclosure",
                ))
                await emitter.critical(
                    f"HARD BLOCK: Active NCLT proceedings detected (₹{case.get('amount', '?')}L)",
                    source_document="Annual Report",
                )

    return blocks


# ──────────────────────────────────────────────
# Scoring Modules
# ──────────────────────────────────────────────

def _make_entry(
    module: ScoreModule, metric: str, value: str, formula: str,
    source: str, page: int, excerpt: str, benchmark: str,
    impact: int, reasoning: str, confidence: float = 0.85,
) -> ScoreBreakdownEntry:
    """Helper to create a ScoreBreakdownEntry with all required fields."""
    # Clamp impact to module limits
    limits = MODULE_LIMITS[module]
    impact = max(limits["max_negative"], min(limits["max_positive"], impact))

    return ScoreBreakdownEntry(
        module=module,
        metric_name=metric,
        metric_value=value,
        computation_formula=formula,
        source_document=source,
        source_page=page,
        source_excerpt=excerpt,
        benchmark_context=benchmark,
        score_impact=impact,
        reasoning=reasoning,
        confidence=confidence,
    )


async def _score_capacity(
    data: Dict[str, Any], emitter: ThinkingEventEmitter,
) -> Tuple[List[ScoreBreakdownEntry], int]:
    """Score the CAPACITY module — financial ability to repay."""
    entries = []
    w1 = data.get("W1", {})
    w2 = data.get("W2", {})

    # Revenue growth
    rev = w1.get("revenue", {})
    fy23 = rev.get("fy2023")
    fy22 = rev.get("fy2022")
    if fy23 and fy22 and fy22 > 0:
        growth = (fy23 - fy22) / fy22 * 100
        if growth > 15:
            impact = 40
        elif growth > 5:
            impact = 20
        elif growth > 0:
            impact = 5
        else:
            impact = -30

        entries.append(_make_entry(
            module=ScoreModule.CAPACITY,
            metric="Revenue Growth YoY",
            value=f"{growth:.1f}%",
            formula=f"(FY23 {fy23} - FY22 {fy22}) / FY22 × 100",
            source="Annual Report",
            page=rev.get("source_page", 45),
            excerpt=f"Revenue FY2023: ₹{fy23}L, FY2022: ₹{fy22}L",
            benchmark="Good: >15%, Moderate: 5-15%, Weak: <0%",
            impact=impact,
            reasoning=f"YoY revenue growth of {growth:.1f}% " + (
                "indicates strong business trajectory" if growth > 15 else
                "shows moderate growth" if growth > 5 else
                "shows declining revenue — capacity concern"
            ),
            confidence=0.90,
        ))
        await emitter.computed(
            f"Revenue growth: {growth:.1f}% → impact {impact:+d}",
            source_document="Annual Report",
            confidence=0.90,
        )

    # EBITDA margin
    ebitda = w1.get("ebitda", {})
    ebitda_val = ebitda.get("fy2023")
    if ebitda_val and fy23 and fy23 > 0:
        margin = ebitda_val / fy23 * 100
        if margin > 20:
            impact = 35
        elif margin > 12:
            impact = 15
        else:
            impact = -15

        entries.append(_make_entry(
            module=ScoreModule.CAPACITY,
            metric="EBITDA Margin",
            value=f"{margin:.1f}%",
            formula=f"EBITDA {ebitda_val} / Revenue {fy23} × 100",
            source="Annual Report",
            page=ebitda.get("source_page", 45),
            excerpt=f"EBITDA: ₹{ebitda_val}L, Revenue: ₹{fy23}L",
            benchmark="Strong: >20%, Adequate: 12-20%, Weak: <12%",
            impact=impact,
            reasoning=f"EBITDA margin of {margin:.1f}% " + (
                "shows strong operating efficiency" if margin > 20 else
                "is adequate for the sector" if margin > 12 else
                "indicates thin margins — capacity risk"
            ),
            confidence=0.88,
        ))
        await emitter.computed(
            f"EBITDA margin: {margin:.1f}% → impact {impact:+d}",
            source_document="Annual Report",
        )

    # EMI regularity from bank statement
    emi = w2.get("emi_regularity", {})
    reg_pct = emi.get("regularity_pct")
    if reg_pct is not None:
        if reg_pct >= 95:
            impact = 30
        elif reg_pct >= 80:
            impact = 10
        else:
            impact = -40

        entries.append(_make_entry(
            module=ScoreModule.CAPACITY,
            metric="EMI Regularity",
            value=f"{reg_pct}%",
            formula=f"On-time months ({emi.get('on_time', '?')}) / Total months ({emi.get('total_months', '?')}) × 100",
            source="Bank Statement",
            page=12,
            excerpt=f"EMI regularity: {reg_pct}% ({emi.get('on_time', '?')}/{emi.get('total_months', '?')} months on-time)",
            benchmark="Excellent: ≥95%, Good: 80-95%, Poor: <80%",
            impact=impact,
            reasoning=f"EMI regularity of {reg_pct}% " + (
                "demonstrates strong repayment discipline" if reg_pct >= 95 else
                "shows mostly regular payments" if reg_pct >= 80 else
                "indicates payment irregularity — high risk"
            ),
            confidence=0.93,
        ))
        await emitter.computed(
            f"EMI regularity: {reg_pct}% → impact {impact:+d}",
            source_document="Bank Statement",
        )

    # Clamp total to module limits
    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.CAPACITY]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    await emitter.decided(
        f"CAPACITY module: {total:+d} points ({len(entries)} metrics)",
        confidence=0.90,
    )

    return entries, total


async def _score_character(
    data: Dict[str, Any], emitter: ThinkingEventEmitter,
    state: Optional[CreditAppraisalState] = None,
) -> Tuple[List[ScoreBreakdownEntry], int]:
    """Score the CHARACTER module — borrower integrity & governance."""
    entries = []
    w1 = data.get("W1", {})
    w2 = data.get("W2", {})

    # Auditor qualifications
    quals = w1.get("auditor_qualifications", [])
    if quals:
        impact = -25 * len(quals)
        entries.append(_make_entry(
            module=ScoreModule.CHARACTER,
            metric="Auditor Qualifications",
            value=f"{len(quals)} qualification(s)",
            formula=f"-25 × {len(quals)} qualifications",
            source="Annual Report",
            page=quals[0].get("source_page", 9) if quals else 9,
            excerpt=quals[0].get("detail", "N/A") if quals else "N/A",
            benchmark="Clean: 0, Acceptable: 1, Concerning: ≥2",
            impact=impact,
            reasoning=f"{len(quals)} auditor qualification(s) detected — raises governance concerns",
            confidence=0.88,
        ))
        await emitter.flagged(
            f"Auditor qualification(s): {len(quals)} → impact {impact:+d}",
            source_document="Annual Report",
        )
    else:
        entries.append(_make_entry(
            module=ScoreModule.CHARACTER,
            metric="Auditor Qualifications",
            value="Clean opinion",
            formula="Clean audit → +30",
            source="Annual Report",
            page=9,
            excerpt="Unqualified audit opinion",
            benchmark="Clean: +30, Qualified: -25 per qual",
            impact=30,
            reasoning="Clean audit opinion indicates good governance and transparent reporting",
            confidence=0.92,
        ))

    # RPT verification
    rpts = w1.get("rpts", {})
    rpt_count = rpts.get("count", 0)
    rpt_amount = rpts.get("total_amount", 0)
    if rpt_count > 0:
        # More RPTs = higher risk
        if rpt_count <= 2 and rpt_amount < 500:
            impact = 10  # Minimal RPTs, well-disclosed
        elif rpt_count <= 5:
            impact = -15  # Moderate RPTs
        else:
            impact = -50  # Excessive RPTs

        entries.append(_make_entry(
            module=ScoreModule.CHARACTER,
            metric="Related Party Transactions",
            value=f"{rpt_count} RPTs totalling ₹{rpt_amount}L",
            formula=f"RPT count={rpt_count}, amount=₹{rpt_amount}L",
            source="Annual Report",
            page=rpts.get("source_page", 68),
            excerpt=f"{rpt_count} RPTs disclosed: ₹{rpt_amount} lakhs",
            benchmark="Low: ≤2 RPTs <₹500L, Moderate: 3-5, High: >5",
            impact=impact,
            reasoning=f"{rpt_count} RPTs totalling ₹{rpt_amount}L — " + (
                "minimal and well-disclosed" if impact > 0 else
                "moderate level needs monitoring" if impact > -30 else
                "excessive RPTs raise governance red flags"
            ),
            confidence=0.85,
        ))
        await emitter.computed(
            f"RPT count: {rpt_count}, amount: ₹{rpt_amount}L → impact {impact:+d}",
        )

    # Cheque bounces from bank statement
    bounces = w2.get("bounces", {})
    bounce_count = bounces.get("count", 0)
    if bounce_count > 0:
        impact = -20 * bounce_count
        entries.append(_make_entry(
            module=ScoreModule.CHARACTER,
            metric="Cheque Bounces",
            value=f"{bounce_count} bounces",
            formula=f"-20 × {bounce_count} bounces",
            source="Bank Statement",
            page=7,
            excerpt=f"{bounce_count} cheque bounces totalling ₹{bounces.get('total_amount', '?')}L",
            benchmark="None: +15, 1-2: -20 each, ≥3: -20 each + extra -10",
            impact=impact,
            reasoning=f"{bounce_count} cheque bounces indicate potential cash flow stress",
            confidence=0.91,
        ))
        await emitter.flagged(
            f"Cheque bounces: {bounce_count} → impact {impact:+d}",
            source_document="Bank Statement",
        )
    else:
        entries.append(_make_entry(
            module=ScoreModule.CHARACTER,
            metric="Cheque Bounces",
            value="0 bounces",
            formula="No bounces → +15",
            source="Bank Statement",
            page=1,
            excerpt="No cheque bounces in 12-month period",
            benchmark="None: +15, 1-2: -20 each, ≥3: -20 each + extra",
            impact=15,
            reasoning="Zero cheque bounces demonstrates consistent financial discipline",
            confidence=0.94,
        ))

    # RPT Concealment — T1.2: Cross-check Board Minutes vs Annual Report
    rpt_concealment = _get_rpt_concealment(state)
    if rpt_concealment:
        concealed_count = rpt_concealment.get("count_mismatch", 0)
        concealed_amount = rpt_concealment.get("concealed_amount", 0)
        missing_parties = rpt_concealment.get("missing_parties", [])
        impact = -35  # Fixed penalty per spec
        entries.append(_make_entry(
            module=ScoreModule.CHARACTER,
            metric="RPT Concealment (BM vs AR)",
            value=(
                f"{concealed_count} RPT(s) concealed, ₹{concealed_amount:.1f}L undisclosed"
            ),
            formula=f"RPT concealment detected → -35",
            source="Board Minutes vs Annual Report",
            page=68,
            excerpt=(
                f"Board Minutes: {rpt_concealment.get('board_minutes_count', '?')} RPTs approved. "
                f"Annual Report: {rpt_concealment.get('annual_report_count', '?')} disclosed. "
                f"Missing parties: {', '.join(missing_parties) if missing_parties else 'N/A'}"
            ),
            benchmark="No concealment: 0, Any concealment: -35",
            impact=impact,
            reasoning=(
                f"Board Minutes record {rpt_concealment.get('board_minutes_count', '?')} RPT approvals but "
                f"Annual Report discloses only {rpt_concealment.get('annual_report_count', '?')}. "
                f"₹{concealed_amount:.1f}L in undisclosed RPTs indicates active governance concealment."
            ),
            confidence=0.88,
        ))
        await emitter.critical(
            f"RPT Concealment: {concealed_count} hidden RPTs (₹{concealed_amount:.1f}L) → impact {impact:+d}",
            source_document="Board Minutes vs Annual Report",
        )

    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.CHARACTER]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    await emitter.decided(
        f"CHARACTER module: {total:+d} points ({len(entries)} metrics)",
        confidence=0.88,
    )

    return entries, total


async def _score_capital(
    data: Dict[str, Any], emitter: ThinkingEventEmitter,
) -> Tuple[List[ScoreBreakdownEntry], int]:
    """Score the CAPITAL module — balance sheet strength."""
    entries = []
    w1 = data.get("W1", {})

    # Debt-to-equity ratio
    debt = w1.get("total_debt", {}).get("fy2023")
    nw = w1.get("net_worth", {}).get("fy2023")
    if debt is not None and nw and nw > 0:
        de_ratio = debt / nw
        if de_ratio < 1.0:
            impact = 40
        elif de_ratio < 2.0:
            impact = 15
        elif de_ratio < 3.0:
            impact = -15
        else:
            impact = -50

        entries.append(_make_entry(
            module=ScoreModule.CAPITAL,
            metric="Debt-to-Equity Ratio",
            value=f"{de_ratio:.2f}x",
            formula=f"Total Debt ₹{debt}L / Net Worth ₹{nw}L",
            source="Annual Report",
            page=w1.get("total_debt", {}).get("source_page", 50),
            excerpt=f"Total Debt: ₹{debt}L, Net Worth: ₹{nw}L",
            benchmark="Conservative: <1x (+40), Moderate: 1-2x (+15), High: 2-3x (-15), Very High: >3x (-50)",
            impact=impact,
            reasoning=f"D/E ratio of {de_ratio:.2f}x " + (
                "shows conservative leverage" if de_ratio < 1 else
                "is within acceptable range" if de_ratio < 2 else
                "indicates high leverage" if de_ratio < 3 else
                "shows excessive leverage — significant risk"
            ),
            confidence=0.90,
        ))
        await emitter.computed(
            f"D/E ratio: {de_ratio:.2f}x → impact {impact:+d}",
            source_document="Annual Report",
        )

    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.CAPITAL]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    await emitter.decided(f"CAPITAL module: {total:+d} points", confidence=0.87)
    return entries, total


async def _score_collateral(
    data: Dict[str, Any], emitter: ThinkingEventEmitter,
) -> Tuple[List[ScoreBreakdownEntry], int]:
    """Score the COLLATERAL module — asset coverage quality."""
    entries = []

    # T0: Placeholder — collateral data requires deeper document parsing
    # In T1+, this reads from property valuations, charge registers, etc.
    entries.append(_make_entry(
        module=ScoreModule.COLLATERAL,
        metric="Collateral Coverage",
        value="Assumed — pending T1 valuation",
        formula="Default moderate collateral assumption",
        source="Assessment Default",
        page=0,
        excerpt="Collateral assessment pending detailed valuation",
        benchmark="Strong: >1.5x coverage, Adequate: 1-1.5x, Weak: <1x",
        impact=15,
        reasoning="Default moderate collateral score — full valuation in T1",
        confidence=0.50,
    ))

    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.COLLATERAL]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    await emitter.decided(f"COLLATERAL module: {total:+d} points (T0 default)", confidence=0.50)
    return entries, total


async def _score_conditions(
    data: Dict[str, Any], emitter: ThinkingEventEmitter,
) -> Tuple[List[ScoreBreakdownEntry], int]:
    """Score the CONDITIONS module — external / market factors."""
    entries = []

    # GST filing compliance (from W3)
    w3 = data.get("W3", {})
    filing = w3.get("filing_compliance", {})
    reg_pct = filing.get("regularity_pct")
    if reg_pct is not None:
        if reg_pct >= 100:
            impact = 20
        elif reg_pct >= 80:
            impact = 5
        else:
            impact = -20

        entries.append(_make_entry(
            module=ScoreModule.CONDITIONS,
            metric="GST Filing Compliance",
            value=f"{reg_pct}% on-time filing",
            formula=f"Filed {filing.get('months_filed', '?')}/{filing.get('months_filed', 12)} months on-time",
            source="GST Returns",
            page=12,
            excerpt=f"GST filing regularity: {reg_pct}%",
            benchmark="Perfect: 100% (+20), Good: 80-99% (+5), Poor: <80% (-20)",
            impact=impact,
            reasoning=f"GST filing regularity at {reg_pct}% — " + (
                "perfect compliance record" if reg_pct >= 100 else
                "mostly compliant" if reg_pct >= 80 else
                "irregular filing raises regulatory risk"
            ),
            confidence=0.94,
        ))
        await emitter.computed(
            f"GST file regularity: {reg_pct}% → impact {impact:+d}",
        )

    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.CONDITIONS]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    await emitter.decided(f"CONDITIONS module: {total:+d} points", confidence=0.85)
    return entries, total


async def _score_compound(
    data: Dict[str, Any],
    state: CreditAppraisalState,
    emitter: ThinkingEventEmitter,
) -> Tuple[List[ScoreBreakdownEntry], int]:
    """Score the COMPOUND module — cross-verification and cascade signals."""
    entries = []

    # Revenue cross-verification deviation
    rdp = state.raw_data_package
    if rdp and rdp.cross_verifications:
        for cv in rdp.cross_verifications:
            if cv.field_name == "Revenue":
                dev = cv.max_deviation_pct
                if dev <= 5:
                    impact = 25
                    reasoning = "Revenue verified across multiple sources with minimal deviation"
                elif dev <= 15:
                    impact = -10
                    reasoning = f"Revenue deviation of {dev:.1f}% across sources — moderate concern"
                else:
                    impact = -40
                    reasoning = f"Revenue deviation of {dev:.1f}% — significant data quality issue"

                entries.append(_make_entry(
                    module=ScoreModule.COMPOUND,
                    metric="Revenue Cross-Verification",
                    value=f"{dev:.1f}% deviation",
                    formula=f"Max deviation across {len(cv.sources)} sources",
                    source="Cross-Verification Engine",
                    page=0,
                    excerpt=f"Sources: {', '.join(cv.sources.keys())}",
                    benchmark="Good: ≤5%, Moderate: 5-15%, Poor: >15%",
                    impact=impact,
                    reasoning=reasoning,
                    confidence=0.90,
                ))
                await emitter.computed(
                    f"Revenue cross-check: {dev:.1f}% deviation → {impact:+d}",
                )

            elif "ITC" in cv.field_name:
                dev = cv.max_deviation_pct
                if dev > 5:
                    # T1.1: Graduated ITC scoring based on severity tiers
                    if dev > 20:
                        impact = -50
                        severity_label = "Critical"
                        reasoning_detail = (
                            f"GSTR-2A vs 3B mismatch of {dev:.1f}% is critically high — "
                            f"strong indicator of fake invoicing or bogus ITC claims. "
                            f"Industry average is ~3.5%. "
                            f"Requires immediate supplier verification."
                        )
                    elif dev > 15:
                        impact = -35
                        severity_label = "High"
                        reasoning_detail = (
                            f"GSTR-2A vs 3B mismatch of {dev:.1f}% significantly exceeds "
                            f"the industry average of ~3.5%. Likely causes: systematic late "
                            f"supplier filing or potential ITC fraud. Needs detailed "
                            f"supplier-wise reconciliation."
                        )
                    elif dev > 10:
                        impact = -20
                        severity_label = "Moderate"
                        reasoning_detail = (
                            f"GSTR-2A vs 3B mismatch of {dev:.1f}% is moderately elevated "
                            f"above the industry average of ~3.5%. May be due to timing "
                            f"differences in supplier filings, but warrants review."
                        )
                    else:
                        impact = -10
                        severity_label = "Low"
                        reasoning_detail = (
                            f"GSTR-2A vs 3B mismatch of {dev:.1f}% is slightly above the "
                            f"5% threshold. Likely caused by normal timing differences in "
                            f"supplier filings. Minimal compliance concern."
                        )

                    entries.append(_make_entry(
                        module=ScoreModule.COMPOUND,
                        metric="GSTR-2A vs 3B Mismatch",
                        value=f"{dev:.1f}% ITC over-claim ({severity_label})",
                        formula="(Claimed ITC - Available ITC) / Available ITC × 100",
                        source="GST Returns",
                        page=10,
                        excerpt=cv.note or f"ITC mismatch: {dev:.1f}%",
                        benchmark=(
                            "Normal: ≤5% (-0), Low: 5-10% (-10), "
                            "Moderate: 10-15% (-20), High: 15-20% (-35), "
                            "Critical: >20% (-50)"
                        ),
                        impact=impact,
                        reasoning=reasoning_detail,
                        confidence=0.92 if dev <= 10 else 0.95,
                    ))
                    await emitter.flagged(
                        f"ITC mismatch: {dev:.1f}% [{severity_label}] → {impact:+d}",
                        source_document="GST Returns",
                    )

    # Contradictions penalty
    if rdp and rdp.contradictions:
        impact = -10 * len(rdp.contradictions)
        entries.append(_make_entry(
            module=ScoreModule.COMPOUND,
            metric="Data Contradictions",
            value=f"{len(rdp.contradictions)} contradiction(s)",
            formula=f"-10 × {len(rdp.contradictions)} contradictions",
            source="Consolidator",
            page=0,
            excerpt=str(rdp.contradictions[0]) if rdp.contradictions else "N/A",
            benchmark="None: 0, Each: -10",
            impact=impact,
            reasoning=f"{len(rdp.contradictions)} contradiction(s) detected across document sources",
            confidence=0.75,
        ))

    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.COMPOUND]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    await emitter.decided(f"COMPOUND module: {total:+d} points", confidence=0.85)
    return entries, total


# ──────────────────────────────────────────────
# CAM Generation
# ──────────────────────────────────────────────

async def _generate_cam(
    session_id: str,
    company_name: str,
    score: int,
    band: ScoreBand,
    outcome: AssessmentOutcome,
    recommendation: str,
    module_summaries: List[ScoreModuleSummary],
    all_entries: List[ScoreBreakdownEntry],
    hard_blocks: List[HardBlock],
    worker_data: Dict[str, Any],
    emitter: ThinkingEventEmitter,
) -> str:
    """
    Generate Credit Appraisal Memo as a text file.

    T0: Generates a structured text CAM.
    T1+: Will use python-docx for proper Word document (Indian banking standard).
    """
    await emitter.read("Generating Credit Appraisal Memo...")

    # Build CAM content
    cam_lines = [
        "=" * 80,
        "CREDIT APPRAISAL MEMO — CONFIDENTIAL",
        "=" * 80,
        f"Date: {datetime.utcnow().strftime('%d %B %Y')}",
        f"Session: {session_id}",
        f"Borrower: {company_name}",
        "",
        "-" * 80,
        "EXECUTIVE SUMMARY",
        "-" * 80,
        f"Credit Score: {score}/850 ({band.value})",
        f"Recommendation: {outcome.value} — {recommendation}",
        "",
    ]

    # Hard blocks
    if hard_blocks:
        cam_lines.append("-" * 80)
        cam_lines.append("⚠️  HARD BLOCK TRIGGERS")
        cam_lines.append("-" * 80)
        for hb in hard_blocks:
            cam_lines.append(f"  • {hb.trigger}: Score capped at {hb.score_cap}")
            cam_lines.append(f"    Evidence: {hb.evidence}")
            cam_lines.append(f"    Source: {hb.source}")
        cam_lines.append("")

    # Module scores
    cam_lines.append("-" * 80)
    cam_lines.append("SCORE BREAKDOWN BY MODULE")
    cam_lines.append("-" * 80)
    for ms in module_summaries:
        cam_lines.append(
            f"  {ms.module.value:12s}: {ms.score:+4d} points "
            f"(range: {ms.max_negative:+d} to {ms.max_positive:+d}, "
            f"{len(ms.metrics)} metric(s))"
        )
    cam_lines.append(f"  {'BASE':12s}: {BASE_SCORE:+4d}")
    cam_lines.append(f"  {'TOTAL':12s}: {score:4d}/850")
    cam_lines.append("")

    # Detailed breakdown
    cam_lines.append("-" * 80)
    cam_lines.append("DETAILED METRIC BREAKDOWN")
    cam_lines.append("-" * 80)
    for entry in all_entries:
        cam_lines.append(f"  [{entry.module.value}] {entry.metric_name}: {entry.metric_value}")
        cam_lines.append(f"    Impact: {entry.score_impact:+d} | Confidence: {entry.confidence:.0%}")
        cam_lines.append(f"    Source: {entry.source_document} (p.{entry.source_page})")
        cam_lines.append(f"    Reasoning: {entry.reasoning}")
        cam_lines.append("")

    cam_lines.append("=" * 80)
    cam_lines.append("END OF CREDIT APPRAISAL MEMO")
    cam_lines.append("=" * 80)

    cam_text = "\n".join(cam_lines)

    # Save CAM to file
    cam_dir = os.path.join("data", "output", session_id)
    os.makedirs(cam_dir, exist_ok=True)
    cam_path = os.path.join(cam_dir, "credit_appraisal_memo.txt")

    with open(cam_path, "w", encoding="utf-8") as f:
        f.write(cam_text)

    await emitter.accepted(
        f"CAM generated: {len(cam_lines)} lines, saved to {cam_path}",
        confidence=0.95,
    )

    return cam_path
