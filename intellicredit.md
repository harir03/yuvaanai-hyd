# INTELLI-CREDIT — PPT Content Guide & Video Script Reference

> This document contains **exactly what to put on each slide** of the presentation, **what to say in the video script** during the prototype demo, and **what judges will specifically look for** at each stage. Every section is written from the judges' perspective.

---

## WHAT JUDGES CARE ABOUT (Keep This In Mind For Every Slide)

```
┌──────────────────────────────────────────────────────────────┐
│  JUDGE'S MENTAL SCORECARD (what they're evaluating silently) │
├──────────────────────────────────────────────────────────────┤
│  1. Did they actually understand the problem?                │
│  2. Is this technically sound or just buzzwords?              │
│  3. Can this actually work or is it theoretical?             │
│  4. What makes this different from every other team?         │
│  5. Did they think about edge cases and real-world use?      │
│  6. Is the demo real or a mockup?                            │
│  7. Can this scale beyond a hackathon?                       │
│  8. Do they know WHY they chose each technology?             │
└──────────────────────────────────────────────────────────────┘
```

**The single biggest differentiator**: Most teams will build a "document reader + LLM summarizer." You built a **multi-agent intelligence system** with graph reasoning, ML anomaly detection, real-time transparency, and institutional learning. Make this contrast visible in EVERY slide.

---

## PPT STRUCTURE — SLIDE BY SLIDE

---

### SLIDE 1: Title Slide

**On the slide:**
```
INTELLI-CREDIT
AI-Powered Credit Decisioning Engine

"From 3 weeks of manual review to 4 minutes of
 transparent, source-traced, AI-driven intelligence"

Team Name | Hackathon Name | Date
```

**What to SAY (script):**
> "Intelli-Credit doesn't just read documents and summarize them. It reads, cross-verifies, researches independently, detects fraud through graph intelligence, scores on a 850-point scale with every single point traced to a specific document and page number, and shows the credit officer its complete reasoning in real time. Let me show you exactly how."

**Why this matters to judges:**
They've seen 10 teams say "we use AI to read documents." Your opening line must immediately signal: this is architecturally deeper than anything else they'll see today.

---

### SLIDE 2: The Problem — Make Judges FEEL It

**On the slide:**

```
THE PROBLEM: ₹50 CRORE DECISION ON INCOMPLETE INFORMATION

Current State:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄  847 pages of documents              → 1 analyst reads them sequentially
🔍  Zero independent research           → Trusts what company submitted
🧮  Manual ratio computation            → Excel, prone to formula errors
🕐  2-3 weeks per application           → Bottleneck of 100s pending
🔗  No cross-document verification      → Revenue in AR ≠ Revenue in ITR? Nobody checks.
🕳️  Director networks invisible         → Promoter owns supplier? Nobody knows.
📊  Approve/reject binary               → No nuanced scoring
🔒  Decision reasoning lost             → "Why was this rejected?" — nobody remembers
🎓  Institutional knowledge walks out   → Senior analyst retires, 30 years of patterns gone
```

**What to SAY (script):**
> "A credit officer today receives 847 pages across 8 different document types for a single ₹50 crore loan application. They read them sequentially over 2-3 weeks. They compute ratios in Excel. They trust the company's own disclosures because they don't have time to independently verify. They don't check if the promoter secretly owns their own suppliers. They don't check if the revenue declared in the annual report matches what was filed with the Income Tax department or the GST portal. And when they finally make a decision, the reasoning behind it is lost — it lives in one person's head. When that person retires, 30 years of pattern recognition walks out the door."

**Why this matters to judges:**
You're not describing a generic problem. You're describing **specific failure modes** that result in NPAs (Non-Performing Assets). Judges from banking backgrounds will nod at every single point. This shows you actually understand the domain, not just the tech.

**Key phrase to emphasize:** _"The problem isn't reading speed. The problem is that no human can hold 847 pages in their head simultaneously and spot the contradiction between page 34 of the Annual Report and page 12 of the Board Minutes."_

---

### SLIDE 3: Our Solution — The 30-Second Elevator Pitch

**On the slide:**

```
INTELLI-CREDIT: NOT A DOCUMENT READER. AN INTELLIGENCE SYSTEM.

┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  8 PARALLEL  │    │  5 RESEARCH │    │   GRAPH     │
│  DOCUMENT    │───▶│  TRACKS +   │───▶│  REASONING  │───▶ SCORE: 0-850
│  WORKERS     │    │  5 SCRAPERS │    │  5 PASSES   │    every point sourced
└─────────────┘    └─────────────┘    └─────────────┘

          + LIVE AI THINKING CHATBOT
          The officer sees EVERYTHING the AI reads,
          thinks, accepts, rejects — in real time.

3 weeks → 4 minutes
Manual → 8 parallel AI agents
Trust-based → Cross-verified across every source
Black box → Every decision traced to document + page
Lost knowledge → Permanently stored, outcome-tracked
```

**What to SAY (script):**
> "Intelli-Credit is a multi-agent credit decisioning engine. It reads all 8 document types simultaneously through 8 parallel workers. It then consolidates, cross-verifies, and organizes the data — computing every financial metric automatically. It independently researches the company through 5 web search tracks and 5 custom Indian government portal scrapers. A dedicated graph reasoning agent connects dots across all data — finding circular trading patterns, undisclosed related parties, and cascade risks that no single document would reveal. And then it scores the company on 0 to 850 — like CIBIL — with every single point traced back to a specific document, page, and paragraph. The entire time, the credit officer watches the AI think in real time through a live chatbot."

**Why this matters to judges:**
This is where you plant the hook. Three things will register: (1) parallel processing — not sequential, (2) independent research — not just reading what's given, (3) graph reasoning — connecting dots across documents. No other team will have all three.

---

### SLIDE 4: Architecture Overview — THE MONEY SLIDE

