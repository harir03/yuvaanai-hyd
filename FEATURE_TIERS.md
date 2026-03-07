# INTELLI-CREDIT — Feature Priority Tier List (Hackathon Implementation Plan)

> **Purpose**: Prioritized breakdown of every feature by implementation urgency, demo impact, judge scoring potential, and technical dependency chain. Read this before writing any backend code.
>
> **Decision Framework**: At a hackathon, judges spend ~5 minutes on your demo. Every feature must answer: *"Will a judge notice this in 5 minutes? Does removing it break the demo?"*

---

## Tier Map Overview

| Tier | Label | Count | Time Budget | Description |
|---|---|---|---|---|
| **T0** | 🔴 Demo Skeleton | 8 features | ~35% of time | Without these, **nothing works**. No demo, no score. |
| **T1** | 🟠 Judge Magnets | 8 features | ~30% of time | These are what **judges will specifically look for** in Credit Appraisal / FinTech tracks. Skipping these = losing to every team that has them. |
| **T2** | 🟡 Strong Differentiators | 7 features | ~20% of time | These separate a **"good project"** from a **"winning project."** Most teams won't have these. |
| **T3** | 🟢 Polish & Depth | 8 features | ~10% of time | Professional touches that signal production-readiness. Do these only after T0–T2 are solid. |
| **T4** | 🔵 Stretch Goals | 6 features | ~5% of time | "Nice to show" but zero impact if missing. Only if time permits after everything else is bulletproof. |

---

## 🔴 TIER 0 — DEMO SKELETON (Must Have — Nothing Works Without These)

These 8 features form the absolute minimum viable demo. If any one of them is missing or broken, the demo fails.

---

### T0.1 — FastAPI Backend Skeleton + WebSocket Server

**What**: The core API server that serves every frontend page, handles file uploads, manages WebSocket connections for the live chatbot, and dispatches tasks to the pipeline.

**Why T0**: Every single frontend page calls this server. No server = blank screens.

**What It Includes**:
- FastAPI app with CORS middleware (frontend lives on different port)
- REST endpoints: `POST /upload`, `GET /assessment/{id}`, `GET /tickets/{id}`, `POST /tickets/{id}/resolve`
- WebSocket endpoint: `ws://localhost:8000/ws/thinking/{session_id}` — pushes ThinkingEvents to the Live Chatbot in real time
- WebSocket endpoint: `ws://localhost:8000/ws/progress/{session_id}` — pushes pipeline stage updates
- Pydantic v2 request/response models for every endpoint (strict validation)
- Basic JWT auth middleware (can be stubbed for hackathon, but route structure must exist)

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| Framework | FastAPI 0.110 | Async-native, auto-OpenAPI docs, native WebSocket, fastest Python framework |
| Validation | Pydantic v2 (2.5+) | Rust-core, 5-50x faster than v1, strict mode catches bad data at boundaries |
| WebSocket | FastAPI native | No extra library needed, integrates with async event loop |
| Auth | python-jose (JWT) | Stateless, standard, simple |
| Rate Limiting | Custom middleware | Prevents abuse during demo |

**Endpoints**:
```
POST   /api/upload                    — Upload documents + company info → starts pipeline
GET    /api/assessment/{session_id}   — Full assessment state (pipeline, workers, events, score)
GET    /api/tickets/{session_id}      — All tickets for an assessment
POST   /api/tickets/{ticket_id}/resolve — Submit human resolution
GET    /api/history                   — All historical assessments
GET    /api/analytics                 — Aggregated stats
WS     /ws/thinking/{session_id}      — Live thinking event stream
WS     /ws/progress/{session_id}      — Pipeline progress updates
```

**Files to Create**:
- `backend/api/main.py` — App factory, CORS, lifespan, router includes
- `backend/api/routes/upload.py` — Upload endpoint
- `backend/api/routes/assessment.py` — Assessment CRUD
- `backend/api/routes/tickets.py` — Ticket resolution
- `backend/api/routes/decisions.py` — Decision store / history
- `backend/api/websocket/thinking_ws.py` — ThinkingEvent WebSocket handler
- `backend/api/websocket/progress_ws.py` — Pipeline progress WebSocket

**Demo Impact**: 🔴 Invisible to judges (backend), but without it → every page shows mock data only.

---

### T0.2 — LangGraph Orchestrator + CreditAppraisalState

**What**: The state machine that orchestrates the entire 9-stage pipeline. A `CreditAppraisalState` Pydantic v2 object passes through every node, accumulating knowledge. Conditional edges control routing (normal path, auto-reject, fraud, human review).

**Why T0**: This IS the pipeline. Without it, there's no automated credit assessment — just disconnected scripts.

**What It Includes**:
- `CreditAppraisalState` — Master Pydantic v2 model carrying ALL pipeline state (company info, documents, worker outputs, consolidated data, organized data, research findings, graph insights, evidence package, tickets, score, CAM)
- LangGraph `StateGraph` definition with all 10 nodes registered
- Conditional edges: normal path, auto-reject (hard blocks), deep fraud (ML signal > threshold), human review (score 550–650)
- `START` → `workers_node` → `consolidator_node` → `validator_node` → `organizer_node` → `research_node` → `reasoning_node` → `evidence_node` → `ticket_node` → `recommendation_node` → `decision_store_node` → `END`
- Async execution with `graph.ainvoke(initial_state)`

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| State Machine | LangGraph 0.2 | Explicit node/edge control, Pydantic state, conditional routing, human-in-the-loop pause/resume |
| Agent Framework | LangChain 0.3 | Document loaders, chains, RAG, tool integrations, automatic LangSmith tracing |
| Observability | LangSmith (latest) | Every LLM call, agent decision, tool use traced — judges can click through the full trace |
| State Model | Pydantic v2 | Strict validation at every node boundary, clear field ownership |

**Key Design Decisions**:
- State is **immutable per node** — each node receives state, processes, returns updated state
- Every node emits `ThinkingEvent`s for the Live Chatbot
- Every node has `try/except` — no silent failures, always emit error ThinkingEvent
- Conditional edges check: `state.hard_blocks`, `state.fraud_signals`, `state.final_score`

**Files to Create**:
- `backend/graph/state.py` — `CreditAppraisalState` + all sub-models
- `backend/graph/orchestrator.py` — LangGraph `StateGraph` definition + conditional edges

**Demo Impact**: 🔴 Invisible to judges directly, but powers the entire pipeline flow they see in the Processing Dashboard.

---

### T0.3 — ThinkingEvent Bus (Redis Pub/Sub → WebSocket → UI)

