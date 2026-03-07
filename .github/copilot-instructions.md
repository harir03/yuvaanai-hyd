# Intelli-Credit — Copilot Instructions

> **Read this file BEFORE and AFTER every task.** These are non-negotiable rules for working on Intelli-Credit.

---

## 1. Project Identity

**Intelli-Credit** is an AI-Powered Credit Decisioning Engine (Hackathon — Credit Appraisal / FinTech Track).

It ingests 8 corporate loan document types in parallel, cross-verifies revenue across 4 sources, detects fraud through graph intelligence and ML anomaly models, scores borrowers on a 0–850 scale with per-point tracing, generates a fully cited Credit Appraisal Memo, and shows the credit officer its complete reasoning in real time via a Live Thinking Chatbot.

### Architecture Layers

| Layer | Purpose |
|---|---|
| **Data Ingestor** | 9 parallel Celery workers → Agent 0.5 Consolidator → Validator → Agent 1.5 Organizer |
| **Research Agent** | Tavily + Exa + SerpAPI + 5 Indian govt scrapers → Verification Engine → Agent 2.5 Graph Reasoning (5 passes) |
| **Recommendation Engine** | Evidence Package Builder → Ticketing Layer → Agent 3 (Score 0–850 + CAM Writer) |
| **Intelligence Layer** | ChromaDB (vectors) + Neo4j (graph) + Elasticsearch (full-text) + PostgreSQL (structured) |
| **Thinking Event Bus** | Redis Pub/Sub → WebSocket → Live Chatbot (real-time AI reasoning feed) |
| **Presentation Layer** | React 18 + TailwindCSS 3 — Upload Portal, Processing Dashboard, Ticket Resolution, Score Report, CAM Viewer, Decision Store |

### Orchestration

**LangGraph** state machine with `CreditAppraisalState` (Pydantic v2) flowing through all nodes. Conditional edges handle: Normal path, Auto-reject (hard blocks), Deep fraud (ML signal), Human review (borderline 550–650). **LangChain** powers agents within each node — document loaders, chains, RAG, tools, LangSmith tracing.

---

## 2. Tech Stack — Locked Versions (DO NOT CHANGE)

### Frontend

| Package | Version | Purpose |
|---|---|---|
| React | 18 | UI framework |
| TailwindCSS | 3 | Utility-first styling |
| WebSocket client | Native | Real-time thinking event feed |
| React Query | 5 | Server state management, caching |
| Recharts | 2 | Score visualization, charts |

### Backend — API Layer

| Package | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Primary language |
| FastAPI | 0.110 | Async API + WebSocket + auto-OpenAPI |
| Pydantic | v2 (2.5+) | Data validation at every boundary (Rust core) |
| Celery | 5 | Parallel document workers with routing + retry |
| Flower | 2 | Real-time Celery worker monitoring |
| Redis | 7 | Task broker + cache + staging + Pub/Sub |
| python-jose | latest | JWT authentication |

### Orchestration & Agent Framework

| Package | Version | Purpose |
|---|---|---|
| LangGraph | 0.2 | Agent state machine, conditional edges, HITL |
| LangChain | 0.3 | Loaders, chains, RAG, tools, LangSmith |
| LangSmith | latest | Full observability — every LLM call traced |

### Document Parsing

| Package | Version | Purpose |
|---|---|---|
| Unstructured.io | 0.12 | Complex PDF spatial layout parsing |
| Tesseract OCR | 5.3 | Scanned pages — local, free, page-parallel |
| Camelot | 0.11 | PDF table extraction |
| PyMuPDF | 1.24 | Fast PDF text extraction (simple docs) |
| Pandas | 2 | Excel/CSV, time-series analysis |
| OpenPyXL | 3.1 | Excel formula support |

### ML Models

| Package | Version | Purpose |
|---|---|---|
| PyTorch Geometric | 2.4 | DOMINANT GNN — circular trading detection |
| scikit-learn | latest | Isolation Forest — tabular anomaly detection |
| HuggingFace (ProsusAI/finbert) | latest | FinBERT — financial text buried risk |

### NLP & Embeddings

| Package | Version | Purpose |
|---|---|---|
| spaCy | 3.7 | Standard NER |
| GLiNER | 0.2 | Zero-shot NER for Indian entities |
| sentence-transformers | 2.7 | Local embedding generation |
| all-MiniLM-L6-v2 | SBERT | 384-dim embeddings, CPU, ~20ms/sentence |

### Storage

| Package | Version | Purpose |
|---|---|---|
| ChromaDB | 0.5 | Vector search — semantic RAG + knowledge base |
| Neo4j CE | 5.14 | Knowledge graph — entities, directors, suppliers |
| Elasticsearch | 8.12 | Full-text + NER — 4 indices |
| PostgreSQL | 15 | Structured — assessments, scores, tickets, outcomes |
| Redis | 7 | Cache (7-day TTL) + staging + Pub/Sub bus |

### Graph Intelligence

| Package | Version | Purpose |
|---|---|---|
| Neo4j Python driver | 5 | Async graph operations |
| Microsoft GraphRAG | 0.3 | Hierarchical graph summarization |
| NetworkX | 3 | Community detection (Louvain) |

### Research APIs

| Package | Version | Purpose |
|---|---|---|
| Tavily API | v2 | AI-native web search |
| Exa API | v1 | Neural semantic search |
| SerpAPI | v3 | Google wrapper — Indian news index |
| BeautifulSoup | 4.12 | HTML parsing for scrapers |
| Selenium | 4.18 | Dynamic JS page scraping (govt portals) |

### LLM

| Model | Purpose |
|---|---|
| Claude Haiku 3.5 | Bulk extraction, classification (80% of calls) |
| Claude Sonnet 4 | CAM writing, complex reasoning, exec summary (20%) |

### Output Generation

