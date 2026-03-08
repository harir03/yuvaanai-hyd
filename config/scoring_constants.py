"""
Intelli-Credit — Scoring Numeric Constants (Leaf Module)

Pure numeric constants with ZERO internal imports.
Used by both backend/models/schemas.py (Pydantic validators)
and config/scoring.py (business rules) to avoid circular imports.
"""

# Score range
MIN_SCORE: int = 0
MAX_SCORE: int = 850
BASE_SCORE: int = 350

# Impact bounds (derived from module limits — max of all max_positive, min of all max_negative)
MAX_POSITIVE_IMPACT: int = 150   # Capacity max_positive
MAX_NEGATIVE_IMPACT: int = -200  # Character max_negative

# Module positive limits
CAPACITY_MAX_POSITIVE: int = 150
CHARACTER_MAX_POSITIVE: int = 120
CAPITAL_MAX_POSITIVE: int = 80
COLLATERAL_MAX_POSITIVE: int = 60
CONDITIONS_MAX_POSITIVE: int = 50
COMPOUND_MAX_POSITIVE: int = 57

# Module negative limits
CAPACITY_MAX_NEGATIVE: int = -100
CHARACTER_MAX_NEGATIVE: int = -200
CAPITAL_MAX_NEGATIVE: int = -80
COLLATERAL_MAX_NEGATIVE: int = -40
CONDITIONS_MAX_NEGATIVE: int = -50
COMPOUND_MAX_NEGATIVE: int = -130

# Hard block score caps
HARD_BLOCK_WILFUL_DEFAULTER: int = 200
HARD_BLOCK_ACTIVE_CRIMINAL: int = 150
HARD_BLOCK_DSCR_BELOW_1: int = 300
HARD_BLOCK_NCLT_ACTIVE: int = 250

# Score band thresholds
BAND_EXCELLENT_THRESHOLD: int = 750
BAND_GOOD_THRESHOLD: int = 650
BAND_FAIR_THRESHOLD: int = 550
BAND_POOR_THRESHOLD: int = 450
BAND_VERY_POOR_THRESHOLD: int = 350

# Loan terms per band
LOAN_EXCELLENT_SANCTION_PCT: str = "100"
LOAN_EXCELLENT_RATE: str = "MCLR + 1.5%"
LOAN_EXCELLENT_TENURE: str = "Up to 7 years"
LOAN_EXCELLENT_REVIEW: str = "Annual"

LOAN_GOOD_SANCTION_PCT: str = "85"
LOAN_GOOD_RATE: str = "MCLR + 2.5%"
LOAN_GOOD_TENURE: str = "Up to 5 years"
LOAN_GOOD_REVIEW: str = "Semi-annual"

LOAN_FAIR_SANCTION_PCT: str = "65"
LOAN_FAIR_RATE: str = "MCLR + 3.5%"
LOAN_FAIR_TENURE: str = "Up to 3 years"
LOAN_FAIR_REVIEW: str = "Quarterly"

LOAN_POOR_SANCTION_PCT: str = "40"
LOAN_POOR_RATE: str = "MCLR + 5.0%"
LOAN_POOR_TENURE: str = "Up to 2 years"
LOAN_POOR_REVIEW: str = "Quarterly"

LOAN_REJECTED_SANCTION_PCT: str = "0"
LOAN_REJECTED_RATE: str = "N/A — Rejected"
LOAN_REJECTED_TENURE: str = "N/A"
LOAN_REJECTED_REVIEW: str = "N/A"

# CAM output directory
CAM_OUTPUT_DIR: str = "data/output"