**What**: The real-time event pipeline that takes every AI reasoning step from backend agents and pushes it to the Live Chatbot in the UI. Every agent publishes `ThinkingEvent`s to Redis Pub/Sub. The WebSocket server subscribes and pushes to connected UI clients.

**Why T0**: The Live Thinking Chatbot is the **#1 demo feature**. Without the event bus, the chatbot is dead. The entire transparency story collapses.

**What It Includes**:
- `ThinkingEventEmitter` class — used by every agent node to publish events
- Redis Pub/Sub channel: `thinking:{session_id}` — one channel per active assessment
- WebSocket server subscribes to the channel and pushes every event to all connected UI clients for that session
- Events stored in PostgreSQL `thinking_events` table for replay
- Event types: `READ`, `FOUND`, `COMPUTED`, `ACCEPTED`, `REJECTED`, `FLAGGED`, `CRITICAL`, `CONNECTING`, `CONCLUDING`, `QUESTIONING`, `DECIDED`

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| Pub/Sub | Redis 7 | Already used as Celery broker + cache, Pub/Sub is built-in, zero additional infrastructure |
| Publisher | Custom `ThinkingEventEmitter` | Thin wrapper around `redis.publish()` with JSON serialization |
| Subscriber | FastAPI WebSocket handler | Subscribes to Redis channel, pushes to WebSocket clients |
| Storage | PostgreSQL | Permanent record for replay, audit trail |

**Event Flow Architecture**:
```
Agent (any stage) → emitter.emit(EventType.FOUND, "Revenue: ₹312.4cr", source="AR p.42")
         ↓
Redis Pub/Sub channel: "thinking:{session_id}"
         ↓
FastAPI WebSocket handler (subscribed) → pushes to all connected clients
         ↓
React Live Chatbot component → appends message, color-codes, auto-scrolls
```

**Files to Create**:
- `backend/thinking/event_emitter.py` — `ThinkingEventEmitter` class
- `backend/thinking/redis_publisher.py` — Redis Pub/Sub publish wrapper
- `backend/thinking/event_formatter.py` — Human-readable formatting
- `backend/models/thinking_event.py` — `ThinkingEvent` Pydantic model

**Demo Impact**: 🔴🔴🔴 **THE** demo feature. Judges watching AI think in real time — naming documents, quoting text, making decisions — is the single most compelling explainability demo possible.

---

### T0.4 — PostgreSQL Schema + Storage Client

**What**: The relational database storing ALL structured data — assessments, score breakdowns, findings, tickets, thinking events, decisions. Source of truth for the entire system.

**Why T0**: Every page reads from PostgreSQL. Score breakdown, tickets, history, analytics — all need structured storage.

**What It Includes**:
- 7 core tables: `assessments`, `score_breakdown`, `findings_store`, `tickets`, `thinking_events`, `rejection_events`, `fraud_investigations`
- Plus `decision_outcomes` (filled after loan matures — demo shows structure)
- Async PostgreSQL client using `asyncpg` or `sqlalchemy[asyncio]`
- All tables linked via `session_id` FK to `assessments`
- Seed data script for demo (pre-populated XYZ Steel assessment)

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| Database | PostgreSQL 15 | ACID compliance, JSONB for flexible fields, rock-solid for structured data |
| Driver | asyncpg or SQLAlchemy async | Non-blocking queries, connection pooling |
| Migrations | Alembic (optional) | Schema versioning |
| ORM | SQLAlchemy 2.0 (optional) | Type-safe queries, or raw SQL is fine for hackathon |

**Key Tables** (see README Section 5 for full schema):
- `assessments` — Master record (session_id, company, score, band, outcome, timestamps)
- `score_breakdown` — Every single point in the 0–850 score with metric, value, formula, source, page, excerpt, benchmark, impact, reasoning, confidence
- `findings_store` — Every research + compound finding with source, decision, severity
- `tickets` — Every conflict with both claims, AI reasoning, precedents, resolution, human resolver
- `thinking_events` — Complete AI thought log (for replay + audit trail)

**Files to Create**:
- `backend/storage/postgres_client.py` — Async CRUD operations for all 7 tables
- `backend/storage/schema.sql` — Table creation DDL
- `backend/storage/seed_data.py` — Demo data for XYZ Steel assessment

**Demo Impact**: 🔴 Invisible to judges, but without it → History page is empty, Analytics page has no data, score breakdown is mock-only.

---

### T0.5 — Redis Setup (Celery Broker + Cache + Pub/Sub + Staging)

**What**: Redis serves 4 roles simultaneously: Celery message broker (dispatching document workers), research cache (7-day TTL), Pub/Sub bus (ThinkingEvents), and staging area (worker outputs before consolidation).

**Why T0**: Celery requires Redis. ThinkingEvent bus requires Redis. Research caching requires Redis. Worker staging requires Redis. Remove Redis = remove parallel processing + live chatbot + research caching.

**What It Includes**:
- Celery broker configuration (`broker_url = redis://...`)
- Worker output staging: key `staging:{session_id}:{worker_id}` with JSON worker output
- Research cache: key `research:{query_hash}` with 7-day TTL
- Pub/Sub channels: `thinking:{session_id}`, `progress:{session_id}`
- Connection pooling for concurrent access

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| Server | Redis 7 | In-memory, sub-millisecond latency, built-in Pub/Sub, Celery's recommended broker |
| Client | redis-py (async) | Official Python client with async support |
| Serialization | JSON | Simple, debuggable, Pydantic models serialize natively |

**Files to Create**:
- `backend/storage/redis_client.py` — Connection pool, staging ops, cache ops, Pub/Sub helpers

**Demo Impact**: 🔴 Invisible, but powers everything that makes the demo work.

---

### T0.6 — Celery Workers (At Minimum 3 Document Workers)

**What**: Parallel document processing workers that run as independent Celery tasks. Each worker processes one document type, extracts structured data, and writes output to Redis staging. **For hackathon MVP, implement at least 3 workers** (Annual Report, Bank Statement, GST Returns) — these cover the most critical cross-verification checks.

**Why T0**: Without workers, there's no document processing. The entire pipeline starts here. The Processing Dashboard's Worker Status Panel shows 8 workers — at least 3 must actually run.

**Minimum 3 Workers for Demo**:

| Worker | Document | Why This One | Parsing Tech |
|---|---|---|---|
| **W1 — Annual Report** | AR PDF | Revenue, EBITDA, PAT, debt, RPTs — the primary financial document | Unstructured.io + Tesseract OCR + Camelot |
| **W2 — Bank Statement** | Bank PDF | Monthly inflows, bounces, EMI regularity — real cash flow evidence | Camelot + Pandas |
| **W3 — GST Returns** | GST Excel/PDF | GSTR-2A vs 3B reconciliation — **explicitly in hackathon evaluation criteria** | Pandas + custom GST parser |