| Package | Version | Purpose |
|---|---|---|
| python-docx | 1.1 | CAM Word document (Indian banking standard) |
| ReportLab | 4 | Score report PDF |
| Jinja2 | 3.1 | Report templating |

### Infrastructure

| Package | Version | Purpose |
|---|---|---|
| Docker Compose | v2 | One-command deployment — all 10 services |
| Nginx | 1.25 | Reverse proxy |

**MANDATORY:** Never upgrade, downgrade, or swap any package version unless explicitly asked by the user. If a version conflict exists, report it — do not silently resolve it.

---

## 3. Project Structure Map

```
intelli-credit/
├── .github/
│   └── copilot-instructions.md       ← THIS FILE — read before every task
├── README.md                          ← Comprehensive project spec (1980 lines)
├── intellicredit.md                   ← PPT/video script reference
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadPortal.jsx              # Drag-drop upload + company info form
│   │   │   ├── ProgressTracker.jsx           # Pipeline 9-stage visualization
│   │   │   ├── WorkerStatusPanel.jsx         # 8 parallel worker status bars
│   │   │   ├── LiveThinkingChatbot.jsx       # Real-time AI reasoning feed
│   │   │   ├── ChatbotFilterPanel.jsx        # Agent/decision/document filters
│   │   │   ├── TicketResolutionInterface.jsx # Human-AI dialogue for conflicts
│   │   │   ├── ManagementInterviewForm.jsx   # Structured 5 Cs interview
│   │   │   ├── ScoreDashboard.jsx            # Score gauge + module breakdown
│   │   │   ├── ScoreDetailDrilldown.jsx      # Per-point breakdown
│   │   │   ├── CAMViewer.jsx                 # CAM preview + citation highlighting
│   │   │   ├── DecisionStoreViewer.jsx       # Historical assessment browser
│   │   │   ├── AnalyticsDashboard.jsx        # Charts + statistics
│   │   │   ├── OfficerNotesPanel.jsx         # Free-form notes
│   │   │   └── FlowerEmbed.jsx               # Celery worker monitor embed
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js               # WebSocket connection manager
│   │   │   ├── useThinkingEvents.js          # Thinking event stream handler
│   │   │   └── useAssessment.js              # Assessment state manager
│   │   ├── pages/
│   │   │   ├── UploadPage.jsx                # Upload portal
│   │   │   ├── ProcessingPage.jsx            # Live processing dashboard
│   │   │   ├── InterviewPage.jsx             # Management interview
│   │   │   ├── TicketPage.jsx                # Ticket resolution
│   │   │   ├── ResultsPage.jsx               # Score + CAM output
│   │   │   ├── HistoryPage.jsx               # Decision store viewer
│   │   │   └── AnalyticsPage.jsx             # Analytics dashboard
│   │   ├── lib/
│   │   │   ├── utils.js                      # Class merge, formatters
│   │   │   └── mockData.js                   # Typed mock data for all components
│   │   ├── App.jsx
│   │   └── index.jsx
│   ├── public/
│   ├── package.json
│   └── tailwind.config.js
│
├── backend/
│   ├── api/
│   │   ├── main.py                           # FastAPI + WebSocket endpoints
│   │   ├── routes/                           # upload, assessment, tickets, decisions, interview
│   │   ├── websocket/                        # thinking_ws, progress_ws
│   │   ├── auth/                             # jwt_handler
│   │   └── middleware/                        # rate_limiter
│   │
│   ├── graph/
│   │   ├── state.py                          # CreditAppraisalState (Pydantic v2)
│   │   ├── orchestrator.py                   # LangGraph state machine
│   │   └── nodes/                            # One node per pipeline stage (10 nodes)
│   │
│   ├── agents/
│   │   ├── ingestor/                         # loaders, ocr, extractor, cross_verifier
│   │   ├── workers/                          # 8 document workers (1 per type)
│   │   ├── consolidator/                     # Agent 0.5: merger, contradiction, completeness
│   │   ├── organizer/                        # Agent 1.5: 5Cs, metrics, graph, ML suite
│   │   ├── research/                         # Agent 2: tavily, exa, serpapi, 5 scrapers, verifier
│   │   ├── reasoning/                        # Agent 2.5: 5 graph reasoning passes
│   │   ├── recommendation/                   # Agent 3: scorer, 6 modules, hard_blocks, cam_writer
│   │   └── evidence/                         # Evidence Package Builder + ticket_raiser
│   │
│   ├── storage/                              # Client wrappers: chromadb, neo4j, es, postgres, redis
│   ├── models/                               # Pydantic v2 schemas (50+ models)
│   ├── ml/                                   # dominant_gnn, isolation_forest, finbert, embeddings
│   ├── thinking/                             # event_emitter, redis_publisher, event_formatter
│   └── workers/                              # celery_app + task definitions
│
├── config/
│   ├── settings.py                           # App config
│   ├── prompts/                              # All LLM prompt templates
│   └── benchmarks/                           # Sector benchmark JSON files
│
├── data/
│   ├── samples/                              # Sample documents for testing
│   └── knowledge_base/                       # Seed KB data
│
├── tests/
│   ├── test_workers/
│   ├── test_agents/
│   ├── test_scoring/
│   └── test_integration/
│
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
├── Dockerfile.frontend
├── nginx.conf
├── requirements.txt
└── .env.example
```

---

## 4. Workflow Orchestration

### 4.1 Plan Mode (Default for Non-Trivial Work)

- Enter plan mode for ANY task with 3+ steps or architectural decisions.
- Write a plan to `tasks/todo.md` (or use the todo tracking tool) BEFORE coding.
- If something goes sideways, **STOP and re-plan immediately** — do not keep pushing broken changes.
- Use plan mode for verification steps, not just building.

### 4.2 Task Management