**On the slide (full-page architecture diagram):**

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│   📤 UPLOAD PORTAL          🧠 LIVE THINKING CHATBOT          📊 SCORE DASHBOARD   │
│   8 docs + company info     Real-time AI reasoning feed        0-850 with breakdown │
│   Management interview      Every agent named, every doc       Per-point drill-down │
│                             cited, every decision shown                              │
│                                                                                     │
│   ◄─────────────── WebSocket (bidirectional real-time) ──────────────────────────►  │
│                                                                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│   FastAPI + Pydantic v2 + JWT Auth + Rate Limiting                                  │
│   ↓ Tasks dispatched to Redis queue                                                │
│                                                                                     │
├───────┬───────┬───────┬───────┬───────┬───────┬───────┬─────────────────────────────┤
│ W1    │ W2    │ W3    │ W4    │ W5    │ W6    │ W7    │ W8                          │
│Annual │Bank   │GST    │ITR    │Legal  │Board  │Share  │Rating                       │
│Report │Stmt   │Returns│       │Notice │Minutes│holding│Report    ◄── 8 PARALLEL     │
│       │       │       │       │       │       │       │              CELERY WORKERS  │
│Unstr. │Camelot│GSTR2A │Custom │Claude │Claude │Camelot│Claude                       │
│+OCR   │+Pandas│vs 3B  │XML    │Haiku  │Haiku  │+Pandas│Haiku                        │
├───────┴───────┴───────┴───────┴───────┴───────┴───────┴─────────────────────────────┤
│                              ↓ All outputs → Redis Staging                          │
│                                                                                     │
│   AGENT 0.5 — THE CONSOLIDATOR                                                     │
│   ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌─────────────┐ ┌───────────────────┐ │
│   │Wait for  │→│Normalize │→│Revenue cross-│→│RPT cross-   │→│Build RawData     │ │
│   │all 8     │ │schemas   │ │check: AR vs  │ │check: Board │ │Package with      │ │
│   │workers   │ │& amounts │ │ITR vs GST vs │ │Minutes vs AR│ │every field tagged │ │
│   │          │ │          │ │Bank (3-way)  │ │(concealment │ │with source doc   │ │
│   │          │ │          │ │              │ │detection)   │ │+ page + conf.    │ │
│   └──────────┘ └──────────┘ └──────────────┘ └─────────────┘ └───────────────────┘ │
│                              ↓                                                      │
│   VALIDATOR → Pydantic schema + GSTIN live verification against govt portal         │
│                              ↓                                                      │
│   AGENT 1.5 — THE ORGANIZER                                                        │
│   ┌──────────┐ ┌───────────┐ ┌───────────┐ ┌────────────────────────────────┐      │
│   │Map to    │→│Compute all│→│Build Neo4j│→│ ML ANOMALY SUITE (parallel)   │      │
│   │5 Cs:     │ │metrics:   │ │internal   │ │                                │      │
│   │Character │ │DSCR       │ │graph:     │ │  🧠 DOMINANT GNN              │      │
│   │Capacity  │ │Current    │ │Directors  │ │     → Circular trading: 0.84   │      │
│   │Capital   │ │D/E Ratio  │ │Suppliers  │ │  📊 Isolation Forest           │      │
│   │Collateral│ │WC Cycle   │ │Customers  │ │     → Ratio anomalies: 0.91   │      │
│   │Conditions│ │Revenue    │ │Banks      │ │  📝 FinBERT                    │      │
│   │          │ │CAGR       │ │Charges    │ │     → Buried risk: 0.89       │      │
│   │          │ │GST-Bank   │ │Ratings    │ │                                │      │
│   │          │ │divergence │ │47 nodes   │ │  "Comfortable liquidity" BUT   │      │
│   │          │ │ITR-AR gap │ │89 edges   │ │  72% shares pledged = MASKING │      │
│   └──────────┘ └───────────┘ └───────────┘ └────────────────────────────────┘      │
│                              ↓                                                      │
│   AGENT 2 — THE RESEARCH AGENT (5 parallel tracks)                                 │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐ ┌────────────┐      │
│   │ TAVILY   │ │ EXA      │ │ SERPAPI   │ │ 5 INDIA SCRAPERS │ │ REGULATORY │      │
│   │ AI-native│ │ Neural   │ │ Google   │ │                  │ │ WATCHLIST  │      │
│   │ web      │ │ semantic │ │ Indian   │ │ MCA21: Directors │ │            │      │
│   │ search   │ │ search   │ │ news     │ │ NJDG: Court cases│ │ RBI/SEBI   │      │
│   │          │ │          │ │ (ET,BS,  │ │ SEBI: Orders     │ │ circulars  │      │
│   │          │ │ Finds    │ │  Mint)   │ │ RBI: Defaulters  │ │ sector     │      │
│   │          │ │ promoter │ │          │ │ GSTIN: Verify    │ │ updates    │      │
│   │          │ │ OTHER co │ │          │ │                  │ │            │      │
│   │          │ │ defaults │ │          │ │ → All write to   │ │            │      │
│   │          │ │          │ │          │ │   Neo4j graph    │ │            │      │
│   └──────────┘ └──────────┘ └──────────┘ └──────────────────┘ └────────────┘      │
│          ↓ All findings pass through VERIFICATION ENGINE (5-tier credibility)       │
│          ↓ Government source = 1.0 | Reputable media = 0.85 | Blog = 0.30          │
│                              ↓                                                      │
│   AGENT 2.5 — GRAPH REASONING (5 passes over complete Neo4j graph)                 │
│   ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────┐ ┌──────────┐ │
│   │ PASS 1        │ │ PASS 2        │ │ PASS 3        │ │ PASS 4   │ │ PASS 5   │ │
│   │ Contradiction │ │ Cascade Risk  │ │ Hidden        │ │ Temporal │ │ Positive │ │
│   │               │ │               │ │ Relationships │ │ Patterns │ │ Signals  │ │
│   │ AR says no    │ │ Customer in   │ │               │ │          │ │          │ │
│   │ litigation    │ │ NCLT → 38%    │ │ Promoter is   │ │ DSCR:    │ │ Order    │ │
│   │ BUT NJDG has  │ │ revenue at    │ │ director of 3 │ │ 2.1→1.6  │ │ book     │ │
│   │ active case   │ │ risk → DSCR   │ │ suppliers     │ │ →1.3     │ │ ₹280cr   │ │
│   │               │ │ 1.43→0.88    │ │ (shell co.)   │ │ →0.9?    │ │ +PLI     │ │
│   │ -45 pts       │ │ -50 pts       │ │ -60 pts       │ │ -20 pts  │ │ +57 pts  │ │
│   └───────────────┘ └───────────────┘ └───────────────┘ └──────────┘ └──────────┘ │
│                              ↓                                                      │
│   EVIDENCE PACKAGE BUILDER → Organize by 5 Cs, cite every claim                    │
│   TICKETING LAYER → Human resolves conflicts, AI dialogue, RAG precedents           │
│                              ↓                                                      │
│   AGENT 3 — RECOMMENDATION ENGINE                                                  │
│   ┌──────────────────────────────────────────────────────────────────────────┐      │
│   │ INTELLI-CREDIT SCORE: 477 / 850                                         │      │
│   │ Band: POOR | Conditional Approval: ₹20cr at 13.5%                       │      │
│   │                                                                          │      │
│   │ Capacity: +42 | Character: -80 | Capital: -5                            │      │
│   │ Collateral: +35 | Conditions: +15 | Compound: -130                      │      │
│   │                                                                          │      │
│   │ CAM Writer: Haiku (bulk sections) + Sonnet (Executive Summary + Risk)   │      │
│   │ Every sentence cites: [Document, Page, Table]                           │      │
│   └──────────────────────────────────────────────────────────────────────────┘      │
│                              ↓                                                      │
│   UNIVERSAL DECISION STORE                                                          │
│   ALL outcomes: Approvals + Rejections + Fraud + Escalations                        │
│   Outcome tracking when loan matures → validates AI accuracy                        │
│                                                                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                          INTELLIGENCE LAYER                                         │
│                                                                                     │
│   ChromaDB          Neo4j            Elasticsearch       PostgreSQL                 │
│   (Semantic         (Knowledge       (Full-text +        (Scores, Insights,         │
│    vectors,          Graph,           NER, 4 indices)     Tickets, Decisions,        │
│    RAG KB)           GraphRAG)                            Outcomes, Thinking)        │
│                                                                                     │
│                    Redis: Queue + Cache + Pub/Sub Event Bus                          │
│                    ↓ Thinking events → WebSocket → Live Chatbot                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**What to SAY (script — walk through the diagram top to bottom):**
> "Let me walk you through the complete architecture. At the top, the credit officer uploads 8 documents and fills in company information. All 8 documents go to 8 parallel Celery workers — they process simultaneously, not one after another. Each worker is specialized: the Annual Report worker uses Unstructured.io for complex layouts plus Tesseract OCR for scanned pages. The bank statement worker uses Camelot for table extraction plus Pandas for time-series analysis. The GST worker does the critical GSTR-2A vs 3B reconciliation.
>
> All outputs land in Agent 0.5, the Consolidator. This is where we do something no other system does — 3-way revenue cross-verification. We check: does the revenue in the Annual Report match what was declared to the Income Tax department in the ITR, match what was filed on the GST portal, and match what actually flowed through the bank account? A 4-way cross-check. We also cross-check: did the board minutes approve 5 related party transactions but the annual report only disclosed 2? That's active concealment. We catch that.
>
> Then Agent 1.5 organizes everything into the 5 Cs of credit, computes every financial metric, builds a Neo4j knowledge graph, and runs 3 ML models in parallel: DOMINANT GNN for circular trading detection, Isolation Forest for ratio anomalies, and FinBERT for hidden risk in management language.
>
> Agent 2 goes external — 5 research tracks running in parallel. Tavily for general web, Exa for semantic neural search, SerpAPI for Indian news, and then 5 custom scrapers we built specifically for Indian government portals: MCA21 for director networks, NJDG for court cases, SEBI for enforcement orders, RBI for wilful defaulter status, and GSTIN for document fabrication detection. Every research finding is verified through a 5-tier credibility engine before it touches the scoring.
>
> Agent 2.5 is where the magic happens — 5 graph reasoning passes over the complete Neo4j graph. It finds contradictions across documents, cascade risks if a customer goes bankrupt, hidden relationships through director network analysis, multi-year deterioration trends, and genuine positive signals. These compound insights are what no human analyst could find by reading reports sequentially.
>
> Finally Agent 3 scores 0 to 850 with every point sourced, writes the CAM section by section, and everything — approvals, rejections, fraud detections — is stored permanently in the Universal Decision Store. And the entire time, the credit officer watches via the Live Thinking Chatbot."

