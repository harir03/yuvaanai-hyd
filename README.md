# INTELLI-CREDIT-AI-Powered Credit Decisioning Engine

> **Architecture Version: A0.1**
> An end-to-end intelligent credit appraisal system that transforms weeks of manual document review into a fully transparent, AI-driven pipeline completing in under 4 minutes — with every decision sourced, every reasoning step visible, and every outcome permanently recorded.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Core Philosophy](#2-core-philosophy)
3. [System Architecture](#3-system-architecture)
4. [Complete Agent Pipeline](#4-complete-agent-pipeline)
   - [Stage 1: Parallel Document Workers](#stage-1-parallel-document-workers-8-workers)
   - [Stage 2: Agent 0.5 — The Consolidator](#stage-2-agent-05--the-consolidator)
   - [Stage 3: Validator Node](#stage-3-validator-node)
   - [Stage 4: Agent 1.5 — The Organizer](#stage-4-agent-15--the-organizer)
   - [Stage 5: Agent 2 — The Research Agent](#stage-5-agent-2--the-research-agent)
   - [Stage 6: Agent 2.5 — Graph Reasoning Agent](#stage-6-agent-25--graph-reasoning-agent)
   - [Stage 7: Evidence Package Builder](#stage-7-evidence-package-builder)
   - [Stage 8: Ticketing Layer](#stage-8-ticketing-layer)
   - [Stage 9: Agent 3 — Recommendation Engine](#stage-9-agent-3--recommendation-engine)
5. [Universal Decision Store](#5-universal-decision-store)
6. [Live Thinking Chatbot](#6-live-thinking-chatbot)
7. [INTELLI-CREDIT Score Model](#7-intelli-credit-score-model)
8. [ML Anomaly Detection Suite](#8-ml-anomaly-detection-suite)
9. [Research Intelligence Stack](#9-research-intelligence-stack)
10. [Storage Architecture](#10-storage-architecture)
11. [Complete Technology Stack](#11-complete-technology-stack)
12. [UI Components, Pages & Dashboard](#12-ui-components-pages--dashboard)
13. [Latency Optimization](#13-latency-optimization)
14. [Project Structure](#14-project-structure)
15. [Infrastructure & Deployment](#15-infrastructure--deployment)
16. [Key Features Summary](#16-key-features-summary)

---

## 1. Project Overview

**Intelli-Credit** is an AI-powered **Credit Appraisal Memo (CAM)** generation system designed for the Indian banking sector. It ingests corporate loan application documents, performs deep multi-source research, detects fraud patterns through graph intelligence, scores the borrower on a 0–850 scale, and produces a fully cited, bank-grade Credit Appraisal Memo — all while showing the credit officer every single step of its reasoning in real time.

### What It Solves

| Traditional Process | Intelli-Credit |
|---|---|
| 2–3 weeks manual review | < 4 minutes end-to-end |
| Single analyst perspective | 8 parallel document workers + 5 research tracks + 5 reasoning passes |
| No cross-document verification | Every claim cross-checked across all sources |
| Black-box decisions | Every point in the score traced to a specific document, page, and paragraph |
| Lost institutional knowledge | Every decision (approve, reject, fraud) stored permanently with outcomes tracked |
| No real-time visibility | Live Thinking Chatbot shows AI reasoning as it happens |

### Three Pillars

| Pillar | Agent | Responsibility |
|---|---|---|
| **Data Ingestor** | Workers → Agent 0.5 → Validator → Agent 1.5 | Read, parse, normalize, organize, compute, graph-build |
| **Research Agent** | Agent 2 → Agent 2.5 | External intelligence + graph reasoning + compound insights |
| **Recommendation Engine** | Evidence Builder → Tickets → Agent 3 | Score (0–850) + CAM generation + decision storage |

---

## 2. Core Philosophy

### Principle 1: DATA BEFORE LLM
Every piece of data is organized, verified, and sourced **before** any LLM sees it. LLMs write and reason. They never hunt for data.

### Principle 2: SINGLE RESPONSIBILITY
Every agent does exactly one job. Every database stores exactly one type of thing. No component does two things.

### Principle 3: NOTHING IS LOST
Every decision — approve, reject, fraud, borderline — is stored with full evidence and reasoning. Every AI thought is logged and shown. Every human resolution is recorded and learned from.

### Principle 4: FULL TRANSPARENCY
The credit officer sees exactly what the AI read, what it thought, what it accepted, what it rejected, and why — in real time, in plain language.

---

## 3. System Architecture

### Master Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                                 │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Upload      │  │  Progress    │  │  Ticket      │  │  CAM Viewer   │  │
│  │  Portal      │  │  Tracker     │  │  Resolution  │  │  + Download   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └───────────────┘  │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │               LIVE THINKING CHATBOT                                  │  │
│  │  "Agent 1.5 is reading Annual Report pg 43..."                      │  │
│  │  "Found revenue ₹124.5cr — accepted ✓"                             │  │
│  │  "FinBERT flagged paragraph on pg 67 — risk signal detected"       │  │
│  │  "Agent 2 running MCA21 scraper for Rajesh Shah..."                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────────────────────────────────┐   │
│  │  Management      │  │  Score Report + Decision Store Viewer        │   │
│  │  Interview Form  │  │  (ALL decisions — approvals + rejections)    │   │
│  └──────────────────┘  └──────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ WebSockets (bidirectional real-time)
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                           API GATEWAY LAYER                                 │
│              FastAPI │ Pydantic v2 │ JWT Auth │ Rate Limiting               │
│                   Redis Queue │ Celery Workers │ Flower Monitor             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                      PARALLEL DOCUMENT WORKERS                              │
│                                                                             │
│  W1: Annual Report   W2: Bank Statement   W3: GST Returns   W4: ITR        │
│  W5: Legal Notice    W6: Board Minutes    W7: Shareholding   W8: Rating     │
│                                                                             │
│  Each worker emits THINKING EVENTS as it processes                         │
│  All outputs land in Redis Staging Area                                    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                    AGENT 0.5 — THE CONSOLIDATOR                             │
│  Wait for all → Normalize → Conflict Detection → Cross-doc Contradictions  │
│  → Build RawDataPackage → Emit thinking events throughout                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────────┐
                    │             │                  │
               Complete       Missing            Conflicts
                    │             │                  │
                    ▼             ▼                  ▼
              VALIDATOR      Request            Ticket raised
              Node           from user          immediately
                    │
┌───────────────────▼─────────────────────────────────────────────────────────┐
│                    AGENT 1.5 — THE ORGANIZER                                │
│  5 Cs mapping → Compute metrics → Tag sources → Build Neo4j internal graph │
│  Board minutes + Shareholding analysis → ML Anomaly Suite                  │
│  → FeatureObject → OrganizedPackage → Emit thinking events                 │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                    AGENT 2 — THE RESEARCH AGENT                             │
│  Tavily │ Exa │ SerpAPI │ MCA21 │ NJDG │ SEBI │ RBI │ GSTIN               │
│  All parallel → Verification Engine → Director Network Mapping              │
│  Enrich Neo4j → VerifiedResearchPackage → Emit thinking events             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                  AGENT 2.5 — GRAPH REASONING AGENT                          │
│  Pass 1: Contradictions → Pass 2: Cascade Risk → Pass 3: Hidden Relations  │
│  Pass 4: Temporal Patterns → Pass 5: Positive Signals                      │
│  → Insight Store → Emit thinking events per reasoning step                 │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                    EVIDENCE PACKAGE BUILDER                                  │
│  Organize by 5 Cs → Attach source to every claim → Raise tickets           │
│  → Emit thinking events for every decision                                 │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                       TICKETING LAYER                                       │
│  Human resolves conflicts → AI dialogue → RAG precedents                   │
│  Resolutions → Knowledge Base → Outcome tracking                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                  AGENT 3 — RECOMMENDATION ENGINE                            │
│  INTELLI-CREDIT SCORE 0-850 → Per-point breakdown with sources             │
│  Loan amount + rate DERIVED from score → CAM Writer                        │
│  → Emit thinking events per module computed                                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                 UNIVERSAL DECISION STORE                                     │
│  ALL outcomes stored: Approvals + Rejections + Fraud + Borderline          │
│  Full pipeline state snapshot for every decision                           │
└─────────────────────────────────────────────────────────────────────────────┘

INTELLIGENCE LAYER (serves all agents)
┌──────────────┐ ┌──────────────┐ ┌─────────────────┐ ┌──────────────────┐
│  ChromaDB    │ │    Neo4j     │ │  Elasticsearch  │ │   PostgreSQL     │
│  Semantic    │ │   Knowledge  │ │  Full-text +    │ │  FeatureObjects  │
│  Vector      │ │   Graph      │ │  NER Search     │ │  Insight Store   │
│  Search      │ │              │ │  4 indices      │ │  Decision Store  │
│              │ │              │ │                 │ │  Ticket Store    │
│              │ │              │ │                 │ │  Knowledge Base  │
└──────────────┘ └──────────────┘ └─────────────────┘ └──────────────────┘
                         └──────────GraphRAG Engine────────────┘

THINKING EVENT BUS
┌─────────────────────────────────────────────────────────────────────────────┐
│  Redis Pub/Sub → Every agent publishes thinking events →                   │
│  WebSocket server subscribes → Pushes to Live Chatbot in real time        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Orchestration Engine

The entire pipeline is a **LangGraph state machine**. A `CreditAppraisalState` Pydantic object passes through every node carrying the accumulated knowledge of all previous stages. Conditional edges implement routing:

- **Normal path**: Workers → 0.5 → Validator → 1.5 → 2 → 2.5 → Evidence → Tickets → 3 → Decision Store
- **Auto-reject path**: Hard block trigger at any stage → immediate rejection with full evidence snapshot
- **Deep fraud path**: ML fraud signal > threshold → freeze graph subgraph → fraud investigation store → regulatory referral
- **Human review path**: Borderline score (550–650) → pipeline pauses → senior manager review → resume

**LangGraph** provides explicit control over every node and edge with the `CreditAppraisalState` object persisting state across the entire flow. **LangChain** powers the agent framework within each node — document loaders, chains, RAG retrievers, tool integrations, and automatic LangSmith tracing.

### CreditAppraisalState Object Structure

The `CreditAppraisalState` (Pydantic v2) is the backbone of the entire pipeline. Every node reads from and writes to this object:

```python
class CreditAppraisalState(BaseModel):
    # Session metadata
    session_id: str
    company: CompanyInfo
    started_at: datetime
    
    # Stage tracking
    current_stage: PipelineStageEnum
    pipeline_stages: List[PipelineStage]
    
    # Worker tracking
    workers_completed: int = 0
    worker_outputs: Dict[str, WorkerOutput]  # W1..W9 keyed by worker_id
    
    # Agent outputs (populated as pipeline progresses)
    raw_data_package: Optional[RawDataPackage]         # After Agent 0.5
    organized_package: Optional[OrganizedPackage]       # After Agent 1.5
    feature_object: Optional[FeatureObject]             # After Agent 1.5
    research_package: Optional[VerifiedResearchPackage] # After Agent 2
    graph_insights: Optional[GraphInsights]             # After Agent 2.5
    evidence_package: Optional[EvidencePackage]         # After Evidence Builder
    
    # Site visit + management interview (optional inputs)
    site_visit_data: Optional[SiteVisitExtraction]
    management_interview_data: Optional[ManagementInterviewData]
    management_credibility_score: Optional[float]       # 0.0–1.0
    cibil_score: Optional[int]                          # CIBIL commercial score
    
    # Routing flags (set by any node, checked by conditional edges)
    hard_block_triggered: bool = False
    hard_block_reason: Optional[str]
    fraud_detected: bool = False
    fraud_type: Optional[str]
    awaiting_human_input: bool = False
    
    # Tickets
    tickets: List[Ticket]
    
    # Thinking events (complete AI thought log)
    thinking_events: List[ThinkingEvent]
    
    # Final outputs (set by Agent 3)
    final_score: Optional[int]                          # 0–850
    score_band: Optional[ScoreBand]
    score_breakdown: List[ScoreBreakdownEntry]
    recommendation: Optional[LoanRecommendation]
    cam_document_path: Optional[str]
```

Every LangGraph node receives this state and returns a partial update dict. The state accumulates knowledge as it flows through the pipeline.

---

## 4. Complete Agent Pipeline

---

### Stage 1: Parallel Document Workers (9 Workers)

All 9 workers fire simultaneously as independent **Celery tasks** via **Redis** as the message broker. Each worker processes one document type and writes its output to a **Redis Staging Area**. Every worker emits **Thinking Events** to the Live Chatbot as it extracts data.

#### Worker 1: Annual Report Processor

| Attribute | Detail |
|---|---|
| **Input** | Annual Report PDF (typically 100–300 pages, often partially scanned) |
| **Tech** | Unstructured.io (spatial layout parsing) + Tesseract OCR (scanned pages) + Camelot (table extraction) |
| **Extracts** | Revenue (3-year), EBITDA, PAT, Total Debt, Net Worth, Current Assets/Liabilities, Director's Report narrative, Related Party Transactions, Auditor Qualifications, Litigation Disclosure |
| **Cross-checks queued** | RPT disclosure vs Board Minutes, Litigation disclosure vs NJDG, Revenue vs ITR/GST |
| **Output schema** | `AnnualReportExtraction` (Pydantic v2 model) |

**Why Unstructured.io**: Indian annual reports use complex multi-column layouts, headers/footers, tables spanning pages, and footnotes. Unstructured.io understands document layout spatially — it identifies columns and extracts each separately. PyMuPDF reads in DOM order which destroys column structure.

**Why Tesseract OCR**: Open-source, runs locally with zero per-page cost. Configured with page-level parallelism, rupee symbol in character set, mixed Hindi-English text support, `psm 6` for financial table pages for optimal Indian document handling.

#### Worker 2: Bank Statement Processor

| Attribute | Detail |
|---|---|
| **Input** | 12-month bank statement PDF (CC/OD accounts) |
| **Tech** | Camelot (table extraction) + Pandas (time-series analysis) |
| **Extracts** | Monthly inflows/outflows, cheque bounce count + amounts + dates, EMI regularity, end-of-quarter round-number transactions, large cash deposits, inward/outward return patterns |
| **Anomaly detection** | Flags end-of-quarter round-number transactions as potential circular trading signals |
| **Derived metrics** | Annual inflow total, average monthly balance, bounce ratio, payment stress score |

#### Worker 3: GST Returns Processor

| Attribute | Detail |
|---|---|
| **Input** | GSTR-3B (self-declared returns) + GSTR-2A (auto-populated purchase register) |
| **Tech** | Pandas + custom Indian GST schema parser |
| **Critical computation** | **GSTR-2A vs GSTR-3B Reconciliation** — Input Tax Credit (ITC) claimed in 3B vs ITC available in 2A. If claimed > available, this signals potential fake invoice fraud. This is in the official evaluation criteria. |
| **Extracts** | Monthly turnover declared, ITC claimed vs available, filing regularity, GSTIN details |
| **Live GSTIN verification** | GSTIN number verified against government portal in real time (existence, active status, name match, filing frequency, cancellation status) — catches document fabrication |

#### Worker 4: ITR Processor

| Attribute | Detail |
|---|---|
| **Input** | ITR-6 XML/PDF (Corporate tax returns) |
| **Tech** | Custom XML parser + Pandas |
| **Extracts** | Schedule BP (business income), Schedule BS (balance sheet), all ITR schedules exhaustively |
| **Critical computation** | **ITR-vs-Annual Report Divergence** — compares declared income in ITR against revenue in Annual Report. Gap > 10% flags potential dual accounting. Also cross-references against GST revenue for three-way validation. |

#### Worker 5: Legal Notice Processor

| Attribute | Detail |
|---|---|
| **Input** | Any legal notices, demand letters, show-cause notices |
| **Tech** | Claude Haiku (LLM semantic extraction — legal documents have unstructured narrative) |
| **Extracts** | Claimant identity, claim type (recovery/cheque bounce/contract), claimed amounts, dates, responding authority, current status |
| **Note** | Many legal findings come from Agent 2's NJDG scraper rather than submitted documents — submitted legal documents often under-represent actual litigation. |

#### Worker 6: Board Meeting Minutes Processor

| Attribute | Detail |
|---|---|
| **Input** | Board meeting minutes from the financial year |
| **Tech** | Claude Haiku (semantic extraction — board minutes are narrative) |
| **Extracts** | Director attendance patterns, concerns raised by any director, CFO/key management changes with dates, **Related Party Transaction approvals** (complete list with amounts), risk discussions, strategic decisions, independent director resignations |
| **Critical cross-check** | RPTs approved in board minutes vs RPTs disclosed in annual report. If board approved 5 RPTs but annual report shows 2, this is **active concealment** — not a timing issue. |
| **Governance signals** | CFO resignation mid-year, multiple independent director exits, risk concerns raised then ignored |

#### Worker 7: Shareholding Pattern Processor

| Attribute | Detail |
|---|---|
| **Input** | Quarterly shareholding pattern filings (typically last 4 quarters) |
| **Tech** | Camelot (structured tabular data) + Pandas (trend analysis) |
| **Extracts** | **Promoter shareholding %** (current + 4-quarter trend), **Promoter shares pledged %** (current + trend), institutional holding changes, cross-holdings identification |
| **Flags** | Pledge ratio > 50% = concern, > 70% = major flag. Consistent promoter holding reduction signals promoter selling own shares. Cross-holdings with borrower's suppliers/customers signal related-party networks. |

#### Worker 8: Rating Agency Reports Processor

| Attribute | Detail |
|---|---|
| **Input** | Credit rating reports from CRISIL/ICRA/CARE/India Ratings |
| **Tech** | Claude Haiku (narrative extraction + structured rating parsing) |
| **Extracts** | Current rating + history, upgrade/downgrade trajectory, **watch/outlook signals** (Positive/Stable/Negative/Credit Watch), key risk factors cited by rating agency, specific rating agency language for CAM inclusion |
| **Analysis** | Downgrade history more important than current rating. Rating agencies use careful language — a "stable outlook" after a downgrade is very different from a "stable outlook" maintained for 3 years. |

#### Worker 9: Factory / Site Visit Notes Processor

| Attribute | Detail |
|---|---|
| **Input** | Credit officer's factory/site visit report (PDF or structured form) |
| **Tech** | Claude Haiku (narrative extraction + structured comparison) |
| **Extracts** | Plant capacity observed vs stated in AR, worker count observed vs payroll declared, raw material inventory visible vs balance sheet, equipment condition vs depreciation schedule, security/collateral physically sighted and condition noted, management behavior/demeanor observations, discrepancies between site observations and submitted documents |
| **Cross-references** | Every observed figure is automatically cross-referenced against the corresponding claim in other documents. Example: "Observed 120 workers on factory floor. Payroll in bank statement shows 340 employees. Gap: 220 — possible payroll inflation or ghost employees." |
| **Output Action** | All discrepancies between site observations and document claims are emitted as FLAGGED ThinkingEvents and fed as discrepancy items into the Evidence Package for scoring. Positive observations ("factory well-maintained, inventory matches BS") feed as supporting evidence. |

#### Additional Input: CIBIL Commercial Report
Handled as an **input field in the UI** rather than a document worker. When provided, integrated into the Character module scoring with explicit score impact (see Section 7 — CIBIL Commercial Score metric). When not available, noted as absent with a confidence reduction applied to the Character score.

#### Additional Input: Databricks Connector
Represented as the data source layer in the architecture. A mock Databricks connector module reads from local files with the same interface as a real Databricks connection. Designed for easy swap to a real Databricks cluster in production.

---

### Stage 2: Agent 0.5 — The Consolidator

**Purpose**: Solves the parallel worker data loss problem — when 8 workers run independently, conflicting data between documents is never reconciled without an explicit merging step.

#### Internal Pipeline (6 Steps)

| Step | Operation | Detail |
|---|---|---|
| 1 | **Completion Monitor** | Polls Redis every 2 seconds. Knows which workers are running. Waits until all 8 complete or timeout (configurable per worker type). |
| 2 | **Schema Normalization** | Every worker outputs slightly different structures. Normalizer converts all to unified `NormalizedExtraction` schema. Amounts normalized to lakhs. Dates to ISO. Names to title-case. |
| 3 | **Conflict Detection** | Same data point from multiple sources → apply priority rules: **Government source > Third-party source > Self-reported source**. Example: GST revenue (government filing) beats Annual Report revenue (self-reported). |
| 4 | **Completeness Check** | Checks against mandatory/important/optional field lists. **Mandatory**: Revenue, EBITDA, total debt, promoter holding. **Important**: DSCR inputs, working capital data. **Optional**: rating report, legal notices. Missing mandatory → request from user. Missing optional → note and continue. |
| 5 | **Cross-Document Contradiction Detection** | 5 specific checks: (a) Revenue across AR/ITR/GST/Bank, (b) RPTs in Board Minutes vs Annual Report, (c) Litigation disclosure vs actual legal documents, (d) Net worth in AR vs ITR balance sheet, (e) Employee count across AR/ESI/PF records. |
| 6 | **Build RawDataPackage** | Consolidates everything into a single Pydantic v2 `RawDataPackage` object with every field tagged with its source document + page number + confidence score. |

**Conflict Priority Rules**:
```
Government source (GST portal, ITR, SEBI) → weight 1.0
Third-party source (Rating agency, bank statement) → weight 0.85
Self-reported source (Annual Report, management claims) → weight 0.70
```

---

### Stage 3: Validator Node

| Check | Method | Action on Failure |
|---|---|---|
| Schema validation | Pydantic v2 strict mode | Reject with specific field error |
| Mandatory document presence | Field completeness map | Request from user |
| 3 years financial data | Year count validation | Proceed with reduced confidence |
| Bank statement 12-month coverage | Month count | Request missing months |
| GSTIN live verification | Government portal API call | Flag fabrication risk |
| Numerical range validation | Min/max bounds per field | Flag outliers |

The Validator does **not** make judgment calls — it enforces technical completeness and hands off to Agent 1.5 for intelligent analysis.

---

### Stage 4: Agent 1.5 — The Organizer

**Purpose**: Takes raw consolidated data and transforms it into an organized, computed, graph-connected, ML-analyzed package ready for research and reasoning.

#### Internal Pipeline (7 Steps)

**Step 1: Map to 5 Cs Framework**

Every extracted data point is tagged with its **C category**:

| C | What It Covers |
|---|---|
| **Character** | Promoter background, management quality, compliance history, SEBI/RBI records, litigation, share pledge |
| **Capacity** | Revenue, EBITDA, DSCR, working capital cycle, cash flow, repayment history |
| **Capital** | Net worth, D/E ratio, existing debt structure, equity contributions |
| **Collateral** | Asset coverage, asset quality, lien status, valuation source |
| **Conditions** | Industry outlook, regulatory environment, order book, market position |

**Step 2: Compute All Derived Metrics**

| Metric | Formula | Source Fields |
|---|---|---|
| **DSCR** | EBITDA / Annual Debt Service | Annual Report EBITDA + Loan schedule |
| **Current Ratio** | Current Assets / Current Liabilities | Balance Sheet |
| **Debt-to-Equity** | Total Debt / Net Worth | Balance Sheet |
| **Working Capital Cycle** | Debtor Days + Inventory Days − Creditor Days | Balance Sheet |
| **Revenue CAGR** | (Revenue_FY24/Revenue_FY22)^(1/2) − 1 | 3-year revenue data |
| **GST-Bank Divergence** | Bank Inflows / GST Turnover | W2 + W3 outputs |
| **ITR-AR Divergence** | (AR Revenue − ITR Income) / AR Revenue | W1 + W4 outputs |

**Step 3: Board Minutes Deep Analysis**

Extracts governance signals: CFO/key management changes, independent director resignations, risk concerns raised by any director, RPT approval count and amounts, strategic direction changes, audit committee observations.

**Step 4: Shareholding Pattern Analysis**

Computes: promoter pledge ratio trend (4 quarters), promoter holding trend, institutional investor movements, cross-holding detection with borrower's counterparties.

**Step 5: Build Internal Neo4j Knowledge Graph**

Creates nodes and relationships from all internal documents:

| Node Types | Relationship Types |
|---|---|
| Company (borrower) | `SUPPLIES_TO`, `BUYS_FROM` |
| Promoter/Director | `IS_DIRECTOR_OF`, `FAMILY_OF` |
| Supplier | `HAS_CHARGE` (registered loan) |
| Customer | `OUTSTANDING_RECEIVABLE` |
| Bank/Lender | `IS_AUDITOR_OF` |
| Auditor | `HAS_RATING_FROM` |
| Rating Agency | `FILED_CASE_AGAINST` |

**Step 6: Run ML Anomaly Suite** (3 models in parallel)

| Model | Target | Input | Output |
|---|---|---|---|
| **DOMINANT GNN** | Circular trading / shell company detection | Neo4j entity-relationship graph | Fraud probability score per community |
| **Isolation Forest** | Tabular financial anomalies | DSCR, D/E, WC cycle, revenue growth, GST-Bank divergence, ITC overclaim ratio | Anomaly score per metric (0–1) |
| **FinBERT** | Hidden risk in management narrative | Director's Report, MD&A, management commentary | Buried risk score + surface sentiment score |

**Step 7: Produce FeatureObject + OrganizedPackage**

The `FeatureObject` is a versioned Pydantic v2 model containing every computed metric, every ML score, every source tag. The `OrganizedPackage` bundles the FeatureObject with the 5 Cs mapping and the Neo4j graph state.

---

### Stage 5: Agent 2 — The Research Agent

**Purpose**: Gathers external intelligence from 5 parallel tracks, verifies every finding through a multi-tier verification engine, and enriches the Neo4j knowledge graph with external entities and relationships.

#### Track 1: Tavily API (AI-Native Web Search)

| Attribute | Detail |
|---|---|
| **Purpose** | Primary general web search |
| **Why Tavily** | Purpose-built for LLM usage — returns clean structured text, supports domain filtering, built-in relevance scoring, native LangChain integration |
| **Queries fired** | `"{company} news India 2024 2025"`, `"{company} {promoter_name} background"`, `"{company} financial performance"`, `"{company} order book contracts"`, `"{company} {sector} market position"` |

#### Track 2: Exa Neural Search (Semantic Web Search)

| Attribute | Detail |
|---|---|
| **Purpose** | Semantic/conceptual research — finds content beyond keyword matches |
| **Why Exa** | Neural search discovers conceptually related content. Finds the promoter's OTHER company default even if the current company is never mentioned in that article. |
| **Queries fired** | Semantic: `"companies similar to {company} that defaulted in {sector}"`, `"{promoter_name} business history"`, `"{company} related entities network"` |

#### Track 3: SerpAPI (Google Wrapper for Indian News)

| Attribute | Detail |
|---|---|
| **Purpose** | Indian business news coverage |
| **Why SerpAPI** | Google has the deepest Indian news index — Economic Times, Business Standard, Mint, Financial Express, MoneyControl, regional business news |
| **Queries fired** | `"{company} site:economictimes.com"`, `"{company} site:livemint.com"`, `"{promoter_name} news"`, `"{sector} industry outlook India 2025"`, `"{sector} RBI regulations 2024 2025"` |

#### Track 4: India-Specific Custom Scrapers (5 Scrapers)

These are the most uniquely valuable research components — no API or third-party service provides this data.

##### MCA21 Scraper (Ministry of Corporate Affairs)

| Attribute | Detail |
|---|---|
| **Input** | Company name or CIN number |
| **Fetches** | All current directors with DIN numbers, director appointment/resignation dates, ALL other companies each director is/was director of (shell company detector), registered charges (all secured loans), ROC annual filing dates, registered address history, paid-up capital history |
| **Neo4j writes** | For every director: `(Director)─[IS_DIRECTOR_OF]─▶(Company)`. For every charge: `(Company)─[HAS_CHARGE]─▶(Bank)` with amount and date. |
| **Why this is gold** | Circular trading requires related parties. Related parties share directors. This scraper finds ALL director overlaps. Cross-referencing with supplier list from GST returns immediately reveals related-party supplier relationships. |

##### NJDG Scraper (National Judicial Data Grid / eCourts)

| Attribute | Detail |
|---|---|
| **Input** | Company name + state |
| **Fetches** | All pending civil cases, disposed cases (5 years), case type (recovery/cheque bounce/contract), claimant identity, claim amounts, court name, filing date, next hearing date, last order summary |
| **Why comprehensive** | Tavily finds cases reported in news. NJDG finds EVERY case including unreported district court matters. A ₹2cr cheque bounce case in a district court will never appear in any news API. NJDG finds it. |

##### SEBI Scraper (Securities and Exchange Board of India)

| Attribute | Detail |
|---|---|
| **Input** | Company name + promoter names |
| **Fetches** | Enforcement orders, adjudication orders, consent orders, show cause notices, debarment orders |
| **Significance** | SEBI actions indicate capital market fraud, insider trading, disclosure violations — about the CHARACTER of the promoter. Many banks miss this. |

##### RBI Defaulter Scraper (Reserve Bank of India)

| Attribute | Detail |
|---|---|
| **Input** | Company name |
| **Fetches** | Wilful defaulter status, defaulted amount, bank(s) with whom defaulted, date of classification |
| **Action** | **HARD BLOCK trigger**. If found → auto-reject regardless of score. RBI publishes quarterly lists. |

##### GSTIN Verifier

| Attribute | Detail |
|---|---|
| **Input** | GSTIN number from submitted documents |
| **Verifies** | GSTIN exists and is active, registered company name matches, filing frequency, registration date, cancellation status |
| **Purpose** | Anti-fabrication check. A company can submit a fake GST return PDF. They cannot fake what the GST portal says. |

#### Track 5: Regulatory Intelligence

A daily crawler feeds the Elasticsearch `regulatory_watchlist` index with:
- RBI circulars and notifications
- SEBI regulations and amendments
- MCA notifications
- GST council decisions
- PLI scheme updates
- Sector-specific ministry notifications

When the company's sector is identified, the system queries: `"regulations affecting {sector} published in last 6 months"` and returns all regulatory changes affecting the company's operating environment.

#### Verification Engine

Every research finding passes through verification before use:

| Tier | Source Type | Credibility Weight |
|---|---|---|
| Tier 1 (1.0) | Government portals (MCA21, SEBI, RBI, NJDG) | Treated as fact |
| Tier 2 (0.85) | Reputable financial media (ET, BS, Mint) | High confidence |
| Tier 3 (0.60) | General news, regional media | Moderate confidence |
| Tier 4 (0.30) | Blogs, unverified sites | Low confidence |
| Tier 5 (0.0) | Social media, anonymous sources | Rejected |

**Verification Checks**:
1. **Entity match**: Is this actually about this company?
2. **Temporal match**: Is this recent enough to matter?
3. **Risk materiality**: Does this affect any of the 5 Cs?
4. **Cross-verification**: Same claim from 2+ independent sources → boost confidence
5. **Duplication check**: Remove duplicate findings from different search APIs

**Final Classification**:
| Status | Meaning |
|---|---|
| **Verified** | Used in scoring with citation |
| **Uncertain** | Shown with caveat, not scored |
| **Rejected** | Shown with reason why rejected |
| **Conflicting** | Shown, needs human resolution via ticket |

**Technologies inside Agent 2**: Tavily API, Exa API, SerpAPI, BeautifulSoup + Selenium (custom scrapers), Redis Cache (7-day TTL per query), FinBERT (sentiment scoring of findings), asyncio (all 5 tracks + all searches run as async coroutines), Neo4j async driver (external entities written to graph as discovered).

---

### Stage 6: Agent 2.5 — Graph Reasoning Agent

**Purpose**: Takes the complete Neo4j knowledge graph (built from internal documents by Agent 1.5, enriched with external data by Agent 2) and runs 5 structured reasoning passes to find **compound insights** — dangerous patterns that no individual data point would reveal.

#### Pass 1: Contradiction Detection

| Attribute | Detail |
|---|---|
| **What it looks for** | Facts from one source that directly contradict facts from another source about the same thing |
| **Method** | For every factual claim in the graph: find all other nodes making claims about the same entity/attribute, apply semantic similarity to check agreement/contradiction |
| **Example** | "No litigation" (Annual Report) vs Active NJDG case → HIGH severity. Board minutes approve 5 RPTs, annual report shows 2 → CRITICAL severity (active concealment). |
| **Output per contradiction** | Both claims with exact sources, confidence in each, possible explanations, score impact, ticket raised with evidence |

#### Pass 2: Cascade Risk Detection

| Attribute | Detail |
|---|---|
| **What it looks for** | Chain reactions — if entity X experiences a negative event, what is the downstream impact on the borrower? |
| **Method** | Multi-hop graph traversal starting from any node with a negative signal. Follow edges back to borrower. Compute financial impact at each hop. |
| **Example** | Customer in NCLT → 38% revenue dependency → ₹14.2cr outstanding receivable (180 days) → DSCR drops from 1.43x to 0.88x → below covenant threshold → **CRITICAL cascade**. |
| **Output** | Complete chain visualization, probability of cascade, financial impact quantification, projected DSCR under stress scenario |

#### Pass 3: Hidden Relationship Detection

| Attribute | Detail |
|---|---|
| **What it looks for** | Undisclosed connections between the borrower and its supposedly independent counterparties |
| **Method** | Community detection algorithm on Neo4j graph (Louvain method via NetworkX). MCA21 director network cross-referencing. |
| **Example** | Promoter is director of 3 suppliers. Wife is director of 4th supplier. 5th supplier incorporated 3 months before first invoice. DOMINANT GNN score: 0.84 circular trading probability. |
| **Output** | Network visualization description, all connected entities, evidence for each connection, transaction amounts, shell company indicators |

#### Pass 4: Temporal Pattern Analysis

| Attribute | Detail |
|---|---|
| **What it looks for** | Multi-year trends that individually look acceptable but together show deterioration |
| **Method** | Year-over-year change for each metric, 3-year trend direction, rate of deterioration, cross-metric correlation (are multiple metrics worsening simultaneously?) |
| **Example** | DSCR: 2.1x → 1.6x → 1.3x. Working capital: 45d → 67d → 94d. CFO resigned. 2 independent directors left. All worsen from same quarter — single root cause. Projected DSCR FY25: 0.9x. |
| **Output** | Timeline of deterioration, projected future values, root cause hypothesis, months until critical threshold breach |

#### Pass 5: Positive Signal Amplification

| Attribute | Detail |
|---|---|
| **What it looks for** | Genuine strengths — not just absence of negatives but actual positive credit signals |
| **Patterns sought** | Strong diversified order book, government scheme beneficiary (PLI), collateral coverage > 1x, clean promoter record over long period, institutional investor backing |
| **Example** | Order book ₹280cr (2.8x revenue, corroborated by ET article + BHEL announcement) → +15 pts. PLI scheme ₹12cr subsidy → +8 pts. Collateral coverage 1.7x → +12 pts. |
| **Output** | All genuine strengths with sources, why each is genuinely positive (not just PR), score impact |

#### Insight Store

All 5 passes write to PostgreSQL:

```
Table: compound_insights
  company_id, type, severity, title, insight_text,
  evidence (JSON array of sources), score_impact,
  neo4j_path_ids, confidence, reasoning_trace, created_at

Table: reasoning_audit_log
  Every traversal step logged
  Every pattern checked (including dismissed ones)
  Full explainability trail
```

**Technologies inside Agent 2.5**: Neo4j + Cypher queries (all 5 passes as graph queries), Microsoft GraphRAG (hierarchical graph summarization for LLM reasoning), NetworkX (community detection — Louvain method), Claude Haiku (semantic analysis for contradiction and positive signal passes).

---

### Stage 7: Evidence Package Builder

**Purpose**: Takes everything from all previous stages and organizes it into one perfectly structured, fully cited package. **Agent 3 reads ONLY this package.** It never touches raw documents, Neo4j, or the Insight Store directly. The Evidence Package Builder is the last intelligence step. Agent 3 is purely a writer.

#### Package Structure

```
EVIDENCE PACKAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each of the 5 Cs:

  C: CHARACTER
  ──────────────
  Claim: "[text]"
  Evidence:
    Source 1: [document, page, exact text]
    Source 2: [document, page, exact text]
  Confidence: 0.94
  Score contribution: +30 pts

  [all character claims...]

  C: CAPACITY
  [all capacity claims with sources + score impacts]

  C: CAPITAL
  [all capital claims with sources + score impacts]

  C: COLLATERAL
  [all collateral claims with sources + score impacts]

  C: CONDITIONS
  [all conditions claims with sources + score impacts]

COMPOUND INSIGHTS:
  [All Agent 2.5 findings with full evidence chains]

VERIFIED RESEARCH:
  [All Agent 2 findings, tiered and annotated]

UNCERTAIN FINDINGS (shown but not scored):
  [Research findings awaiting verification]

REJECTED FINDINGS (shown with rejection reason):
  [What was found but excluded and exactly why]

CONFLICTING FINDINGS (needs resolution):
  [Opposing claims, both shown]

OPEN TICKETS:
  [All unresolved conflicts awaiting human review]
```

#### Ticket Raising Within Evidence Package Builder

When the builder encounters any of these conditions, it raises a ticket instead of making an assumption:

| Trigger | Example |
|---|---|
| Two sources contradict each other | Annual Report vs Board Minutes RPT count |
| Extraction confidence below 0.75 for a material number | OCR-extracted revenue figure unclear |
| Research finding is unverified but material | Tavily article about promoter fraud — only 1 source |
| DOMINANT GNN fraud signal without full evidence chain | Circular trading probability 0.7 but incomplete director mapping |
| Management interview claim contradicts documentary evidence | "No related party suppliers" vs MCA21 director overlap |
| Finding that would change score by > 20 pts if accepted vs rejected | Greenfield NCLT case impact on cascade DSCR |

**Pipeline behavior by ticket severity**:
| Severity | Action |
|---|---|
| LOW | Pipeline continues, ticket resolved asynchronously |
| HIGH | Pipeline pauses at Agent 3, must resolve before scoring |
| CRITICAL | Pipeline stops completely, senior manager notification sent |

---

### Stage 8: Ticketing Layer

**Purpose**: The human-AI dialogue system for resolving conflicts, ambiguities, and uncertain findings.

#### Ticket Resolution Flow

```
Human receives ticket in UI:
  → Full problem description
  → Evidence for Claim A (full citation)
  → Evidence for Claim B (full citation)
  → AI reasoning about which is more likely correct
  → Past precedents from RAG knowledge base
  → Score impact if accepted vs rejected
  → Recommended action with reasoning
  → Options: Accept A | Accept B | Escalate | Need More Info | Custom

Human responds → AI responds:
  → Confirms understanding
  → Asks follow-up if resolution has downstream implications
  → "You accepted this as post-report filing.
     Should I also update the working capital calculation
     to reflect the disputed receivable?"

Human finalizes → Resolution stored:
  → PostgreSQL ticket store
  → ChromaDB knowledge base with pattern fingerprint
  → Resolver identity + expertise level
  → Outcome field (filled when loan matures)
```

#### RAG Learning System

Every resolved ticket becomes a precedent:

```
Knowledge Base Entry:
  pattern_type:       RPT_UNDISCLOSED
  sector:             MANUFACTURING_STEEL
  company_size:       MID (₹50-200cr revenue)
  situation:          "Board minutes: 5 RPTs. Annual report: 2."
  resolution:         CONFIRMED CONCEALMENT
  resolution_reason:  "Same year, same board. No timing explanation."
  resolved_by:        Senior Credit Manager (12 yrs, steel specialist)
  score_applied:      -45 pts
  outcome:            (filled 18 months later when loan matures)
  validated_signal:   true/false
  precedent_weight:   HIGH (if outcome confirmed)
  tags:               [rpt_concealment, board_minutes_gap, steel_sector]
```

When a new similar ticket is raised, the system retrieves top 3 precedents and shows: "In a similar steel sector case, senior manager resolved as X because Y. That loan was repaid on schedule / restructured / became NPA."

Over time: system gets better at predicting human decisions, precedents accumulate institutional knowledge, outcome tracking validates which resolutions were correct.

**This is RAG-based learning, not model retraining** — appropriate for hackathon scope and practical for production.

---

### Stage 9: Agent 3 — Recommendation Engine

**Purpose**: Receives ONLY the Evidence Package. Computes the INTELLI-CREDIT Score (0–850), derives loan recommendation from the score, and writes the Credit Appraisal Memo section by section.

#### Score Computation

Starting baseline: **600** (industry average). Score moves up and down from here.

Every single point added or deducted has this structure:
- Metric name
- Value found
- How it was computed (formula)
- Exact source (document, page, table)
- Benchmark context (industry average)
- Score impact
- Reasoning paragraph explaining the impact

#### Loan Parameters Derived from Score

| Score Band | Rating | Loan Amount | Interest Rate | Conditions |
|---|---|---|---|---|
| 750–850 | Excellent | 100% of requested | MCLR + 1.5% | Standard monitoring |
| 650–749 | Good | 85% of requested | MCLR + 2.5% | Quarterly reporting |
| 550–649 | Fair | 65% of requested | MCLR + 3.5% | Quarterly audit + collateral enhancement |
| 450–549 | Poor | 40% of requested | MCLR + 5.0% | Monthly reporting + personal guarantee + additional collateral |
| 350–449 | Very Poor | Reject | N/A | Reapply in 12 months |
| < 350 | Default Risk | Permanent Reject | N/A | Regulatory review |

> MCLR as of March 2025: ~8.5%

The score is the **primary output**. Loan amount and interest rate are **derived from the score** — they are never the AI's independent judgment.

#### CAM Writer — Model Tiering

| CAM Section | LLM Model | Why |
|---|---|---|
| Executive Summary | Claude Sonnet | Judges read this first — needs best quality |
| Character | Claude Haiku | Primarily structured data summaries |
| Capacity | Claude Haiku | Number-heavy, formula-driven |
| Capital | Claude Haiku | Balance sheet analysis |
| Collateral | Claude Haiku | Asset data summaries |
| Conditions | Claude Haiku | Industry/regulatory findings |
| Risk Flags | Claude Sonnet | Critical section — complex reasoning needed |
| Decision Rationale | Claude Sonnet | Final reasoning — highest stakes |

Every sentence in the CAM references its evidence:
```
"Revenue has grown at an 18.2% CAGR over FY2022-24
[Annual Report FY2024, Page 43, Table 2],
significantly above the steel sector average of 12%.
This growth has been verified against ITR filings
[ITR FY2024 Schedule BP] confirming the revenue
is reflected in tax declarations."
```

**Output format**: python-docx generates a Word document (industry standard for Indian banking CAMs — editable after generation).

---

## 5. Universal Decision Store

**Every single outcome is stored permanently** — approvals, rejections, fraud detections, borderline cases, escalations, everything.

### Database Schema

#### `assessments` (master record)

| Column | Type | Description |
|---|---|---|
| `session_id` | UUID (PK) | Unique assessment identifier |
| `company_id` | VARCHAR | Company identifier |
| `company_name` | VARCHAR | Full company name |
| `assessment_date` | TIMESTAMP | When assessment was run |
| `requested_amount` | DECIMAL | Loan amount requested |
| `requested_tenure` | INTEGER | Tenure in months |
| `purpose` | TEXT | Loan purpose |
| `final_score` | INTEGER | INTELLI-CREDIT score (0–850) |
| `score_band` | VARCHAR | EXCELLENT/GOOD/FAIR/POOR/VERY_POOR/DEFAULT |
| `outcome_type` | ENUM | APPROVED / CONDITIONAL_APPROVAL / REJECTED / FRAUD_DETECTED / ESCALATED / WITHDRAWN |
| `recommended_amount` | DECIMAL | Derived from score band |
| `recommended_rate` | DECIMAL | MCLR + spread from band |
| `recommended_tenure` | INTEGER | Months |
| `conditions_imposed` | JSONB | Array of conditions |
| `pipeline_duration_sec` | INTEGER | Total processing time |
| `documents_processed` | INTEGER | Count |
| `pages_read` | INTEGER | Total pages OCR'd/parsed |
| `research_findings` | INTEGER | Number of findings |
| `compound_insights` | INTEGER | Number of Agent 2.5 insights |
| `tickets_raised` | INTEGER | Count |
| `tickets_resolved` | INTEGER | Count |
| `cam_document_path` | VARCHAR | Path to generated CAM |
| `score_report_path` | VARCHAR | Path to score report |
| `thinking_log_path` | VARCHAR | Path to thinking log JSON |
| `langsmith_trace_url` | VARCHAR | LangSmith trace link |
| `compliance_flagged` | BOOLEAN | Whether compliance team notified |
| `compliance_reason` | TEXT | Why |
| `knowledge_base_added` | BOOLEAN | Whether entry added to KB |
| `created_by` | VARCHAR | Credit officer name |

#### `score_breakdown` (every point explained)

| Column | Type | Description |
|---|---|---|
| `session_id` | FK → assessments | Links to assessment |
| `module` | ENUM | CAPACITY / CHARACTER / CAPITAL / COLLATERAL / CONDITIONS / COMPOUND |
| `metric_name` | VARCHAR | e.g., "DSCR" |
| `metric_value` | VARCHAR | e.g., "1.38x" |
| `computation_formula` | TEXT | e.g., "EBITDA ₹18,200L / Debt Service ₹12,700L" |
| `source_document` | VARCHAR | e.g., "Annual Report FY2024" |
| `source_page` | INTEGER | Page number |
| `source_excerpt` | TEXT | Exact text quoted |
| `benchmark_context` | TEXT | Industry comparison |
| `score_impact` | INTEGER | +42 or -45 |
| `reasoning` | TEXT | Full paragraph |
| `confidence` | DECIMAL | 0.0–1.0 |
| `human_override` | BOOLEAN | If human changed this |

#### `findings_store` (every research + compound finding)

| Column | Type | Description |
|---|---|---|
| `session_id` | FK → assessments | |
| `finding_type` | ENUM | RESEARCH / COMPOUND / CONTRADICTION / CASCADE / HIDDEN_REL / TEMPORAL / POSITIVE |
| `source` | VARCHAR | "MCA21" / "NJDG" / "Tavily" / "Annual Report" etc. |
| `source_url` | VARCHAR | URL if web source |
| `source_document` | VARCHAR | Document name if internal |
| `source_page` | INTEGER | Page if applicable |
| `raw_content` | TEXT | Exact text/data found |
| `extracted_claim` | TEXT | What was extracted |
| `decision` | ENUM | ACCEPTED / REJECTED / UNCERTAIN / FLAGGED |
| `decision_reason` | TEXT | Why this decision |
| `severity` | ENUM | CRITICAL / HIGH / MEDIUM / LOW / POSITIVE |
| `score_impact` | INTEGER | Points |
| `used_in_cam` | BOOLEAN | Whether referenced in CAM |
| `ticket_id` | FK → tickets | If raised a ticket |

#### `tickets` (every conflict and resolution)

| Column | Type | Description |
|---|---|---|
| `session_id` | FK → assessments | |
| `ticket_type` | ENUM | CONTRADICTION / UNVERIFIED_MATERIAL / LOW_CONFIDENCE / FRAUD_SIGNAL / REGULATORY_CONCERN / RPT_UNDISCLOSED |
| `severity` | ENUM | CRITICAL / HIGH / MEDIUM / LOW |
| `claim_a` | TEXT | Full claim with source |
| `claim_b` | TEXT | Opposing claim (if contradiction) |
| `ai_reasoning` | TEXT | AI's analysis |
| `rag_precedents` | JSONB | Top 3 similar past resolutions |
| `score_if_accepted` | INTEGER | Impact if accepted |
| `score_if_rejected` | INTEGER | Impact if rejected |
| `status` | ENUM | OPEN / RESOLVED / ESCALATED |
| `resolved_by` | VARCHAR | Human resolver name |
| `resolution` | ENUM | ACCEPTED_A / ACCEPTED_B / CUSTOM |
| `resolution_text` | TEXT | Human's reasoning |
| `followup_questions` | TEXT | AI follow-ups asked |
| `followup_answers` | TEXT | Human responses |
| `final_score_applied` | INTEGER | Actual impact applied |
| `knowledge_base_added` | BOOLEAN | Added to RAG KB |

#### `decision_outcomes` (filled AFTER loan matures)

| Column | Type | Description |
|---|---|---|
| `session_id` | FK → assessments | |
| `loan_disbursed` | BOOLEAN | |
| `disbursement_date` | DATE | |
| `final_disbursed_amount` | DECIMAL | Actual amount |
| `actual_rate` | DECIMAL | Actual rate applied |
| `loan_performance` | ENUM | CURRENT / WATCHLIST / NPA / RESTRUCTURED / CLOSED_NORMAL / CLOSED_EARLY |
| `first_default_date` | DATE | If applicable |
| `npa_declared_date` | DATE | If applicable |
| `retrospective_notes` | TEXT | Was AI assessment correct? |
| `risk_flags_validated` | JSONB | Flags that proved correct |
| `risk_flags_false_pos` | JSONB | Flags that were wrong |
| `knowledge_base_impact` | TEXT | Learning feedback |

#### `thinking_events` (complete AI thought log)

| Column | Type | Description |
|---|---|---|
| `session_id` | FK → assessments | |
| `sequence_number` | INTEGER | Order of events |
| `timestamp` | TIMESTAMP | When event occurred |
| `agent_name` | VARCHAR | "Agent 2.5 — Graph Reasoning" |
| `agent_stage` | VARCHAR | "CASCADE_RISK_PASS_2" |
| `event_type` | ENUM | READ / FOUND / COMPUTED / ACCEPTED / REJECTED / FLAGGED / CONNECTING / CONCLUDING / QUESTIONING / DECIDED |
| `document_name` | VARCHAR | Document being processed |
| `page_number` | INTEGER | Page number |
| `content` | TEXT | Full text being processed |
| `extracted` | TEXT | What was pulled |
| `decision` | ENUM | ACCEPTED / REJECTED / FLAGGED |
| `decision_reason` | TEXT | Why |
| `score_impact` | INTEGER | If applicable |
| `confidence` | DECIMAL | 0.0–1.0 |
| `links_to_events` | JSONB | Related event IDs |
| `shown_in_chatbot` | BOOLEAN | Whether pushed to UI |

#### Rejection Event Store

```sql
TABLE: rejection_events
  id, company_id, rejection_type, triggered_at,
  trigger_reasons (JSONB with full evidence),
  full_pipeline_state_snapshot (JSONB),
  rejection_letter_generated (BOOLEAN),
  rejection_letter_path (VARCHAR),
  reapplication_allowed_after (DATE),
  knowledge_base_entry_id (FK)
```

#### Rejection Letter Generation

When the pipeline routes to rejection, a formal rejection letter is auto-generated:

| Attribute | Detail |
|---|---|
| **Generator** | Claude Sonnet + python-docx |
| **Format** | Formal bank letterhead Word document |
| **Contents** | Formal salutation → Reference (loan application number, date, amount) → **Reasons for rejection** (plain English, specific — each reason references supporting evidence but does NOT disclose exact scores or internal metrics) → Reapplication conditions if permitted (what specifically needs to change, by when) → If fraud detected: standard regulatory language only (no internal detail — legal requirement) → Grievance redressal process and contact → Formal closing |
| **Stored at** | `rejection_events.rejection_letter_path` |
| **Also stored in** | Universal Decision Store as assessment output |

#### Fraud Investigation Store

```sql
TABLE: fraud_investigations
  id, company_id, fraud_type, evidence_chain (JSONB),
  neo4j_subgraph_snapshot (JSONB — frozen at time of detection),
  ml_model_scores (JSONB),
  human_verdict (pending initially),
  regulatory_report_required (BOOLEAN — PMLA/FIU-IND)
```

Both stores automatically write a knowledge base entry — every rejection and fraud detection becomes a precedent for future cases.

### How All Stores Connect

```
assessment (session_id: IC-2025-0847)
    │
    ├──▶ score_breakdown (12 score entries)
    │         each with document + page + formula
    │
    ├──▶ findings_store (47 research + 17 compound)
    │         each with source + decision + reason
    │
    ├──▶ tickets (3 tickets)
    │         each with both claims + resolution
    │         → feeds knowledge_base
    │
    ├──▶ thinking_events (847 events logged)
    │         complete AI thought record
    │         shown in live chatbot
    │
    └──▶ decision_outcomes (filled after loan matures)
              validates the assessment retrospectively
```

---

## 6. Live Thinking Chatbot

### What It Is

A persistent chat panel in the UI showing the AI's **complete internal monologue in real time**. Not a summary. Not logs. The actual reasoning — what document the agent is reading, what text it found, what it decided to do with it, and why. Every agent is named. Every document is named. Every decision is shown with its outcome.

### Why It Exists

1. **Transparency**: The credit officer is an active participant who sees exactly what the AI read and thought. If the AI read something wrong, the officer catches it immediately.
2. **Trust**: A black-box AI making lending decisions will never be trusted. A system that narrates its reasoning builds trust naturally.
3. **Demo Impact**: Judges watching the AI think in real time — naming documents, quoting text, explaining decisions — is the most compelling explainability demonstration possible.

### Thinking Event Structure

```python
ThinkingEvent {
    event_id:        UUID
    timestamp:       ISO datetime
    session_id:      "assessment_XYZ_Steel_001"
    agent_name:      "Agent 1.5 — The Organizer"
    agent_stage:     "COMPUTING_METRICS"
    event_type:      READ | FOUND | COMPUTED | ACCEPTED |
                     REJECTED | FLAGGED | DECIDED |
                     QUESTIONING | CONNECTING | CONCLUDING
    document_name:   "Annual Report FY2024.pdf"
    page_number:     43
    content:         "Full text the agent is processing"
    extracted:       "What the agent pulled from this content"
    decision:        ACCEPTED | REJECTED | FLAGGED | UNCERTAIN
    decision_reason: "Why this decision was made"
    score_impact:    +7  # (if applicable)
    confidence:      0.94
    links_to:        [other event IDs this connects to]
}
```

### Event Flow Architecture

```
AGENT (any stage)
  │  agent.emit(ThinkingEvent(...))
  ▼
Redis Pub/Sub Channel: "thinking:{session_id}"
  │
  ▼
WebSocket Server (FastAPI) — subscribed to channel
  │
  ▼
WebSocket Push to all connected UI clients for this session
  │
  ▼
React Live Chatbot Component
  → Appends new message to feed
  → Formats with agent name, icon, color
  → Color-coded decisions:
      ✅ Green = Accepted
      ⚠️ Yellow = Flagged
      🚨 Red = Critical flag
      ❌ Crossed = Rejected
      💬 Blue = AI questioning
  → Auto-scrolls to latest event
  → Full event stored in thinking_events table
```

### Event Type Display

| Event Type | Display |
|---|---|
| `READ` | "Agent 1.5 is reading Annual Report pg 43" |
| `FOUND` | "Found: Revenue ₹124.5cr" |
| `COMPUTED` | "Computed: DSCR = 18200/12700 = 1.43x" |
| `ACCEPTED` ✅ | "Accepted: Revenue figure, confidence 0.97" |
| `REJECTED` ❌ | "Rejected: Blog post, unverifiable source" |
| `FLAGGED` ⚠️ | "Flagged: ITC claimed > ITC available" |
| `CRITICAL` 🚨 | "Critical: 3 undisclosed related parties" |
| `CONNECTING` 🔗 | "Connecting: Greenfield NCLT → revenue loss" |
| `CONCLUDING` 💡 | "Conclusion: DSCR drops to 0.88x in stress" |
| `QUESTIONING` 💬 | "Agent 2.5 asks: Include Priya Shah in circular analysis?" |
| `DECIDED` ✅ | "Score module CAPACITY: +42 pts" |

### Chatbot Filter Panel

```
FILTER BY AGENT:        FILTER BY DECISION:      FILTER BY DOCUMENT:
☑ All Agents            ☑ All                    ☑ All Documents
☐ Workers Only          ☐ Accepted only          ☐ Annual Report only
☐ Agent 0.5             ☐ Flagged only           ☐ Bank Statement only
☐ Agent 1.5             ☐ Critical only          ☐ Board Minutes only
☐ Agent 2               ☐ Rejected only          ☐ GST Returns only
☐ Agent 2.5                                      [etc.]
☐ Evidence Builder
☐ Agent 3

SEARCH: Free-text search within the thinking log
  "Show me everything about Greenfield Energy"
  → Filters to all events mentioning Greenfield
```

---

## 7. INTELLI-CREDIT Score Model

### Score Range: 0 to 850

Modeled after the CIBIL scoring system used in Indian banking.

### Score Bands

| Band | Score Range | Recommendation |
|---|---|---|
| Excellent | 750–850 | Approve full amount, best rate (MCLR+1.5%) |
| Good | 650–749 | Approve 85%, standard rate (MCLR+2.5%) |
| Fair | 550–649 | Approve 65%, higher rate (MCLR+3.5%), conditions |
| Poor | 450–549 | Approve 40%, highest rate (MCLR+5%), strict conditions |
| Very Poor | 350–449 | Reject, reapply in 12 months |
| Default Risk | < 350 | Permanent reject, regulatory review |

### Hard Block Triggers (Override Any Score)

| Trigger | Score Cap |
|---|---|
| Wilful defaulter (RBI list) | Capped at 200 |
| Active criminal case against promoter | Capped at 150 |
| DSCR < 1.0x (cannot service debt) | Capped at 300 |
| NCLT active proceedings (insolvency) | Capped at 250 |

### 5 Scoring Modules

| Module | Max Positive | Max Negative | Key Metrics |
|---|---|---|---|
| **Capacity** | +150 pts | -100 pts | DSCR, revenue growth, working capital cycle, cash flow, repayment history |
| **Character** | +120 pts | -200 pts | Promoter track record, SEBI/RBI history, RPT disclosure, share pledge, management stability, CIBIL commercial score, management credibility score |
| **Capital** | +80 pts | -80 pts | D/E ratio, net worth, existing obligations, equity contributions |
| **Collateral** | +60 pts | -40 pts | Coverage ratio, asset quality, lien status, valuation source |
| **Conditions** | +50 pts | -50 pts | Order book, sector outlook, regulatory environment, PLI/government support |
| **Compound Insights** | +57 pts | -130 pts | Cascade risk, circular trading, temporal deterioration, positive signals |

### CHARACTER Module — Detailed Metrics

#### Management Credibility Score

The management interview is not just a form — the AI computes a **management_credibility_score (0.0–1.0)** that feeds directly into the CHARACTER module:

**Computation:**
- Claims made in interview that **match** documents → +confidence
- Claims made in interview that **contradict** documents → -confidence  
- Claims that cannot be verified either way → neutral

**Example output:**
```
"Management claimed order book ₹280cr → corroborated by BHEL
 announcement and ET article. (+confidence)"
"Management claimed no related party suppliers → directly
 contradicted by MCA21 director overlap. (-confidence)"
"Management claimed no disputes → contradicted by NJDG case. (-confidence)"

Credibility Score: 0.61 / 1.0
```

**Score impact (CHARACTER module):**

| Credibility Score | Impact |
|---|---|
| 0.80–1.0 | +15 pts |
| 0.60–0.79 | +5 pts |
| 0.40–0.59 | -10 pts |
| 0.20–0.39 | -20 pts |
| < 0.20 | -25 pts |

#### CIBIL Commercial Score

When the credit officer provides a CIBIL Commercial score at upload, it feeds into the CHARACTER module:

| CIBIL Score | Impact |
|---|---|
| 800+ | +30 pts |
| 700–799 | +15 pts |
| 600–699 | +5 pts |
| 500–599 | -10 pts |
| < 500 | -30 pts |
| Not provided | 0 pts (confidence reduction flag) |

**When absent:**
> "CIBIL Commercial score was not provided. Assessment confidence on payment history: REDUCED. If CIBIL is provided and shows score >700, score would improve by up to +15 pts."

### Sector Benchmark Data

Every ratio computation in the scoring model references sector-specific industry benchmarks stored in `config/benchmarks/`.

**Source:** RBI DBIE (Database on Indian Economy) + CMIE Prowess

**Steel Sector Benchmarks (example from `config/benchmarks/steel_sector.json`):**

| Metric | Sector Average | Warning | Critical |
|---|---|---|---|
| DSCR | 1.8x | < 1.2x | < 1.0x |
| D/E Ratio | 1.4x | > 2.5x | > 3.5x |
| Working Capital Days | 65 days | > 90 days | > 120 days |
| Revenue CAGR (3yr) | 12% | < 5% | < 0% |
| Gross Margin | 16–18% | < 12% | < 8% |
| Current Ratio | 1.4x | < 1.1x | < 0.8x |

**Usage:**
- Used in every per-point score reasoning paragraph: *"This DSCR of 1.38x is below the sector average of 1.8x"*
- Updated quarterly from public RBI data
- Sector auto-detected from Annual Report or manually selected at upload
- Benchmark files: `steel_sector.json`, `manufacturing.json`, `services.json`

### Per-Point Breakdown Structure

Every single point in the score includes:

```
Metric:       DSCR
Value:        1.38x
Formula:      EBITDA ₹18,200L / Debt Service ₹12,700L
Source:       Annual Report FY2024, Page 67
Excerpt:      "EBITDA for the year was ₹18,200 lakhs"
Benchmark:    Industry average DSCR: 1.2-1.5x
Impact:       +42 points
Reasoning:    "DSCR of 1.38x falls within the acceptable
              range for the steel sector. While above the
              minimum threshold of 1.2x, the declining
              trend from 2.1x (FY22) to 1.38x (FY24) at
              a rate of -0.34x per year suggests capacity
              erosion. Projected FY25 DSCR: 1.04x which
              approaches the hard block threshold..."
```

---

## 8. ML Anomaly Detection Suite

Three pre-trained open-source models run in parallel during Agent 1.5:

### DOMINANT GNN (Graph Neural Network)

| Attribute | Detail |
|---|---|
| **Library** | PyTorch Geometric |
| **Purpose** | Circular trading and shell company detection |
| **Input** | Neo4j entity-relationship graph (company → suppliers/customers/directors → their other companies) |
| **What it detects** | Unusually dense clusters of entities connected through shared directors, same registered addresses, synchronized incorporation dates, round-number transactions between related entities |
| **Output** | Fraud probability score per community cluster (0–1). Score > 0.7 = investigate. Score > 0.85 = high confidence fraud signal. |
| **Pre-trained on** | Financial transaction graphs. Fine-tuned on SEBI enforcement order descriptions for Indian market patterns. |

### Isolation Forest (Tabular Anomaly Detection)

| Attribute | Detail |
|---|---|
| **Library** | scikit-learn |
| **Purpose** | Detecting statistically anomalous financial ratios |
| **Input** | Computed metrics: DSCR, D/E ratio, working capital cycle, revenue growth, GST-Bank divergence, ITC overclaim ratio, debtor days, creditor days |
| **How it works** | Learns the distribution of "normal" financial data. Identifies data points that don't fit. No labeled training data needed — unsupervised. |
| **Output** | Anomaly score per metric (0–1). Higher = more anomalous. Identifies which specific metrics are outliers. |
| **Why Isolation Forest** | Specifically designed for anomaly detection. Outperforms one-class SVM and DBSCAN on tabular financial data in benchmarks. |

### FinBERT (Financial Text Analysis)

| Attribute | Detail |
|---|---|
| **Library** | HuggingFace (ProsusAI/finbert) |
| **Purpose** | Detecting hidden risk signals in management narrative |
| **Input** | Director's Report, MD&A section, management commentary — any narrative text |
| **What it detects** | Buried risk behind positive language. Understands that "notwithstanding temporary headwinds" is a negative signal even though individual words are neutral. |
| **Output** | Surface sentiment score + buried risk score. When surface is positive (0.7+) but buried risk is high (0.8+), management is actively masking problems. |
| **Pre-trained on** | Financial news, earnings calls, and financial reports — domain matches exactly. |

---

## 9. Research Intelligence Stack

### API Comparison & Selection

| API | Role | Strength | Cost |
|---|---|---|---|
| **Tavily** | Primary web search | AI-native, clean output, domain filtering, LangChain native | $$ |
| **Exa** | Neural semantic search | Finds conceptually related content beyond keywords | $$ |
| **SerpAPI** | Google wrapper | Deepest Indian news index (ET, BS, Mint, FE, MC) | $$ |

### Custom Indian Scrapers

| Scraper | Source | Tech | Hard Block? |
|---|---|---|---|
| **MCA21** | Ministry of Corporate Affairs | BeautifulSoup + Selenium | No (intelligence) |
| **NJDG** | National Judicial Data Grid | BeautifulSoup + Selenium | No (flag) |
| **SEBI** | Securities Exchange Board | BeautifulSoup | No (flag) |
| **RBI Defaulter** | Reserve Bank of India | BeautifulSoup | **YES** |
| **GSTIN** | GST Portal | API call | No (fabrication check) |

### Research Caching

**Redis** with 7-day TTL per research query:
- Same company researched again → all cached results served instantly
- Cross-company sector research cached — two steel companies assessed same week share sector data
- Reduces API costs and latency significantly

---

## 10. Storage Architecture

### Four Database Systems

| Database | Type | Purpose | Why This Choice |
|---|---|---|---|
| **ChromaDB** | Vector DB | Semantic search over document chunks + RAG knowledge base | Open source, local, native LangChain integration, metadata filtering, persistence layer |
| **Neo4j Community Edition** | Graph DB | Knowledge graph — entity relationships, director networks, supplier chains | Purpose-built for graph, Cypher language, best Python driver, GraphRAG integration |
| **Elasticsearch 8** | Search Engine | Full-text + NER-tagged entity search across 4 indices | Best Python client, REST API, NLP pipeline, better than Solr for ML features |
| **PostgreSQL 15** | Relational DB | All structured data — assessments, scores, insights, tickets, outcomes, knowledge base | ACID compliance, strict schema enforcement, well-defined schemas that don't change |

### Elasticsearch 4 Indices

| Index | Purpose | Contents |
|---|---|---|
| `document_store` | All extracted text from documents | Full text chunks with metadata (doc type, page, extraction confidence) |
| `research_intelligence` | Web research results | Articles, court records, government portal findings with source tier |
| `company_profiles` | Historical assessment data | Past CAMs, peer companies, sector benchmarks for comparison |
| `regulatory_watchlist` | Regulatory updates | RBI circulars, SEBI regulations, MCA notifications, GST council decisions, PLI updates |

### Embedding Model

**sentence-transformers/all-MiniLM-L6-v2** (SBERT):
- 384-dimensional vectors
- Runs on CPU in ~20ms per sentence
- ~12 seconds for 600 chunks
- Local — zero API calls, zero cost, zero latency
- Specifically benchmarked for semantic similarity and retrieval tasks

### Hybrid Search (Reciprocal Rank Fusion)

```
Query → ChromaDB (semantic/vector) + Elasticsearch (keyword/NER) + Neo4j (graph traversal)
  → Reciprocal Rank Fusion combines results → ranked result set
```

### NER Pipeline

**spaCy** for standard entities (dates, amounts, organizations). **GLiNER** for zero-shot entity recognition — recognizes Indian court names, regulatory body names, Indian company name patterns without fine-tuning.

---

## 11. Complete Technology Stack

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| React | 18 | UI framework — component model for multi-panel interface |
| TailwindCSS | 3 | Rapid professional styling without writing CSS |
| WebSocket client | Native | Real-time bidirectional communication for chatbot |
| React Query | 5 | Server state management, caching, background refetching |
| Recharts | 2 | Score visualization charts and graphs |

### API Layer

| Technology | Version | Purpose |
|---|---|---|
| FastAPI | 0.110 | Async API server — native async, WebSocket, auto-OpenAPI docs |
| Pydantic v2 | 2.5 | Data validation at every boundary — 5-50x faster than v1 (Rust core) |
| WebSockets | FastAPI native | Real-time thinking event push to UI |
| JWT | python-jose | Stateless authentication |
| Redis | 7 | Task queue broker + research cache + staging area |

### Task Processing

| Technology | Version | Purpose |
|---|---|---|
| Celery | 5 | Parallel document workers — routing, retry, exponential backoff, prioritization |
| Flower | 2 | Real-time worker monitoring dashboard — shows all 8 workers running |
| Redis | 7 | Celery message broker |

### Orchestration

| Technology | Version | Purpose |
|---|---|---|
| LangGraph | 0.2 | Agent state machine — CreditAppraisalState flows through all nodes, conditional edges, human-in-the-loop |
| LangChain | 0.3 | Agent framework — loaders, chains, RAG, tool use, automatic LangSmith integration |
| LangSmith | Latest | Complete observability — every LLM call, agent decision, tool use traced automatically |

### Document Parsing

| Technology | Version | Purpose |
|---|---|---|
| Unstructured.io | 0.12 | Complex PDF layout parsing — spatial understanding for multi-column Indian annual reports |
| Tesseract OCR | 5.3 | Scanned document OCR — local, free, page-level parallelism |
| Camelot | 0.11 | PDF table extraction — financial tables, bank statements |
| PyMuPDF | 1.24 | Fast PDF text extraction for simple documents |
| Pandas | 2 | Excel/CSV parsing, time-series bank statement analysis |
| OpenPyXL | 3.1 | Excel formula support |

### ML Models

| Technology | Version | Purpose |
|---|---|---|
| DOMINANT GNN | PyTorch Geometric 2.4 | Graph neural network for circular trading / shell company detection |
| Isolation Forest | scikit-learn | Unsupervised tabular anomaly detection on financial ratios |
| FinBERT | HuggingFace (ProsusAI/finbert) | Financial text risk analysis — buried risk behind positive language |
| PyTorch Geometric | 2.4 | GNN operations framework |

### NLP

| Technology | Version | Purpose |
|---|---|---|
| spaCy | 3.7 | Standard Named Entity Recognition |
| GLiNER | 0.2 | Zero-shot NER for Indian entity types (no fine-tuning needed) |
| sentence-transformers | 2.7 | Local embedding generation |
| all-MiniLM-L6-v2 | SBERT | Embedding model — 384-dim, CPU, ~20ms/sentence |

### Storage

| Technology | Version | Purpose |
|---|---|---|
| ChromaDB | 0.5 | Vector search — semantic RAG retrieval + knowledge base |
| Neo4j Community Edition | 5.14 | Knowledge graph — entity relationships, director networks |
| Elasticsearch | 8.12 | Full-text + NER search — 4 indices |
| PostgreSQL | 15 | All structured data — assessments, scores, tickets, outcomes |
| Redis | 7 | Cache (7-day TTL) + staging area + Pub/Sub event bus |

### Graph Intelligence

| Technology | Version | Purpose |
|---|---|---|
| Neo4j Python driver | 5 | Async graph reads/writes |
| Microsoft GraphRAG | 0.3 | Hierarchical graph summarization for multi-hop LLM reasoning |
| NetworkX | 3 | Community detection (Louvain method for cluster finding) |

### Research APIs

| Technology | Version | Purpose |
|---|---|---|
| Tavily API | v2 | AI-native web search with domain filtering |
| Exa API | v1 | Neural semantic web search |
| SerpAPI | v3 | Google wrapper for Indian news coverage |
| BeautifulSoup | 4.12 | HTML parsing for custom scrapers |
| Selenium | 4.18 | Dynamic JavaScript page scraping for government portals |

### LLM

| Technology | Version | Purpose |
|---|---|---|
| Claude Haiku | 3.5 | Bulk extraction, classification, structured data analysis (80% of LLM calls) |
| Claude Sonnet | 4 | CAM writing, complex reasoning, executive summary (20% of LLM calls — critical sections) |

### Thinking Event Bus

| Technology | Version | Purpose |
|---|---|---|
| Redis Pub/Sub | 7 | Event publishing from all agents to WebSocket server |
| asyncio | Python 3.12 | Async event handling |
| WebSocket server | FastAPI native | Real-time push from server to UI |

### Output Generation

| Technology | Version | Purpose |
|---|---|---|
| python-docx | 1.1 | CAM Word document (Indian banking standard — editable) |
| ReportLab | 4 | Score report PDF generation |
| Jinja2 | 3.1 | Report templating |

### Infrastructure

| Technology | Version | Purpose |
|---|---|---|
| Docker Compose | v2 | One-command deployment — all 8+ services in containers |
| Nginx | 1.25 | Reverse proxy |

---

## 12. UI Components, Pages & Dashboard

### Page Architecture

The frontend is a single-page React application with the following views:

---

### Page 1: Upload Portal

**Purpose**: Document upload + initial data entry

| Component | Detail |
|---|---|
| **Drag-and-Drop Zone** | Supports PDF, Excel, CSV, XML. Multi-file upload. Accepts all 8 document types simultaneously. |
| **Document Type Selector** | Dropdown per uploaded file to tag: Annual Report, Bank Statement, GST Returns, ITR, Legal Notice, Board Minutes, Shareholding Pattern, Rating Report |
| **Company Information Form** | Company Name, CIN, GSTIN, Sector dropdown, Requested Loan Amount (₹), Requested Tenure (months), Purpose |
| **CIBIL Input Field** | Optional — CIBIL commercial score + key CIBIL data points. When provided, integrated into scoring. When absent, noted with confidence reduction. |
| **Databricks Connection** | Mock connector field. Reads from local files with same interface. Easy swap to real Databricks. |
| **Submit Button** | Triggers Celery tasks and starts LangGraph pipeline |
| **Upload Progress** | Per-file upload progress bars |

---

### Page 2: Live Processing Dashboard

**Purpose**: Real-time visibility into the entire pipeline

#### Component: Progress Tracker (Top Bar)

A horizontal pipeline visualization showing all 9 stages:

```
[Workers] → [Agent 0.5] → [Validator] → [Agent 1.5] → [Agent 2] → [Agent 2.5] → [Evidence] → [Tickets] → [Agent 3]
   🟢          ⚪           ⚪            ⚪           ⚪          ⚪           ⚪          ⚪         ⚪
```

- 🟢 Green = currently processing
- ✅ Checkmark = completed
- ⚪ Gray = not started
- 🔴 Red = error/blocked
- ⏸️ Paused = waiting for human input

Each stage shows elapsed time and percentage completion.

#### Component: Worker Status Panel (Left Side)

Shows all 8 parallel workers with individual status:

```
W1: Annual Report     ████████████░░░ 78%  12.3s
W2: Bank Statement    ████████████████ 100% ✅ 8.1s
W3: GST Returns       ████████░░░░░░░ 52%  ...
W4: ITR               ████████████████ 100% ✅ 11.4s
W5: Legal Notice      ████░░░░░░░░░░░ 25%  ...
W6: Board Minutes     ████████████░░░ 80%  ...
W7: Shareholding      ████████████████ 100% ✅ 9.2s
W8: Rating Report     ██████████░░░░░ 65%  ...
```

#### Component: Live Thinking Chatbot (Center — Main Panel)

The primary real-time feed showing AI reasoning. Full specification in [Section 6](#6-live-thinking-chatbot).

Displays:
- Agent name + stage for every message
- Document name + page number being read
- Exact text being processed
- Extraction results
- Decision with color-coded status
- Score impact when applicable
- Timestamps

Includes filter panel: by agent, by decision type, by document, free-text search.

#### Component: Running Statistics (Right Side)

Live-updating counters:
```
Documents Processed:  6 / 8
Pages Read:          623 / ~847
Findings:            34
Flags Raised:        7
Contradictions:      2
Score Preview:       ~520 (updating...)
Elapsed Time:        2m 14s
```

---

### Page 3: Management Interview Form

**Purpose**: Structured input form for management interview responses

#### Form Structure (Matching 5 Cs)

| Section | Questions |
|---|---|
| **Character** | Promoter background narrative, previous ventures, exit history, vision statement |
| **Capacity** | Revenue growth drivers, customer concentration plans, WC management strategy |
| **Capital** | Capital infusion plans, D/E reduction timeline, equity commitment |
| **Collateral** | Additional collateral available, asset maintenance schedule |
| **Conditions** | Industry outlook (own view), competitive advantages, regulatory preparedness |

Each answer field supports:
- Free-text input
- File attachment (supporting documents)
- "AI will verify this against documentary evidence" notice

**AI Credibility Scoring**: After Agent 2 completes, management claims are cross-referenced against documentary evidence and research findings. Discrepancies are flagged and shown in the chatbot.

---

### Page 4: Ticket Resolution Interface

**Purpose**: Human-AI dialogue for resolving conflicts and uncertainties

#### Layout

**Left Panel: Ticket Queue**
```
🚨 TICKET #IC-2025-0847-A (HIGH)
   RPT Concealment — 3 undisclosed related parties
   
⚠️ TICKET #IC-2025-0847-B (MEDIUM)
   Post-report litigation from key customer
   
🚨 TICKET #IC-2025-0847-C (HIGH)
   Revenue figure — which source to use?
```

**Center Panel: Active Ticket Detail**
- Full problem description
- Evidence for Claim A with document + page + exact text
- Evidence for Claim B with document + page + exact text
- AI reasoning paragraph
- RAG precedents: 3 most similar past resolutions with outcomes
- Score impact visualization (if accepted vs rejected)

**Right Panel: Resolution Controls**
- Accept Claim A (button)
- Accept Claim B (button)
- Escalate to Senior Manager (button)
- Need More Information (button + text field)
- Custom Response (free text)

**Bottom Panel: AI Dialogue**
After human selects a resolution, AI responds with follow-up questions:
```
AI: "You accepted this as post-report filing. Should I also
     update the working capital calculation to reflect the
     disputed receivable of ₹14.2cr?"
Human: [Yes/No + optional text]
AI: "Updated. DSCR sensitivity analysis now includes
     receivable-adjusted scenario."
```

---

### Page 5: Score Report & CAM Viewer

**Purpose**: Final output display + document download

#### Component: Score Dashboard

**Score Gauge**: Large circular visualization showing 477/850 with color band.

**Module Breakdown Table**:

| Module | Score Impact | Key Driver |
|---|---|---|
| Capacity | +42 | DSCR 1.38x, WC deterioration |
| Character | -80 | RPT concealment, 72% pledge |
| Capital | -5 | D/E 2.10x |
| Collateral | +35 | Coverage 1.7x |
| Conditions | +15 | Order book ₹280cr |
| Compound | -130 | Cascade risk, shell network |
| **TOTAL** | **477** | |

**Per-Point Drill-Down**: Click any module → expands to show every metric with value, formula, source document + page, benchmark, score impact, and reasoning paragraph.

**Recommendation Panel**:
```
INTELLI-CREDIT SCORE: 477 / 850
BAND: POOR
RECOMMENDATION: CONDITIONAL APPROVAL
  Loan: ₹20cr (40% of ₹50cr requested)
  Rate: 13.5% (MCLR + 5%)
  Tenure: 48 months
  Conditions:
    • Monthly financial reporting
    • Personal guarantee from promoter
    • Complete collateral over factory land
    • Compliance review of RPT issue first
```

#### Component: CAM Viewer

- Full CAM document preview (rendered from generated .docx)
- Section navigation sidebar (Executive Summary, Character, Capacity, Capital, Collateral, Conditions, Risk Flags, Decision Rationale)
- Citation highlighting: hover over any claim → highlights source document + page
- **Download buttons**: CAM (Word), Score Report (PDF), Thinking Log (JSON), Full Evidence Package (ZIP)

#### Component: LangSmith Trace Link

Direct link to the LangSmith dashboard showing the complete trace of every LLM call, agent decision, and tool use for this assessment. Judges can click through every AI decision.

---

### Page 6: Decision Store Viewer

**Purpose**: Historical view of ALL assessments — approvals, rejections, fraud, borderline

#### Component: Assessment List

| Column | Filter | Sort |
|---|---|---|
| Date | Date range picker | ↑↓ |
| Company | Search | A-Z |
| Score | Range slider | ↑↓ |
| Band | Dropdown | - |
| Outcome | Multi-select (Approved, Conditional, Rejected, Fraud, Escalated) | - |
| Compliance Flag | Yes/No | - |

#### Component: Assessment Detail (click-through)

Full assessment record including:
- Score with complete breakdown
- All findings (accepted + rejected + uncertain)
- All tickets with resolutions
- Thinking log (replayable)
- CAM download
- Outcome (if loan has matured)
- Retrospective validation (which flags proved correct/false positive)

#### Component: Analytics Dashboard

- Score distribution histogram across all assessments
- Outcome pie chart (approved / conditional / rejected / fraud)
- Average pipeline duration trend
- Most common flag types bar chart
- Sector-wise approval rate
- Knowledge base growth curve

---

### Page 7: Officer Notes Panel

**Purpose**: Free-form note-taking by credit officer during assessment review. Available as a persistent side panel on every page.

| Feature | Detail |
|---|---|
| Note creation | Free text field + auto-timestamp + author from JWT |
| Note context | Each note records which page/section it was made from |
| Note attachment | Can reference specific thinking event, finding, or ticket |
| Note categories | Observation / Concern / Follow-up / Override Justification |
| Persistence | Stored with assessment in PostgreSQL (`assessments` table) |
| Search | Full-text search across all notes |
| CAM integration | Notes are visible alongside the CAM in the final output, tagged as "Credit Officer Observations" section |
| Scope boundary | Notes are clearly labeled as **human annotation, NOT AI data** — they are NOT input into the scoring model |

**Use case:** Officer observed something during a site visit not captured in the structured form, or has contextual knowledge about the promoter from prior interactions. These observations travel with the assessment but remain clearly separated from the AI's analysis.

---

### Page 8: Analytics Dashboard

**Purpose**: Aggregate analytics across all assessments processed by Intelli-Credit

| Visualization | Detail |
|---|---|
| **Score by Sector** | Bar chart — average INTELLI-CREDIT Score by sector (Steel, Manufacturing, Services, etc.) |
| **Outcome Trends** | Line chart — Approval / Rejection / Fraud rate over time |
| **Top Score Deductions** | Ranked bar chart — most common score deductions (which risks appear most often across assessments) |
| **Top Ticket Types** | Ranked list — most common ticket categories raised (Revenue Discrepancy, ITC Mismatch, RPT Concealment, etc.) |
| **Pipeline Duration** | Bar chart — average pipeline processing time by document count |
| **Score Distribution** | Histogram — distribution of scores across all assessments |
| **Fraud Signals** | Ranked table — top fraud signals detected, ranked by frequency |
| **Knowledge Base Growth** | Line chart — resolved ticket precedents added to ChromaDB over time |
| **Officer Performance** | Table — tickets resolved per officer, average resolution time |
| **NPA Correlation** | Scatter plot — which risk flags most accurately predicted actual NPAs (populated when `decision_outcomes` data is available) |

---

### Page 9: Flower Worker Monitor (Embedded)

**Purpose**: Technical monitoring of Celery workers

| Feature | Detail |
|---|---|
| Active tasks | All running workers with status |
| Task queue | Pending tasks by priority |
| Worker stats | CPU, memory, task completion rate |
| Task history | Completed tasks with duration |
| Retry tracking | Failed + retried tasks |

Embedded as an iframe or linked dashboard. Shows all 8 document workers running in parallel — visually impressive for demos.

---

## 13. Latency Optimization

Total pipeline time reduced from estimated 22+ minutes to under 4 minutes:

| Bottleneck | Solution | Before | After |
|---|---|---|---|
| Sequential document processing | **8 parallel Celery workers** | ~8 min | ~45 sec |
| Full-document OCR | **Page-level OCR parallelism** (Tesseract) | ~3 min | ~30 sec |
| Sequential LLM calls | **Model tiering** (Haiku bulk + Sonnet critical) + **request batching** | ~30 min | ~3 min |
| Remote embedding API calls | **Local embeddings** (all-MiniLM-L6-v2 on CPU) | ~5 min | ~12 sec |
| Sequential research queries | **Async parallel searches** (5 tracks) + **Redis cache** (7-day TTL) | ~50 sec | ~4 sec |
| Synchronous Neo4j graph writes | **Async Neo4j driver** — writes happen in background | ~2 min | ~0 sec (non-blocking) |
| User waiting for full completion | **WebSocket streaming** — partial results visible immediately | ~22 min perceived | Perceived 5x faster |

### Additional Optimizations

- **Research caching**: Same company researched within 7 days → all cached. Same sector researched → sector data shared.
- **Chunking strategy**: Documents chunked at 500 tokens with 50-token overlap for optimal RAG retrieval.
- **Embedding batching**: All chunks embedded in one batch call to local model.
- **LLM request grouping**: Multiple extractions batched where context window allows.
- **Streaming CAM generation**: Sections stream to UI as they're generated (see streaming order below).

### Streaming CAM Generation Order

The CAM streams to the UI section-by-section so the credit officer can begin reading before the full document is complete:

| Order | Section | Model | Streams at |
|---|---|---|---|
| 1st | Executive Summary | Sonnet | ~2:30 into assessment |
| 2nd–6th | 5 Cs sections (Character, Capacity, Capital, Collateral, Conditions) | Haiku (parallel) | ~3:00 |
| 7th–8th | Risk Flags + Decision Rationale | Sonnet | ~3:45 |

**User experience:**
- At **2:30** → Executive Summary readable
- At **3:00** → All 5 Cs sections complete
- At **3:45** → Risk Flags and Decision Rationale complete
- **Total perceived wait before useful content: ~2.5 minutes** (vs ~4 minutes if waiting for entire CAM)

---

## 14. Project Structure

```
intelli-credit/
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadPortal.jsx              # Drag-drop upload + company info form
│   │   │   ├── ProgressTracker.jsx           # Pipeline stage visualization
│   │   │   ├── WorkerStatusPanel.jsx         # 8 parallel worker status
│   │   │   ├── LiveThinkingChatbot.jsx       # Real-time AI reasoning feed
│   │   │   ├── ChatbotFilterPanel.jsx        # Agent / decision / document filters
│   │   │   ├── TicketResolutionInterface.jsx # Human-AI dialogue for conflicts
│   │   │   ├── ManagementInterviewForm.jsx   # Structured 5 Cs interview
│   │   │   ├── ScoreDashboard.jsx            # Score gauge + module breakdown
│   │   │   ├── ScoreDetailDrilldown.jsx      # Per-point breakdown view
│   │   │   ├── CAMViewer.jsx                 # CAM preview + citation highlighting
│   │   │   ├── DecisionStoreViewer.jsx       # Historical assessment browser
│   │   │   ├── AnalyticsDashboard.jsx        # Charts + statistics
│   │   │   ├── OfficerNotesPanel.jsx         # Free-form notes
│   │   │   └── FlowerEmbed.jsx               # Celery worker monitor
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js               # WebSocket connection manager
│   │   │   ├── useThinkingEvents.js          # Thinking event stream handler
│   │   │   └── useAssessment.js              # Assessment state manager
│   │   ├── pages/
│   │   │   ├── UploadPage.jsx                # Upload portal page
│   │   │   ├── ProcessingPage.jsx            # Live processing dashboard
│   │   │   ├── InterviewPage.jsx             # Management interview form
│   │   │   ├── TicketPage.jsx                # Ticket resolution page
│   │   │   ├── ResultsPage.jsx               # Score + CAM output page
│   │   │   ├── HistoryPage.jsx               # Decision store viewer
│   │   │   └── AnalyticsPage.jsx             # Analytics dashboard
│   │   ├── App.jsx
│   │   └── index.jsx
│   ├── package.json
│   └── tailwind.config.js
│
├── backend/
│   ├── api/
│   │   ├── main.py                           # FastAPI app + WebSocket endpoints
│   │   ├── routes/
│   │   │   ├── upload.py                     # Document upload endpoints
│   │   │   ├── assessment.py                 # Assessment CRUD endpoints
│   │   │   ├── tickets.py                    # Ticket resolution endpoints
│   │   │   ├── decisions.py                  # Decision store endpoints
│   │   │   └── interview.py                  # Management interview endpoints
│   │   ├── websocket/
│   │   │   ├── thinking_ws.py                # Thinking event WebSocket handler
│   │   │   └── progress_ws.py                # Pipeline progress WebSocket
│   │   ├── auth/
│   │   │   └── jwt_handler.py                # JWT authentication
│   │   └── middleware/
│   │       └── rate_limiter.py               # Rate limiting
│   │
│   ├── graph/
│   │   ├── state.py                          # CreditAppraisalState (Pydantic v2)
│   │   ├── orchestrator.py                   # LangGraph state machine definition
│   │   └── nodes/
│   │       ├── workers_node.py               # Celery task dispatcher
│   │       ├── consolidator_node.py          # Agent 0.5
│   │       ├── validator_node.py             # Validator
│   │       ├── organizer_node.py             # Agent 1.5
│   │       ├── research_node.py              # Agent 2
│   │       ├── reasoning_node.py             # Agent 2.5
│   │       ├── evidence_node.py              # Evidence Package Builder
│   │       ├── ticket_node.py                # Ticketing Layer
│   │       ├── recommendation_node.py        # Agent 3
│   │       └── decision_store_node.py        # Universal Decision Store writer
│   │
│   ├── agents/
│   │   ├── ingestor/
│   │   │   ├── loaders.py                    # Document loaders (Unstructured, Camelot, etc.)
│   │   │   ├── ocr.py                        # Tesseract OCR with page-level parallelism
│   │   │   ├── extractor.py                  # Data extraction chains (LangChain)
│   │   │   └── cross_verifier.py             # Cross-document verification
│   │   ├── workers/
│   │   │   ├── annual_report_worker.py       # Worker 1
│   │   │   ├── bank_statement_worker.py      # Worker 2
│   │   │   ├── gst_returns_worker.py         # Worker 3
│   │   │   ├── itr_worker.py                 # Worker 4
│   │   │   ├── legal_notice_worker.py        # Worker 5
│   │   │   ├── board_minutes_worker.py       # Worker 6
│   │   │   ├── shareholding_worker.py        # Worker 7
│   │   │   ├── rating_report_worker.py       # Worker 8
│   │   │   └── site_visit_worker.py          # Worker 9 — Factory/site visit notes
│   │   ├── consolidator/
│   │   │   ├── merger.py                     # Schema normalization + conflict detection
│   │   │   ├── contradiction_detector.py     # Cross-document contradictions
│   │   │   └── completeness_checker.py       # Mandatory/important/optional validation
│   │   ├── organizer/
│   │   │   ├── five_cs_mapper.py             # Map data to Character/Capacity/Capital/Collateral/Conditions
│   │   │   ├── metric_computer.py            # DSCR, current ratio, D/E, WC cycle, CAGR, divergences
│   │   │   ├── board_analyzer.py             # Board minutes deep analysis
│   │   │   ├── shareholding_analyzer.py      # Pledge ratio, holding trends, cross-holdings
│   │   │   ├── graph_builder.py              # Internal Neo4j graph construction
│   │   │   └── ml_suite.py                   # DOMINANT GNN + Isolation Forest + FinBERT runner
│   │   ├── research/
│   │   │   ├── tavily_search.py              # Tavily API integration
│   │   │   ├── exa_search.py                 # Exa neural search integration
│   │   │   ├── serpapi_search.py             # SerpAPI Google wrapper
│   │   │   ├── scrapers/
│   │   │   │   ├── mca21_scraper.py          # Ministry of Corporate Affairs
│   │   │   │   ├── njdg_scraper.py           # National Judicial Data Grid
│   │   │   │   ├── sebi_scraper.py           # SEBI enforcement orders
│   │   │   │   ├── rbi_defaulter_scraper.py  # RBI wilful defaulter list
│   │   │   │   └── gstin_verifier.py         # GST portal verification
│   │   │   ├── verification_engine.py        # 5-tier verification, relevance, cross-check
│   │   │   └── neo4j_enricher.py             # External entity graph enrichment
│   │   ├── reasoning/
│   │   │   ├── contradiction_pass.py         # Pass 1: Contradiction detection
│   │   │   ├── cascade_pass.py               # Pass 2: Cascade risk detection
│   │   │   ├── hidden_relationship_pass.py   # Pass 3: Hidden relationship detection
│   │   │   ├── temporal_pass.py              # Pass 4: Temporal pattern analysis
│   │   │   ├── positive_signal_pass.py       # Pass 5: Positive signal amplification
│   │   │   └── insight_store.py              # Insight Store writer
│   │   ├── recommendation/
│   │   │   ├── scorer.py                     # INTELLI-CREDIT 0-850 scoring engine
│   │   │   ├── score_modules/
│   │   │   │   ├── capacity_module.py        # Capacity scoring (+150/-100)
│   │   │   │   ├── character_module.py       # Character scoring (+120/-200)
│   │   │   │   ├── capital_module.py         # Capital scoring (+80/-80)
│   │   │   │   ├── collateral_module.py      # Collateral scoring (+60/-40)
│   │   │   │   ├── conditions_module.py      # Conditions scoring (+50/-50)
│   │   │   │   └── compound_module.py        # Compound insights scoring (+57/-130)
│   │   │   ├── hard_blocks.py                # Wilful defaulter, criminal case, DSCR<1.0, NCLT
│   │   │   ├── rag_chain.py                  # RAG retrieval for CAM context
│   │   │   └── cam_writer.py                 # Section-by-section CAM generation
│   │   └── evidence/
│   │       ├── package_builder.py            # Evidence Package Builder
│   │       └── ticket_raiser.py              # Ticket generation logic
│   │
│   ├── storage/
│   │   ├── chromadb_client.py                # ChromaDB vector store operations
│   │   ├── neo4j_client.py                   # Neo4j async driver operations
│   │   ├── elasticsearch_client.py           # ES 4-index operations
│   │   ├── postgres_client.py                # PostgreSQL all-table operations
│   │   └── redis_client.py                   # Redis cache + staging + Pub/Sub
│   │
│   ├── models/
│   │   ├── schemas.py                        # All Pydantic v2 models (50+ schemas)
│   │   ├── thinking_event.py                 # ThinkingEvent model
│   │   ├── evidence_package.py               # EvidencePackage model
│   │   ├── feature_object.py                 # FeatureObject model
│   │   └── ticket.py                         # Ticket model
│   │
│   ├── ml/
│   │   ├── dominant_gnn.py                   # DOMINANT GNN model wrapper
│   │   ├── isolation_forest.py               # Isolation Forest model wrapper
│   │   ├── finbert.py                        # FinBERT model wrapper
│   │   └── embeddings.py                     # Local embedding model (MiniLM)
│   │
│   ├── thinking/
│   │   ├── event_emitter.py                  # ThinkingEvent emission helper
│   │   ├── redis_publisher.py                # Redis Pub/Sub publisher
│   │   └── event_formatter.py                # Human-readable event formatting
│   │
│   └── workers/
│       └── celery_app.py                     # Celery configuration + task definitions
│
├── data/
│   ├── samples/                              # Sample documents for testing
│   └── knowledge_base/                       # Initial knowledge base seed data
│
├── config/
│   ├── settings.py                           # Application configuration
│   ├── prompts/                              # All LLM prompt templates
│   │   ├── extraction_prompts.py             # Document extraction prompts
│   │   ├── reasoning_prompts.py              # Graph reasoning prompts
│   │   ├── cam_prompts.py                    # CAM section generation prompts
│   │   └── dialogue_prompts.py               # Ticket AI dialogue prompts
│   └── benchmarks/                           # Industry benchmark data
│       ├── steel_sector.json
│       ├── manufacturing.json
│       └── services.json
│
├── tests/
│   ├── test_workers/
│   ├── test_agents/
│   ├── test_scoring/
│   └── test_integration/
│
├── docker-compose.yml                        # One-command full stack
├── Dockerfile.api                            # FastAPI container
├── Dockerfile.worker                         # Celery worker container
├── Dockerfile.frontend                       # React frontend container
├── nginx.conf                                # Reverse proxy configuration
├── requirements.txt                          # Python dependencies
├── .env.example                              # Environment variables template
└── README.md                                 # This file
```

---

## 15. Infrastructure & Deployment

### Docker Compose Services

```yaml
services:
  # Application Services
  api:            FastAPI server (port 8000)
  worker:         Celery worker (8 concurrent tasks)
  frontend:       React app (port 3000)
  
  # Data Services
  redis:          Redis 7 (port 6379) — broker + cache + pub/sub
  postgres:       PostgreSQL 15 (port 5432) — all structured data
  elasticsearch:  Elasticsearch 8 (port 9200) — 4 indices
  neo4j:          Neo4j 5.14 (port 7474/7687) — knowledge graph
  chromadb:       ChromaDB (port 8100) — vector search
  
  # Monitoring
  flower:         Celery Flower (port 5555) — worker monitor
  nginx:          Nginx 1.25 (port 80) — reverse proxy
```

### Single Command Deployment

```bash
docker-compose up -d
```

Spins up all 10 services. Works on any machine. Demo-ready in one command.

### Environment Variables

```env
# LLM
ANTHROPIC_API_KEY=sk-...

# Research APIs
TAVILY_API_KEY=tvly-...
EXA_API_KEY=exa-...
SERPAPI_API_KEY=...

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=intelli-credit

# Database
POSTGRES_URL=postgresql://...
NEO4J_URI=bolt://localhost:7687
ELASTICSEARCH_URL=http://localhost:9200
CHROMADB_HOST=localhost
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256
```

---

## 16. Key Features Summary

### Unique Differentiators

| Feature | Description |
|---|---|
| **Live Thinking Chatbot** | Real-time AI reasoning visible to credit officer — every document, page, extraction, decision narrated |
| **0–850 Credit Score** | CIBIL-modeled score with per-point source-traced breakdown — not just approve/reject |
| **Director Network Shell Detection** | MCA21 scraper + DOMINANT GNN finds undisclosed related parties and circular trading |
| **GSTR-2A vs 3B Reconciliation** | Catches fake invoice fraud through ITC overclaim detection |
| **Board Minutes Governance Extraction** | RPT approval cross-referencing catches active concealment |
| **Cascade Risk Modeling** | Multi-hop graph traversal computes downstream DSCR impact of counterparty failure |
| **5-Tier Research Verification** | Every research finding classified by source credibility before scoring |
| **Human-AI Ticket Dialogue** | Not just approve/reject — conversational resolution with follow-up questions |
| **RAG-Based Institutional Learning** | Resolved tickets become precedents. Outcomes validate signals over time. |
| **Universal Decision Store** | ALL outcomes stored (approvals, rejections, fraud) — nothing lost |
| **FinBERT Buried Risk Detection** | Detects management masking problems behind positive language |
| **72.4% Pledge Detection** | Shareholding pattern analysis catches promoter financial stress |
| **Evidence Package Architecture** | Agent 3 never reasons — it only writes from perfectly organized, pre-scored evidence |
| **3-Way Revenue Validation** | AR revenue vs ITR income vs GST turnover vs Bank inflows — catches inflation |
| **Compliance Auto-Flagging** | Undisclosed RPTs, SEBI violations, RBI defaulter status trigger compliance review |
| **Outcome-Validated Learning** | When loans mature, which AI flags proved correct is tracked — strengthens future assessments |

### Processing Pipeline At Scale

| Metric | Value |
|---|---|
| Documents processed simultaneously | 8 |
| Total pipeline time | < 4 minutes |
| Parallel research tracks | 5 (Tavily + Exa + SerpAPI + Custom Scrapers + Regulatory) |
| Graph reasoning passes | 5 |
| ML models running | 3 (DOMINANT GNN + Isolation Forest + FinBERT) |
| Databases | 4 (ChromaDB + Neo4j + Elasticsearch + PostgreSQL) |
| Research cache TTL | 7 days |
| Score range | 0–850 |
| Hard block triggers | 4 (Wilful defaulter, Criminal case, DSCR<1.0, NCLT) |
| Scoring modules | 5 + compound insights |
| CAM sections | 8 (Executive Summary, Character, Capacity, Capital, Collateral, Conditions, Risk Flags, Decision Rationale) |

---

## 17. Implementation Tier List — Feature Roadmap

> **Strategy:** All backend tiers (T3–T8) are completed first. Frontend integration (T9) happens last — wiring each backend feature to its React component one-by-one. This prevents context-switching between Python and JS, keeps the API contract clean, and ensures every frontend component has a fully-tested backend to connect to.

### Completion Status

| Tier | Name | Features | Tests | Status |
|------|------|----------|-------|--------|
| T0 | Foundations | 8/8 | ~80 | ✅ COMPLETE |
| T1 | Advanced Features | 8/8 | ~120 | ✅ COMPLETE |
| T2 | Scoring & Output | 5/5 | ~124 | ✅ COMPLETE |
| T3 | Demo Pipeline | 8 | ~110 | 🔴 IN PROGRESS |
| T4 | ML Intelligence | 8 | ~80 | ⬜ PLANNED |
| T5 | External Research | 8 | ~72 | ⬜ PLANNED |
| T6 | Storage & RAG | 8 | ~74 | ⬜ PLANNED |
| T7 | LLM Integration | 8 | ~56 | ⬜ PLANNED |
| T8 | Production Hardening | 8 | ~50 | ⬜ PLANNED |
| T9 | Frontend Integration | 12 | ~90 | ⬜ PLANNED (LAST) |

---

### 🔴 T3 — Demo Pipeline (Make Backend Run End-to-End)

> **Goal:** A complete backend pipeline that can ingest documents, process through all agents, score, and produce a CAM — testable via API calls alone.

| ID | Feature | Description | Tests |
|----|---------|-------------|-------|
| T3.1 | Workers W4–W8 | ITR Worker, Legal Notice Worker, Board Minutes Worker, Shareholding Worker, Rating Report Worker — each with structured mock extraction matching Pydantic schemas | ~25 |
| T3.2 | Pipeline Trigger | Wire `POST /api/upload` → Celery task dispatch → `run_pipeline()` with real state flow through all LangGraph nodes | ~15 |
| T3.3 | Decision Store Node | `decision_store_node.py` — persist final assessment to PostgreSQL (in-memory fallback), store score breakdown, CAM, and outcome | ~12 |
| T3.4 | Sector Benchmarks | JSON benchmark files for 5 sectors (Steel, Textiles, Pharma, IT Services, FMCG) with DSCR, D/E, ICR, revenue growth thresholds | ~10 |
| T3.5 | Research Node (Basic) | Replace stub `research_node.py` with structured mock research: MCA21, SEBI, RBI defaulter list, NJDG, news sentiment — all with source tiers and confidence scores | ~18 |
| T3.6 | CAM Download Endpoint | `GET /api/cam/{session_id}/download` — generate Word doc (python-docx) from CAM data, return as file stream | ~10 |
| T3.7 | Environment Config | `.env.example` with all required env vars, `config/settings.py` with Pydantic BaseSettings, env-driven configuration | ~8 |
| T3.8 | Docker Compose | `docker-compose.yml` with 10 services (API, worker, Redis, PostgreSQL, Neo4j, ES, ChromaDB, Flower, Nginx, frontend), health checks, volume mounts | ~12 |

---

### 🟡 T4 — ML Intelligence (Real Anomaly Detection)

> **Goal:** Three ML models running locally — Isolation Forest for tabular anomalies, FinBERT for buried financial risk in text, DOMINANT GNN for circular trading in graphs.

| ID | Feature | Description | Tests |
|----|---------|-------------|-------|
| T4.1 | Isolation Forest | scikit-learn Isolation Forest on bank statement + financial metrics — detect round-number transactions, irregular patterns, outlier EMI amounts | ~12 |
| T4.2 | FinBERT Sentiment | ProsusAI/finbert on Annual Report MD&A, auditor qualifications, board minutes risk discussions — flag buried negative language | ~10 |
| T4.3 | DOMINANT GNN | PyTorch Geometric DOMINANT model on Neo4j subgraph — detect circular trading patterns between supplier/customer/company nodes | ~15 |
| T4.4 | ML Pipeline Wrapper | Unified `MLAnalysisPipeline` class that runs all 3 models in parallel, combines results into `MLSignals` Pydantic model | ~8 |
| T4.5 | Anomaly Scoring Integration | Wire ML signals into Compound scoring module — circular trading penalty (-80), buried risk penalty (-25), tabular anomaly penalty (-30) | ~10 |
| T4.6 | ML Model Registry | Load models once at startup, store in app state, health check endpoints for each model | ~8 |
| T4.7 | Training Data Generator | Synthetic training data generator for Isolation Forest (normal + anomalous bank patterns) and GNN (normal + circular graphs) | ~8 |
| T4.8 | ML Confidence Calibration | Confidence scores for each ML prediction, threshold tuning, ensemble agreement scoring | ~9 |

---

### 🟢 T5 — External Research (Real-World Verification)

> **Goal:** 5 Indian government portal scrapers + 3 search APIs producing verified intelligence with source credibility tiers.

| ID | Feature | Description | Tests |
|----|---------|-------------|-------|
| T5.1 | MCA21 Scraper | Company master data, director DIN lookup, charge status, filing history — Selenium + BeautifulSoup with retry/timeout/fallback | ~10 |
| T5.2 | SEBI Scraper | Enforcement actions, debarred entities, insider trading orders — structured extraction with case matching | ~8 |
| T5.3 | RBI Defaulter Scraper | Wilful defaulter list, fraud accounts, NBFC alerts — PDF table extraction from RBI circulars | ~8 |
| T5.4 | NJDG Scraper | National Judicial Data Grid — pending cases, disposed cases, case type classification (civil/criminal/NCLT) | ~8 |
| T5.5 | GST Portal Scraper | GSTIN verification, return filing status, annual aggregate turnover validation | ~8 |
| T5.6 | Tavily + Exa Integration | AI-native web search (Tavily) + neural semantic search (Exa) for news, analysis, and sector intelligence | ~10 |
| T5.7 | Source Credibility Engine | 5-tier verification: Government (1.0) → Financial media (0.85) → General news (0.60) → Regional (0.30) → Social (0.0) with automatic tier classification | ~10 |
| T5.8 | Research Cache Layer | Redis-backed cache (7-day TTL) for scraper results, search results with key namespacing and invalidation | ~10 |

---

### 🔵 T6 — Storage & RAG (Intelligence Layer)

> **Goal:** All 4 databases operational — ChromaDB for vector search, Neo4j for graph intelligence, Elasticsearch for full-text, PostgreSQL for structured records.

| ID | Feature | Description | Tests |
|----|---------|-------------|-------|
| T6.1 | ChromaDB Client | Document chunk storage, semantic similarity search, knowledge base CRUD, resolved ticket precedent storage | ~10 |
| T6.2 | Elasticsearch Client | 4 indices (document_store, research_intelligence, company_profiles, regulatory_watchlist), bulk indexing, hybrid search | ~10 |
| T6.3 | PostgreSQL Client | SQLAlchemy 2.0 async, 8 tables (assessments, score_breakdown, findings_store, tickets, decision_outcomes, thinking_events, rejection_events, fraud_investigations), migrations | ~12 |
| T6.4 | Neo4j Client Enhancement | Async driver, bulk node/relationship creation, Cypher query builder, community detection (Louvain via NetworkX) | ~10 |
| T6.5 | Document Ingestor | Unstructured.io + Tesseract OCR + Camelot + PyMuPDF — parallel page processing, chunk extraction, metadata tagging | ~10 |
| T6.6 | RAG Pipeline | ChromaDB vector search → context assembly → LLM prompt → cited answer — with source tracing back to document + page | ~8 |
| T6.7 | Embedding Service | sentence-transformers (all-MiniLM-L6-v2), batch embedding, 384-dim vectors, CPU-optimized, ~20ms/sentence | ~8 |
| T6.8 | Knowledge Base Seeder | Seed ChromaDB with RBI guidelines, SEBI regulations, Indian banking standards, sector benchmarks for RAG context | ~6 |

---

### 🟣 T7 — LLM Integration (Claude Calls)

> **Goal:** Real Claude API calls replacing mock extractions — Haiku for 80% bulk work, Sonnet for 20% reasoning/writing.

| ID | Feature | Description | Tests |
|----|---------|-------------|-------|
| T7.1 | LLM Client Wrapper | Anthropic SDK wrapper with retry, fallback (Haiku ↔ Sonnet), token tracking, cost estimation, LangSmith tracing | ~8 |
| T7.2 | Extraction Chains | LangChain chains for each document type — structured output parsing with Pydantic models, confidence scoring | ~10 |
| T7.3 | Prompt Template System | All prompts in `config/prompts/` as Jinja2 templates — extraction, classification, reasoning, CAM writing, executive summary | ~6 |
| T7.4 | CAM Writer (LLM) | Claude Sonnet-powered CAM generation — executive summary, risk narrative, decision rationale with citation insertion | ~8 |
| T7.5 | Reasoning Chains | Multi-step reasoning for cross-verification, contradiction resolution, evidence synthesis — chain-of-thought with tracing | ~8 |
| T7.6 | Classification Agent | Document type auto-classification, entity extraction, sentiment analysis — all via Haiku for speed | ~6 |
| T7.7 | LLM Cost Monitor | Per-session token tracking, cost breakdown by model tier, budget alerts, usage analytics | ~5 |
| T7.8 | Fallback Strategy | Haiku timeout → retry → Sonnet fallback → cached response → graceful degradation with ThinkingEvent emission | ~5 |

---

### ⚪ T8 — Production Hardening

> **Goal:** Security, monitoring, observability, and deployment readiness.

| ID | Feature | Description | Tests |
|----|---------|-------------|-------|
| T8.1 | JWT Authentication | python-jose JWT auth, login/register endpoints, token refresh, role-based access (officer, senior, admin) | ~8 |
| T8.2 | Rate Limiting | Redis-backed rate limiter — per-user, per-endpoint, configurable limits, 429 responses | ~6 |
| T8.3 | WebSocket Authentication | JWT-authenticated WebSocket connections, session validation, connection cleanup on disconnect | ~6 |
| T8.4 | Structured Logging | JSON logging with component tags, correlation IDs, log levels, ELK-compatible format | ~5 |
| T8.5 | Health Check Suite | `/health` endpoint checking all 5 services (Redis, PostgreSQL, Neo4j, ES, ChromaDB), readiness vs liveness probes | ~8 |
| T8.6 | Error Recovery | Global exception handler, circuit breakers for external services, graceful shutdown, worker drain | ~6 |
| T8.7 | PII Protection | Mask sensitive data in logs, encrypt PII at rest, secure file upload handling, input sanitization | ~6 |
| T8.8 | CI/CD Pipeline | GitHub Actions — lint, type check, test, build Docker images, deploy staging | ~5 |

---

### 🟠 T9 — Frontend Integration (LAST — After All Backend Tiers)

> **Strategy:** Every React component was built with mock data fallback (T0–T2). Now wire each component to its real backend API one-by-one. Each integration is a single PR with its own tests.

| ID | Feature | Backend Dependency | Frontend Component | Tests |
|----|---------|-------------------|-------------------|-------|
| T9.1 | Upload Integration | T3.2 (Pipeline Trigger) | `UploadPortal.jsx` — wire drag-drop to `POST /api/upload`, show real upload progress | ~8 |
| T9.2 | Worker Status Live | T3.2 (Pipeline Trigger) | `WorkerStatusPanel.jsx` — WebSocket subscription to worker progress events | ~6 |
| T9.3 | Thinking Chatbot Live | T3.2 + All Agents | `LiveThinkingChatbot.jsx` — WebSocket subscription to Redis Pub/Sub thinking events, color-coded, filterable | ~10 |
| T9.4 | Progress Tracker Live | T3.2 (Pipeline State) | `ProgressTracker.jsx` — real pipeline stage progression via WebSocket | ~6 |
| T9.5 | Score Dashboard Live | T2.4 (Score API) | `ScoreDashboard.jsx` — fetch real score from `GET /api/score/{id}`, render gauge + breakdown | ~8 |
| T9.6 | Score Drilldown Live | T2.4 (Score API) | `ScoreDetailDrilldown.jsx` — per-point evidence with source document links | ~6 |
| T9.7 | CAM Viewer Live | T3.6 (CAM Download) | `CAMViewer.jsx` — render real CAM with citation highlighting, download button | ~8 |
| T9.8 | Ticket Resolution Live | T1.7 (Tickets API) | `TicketResolutionInterface.jsx` — real ticket queue, resolve/escalate actions | ~8 |
| T9.9 | Decision Store Live | T2.5 (Decisions API) | `DecisionStoreViewer.jsx` — paginated history, filters, officer notes | ~8 |
| T9.10 | Interview Form Live | T3.2 (Pipeline) | `ManagementInterviewForm.jsx` — submit interview → inject into pipeline state | ~6 |
| T9.11 | Analytics Live | All Backend | `AnalyticsDashboard.jsx` — real metrics from `GET /api/analytics/*` | ~8 |
| T9.12 | Flower Embed | Docker (Flower) | `FlowerEmbed.jsx` — embed Flower monitoring dashboard via iframe | ~4 |

---

### Hackathon Cutline

```
┌─────────────────────────────────────────────────────────────┐
│  MUST SHIP (Functional Demo):  T3 + T9 (partial: T9.1-T9.5)│
│  STRONG ENTRY:                 + T4 (ML) + T9.6-T9.9       │
│  WINNING ENTRY:                + T5 (Research) + T7 (LLM)  │
│  PRODUCTION READY:             + T6 + T8 + T9.10-T9.12     │
└─────────────────────────────────────────────────────────────┘
```

**Total Estimated:** ~850+ tests across all tiers, ~60+ Python files, ~15 React components wired.

---

## License

This project is built for the Intelli-Credit Hackathon Challenge.

---

> **Built with**: LangGraph + LangChain + Claude (Haiku + Sonnet) + FastAPI + React + Neo4j + Elasticsearch + ChromaDB + PostgreSQL + Redis + Celery + DOMINANT GNN + Isolation Forest + FinBERT + Tesseract + Unstructured.io + Tavily + Exa + SerpAPI + Docker Compose