1. **Plan First:** Write a plan with checkable items before starting implementation.
2. **Verify Plan:** Double-check the plan makes sense before writing code.
3. **Track Progress:** Mark items complete as each step finishes.
4. **Explain Changes:** Provide a high-level summary at each step.
5. **Document Results:** Add a review section when the task is done.

### 4.3 Subagent Strategy

- Use subagents liberally to keep the main context window clean.
- Offload research, file exploration, and parallel analysis to subagents.
- One task per subagent for focused execution.

### 4.4 Verification Before Done

- **Never mark a task complete without proving it works.**
- Backend: run type checks, ensure imports resolve, verify FastAPI starts.
- Frontend: verify dev server compiles, no blank screens, no console errors.
- Ask: "Would a staff engineer approve this?"
- For UI work: confirm the component renders without blank screens.
- For backend work: confirm the endpoint responds correctly.

### 4.5 Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: reconsider. Implement the clean solution.
- But don't over-engineer simple things — simplicity wins.

---

## 5. Code Conventions — Frontend (React 18 + TailwindCSS 3)

### 5.1 File & Naming Rules

| Entity | Convention | Example |
|---|---|---|
| Components | PascalCase, named export | `export function ScoreDashboard() {}` |
| Component files | PascalCase | `ScoreDashboard.jsx`, `LiveThinkingChatbot.jsx` |
| Hook files | camelCase, `use` prefix | `useWebSocket.js`, `useThinkingEvents.js` |
| Utility files | camelCase | `utils.js`, `mockData.js` |
| Page files | PascalCase | `ProcessingPage.jsx`, `ResultsPage.jsx` |
| Interfaces/types | If using TypeScript later: PascalCase | `AssessmentRecord`, `ThinkingEvent`, `ScoreBreakdown` |

### 5.2 Import Ordering

```jsx
// 1. React
import { useState, useEffect, useMemo } from "react";

// 2. Third-party libraries
import { motion } from "framer-motion";
import { LineChart, Line } from "recharts";

// 3. Internal hooks
import { useWebSocket } from "../hooks/useWebSocket";
import { useThinkingEvents } from "../hooks/useThinkingEvents";

// 4. Internal components
import { WorkerStatusPanel } from "../components/WorkerStatusPanel";

// 5. Internal data / utilities
import { mockAssessment } from "../lib/mockData";
import { cn, formatScore } from "../lib/utils";
```

### 5.3 Component Patterns

**WebSocket-Connected Components (Chatbot, Worker Status):**
```jsx
// Must handle: connection, reconnection, message parsing, disconnect
const { messages, isConnected, reconnect } = useWebSocket(sessionId);
// Always show connection status indicator
// Always handle reconnection with exponential backoff
```

**Mock Data Pattern (Hackathon — backend may not be ready):**
```jsx
// Every component must work with mock data when backend is unavailable
const data = apiData ?? mockData;
// This is a REQUIREMENT — demo must work offline
```

### 5.4 Styling Rules

| Token | Usage |
|---|---|
| Card | `bg-white rounded-xl border border-slate-100 p-4 shadow-sm` |
| Page bg | `bg-slate-50` |
| Primary | `teal-600` (brand, active states, primary actions) |
| Warning | `amber-500/600` (flags, warnings) |
| Danger | `red-500` (critical alerts, rejections) |
| Success | `emerald-600` / `green-*` (accepted, approved) |
| Text primary | `text-slate-800` |
| Text secondary | `text-slate-500` |

**Thinking Event Color Coding (CRITICAL — matches architecture):**
```
✅ ACCEPTED   → green
⚠️ FLAGGED    → amber/yellow
🚨 CRITICAL   → red
❌ REJECTED   → red with strikethrough
💬 QUESTIONING → blue
🔗 CONNECTING → purple/indigo
💡 CONCLUDING → teal
📄 READ       → gray/slate
```

---

## 6. Code Conventions — Backend (Python 3.12 + FastAPI)

### 6.1 File & Naming Rules

| Entity | Convention | Example |
|---|---|---|
| Modules | snake_case | `cross_verifier.py`, `cascade_pass.py` |
| Classes | PascalCase | `CreditAppraisalState`, `EvidencePackage` |
| Functions | snake_case | `compute_dscr()`, `detect_circular_trading()` |
| Constants | UPPER_SNAKE | `HARD_BLOCK_WILFUL_DEFAULTER = 200` |
| Pydantic models | PascalCase | `AnnualReportExtraction`, `ThinkingEvent` |
| Env vars | UPPER_SNAKE | `ANTHROPIC_API_KEY`, `NEO4J_URI` |

### 6.2 Agent Node Pattern (LangGraph)

Every LangGraph node MUST follow this pattern:
```python
async def consolidator_node(state: CreditAppraisalState) -> CreditAppraisalState:
    """Agent 0.5 — The Consolidator.
    
    Waits for all workers, normalizes schemas, detects conflicts,
    cross-verifies revenue, builds RawDataPackage.
    """
    emitter = ThinkingEventEmitter(state.session_id, "Agent 0.5 — The Consolidator")
    
    try:
        # 1. Emit what we're doing
        await emitter.emit(EventType.READ, "Collecting all worker outputs...")
        
        # 2. Do the work
        raw_data = await merge_worker_outputs(state)
        
        # 3. Emit what we found
        await emitter.emit(EventType.FOUND, f"Revenue: AR ₹{ar_rev}cr, GST ₹{gst_rev}cr, ITR ₹{itr_rev}cr")
        
        # 4. Update state and return
        state.raw_data_package = raw_data
        return state
        
    except Exception as e:
        await emitter.emit(EventType.CRITICAL, f"Consolidation failed: {str(e)}")
        raise
```

**Key rules:**
- Every node receives and returns `CreditAppraisalState`.
- Every node emits `ThinkingEvent`s for the Live Chatbot.
- Every node has try/except — no silent failures.
- Every node is async.
- NEVER put business logic in the orchestrator — it goes in the node.