**Why this matters to judges:**
This is the slide they'll photograph. Make it clean. This diagram shows **depth** — not "we put documents into an LLM and get output." Every box has a reason to exist.

---

### SLIDE 5: The Three Things No Other Team Will Have

**On the slide:**

```
OUR THREE UNFAIR ADVANTAGES

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. DIRECTOR NETWORK INTELLIGENCE
   ┌─────────────────────────────────────────────────────┐
   │  MCA21 Scraper fetches ALL companies a director     │
   │  is associated with (current + historical).         │
   │                                                     │
   │  (Rajesh Shah)──[DIRECTOR_OF]──▶(XYZ Steel)         │
   │  (Rajesh Shah)──[DIRECTOR_OF]──▶(Supplier A)  🚨    │
   │  (Rajesh Shah)──[DIRECTOR_OF]──▶(Supplier B)  🚨    │
   │  (Priya Shah)───[DIRECTOR_OF]──▶(Supplier C)  🚨    │
   │  (Priya Shah)───[FAMILY_OF]────▶(Rajesh Shah)       │
   │                                                     │
   │  Result: 3 of 5 top suppliers controlled by         │
   │  promoter = circular trading network                │
   │  DOMINANT GNN confirms: 0.84 probability            │
   └─────────────────────────────────────────────────────┘

2. LIVE AI THINKING CHATBOT
   ┌─────────────────────────────────────────────────────┐
   │  Not logs. Not summaries. The actual AI reasoning   │
   │  in real time:                                      │
   │                                                     │
   │  📄 "Reading Annual Report pg 67..."                │
   │  ✅ "Found EBITDA ₹18,200L — accepted"              │
   │  🚨 "Board Minutes show 5 RPTs, AR shows 2!"       │
   │  🔗 "Connecting: Greenfield NCLT → DSCR drops"     │
   │  💡 "Cascade scenario: DSCR 1.43 → 0.88"           │
   │                                                     │
   │  Officer sees everything. Catches AI mistakes.      │
   │  Builds trust. Judges LOVE this in demo.            │
   └─────────────────────────────────────────────────────┘

3. GRAPH REASONING — CONNECTING DOTS HUMANS CAN'T
   ┌─────────────────────────────────────────────────────┐
   │  Individual facts look acceptable:                  │
   │    DSCR 1.43x ✓  |  Revenue growing ✓              │
   │    No criminal cases ✓  |  Collateral exists ✓     │
   │                                                     │
   │  But connected together:                            │
   │    Customer (38% revenue) in NCLT insolvency        │
   │    → Revenue drops 38%                              │
   │    → DSCR recalculated: 0.88x                      │
   │    → Below loan covenant threshold                  │
   │    → Company CANNOT repay loan                      │
   │                                                     │
   │  This cascade is invisible to sequential readers.   │
   │  Only a knowledge graph reveals it.                 │
   └─────────────────────────────────────────────────────┘
```

**What to SAY (script):**
> "Let me highlight three capabilities that fundamentally differentiate us. First, director network intelligence. Our MCA21 scraper fetches every company a director has ever been associated with from the Ministry of Corporate Affairs and maps them into a Neo4j knowledge graph. In our demo case, the promoter Rajesh Shah turns out to be director of 3 of the company's own suppliers. His wife directs a 4th. That's circular trading — money going from the company to the promoter through fake supplier invoices. No document tells you this directly. Our graph finds it.
>
> Second, the Live Thinking Chatbot. The credit officer isn't waiting for a final answer. They're watching the AI read, extract, flag, and decide in real time. They see 'Reading Annual Report page 67... Found EBITDA ₹18,200 lakhs... Accepted.' They see 'Board Minutes show 5 related parties, Annual Report shows 2 — critical contradiction detected!' This transparency is what turns an AI tool into a trusted colleague.
>
> Third, graph reasoning. Individual data points look fine. DSCR 1.43x is acceptable. Revenue is growing. No criminal cases. But when you connect the dots through the knowledge graph, you discover that 38% of revenue depends on one customer who just filed for insolvency. Remove that customer, DSCR drops to 0.88x — below the repayment threshold. The company physically cannot repay the loan. This cascade is invisible to anyone reading documents one by one. Only a knowledge graph reveals it."

**Why this matters to judges:**
These three features are your "wow factor." Every other team will have document parsing and LLM summarization. Nobody else will have director network graphing, real-time AI thinking, and cascade risk modeling. Plant this in judges' minds early.

---

### SLIDE 6: Cross-Document Intelligence — The Verification Layer