**Nice-to-Have Workers for Demo** (implement if time):
| Worker | Document | Why | Parsing Tech |
|---|---|---|---|
| W4 — ITR | ITR XML/PDF | Revenue cross-check (3-way with AR + GST) | Custom XML + Pandas |
| W6 — Board Minutes | BM PDF | RPT concealment detection (vs AR) | Claude Haiku (narrative) |
| W7 — Shareholding | SP PDF | Promoter pledge detection | Camelot + Pandas |

**Each Worker Must**:
1. Receive document file path from Celery task
2. Parse using appropriate tech stack
3. Extract structured data into a typed Pydantic model
4. Emit `ThinkingEvent`s as it processes (READ, FOUND, FLAGGED)
5. Write output to Redis staging area: `staging:{session_id}:{worker_id}`
6. Handle errors gracefully (never crash the pipeline)

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| Task Queue | Celery 5 | Mature, production-proven, retry/backoff, task routing, priority queues |
| Broker | Redis 7 | Fast, reliable, already in the stack |
| Monitor | Flower 2 | Real-time worker dashboard — visually impressive for demo |
| PDF Parsing | Unstructured.io 0.12 | Spatial layout understanding for complex Indian annual reports |
| OCR | Tesseract 5.3 | Open-source, local, free, page-level parallelism |
| Table Extraction | Camelot 0.11 | Best-in-class PDF table extraction |
| Data Analysis | Pandas 2 | Excel/CSV, time-series bank statement analysis |
| LLM Extraction | Claude Haiku 3.5 | For unstructured narrative docs (legal, board minutes, rating) |

**Files to Create**:
- `backend/workers/celery_app.py` — Celery config, task registration
- `backend/agents/workers/annual_report_worker.py`
- `backend/agents/workers/bank_statement_worker.py`
- `backend/agents/workers/gst_returns_worker.py`
- `backend/agents/ingestor/loaders.py` — Document loaders
- `backend/agents/ingestor/ocr.py` — Tesseract OCR wrapper
- `backend/agents/ingestor/extractor.py` — LLM extraction chains

**Demo Impact**: 🟠 Workers are **visible** in the Worker Status Panel (8 progress bars) and their ThinkingEvents fill the chatbot. This is where judges first see the system "doing work."

---

### T0.7 — Agent 0.5 — The Consolidator (Cross-Verification)

**What**: Waits for all workers to complete, merges their outputs, normalizes schemas, detects cross-document contradictions, and performs the critical **4-way revenue cross-verification** (AR vs ITR vs GST vs Bank).

**Why T0**: Without consolidation, worker outputs are isolated data islands. The 4-way revenue check is the **single most impressive data integrity feature** in the demo. This is where the chatbot starts saying things like *"Revenue: AR ₹312.4cr vs GST ₹308.7cr vs ITR ₹310.1cr vs Bank ₹298.6cr — 4.4% max deviation, within tolerance."*

**What It Includes** (6 internal steps):
1. **Completion Monitor** — Polls Redis staging until all workers report done (or timeout)
2. **Schema Normalization** — Converts all worker outputs to unified `NormalizedExtraction` schema (amounts→lakhs, dates→ISO, names→title-case)
3. **Conflict Detection** — Same data from multiple sources → apply priority: Government (1.0) > Third-party (0.85) > Self-reported (0.70)
4. **Completeness Check** — Mandatory fields present? (Revenue, EBITDA, debt, promoter holding)
5. **Cross-Document Contradiction Detection** — 5 specific checks:
   - Revenue across AR / ITR / GST / Bank (4-way)
   - RPTs in Board Minutes vs Annual Report
   - Litigation disclosure vs actual legal documents
   - Net worth in AR vs ITR balance sheet
   - GSTR-2A vs 3B ITC reconciliation
6. **Build RawDataPackage** — Single Pydantic object with every field tagged: source doc + page + confidence

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| State | CreditAppraisalState (Pydantic v2) | Strict typing, every field traceable |
| LLM | Claude Haiku 3.5 | For semantic comparison of textual contradictions |
| Pub/Sub | Redis → ThinkingEvent bus | Cross-verification results stream to chatbot in real time |

**Files to Create**:
- `backend/graph/nodes/consolidator_node.py` — LangGraph node
- `backend/agents/consolidator/merger.py` — Schema normalization
- `backend/agents/consolidator/contradiction_detector.py` — 5 cross-checks
- `backend/agents/consolidator/completeness_checker.py` — Field validation
- `backend/agents/ingestor/cross_verifier.py` — Revenue 4-way check

**Demo Impact**: 🟠🟠🟠 This is where the chatbot says *"Revenue cross-verified across 4 sources — max deviation 4.4%."* Judges audibly react to this. It's the "oh, this actually works" moment.

---

### T0.8 — Agent 3 — Scorer (0–850) + CAM Writer

**What**: Receives the Evidence Package, computes the INTELLI-CREDIT Score on a 0–850 scale (modeled after CIBIL), derives loan parameters from the score band, and writes the Credit Appraisal Memo section by section.

**Why T0**: The score IS the output. Without it, the Results page is empty. The CAM IS the deliverable. Without it, there's no professional banking document to show judges.

**What It Includes**:
- **6 Scoring Modules** computing independently (Capacity, Character, Capital, Collateral, Conditions, Compound)
- **Hard Block Checker** — 4 overrides (Wilful defaulter→200 cap, Criminal case→150, DSCR<1.0→300, NCLT→250)
- **Per-Point Breakdown** — Every single point has: metric, value, formula, source doc + page + excerpt, benchmark, impact, reasoning, confidence
- **Score Band Derivation** — Score → Band → Loan Amount % → Interest Rate → Conditions
- **CAM Writer** — 8 sections (Executive Summary, Character, Capacity, Capital, Collateral, Conditions, Risk Flags, Decision Rationale), each citing evidence
- **LLM Tiering** — Haiku for structured sections, Sonnet for Executive Summary + Risk Flags + Decision Rationale

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| Scoring Engine | Python + Pydantic v2 | Deterministic computation, every point is a `ScoreBreakdownEntry` |
| CAM Writer | Claude Sonnet 4 (critical) + Claude Haiku 3.5 (bulk) | Quality where it matters, speed elsewhere |
| Output: CAM | python-docx 1.1 | Word document — Indian banking standard (editable post-generation) |
| Output: Score Report | ReportLab 4 | PDF for formal score report |
| Templates | Jinja2 3.1 | CAM section templating |