### 6.3 Pydantic v2 Schema Rules

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class ScoreModule(str, Enum):
    CAPACITY = "CAPACITY"
    CHARACTER = "CHARACTER"
    CAPITAL = "CAPITAL"
    COLLATERAL = "COLLATERAL"
    CONDITIONS = "CONDITIONS"
    COMPOUND = "COMPOUND"

class ScoreBreakdownEntry(BaseModel):
    """Every single point in the 0-850 score."""
    module: ScoreModule
    metric_name: str = Field(..., description="e.g., 'DSCR'")
    metric_value: str = Field(..., description="e.g., '1.38x'")
    computation_formula: str
    source_document: str
    source_page: int
    source_excerpt: str
    benchmark_context: str
    score_impact: int = Field(..., ge=-200, le=150)
    reasoning: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    human_override: bool = False
```

- Use `Field(...)` with descriptions for every non-obvious field.
- Use Enums for finite sets (score modules, event types, ticket severities).
- Use `model_config = ConfigDict(strict=True)` for critical schemas.
- NEVER use `dict` or `Any` where a proper model exists.

### 6.4 ThinkingEvent Emission (MANDATORY for every agent)

Every agent must emit thinking events. This is the #1 demo feature.

```python
# Available event types (always use these exact types):
class EventType(str, Enum):
    READ = "READ"             # Reading a document/page
    FOUND = "FOUND"           # Found a data point
    COMPUTED = "COMPUTED"     # Computed a derived metric
    ACCEPTED = "ACCEPTED"     # Accepted a finding
    REJECTED = "REJECTED"     # Rejected a finding with reason
    FLAGGED = "FLAGGED"       # Flagged for review
    CRITICAL = "CRITICAL"     # Critical finding
    CONNECTING = "CONNECTING" # Graph reasoning — connecting dots
    CONCLUDING = "CONCLUDING" # Drawing a conclusion
    QUESTIONING = "QUESTIONING" # AI is uncertain, may raise ticket
    DECIDED = "DECIDED"       # Final decision on a score module
```

**Rule: Every significant operation MUST have a ThinkingEvent.** If it doesn't show in the chatbot, it didn't happen for the credit officer. Better to over-emit than under-emit.

### 6.5 Cross-Verification Rules

These are architecturally critical — never skip them:

| Cross-Check | Documents | What to Compare |
|---|---|---|
| Revenue 4-way | AR + ITR + GST + Bank | Same revenue figure, 4 sources |
| RPT concealment | Board Minutes + AR | RPT count and amounts |
| Litigation disclosure | AR + NJDG scraper | Disclosed vs actual |
| Net worth | AR + ITR balance sheet | Should match |
| GSTR-2A vs 3B | GST Returns (W3) | ITC claimed vs ITC available |

**Priority Rule (hardcoded — never change):**
```
Government source (GST, ITR, SEBI, RBI, MCA21, NJDG) → weight 1.0
Third-party source (Rating agency, bank statement)     → weight 0.85
Self-reported source (Annual Report, management claims) → weight 0.70
```

### 6.6 Error Handling

```python
# EVERY async function must have try/except
async def scrape_mca21(company_cin: str) -> MCA21Result:
    try:
        result = await _do_scrape(company_cin)
        return result
    except TimeoutError:
        logger.warning(f"[MCA21] Timeout for {company_cin}, using cached/fallback")
        return MCA21Result(status="degraded", data=None, error="Timeout")
    except Exception as e:
        logger.error(f"[MCA21] Failed for {company_cin}: {e}")
        # Emit thinking event so officer sees the degradation
        await emitter.emit(EventType.FLAGGED, f"MCA21 scraper unavailable: {e}")
        return MCA21Result(status="failed", data=None, error=str(e))
