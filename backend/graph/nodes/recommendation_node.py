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
from config.scoring import (
    BASE_SCORE,
    MODULE_LIMITS,
    SCORE_BANDS,
    HARD_BLOCK_RULES,
    MIN_SCORE,
    MAX_SCORE,
    CAM_OUTPUT_DIR,
    get_score_band,
    get_loan_terms as _get_loan_terms,
)

logger = logging.getLogger(__name__)


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
        cap_entries, cap_total = await _score_capacity(worker_data, emitter, state)
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
        cap2_entries, cap2_total = await _score_capital(worker_data, emitter, state)
        all_entries.extend(cap2_entries)
        module_summaries.append(ScoreModuleSummary(
            module=ScoreModule.CAPITAL,
            score=cap2_total,
            max_positive=MODULE_LIMITS[ScoreModule.CAPITAL]["max_positive"],
            max_negative=MODULE_LIMITS[ScoreModule.CAPITAL]["max_negative"],
            metrics=cap2_entries,
        ))

        # Collateral Module
        coll_entries, coll_total = await _score_collateral(worker_data, emitter, state)
        all_entries.extend(coll_entries)
        module_summaries.append(ScoreModuleSummary(
            module=ScoreModule.COLLATERAL,
            score=coll_total,
            max_positive=MODULE_LIMITS[ScoreModule.COLLATERAL]["max_positive"],
            max_negative=MODULE_LIMITS[ScoreModule.COLLATERAL]["max_negative"],
            metrics=coll_entries,
        ))

        # Conditions Module
        cond_entries, cond_total = await _score_conditions(worker_data, emitter, state)
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

        # Clamp to configured range
        final_score = max(MIN_SCORE, min(MAX_SCORE, effective_score))

        # ── Step 5: Derive band + outcome ──
        band, outcome, recommendation = get_score_band(final_score)

        await emitter.decided(
            f"Final Score: {final_score}/{MAX_SCORE} — {band.value} ({outcome.value}). "
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
                stage.message = f"Score: {final_score}/{MAX_SCORE} — {band.value}"

        await emitter.concluding(
            f"Scoring complete. {company_name}: {final_score}/{MAX_SCORE} ({band.value}). "
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
    """Check for hard block triggers that cap the score.

    Hard block triggers (per architecture):
      wilful_defaulter     → capped at 200
      active_criminal_case → capped at 150
      dscr_below_1         → capped at 300
      nclt_active          → capped at 250
    """
    blocks = []
    w1 = worker_data.get("W1", {})
    w2 = worker_data.get("W2", {})

    # 1. Wilful Defaulter (RBI list match from research / litigation disclosure)
    directors = w1.get("directors", [])
    for d in directors:
        if d.get("wilful_defaulter"):
            blocks.append(HardBlock(
                trigger="wilful_defaulter",
                score_cap=HARD_BLOCK_RULES["wilful_defaulter"],
                evidence=f"Director {d.get('name', 'Unknown')} (DIN: {d.get('din', '?')}) listed as wilful defaulter",
                source="RBI Wilful Defaulter List / Annual Report",
            ))
            await emitter.critical(
                f"HARD BLOCK: Wilful defaulter — {d.get('name', 'Unknown')} (DIN: {d.get('din', '?')})",
                source_document="RBI / Annual Report",
            )
            break  # One wilful defaulter is enough

    # Also check a top-level flag if set by research
    if w1.get("wilful_defaulter"):
        if not any(b.trigger == "wilful_defaulter" for b in blocks):
            blocks.append(HardBlock(
                trigger="wilful_defaulter",
                score_cap=HARD_BLOCK_RULES["wilful_defaulter"],
                evidence="Company flagged as wilful defaulter on RBI list",
                source="RBI Wilful Defaulter List",
            ))
            await emitter.critical(
                "HARD BLOCK: Company is a wilful defaulter (RBI list)",
                source_document="RBI",
            )

    # 2. Active Criminal Case against promoter
    lit = w1.get("litigation_disclosure", {})
    if lit:
        for case in lit.get("cases", []):
            case_type = case.get("type", "").lower()
            status = case.get("status", "").lower()
            if case_type == "criminal" and status in ("pending", "active"):
                blocks.append(HardBlock(
                    trigger="active_criminal_case",
                    score_cap=HARD_BLOCK_RULES["active_criminal_case"],
                    evidence=(
                        f"Active criminal case: {case.get('type', 'unknown')} at "
                        f"{case.get('forum', 'unknown')} — ₹{case.get('amount', '?')}L"
                    ),
                    source="Annual Report — Litigation Disclosure",
                ))
                await emitter.critical(
                    f"HARD BLOCK: Active criminal case against promoter ({case.get('forum', 'unknown')})",
                    source_document="Annual Report",
                )
                break  # One criminal case is enough

    # 3. DSCR < 1.0x — borrower cannot service debt from earnings
    ebitda_val = w1.get("ebitda", {}).get("fy2023")
    interest_exp = w1.get("interest_expense", {}).get("fy2023")
    if ebitda_val is not None and interest_exp and interest_exp > 0:
        dscr = ebitda_val / interest_exp
        if dscr < 1.0:
            blocks.append(HardBlock(
                trigger="dscr_below_1",
                score_cap=HARD_BLOCK_RULES["dscr_below_1"],
                evidence=f"DSCR = {dscr:.2f}x (EBITDA ₹{ebitda_val}L / Interest ₹{interest_exp}L)",
                source="Annual Report — Financial Statements",
            ))
            await emitter.critical(
                f"HARD BLOCK: DSCR {dscr:.2f}x < 1.0 — borrower cannot cover debt service",
                source_document="Annual Report",
            )

    # 4. NCLT active proceedings (insolvency)
    if lit:
        for case in lit.get("cases", []):
            if case.get("forum", "").upper() == "NCLT" and case.get("status", "").lower() in ("pending", "active"):
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
                break  # One NCLT case is enough

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
    state: Optional[CreditAppraisalState] = None,
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

    # DSCR (Debt Service Coverage Ratio)
    ebitda_val = w1.get("ebitda", {}).get("fy2023")
    interest_exp = w1.get("interest_expense", {}).get("fy2023")
    if ebitda_val and interest_exp and interest_exp > 0:
        dscr = ebitda_val / interest_exp
        if dscr >= 2.0:
            impact = 40
        elif dscr >= 1.5:
            impact = 25
        elif dscr >= 1.2:
            impact = 10
        elif dscr >= 1.0:
            impact = -10
        else:
            impact = -50

        entries.append(_make_entry(
            module=ScoreModule.CAPACITY,
            metric="DSCR",
            value=f"{dscr:.2f}x",
            formula=f"EBITDA ₹{ebitda_val}L / Interest ₹{interest_exp}L",
            source="Annual Report",
            page=w1.get("interest_expense", {}).get("source_page", 46),
            excerpt=f"EBITDA: ₹{ebitda_val}L, Interest Expense: ₹{interest_exp}L → DSCR {dscr:.2f}x",
            benchmark="Strong: ≥2.0x (+40), Good: 1.5-2.0x (+25), Adequate: 1.2-1.5x (+10), Thin: 1.0-1.2x (-10), Deficit: <1.0x (-50)",
            impact=impact,
            reasoning=f"DSCR of {dscr:.2f}x " + (
                "demonstrates strong debt servicing capacity" if dscr >= 2.0 else
                "indicates good ability to service debt" if dscr >= 1.5 else
                "shows adequate but thin coverage" if dscr >= 1.2 else
                "is marginally above breakeven — high risk" if dscr >= 1.0 else
                "is below 1.0x — borrower cannot cover debt service from earnings"
            ),
            confidence=0.92,
        ))
        await emitter.computed(
            f"DSCR: {dscr:.2f}x → impact {impact:+d}",
            source_document="Annual Report",
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
    state: Optional[CreditAppraisalState] = None,
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

    # Net Worth Adequacy — compare net worth to requested loan amount
    loan_amount = None
    if state and state.company and state.company.loan_amount_numeric:
        loan_amount = state.company.loan_amount_numeric
    if nw and loan_amount and loan_amount > 0:
        nw_coverage = nw / loan_amount
        if nw_coverage >= 1.5:
            impact = 25
        elif nw_coverage >= 1.0:
            impact = 10
        elif nw_coverage >= 0.5:
            impact = -10
        else:
            impact = -30

        entries.append(_make_entry(
            module=ScoreModule.CAPITAL,
            metric="Net Worth Adequacy",
            value=f"{nw_coverage:.2f}x loan amount",
            formula=f"Net Worth ₹{nw}L / Loan Amount ₹{loan_amount}L",
            source="Annual Report",
            page=w1.get("net_worth", {}).get("source_page", 50),
            excerpt=f"Net Worth: ₹{nw}L vs Loan Requested: ₹{loan_amount}L",
            benchmark="Strong: ≥1.5x (+25), Adequate: 1-1.5x (+10), Thin: 0.5-1x (-10), Weak: <0.5x (-30)",
            impact=impact,
            reasoning=f"Net worth covers {nw_coverage:.2f}x the requested loan — " + (
                "strong capital base relative to borrowing" if nw_coverage >= 1.5 else
                "adequate net worth backing" if nw_coverage >= 1.0 else
                "borrower's net worth is thin relative to loan" if nw_coverage >= 0.5 else
                "net worth significantly below loan amount — high capital risk"
            ),
            confidence=0.88,
        ))
        await emitter.computed(
            f"Net Worth Adequacy: {nw_coverage:.2f}x loan → impact {impact:+d}",
            source_document="Annual Report",
        )

    # Interest Coverage Ratio — EBITDA / Interest Expense
    ebitda_val = w1.get("ebitda", {}).get("fy2023")
    interest_exp = w1.get("interest_expense", {}).get("fy2023")
    if ebitda_val and interest_exp and interest_exp > 0:
        icr = ebitda_val / interest_exp
        if icr >= 4.0:
            impact = 20
        elif icr >= 2.5:
            impact = 10
        elif icr >= 1.5:
            impact = -5
        else:
            impact = -25

        entries.append(_make_entry(
            module=ScoreModule.CAPITAL,
            metric="Interest Coverage Ratio",
            value=f"{icr:.2f}x",
            formula=f"EBITDA ₹{ebitda_val}L / Interest Expense ₹{interest_exp}L",
            source="Annual Report",
            page=w1.get("interest_expense", {}).get("source_page", 46),
            excerpt=f"EBITDA: ₹{ebitda_val}L, Interest: ₹{interest_exp}L → ICR {icr:.2f}x",
            benchmark="Strong: ≥4x (+20), Good: 2.5-4x (+10), Adequate: 1.5-2.5x (-5), Weak: <1.5x (-25)",
            impact=impact,
            reasoning=f"ICR of {icr:.2f}x " + (
                "shows comfortable interest servicing ability" if icr >= 4.0 else
                "indicates good interest coverage" if icr >= 2.5 else
                "interest coverage is thin" if icr >= 1.5 else
                "interest coverage inadequate — earnings barely cover interest"
            ),
            confidence=0.90,
        ))
        await emitter.computed(
            f"Interest Coverage: {icr:.2f}x → impact {impact:+d}",
            source_document="Annual Report",
        )

    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.CAPITAL]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    await emitter.decided(f"CAPITAL module: {total:+d} points ({len(entries)} metrics)", confidence=0.87)
    return entries, total


async def _score_collateral(
    data: Dict[str, Any], emitter: ThinkingEventEmitter,
    state: Optional[CreditAppraisalState] = None,
) -> Tuple[List[ScoreBreakdownEntry], int]:
    """Score the COLLATERAL module — asset coverage quality."""
    entries = []
    w7 = data.get("W7", {})

    # Promoter Holding % — higher holding = more skin in the game
    promoter_pct = w7.get("promoter_holding_pct")
    if promoter_pct is not None:
        if promoter_pct >= 60:
            impact = 25
        elif promoter_pct >= 40:
            impact = 10
        elif promoter_pct >= 25:
            impact = -5
        else:
            impact = -20

        entries.append(_make_entry(
            module=ScoreModule.COLLATERAL,
            metric="Promoter Holding",
            value=f"{promoter_pct:.1f}%",
            formula=f"Promoter shareholding: {promoter_pct:.1f}%",
            source="Shareholding Pattern",
            page=w7.get("source_page", 1),
            excerpt=f"Promoter and promoter group holding: {promoter_pct:.1f}%",
            benchmark="Strong: ≥60% (+25), Good: 40-60% (+10), Moderate: 25-40% (-5), Low: <25% (-20)",
            impact=impact,
            reasoning=f"Promoter holding at {promoter_pct:.1f}% " + (
                "shows strong promoter commitment and alignment" if promoter_pct >= 60 else
                "indicates good promoter stake" if promoter_pct >= 40 else
                "promoter holding is moderate — limited skin in game" if promoter_pct >= 25 else
                "low promoter holding — weak alignment with lender interests"
            ),
            confidence=0.92,
        ))
        await emitter.computed(
            f"Promoter holding: {promoter_pct:.1f}% → impact {impact:+d}",
            source_document="Shareholding Pattern",
        )

    # Promoter Pledge % — pledged shares indicate financial stress
    pledge_pct = w7.get("promoter_pledge_pct")
    if pledge_pct is not None:
        if pledge_pct == 0:
            impact = 20
        elif pledge_pct <= 10:
            impact = 5
        elif pledge_pct <= 30:
            impact = -10
        else:
            impact = -25

        entries.append(_make_entry(
            module=ScoreModule.COLLATERAL,
            metric="Promoter Pledge",
            value=f"{pledge_pct:.1f}% pledged",
            formula=f"Pledged shares / Promoter holding × 100 = {pledge_pct:.1f}%",
            source="Shareholding Pattern",
            page=w7.get("source_page", 1),
            excerpt=f"Promoter shares pledged: {pledge_pct:.1f}%",
            benchmark="None: 0% (+20), Low: ≤10% (+5), Moderate: 10-30% (-10), High: >30% (-25)",
            impact=impact,
            reasoning=f"Promoter pledge at {pledge_pct:.1f}% " + (
                "— no shares pledged, clean collateral position" if pledge_pct == 0 else
                "is minimal, limited concern" if pledge_pct <= 10 else
                "indicates moderate financial stress on promoters" if pledge_pct <= 30 else
                "is high — significant promoter distress, collateral at risk"
            ),
            confidence=0.90,
        ))
        await emitter.computed(
            f"Promoter pledge: {pledge_pct:.1f}% → impact {impact:+d}",
            source_document="Shareholding Pattern",
        )

    # If no W7 data available, use a reduced-confidence default
    if not entries:
        entries.append(_make_entry(
            module=ScoreModule.COLLATERAL,
            metric="Collateral Coverage",
            value="Data unavailable — default assessment",
            formula="No shareholding data available → default moderate",
            source="Assessment Default",
            page=0,
            excerpt="Shareholding pattern not provided; collateral scored at default",
            benchmark="Strong: >1.5x, Adequate: 1-1.5x, Weak: <1x",
            impact=5,
            reasoning="Shareholding data unavailable; applying conservative default score",
            confidence=0.40,
        ))

    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.COLLATERAL]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    conf_label = f"({len(entries)} metrics)" if any("Default" not in e.metric_name for e in entries) else "(default)"
    await emitter.decided(f"COLLATERAL module: {total:+d} points {conf_label}", confidence=0.85 if len(entries) > 1 else 0.40)
    return entries, total


async def _score_conditions(
    data: Dict[str, Any], emitter: ThinkingEventEmitter,
    state: Optional[CreditAppraisalState] = None,
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

    # Rating Outlook (from W8 — Rating Report)
    w8 = data.get("W8", {})
    outlook = w8.get("outlook", "").lower() if w8.get("outlook") else None
    current_rating = w8.get("current_rating")
    if outlook:
        if outlook in ("positive", "upgrade"):
            impact = 20
        elif outlook == "stable":
            impact = 10
        elif outlook in ("negative", "watch"):
            impact = -15
        else:
            impact = 0  # unknown outlook

        if impact != 0:
            entries.append(_make_entry(
                module=ScoreModule.CONDITIONS,
                metric="Rating Outlook",
                value=f"{current_rating or 'N/A'} ({outlook.capitalize()})",
                formula=f"Rating: {current_rating or 'N/A'}, Outlook: {outlook.capitalize()}",
                source="Rating Report",
                page=w8.get("source_page", 1),
                excerpt=f"Current rating: {current_rating or 'N/A'}, Outlook: {outlook.capitalize()}",
                benchmark="Positive/Upgrade: +20, Stable: +10, Negative/Watch: -15",
                impact=impact,
                reasoning=f"Rating outlook is {outlook} " + (
                    "— positive momentum in credit quality" if outlook in ("positive", "upgrade") else
                    "— stable credit conditions" if outlook == "stable" else
                    "— deteriorating credit conditions, heightened risk"
                ),
                confidence=0.88,
            ))
            await emitter.computed(
                f"Rating outlook: {outlook.capitalize()} → impact {impact:+d}",
                source_document="Rating Report",
            )

    total = sum(e.score_impact for e in entries)
    limits = MODULE_LIMITS[ScoreModule.CONDITIONS]
    total = max(limits["max_negative"], min(limits["max_positive"], total))

    await emitter.decided(f"CONDITIONS module: {total:+d} points ({len(entries)} metrics)", confidence=0.85)
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
    Generate Credit Appraisal Memo as a structured text file.

    Sections:
      1. Header + Executive Summary
      2. Hard Block Triggers (if any)
      3. Key Financial Metrics
      4. Score Breakdown by Module
      5. Cross-Verification Summary
      6. Risk Flags
      7. Loan Terms Recommendation
      8. Detailed Metric Breakdown
      9. Footer
    """
    await emitter.read("Generating Credit Appraisal Memo...")

    w1 = worker_data.get("W1", {})

    # ── 1. Header + Executive Summary ──
    cam_lines = [
        "=" * 80,
        "CREDIT APPRAISAL MEMO — CONFIDENTIAL",
        "=" * 80,
        f"Date: {datetime.utcnow().strftime('%d %B %Y')}",
        f"Session: {session_id}",
        f"Borrower: {company_name}",
        "",
        "-" * 80,
        "1. EXECUTIVE SUMMARY",
        "-" * 80,
        f"Credit Score: {score}/{MAX_SCORE} ({band.value})",
        f"Recommendation: {outcome.value} — {recommendation}",
        "",
    ]

    # ── 2. Hard Blocks ──
    if hard_blocks:
        cam_lines.append("-" * 80)
        cam_lines.append("2. HARD BLOCK TRIGGERS")
        cam_lines.append("-" * 80)
        for hb in hard_blocks:
            cam_lines.append(f"  • {hb.trigger}: Score capped at {hb.score_cap}")
            cam_lines.append(f"    Evidence: {hb.evidence}")
            cam_lines.append(f"    Source: {hb.source}")
        cam_lines.append("")

    # ── 3. Key Financial Metrics ──
    cam_lines.append("-" * 80)
    cam_lines.append("3. KEY FINANCIAL METRICS")
    cam_lines.append("-" * 80)

    rev = w1.get("revenue", {})
    fy23_rev = rev.get("fy2023")
    fy22_rev = rev.get("fy2022")
    if fy23_rev:
        cam_lines.append(f"  Revenue (FY2023):     ₹{fy23_rev:,.0f}L")
    if fy22_rev and fy23_rev:
        growth = (fy23_rev - fy22_rev) / fy22_rev * 100
        cam_lines.append(f"  Revenue Growth YoY:   {growth:.1f}%")

    ebitda = w1.get("ebitda", {}).get("fy2023")
    if ebitda and fy23_rev:
        cam_lines.append(f"  EBITDA (FY2023):      ₹{ebitda:,.0f}L ({ebitda/fy23_rev*100:.1f}% margin)")

    debt = w1.get("total_debt", {}).get("fy2023")
    nw = w1.get("net_worth", {}).get("fy2023")
    if debt is not None and nw and nw > 0:
        cam_lines.append(f"  Debt-to-Equity:       {debt/nw:.2f}x")
    if nw:
        cam_lines.append(f"  Net Worth (FY2023):   ₹{nw:,.0f}L")

    interest = w1.get("interest_expense", {}).get("fy2023")
    if ebitda and interest and interest > 0:
        dscr = ebitda / interest
        cam_lines.append(f"  DSCR:                 {dscr:.2f}x")
        cam_lines.append(f"  Interest Coverage:    {dscr:.2f}x")

    w2 = worker_data.get("W2", {})
    emi = w2.get("emi_regularity", {})
    if emi.get("regularity_pct") is not None:
        cam_lines.append(f"  EMI Regularity:       {emi['regularity_pct']}%")

    cam_lines.append("")

    # ── 4. Module Scores ──
    cam_lines.append("-" * 80)
    cam_lines.append("4. SCORE BREAKDOWN BY MODULE")
    cam_lines.append("-" * 80)
    for ms in module_summaries:
        cam_lines.append(
            f"  {ms.module.value:12s}: {ms.score:+4d} points "
            f"(range: {ms.max_negative:+d} to {ms.max_positive:+d}, "
            f"{len(ms.metrics)} metric(s))"
        )
    cam_lines.append(f"  {'BASE':12s}: {BASE_SCORE:+4d}")
    cam_lines.append(f"  {'TOTAL':12s}: {score:4d}/{MAX_SCORE}")
    cam_lines.append("")

    # ── 5. Cross-Verification Summary ──
    cam_lines.append("-" * 80)
    cam_lines.append("5. CROSS-VERIFICATION SUMMARY")
    cam_lines.append("-" * 80)
    cv_entries = [e for e in all_entries if e.module == ScoreModule.COMPOUND
                  and ("Cross" in e.metric_name or "ITC" in e.metric_name or "GSTR" in e.metric_name)]
    if cv_entries:
        for entry in cv_entries:
            cam_lines.append(f"  • {entry.metric_name}: {entry.metric_value}")
            cam_lines.append(f"    Impact: {entry.score_impact:+d} | {entry.reasoning}")
    else:
        cam_lines.append("  No cross-verification flags.")
    cam_lines.append("")

    # ── 6. Risk Flags ──
    cam_lines.append("-" * 80)
    cam_lines.append("6. RISK FLAGS")
    cam_lines.append("-" * 80)
    risk_entries = [e for e in all_entries if e.score_impact < -10]
    if risk_entries:
        for entry in risk_entries:
            cam_lines.append(f"  ⚠ [{entry.module.value}] {entry.metric_name}: {entry.score_impact:+d}")
            cam_lines.append(f"    {entry.reasoning}")
    else:
        cam_lines.append("  No significant risk flags identified.")
    cam_lines.append("")

    # ── 7. Loan Terms Recommendation ──
    cam_lines.append("-" * 80)
    cam_lines.append("7. LOAN TERMS RECOMMENDATION")
    cam_lines.append("-" * 80)
    # Derive terms from score band
    terms = _get_loan_terms(band)
    cam_lines.append(f"  Sanction:  {terms['sanction_pct']}% of requested amount")
    cam_lines.append(f"  Rate:      {terms['rate']}")
    cam_lines.append(f"  Tenure:    {terms['tenure']}")
    cam_lines.append(f"  Review:    {terms['review']}")
    cam_lines.append("")

    # ── 8. Detailed breakdown ──
    cam_lines.append("-" * 80)
    cam_lines.append("8. DETAILED METRIC BREAKDOWN")
    cam_lines.append("-" * 80)
    for entry in all_entries:
        cam_lines.append(f"  [{entry.module.value}] {entry.metric_name}: {entry.metric_value}")
        cam_lines.append(f"    Impact: {entry.score_impact:+d} | Confidence: {entry.confidence:.0%}")
        cam_lines.append(f"    Source: {entry.source_document} (p.{entry.source_page})")
        cam_lines.append(f"    Reasoning: {entry.reasoning}")
        cam_lines.append("")

    # ── 9. Footer ──
    cam_lines.append("=" * 80)
    cam_lines.append("END OF CREDIT APPRAISAL MEMO")
    cam_lines.append("=" * 80)

    cam_text = "\n".join(cam_lines)

    # Save CAM to file
    cam_dir = os.path.join(*CAM_OUTPUT_DIR.split("/"), session_id)
    os.makedirs(cam_dir, exist_ok=True)
    cam_path = os.path.join(cam_dir, "credit_appraisal_memo.txt")

    with open(cam_path, "w", encoding="utf-8") as f:
        f.write(cam_text)

    await emitter.accepted(
        f"CAM generated: {len(cam_lines)} lines, saved to {cam_path}",
        confidence=0.95,
    )

    return cam_path


# _get_loan_terms is imported from config.scoring (aliased as _get_loan_terms)
# Kept for backward compatibility — all consumers already import it from here
