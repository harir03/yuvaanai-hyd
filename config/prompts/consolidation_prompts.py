"""
Intelli-Credit — Consolidation Prompt Templates

Prompt templates for Agent 0.5 (The Consolidator).
All prompts live here — never hardcoded in agent code.
"""

# ── Schema Normalization ──
NORMALIZATION_PROMPT = """You are a data normalization specialist for credit appraisal.

**WORKER OUTPUTS (Raw Extractions):**
{worker_outputs}

Normalize all financial figures to a consistent schema:
1. Convert all amounts to ₹ Lakhs (1 Crore = 100 Lakhs)
2. Standardize percentage formats (0.12 → 12%)
3. Map field names to the canonical schema below
4. Flag any extraction confidence below 0.7 for human review

**Canonical Revenue Fields:**
- revenue_fy2023, revenue_fy2022, revenue_fy2021 (₹ Lakhs)
- ebitda_fy2023, ebitda_fy2022, ebitda_fy2021 (₹ Lakhs)
- pat_fy2023, pat_fy2022, pat_fy2021 (₹ Lakhs)

**Canonical Balance Sheet:**
- total_assets, net_worth, total_debt (₹ Lakhs)
- current_assets, current_liabilities

Output normalized data in canonical format."""


# ── Contradiction Detection ──
CONTRADICTION_DETECTION_PROMPT = """You are a financial auditor detecting contradictions across multiple documents.

**SOURCE 1 — Annual Report (self-reported, weight 0.70):**
{annual_report_data}

**SOURCE 2 — ITR (government, weight 1.0):**
{itr_data}

**SOURCE 3 — GST Returns (government, weight 1.0):**
{gst_data}

**SOURCE 4 — Bank Statement (third-party, weight 0.85):**
{bank_data}

**SOURCE WEIGHT HIERARCHY:**
Government (GST, ITR) = 1.0 > Third-party (Bank) = 0.85 > Self-reported (AR) = 0.70

Compare the following critical fields across all available sources:

**Revenue Cross-Verification (CRITICAL):**
- AR revenue vs ITR revenue vs GST turnover vs Bank credits
- Flag if any pair diverges by > 5%
- The government source is assumed correct when conflicts exist

**RPT Concealment Check:**
- Board Minutes RPT approvals count vs AR RPT disclosure count
- If BM count > AR count, flag as concealment

**Net Worth Verification:**
- AR net worth vs ITR balance sheet net worth
- Flag divergence > 3%

**Litigation Cross-Check:**
- AR litigation disclosure vs actual court records (if available from W5)
- Flag any cases found in W5 but not disclosed in AR

For each contradiction found, provide:
- Field name
- Values from each source
- Divergence amount and percentage
- Severity (LOW / MEDIUM / HIGH / CRITICAL)
- Which source to trust (per weight hierarchy)"""


# ── Revenue Cross-Verification ──
REVENUE_CROSS_VERIFICATION_PROMPT = """You are verifying revenue accuracy across 4 independent sources.

**Annual Report Revenue (Weight 0.70):** ₹{ar_revenue} Lakhs (FY{fy})
**ITR Revenue (Weight 1.0):** ₹{itr_revenue} Lakhs (AY{ay})
**GST Turnover (Weight 1.0):** ₹{gst_turnover} Lakhs ({gst_period})
**Bank Statement Credits (Weight 0.85):** ₹{bank_credits} Lakhs ({bank_period})

Perform 4-way cross-verification:

1. **AR vs ITR:** Divergence = {ar_itr_gap}%. Government source (ITR) takes priority.
2. **AR vs GST:** Divergence = {ar_gst_gap}%. Government source (GST) takes priority.
3. **AR vs Bank:** Divergence = {ar_bank_gap}%. Third-party source (Bank) takes priority.
4. **ITR vs GST:** Divergence = {itr_gst_gap}%. Both government — flag if >3%.
5. **ITR vs Bank:** Divergence = {itr_bank_gap}%.
6. **GST vs Bank:** Divergence = {gst_bank_gap}%.

Determine:
- The most reliable revenue figure (weighted average with source trust weights)
- Whether revenue inflation exists (AR > government sources consistently)
- Confidence score for the final revenue figure (0.0 - 1.0)
- Whether a ticket should be raised for human review"""


# ── Completeness Check ──
COMPLETENESS_CHECK_PROMPT = """You are checking data completeness after document extraction.

**WORKER STATUS:**
{worker_status}

**REQUIRED DOCUMENTS:** Annual Report (W1), Bank Statement (W2), GST Returns (W3), ITR (W4)
**OPTIONAL DOCUMENTS:** Legal Notice (W5), Board Minutes (W6), Shareholding (W7), Rating Report (W8)

**EXTRACTED FIELDS SUMMARY:**
{extracted_fields}

Verify:
1. All 4 mandatory documents are present and extraction succeeded
2. Critical fields exist for scoring:
   - Revenue (at least 2 years)
   - EBITDA or operating profit
   - Total debt
   - Net worth
   - Trade receivables / payables
3. If mandatory fields are missing, can they be derived from other sources?
4. What is the overall data completeness percentage?
5. What scoring modules will have reduced confidence due to missing data?

Output:
- missing_mandatory: list of missing required documents
- missing_fields: list of critical fields not available from any source
- derivable_fields: fields that can be computed from available data
- completeness_score: percentage (0-100)
- affected_modules: which 5C modules will have reduced accuracy"""