**Scoring Ranges**:
| Module | Max Up | Max Down |
|---|---|---|
| Capacity | +150 | -100 |
| Character | +120 | -200 |
| Capital | +80 | -80 |
| Collateral | +60 | -40 |
| Conditions | +50 | -50 |
| Compound | +57 | -130 |

**Score Bands**:
| Band | Range | Loan % | Rate |
|---|---|---|---|
| Excellent | 750–850 | 100% | MCLR+1.5% |
| Good | 650–749 | 85% | MCLR+2.5% |
| Fair | 550–649 | 65% | MCLR+3.5% |
| Poor | 450–549 | 40% | MCLR+5.0% |
| Very Poor | 350–449 | Reject | — |
| Default Risk | <350 | Permanent Reject | — |

**Files to Create**:
- `backend/graph/nodes/recommendation_node.py` — LangGraph node
- `backend/agents/recommendation/scorer.py` — Scoring engine runner
- `backend/agents/recommendation/score_modules/capacity_module.py`
- `backend/agents/recommendation/score_modules/character_module.py`
- `backend/agents/recommendation/score_modules/capital_module.py`
- `backend/agents/recommendation/score_modules/collateral_module.py`
- `backend/agents/recommendation/score_modules/conditions_module.py`
- `backend/agents/recommendation/score_modules/compound_module.py`
- `backend/agents/recommendation/hard_blocks.py`
- `backend/agents/recommendation/cam_writer.py`
- `config/prompts/cam_prompts.py` — All CAM section prompts

**Demo Impact**: 🟠🟠🟠 The score gauge (677/850), the per-point breakdown with sources, and the CAM document are the **final deliverables** judges evaluate. This is the "money shot" of the demo.

---

## 🟠 TIER 1 — JUDGE MAGNETS (High Impact — Judges Specifically Evaluate These)

These 8 features are what separate "a working demo" from "a demo that scores well." Hackathon judges in Credit Appraisal / FinTech tracks have specific evaluation criteria — these features directly address them.

---

### T1.1 — GSTR-2A vs 3B Reconciliation (Worker 3 Enhancement)

**What**: Compares Input Tax Credit (ITC) *claimed* in GSTR-3B (self-declared) against ITC *available* per GSTR-2A (auto-populated from supplier filings). If claimed > available → potential fake invoice fraud.

**Why T1**: **Explicitly mentioned in hackathon evaluation criteria.** Fake invoicing is a ₹1 lakh crore problem in India. This check is the gold standard for detecting it. Every judge from a banking background knows what GSTR-2A vs 3B means.

**Technical Detail**:
- Parse GSTR-3B: aggregate ITC claimed across all months
- Parse GSTR-2A: aggregate ITC available (auto-populated by suppliers)
- If 3B > 2A: compute excess claim amount + percentage
- Industry average excess: 3–5% (timing differences are normal)
- Above 10%: flag for review. Above 20%: HIGH severity ticket
- Emit ThinkingEvent: *"⚠️ ITC claimed ₹4.82cr but only ₹4.31cr available per GSTR-2A. Excess: ₹0.51cr (10.6%). Industry avg: 3-5%."*

**Tech Stack**: Pandas 2 (Excel/CSV parsing) + custom GST schema parser + ThinkingEvent emitter

**Files**: `backend/agents/workers/gst_returns_worker.py` (enhance with 2A vs 3B logic)

**Demo Impact**: 🟠🟠 Judges in fintech tracks will **specifically look** for this. Saying "we do GSTR-2A vs 3B" is an instant credibility signal.

---

### T1.2 — RPT Concealment Detection (Board Minutes vs Annual Report)

**What**: Cross-references Related Party Transactions (RPTs) approved in Board Minutes against RPTs disclosed in the Annual Report. If Board Minutes record 3 RPTs but the AR shows only 2, that's **active concealment** — not a timing issue.

**Why T1**: RPT fraud is the most common corporate governance failure in Indian lending. Detecting it automatically is a massive differentiator. The XYZ Steel example in our demo specifically shows this: Board Minutes have 3 RPTs (₹18.2cr), AR discloses only 2 (₹12.1cr), ₹6.1cr concealed.

**Technical Detail**:
- W6 (Board Minutes worker) extracts: all RPT approvals with amounts, counterparties, dates
- W1 (Annual Report worker) extracts: RPT disclosure section, AS-18 / Ind AS 24 disclosures
- Agent 0.5 compares: count, amounts, counterparty names
- Mismatch → CRITICAL ThinkingEvent + HIGH severity ticket with both evidence sets
- Scoring impact: -35 points in Character module (concealment pattern)

**Tech Stack**: Claude Haiku (board minutes are narrative text), Pydantic comparison logic, ThinkingEvent emitter

**Files**: `backend/agents/consolidator/contradiction_detector.py` (RPT cross-check function)

**Demo Impact**: 🟠🟠 The chatbot saying *"⚠️ RPT disclosure in AR lists only 2 transactions (₹12.1cr) — Board Minutes show 3 (₹18.2cr). Potential concealment of ₹6.1cr RPT."* — judges lean forward at this moment.

---

### T1.3 — Neo4j Knowledge Graph (Entity-Relationship Network)

**What**: A graph database storing all entities discovered across documents and research — companies, directors, suppliers, customers, banks, auditors, courts — and their relationships. Powers graph reasoning, cascade risk, hidden relationship detection.

**Why T1**: The knowledge graph IS the "intelligence" in "Intelli-Credit." Without it, you're just a document reader with scoring. With it, you can detect circular trading, cascade risk, and undisclosed related parties — things that no single document reveals.

**What It Includes**:
- **Node Types**: Company, Director, Supplier, Customer, Bank, Auditor, RatingAgency, Court/Case
- **Relationship Types**: `SUPPLIES_TO`, `BUYS_FROM`, `IS_DIRECTOR_OF`, `FAMILY_OF`, `HAS_CHARGE`, `OUTSTANDING_RECEIVABLE`, `IS_AUDITOR_OF`, `HAS_RATING_FROM`, `FILED_CASE_AGAINST`
- **Internal graph** (built by Agent 1.5): entities from submitted documents
- **External enrichment** (built by Agent 2): entities from MCA21 + NJDG + research
- **Graph queries** (used by Agent 2.5): multi-hop traversals for compound insight detection

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| Database | Neo4j Community Edition 5.14 | Purpose-built graph DB, Cypher query language, best Python driver |
| Driver | Neo4j Python driver 5 (async) | Non-blocking writes, connection pooling |
| Community Detection | NetworkX 3 (Louvain method) | Finding clusters of related entities |
| Graph Summarization | Microsoft GraphRAG 0.3 | Hierarchical summarization for LLM multi-hop reasoning |