**On the slide:**

```
WHAT WE CROSS-VERIFY (that nobody else does)

                    Annual      GST        ITR       Bank
                    Report     Returns    Filing    Statement
                    ─────────  ─────────  ────────  ─────────
Revenue             ₹124.5cr   ₹118.7cr   ₹98.2cr   ₹71.4cr
                         ↑         ↑          ↑          ↑
                         │    4.7% gap    21% gap!   42% gap!!
                         │         │          │          │
                    Self-     Govt      Govt       Actual
                    reported  filing    filing     cash flow
                    
Question: WHICH NUMBER IS REAL?

Priority Rule: Government filing > Third-party > Self-reported
Answer: GST figure ₹118.7cr is primary. AR inflated by ₹5.8cr.
        ITR-AR gap of 21% = potential dual accounting.
        Bank-GST gap = not all revenue flows through this account.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RPT CONCEALMENT DETECTION:

Board Minutes (Oct 2023):        Annual Report (Mar 2024):
"Approved transactions with       "Related party transactions
 5 entities: ₹45cr total"         with 2 entities: ₹21.8cr"

  5 ≠ 2 → 3 entities HIDDEN → ₹18cr undisclosed
  Same financial year. Same company. Same board.
  This is ACTIVE CONCEALMENT. Not a timing issue.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GSTR-2A vs GSTR-3B RECONCILIATION:

ITC Claimed (GSTR-3B):    ₹22,100 lakhs
ITC Available (GSTR-2A):  ₹18,400 lakhs
                           ─────────────
EXCESS CLAIMED:            ₹3,700 lakhs  🚨

If you claim more input tax credit than what suppliers
actually filed → you're using FAKE INVOICES.
```

**What to SAY (script):**
> "This slide shows what happens when you cross-verify instead of trusting. The Annual Report says revenue is ₹124.5 crores. But the GST filing — submitted to the government, with legal consequences for lying — says ₹118.7 crores. The ITR — also submitted to the government — says ₹98.2 crores. And the bank statement — actual money flowing — shows only ₹71.4 crores. These are four different numbers for the same thing. Our system catches this automatically, applies a priority rule — government filings beat self-reported data — and flags the discrepancy. The 21% gap between the Annual Report and the ITR is a hard signal of potential dual accounting.
>
> Even more damning: the board minutes approved transactions with 5 related parties totaling ₹45 crores. The annual report, published to shareholders, disclosed only 2 parties and ₹21.8 crores. Three entities and ₹18 crores were deliberately hidden. This is in the same financial year. Same company. Same board that approved them. This is not a timing issue — it's active concealment. Our system catches this because Agent 0.5 explicitly cross-references board minutes against the annual report.
>
> And the GSTR-2A vs 3B reconciliation: if you claim more input tax credit than your suppliers actually filed in their returns, you're using invoices from suppliers that don't exist. Fake invoices. ₹3,700 lakhs of excess ITC claimed. This is a specific evaluation criterion the judges will look for."

**Why this matters to judges:**
This is your **credibility slide**. It proves you understand Indian accounting, Indian tax law, and the specific fraud patterns that cause NPAs. Judges with banking experience will be deeply impressed by the GSTR-2A/3B cross-check and RPT concealment detection.

---

### SLIDE 7: The ML Anomaly Detection Suite

**On the slide:**

```
THREE PRE-TRAINED ML MODELS — RUNNING IN PARALLEL

┌──────────────────────────────────────────────────────────────┐
│ 🧠 DOMINANT GNN                                              │
│ Graph Neural Network for Financial Fraud                     │
│                                                              │
│ Input:  Neo4j entity-relationship graph                      │
│ Detects: Circular trading, shell companies, related-party    │
│          networks through unusually dense entity clusters     │
│                                                              │
│ Pre-trained: Financial transaction graphs                    │
│ Fine-tuned:  SEBI enforcement order descriptions             │
│              (real Indian fraud patterns)                     │
│                                                              │
│ Library:  PyTorch Geometric                                  │
│ Output:   Fraud probability per community (0–1)              │
│           Score > 0.7 = investigate                          │
│           Score > 0.85 = high confidence fraud               │
│                                                              │
│ WHY NOT rule-based? Rules catch known patterns.              │
│ GNN finds NOVEL patterns by learning graph structure.        │
│ A new circular trading setup with different entity types     │
│ would evade rules but NOT a trained GNN.                     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 📊 ISOLATION FOREST                                          │
│ Unsupervised Tabular Anomaly Detection                       │
│                                                              │
│ Input:  Financial ratios — DSCR, D/E, WC cycle, revenue     │
│         growth, GST-Bank divergence, ITC overclaim ratio     │
│ Detects: Metrics that statistically don't fit                │
│                                                              │
│ Library:  scikit-learn                                       │
│ Training: UNSUPERVISED — no labeled data needed              │
│           Learns what "normal" looks like,                   │
│           flags what doesn't fit                             │
│                                                              │
│ WHY NOT one-class SVM? Isolation Forest was specifically     │
│ designed for anomaly detection. Benchmark-proven superior    │
│ on tabular financial data.                                   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ 📝 FINBERT (ProsusAI)                                        │
│ Financial Language Risk Detection                            │
│                                                              │
│ Input:  Director's Report, MD&A, management commentary       │
│ Detects: Hidden risk behind positive language                │
│                                                              │
│ Pre-trained: Financial news, earnings calls, annual reports  │
│                                                              │
│ Example:                                                     │
│   Text: "comfortable liquidity notwithstanding temporary     │
│          working capital pressures"                          │
│   Surface sentiment: POSITIVE (0.72)                         │
│   Buried risk score: HIGH (0.89)                             │
│   Translation: Company has cash flow problems.               │
│                Management is masking it.                      │
│                                                              │
│ WHY NOT vanilla BERT? FinBERT's pre-training domain          │
│ matches our use case EXACTLY. Vanilla BERT doesn't know      │
│ that "headwinds" in a financial report = negative signal.    │
└──────────────────────────────────────────────────────────────┘
```

**What to SAY (script):**
> "Three ML models run in parallel during Agent 1.5. DOMINANT GNN is a graph neural network from PyTorch Geometric, pre-trained on financial transaction graphs and fine-tuned on SEBI enforcement order descriptions — real Indian fraud case patterns. It doesn't use rules. It learns graph structure. So when a promoter builds a new circular trading network using a different entity structure that no rule has seen before, the GNN still catches it because the graph pattern is anomalous.
>
> Isolation Forest from scikit-learn is unsupervised — it needs zero labeled training data. It learns what normal financial ratios look like and flags anything that doesn't fit. When the GST-to-Bank divergence scores 0.91 anomaly, that's the model saying: this number is in the extreme tail of what companies normally show.
>
> FinBERT from ProsusAI on HuggingFace is pre-trained specifically on financial text — earnings calls, annual reports, financial news. It understands domain-specific language. When a Director's Report says 'comfortable liquidity notwithstanding temporary headwinds,' a generic sentiment model scores that as positive. FinBERT scores it as high buried risk — because in financial language, 'notwithstanding temporary headwinds' is code for 'we have a problem we don't want to talk about.'"

