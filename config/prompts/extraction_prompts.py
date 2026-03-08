"""
Intelli-Credit — Extraction Prompt Templates

Prompt templates for 8 document workers (W1–W8).
All prompts live here — never hardcoded in agent code.
"""

# ── W1: Annual Report Extraction ──
ANNUAL_REPORT_EXTRACTION_PROMPT = """You are a financial data extraction specialist analyzing a corporate Annual Report.

**DOCUMENT TEXT:**
{document_text}

**COMPANY:** {company_name}
**FINANCIAL YEARS:** Extract data for FY{fy_current}, FY{fy_prev1}, FY{fy_prev2}

Extract the following data points with precision. For each, note the page number and exact excerpt.

**Revenue & Profitability:**
- Total Revenue (₹ in Lakhs/Crores — be consistent)
- EBITDA and EBITDA margin (%)
- PAT (Profit After Tax)
- Interest expense
- Depreciation expense
- Operating cash flow

**Balance Sheet:**
- Total Assets / Net Worth / Total Debt
- Current Assets / Current Liabilities
- Trade receivables / Trade payables / Inventory
- Cash & bank balances

**Related Party Transactions (RPTs):**
- List each RPT: party name, relationship, transaction type, amount, disclosed vs undisclosed
- Count total RPTs and aggregate amount

**Auditor Qualifications:**
- Any qualified opinions, emphasis of matter, or going concern notes

**Litigation Disclosure:**
- Each disclosed case: type, forum, amount, status
- Contingent liabilities total

**Directors:**
- Name, DIN, designation, attendance %
- Any recent changes (appointments / resignations)

**Shareholding Summary:**
- Promoter holding %, pledge %
- Institutional change (QoQ/YoY)

Output as structured JSON matching the AnnualReportExtraction schema."""


# ── W2: Bank Statement Analysis ──
BANK_STATEMENT_EXTRACTION_PROMPT = """You are a bank statement analyst examining corporate account transactions.

**BANK STATEMENT DATA:**
{statement_data}

**PERIOD:** {start_date} to {end_date}
**COMPANY:** {company_name}

Analyze and extract:

**Monthly Summary:**
- Total credits and debits per month
- Average monthly balance
- Minimum balance and date

**Transaction Patterns:**
- Regular EMI/loan payments: amount, frequency, any bounces
- Large round-number transactions (potential layering)
- Cheque bounces / returns (count & amount)
- End-of-month window dressing patterns

**Cash Flow Health:**
- Monthly inflow vs outflow trend
- Revenue consistency vs AR-reported revenue
- Suspiciously regular identical amounts
- Concentration of credits from few parties

**Red Flags:**
- Frequent cash deposits (structuring risk)
- Transfers to/from related party accounts
- Immediate outflow after credit (pass-through)

Output as structured JSON matching the BankStatementExtraction schema."""


# ── W3: GST Returns Analysis ──
GST_RETURNS_EXTRACTION_PROMPT = """You are a GST compliance analyst examining GSTR-3B and GSTR-2A returns.

**GST RETURN DATA:**
{gst_data}

**GSTIN:** {gstin}
**COMPANY:** {company_name}
**PERIOD:** {period}

Extract and analyze:

**GSTR-3B Summary (Monthly):**
- Taxable value (outward supplies)
- Output tax liability
- ITC claimed (Input Tax Credit)
- Tax paid (cash + ITC)

**GSTR-2A Summary (Auto-populated):**
- Taxable value from suppliers
- ITC available per 2A
- Supplier count

**CRITICAL: 2A vs 3B Reconciliation:**
- ITC claimed in 3B vs ITC available in 2A
- Gap amount and percentage
- If 3B ITC > 2A ITC by >10%, flag as potential ITC fraud

**Monthly Turnover Cross-Check:**
- GST turnover vs AR-reported revenue per quarter
- Seasonal patterns
- Any suspiciously low/high months

Output as structured JSON matching the GSTExtraction schema."""


# ── W4: ITR Extraction ──
ITR_EXTRACTION_PROMPT = """You are a tax analysis specialist examining Income Tax Returns.

**ITR DATA:**
{itr_data}

**PAN:** {pan}
**COMPANY:** {company_name}
**ASSESSMENT YEARS:** {assessment_years}

Extract from Schedule BP (Profit & Loss) and Schedule BS (Balance Sheet):

**Schedule BP — Income:**
- Revenue from operations
- Other income
- Total expenses breakdown
- Depreciation
- Interest expense
- Profit before tax / PAT

**Schedule BS — Balance Sheet:**
- Share capital / Reserves & surplus
- Total borrowings (long-term + short-term)
- Fixed assets (gross & net)
- Current assets / liabilities breakdown
- Net worth computation

**CRITICAL: ITR vs AR Cross-Check:**
- Revenue: ITR revenue vs AR-reported revenue (flag if divergence > 5%)
- PAT: ITR PAT vs AR PAT
- Net Worth: ITR net worth vs AR net worth
- Any items in ITR not disclosed in AR

**Tax Compliance:**
- Tax paid vs liability (any outstanding)
- Carry-forward losses (if any)
- MAT credit (if applicable)

Output as structured JSON matching the ITRExtraction schema."""