```

**Rules:**
- Never use empty `except: pass`.
- Always log with the component name: `[Agent 2.5]`, `[MCA21]`, `[Scorer]`.
- Always emit a ThinkingEvent when something degrades.
- Scrapers must have timeout + retry + fallback (pipeline never breaks).

---

## 7. Data Layer Rules

### 7.1 Database Responsibility Separation (STRICT)

| Database | What Goes Here | What NEVER Goes Here |
|---|---|---|
| **ChromaDB** | Document chunk vectors, RAG knowledge base entries, resolved ticket precedents | Structured data, scores, metadata-only records |
| **Neo4j** | Entity-relationship graph (companies, directors, suppliers, customers, banks, charges, cases) | Raw text, financial numbers, scores |
| **Elasticsearch** | Full-text search (4 indices: document_store, research_intelligence, company_profiles, regulatory_watchlist) | Graph relationships, vector embeddings |
| **PostgreSQL** | All structured records: assessments, score_breakdown, findings_store, tickets, decision_outcomes, thinking_events, rejection_events, fraud_investigations | Document text, embeddings, graph data |
| **Redis** | Celery broker, worker staging area, research cache (7-day TTL), Pub/Sub thinking events | Permanent storage of any kind |

**NEVER store the same data in two databases** unless it's for a fundamentally different query pattern (e.g., document text in ES for full-text search AND in ChromaDB for semantic search is acceptable).

### 7.2 PostgreSQL Schema (Source of Truth)

These 7 tables are defined in detail in [README.md Section 5](README.md). When implementing:
- `assessments` — master record, one per loan application
- `score_breakdown` — every point in the 0–850 score
- `findings_store` — every research + compound finding
- `tickets` — every conflict and its resolution
- `decision_outcomes` — filled AFTER loan matures
- `thinking_events` — complete AI thought log
- `rejection_events` — all rejections with evidence snapshots
- `fraud_investigations` — all fraud detections with graph snapshots

**All tables link to `assessments` via `session_id` FK.** Never create orphaned records.

### 7.3 Neo4j Node & Relationship Types (Source of Truth)

| Node Types | Relationship Types |
|---|---|
| `Company` | `SUPPLIES_TO`, `BUYS_FROM` |
| `Director` | `IS_DIRECTOR_OF`, `FAMILY_OF` |
| `Supplier` | `HAS_CHARGE` |
| `Customer` | `OUTSTANDING_RECEIVABLE` |
| `Bank` | `IS_AUDITOR_OF` |
| `Auditor` | `HAS_RATING_FROM` |
| `RatingAgency` | `FILED_CASE_AGAINST` |

When adding new node types or relationships, document them HERE first.

### 7.4 Elasticsearch 4 Indices

| Index | Contents |
|---|---|
| `document_store` | Extracted text chunks + metadata (doc type, page, confidence) |
| `research_intelligence` | Web research results + source tier |
| `company_profiles` | Past assessments, peer data, sector benchmarks |
| `regulatory_watchlist` | RBI circulars, SEBI regs, MCA notifications, GST council |

### 7.5 Defensive Data Access

**Frontend (JavaScript):**
```js
// ALWAYS use optional chaining + nullish coalescing
const score = assessment?.finalScore ?? 0;
const band = assessment?.scoreBand ?? "Unknown";
const findings = assessment?.findings ?? [];
const dscr = breakdown?.capacity?.dscr?.value ?? "N/A";
```

**Backend (Python):**
```python
# ALWAYS guard against None
revenue = extraction.revenue if extraction else Decimal("0")
director_name = mca_result.directors[0].name if mca_result and mca_result.directors else "Unknown"
```

---

## 8. Domain Knowledge — Credit Appraisal Context

### 8 Document Types (Processed by Workers)

| Worker | Document | Key Extractions |
|---|---|---|
| W1 | Annual Report | Revenue (3yr), EBITDA, PAT, Debt, Net Worth, RPTs, Auditor Quals, Litigation Disclosure |
| W2 | Bank Statement | Monthly inflows/outflows, bounces, EMI regularity, round-number transactions |
| W3 | GST Returns | GSTR-2A vs 3B reconciliation, monthly turnover, ITC claimed vs available |
| W4 | ITR | Schedule BP (income), Schedule BS (balance sheet), ITR-vs-AR divergence |
| W5 | Legal Notice | Claimant, claim type, amounts, dates, status |
| W6 | Board Minutes | Director attendance, RPT approvals, CFO changes, risk discussions |
| W7 | Shareholding Pattern | Promoter %, pledge %, institutional changes, cross-holdings |
| W8 | Rating Report | Current rating, upgrade/downgrade history, watch/outlook |
| W9 | Site Visit Notes | Factory condition, capacity utilization, inventory, management observations |

### 5 Cs of Credit (Scoring Framework)

| C | Max Up | Max Down | Key Signals |
|---|---|---|---|
| **Capacity** | +150 | -100 | DSCR, revenue growth, WC cycle, cash flow, repayment |
| **Character** | +120 | -200 | Promoter track record, SEBI/RBI, RPT disclosure, pledge, management |
| **Capital** | +80 | -80 | D/E ratio, net worth, existing debt, equity contributions |
| **Collateral** | +60 | -40 | Coverage ratio, asset quality, lien status |
| **Conditions** | +50 | -50 | Order book, sector outlook, regulatory, PLI support |
| **Compound** | +57 | -130 | Cascade risk, circular trading, temporal patterns, positive signals |

### Hard Block Triggers (Override Everything)

| Trigger | Score Cap |
|---|---|
| Wilful defaulter (RBI list) | Capped at 200 |
| Active criminal case against promoter | Capped at 150 |
| DSCR < 1.0x | Capped at 300 |
| NCLT active proceedings | Capped at 250 |

### Score Bands

| Band | Range | Recommendation |
|---|---|---|
| Excellent | 750–850 | Full amount, MCLR+1.5% |
| Good | 650–749 | 85%, MCLR+2.5% |
| Fair | 550–649 | 65%, MCLR+3.5% |
| Poor | 450–549 | 40%, MCLR+5.0% |
| Very Poor | 350–449 | Reject |
| Default Risk | <350 | Permanent reject |

### Verification Engine — Source Credibility Tiers

| Tier | Weight | Source |
|---|---|---|
| 1 (1.0) | Fact | Government portals (MCA21, SEBI, RBI, NJDG, GST) |
| 2 (0.85) | High | Reputable financial media (ET, BS, Mint, FE) |
| 3 (0.60) | Moderate | General/regional news |
| 4 (0.30) | Low | Blogs, unverified sites |
| 5 (0.0) | Rejected | Social media, anonymous |

### Ticket Severity Behavior

| Severity | Pipeline Action |
|---|---|
| LOW | Pipeline continues, ticket resolved async |
| HIGH | Pipeline pauses at Agent 3, must resolve first |
| CRITICAL | Pipeline stops, senior manager notification |

---

## 9. Post-Implementation Review Checklist

### 9.1 Code Quality (0–25 points)

- [ ] **Naming:** All new functions, variables, files follow conventions (Section 5 / Section 6).
- [ ] **Error handling:** Every async function has try/except. Decide fail-open or fail-closed intentionally.
- [ ] **ThinkingEvents:** Every agent operation emits thinking events. If it doesn't show in chatbot, it needs one.
- [ ] **Comments:** Every new logic block has a comment explaining *what* and *why*.
- [ ] **Code change policy:** When replacing logic — comment out old code with explanation, add new code below with comment. Never silently delete working code.
- [ ] **Dead code:** Remove or comment out leftover references to replaced functions, models, or variables.
- [ ] **Consistency:** New code matches the style, indentation, and patterns of surrounding code.
- [ ] **DRY:** Extract and reuse duplicated logic. Use existing components before creating new ones.
- [ ] **Magic numbers:** Domain constants (score ranges, hard blocks, weights) go in `config/settings.py` or module constants.
- [ ] **Pydantic models:** All data structures use Pydantic v2 models. No raw `dict` for structured data.

### 9.2 Cross-File Impact Analysis (0–25 points)

- [ ] **Trace dependencies:** For every change, check what else depends on it.
- [ ] **Schema sync:** If a Pydantic model changes → update every consumer (nodes, API routes, tests, mock data).
- [ ] **State sync:** If `CreditAppraisalState` changes → every LangGraph node must be verified.
- [ ] **API shape sync:** If API response format changes → update frontend mock data + every consumer component.
- [ ] **Neo4j schema:** If node/relationship types change → update Section 7.3 of this file + all Cypher queries.
- [ ] **Import check:** After renaming/moving files, update all import paths.
- [ ] **Config check:** If changing env vars or settings → update `.env.example` and `config/settings.py`.

### 9.3 Architecture Integrity (0–20 points)

- [ ] **Single responsibility:** Each agent does exactly one job. Each database stores exactly one type of thing.
- [ ] **Data before LLM:** Data is organized, verified, and sourced BEFORE any LLM sees it.
- [ ] **Evidence Package gate:** Agent 3 reads ONLY the Evidence Package. It never touches raw documents, Neo4j, or Insight Store.
- [ ] **Source tracing:** Every claim, every score point, every finding traces back to document + page + excerpt.
- [ ] **Cross-verification:** Revenue checked across 4 sources. RPTs checked across Board Minutes + AR. Litigation checked across AR + NJDG.
- [ ] **Credential priority:** Government > Third-party > Self-reported. Never reversed.
- [ ] **Thinking pipeline:** Every significant operation emits a ThinkingEvent to Redis Pub/Sub.
- [ ] **Graceful degradation:** If a scraper/API fails, pipeline continues with reduced scope + ticket raised. Never crashes.

### 9.4 Edge Cases (0–20 points)

- [ ] **Missing documents:** Mandatory documents missing → request from user via validator. Optional missing → proceed with note.
- [ ] **OCR low confidence:** Page below threshold → ticket raised, not silently accepted.
- [ ] **Scraper timeout:** Retry with exponential backoff → fallback to cached → proceed without + ticket.
- [ ] **LLM failure:** Retry once → if still fails, use alternative model tier → if still fails, emit critical event.
- [ ] **Neo4j disconnection:** Async writes queued in Redis → retry when available. Graph reasoning uses last snapshot.
- [ ] **WebSocket disconnect:** Client reconnects with exponential backoff. Missed events replayed from thinking_events table.
- [ ] **Empty graph:** If Neo4j has no external enrichment (all scrapers failed), reasoning still runs on internal document data.
- [ ] **Hard block mid-pipeline:** Wilful defaulter found at any stage → immediate pipeline halt, rejection stored, full evidence snapshot.
- [ ] **Demo mode:** All components MUST work with mock data when backend is unavailable.

### 9.5 Confidence Score (0–10 points: Test Readiness)

| Category | Max Points |
|---|---|
| Code Quality | 25 |
| Cross-File Impact | 25 |
| Architecture Integrity | 20 |
| Edge Case Coverage | 20 |
| Test Readiness | 10 |
| **Total** | **100** |

**Verdict:**
- **SHIP IT** (90+): Merge-ready.
- **REVIEW NEEDED** (70–89): Address flagged items, re-score.
- **REWORK** (below 70): Significant issues — re-plan.

---

## 10. Testing Procedure

### 10.1 Frontend Tests

```bash
cd frontend
# Verify dev server starts without errors
npm run dev