**Why this matters to judges:**
This shows you're not just using "AI" generically. You've selected **specific models for specific tasks**, explained why each one beats alternatives, and shown how they work together. The FinBERT example is particularly powerful for a live demo.

---

### SLIDE 8: Technology Stack — Why Each Choice

**On the slide:**

```
EVERY TECHNOLOGY CHOSEN FOR A SPECIFIC REASON

CATEGORY          CHOSEN           WHY NOT THE ALTERNATIVE?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Orchestration     LangGraph        vs CrewAI: LangGraph gives explicit
                                   control over every node + edge.
                                   We can show judges the exact graph.
                                   CrewAI abstracts away the control.

Agent Framework   LangChain        vs raw API calls: Tested abstractions
                                   for RAG, tools, memory. Auto-LangSmith
                                   tracing with zero extra code.

LLM               Claude           vs GPT-4: Larger context window
                  (Haiku+Sonnet)   (fits entire annual report in one call),
                                   stronger structured output parsing,
                                   better financial text performance.
                                   Haiku at 5x lower cost for 80% of calls.

PDF Parsing       Unstructured.io  vs PyMuPDF: Spatial layout understanding.
                                   Indian annual reports have complex
                                   multi-column layouts. PyMuPDF reads DOM
                                   order → destroys column structure.

OCR               Tesseract        vs Google Vision: Runs locally. No per-page
                  (local)          cost. With page-level parallelism + Indian
                                   script config, comparable accuracy.

Embeddings        all-MiniLM-L6-v2 vs text-embedding-ada-002: LOCAL. Zero API
                  (local, CPU)     calls. 600 chunks in 12 seconds. OpenAI
                                   would be 600 API calls × 500ms each.

Vector DB         ChromaDB         vs FAISS: ChromaDB has client-server arch,
                                   metadata filtering, persistence layer.
                                   FAISS is just in-memory.

Graph DB          Neo4j            vs PostgreSQL+AGE: Purpose-built for graph.
                                   Cypher is natural. GraphRAG integrates
                                   natively. Multi-hop queries are 10x faster.

Search            Elasticsearch    vs Solr: Better Python client, better REST
                                   API, NER pipeline is first-class in ES 8.

Relational DB     PostgreSQL       vs MongoDB: Strict schemas. ACID. Our data
                                   structures are well-defined. Partial writes
                                   never exist.

NER               spaCy + GLiNER   vs fine-tuned BERT NER: GLiNER does zero-shot
                                   entity recognition. Recognizes Indian court
                                   names, regulatory bodies WITHOUT fine-tuning.

Task Queue        Celery + Redis   vs RQ: Richer features — routing, retry with
                                   exponential backoff, priority, Flower UI.

Web Search        Tavily           vs Brave: AI-native output, domain filtering,
                  + Exa            clean structured JSON. Exa's neural search
                  + SerpAPI        finds conceptually related content. SerpAPI
                                   wraps Google's Indian news index.

CAM Output        python-docx      vs ReportLab PDF: Word is the Indian banking
                                   standard for CAMs. Editable after generation.

Infra             Docker Compose   vs Kubernetes: K8s is overkill for hackathon.
                                   Docker Compose = one command, all 10 services.

Frontend          React +          vs Angular: Far less boilerplate for hackathon.
                  TailwindCSS      Tailwind produces professional UI fast.
```

**What to SAY (script):**
> "Every single technology in our stack was chosen with a specific reason and a specific rejection of the alternative. We didn't pick Neo4j because it sounds cool — we picked it because our Agent 2.5 runs multi-hop Cypher queries that would be 10x slower on a PostgreSQL graph extension. We didn't pick Unstructured.io because it's popular — we picked it because Indian annual reports have multi-column layouts that PyMuPDF would scramble. We run embeddings locally on CPU because 600 API calls to OpenAI would add 5 minutes and cost money — our local model does it in 12 seconds for free. We use Claude Haiku for 80% of LLM calls because they're extraction tasks — Sonnet quality isn't needed and costs 5x more. But for the Executive Summary and Risk Flags in the CAM — the sections judges and bankers read first — we use Sonnet."

**Why this matters to judges:**
The #1 sign that a team actually knows what they're doing is the ability to explain **why not** the alternative. Most teams say "we used React." You say "we used React not Angular because Angular's boilerplate is a hackathon killer." That signals engineering maturity.

---

### SLIDE 9: The Credit Score Model — 0 to 850

**On the slide:**

```
INTELLI-CREDIT SCORE: 0 − 850  (modeled after CIBIL)

BASELINE: 600 (industry average starting point)
Every point moves UP or DOWN with full source tracing.

SCORING MODULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Module          Max Up    Max Down    Key Metrics
──────────────────────────────────────────────────────
CAPACITY        +150      -100       DSCR, WC cycle, cash flow
CHARACTER       +120      -200       Promoter, SEBI, RPT, pledge
CAPITAL         +80       -80        D/E ratio, net worth
COLLATERAL      +60       -40        Coverage ratio, quality
CONDITIONS      +50       -50        Order book, sector outlook
COMPOUND        +57       -130       Cascade, fraud, temporal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HARD BLOCKS (override everything):
  Wilful defaulter → capped at 200
  Criminal case    → capped at 150
  DSCR < 1.0x     → capped at 300
  NCLT active      → capped at 250

EVERY POINT LOOKS LIKE THIS:
┌──────────────────────────────────────────────────────┐
│ Metric:     DSCR                                     │
│ Value:      1.38x                                    │
│ Formula:    EBITDA ₹18,200L / Debt Service ₹12,700L │
│ Source:     Annual Report FY2024, Page 67             │
│ Benchmark:  Industry avg 1.2-1.5x                    │
│ Impact:     +42 points                               │
│ Reasoning:  "DSCR of 1.38x within acceptable band   │
│              but declining trend from 2.1x (FY22)    │
│              at -0.34x/year. Projected FY25: 1.04x   │
│              approaching hard block threshold."       │
└──────────────────────────────────────────────────────┘

SCORE → LOAN PARAMETERS (derived, never AI's judgment):
  750-850: Full amount,  MCLR+1.5% = 10.0%
  650-749: 85% amount,   MCLR+2.5% = 11.0%
  550-649: 65% amount,   MCLR+3.5% = 12.0%
  450-549: 40% amount,   MCLR+5.0% = 13.5%
  350-449: REJECT. Reapply in 12 months.
  <350:    PERMANENT REJECT. Regulatory review.
```

**What to SAY (script):**
> "Our primary output is NOT approve or reject. It's a score from 0 to 850, modeled after the CIBIL scoring system that Indian banks already understand. We start at 600 — the industry average. Every metric adds or deducts points with a full audit trail. Our demo company XYZ Steel scores 477 — in the Poor band — because while the fundamentals look okay on paper, the graph reasoning found a circular trading network worth ₹41 crores, a cascade risk where DSCR drops to 0.88x if one key customer fails, and active concealment of related party transactions. These compound insights alone cost the company 130 points.
>
> What makes this different from other scoring approaches: every single point is traced back to a document, page, and paragraph. A credit officer can click on any score and see exactly why. Plus, there are hard blocks — if the company is on the RBI wilful defaulter list, the score is automatically capped at 200 regardless of everything else. No AI can override this.
>
> The loan amount and interest rate are derived from the score band — they're never the AI's independent judgment. The AI computes the score. The policy determines the parameters."