**Files to Create**:
- `backend/storage/neo4j_client.py` — Async CRUD + Cypher query helpers
- `backend/agents/organizer/graph_builder.py` — Internal graph construction from documents
- `backend/agents/research/neo4j_enricher.py` — External entity enrichment

**Demo Impact**: 🟠🟠 When the chatbot says *"🔗 Cross-directorship detected: Rajesh Agarwal → Agarwal Holdings (NPA) → AK Traders → XYZ Steel supply chain. 3-hop connection."* — this is graph intelligence in action.

---

### T1.4 — Agent 2.5 — Graph Reasoning (5 Passes)

**What**: Takes the complete Neo4j graph (internal + external) and runs 5 structured reasoning passes to find **compound insights** — dangerous patterns invisible in any single document.

**Why T1**: This is the "graph intelligence" that makes Intelli-Credit different from every "LLM reads documents" project. Multi-hop reasoning across the knowledge graph finds cascade risks, circular trading, hidden relationships — the kind of fraud that costs banks crores.

**5 Reasoning Passes**:
| Pass | What It Finds | Example Output |
|---|---|---|
| **Pass 1: Contradictions** | Facts from one source contradict another | *"AR: no litigation. NJDG: active case."* (-45 pts) |
| **Pass 2: Cascade Risk** | Chain reactions from counterparty failure | *"Customer NCLT → 38% revenue at risk → DSCR drops 1.43→0.88"* (-50 pts) |
| **Pass 3: Hidden Relationships** | Undisclosed connections (shared directors, shell companies) | *"Promoter is director of 3 suppliers (shell co.)"* (-60 pts) |
| **Pass 4: Temporal Patterns** | Multi-year deterioration trends | *"DSCR: 2.1→1.6→1.3→projected 0.9"* (-20 pts) |
| **Pass 5: Positive Signals** | Genuine strengths (not just absence of negatives) | *"Order book ₹280cr + PLI ₹12cr subsidy"* (+57 pts) |

**Tech Stack**:
| Component | Technology | Why |
|---|---|---|
| Graph Queries | Neo4j Cypher | Multi-hop traversals, path finding, community detection |
| LLM Reasoning | Claude Haiku 3.5 | Semantic analysis for contradiction and positive signal evaluation |
| Graph Summarization | Microsoft GraphRAG 0.3 | Hierarchical graph context for LLM reasoning window |
| Community Detection | NetworkX 3 | Louvain method for finding entity clusters |

**Files to Create**:
- `backend/graph/nodes/reasoning_node.py` — LangGraph node
- `backend/agents/reasoning/contradiction_pass.py`
- `backend/agents/reasoning/cascade_pass.py`
- `backend/agents/reasoning/hidden_relationship_pass.py`
- `backend/agents/reasoning/temporal_pass.py`
- `backend/agents/reasoning/positive_signal_pass.py`
- `backend/agents/reasoning/insight_store.py`
- `config/prompts/reasoning_prompts.py`

**Demo Impact**: 🟠🟠🟠 The most technically impressive part of the demo. When the chatbot narrates cascade risk calculations in real time with exact numbers, judges understand this isn't a toy.

---

### T1.5 — Evidence Package Builder + Ticket Raiser

**What**: Organizes ALL findings from all previous stages into one structured, fully cited package. Raises tickets for anything ambiguous, conflicting, or high-impact-uncertain. **Agent 3 reads ONLY this package.** It never touches raw data.

**Why T1**: This is the architectural discipline that judges evaluate. "The AI doesn't just guess — it organizes evidence, cites everything, and raises tickets for ambiguity before scoring." This clean separation impresses systems-thinking judges.

**What It Includes**:
- Package organized by 5 Cs: every claim has source document + page + excerpt + confidence + score contribution
- Compound insights from Agent 2.5 with full evidence chains
- Verified vs Uncertain vs Rejected vs Conflicting findings (each shown)
- Ticket raising triggers: contradiction, low confidence extraction, unverified material finding, ML fraud signal without full evidence, management interview discrepancy, finding that would change score by >20 pts

**Ticket Severity Behavior**:
| Severity | Pipeline Action |
|---|---|
| LOW | Pipeline continues, ticket resolved async |
| HIGH | Pipeline pauses at Agent 3, must resolve first |
| CRITICAL | Pipeline stops completely, senior manager notification |

**Files to Create**:
- `backend/graph/nodes/evidence_node.py`
- `backend/agents/evidence/package_builder.py`
- `backend/agents/evidence/ticket_raiser.py`
- `backend/models/evidence_package.py`

**Demo Impact**: 🟠 Not directly visible, but enables clean ticket resolution and fully-cited scoring.

---

### T1.6 — Agent 1.5 — The Organizer (5 Cs + Metrics + ML Suite)

**What**: Takes raw consolidated data and transforms it into an organized, computed, graph-connected, ML-analyzed package. Maps everything to the 5 Cs framework, computes all derived financial metrics, builds the internal Neo4j graph, and runs the ML anomaly detection suite.

**Why T1**: Without organization, the Evidence Package is chaos. Without computed metrics, there's nothing to score. Without the 5 Cs framework, the score has no structure.

**Key Steps**:
1. **Map to 5 Cs**: Every data point tagged (Character/Capacity/Capital/Collateral/Conditions)
2. **Compute Metrics**: DSCR, Current Ratio, D/E, WC Cycle, Revenue CAGR, GST-Bank Divergence, ITR-AR Divergence
3. **Board Minutes Analysis**: Governance signals (CFO changes, RPT approvals, director resignations)
4. **Shareholding Analysis**: Pledge ratio trend, cross-holdings
5. **Build Internal Neo4j Graph**: Nodes + relationships from documents
6. **Run ML Suite**: DOMINANT GNN + Isolation Forest + FinBERT (see T2.4)
7. **Produce FeatureObject + OrganizedPackage**

**Files to Create**:
- `backend/graph/nodes/organizer_node.py`
- `backend/agents/organizer/five_cs_mapper.py`
- `backend/agents/organizer/metric_computer.py`
- `backend/agents/organizer/board_analyzer.py`
- `backend/agents/organizer/shareholding_analyzer.py`
- `backend/agents/organizer/graph_builder.py`
- `backend/agents/organizer/ml_suite.py`

**Demo Impact**: 🟠 The chatbot says *"Computed DSCR: 1.38x — (EBITDA ₹42.6cr - Tax ₹8.1cr) / (Interest ₹18.2cr + Principal ₹6.8cr)"*. Judges see the AI showing its math.

