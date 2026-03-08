"""
Intelli-Credit — Research Prompt Templates

Prompt templates for Agent 2 (Research Agent).
All prompts live here — never hardcoded in agent code.
"""

# ── Web Search Query Generation ──
SEARCH_QUERY_GENERATION_PROMPT = """You are generating targeted web search queries for corporate due diligence.

**COMPANY:** {company_name}
**CIN:** {cin}
**SECTOR:** {sector}
**PROMOTERS:** {promoter_names}
**LOAN AMOUNT:** ₹{loan_amount}

Generate search queries for each research track:

**Track 1 — Regulatory (Government Sources, Weight 1.0):**
- SEBI orders/penalties against company or promoters
- RBI directions or circulars affecting the company
- MCA21 recent filings, charge creation/modification
- NCLT orders involving the company
- GST compliance status
Queries should target: sebi.gov.in, rbi.org.in, mca.gov.in, nclt.gov.in

**Track 2 — Financial Media (Weight 0.85):**
- Recent news about the company (last 24 months)
- Sector analysis and outlook
- Peer company comparisons
- Any negative press (fraud allegations, defaults, regulatory issues)
Queries should target: economictimes.com, livemint.com, business-standard.com, financialexpress.com

**Track 3 — Legal/Litigation (Weight 0.85):**
- Court cases involving the company or promoters
- NJDG (National Judicial Data Grid) records
- Consumer complaints
- Labor disputes

For each query, specify:
- Search engine to use (Tavily for general, Exa for semantic, SerpAPI for Google)
- Expected source tier (1-5)
- Key data points to extract from results"""


# ── Research Result Verification ──
RESEARCH_VERIFICATION_PROMPT = """You are verifying and scoring web research results for credit appraisal.

**SEARCH RESULTS:**
{search_results}

**SOURCE CREDIBILITY TIERS:**
Tier 1 (Weight 1.0): Government portals (MCA21, SEBI, RBI, NJDG, GST)
Tier 2 (Weight 0.85): Reputable financial media (ET, BS, Mint, FE)
Tier 3 (Weight 0.60): General/regional news
Tier 4 (Weight 0.30): Blogs, unverified sites
Tier 5 (Weight 0.0): Social media, anonymous — REJECT

For each result:
1. Classify the source tier (1-5)
2. Assign credibility weight
3. Extract relevant data points
4. Cross-reference with document extractions:
   - Does this confirm or contradict what we found in documents?
   - Does this reveal information NOT present in submitted documents?
5. Flag high-impact findings (regulatory actions, fraud allegations, defaults)

Reject any result from Tier 5 sources.
For Tier 4, only include if corroborated by Tier 1-3 source."""


# ── Neo4j Graph Enrichment ──
GRAPH_ENRICHMENT_PROMPT = """You are enriching the knowledge graph with external research findings.

**CURRENT GRAPH ENTITIES:**
{existing_entities}

**RESEARCH FINDINGS:**
{research_findings}

**SCRAPER RESULTS:**
{scraper_results}

Determine new nodes and relationships to add:

**From MCA21 Scraper:**
- Director cross-appointments (same director on multiple boards)
- Recent charge registrations (new secured creditors)
- Recent filings (form changes, resolutions)

**From SEBI Scraper:**
- Regulatory orders against the company or promoters
- Investigation status

**From RBI Scraper:**
- Wilful defaulter list matches
- SMA (Special Mention Account) categorization
- NPA status of related entities

**From NJDG Scraper:**
- Court cases not disclosed in Annual Report
- Case values and status

**From GST Scraper:**
- GSTIN validity and status
- Return filing regularity

For each new entity/relationship:
- Link to existing graph nodes where possible
- Set source_tier and confidence
- Flag undisclosed items (found externally but not in submitted documents)"""


# ── Scraper Result Parsing ──
SCRAPER_RESULT_PROMPT = """You are parsing raw scraper output from Indian government portals.

**PORTAL:** {portal_name}
**RAW HTML/DATA:**
{raw_content}

**TARGET COMPANY:** {company_name}
**IDENTIFIER:** {identifier}

Extract structured data:

**For MCA21:**
- Company status (Active/Strike-off/Under Liquidation)
- Date of incorporation
- Registered office address
- Directors list (name, DIN, appointment date, status)
- Charges (holder, amount, date, status)
- Recent filings (form type, date, description)

**For SEBI:**
- Orders (date, order number, penalty, subject)
- Investigation status
- Debarment orders

**For RBI:**
- Wilful defaulter match (YES/NO)
- Defaulter suit amount
- NPA classification if any
- Basel III capital adequacy (for banking entities)

**For NJDG:**
- Case count, pending/disposed
- Total claim amount
- Case types (civil/criminal/consumer)
- High value cases (>₹1cr)

**For GST:**
- GSTIN status (Active/Cancelled/Suspended)
- Registration date
- Return filing status (regular/irregular/defaulter)
- Last return filed date

Handle missing/unavailable data gracefully — return partial results with confidence flags."""