**Why this matters to judges:**
A 0-850 score with per-point tracing is dramatically more sophisticated than "approve/reject." It shows the system can handle nuance — a company scoring 550 isn't the same as one scoring 350. And the hard blocks show you understand regulatory reality.

---

### SLIDE 10: Scalability & Real-World Impact

**On the slide:**

```
SCALABILITY: FROM HACKATHON TO PRODUCTION

LATENCY OPTIMIZATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bottleneck                  Before        After         How
──────────────────────────────────────────────────────────────────
Sequential documents        ~8 min        ~45 sec       8 Celery workers
Full-document OCR           ~3 min        ~30 sec       Page-level parallelism
Sequential LLM calls        ~30 min       ~3 min        Model tiering + batching
Remote embedding API        ~5 min        ~12 sec       Local MiniLM on CPU
Sequential research         ~50 sec       ~4 sec        5 async tracks + cache
Neo4j graph writes          ~2 min        ~0 sec        Async non-blocking
User waiting for output     22 min felt   ~45 sec felt  WebSocket streaming
──────────────────────────────────────────────────────────────────
TOTAL:                      ~22 minutes   < 4 minutes

REAL-WORLD IMPACT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 1 analyst processes 1-2 applications per week
  → Intelli-Credit: 100+ per day per instance

• Indian banking NPAs: ₹7.4 lakh crore (2024)
  → Early fraud detection catches circular trading BEFORE disbursement

• Institutional knowledge lost when analysts retire
  → Universal Decision Store + RAG Knowledge Base preserves forever

• Regulatory compliance burden increasing each year
  → Auto-flagging for RPT concealment, SEBI violations, PMLA reporting

SCALABILITY PATH:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Current:   Docker Compose on single machine
Scale 1:   Kubernetes cluster, horizontal Celery scaling
Scale 2:   Multi-tenant SaaS for regional rural banks
Scale 3:   RBI/NABARD integration for real-time regulatory feed
Scale 4:   Cross-bank consortium for shared fraud intelligence
```

**What to SAY (script):**
> "Let me talk about why this isn't just a hackathon project. On latency: we've reduced the pipeline from an estimated 22 minutes with naive implementation to under 4 minutes through systematic optimization — parallel workers, page-level OCR, model tiering, local embeddings, async graph writes, and WebSocket streaming that shows results within 45 seconds even while the pipeline is still running.
>
> On impact: Indian banking NPAs stand at ₹7.4 lakh crore as of 2024. A significant portion of these are because fraud signals were missed during appraisal. Our system catches circular trading, related party concealment, and cascade risks at the appraisal stage — before a single rupee is disbursed.
>
> On scalability: today this runs on Docker Compose on a single machine. But every component is horizontally scalable. Celery workers scale to any number. Neo4j has cluster mode. Elasticsearch shards automatically. The same architecture could serve a multi-tenant SaaS for hundreds of regional banks. And the dream state: a cross-bank consortium where fraud intelligence is shared — if a promoter is flagged at Bank A, Bank B knows about it before they even open the application."

**Why this matters to judges:**
They want to know: is this a toy or a real thing? The latency breakdown shows engineering rigor. The NPA number shows real-world relevance. The scalability path shows you've thought beyond the hackathon.

---

### SLIDE 11: The Demo — What You'll See

**On the slide:**

```
LIVE DEMO: XYZ STEEL LIMITED — ₹50 CRORE WORKING CAPITAL LOAN

Step 1:  Upload 8 documents → all workers fire simultaneously
         Chatbot starts streaming: "Worker 1 reading Annual Report..."

Step 2:  Agent 0.5 catches 3-way revenue discrepancy
         Chatbot: "Revenue: AR ₹124.5cr ≠ GST ₹118.7cr ≠ ITR ₹98.2cr 🚨"

Step 3:  Agent 1.5 builds Neo4j graph + ML suite runs
         Chatbot: "DOMINANT GNN: circular trading probability 0.84 🚨"
         Chatbot: "FinBERT: buried risk in Director's Report 0.89 🚨"

Step 4:  Agent 2 scrapes MCA21 → promoter controls 3 suppliers
         Chatbot: "Rajesh Shah is director of Supplier A, B, RS Trading 🚨"

Step 5:  Agent 2.5 cascade: Greenfield NCLT → DSCR 1.43 → 0.88
         Chatbot: "CRITICAL: DSCR drops below 1.0x in stress scenario"

Step 6:  3 tickets raised → officer resolves via dialogue
         Officer: "Confirmed concealment." AI: "Should I flag compliance?"

Step 7:  Score: 477/850 → POOR → Conditional approval ₹20cr at 13.5%
         Every single point traceable to document + page

Step 8:  CAM generated — section by section with citations
         Download Word document, PDF score report, thinking log
```

**What to SAY (script — this IS the video demo script):**
> [Walk through each step live, narrating what appears on screen. See detailed video script section below.]

---

### SLIDE 12: Thank You + Q&A Preparation

**On the slide:**

```
INTELLI-CREDIT

"Not just reading documents.
 Connecting dots that humans can't."

🔗 9 agents | 4 databases | 3 ML models | 5 scrapers | 850-point score
📊 Every point sourced | Every thought visible | Every decision stored

Team: [Names]
GitHub: [Link]
Demo: [Link if deployed]
```

---

## VIDEO SCRIPT — PROTOTYPE DEMO (DETAILED)

The video demo should follow this exact narration synchronized with screen recording:

---

### Video Intro (15 seconds)

**[Screen: Title card with Intelli-Credit logo/name]**

> "This is Intelli-Credit — an AI-powered credit decisioning engine that transforms a 3-week manual process into a 4-minute transparent, cross-verified, source-traced intelligence pipeline. Let me show you exactly what happens when a loan application comes in."

---

### Section 1: Upload (30 seconds)

**[Screen: Upload Portal page]**

> "A credit officer opens the portal. They upload 8 documents for XYZ Steel Limited — Annual Report, Bank Statement, GST Returns, ITR, Legal Notices, Board Meeting Minutes, Shareholding Pattern, and Rating Reports. They enter the loan details: 50 crores, working capital, 60 months."

**[Action: Drag and drop files, fill form, click Submit]**

> "The moment they hit submit, 8 parallel Celery workers fire simultaneously. Watch the worker panel on the left."

---

### Section 2: Parallel Processing (45 seconds)

**[Screen: Processing Dashboard — worker status panel + chatbot]**

> "All 8 workers are processing at the same time. The Annual Report worker uses Unstructured.io — which understands multi-column layouts — plus Tesseract OCR for scanned pages. Watch the chatbot on the right."

