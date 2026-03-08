"""
Intelli-Credit — Scoring Configuration (Single Source of Truth)

ALL scoring business rules live here. Every module that needs scoring constants
imports from this file. To adjust scoring policy, change ONLY this file
(and config/scoring_constants.py for numeric bounds).

Covers:
  - Score range and base score
  - Module limits (5 Cs + Compound)
  - Score band thresholds and outcomes
  - Hard block rules and score caps
  - Loan terms per score band
  - CAM output directory
"""

from backend.models.schemas import (
    AssessmentOutcome,
    ScoreBand,
    ScoreModule,
)
from config.scoring_constants import (
    MIN_SCORE,
    MAX_SCORE,
    BASE_SCORE,
    MAX_POSITIVE_IMPACT,
    MAX_NEGATIVE_IMPACT,
    CAPACITY_MAX_POSITIVE, CAPACITY_MAX_NEGATIVE,
    CHARACTER_MAX_POSITIVE, CHARACTER_MAX_NEGATIVE,
    CAPITAL_MAX_POSITIVE, CAPITAL_MAX_NEGATIVE,
    COLLATERAL_MAX_POSITIVE, COLLATERAL_MAX_NEGATIVE,
    CONDITIONS_MAX_POSITIVE, CONDITIONS_MAX_NEGATIVE,
    COMPOUND_MAX_POSITIVE, COMPOUND_MAX_NEGATIVE,
    HARD_BLOCK_WILFUL_DEFAULTER, HARD_BLOCK_ACTIVE_CRIMINAL,
    HARD_BLOCK_DSCR_BELOW_1, HARD_BLOCK_NCLT_ACTIVE,
    BAND_EXCELLENT_THRESHOLD, BAND_GOOD_THRESHOLD,
    BAND_FAIR_THRESHOLD, BAND_POOR_THRESHOLD,
    BAND_VERY_POOR_THRESHOLD,
    LOAN_EXCELLENT_SANCTION_PCT, LOAN_EXCELLENT_RATE,
    LOAN_EXCELLENT_TENURE, LOAN_EXCELLENT_REVIEW,
    LOAN_GOOD_SANCTION_PCT, LOAN_GOOD_RATE,
    LOAN_GOOD_TENURE, LOAN_GOOD_REVIEW,
    LOAN_FAIR_SANCTION_PCT, LOAN_FAIR_RATE,
    LOAN_FAIR_TENURE, LOAN_FAIR_REVIEW,
    LOAN_POOR_SANCTION_PCT, LOAN_POOR_RATE,
    LOAN_POOR_TENURE, LOAN_POOR_REVIEW,
    LOAN_REJECTED_SANCTION_PCT, LOAN_REJECTED_RATE,
    LOAN_REJECTED_TENURE, LOAN_REJECTED_REVIEW,
    CAM_OUTPUT_DIR,
)

# Re-export numeric constants for convenience
__all__ = [
    "MIN_SCORE", "MAX_SCORE", "BASE_SCORE",
    "MODULE_LIMITS", "SCORE_BANDS", "HARD_BLOCK_RULES",
    "LOAN_TERMS", "DEFAULT_MISSING_BAND", "CAM_OUTPUT_DIR",
    "get_score_band", "get_loan_terms",
    "get_module_max_impact", "get_module_min_impact",
]

# ── Module Score Limits (per 5 Cs + Compound framework) ──
MODULE_LIMITS: dict = {
    ScoreModule.CAPACITY:   {"max_positive": CAPACITY_MAX_POSITIVE,   "max_negative": CAPACITY_MAX_NEGATIVE},
    ScoreModule.CHARACTER:  {"max_positive": CHARACTER_MAX_POSITIVE,  "max_negative": CHARACTER_MAX_NEGATIVE},
    ScoreModule.CAPITAL:    {"max_positive": CAPITAL_MAX_POSITIVE,    "max_negative": CAPITAL_MAX_NEGATIVE},
    ScoreModule.COLLATERAL: {"max_positive": COLLATERAL_MAX_POSITIVE, "max_negative": COLLATERAL_MAX_NEGATIVE},
    ScoreModule.CONDITIONS: {"max_positive": CONDITIONS_MAX_POSITIVE, "max_negative": CONDITIONS_MAX_NEGATIVE},
    ScoreModule.COMPOUND:   {"max_positive": COMPOUND_MAX_POSITIVE,   "max_negative": COMPOUND_MAX_NEGATIVE},
}