---

### T1.7 — Ticket Resolution Interface (Backend)

**What**: API endpoints + logic for the human-AI dialogue system that resolves conflicts. When a ticket is raised, the officer sees full evidence for both sides, AI recommendation, past precedents, and score impact. The officer resolves, AI asks follow-ups, resolution is stored as a precedent.

**Why T1**: Human-in-the-loop is a **key differentiator**. Not just approve/reject — conversational resolution with follow-up questions. This shows judges the system isn't blindly autonomous; it knows when to ask humans.

**Files to Create**:
- `backend/graph/nodes/ticket_node.py` — LangGraph node (pauses for HIGH tickets)
- `backend/api/routes/tickets.py` — CRUD + resolve endpoints

**Demo Impact**: 🟠🟠 The ticket resolution page is one of 7 pages judges see. It demonstrates responsible AI with human oversight.

---

### T1.8 — Validator Node

**What**: Enforces technical completeness between consolidation and organization. Schema validation (Pydantic strict mode), mandatory document presence, 3-year financial data check, bank statement 12-month coverage, GSTIN live verification, numerical range validation.

**Why T1**: Without validation, bad data flows into scoring. The Validator is the quality gate. It does NOT make judgment calls — it enforces technical correctness.

**Files to Create**:
- `backend/graph/nodes/validator_node.py`

**Demo Impact**: 🟡 Chatbot says *"✅ All 8 mandatory documents received and parsed. Completeness check passed."* Quick but builds confidence.

---

## 🟡 TIER 2 — STRONG DIFFERENTIATORS (Separate Good from Winning)

These 7 features make judges say *"This team thought deeper than everyone else."* Most competing teams won't have these.

---

### T2.1 — MCA21 Scraper (Director Cross-Directorships)

**What**: Scrapes the Ministry of Corporate Affairs portal for ALL companies where the promoter/directors serve. Finds director overlaps with suppliers, customers, related parties. Feeds the Neo4j graph.

**Why T2**: This is how you find circular trading and shell companies. If the promoter is director of a supplier AND a customer → circular trading signal. If a supplier was incorporated 3 months before its first invoice → shell company.

**Fetches**: All directors with DIN, their other companies, registered charges, filing dates, registered address history.

**Tech Stack**: BeautifulSoup 4.12 + Selenium 4.18 (dynamic pages), retry + exponential backoff + cache.

**Files**: `backend/agents/research/scrapers/mca21_scraper.py`

**Demo Impact**: 🟡🟡 *"MCA21: Rajesh K. Agarwal is director in 4 companies — XYZ Steel, Agarwal Holdings, AK Traders, Steel Logistics India."* — judges immediately understand the intelligence value.

---

### T2.2 — NJDG Scraper (Litigation Verification)

**What**: Scrapes the National Judicial Data Grid for ALL pending and disposed court cases against the company. Catches cases that the company didn't disclose in submitted documents.

**Why T2**: Tavily finds cases reported in news. NJDG finds **every** case including unreported district court matters. A ₹2cr cheque bounce case in a district court will never appear in any news API.

**Fetches**: Pending civil cases, disposed cases (5 years), case type, claimant, amounts, court, dates.

**Tech Stack**: BeautifulSoup + Selenium, retry + fallback to cached.

**Files**: `backend/agents/research/scrapers/njdg_scraper.py`

**Demo Impact**: 🟡 *"NJDG: 1 active case — Commercial suit ₹2.3cr. AR disclosure matches — no concealment detected."*

---

### T2.3 — Agent 2 — Research Agent (Tavily + Scrapers)

**What**: The external intelligence gatherer. Runs 5 parallel research tracks (Tavily, Exa, SerpAPI, custom scrapers, regulatory), verifies every finding through a 5-tier credibility engine, and enriches Neo4j with external entities.

**Why T2**: Without external research, the system only analyzes what the company submitted. Companies lie on documents. Independent verification is what makes this an "intelligence system" not a "document reader."

**Minimum for Demo**: Tavily API (primary web search) + MCA21 scraper + NJDG scraper.

**5-Tier Verification Engine**:
| Tier | Source | Weight |
|---|---|---|
| 1 | Government portals (MCA21, SEBI, RBI, NJDG, GST) | 1.0 (fact) |
| 2 | Reputable financial media (ET, BS, Mint, FE) | 0.85 |
| 3 | General/regional news | 0.60 |
| 4 | Blogs, unverified sites | 0.30 |
| 5 | Social media, anonymous | 0.0 (rejected) |

**Tech Stack**: Tavily API v2, Exa API v1, SerpAPI v3, BeautifulSoup, Selenium, Redis cache (7-day TTL), asyncio (all tracks parallel).

**Files to Create**:
- `backend/graph/nodes/research_node.py`
- `backend/agents/research/tavily_search.py`
- `backend/agents/research/verification_engine.py`
- `backend/agents/research/neo4j_enricher.py`
- `config/prompts/extraction_prompts.py` (research extraction prompts)

**Demo Impact**: 🟡🟡 External research findings streaming into the chatbot is visually impressive and intellectually credible.

---

### T2.4 — ML Anomaly Detection Suite (3 Models)

**What**: Three pre-trained open-source ML models run in parallel during Agent 1.5: DOMINANT GNN (circular trading), Isolation Forest (financial ratio anomalies), FinBERT (buried risk in narrative text).

**Why T2**: ML-based anomaly detection is a strong differentiator. Most teams use zero ML. Having 3 models — a GNN, an unsupervised detector, and a financial NLP model — shows serious technical depth.

**3 Models**:
| Model | Library | Purpose | Input | Output |
|---|---|---|---|---|
| **DOMINANT GNN** | PyTorch Geometric 2.4 | Circular trading / shell company detection | Neo4j entity graph | Fraud probability per community (0–1) |
| **Isolation Forest** | scikit-learn | Tabular financial anomaly detection | DSCR, D/E, WC cycle, revenue growth, GST divergence, ITC overclaim | Anomaly score per metric (0–1) |
| **FinBERT** | HuggingFace (ProsusAI/finbert) | Hidden risk in management narrative | Director's Report, MD&A, management commentary | Surface sentiment + buried risk score |

**FinBERT Example**: Text says *"comfortable liquidity position"* → surface sentiment is positive. But context reveals 72% promoter shares pledged → buried risk is HIGH. Surface positive + high buried risk = management masking problems.

**Files to Create**:
- `backend/ml/dominant_gnn.py` — GNN wrapper + model loading
- `backend/ml/isolation_forest.py` — Isolation Forest wrapper
- `backend/ml/finbert.py` — FinBERT wrapper
- `backend/ml/embeddings.py` — Local MiniLM embedding model