# If using TypeScript later:
# npx tsc --noEmit
```

Verify:
- All 7 pages load without blank screens.
- WebSocket connection indicator shows status.
- Mock data renders correctly in all components.
- Thinking chatbot renders color-coded events.
- Score dashboard renders gauge + breakdown correctly.
- Ticket interface renders ticket queue + detail.

### 10.2 Backend Tests

```bash
cd backend
# Python syntax + import check
python -m py_compile api/main.py

# Run tests
pytest tests/ -v

# Type checking (if mypy configured)
mypy api/ agents/ --ignore-missing-imports
```

Verify:
- FastAPI starts without import errors.
- All Pydantic models validate correctly.
- LangGraph state machine compiles.
- All Celery tasks register.
- WebSocket endpoint accepts connections.
- ThinkingEvent emission works end-to-end.

### 10.3 Integration Tests

```bash
# Full stack smoke test
docker-compose up -d
# Wait for all services healthy
# Run integration suite
pytest tests/test_integration/ -v
```

Verify:
- Upload → Workers fire → Agent 0.5 → ... → Agent 3 → Score + CAM
- ThinkingEvents flow from agents → Redis → WebSocket → UI
- Tickets created and resolvable
- Score persisted to PostgreSQL with full breakdown
- Knowledge base stores resolved ticket precedents

### 10.4 Demo Smoke Test (CRITICAL for hackathon)

- [ ] Upload sample documents → pipeline starts.
- [ ] Thinking chatbot shows real-time messages from each agent.
- [ ] Worker status panel shows all 8 workers.
- [ ] Cross-verification flag appears in chatbot.
- [ ] Score dashboard renders 477/850 with module breakdown.
- [ ] Per-point drilldown works (click module → see metrics).
- [ ] CAM viewer renders with citation highlighting.
- [ ] Ticket resolution dialogue works.
- [ ] Decision Store shows historical assessment.
- [ ] Everything works with mock data if backend is down.

---

## 11. AI Agent Mandatory Rules (Pitfall Prevention)

### 11.1 Version Consistency

Never change package versions unless asked. This includes:
- `requirements.txt` versions
- `package.json` dependencies
- Docker image tags in `docker-compose.yml`
- Python runtime version

### 11.2 Architecture Compliance

Before implementing any feature, verify:
1. Does this respect the pipeline order? (Workers → 0.5 → Validator → 1.5 → 2 → 2.5 → Evidence → Tickets → 3)
2. Does this use the correct database for this data type? (Section 7.1)
3. Does Agent 3 ONLY read from the Evidence Package? (It must NEVER query Neo4j, ES, or raw documents directly.)
4. Does every finding trace back to a source document + page?
5. Does this emit ThinkingEvents?

### 11.3 Schema Sync Protocol

When ANY Pydantic model changes:
1. Update the model definition in `backend/models/`.
2. Update `CreditAppraisalState` in `backend/graph/state.py` if the state is affected.
3. Update every LangGraph node that reads/writes the changed field.
4. Update every API route that serializes/deserializes the model.
5. Update frontend mock data if the API response shape changed.
6. Update every frontend component consuming that data.
7. Update tests.
8. Verify no `KeyError`, `AttributeError`, or `ValidationError` at runtime.

### 11.4 Defensive Data Access

```python
# ALWAYS — Python
value = data.get("revenue", Decimal("0"))
director = (extraction.directors or [])[0] if extraction and extraction.directors else None
```

```javascript
// ALWAYS — JavaScript
const score = assessment?.finalScore ?? 0;
const events = data?.thinkingEvents ?? [];
```

### 11.5 Fresh Rebuilds

Never copy `node_modules/`, `.next/`, `__pycache__/`, `venv/` between tasks. If dependencies change:
```bash
# Frontend
rm -rf node_modules .next
npm install
npm run dev