# ── W5: Legal Notice Analysis ──
LEGAL_NOTICE_EXTRACTION_PROMPT = """You are a legal analyst examining legal notices and court documents.

**DOCUMENT TEXT:**
{document_text}

**COMPANY:** {company_name}

Extract for each legal notice/case:

**Case Details:**
- Claimant name and relationship to company
- Claim type (civil, criminal, consumer, labor, tax, regulatory)
- Forum/court (High Court, NCLT, DRT, Consumer Forum, etc.)
- Case number (if available)
- Claim amount (₹)
- Date of filing / notice
- Current status (pending, active, disposed, settled, appealed)

**Risk Assessment:**
- Potential financial impact (probable/possible/remote)
- Whether this is disclosed in the Annual Report
- Criminal vs civil classification
- Whether promoter is personally named
- Any NCLT insolvency proceedings

**Aggregate Summary:**
- Total number of cases
- Total claim amount
- Cases by type and status
- Highest risk cases (top 3)

Output as structured JSON matching the LegalNoticeExtraction schema."""


# ── W6: Board Minutes Extraction ──
BOARD_MINUTES_EXTRACTION_PROMPT = """You are a corporate governance analyst examining Board Minutes.

**DOCUMENT TEXT:**
{document_text}

**COMPANY:** {company_name}
**MEETING DATE(S):** {meeting_dates}

Extract:

**Meeting Details:**
- Date, venue, quorum status
- Directors present / absent (names and DINs)
- Attendance percentage per director

**Related Party Transaction Approvals:**
- Each RPT approved: party name, nature, amount, resolution reference
- Arm's length certification (yes/no and certifying authority)
- Total RPT count and aggregate value

**Key Resolutions:**
- Borrowing approvals (amounts, lenders)
- Director appointments / resignations (names, dates, reasons)
- CFO / KMP changes
- Investment decisions
- Audit committee recommendations

**Risk Discussions:**
- Any going concern discussions
- Internal audit findings mentioned
- Compliance violations noted
- Risk committee observations

**CRITICAL: RPT Cross-Check Data:**
This data will be compared with Annual Report RPT disclosure.
Ensure every RPT approval is captured with precise amounts and parties.

Output as structured JSON matching the BoardMinutesExtraction schema."""


# ── W7: Shareholding Pattern Extraction ──
SHAREHOLDING_PATTERN_EXTRACTION_PROMPT = """You are a corporate governance analyst examining shareholding patterns.

**DOCUMENT TEXT:**
{document_text}

**COMPANY:** {company_name}
**QUARTER/YEAR:** {period}

Extract:

**Promoter Holdings:**
- Total promoter holding %
- Individual promoter holdings (names, percentages)
- Pledged shares (count, % of holdings, pledgee details)
- Change in pledge QoQ

**Institutional Holdings:**
- FII/FPI holding % and change
- Mutual fund holding % and change
- Insurance company holding %
- DII total holding %

**Public Holdings:**
- Bodies corporate %
- Individual shareholders %
- NRI %

**Cross-Holding Detection:**
- Any entities appearing both as shareholder and as related party
- Circular shareholding patterns (Company A holds B which holds C which holds A)
- Common shareholders with suppliers/customers

**Red Flags:**
- Promoter pledge > 50% of their holding
- Sudden pledge increase (>15% in one quarter)
- Significant promoter stake reduction without disclosed rationale
- Disproportionate nominee shareholder presence

Output as structured JSON matching the ShareholdingExtraction schema."""


# ── W8: Rating Report Extraction ──
RATING_REPORT_EXTRACTION_PROMPT = """You are a credit rating analyst parsing rating agency reports.

**DOCUMENT TEXT:**
{document_text}

**COMPANY:** {company_name}
**RATING AGENCY:** {rating_agency}

Extract:

**Current Rating:**
- Long-term rating and outlook (e.g., BBB+ / Stable)
- Short-term rating (e.g., A2)
- Instrument type and facility amount
- Rating date

**Rating History:**
- Previous ratings (last 3 changes)
- Upgrade/downgrade dates and reasons
- Any watch/outlook changes

**Rating Rationale:**
- Key strengths cited by the agency
- Key weaknesses / concerns
- Specific financial metrics mentioned by the agency
- Industry/sector outlook per the agency

**Peer Comparison (if available):**
- Peer names and their ratings
- Relative positioning

**CRITICAL Assessment:**
- Is rating on watch? (positive/negative/developing)
- Was there a recent downgrade? (within last 12 months)
- Are any facilities under "non-cooperation" status?
- Does the agency express going concern risk?

Output as structured JSON matching the RatingReportExtraction schema."""