**Demo Impact**: 🟡🟡 *"DOMINANT GNN: Circular trading probability 0.84 in entity cluster. Isolation Forest: D/E ratio anomalous (0.91). FinBERT: Buried risk detected (0.89) despite positive surface language."*

---

### T2.5 — ChromaDB Vector Store (RAG + Knowledge Base)

**What**: Vector database for two purposes: (1) RAG retrieval — semantic search over document chunks during CAM writing, (2) Knowledge Base — resolved ticket precedents stored as embeddings for future ticket resolution.

**Why T2**: RAG is essential for CAM quality (Agent 3 needs to cite exact text). The knowledge base is the "institutional learning" story that impresses judges.

**Tech Stack**: ChromaDB 0.5 (open source, local, native LangChain integration), sentence-transformers/all-MiniLM-L6-v2 (384-dim embeddings, CPU, ~20ms/sentence).

**Files to Create**:
- `backend/storage/chromadb_client.py` — Collection management, embed + store + retrieve
- `backend/ml/embeddings.py` — Local embedding model

**Demo Impact**: 🟡 Invisible but enables fully-cited CAM and precedent-based ticket resolution.

---

### T2.6 — Elasticsearch (4-Index Full-Text Search)

**What**: Full-text search engine with 4 indices: `document_store` (extracted text), `research_intelligence` (web findings), `company_profiles` (historical assessments), `regulatory_watchlist` (RBI/SEBI/MCA notifications).

**Why T2**: Enables keyword search across all documents and research, NER-tagged entity search, and regulatory context injection. Complements ChromaDB's semantic search.

**Tech Stack**: Elasticsearch 8.12 + official Python client.

**Files to Create**:
- `backend/storage/elasticsearch_client.py` — 4-index operations

**Demo Impact**: 🟡 Powers search within Decision Store and regulatory context. Not directly visible but adds depth.

---

### T2.7 — Decision Store Writer (Historical Storage)

**What**: After Agent 3 completes, writes the FULL assessment to PostgreSQL's Universal Decision Store — assessment record, complete score breakdown, all findings, all tickets with resolutions, thinking event log, CAM path, LangSmith trace URL.

**Why T2**: The History page and Analytics page read from this. It's the "Nothing Is Lost" principle in action. Every single decision is permanently stored with full evidence trail.

**Files to Create**:
- `backend/graph/nodes/decision_store_node.py`

**Demo Impact**: 🟡 Enables the History page to show real data instead of hardcoded mock.

---

## 🟢 TIER 3 — POLISH & DEPTH (Production-Readiness Signals)

These 8 features signal to judges that this isn't just a hackathon toy — it's architected for production. Do these only after T0–T2 are solid.

---

### T3.1 — Exa Neural Search (Semantic Web Research)

**What**: Second research track using Exa's neural search API. Finds conceptually related content beyond keyword matches — discovers the promoter's OTHER company default even if the current company is never mentioned.

**Tech Stack**: Exa API v1 + LangChain integration.

**Files**: `backend/agents/research/exa_search.py`

**Demo Impact**: 🟢 Adds depth to research findings. Nice-to-have.

---

### T3.2 — SerpAPI Google Wrapper (Indian News)

**What**: Third research track. Google has the deepest Indian news index (ET, Business Standard, Mint, Financial Express, MoneyControl). Domain-specific queries like `"{company} site:economictimes.com"`.

**Tech Stack**: SerpAPI v3 + result parsing.

**Files**: `backend/agents/research/serpapi_search.py`

**Demo Impact**: 🟢 More research breadth. Judges appreciate multi-source.

---

### T3.3 — SEBI Scraper (Enforcement Orders)

**What**: Scrapes SEBI for enforcement orders, adjudication orders, consent orders, debarment orders against the company or promoter. Indicates capital market fraud, insider trading, disclosure violations.

**Files**: `backend/agents/research/scrapers/sebi_scraper.py`

**Demo Impact**: 🟢 Additional government source verification.

---

### T3.4 — RBI Defaulter Scraper (Hard Block Trigger)

**What**: Checks RBI's quarterly wilful defaulter list. If found → **automatic hard block** — score capped at 200, pipeline redirects to rejection path.

**This is one of the 4 hard block triggers.** If the company is a wilful defaulter, nothing else matters.

**Files**: `backend/agents/research/scrapers/rbi_defaulter_scraper.py`

**Demo Impact**: 🟢 Hard block demonstration is impressive but requires RBI test data.

---

### T3.5 — GSTIN Live Verification

**What**: Verifies GSTIN number against the government GST portal in real time. Checks: existence, active status, name match, filing frequency, cancellation status. Catches document fabrication.

**Files**: `backend/agents/research/scrapers/gstin_verifier.py`

**Demo Impact**: 🟢 Anti-fabrication check. *"GSTIN verified — active, name matches, filing regular."*

---

### T3.6 — Management Interview Cross-Referencing

**What**: After Agent 2 completes, management claims from the interview form are cross-referenced against documentary evidence and research findings. Discrepancies flagged.

**Example**: Management says "no related party suppliers" but MCA21 shows director overlap → FLAGGED + ticket.

**Files**: Enhancement to organizer_node.py or a dedicated interview verification step.

**Demo Impact**: 🟢 Shows the system doesn't blindly trust management.

---

### T3.7 — RAG-Based Institutional Learning (Precedent System)

**What**: Every resolved ticket becomes a precedent in ChromaDB with a pattern fingerprint. When a new similar ticket is raised, top 3 precedents shown with outcomes. Over time, system improves.

**Why**: This is the "institutional knowledge" story. When a senior analyst retires, their pattern recognition doesn't leave — it's in the knowledge base.

**Files**: Enhancement to ticket resolution flow + ChromaDB writes.

**Demo Impact**: 🟢🟢 Compelling narrative: *"In a similar steel sector case, senior manager resolved as X. That loan was repaid on schedule."*

---

### T3.8 — LangSmith Full Tracing

**What**: Every LLM call, agent decision, and tool use automatically traced via LangSmith. Judges can click a link and see the complete execution trace.

**Tech Stack**: LangSmith (free tier sufficient), LangChain automatic integration.

**Setup**: Set `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT=intelli-credit` in `.env`.

**Demo Impact**: 🟢🟢 A LangSmith trace link in the Results page adds massive credibility. Judges who know LangSmith will be deeply impressed.

---

## 🔵 TIER 4 — STRETCH GOALS (Only If Everything Else Is Perfect)

These 6 features add value but zero impact if missing. Do these only if T0–T3 are bulletproof and battle-tested.