# Backend
rm -rf __pycache__ venv
python -m venv venv
pip install -r requirements.txt
```

### 11.6 Working Directory Awareness

Always verify `cwd` before running terminal commands:
- Frontend commands: run from `frontend/`
- Backend commands: run from `backend/`
- Docker commands: run from project root
- Tests: run from project root or the specific test directory

### 11.7 No Silent Failures

- Do not suppress errors with empty except blocks.
- Always log with component name: `logger.error("[Agent 2.5] ...")`.
- Always emit a ThinkingEvent when something goes wrong — the officer must see it.
- Show user-visible error states in UI, not blank screens.

### 11.8 Imports After Refactoring

After any rename, move, or delete:
- Grep for the old import path across the entire project.
- Update every occurrence.
- Verify with `python -m py_compile` (backend) or dev server (frontend).

### 11.9 Prompt Templates

All LLM prompts live in `config/prompts/`. Never hardcode prompts in agent code.
```python
# CORRECT
from config.prompts.extraction_prompts import ANNUAL_REPORT_EXTRACTION_PROMPT
chain = prompt | model | parser

# WRONG
chain = ChatPromptTemplate.from_template("Extract the revenue from...") | model
```

### 11.10 Mock Data for Demo

Every frontend component and every API endpoint MUST have a mock data fallback. The hackathon demo must work even if:
- A database is down
- An external API is unreachable
- A scraper times out
- The LLM returns an error

Mock data should be realistic, using the XYZ Steel ₹50cr Working Capital example from the architecture spec.

---

## 12. Review Personas

When reviewing your own work, simulate these three reviewers:

### Credit Domain Expert
- Does the cross-verification actually check the right fields?
- Are the scoring weights and hard blocks correct for Indian banking?
- Does the GSTR-2A vs 3B check work correctly (ITC claimed vs available)?
- Is the RPT concealment detection comparing the right documents?
- Would a credit officer trust this output?

### Security Architect
- Is user input validated before use?
- Are API calls protected (JWT, rate limiting)?
- Is PII handled correctly (no logging of sensitive data)?
- Are WebSocket connections authenticated?
- Can a malicious document exploit the parser?

### Systems Engineer
- Does this scale? (Can Celery handle 10 concurrent assessments?)
- Is the database being used correctly? (Not full-text search on PostgreSQL)
- Are Redis cache keys properly namespaced and TTL'd?
- Is the WebSocket connection properly cleaned up on disconnect?
- Is memory managed? (Large PDFs, long graph traversals)

---

## 13. Self-Improvement Loop

- After ANY correction from the user: document the pattern in `tasks/lessons.md` (create if needed).
- Review lessons at the start of each session.
- Never make the same mistake twice.

---

## 14. Key Files Quick Reference

| What | Where |
|---|---|
| Full project specification | `README.md` (1980 lines) |
| PPT/video script guide | `intellicredit.md` |
| LangGraph state machine | `backend/graph/orchestrator.py` |
| Pipeline state object | `backend/graph/state.py` |
| All Pydantic schemas | `backend/models/schemas.py` |
| ThinkingEvent model | `backend/models/thinking_event.py` |
| LLM prompt templates | `config/prompts/` |
| Application config | `config/settings.py` |
| Environment variables | `.env.example` |
| Score modules | `backend/agents/recommendation/score_modules/` |
| 8 document workers | `backend/agents/workers/` |
| 5 graph reasoning passes | `backend/agents/reasoning/` |
| 5 Indian scrapers | `backend/agents/research/scrapers/` |
| Storage clients | `backend/storage/` |
| ML model wrappers | `backend/ml/` |
| Frontend components | `frontend/src/components/` |
| Frontend mock data | `frontend/src/lib/mockData.js` |
| Docker Compose | `docker-compose.yml` |

---

## 15. Component Creation Checklist

### Frontend — New Component

1. [ ] Check if an existing component can be reused or extended.
2. [ ] Place in `frontend/src/components/` organized by domain.
3. [ ] Use named export: `export function MyComponent() {}`.
4. [ ] Include mock data fallback — component must render without backend.
5. [ ] Follow card pattern for panel-type components.
6. [ ] Add empty state handling if the component displays data.
7. [ ] Add loading state if the component fetches data.
8. [ ] Use thinking event color coding for chatbot-related components.
9. [ ] Test: renders without crash with mock data.

### Backend — New Agent Node

1. [ ] Create node function in `backend/graph/nodes/`.
2. [ ] Node receives and returns `CreditAppraisalState`.
3. [ ] Node emits ThinkingEvents for every significant operation.
4. [ ] Node has try/except with proper logging and error ThinkingEvent.
5. [ ] Node is async.
6. [ ] Register node in `backend/graph/orchestrator.py`.
7. [ ] Add edge in LangGraph state machine.
8. [ ] Define any new Pydantic models in `backend/models/`.
9. [ ] Add prompts to `config/prompts/` (never hardcode).
10. [ ] Create tests in `tests/test_agents/`.
11. [ ] Verify: `python -m py_compile backend/graph/nodes/new_node.py`.

### Backend — New Scraper

1. [ ] Create in `backend/agents/research/scrapers/`.
2. [ ] Implement timeout + retry with exponential backoff.
3. [ ] Implement fallback (cached result or graceful skip).
4. [ ] Emit ThinkingEvents for start, findings, errors.
5. [ ] Return a typed Pydantic result (never raw dict).
6. [ ] Register in Agent 2's parallel track dispatcher.
7. [ ] What findings does it write to Neo4j? Define nodes + relationships.
8. [ ] Update the verification engine tier if needed.
9. [ ] Add mock response for demo fallback.
10. [ ] Test: scraper timeout → pipeline continues with ticket.

### Backend — New Score Module

1. [ ] Create in `backend/agents/recommendation/score_modules/`.
2. [ ] Define max_positive and max_negative constants matching architecture.
3. [ ] Every point allocated must have: metric, value, formula, source, page, excerpt, benchmark, reasoning.
4. [ ] Register in the scorer's module runner.
5. [ ] Add to `ScoreModule` enum.
6. [ ] Test: module returns correct impact for known inputs.
7. [ ] Test: module handles missing data gracefully (reduced confidence, not crash).

---

## 16. Git & Commit Rules

- Commit messages follow: `type(scope): description`
  - Types: `feat`, `fix`, `refactor`, `style`, `docs`, `test`, `chore`, `infra`
  - Scope: `workers`, `consolidator`, `organizer`, `research`, `reasoning`, `scorer`, `cam`, `tickets`, `frontend`, `api`, `docker`, `graph`, `ml`, `storage`
  - Example: `feat(reasoning): add cascade_pass with multi-hop DSCR recalculation`
- Never commit: `node_modules/`, `.next/`, `__pycache__/`, `venv/`, `*.pyc`, `*.pkl`, `*.pt`, `.env`
- Pull before pushing. Resolve conflicts locally.

---

## 17. Performance Rules

### Backend

- **ML models loaded ONCE at startup**, not per-request. Store in app state.
- **Celery workers are the parallelism** — don't create thread pools inside workers.
- **Neo4j writes are async and non-blocking** — use the async driver.
- **Redis cache everything** that's expensive: scraper results (7-day TTL), LLM responses for identical inputs (24h TTL).
- **Batch embedding**: embed all document chunks in one call to local MiniLM, not one-by-one.
- **LLM tiering is strict**: Haiku for 80% of calls (extraction, classification). Sonnet for 20% (Executive Summary, Risk Flags, Decision Rationale).

### Frontend

- **WebSocket connection**: one per session, shared across components. Never open multiple WebSocket connections.
- **Thinking events**: virtualized list if >500 events visible. Do not render thousands of DOM nodes.
- **Charts**: lazy-load with dynamic import if using SSR framework.
- **Mock data**: pre-computed, never simulate expensive operations client-side.

---

## 18. Environment Setup

### First-Time Setup

```bash
# 1. Clone and enter project
git clone <repo>
cd intelli-credit