# ── Score Bands (threshold, band, outcome, description) ──
# Evaluated top-down: first match wins
SCORE_BANDS: list = [
    (BAND_EXCELLENT_THRESHOLD,  ScoreBand.EXCELLENT,    AssessmentOutcome.APPROVED,    "Full amount, MCLR+1.5%"),
    (BAND_GOOD_THRESHOLD,       ScoreBand.GOOD,         AssessmentOutcome.APPROVED,    "85% amount, MCLR+2.5%"),
    (BAND_FAIR_THRESHOLD,       ScoreBand.FAIR,         AssessmentOutcome.CONDITIONAL, "65% amount, MCLR+3.5%"),
    (BAND_POOR_THRESHOLD,       ScoreBand.POOR,         AssessmentOutcome.CONDITIONAL, "40% amount, MCLR+5.0%"),
    (BAND_VERY_POOR_THRESHOLD,  ScoreBand.VERY_POOR,    AssessmentOutcome.REJECTED,    "Reject"),
    (0,                         ScoreBand.DEFAULT_RISK,  AssessmentOutcome.REJECTED,    "Permanent reject"),
]

# ── Hard Block Rules (trigger → score cap) ──
HARD_BLOCK_RULES: dict = {
    "wilful_defaulter":     HARD_BLOCK_WILFUL_DEFAULTER,
    "active_criminal_case": HARD_BLOCK_ACTIVE_CRIMINAL,
    "dscr_below_1":         HARD_BLOCK_DSCR_BELOW_1,
    "nclt_active":          HARD_BLOCK_NCLT_ACTIVE,
}

# ── Loan Terms Per Score Band ──
LOAN_TERMS: dict = {
    ScoreBand.EXCELLENT:    {"sanction_pct": LOAN_EXCELLENT_SANCTION_PCT, "rate": LOAN_EXCELLENT_RATE, "tenure": LOAN_EXCELLENT_TENURE, "review": LOAN_EXCELLENT_REVIEW},
    ScoreBand.GOOD:         {"sanction_pct": LOAN_GOOD_SANCTION_PCT,     "rate": LOAN_GOOD_RATE,      "tenure": LOAN_GOOD_TENURE,      "review": LOAN_GOOD_REVIEW},
    ScoreBand.FAIR:         {"sanction_pct": LOAN_FAIR_SANCTION_PCT,     "rate": LOAN_FAIR_RATE,      "tenure": LOAN_FAIR_TENURE,      "review": LOAN_FAIR_REVIEW},
    ScoreBand.POOR:         {"sanction_pct": LOAN_POOR_SANCTION_PCT,     "rate": LOAN_POOR_RATE,      "tenure": LOAN_POOR_TENURE,      "review": LOAN_POOR_REVIEW},
    ScoreBand.VERY_POOR:    {"sanction_pct": LOAN_REJECTED_SANCTION_PCT, "rate": LOAN_REJECTED_RATE,  "tenure": LOAN_REJECTED_TENURE,  "review": LOAN_REJECTED_REVIEW},
    ScoreBand.DEFAULT_RISK: {"sanction_pct": LOAN_REJECTED_SANCTION_PCT, "rate": LOAN_REJECTED_RATE,  "tenure": LOAN_REJECTED_TENURE,  "review": LOAN_REJECTED_REVIEW},
}

# ── Default Score Band (when score is missing in history/fallback) ──
DEFAULT_MISSING_BAND: ScoreBand = ScoreBand.DEFAULT_RISK

# ── CAM Output Directory ──
CAM_OUTPUT_DIR: str = "data/output"


# ── Derived helpers ──

def get_score_band(score: int):
    """Return (ScoreBand, AssessmentOutcome, recommendation) for a given score."""
    for threshold, band, outcome, rec in SCORE_BANDS:
        if score >= threshold:
            return band, outcome, rec
    return ScoreBand.DEFAULT_RISK, AssessmentOutcome.REJECTED, "Permanent reject"


def get_loan_terms(band: ScoreBand) -> dict:
    """Derive loan terms from score band."""
    return LOAN_TERMS.get(
        band,
        {"sanction_pct": "0", "rate": "N/A — Rejected", "tenure": "N/A", "review": "N/A"},
    )


def get_module_max_impact() -> int:
    """Max positive score impact any single metric can have (for Pydantic validation)."""
    return max(lim["max_positive"] for lim in MODULE_LIMITS.values())


def get_module_min_impact() -> int:
    """Max negative score impact any single metric can have (for Pydantic validation)."""
    return min(lim["max_negative"] for lim in MODULE_LIMITS.values())
