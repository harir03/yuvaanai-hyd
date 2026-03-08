"""
Intelli-Credit — CAM (Credit Appraisal Memo) Prompt Templates

Prompt templates for the CAM Writer component of Agent 3.
All prompts live here — never hardcoded in agent code.
"""

# ── Executive Summary ──
CAM_EXECUTIVE_SUMMARY_PROMPT = """You are writing the Executive Summary for a Credit Appraisal Memo (CAM) in Indian banking format.

**COMPANY:** {company_name}
**LOAN:** ₹{loan_amount} — {loan_type}
**SCORE:** {score}/850 — {score_band}
**RECOMMENDATION:** {recommendation}

**KEY METRICS:**
{key_metrics}

**CRITICAL FINDINGS:**
{critical_findings}

Write a concise Executive Summary (400-600 words) following Indian banking CAM conventions:

1. **Application Summary** (2-3 sentences)
   - Company name, sector, promoter, loan request details
   
2. **Financial Snapshot** (4-5 bullet points)
   - Revenue trend (3 years)
   - DSCR and adequacy assessment
   - D/E ratio and leverage commentary
   - Working capital cycle adequacy
   - Cash flow sufficiency for proposed EMI

3. **Key Risks** (3-5 bullet points, severity-ordered)
   - Each risk with specific evidence
   - Quantified impact where possible

4. **Key Strengths** (3-4 bullet points)
   - Genuine positives with evidence

5. **Scoring Summary**
   - Final score and band
   - Top 3 contributing factors (positive)
   - Top 3 detracting factors (negative)
   - Hard blocks if any

6. **Recommendation**
   - Approve/Conditional/Reject
   - Loan amount (may be less than requested)
   - Suggested interest rate
   - Key conditions/covenants if conditional

Tone: professional, factual, evidence-based. No speculation.
Use ₹ with Lakhs/Crores notation. Follow RBI/CIBIL conventions."""


# ── Detailed Financial Analysis ──
CAM_FINANCIAL_ANALYSIS_PROMPT = """You are writing the Financial Analysis section of a Credit Appraisal Memo.

**FINANCIAL DATA (Verified):**
{financial_data}

**BENCHMARKS:**
{sector_benchmarks}

**CROSS-VERIFICATION:**
{cross_verification}

Write the Financial Analysis section covering:

**1. Revenue & Profitability Analysis**
- 3-year revenue trend with CAGR
- EBITDA and PAT margins trend
- Revenue quality (cross-verified figure vs self-reported)
- Revenue concentration risk (if top customer data available)

**2. Debt Servicing Capacity**
- DSCR computation with full formula
- DSCR trend and projection
- Interest coverage ratio
- Cash flow adequacy for proposed EMI

**3. Balance Sheet Analysis**
- Net worth growth
- Leverage ratios (D/E, Total Debt/EBITDA)
- Working capital position (current ratio, quick ratio)
- Working capital cycle (days)

**4. Cash Flow Analysis**
- Operating cash flow trend
- Free cash flow
- Bank statement inflow vs AR revenue reconciliation
- Cash conversion efficiency

Every metric must include:
- Actual value
- Sector benchmark
- 3-year trend direction (↑ Improving / → Stable / ↓ Declining)
- Source document reference"""


# ── Risk Assessment Section ──
CAM_RISK_ASSESSMENT_PROMPT = """You are writing the Risk Assessment section of a Credit Appraisal Memo.

**ALL FINDINGS (Severity-ordered):**
{findings}

**GRAPH INTELLIGENCE:**
{graph_findings}

**ML MODEL FLAGS:**
{ml_flags}

**COMPLIANCE:**
{compliance_flags}

Write the Risk Assessment section:

**1. Credit Risk**
- Default probability assessment
- DSCR adequacy and trend
- Revenue predictability

**2. Governance Risk**
- RPT disclosure accuracy
- Auditor qualifications
- Management stability (CFO/Director changes)
- Board governance quality

**3. Regulatory Risk**
- SEBI/RBI orders or investigations
- Tax compliance (GST filing regularity, ITR compliance)
- Environmental/industry-specific compliance

**4. Concentration Risk**
- Customer concentration (top 5 customers as % of revenue)
- Supplier concentration
- Geographic concentration
- Sector cyclicality

**5. Fraud Risk Indicators**
- Circular trading signals (graph analysis)
- Revenue inflation indicators (cross-verification gaps)
- RPT concealment attempts
- ML anomaly flags

**6. External Risk**
- Sector outlook
- Regulatory changes forthcoming
- Market competition intensity
- Input cost volatility

Each risk: description → evidence → severity → mitigation (if any) → impact on score."""


# ── Terms & Conditions ──
CAM_TERMS_PROMPT = """You are generating recommended loan terms based on the credit assessment.

**SCORE:** {score}/850 — {score_band}
**REQUESTED:** ₹{requested_amount} — {loan_type} — {tenor} months
**KEY RISKS:** {key_risks}

**SCORE BAND PRICING:**
750-850 (Excellent): Full amount, MCLR + 1.5%
650-749 (Good):      85% of amount, MCLR + 2.5%
550-649 (Fair):      65% of amount, MCLR + 3.5%
450-549 (Poor):      40% of amount, MCLR + 5.0%
350-449 (Very Poor): Reject
<350 (Default Risk): Permanent reject

Generate loan terms:

**1. Loan Amount:** (Apply band-based percentage to requested amount)
**2. Interest Rate:** (Apply band-based spread over MCLR)
**3. Tenor:** (May be shorter than requested if risk warrants)
**4. Collateral Requirement:** (Based on collateral module score)
**5. Key Covenants:**
   - Financial covenants (minimum DSCR, maximum D/E, etc.)
   - Reporting covenants (quarterly financials, annual audit)
   - Negative covenants (no additional borrowing without consent, no dividend if DSCR < 1.5x)
**6. Special Conditions:**
   - Based on specific risks identified (e.g., RPT monitoring)
   - Trigger events for review (rating downgrade, promoter pledge increase)

Format as a standard Indian banking sanction letter."""


# ── CAM Full Document Assembly ──
CAM_ASSEMBLY_PROMPT = """You are assembling the complete Credit Appraisal Memo document.

**SECTIONS COMPLETED:**
1. Executive Summary: {executive_summary}
2. Financial Analysis: {financial_analysis}
3. Risk Assessment: {risk_assessment}
4. Score Breakdown: {score_breakdown}
5. Terms & Conditions: {terms}

Assemble into a complete CAM with:
- Cover page (Company, Date, Session ID, Officer)
- Table of Contents
- Section numbering (1.0, 1.1, 1.2, etc.)
- Cross-references between sections
- Appendices:
  A. Score Breakdown Table (all entries)
  B. Cross-Verification Matrix
  C. Document List & Dates
  D. Disclaimer

Ensure:
- Every factual claim has a source citation
- Financial figures are consistently in ₹ Lakhs or ₹ Crores (don't mix)
- Score band and recommendation are consistent
- Document is 15-25 pages (Indian banking standard)"""
