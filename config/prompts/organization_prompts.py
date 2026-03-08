"""
Intelli-Credit — Organization Prompt Templates

Prompt templates for Agent 1.5 (The Organizer).
All prompts live here — never hardcoded in agent code.
"""

# ── 5 Cs Classification ──
FIVE_CS_CLASSIFICATION_PROMPT = """You are organizing verified financial data into the 5 Cs credit framework.

**NORMALIZED DATA PACKAGE:**
{normalized_data}

**CROSS-VERIFICATION RESULTS:**
{cross_verification}

**CONTRADICTIONS:**
{contradictions}

Classify each extracted data point into the appropriate C module:

**CAPACITY (Financial ability to repay):**
- Revenue, EBITDA, PAT trends (3 years)
- DSCR computation (EBITDA / (Interest + Principal))
- Working capital cycle (Receivable days + Inventory days - Payable days)
- Cash flow from operations
- Bank statement regularity (EMI bounces, credit patterns)

**CHARACTER (Borrower's track record and integrity):**
- Promoter background (criminal cases, defaults, SEBI/RBI flags)
- RPT disclosure accuracy (AR vs Board Minutes)
- Auditor qualifications and emphasis of matter
- Management changes (CFO turnover, director resignations)
- Credit history (rating upgrades/downgrades)

**CAPITAL (Skin in the game):**
- Debt-to-Equity ratio (Total debt / Net worth)
- Net worth trend
- Existing debt obligations
- Promoter contribution to this specific loan
- Share pledge levels

**COLLATERAL (Security offered):**
- Collateral coverage ratio (security value / loan amount)
- Asset quality and type (fixed vs movable, depreciating vs appreciating)
- Existing liens and charges
- Valuation recency and reliability

**CONDITIONS (External environment):**
- Sector outlook (Government source data preferred)
- Order book / pipeline visibility
- Regulatory environment (favorable: PLI, adverse: new compliance)
- Customer/supplier concentration risk
- Market position (market share, competition)

For each data point assigned:
- State the source document, page number, and exact excerpt
- Assign a confidence score based on source weight
- Flag items from self-reported sources that contradict government sources"""


# ── Metric Computation ──
METRIC_COMPUTATION_PROMPT = """You are computing derived financial metrics for credit scoring.

**RAW FINANCIALS (Verified):**
{financials}

Compute the following metrics with full formula transparency:

**Capacity Metrics:**
- DSCR = EBITDA / (Interest Expense + Principal Repayment)
- Revenue CAGR = ((Current Revenue / Base Revenue) ^ (1/years) - 1)
- EBITDA Margin = EBITDA / Revenue × 100
- Working Capital Cycle = Receivable Days + Inventory Days - Payable Days
  where Receivable Days = (Trade Receivables / Revenue) × 365
  and Inventory Days = (Inventory / COGS) × 365
  and Payable Days = (Trade Payables / COGS) × 365

**Capital Metrics:**
- D/E Ratio = Total Debt / Net Worth
- Interest Coverage = EBITDA / Interest Expense
- Current Ratio = Current Assets / Current Liabilities

**Collateral Metrics:**
- Collateral Coverage = Total Security Value / Loan Amount
- Asset Quality Score (based on asset types and depreciation)

For each metric:
- Show the computation formula with actual values
- State the source of each input value
- Provide the sector benchmark for comparison
- Flag metrics that are below sector median"""


# ── Graph Construction Guidance ──
GRAPH_CONSTRUCTION_PROMPT = """You are structuring entity relationships for knowledge graph construction.

**EXTRACTED ENTITIES:**
{entities}

**TRANSACTION DATA:**
{transactions}

**DIRECTORSHIP DATA:**
{directorships}

Map the following relationship types for Neo4j:

**Nodes to create:**
- Company (name, CIN, sector, revenue)
- Director (name, DIN, designation)
- Supplier (name, transaction_value, % of purchases)
- Customer (name, transaction_value, % of revenue)
- Bank (name, facility_type, facility_amount)
- Auditor (name, qualification_type)

**Relationships to create:**
- IS_DIRECTOR_OF (Director → Company : period, attendance%)
- SUPPLIES_TO (Supplier → Company : annual_value, % concentration)
- BUYS_FROM (Company → Customer : annual_value, % concentration)
- HAS_CHARGE (Bank → Company : facility_type, amount)
- IS_AUDITOR_OF (Auditor → Company : years, qualification?)
- HAS_RATING_FROM (Company → RatingAgency : current_rating, outlook)

For each relationship, include:
- Transaction amounts (₹ Lakhs)
- Concentration percentages
- Duration/period
- Source document and page"""


# ── ML Feature Preparation ──
ML_FEATURE_PREP_PROMPT = """You are preparing feature vectors for ML anomaly detection models.

**FINANCIAL DATA:**
{financial_data}

**TRANSACTION DATA:**
{transaction_data}

**GRAPH SUMMARY:**
{graph_summary}

Prepare features for:

**Isolation Forest (Tabular Anomaly Detection):**
Extract numerical features:
- Revenue growth rate (3 years)
- EBITDA margin trend
- D/E ratio
- DSCR
- Working capital cycle (days)
- Promoter pledge %
- RPT as % of revenue
- Cheque bounce rate
- ITC gap % (GSTR-3B vs 2A)
- Auditor qualification flag (0/1)
- Director resignation count
- Litigation amount as % of net worth

**DOMINANT GNN (Graph Anomaly Detection):**
Prepare graph adjacency matrix:
- Node features: [entity_type, transaction_value, risk_flags]
- Edge features: [relationship_type, transaction_amount, directionality]
- Target: identify structurally anomalous nodes (potential circular trading, shell entities)

**FinBERT (Financial Text Risk):**
Extract text segments for buried risk detection:
- Auditor's report emphasis of matter paragraphs
- Management Discussion & Analysis (MD&A) risk sections
- Board minutes resolution discussions
- Rating report key concerns section"""
