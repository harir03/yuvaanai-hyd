"""
Intelli-Credit — Reasoning Prompt Templates

Prompt templates for Agent 2.5's 5 graph reasoning passes.
All prompts live here — never hardcoded in agent code.
"""

# ── Pass 1: Contradictions ──
CONTRADICTION_ANALYSIS_PROMPT = """You are a credit analyst examining contradictions between self-reported and verified data.

**DOCUMENT CLAIMS:**
{document_claims}

**VERIFIED FINDINGS (Government/Third-party sources):**
{verified_findings}

**GRAPH RELATIONSHIPS:**
{graph_context}

Identify any contradictions where self-reported claims do NOT match verified findings.
For each contradiction, explain the specific discrepancy and its severity for credit risk.

Focus on:
- Litigation disclosure mismatches (AR vs NJDG/Court records)
- Revenue discrepancies (AR vs ITR vs GST vs Bank)
- RPT disclosure gaps (AR vs actual graph relationships)
- Director/governance discrepancies

Output a structured list of contradictions found."""


# ── Pass 2: Cascade Risk ──
CASCADE_RISK_PROMPT = """You are a credit risk analyst assessing cascade failure risk.

**COMPANY FINANCIALS:**
{financials}

**COUNTERPARTY GRAPH:**
{counterparty_graph}

**KNOWN RISK EVENTS:**
{risk_events}

Trace cascade chains:
1. Counterparty in NCLT/NPA/litigation → revenue concentration risk
2. Revenue at risk → impact on DSCR and repayment capacity
3. Supplier concentration → production risk if supplier fails

For each cascade chain found, compute:
- Revenue at risk (% and amount)
- DSCR impact (before and after)
- Severity classification

Focus on chains that would push DSCR below 1.0x."""


# ── Pass 3: Hidden Relationships ──
HIDDEN_RELATIONSHIP_PROMPT = """You are a fraud detection analyst examining entity relationships.

**KNOWLEDGE GRAPH ENTITIES:**
{entities}

**SHARED DIRECTOR ANALYSIS:**
{shared_directors}

**COMMUNITY CLUSTERS:**
{clusters}

**RPT DISCLOSURES (Self-reported):**
{rpt_disclosures}

Identify undisclosed or suspicious relationships:
1. Directors serving on boards of multiple related entities (potential conflict of interest)
2. Suppliers/customers that share addresses or directors with the target company (potential shell companies)
3. Circular trading patterns (A→B→C→A)
4. Entities that appear in the graph but are NOT disclosed in RPT reports

For each hidden relationship, assess the fraud risk and potential financial impact."""


# ── Pass 4: Temporal Patterns ──
TEMPORAL_ANALYSIS_PROMPT = """You are a credit analyst examining multi-year financial trends.

**FINANCIAL TIME SERIES:**
{time_series}

**BENCHMARK DATA:**
{benchmarks}

Identify concerning temporal patterns:
1. Consistently declining metrics (DSCR, margins, revenue growth)
2. Deterioration acceleration (getting worse faster)
3. Metrics approaching critical thresholds
4. Divergence between reported growth and actual performance

For each pattern, project the trajectory and assess when critical thresholds may be breached."""


# ── Pass 5: Positive Signals ──
POSITIVE_SIGNAL_PROMPT = """You are a credit analyst identifying genuine strengths in the borrower profile.

**COMPANY DATA:**
{company_data}

**MARKET POSITION:**
{market_data}

**GRAPH RELATIONSHIPS:**
{graph_context}

Identify GENUINE positive signals (not just absence of negatives):
1. Strong and growing order book
2. Government subsidies or PLI support
3. Customer/supplier diversification
4. Improving financial trends
5. Strong institutional backing
6. Industry tailwinds

For each positive signal, assess its reliability and sustainability.
Only include signals with concrete evidence — no speculation."""
