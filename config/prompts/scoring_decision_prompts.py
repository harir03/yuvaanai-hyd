"""
Intelli-Credit — Scoring Decision Prompt Templates

Prompt templates for hard block evaluation and scoring decisions.
All prompts live here — never hardcoded in agent code.
"""

# ── Hard Block Evaluation ──
HARD_BLOCK_EVALUATION_PROMPT = """You are evaluating whether any hard block triggers should activate.

**EVIDENCE:**
{evidence}

**HARD BLOCK RULES (Non-negotiable):**
1. Wilful Defaulter (RBI list) → Score capped at 200
2. Active Criminal Case (against promoter) → Score capped at 150
3. DSCR < 1.0x → Score capped at 300
4. NCLT Active Proceedings → Score capped at 250

For each rule, evaluate:

**Wilful Defaulter:**
- Is the company on the RBI wilful defaulter list?
- Is any promoter/director on the list (personal or through another entity)?
- Evidence: {rbi_data}

**Active Criminal Case:**
- Are there pending criminal cases against promoters?
- Include cases from Annual Report disclosure AND NJDG/court research
- Only criminal (not civil/consumer) and only active (not disposed/settled)
- Evidence: {litigation_data}

**DSCR Threshold:**
- Current DSCR = {dscr_value}
- Is DSCR < 1.0x based on verified (government-source) financials?
- Use ITR figures if available, then AR figures
- Evidence: {financial_data}

**NCLT Proceedings:**
- Any active NCLT proceedings against the company?
- Include both insolvency applications AND company law matters
- Only active (not resolved/withdrawn)
- Evidence: {nclt_data}

For each triggered block:
- State the specific evidence (document, page, excerpt)
- Confirm the score cap
- Note that this overrides ALL module scores

If multiple blocks trigger, the LOWEST cap applies."""


# ── Score Band Decision ──
SCORE_BAND_DECISION_PROMPT = """You are making the final scoring decision based on all module scores.

**MODULE SCORES:**
{module_scores}

**TOTAL IMPACT:** {total_impact} points
**BASE SCORE:** 350
**RAW SCORE:** {raw_score}/850
**HARD BLOCK CAP:** {hard_block_cap} (if applicable)
**FINAL SCORE:** {final_score}/850

**SCORE BANDS:**
750-850: Excellent → Full amount, MCLR+1.5%
650-749: Good → 85% amount, MCLR+2.5%
550-649: Fair → 65% amount, MCLR+3.5%
450-549: Poor → 40% amount, MCLR+5.0%
350-449: Very Poor → Reject
<350: Default Risk → Permanent reject

Determine:
1. Score band assignment
2. Recommendation (APPROVED / CONDITIONAL / REJECTED)
3. Loan amount percentage
4. Interest rate spread

**For scores 550-650 (borderline zone):**
- Recommend human review
- Highlight the 3 factors that could tip the decision
- Suggest what additional evidence would clarify

**For scores with hard block caps:**
- Explain that the uncapped score was {raw_score} but is capped to {final_score}
- State the specific hard block trigger
- This cannot be overridden by the credit officer without senior manager approval"""


# ── Module Scoring Guidance — Capacity ──
CAPACITY_SCORING_PROMPT = """You are scoring the CAPACITY module (max +150, min -100).

**VERIFIED FINANCIALS:**
{financials}

**SECTOR BENCHMARKS:**
{benchmarks}

Score these metrics:

**DSCR (+40 to -50):**
- > 2.0x: +40 (Comfortable margin)
- 1.5x-2.0x: +25 (Adequate)
- 1.2x-1.5x: +10 (Acceptable)
- 1.0x-1.2x: -15 (Tight cover)
- < 1.0x: -50 (Hard block territory, separate rule applies)

**Revenue Growth (+35 to -20):**
- > 15% CAGR: +35 (Strong growth)
- 8-15% CAGR: +20 (Steady growth)
- 0-8% CAGR: +5 (Modest growth)
- Negative growth: -20 (Declining business)

**Working Capital Cycle (+25 to -15):**
- < 60 days: +25 (Efficient cycle)
- 60-90 days: +10 (Normal)
- 90-120 days: -5 (Stressed)
- > 120 days: -15 (Working capital strain)

**Cash Flow Quality (+25 to -10):**
- Positive OCF with growing trend: +25
- Positive OCF but declining: +10
- Negative OCF: -10

**EMI Regularity (+25 to -5):**
- No bounces, regular payments: +25
- Occasional delays (<3): +10
- Frequent bounces (>3): -5

For each metric: value → benchmark comparison → score impact → reasoning."""


# ── Module Scoring Guidance — Character ──
CHARACTER_SCORING_PROMPT = """You are scoring the CHARACTER module (max +120, min -200).

This module has the HIGHEST negative potential because character risk can override financial strength.

**GOVERNANCE DATA:**
{governance_data}

**PROMOTER DATA:**
{promoter_data}

**COMPLIANCE DATA:**
{compliance_data}

Score these metrics:

**Credit History (+30 to -60):**
- Clean track record, stable/improving rating: +30
- Minor issues, resolved: +10
- Recent downgrade: -30
- Default history: -60

**RPT Disclosure (+25 to -50):**
- Full, accurate RPT disclosure: +25
- Minor gaps (rounding): +5
- Concealment detected (BM vs AR mismatch): -50

**Regulatory Compliance (+20 to -40):**
- Clean regulatory record: +20
- Minor compliance issues (resolved): +5
- SEBI/RBI penalties: -40

**Management Stability (+20 to -25):**
- Stable management, good attendance: +20
- Recent CFO change (note reason): -10
- Multiple director resignations: -25

**Pledge & Commitment (+25 to -25):**
- Low pledge (<20%), no recent increase: +25
- Moderate pledge (20-40%): +5
- High pledge or recent spike: -25

NOTE: Wilful defaulter detected → Character module automatically = -200 (hard block)."""


# ── Module Scoring Guidance — Compound ──
COMPOUND_SCORING_PROMPT = """You are scoring the COMPOUND module (max +57, min -130).

This module captures cross-cutting insights from graph reasoning and ML models.

**GRAPH REASONING OUTPUT:**
{graph_reasoning}

**ML MODEL FLAGS:**
{ml_flags}

**CROSS-VERIFICATION:**
{cross_verification}

**TEMPORAL ANALYSIS:**
{temporal_analysis}

Score these signals:

**Revenue Cross-Verification (+20 to -40):**
- All 4 sources match (<3% divergence): +20
- Minor divergence (3-10%): +5
- Significant divergence (10-20%): -20
- Major divergence (>20%): -40

**Cascade Risk (0 to -30):**
- No cascade risk identified: 0
- Low cascade risk (<10% revenue at risk): -10
- Medium (10-25% revenue at risk): -20
- High (>25% revenue at risk, DSCR impact): -30

**Graph Anomaly (0 to -40):**
- No anomalies: 0
- Undisclosed relationships: -15
- Circular trading detected: -40

**Temporal Deterioration (+7 to -10):**
- All metrics improving: +7
- Stable: 0
- Declining trends: -10

**GST ITC Mismatch (+10 to -10):**
- 3B matches 2A: +10
- Minor gap (<5%): 0
- Significant gap (>10%): -10

**Positive Signals (+20):**
- Government support (PLI, subsidies): up to +10
- Strong order book (>12 months visibility): up to +10"""