---

### T4.1 — Docker Compose Full Deployment

**What**: `docker-compose up -d` spins up all 10 services (API, workers, frontend, Redis, PostgreSQL, Neo4j, Elasticsearch, ChromaDB, Flower, Nginx).

**Why**: One-command deployment impresses infrastructure-minded judges. Shows production-readiness.

**Files**: `docker-compose.yml`, `Dockerfile.api`, `Dockerfile.worker`, `Dockerfile.frontend`, `nginx.conf`

---

### T4.2 — GraphRAG Integration (Microsoft)

**What**: Hierarchical graph summarization for multi-hop LLM reasoning over the Neo4j graph. Creates community summaries at different granularity levels.

**Why**: Extends Agent 2.5's reasoning capability with global graph understanding.

**Files**: Integration in `backend/agents/reasoning/` passes.

---

### T4.3 — Regulatory Intelligence Feed

**What**: Daily crawler indexing RBI circulars, SEBI regulations, MCA notifications, GST council decisions into Elasticsearch `regulatory_watchlist` index. When assessment runs, queries sector-relevant regulations from last 6 months.

**Files**: `backend/agents/research/regulatory_feed.py`

---

### T4.4 — Officer Notes Panel

**What**: Free-form note-taking by credit officer during assessment review. Notes attached to specific findings/tickets, categorized (Observation/Concern/Follow-up/Override Justification), full-text searchable.

**Files**: Frontend component + PostgreSQL table + API endpoints.

---

### T4.5 — Compliance Auto-Flagging Workflow

**What**: When specific conditions trigger (undisclosed RPTs, SEBI violations, RBI defaulter, fraud signal > threshold), the system automatically flags the assessment for compliance review and generates a notification.

**Files**: Enhancement to Evidence Package Builder + Decision Store.

---

### T4.6 — Flower Worker Monitor (Embedded)

**What**: Celery Flower dashboard embedded as iframe showing all 8 workers with real-time status, task queue, CPU/memory, retry tracking.

**Why**: Visually impressive for demos — seeing 8 workers running in parallel.

**Setup**: Flower runs as a separate container, embedded in frontend via FlowerEmbed component.

---

## Implementation Priority Matrix

```
                    HIGH DEMO IMPACT
                         │
    T0.3 ThinkingBus ●   │   ● T1.4 Graph Reasoning
    T0.8 Scorer+CAM  ●   │   ● T1.2 RPT Detection
    T0.7 Consolidator ●  │   ● T2.4 ML Suite
                          │   ● T1.1 GST 2A vs 3B
                          │
 LOW ─────────────────────┼──────────────────── HIGH
 EFFORT                   │                    EFFORT
                          │
    T0.1 FastAPI ●        │   ● T2.1 MCA21 Scraper
    T0.5 Redis ●          │   ● T2.3 Research Agent
    T1.8 Validator ●      │   ● T1.3 Neo4j Graph
    T0.4 PostgreSQL ●     │
                          │
                    LOW DEMO IMPACT
```

---

## Recommended Build Order (Day-by-Day for 48h Hackathon)

### Day 1 — Morning (Hours 1–6): Foundation
1. T0.1 — FastAPI skeleton + WebSocket endpoints
2. T0.5 — Redis setup
3. T0.4 — PostgreSQL schema + client
4. T0.2 — LangGraph orchestrator + CreditAppraisalState
5. T0.3 — ThinkingEvent bus (Redis → WebSocket → UI)

### Day 1 — Afternoon (Hours 7–12): Workers + Intelligence
6. T0.6 — At least 3 Celery workers (AR, Bank, GST)
7. T0.7 — Agent 0.5 Consolidator (revenue cross-verification)
8. T1.8 — Validator node
9. T1.6 — Agent 1.5 Organizer (5 Cs + metrics)
10. T1.1 — GSTR-2A vs 3B (enhance GST worker)

### Day 1 — Evening (Hours 13–16): Graph + Research
11. T1.3 — Neo4j graph setup + internal graph build
12. T2.1 — MCA21 scraper
13. T2.2 — NJDG scraper
14. T2.3 — Agent 2 Research (Tavily + scrapers)

### Day 2 — Morning (Hours 17–24): Reasoning + Scoring
15. T1.4 — Agent 2.5 Graph Reasoning (5 passes)
16. T1.5 — Evidence Package Builder + ticket raiser
17. T1.2 — RPT concealment detection
18. T0.8 — Agent 3 Scorer + CAM Writer

### Day 2 — Afternoon (Hours 25–32): ML + Polish
19. T2.4 — ML Suite (DOMINANT GNN + Isolation Forest + FinBERT)
20. T2.5 — ChromaDB RAG + knowledge base
21. T1.7 — Ticket resolution backend
22. T2.7 — Decision Store writer
23. Connect frontend to real backend (replace mock data with API calls)

### Day 2 — Evening (Hours 33–40): Depth + Demo Prep
24. T3.7 — RAG precedent system
25. T3.8 — LangSmith tracing
26. T2.6 — Elasticsearch indices
27. T3.3–T3.5 — Additional scrapers (if time)
28. End-to-end testing with XYZ Steel sample documents
29. Demo script rehearsal

### Final Hours (Hours 41–48): Lock & Test
30. Fix bugs, fix bugs, fix bugs
31. Verify all 7 frontend pages work with real backend data
32. Verify fallback to mock data if backend is down
33. Record video backup of working demo
34. Prepare slides + talking points

---

## What Judges Will Actually Look At (5-Minute Demo Checklist)

In order of impact:

1. **Live Thinking Chatbot** — AI narrating its reasoning in real time (T0.3, T0.6, T0.7)
2. **Score Breakdown** — 677/850 with per-point sourcing: metric, value, formula, document, page (T0.8)
3. **Cross-Verification** — Revenue checked across 4 sources, RPT checked across 2 (T0.7, T1.2)
4. **GSTR-2A vs 3B** — ITC mismatch detection (T1.1)
5. **Graph Intelligence** — Cascade risk, hidden relationships, circular trading (T1.3, T1.4)
6. **Ticket Resolution** — Human-AI dialogue for conflicts (T1.5, T1.7)
7. **CAM Document** — Professional banking document with citations (T0.8)
8. **ML Models** — GNN + Isolation Forest + FinBERT (T2.4)
9. **Historical Decision Store** — Every decision stored, outcome-tracked (T2.7)
10. **Architecture Depth** — LangGraph, 4 databases, 5 scrapers, 8 workers (the breadth)

---

*Last updated: March 6, 2026*
*For: Intelli-Credit Hackathon — Credit Appraisal / FinTech Track*