**[Point to chatbot messages appearing]**

> "Here — Worker 1 says 'Reading Annual Report page 43. Found Revenue: ₹1,24,500 lakhs for FY2024. Accepted — three years present, auditor-signed.' Now Worker 2: 'Bank Statement — 3 cheque bounces in 5 months. Flagged — payment discipline concern.'
>
> Worker 3 — this is important — 'GSTR-2A vs 3B: Input Tax Credit claimed is ₹22,100 lakhs but only ₹18,400 lakhs available. Excess ₹3,700 lakhs. This could indicate fake invoices.' This is the GSTR reconciliation check that's in the evaluation criteria."

---

### Section 3: Consolidation + Cross-Verification (30 seconds)

**[Screen: Chatbot showing Agent 0.5 messages]**

> "All 8 workers are done. Agent 0.5 — the Consolidator — starts cross-verifying. Watch: 'Revenue cross-check — Annual Report ₹124.5 crores, GST ₹118.7, ITR ₹98.2, Bank ₹71.4. Four different numbers for the same thing. Government sources selected as primary. Revenue gap: 21% between AR and ITR. Flagged.'
>
> Now the critical one: 'Board Minutes approved 5 related party transactions. Annual Report shows 2. Three entities and ₹18 crores undisclosed. CRITICAL ticket raised.'"

---

### Section 4: Organization + ML Suite (30 seconds)

**[Screen: Chatbot showing Agent 1.5 messages]**

> "Agent 1.5 maps everything to the 5 Cs of credit, computes all derived metrics — DSCR 1.43x, Working Capital 94 days — and builds the Neo4j knowledge graph: 47 nodes, 89 relationships.
>
> Now the ML anomaly suite runs: DOMINANT GNN analyzes the entity graph — circular trading pattern detected with 0.84 probability. Isolation Forest flags the GST-Bank divergence as 0.91 anomalous. And FinBERT reads the Director's Report: surface sentiment positive at 0.72, but buried risk score 0.89. Management is using positive language to mask a cash flow crisis."

---

### Section 5: External Research (30 seconds)

**[Screen: Chatbot showing Agent 2 messages]**

> "Agent 2 runs 5 research tracks in parallel. Watch: Tavily finds the ₹280 crore BHEL order — corroborated by both Economic Times and Livemint — good signal. But here's the MCA21 scraper — it checks director DIN 01234567, Rajesh Shah. Found: he's director of XYZ Steel, AND Supplier A, AND Supplier B, AND RS Trading. Three of the top five suppliers are controlled by the promoter himself.
>
> And NJDG finds an active court case filed by Greenfield Energy for ₹14.2 crores — but the annual report said 'no litigation.' Case was filed post-report — possible timing explanation, but the board knew about Greenfield payment problems since April 2023."

---

### Section 6: Graph Reasoning (45 seconds)

**[Screen: Chatbot showing Agent 2.5 messages, possibly graph visualization]**

> "This is Agent 2.5 — the Graph Reasoning Agent. Five passes over the complete Neo4j knowledge graph.
>
> Pass 1 — Contradiction Detection: Annual Report says no litigation, but NJDG has an active case. Annual Report shows 2 related parties, board minutes show 5. Minus 45 points.
>
> Pass 2 — Cascade Risk: This is the most important finding. Greenfield Energy, which provides 38% of XYZ Steel's revenue, has filed for NCLT insolvency. Follow the chain: if Greenfield collapses, revenue drops 38%. EBITDA drops proportionally. DSCR recalculates from 1.43x to 0.88x. That's below 1.0x — the company physically cannot service this loan. Minus 50 points.
>
> Pass 3 — Hidden Relationships: Community detection algorithm finds a tight cluster — the promoter at the center, connected to 4 entities through director and family relationships. Total transactions flowing through this network: ₹41 crores. DOMINANT GNN confirms: 0.84 probability of circular trading. Minus 60 points.
>
> This is what makes graph reasoning essential — no single document reveals this. Only the connections between all documents and all external data reveal it."

---

### Section 7: Ticket Resolution (30 seconds)

**[Screen: Ticket Resolution Interface]**

> "The Evidence Package Builder has raised 3 tickets requiring human judgment. Here's Ticket A — the RPT concealment. The officer sees both claims side by side: board minutes showing 5 entities, annual report showing 2. The AI recommends confirmed concealment and shows 3 similar precedents from the RAG knowledge base.
>
> The officer selects 'Confirmed concealment.' The AI follows up: 'Should I also flag this for compliance review given the undisclosed ₹19.2 crores?' The officer says yes. This isn't a binary accept/reject ticket system — it's a dialogue. The AI asks follow-up questions because the resolution has downstream implications."

---

### Section 8: Score + CAM Output (30 seconds)

**[Screen: Score Dashboard + CAM Viewer]**

> "Agent 3 computes the final score. Starting baseline 600. Capacity adds 42 — DSCR is acceptable but declining. Character deducts 80 — RPT concealment and 72% share pledge are devastating. Compound insights deduct 130 — cascade risk, circular trading, temporal deterioration. Final score: 477 out of 850. Band: Poor. Conditional approval: ₹20 crores at 13.5%.
>
> The CAM is generated section by section — Executive Summary and Risk Flags use Claude Sonnet for the best quality. Every sentence references its evidence. 'Revenue has grown at 18.2% CAGR over FY2022-24 [Annual Report FY2024, Page 43, Table 2], cross-verified against ITR filings [ITR FY2024 Schedule BP].'
>
> The officer can download the CAM as a Word document — the standard format in Indian banking — the score report as PDF, and the complete thinking log as JSON. The LangSmith trace is one click away."

---

### Video Closing (15 seconds)

> "Under 4 minutes. 847 pages read. 47 research findings. 17 compound insights. 3 tickets resolved. Every decision stored, every thought visible, every point traceable. This is Intelli-Credit."

---

## ANTICIPATED JUDGE QUESTIONS & PREPARED ANSWERS

### Q: "How is this different from just using GPT-4 on the documents?"

> **A:** "GPT-4 can read and summarize. It cannot independently research the promoter's other companies on MCA21, scrape court cases from NJDG, run a graph neural network for circular trading detection, cross-verify revenue across four sources, or compute cascade DSCR by traversing a knowledge graph. We use LLMs where they're best — writing and reasoning. But the intelligence comes from the multi-agent architecture around the LLMs."

### Q: "Is the MCA21 scraper actually possible? Doesn't MCA require login?"

> **A:** "Basic director information and company charges are publicly available on the MCA21 portal without login. DIN-level director search, company charge details, and ROC filing dates are accessible via the public search interface. For the hackathon, we also have a mock data layer that simulates the scraper responses, demonstrating the architecture. In production, integration with an authorized MCA data provider like Signzy or Perfios would replace the scraper."

### Q: "What about data privacy and PII handling?"

> **A:** "All data stays within our Docker Compose stack — no document content is sent to external services except the LLM API calls, which use Anthropic's Claude with their enterprise data handling policy. The research scrapers query using company names and CIN numbers, not individual PII. All PostgreSQL columns containing personal data can be encrypted at rest. JWT authentication ensures only authorized officers access assessments."