# 2. Copy env template
cp .env.example .env
# Fill in API keys: ANTHROPIC_API_KEY, TAVILY_API_KEY, EXA_API_KEY, etc.

# 3. Start all services
docker-compose up -d

# 4. Frontend dev (if developing outside Docker)
cd frontend
npm install
npm run dev

# 5. Backend dev (if developing outside Docker)
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

### Required Services

All must be running for full pipeline:
- Redis (port 6379)
- PostgreSQL (port 5432)
- Neo4j (port 7474/7687)
- Elasticsearch (port 9200)
- ChromaDB (port 8100)

For frontend-only development, mock data is sufficient.

---

## 19. Feature Implementation Rules

### One Feature at a Time — Strictly Enforced

**NEVER implement an entire tier of features in one pass.** Always follow this cycle:

1. **Pick ONE feature** from the current tier (e.g., T1.1, not "all of T1").
2. **Implement that single feature** completely — frontend component, backend endpoint, or agent node.
3. **Write and run tests** for that feature immediately after implementation.
4. **All tests must pass** (both the new tests AND all existing tests) before moving on.
5. **Mark it complete** in the todo list.
6. **Only then** pick the next feature.

**Why**: Implementing multiple features before testing leads to cascading failures, hard-to-debug interactions, and wasted time. One feature + tests = confidence. Batch features + deferred tests = chaos.

**Anti-patterns (NEVER do these)**:
- Implementing T1.1 through T1.8 then running tests → NO
- Implementing a feature and saying "tests will come later" → NO
- Skipping tests because "it's just a small change" → NO

---

*Last updated: March 6, 2026*
*Applies to: Intelli-Credit AI-Powered Credit Decisioning Engine*
*Stack: React 18 + TailwindCSS 3 (frontend) | FastAPI + LangGraph + LangChain + Celery + 4 databases + 3 ML models + 5 scrapers (backend)*
