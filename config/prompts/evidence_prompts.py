"""
Intelli-Credit — Evidence Package Prompt Templates

Prompt templates for the Evidence Package Builder.
All prompts live here — never hardcoded in agent code.
"""

# ── Evidence Package Assembly ──
EVIDENCE_PACKAGE_PROMPT = """You are assembling the Evidence Package — the ONLY input that Agent 3 (Scorer + CAM Writer) will see.

**NORMALIZED DATA:**
{normalized_data}

**CROSS-VERIFICATION RESULTS:**
{cross_verification}

**RESEARCH FINDINGS (Verified, Tier 1-3 only):**
{research_findings}

**GRAPH REASONING CONCLUSIONS:**
{reasoning_conclusions}

**ML MODEL OUTPUTS:**
{ml_outputs}

**RESOLVED TICKETS:**
{resolved_tickets}

**PENDING TICKETS:**
{pending_tickets}

Build the Evidence Package with these mandatory sections:

**1. Financial Summary (Verified Figures Only):**
- Use government-source figures where available (ITR/GST weight 1.0)
- Fall back to bank statement (weight 0.85) then AR (weight 0.70)
- State the source and confidence for each figure
- Include 3-year trends where available

**2. Risk Findings (Ranked by Severity):**
For each finding, include:
- Finding title and description
- Severity (LOW / MEDIUM / HIGH / CRITICAL)
- Source document(s), page(s), and excerpts
- Cross-verification status (confirmed by N sources)
- ML model flag (if applicable)

**3. Cross-Verification Summary:**
- Revenue 4-way check: match/mismatch with amounts
- RPT concealment: BM count vs AR count
- Litigation disclosure: AR vs NJDG
- Net worth: AR vs ITR

**4. Graph Intelligence:**
- Cascade risk chains and DSCR impact
- Hidden relationships detected
- Circular trading patterns (if any)
- Community clusters

**5. Compliance & External Intelligence:**
- Regulatory flags (SEBI, RBI orders)
- Wilful defaulter status
- Media sentiment summary
- Sector outlook

**6. Ticket Resolutions:**
- Each resolved ticket: original conflict, resolution, impact on scoring

CRITICAL: Agent 3 sees ONLY this Evidence Package.
Everything relevant must be included. Nothing excluded should be needed."""


# ── Ticket Generation ──
TICKET_GENERATION_PROMPT = """You are determining whether to raise a ticket for human review.

**FINDING:**
{finding}

**CONTRADICTION DETAILS:**
{contradiction}

**SEVERITY THRESHOLDS:**
- LOW: Pipeline continues, ticket resolved async. Minor discrepancies (<5%)
- HIGH: Pipeline pauses at Agent 3. Major discrepancies (5-20%) or governance concerns
- CRITICAL: Pipeline stops. Fraud indicators, regulatory blocks, or data integrity failures

Determine:
1. Should a ticket be raised? (YES/NO)
2. If YES, what severity? (LOW/HIGH/CRITICAL)
3. What is the specific question for the credit officer?
4. What AI recommendation should accompany the ticket?
5. What evidence should be attached?

**Ticket Triggers (always raise):**
- Revenue divergence > 10% between any two sources
- RPT concealment (BM count ≠ AR count)
- GSTR-2A vs 3B ITC gap > 10%
- ML anomaly flag with confidence > 0.8
- Graph circular trading detection
- Undisclosed litigation (found in NJDG but not in AR)
- Wilful defaulter association (director-level)

**Do NOT raise tickets for:**
- Minor rounding differences (<2%)
- Expected sector-specific variations
- Already-explained items (auditor qualification with management response)"""


# ── Evidence Source Tracing ──
SOURCE_TRACING_PROMPT = """You are ensuring complete source tracing for every claim in the Evidence Package.

**EVIDENCE CLAIMS:**
{evidence_claims}

For each claim, verify that the following chain is complete:

1. **Source Document** (e.g., "Annual Report FY2023")
2. **Page Number** (e.g., "p.87")
3. **Exact Excerpt** (verbatim text, not paraphrased)
4. **Cross-Verification** (which other sources confirm/deny this)
5. **Confidence Score** (based on source tier and corroboration)

Flag any claim that:
- Has no page number → assign "unverified" status
- Has no excerpt → downgrade confidence by 0.2
- Is only from a self-reported source → flag for cross-check
- Contradicts a government source → mark as "disputed"

A credit officer must be able to trace any claim back to the original document page."""