### Q: "What if the OCR quality is poor?"

> **A:** "Tesseract assigns a per-page confidence score. If any page falls below our threshold, the extraction from that page is flagged as low-confidence and a ticket is raised. The system doesn't silently accept bad OCR — it tells the officer 'I'm not sure about this number, please verify.' This is why the ticketing layer exists."

### Q: "How do you handle documents in non-English languages?"

> **A:** "Tesseract is configured with Hindi-English mixed mode for Indian documents. spaCy's multilingual pipeline handles Hindi entity recognition. For the hackathon scope, we focus on English-primary documents with Hindi annotations, which covers 90%+ of corporate loan applications. The architecture supports adding language-specific models as additional workers."

### Q: "The DOMINANT GNN — how is it fine-tuned without your own labeled data?"

> **A:** "DOMINANT is pre-trained on financial transaction graph datasets that are publicly available for research. For Indian market specificity, we fine-tune on SEBI enforcement order descriptions which provide labeled examples of fraud patterns — the SEBI website publishes detailed descriptions of the entity networks involved in each case. These are converted into graph structures that the GNN learns from. In the hackathon, we use the pre-trained model with Indian-specific graph feature engineering rather than full fine-tuning."

### Q: "What happens when there's a network issue with the scrapers?"

> **A:** "Every scraper has a timeout, retry with exponential backoff, and a fallback. If MCA21 is unreachable, the director network analysis proceeds without external data — it still has internal document data — and a ticket is raised noting 'MCA21 enrichment unavailable, director verification incomplete.' The pipeline doesn't break. It degrades gracefully and documents the degradation."

### Q: "Can this replace the credit officer?"

> **A:** "No, and it shouldn't. This system does the reading, computing, researching, and connecting that takes 3 weeks manually. The credit officer still makes the final judgment. Every ticket requires human resolution. The score is a recommendation — the officer can override. The system is designed as an intelligence amplifier, not a replacement. That's why the Live Thinking Chatbot exists — the officer is an active participant, not a passive recipient."

### Q: "What about regulatory compliance — does this meet RBI/SEBI requirements?"

> **A:** "Yes, in several ways. First, our system auto-flags wilful defaulters from the RBI published list — this is a regulatory mandate. Second, undisclosed related party transactions above threshold trigger a compliance notification. Third, the Universal Decision Store provides a complete audit trail for every decision — which RBI requires banks to maintain. Fourth, if fraud patterns suggest money laundering, our system flags for PMLA/FIU-IND reporting. The system doesn't just process loans — it enforces regulatory awareness at every step."

### Q: "Why 4 databases? Isn't that over-engineering?"

> **A:** "Each database does something the others can't. ChromaDB does semantic vector search — PostgreSQL can't. Neo4j does multi-hop graph traversal — Elasticsearch can't. Elasticsearch does full-text search with NER — ChromaDB can't. PostgreSQL enforces ACID transactions — Neo4j doesn't. We use each tool for exactly what it was built for. We're not running four databases for the same data — we're running four specialized engines for four fundamentally different types of queries."

---

## KEY PHRASES TO USE THROUGHOUT THE PRESENTATION

These phrases are designed to be memorable and differentiate you from other teams:

```
"We don't just read documents. We cross-verify them."

"Individual facts look fine. Connected facts reveal fraud."

"Not approve/reject. 850 points. Every point traced."

"The AI shows its work. Every page. Every decision. In real time."

"Government filing beats self-reported data. Always."

"If the promoter owns his own suppliers, that's not a supply chain — that's circular trading."

"No human can hold 847 pages in their head simultaneously."

"FinBERT understands that 'notwithstanding temporary headwinds' is management-speak for 'we have a problem.'"

"Our system doesn't just make a decision. It remembers every decision it's ever made."

"When that senior analyst retires, 30 years of pattern recognition doesn't walk out the door."
```

---

## PPT DESIGN TIPS (Visual Guidance)

1. **Dark background, light text** — technical presentations read better in dark mode
2. **Architecture diagram: FULL PAGE** — let it breathe, judges will photograph it
3. **Score example: use color coding** — green for positives, red for negatives, make the math visible
4. **Chatbot screenshots: use the actual font and colors from the UI** — it should look like the real product
5. **Every slide should have ONE key number or ONE key visual** — don't overload
6. **Technology comparison table: bold your choice, gray the alternative** — visual hierarchy matters
7. **Use the XYZ Steel example consistently** — same company throughout, builds a narrative
8. **The cascade DSCR chain should be animated** — show each hop appearing one by one
9. **Show the Neo4j graph visualization** — even a mock one — graphs are visually compelling
10. **End with the 477/850 score** — it's a concrete number judges remember

---

## THINGS JUDGES WILL SPECIFICALLY CHECK FROM THE PROBLEM STATEMENT

Make sure these are visibly addressed:

| PS Requirement | Where We Address It | Slide |
|---|---|---|
| Multiple document types ingestion | 8 parallel workers | Slide 4 |
| Financial statement analysis | Agent 1.5 metric computation | Slide 4 |
| GST return reconciliation | Worker 3: GSTR-2A vs 3B | Slide 6 |
| ITR cross-verification | Worker 4 + 3-way revenue check | Slide 6 |
| Board minutes analysis | Worker 6 + RPT cross-check | Slide 6 |
| Shareholding pattern | Worker 7 + pledge analysis | Slide 4 |
| Rating report analysis | Worker 8 + downgrade tracking | Slide 4 |
| CIBIL integration | UI input field + Character module | Slide 9 |
| Management interview | Structured 5 Cs form + AI credibility check | Demo |
| Research capability | 5 tracks + 5 scrapers + verification | Slide 4, 5 |
| Risk assessment | ML suite + graph reasoning | Slide 5, 7 |
| Credit score | 0-850 with per-point breakdown | Slide 9 |
| CAM generation | Section-by-section with citations | Demo |
| Explainability | Live Thinking Chatbot + per-point trace | Slide 5 |
| Scalability discussion | Latency optimization + growth path | Slide 10 |
| Databricks mention | Mock connector in architecture | Slide 4 note |

---

## FINAL CHECKLIST BEFORE PRESENTING

```
□ Can you explain WHY you chose each technology, not just WHAT?
□ Can you explain the 3-way revenue cross-verification in one sentence?
□ Can you draw the cascade DSCR chain from memory?
□ Can you explain how director network mapping catches circular trading?
□ Can you explain the GSTR-2A vs 3B reconciliation?
□ Can you explain why 4 databases and not 1?
□ Can you explain what "graph reasoning" finds that LLMs can't?
□ Can you explain the score model in 30 seconds?
□ Can you explain the ticketing system's RAG learning in one sentence?
□ Can you answer "how is this different from just using GPT-4?"
□ Does the demo video show the chatbot streaming in real time?
□ Does the demo show at least one ticket being resolved?
□ Does the demo show the final score with per-point breakdown?
□ Have you rehearsed the full presentation under the time limit?
```
