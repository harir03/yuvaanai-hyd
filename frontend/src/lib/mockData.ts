// =============================================================================
// Intelli-Credit — Comprehensive Mock Data
// Uses XYZ Steel ₹50cr Working Capital example from architecture spec
// Every component MUST work with this data when backend is unavailable
// =============================================================================

// --- Types -------------------------------------------------------------------

export interface CompanyInfo {
    name: string;
    cin: string;
    loanAmount: string;
    loanType: string;
    sector: string;
    incorporationYear: number;
    promoter: string;
    existingBanker: string;
}

export interface DocumentUpload {
    id: string;
    type: string;
    fileName: string;
    status: "pending" | "uploaded" | "processing" | "completed" | "error";
    pages: number;
    confidence: number;
    workerLabel: string;
}

export interface PipelineStage {
    id: number;
    name: string;
    agent: string;
    status: "pending" | "in_progress" | "completed" | "failed" | "skipped";
    progress: number;
    duration?: string;
    startTime?: string;
    endTime?: string;
    thinkingCount: number;
}

export interface WorkerStatus {
    id: string;
    name: string;
    label: string;
    document: string;
    status: "idle" | "processing" | "completed" | "error";
    progress: number;
    pages: number;
    currentPage: number;
    currentTask?: string;
}

export interface ThinkingEvent {
    id: string;
    timestamp: string;
    agent: string;
    eventType: "READ" | "FOUND" | "COMPUTED" | "ACCEPTED" | "REJECTED" | "FLAGGED" | "CRITICAL" | "CONNECTING" | "CONCLUDING" | "QUESTIONING" | "DECIDED";
    message: string;
    source?: string;
    confidence?: number;
}

export interface Ticket {
    id: string;
    title: string;
    severity: "LOW" | "HIGH" | "CRITICAL";
    status: "open" | "resolved" | "escalated";
    source_agent: string;
    description: string;
    ai_evidence: { source: string; finding_type: string; detail: string; excerpt?: string; page_ref?: string }[];
    ai_recommendation: string;
    humanResolution?: string;
    created_at: string;
    resolvedAt?: string;
    affected_documents: string[];
}

export interface ScoreBreakdownEntry {
    module: string;
    metricName: string;
    metricValue: string;
    formula: string;
    sourceDocument: string;
    sourcePage: number;
    sourceExcerpt: string;
    benchmarkContext: string;
    scoreImpact: number;
    reasoning: string;
    confidence: number;
}

export interface ScoreModule {
    name: string;
    label: string;
    maxPositive: number;
    maxNegative: number;
    score: number;
    metrics: ScoreBreakdownEntry[];
}

export interface CAMSection {
    title: string;
    content: string;
    citations: { document: string; page: number; excerpt: string }[];
}

export interface Assessment {
    sessionId: string;
    company: CompanyInfo;
    documents: DocumentUpload[];
    pipeline: PipelineStage[];
    workers: WorkerStatus[];
    thinkingEvents: ThinkingEvent[];
    tickets: Ticket[];
    finalScore: number;
    scoreBand: string;
    recommendation: string;
    interestRate: string;
    approvedAmount: string;
    processingTime: string;
    documentsAnalyzed: number;
    findingsCount: number;
    ticketsRaised: number;
    ticketsResolved: number;
    scoreModules: ScoreModule[];
    cam: CAMSection[];
    hardBlocks: string[];
    createdAt: string;
    completedAt: string;
    status: "uploading" | "processing" | "interview" | "tickets" | "completed" | "rejected";
}

export interface HistoryRecord {
    sessionId: string;
    companyName: string;
    sector: string;
    loanAmount: string;
    loanType: string;
    score: number;
    scoreBand: string;
    status: string;
    date: string;
    officer: string;
    recommendation: string;
}

// --- Mock Data ---------------------------------------------------------------

export const mockCompany: CompanyInfo = {
    name: "XYZ Steel Private Limited",
    cin: "U27100MH2005PTC123456",
    loanAmount: "₹50,00,00,000",
    loanType: "Working Capital",
    sector: "Steel Manufacturing",
    incorporationYear: 2005,
    promoter: "Rajesh Kumar Agarwal",
    existingBanker: "State Bank of India",
};

export const mockDocuments: DocumentUpload[] = [
    { id: "d1", type: "Annual Report", fileName: "XYZ_Steel_AR_FY2025.pdf", status: "completed", pages: 148, confidence: 0.94, workerLabel: "W1" },
    { id: "d2", type: "Bank Statement", fileName: "SBI_Statement_12M.pdf", status: "completed", pages: 62, confidence: 0.97, workerLabel: "W2" },
    { id: "d3", type: "GST Returns", fileName: "GSTR_2024-25.xlsx", status: "completed", pages: 24, confidence: 0.99, workerLabel: "W3" },
    { id: "d4", type: "ITR", fileName: "ITR6_AY2025.pdf", status: "completed", pages: 38, confidence: 0.96, workerLabel: "W4" },
    { id: "d5", type: "Legal Notice", fileName: "Legal_Notices_Bundle.pdf", status: "completed", pages: 12, confidence: 0.88, workerLabel: "W5" },
    { id: "d6", type: "Board Minutes", fileName: "Board_Minutes_FY2025.pdf", status: "completed", pages: 28, confidence: 0.92, workerLabel: "W6" },
    { id: "d7", type: "Shareholding", fileName: "Shareholding_Pattern.pdf", status: "completed", pages: 8, confidence: 0.95, workerLabel: "W7" },
    { id: "d8", type: "Rating Report", fileName: "CRISIL_Rating_Report.pdf", status: "completed", pages: 6, confidence: 0.98, workerLabel: "W8" },
];

export const mockPipeline: PipelineStage[] = [
    { id: 1, name: "Document Ingestion", agent: "8 Parallel Workers", status: "completed", progress: 100, duration: "2m 30s", startTime: "10:00:00", endTime: "10:02:30", thinkingCount: 48 },
    { id: 2, name: "Agent 0.5 — Consolidator", agent: "Agent 0.5 — The Consolidator", status: "completed", progress: 100, duration: "44s", startTime: "10:02:31", endTime: "10:03:15", thinkingCount: 12 },
    { id: 3, name: "Validation Gate", agent: "Validator", status: "completed", progress: 100, duration: "29s", startTime: "10:03:16", endTime: "10:03:45", thinkingCount: 8 },
    { id: 4, name: "Agent 1.5 — Organizer", agent: "Agent 1.5 — The Organizer", status: "completed", progress: 100, duration: "1m 14s", startTime: "10:03:46", endTime: "10:05:00", thinkingCount: 22 },
    { id: 5, name: "Agent 2 — Research", agent: "Agent 2 — The Researcher", status: "completed", progress: 100, duration: "2m 29s", startTime: "10:05:01", endTime: "10:07:30", thinkingCount: 35 },
    { id: 6, name: "Agent 2.5 — Reasoning", agent: "Agent 2.5 — 5 Passes", status: "completed", progress: 100, duration: "1m 29s", startTime: "10:07:31", endTime: "10:09:00", thinkingCount: 28 },
    { id: 7, name: "Evidence Packaging", agent: "Evidence Package Builder", status: "completed", progress: 100, duration: "29s", startTime: "10:09:01", endTime: "10:09:30", thinkingCount: 6 },
    { id: 8, name: "Ticket Resolution", agent: "Ticketing Layer", status: "in_progress", progress: 65, duration: undefined, startTime: "10:09:31", endTime: undefined, thinkingCount: 4 },
    { id: 9, name: "Agent 3 — Scorer & CAM", agent: "Agent 3 — The Judge", status: "pending", progress: 0, duration: undefined, startTime: undefined, endTime: undefined, thinkingCount: 0 },
];

export const mockWorkers: WorkerStatus[] = [
    { id: "w1", name: "W1 — Annual Report", label: "W1 — Annual Report", document: "XYZ_Steel_AR_FY2025.pdf", status: "completed", progress: 100, pages: 148, currentPage: 148, currentTask: "Completed — 148 pages extracted" },
    { id: "w2", name: "W2 — Bank Statement", label: "W2 — Bank Statement", document: "SBI_Statement_12M.pdf", status: "completed", progress: 100, pages: 62, currentPage: 62, currentTask: "Completed — 62 pages extracted" },
    { id: "w3", name: "W3 — GST Returns", label: "W3 — GST Returns", document: "GSTR_2024-25.xlsx", status: "completed", progress: 100, pages: 24, currentPage: 24, currentTask: "Completed — 24 sheets processed" },
    { id: "w4", name: "W4 — ITR", label: "W4 — ITR", document: "ITR6_AY2025.pdf", status: "completed", progress: 100, pages: 38, currentPage: 38, currentTask: "Completed — 38 pages extracted" },
    { id: "w5", name: "W5 — Legal Notice", label: "W5 — Legal Notice", document: "Legal_Notices_Bundle.pdf", status: "completed", progress: 100, pages: 12, currentPage: 12, currentTask: "Completed — 12 pages extracted" },
    { id: "w6", name: "W6 — Board Minutes", label: "W6 — Board Minutes", document: "Board_Minutes_FY2025.pdf", status: "processing", progress: 72, pages: 28, currentPage: 20, currentTask: "Extracting RPT approvals — page 20" },
    { id: "w7", name: "W7 — Shareholding", label: "W7 — Shareholding", document: "Shareholding_Pattern.pdf", status: "processing", progress: 50, pages: 8, currentPage: 4, currentTask: "Parsing promoter pledge data" },
    { id: "w8", name: "W8 — Rating Report", label: "W8 — Rating Report", document: "CRISIL_Rating_Report.pdf", status: "idle", progress: 0, pages: 6, currentPage: 0, currentTask: undefined },
];

export const mockThinkingEvents: ThinkingEvent[] = [
    { id: "t1", timestamp: "10:00:01", agent: "W1 — Annual Report", eventType: "READ", message: "Reading Annual Report FY2025 — 148 pages, PDF format detected", confidence: 0.94 },
    { id: "t2", timestamp: "10:00:15", agent: "W1 — Annual Report", eventType: "FOUND", message: "Revenue FY2025: ₹312.4cr (AR) — extracted from P&L Statement, Page 42", source: "Annual Report p.42", confidence: 0.96 },
    { id: "t3", timestamp: "10:00:22", agent: "W3 — GST Returns", eventType: "FOUND", message: "Annual turnover from GSTR-3B: ₹308.7cr — aggregated from 12 monthly returns", source: "GST Returns", confidence: 0.99 },
    { id: "t4", timestamp: "10:00:30", agent: "W4 — ITR", eventType: "FOUND", message: "Revenue per ITR6 Schedule BP: ₹310.1cr", source: "ITR p.8", confidence: 0.97 },
    { id: "t5", timestamp: "10:00:45", agent: "W2 — Bank Statement", eventType: "FOUND", message: "Total annual credit inflows: ₹298.6cr — 14 accounts aggregated", source: "Bank Statement", confidence: 0.95 },
    { id: "t6", timestamp: "10:01:00", agent: "W6 — Board Minutes", eventType: "FOUND", message: "RPT approvals found: 3 transactions totaling ₹18.2cr with Agarwal Holdings", source: "Board Minutes p.12", confidence: 0.91 },
    { id: "t7", timestamp: "10:01:10", agent: "W1 — Annual Report", eventType: "FLAGGED", message: "⚠️ RPT disclosure in AR lists only 2 transactions (₹12.1cr) — Board Minutes show 3 (₹18.2cr). Potential concealment of ₹6.1cr RPT.", source: "AR p.87 vs BM p.12", confidence: 0.89 },
    { id: "t8", timestamp: "10:01:30", agent: "W7 — Shareholding", eventType: "FOUND", message: "Promoter holding: 62.4%, Pledge: 8.2% of promoter shares", source: "Shareholding Pattern p.2", confidence: 0.98 },
    { id: "t9", timestamp: "10:01:45", agent: "W8 — Rating Report", eventType: "FOUND", message: "CRISIL BBB+ (Stable) — upgraded from BBB in Feb 2025", source: "Rating Report p.1", confidence: 0.99 },
    { id: "t10", timestamp: "10:02:00", agent: "W5 — Legal Notice", eventType: "FOUND", message: "2 active legal notices: (1) ₹2.3cr supplier dispute, (2) ₹0.8cr labor tribunal", source: "Legal Notice p.3,8", confidence: 0.88 },
    { id: "t11", timestamp: "10:02:35", agent: "Agent 0.5 — Consolidator", eventType: "COMPUTED", message: "Revenue cross-verification: AR ₹312.4cr | GST ₹308.7cr | ITR ₹310.1cr | Bank ₹298.6cr — Max deviation 4.4% (within 5% tolerance)", confidence: 0.93 },
    { id: "t12", timestamp: "10:02:50", agent: "Agent 0.5 — Consolidator", eventType: "FLAGGED", message: "⚠️ Bank inflow (₹298.6cr) is 4.4% below AR revenue (₹312.4cr). Possible deferred collections or off-book revenue.", confidence: 0.85 },
    { id: "t13", timestamp: "10:03:00", agent: "Agent 0.5 — Consolidator", eventType: "ACCEPTED", message: "✅ Revenue accepted at ₹310.1cr (ITR figure) — government source, weight 1.0", confidence: 0.97 },
    { id: "t14", timestamp: "10:03:20", agent: "Validator", eventType: "ACCEPTED", message: "✅ All 8 mandatory documents received and parsed. Completeness check passed.", confidence: 1.0 },
    { id: "t15", timestamp: "10:03:50", agent: "Agent 1.5 — Organizer", eventType: "COMPUTED", message: "DSCR calculated: 1.38x — (EBITDA ₹42.6cr - Tax ₹8.1cr) / (Interest ₹18.2cr + Principal ₹6.8cr)", source: "AR p.42, p.68", confidence: 0.94 },
    { id: "t16", timestamp: "10:04:10", agent: "Agent 1.5 — Organizer", eventType: "COMPUTED", message: "Debt-to-Equity: 1.82x — Total Debt ₹142.3cr / Net Worth ₹78.2cr", source: "AR p.48", confidence: 0.95 },
    { id: "t17", timestamp: "10:04:30", agent: "Agent 1.5 — Organizer", eventType: "COMPUTED", message: "Working Capital Cycle: 87 days — Inventory 45d + Receivable 62d - Payable 20d", source: "AR p.52", confidence: 0.92 },
    { id: "t18", timestamp: "10:05:10", agent: "Agent 2 — Researcher", eventType: "READ", message: "Querying MCA21 for director cross-directorships...", confidence: 0.9 },
    { id: "t19", timestamp: "10:05:40", agent: "Agent 2 — Researcher", eventType: "FOUND", message: "MCA21: Rajesh K. Agarwal is director in 4 companies — XYZ Steel, Agarwal Holdings, AK Traders, Steel Logistics India", source: "MCA21 Scraper", confidence: 1.0 },
    { id: "t20", timestamp: "10:06:00", agent: "Agent 2 — Researcher", eventType: "FOUND", message: "NJDG: 1 active case — Commercial suit ₹2.3cr filed by Tata Metaliks (matches Legal Notice)", source: "NJDG Scraper", confidence: 1.0 },
    { id: "t21", timestamp: "10:06:20", agent: "Agent 2 — Researcher", eventType: "ACCEPTED", message: "✅ AR litigation disclosure matches NJDG — no concealment detected for this case", confidence: 0.95 },
    { id: "t22", timestamp: "10:06:45", agent: "Agent 2 — Researcher", eventType: "FLAGGED", message: "⚠️ RBI: Agarwal Holdings (related party) has NPA classification with PNB — potential cascade risk", source: "RBI Defaulter Scraper", confidence: 0.92 },
    { id: "t23", timestamp: "10:07:40", agent: "Agent 2.5 — Graph Reasoning", eventType: "CONNECTING", message: "🔗 Cross-directorship detected: Rajesh Agarwal → Agarwal Holdings (NPA) → AK Traders → XYZ Steel supply chain. 3-hop connection.", confidence: 0.88 },
    { id: "t24", timestamp: "10:08:00", agent: "Agent 2.5 — Graph Reasoning", eventType: "CONNECTING", message: "🔗 Cascade Pass: If Agarwal Holdings defaults, ₹18.2cr RPT receivable at risk → DSCR drops to 0.97x (below 1.0 threshold)", confidence: 0.85 },
    { id: "t25", timestamp: "10:08:20", agent: "Agent 2.5 — Graph Reasoning", eventType: "CRITICAL", message: "🚨 Conditional hard block: If RPT receivable (₹18.2cr) becomes irrecoverable, DSCR < 1.0 → score capped at 300", confidence: 0.82 },
    { id: "t26", timestamp: "10:08:45", agent: "Agent 2.5 — Graph Reasoning", eventType: "QUESTIONING", message: "💬 RPT concealment (₹6.1cr undisclosed) + related party NPA → raising HIGH severity ticket for human review", confidence: 0.8 },
    { id: "t27", timestamp: "10:09:10", agent: "Evidence Builder", eventType: "CONCLUDING", message: "💡 Evidence Package assembled: 42 findings, 3 flags, 1 critical, 2 tickets. Ready for Agent 3.", confidence: 0.95 },
    { id: "t28", timestamp: "10:11:10", agent: "Agent 3 — The Judge", eventType: "DECIDED", message: "📊 CAPACITY module: +95/150 — DSCR 1.38x (good but conditional risk), revenue growth 8.2% YoY, WC cycle 87d (above sector avg 72d)", confidence: 0.94 },
    { id: "t29", timestamp: "10:11:30", agent: "Agent 3 — The Judge", eventType: "DECIDED", message: "📊 CHARACTER module: +42/120 — RPT concealment (-35), promoter NPA link (-25), but CRISIL upgrade (+12), no SEBI actions (+15)", confidence: 0.91 },
    { id: "t30", timestamp: "10:11:50", agent: "Agent 3 — The Judge", eventType: "DECIDED", message: "📊 CAPITAL module: +28/80 — D/E 1.82x (high for sector), net worth ₹78.2cr (adequate)", confidence: 0.93 },
    { id: "t31", timestamp: "10:12:05", agent: "Agent 3 — The Judge", eventType: "DECIDED", message: "📊 COLLATERAL module: +35/60 — Asset coverage 1.6x, no prior liens, property valued at ₹82cr", confidence: 0.95 },
    { id: "t32", timestamp: "10:12:20", agent: "Agent 3 — The Judge", eventType: "DECIDED", message: "📊 CONDITIONS module: +22/50 — Steel sector outlook neutral, PLI scheme benefit possible, order book ₹89cr", confidence: 0.88 },
    { id: "t33", timestamp: "10:12:40", agent: "Agent 3 — The Judge", eventType: "DECIDED", message: "📊 COMPOUND module: -45/57 — Cascade risk via Agarwal Holdings (-30), RPT concealment pattern (-15)", confidence: 0.86 },
    { id: "t34", timestamp: "10:12:55", agent: "Agent 3 — The Judge", eventType: "CONCLUDING", message: "💡 FINAL SCORE: 677/850 — Band: GOOD. Recommendation: Approve at 85% (₹42.5cr) at MCLR+2.5%", confidence: 0.93 },
];

export const mockTickets: Ticket[] = [
    {
        id: "TKT-001",
        title: "RPT Concealment — ₹6.1cr Undisclosed Transaction",
        severity: "HIGH",
        status: "resolved",
        source_agent: "Agent 2.5 — Graph Reasoning",
        description: "Annual Report discloses 2 RPTs (₹12.1cr) but Board Minutes show 3 RPTs (₹18.2cr) with Agarwal Holdings. ₹6.1cr transaction appears concealed.",
        ai_evidence: [
            { source: "Annual Report", finding_type: "RPT Disclosure", detail: "AR p.87 lists 2 RPTs: (1) Management fee ₹7.2cr to Agarwal Holdings, (2) Raw material purchase ₹4.9cr from AK Traders. Total disclosed: ₹12.1cr.", excerpt: "Related Party Transactions per AS-18: Management Fee ₹7.2cr, Raw Material ₹4.9cr", page_ref: "Annual Report p.87" },
            { source: "Board Minutes", finding_type: "RPT Approval", detail: "Board Minutes record approval of 3 RPTs totaling ₹18.2cr including ₹6.1cr inter-corporate deposit to Agarwal Holdings — not in AR disclosure.", excerpt: "Resolved: Inter-corporate deposit of ₹6,10,00,000 to Agarwal Holdings Pvt Ltd approved", page_ref: "Board Minutes p.12" },
        ],
        ai_recommendation: "Flag for Character module scoring. The ₹6.1cr concealment suggests weak disclosure practices. Recommend covenant requiring full RPT disclosure in future filings.",
        humanResolution: "Verified with company CFO. The ₹6.1cr inter-corporate deposit was classified as 'short-term investment' in AR Schedule 8 rather than RPT disclosure. While technically compliant under AS-18 narrow definition, this is a disclosure quality concern.",
        created_at: "2026-03-05 10:08:45",
        resolvedAt: "2026-03-05 10:10:30",
        affected_documents: ["Annual Report p.87", "Board Minutes p.12"],
    },
    {
        id: "TKT-002",
        title: "Related Party NPA Cascade Risk",
        severity: "HIGH",
        status: "resolved",
        source_agent: "Agent 2.5 — Graph Reasoning",
        description: "Agarwal Holdings (promoter Rajesh Agarwal is director) flagged as NPA with PNB. XYZ Steel has ₹18.2cr RPT exposure. If irrecoverable, DSCR drops below 1.0x.",
        ai_evidence: [
            { source: "RBI Defaulter List", finding_type: "NPA Classification", detail: "Agarwal Holdings Pvt Ltd classified as NPA since Oct 2025 with PNB (₹28cr facility)." },
            { source: "MCA21 Director Records", finding_type: "Cross-Directorship", detail: "Common director: Rajesh Kumar Agarwal serves on both XYZ Steel and Agarwal Holdings boards." },
            { source: "Board Minutes", finding_type: "RPT Exposure", detail: "Total RPT exposure to Agarwal Holdings group: ₹18.2cr. If irrecoverable, DSCR drops from 1.38x to 0.97x.", excerpt: "Total inter-company transactions with Agarwal Holdings: ₹18,20,00,000", page_ref: "Board Minutes p.12" },
        ],
        ai_recommendation: "Flag as conditional hard block scenario. If RPT receivable becomes irrecoverable, DSCR < 1.0 triggers automatic score cap at 300. Recommend covenant to reduce RPT exposure below ₹10cr within 6 months.",
        humanResolution: "Officer confirms Agarwal Holdings has submitted restructuring plan to PNB. ₹12cr of RPT is trade receivable (current). Conditional approval with covenant: RPT exposure must reduce below ₹10cr within 6 months.",
        created_at: "2026-03-05 10:08:50",
        resolvedAt: "2026-03-05 10:10:45",
        affected_documents: ["RBI Defaulter List", "MCA21 Director Records", "Board Minutes p.12"],
    },
    {
        id: "TKT-003",
        title: "GSTR-2A vs 3B ITC Mismatch",
        severity: "LOW",
        status: "resolved",
        source_agent: "W3 — GST Worker",
        description: "Input Tax Credit claimed in GSTR-3B (₹4.82cr) exceeds ITC available per GSTR-2A (₹4.31cr). Excess claim: ₹0.51cr.",
        ai_evidence: [
            { source: "GST Returns", finding_type: "ITC Mismatch", detail: "GSTR-3B aggregate ITC claimed: ₹4,82,00,000. GSTR-2A matched ITC: ₹4,31,00,000. Difference: ₹51,00,000 (10.6% excess). Industry average excess: 3-5%.", page_ref: "GST Returns — GSTR-3B vs GSTR-2A" },
        ],
        ai_recommendation: "Low severity — likely timing difference or reverse charge items. Verify with company and flag in Conditions module if excess persists.",
        humanResolution: "Verified: ₹38L relates to reverse charge mechanism invoices. Remaining ₹13L is a timing difference from Q4 invoices. No fraud indicated.",
        created_at: "2026-03-05 10:01:15",
        resolvedAt: "2026-03-05 10:03:00",
        affected_documents: ["GST Returns — GSTR-2A", "GST Returns — GSTR-3B"],
    },
];

export const mockScoreModules: ScoreModule[] = [
    {
        name: "CAPACITY",
        label: "Capacity",
        maxPositive: 150,
        maxNegative: -100,
        score: 95,
        metrics: [
            { module: "CAPACITY", metricName: "DSCR", metricValue: "1.38x", formula: "(EBITDA - Tax) / (Interest + Principal)", sourceDocument: "Annual Report", sourcePage: 42, sourceExcerpt: "EBITDA: ₹42.6cr, Tax: ₹8.1cr, Interest: ₹18.2cr, Principal Repayment: ₹6.8cr", benchmarkContext: "Steel sector avg: 1.25x, Good threshold: 1.3x", scoreImpact: 30, reasoning: "DSCR of 1.38x is above sector average and good threshold, indicating adequate debt servicing capacity. However, conditional risk exists if RPT receivable becomes irrecoverable.", confidence: 0.94 },
            { module: "CAPACITY", metricName: "Revenue Growth", metricValue: "8.2% YoY", formula: "(Rev_FY25 - Rev_FY24) / Rev_FY24", sourceDocument: "Annual Report", sourcePage: 42, sourceExcerpt: "FY2025: ₹312.4cr, FY2024: ₹288.7cr, FY2023: ₹261.2cr", benchmarkContext: "Steel sector avg growth: 6.5% YoY", scoreImpact: 25, reasoning: "Consistent revenue growth above sector average for 3 consecutive years. Positive trajectory.", confidence: 0.96 },
            { module: "CAPACITY", metricName: "Working Capital Cycle", metricValue: "87 days", formula: "Inventory Days + Receivable Days - Payable Days", sourceDocument: "Annual Report", sourcePage: 52, sourceExcerpt: "Inventory: 45 days, Receivables: 62 days, Payables: 20 days", benchmarkContext: "Steel sector avg: 72 days", scoreImpact: -10, reasoning: "Working capital cycle 15 days above sector average, indicating slower collection or higher inventory holding. Moderate concern.", confidence: 0.92 },
            { module: "CAPACITY", metricName: "Cash Flow from Operations", metricValue: "₹28.4cr", formula: "Direct method from cash flow statement", sourceDocument: "Annual Report", sourcePage: 68, sourceExcerpt: "CFO: ₹28.4cr (FY25), ₹22.1cr (FY24)", benchmarkContext: "Positive and growing — adequate", scoreImpact: 25, reasoning: "Strong positive operating cash flow with 28.5% YoY growth. Supports debt servicing.", confidence: 0.95 },
            { module: "CAPACITY", metricName: "EMI Regularity", metricValue: "98.2%", formula: "On-time EMIs / Total EMIs in 12 months", sourceDocument: "Bank Statement", sourcePage: 15, sourceExcerpt: "55 of 56 EMI debits on or before due date. 1 delay of 3 days in Aug 2024.", benchmarkContext: "Threshold: 95%+", scoreImpact: 25, reasoning: "Excellent EMI regularity. Single minor delay does not indicate distress.", confidence: 0.97 },
        ],
    },
    {
        name: "CHARACTER",
        label: "Character",
        maxPositive: 120,
        maxNegative: -200,
        score: 42,
        metrics: [
            { module: "CHARACTER", metricName: "RPT Disclosure Quality", metricValue: "Partial concealment", formula: "AR RPT disclosure vs Board Minutes", sourceDocument: "Annual Report + Board Minutes", sourcePage: 87, sourceExcerpt: "AR: 2 RPTs (₹12.1cr), BM: 3 RPTs (₹18.2cr). ₹6.1cr undisclosed.", benchmarkContext: "Full disclosure expected", scoreImpact: -35, reasoning: "₹6.1cr inter-corporate deposit classified as investment rather than RPT. While arguably compliant, indicates weak disclosure practices.", confidence: 0.89 },
            { module: "CHARACTER", metricName: "Promoter NPA Link", metricValue: "Related entity NPA", formula: "Graph: Director → Company → NPA status", sourceDocument: "RBI Defaulter List + MCA21", sourcePage: 0, sourceExcerpt: "Agarwal Holdings: NPA with PNB since Oct 2025. Common director: Rajesh K. Agarwal.", benchmarkContext: "No related party NPA preferred", scoreImpact: -25, reasoning: "Promoter's related entity has NPA status. Creates cascade risk and raises character concerns about group financial management.", confidence: 0.92 },
            { module: "CHARACTER", metricName: "Credit Rating Trend", metricValue: "BBB+ (Upgraded)", formula: "Current rating vs historical", sourceDocument: "CRISIL Rating Report", sourcePage: 1, sourceExcerpt: "Upgraded from BBB to BBB+ in Feb 2025. Outlook: Stable.", benchmarkContext: "Upgrade is positive signal", scoreImpact: 12, reasoning: "Recent rating upgrade indicates improving credit profile as assessed by independent agency.", confidence: 0.99 },
            { module: "CHARACTER", metricName: "Promoter Track Record", metricValue: "20 years, no SEBI actions", formula: "SEBI + RBI check + business history", sourceDocument: "SEBI Scraper + MCA21", sourcePage: 0, sourceExcerpt: "No SEBI enforcement actions. Company incorporated 2005. Promoter in steel business since 2000.", benchmarkContext: "Clean record preferred", scoreImpact: 15, reasoning: "Long operating history with clean regulatory record (excluding current RPT concern).", confidence: 0.95 },
            { module: "CHARACTER", metricName: "Promoter Pledge", metricValue: "8.2%", formula: "Pledged shares / Total promoter shares", sourceDocument: "Shareholding Pattern", sourcePage: 2, sourceExcerpt: "Promoter holding: 62.4%, of which 8.2% pledged with ICICI Bank.", benchmarkContext: "Below 10% acceptable, above 25% red flag", scoreImpact: -5, reasoning: "Moderate pledge level. Below warning threshold but indicates some financial stress at promoter level.", confidence: 0.98 },
        ],
    },
    {
        name: "CAPITAL",
        label: "Capital",
        maxPositive: 80,
        maxNegative: -80,
        score: 28,
        metrics: [
            { module: "CAPITAL", metricName: "Debt-to-Equity", metricValue: "1.82x", formula: "Total Debt / Net Worth", sourceDocument: "Annual Report", sourcePage: 48, sourceExcerpt: "Total Debt: ₹142.3cr, Net Worth: ₹78.2cr", benchmarkContext: "Steel sector avg: 1.5x, Upper limit: 2.0x", scoreImpact: -15, reasoning: "D/E of 1.82x is above sector average but below upper limit. High leverage requires monitoring.", confidence: 0.95 },
            { module: "CAPITAL", metricName: "Net Worth", metricValue: "₹78.2cr", formula: "Share Capital + Reserves - Losses", sourceDocument: "Annual Report", sourcePage: 48, sourceExcerpt: "Paid-up capital: ₹10cr, Reserves: ₹68.2cr", benchmarkContext: "Adequate for ₹50cr WC facility", scoreImpact: 20, reasoning: "Net worth of ₹78.2cr provides reasonable equity cushion for the requested ₹50cr facility.", confidence: 0.96 },
            { module: "CAPITAL", metricName: "Interest Coverage", metricValue: "2.34x", formula: "EBITDA / Interest Expense", sourceDocument: "Annual Report", sourcePage: 42, sourceExcerpt: "EBITDA: ₹42.6cr / Interest: ₹18.2cr", benchmarkContext: "Minimum: 1.5x, Comfortable: 2.5x+", scoreImpact: 15, reasoning: "Interest coverage is adequate but not comfortable. Room for improvement.", confidence: 0.94 },
            { module: "CAPITAL", metricName: "Promoter Contribution", metricValue: "62.4%", formula: "Promoter equity / Total equity", sourceDocument: "Shareholding Pattern", sourcePage: 2, sourceExcerpt: "Promoter & Promoter Group: 62.4%", benchmarkContext: "Above 50% preferred", scoreImpact: 8, reasoning: "Strong promoter skin-in-the-game with majority holding.", confidence: 0.98 },
        ],
    },
    {
        name: "COLLATERAL",
        label: "Collateral",
        maxPositive: 60,
        maxNegative: -40,
        score: 35,
        metrics: [
            { module: "COLLATERAL", metricName: "Asset Coverage Ratio", metricValue: "1.6x", formula: "Collateral Value / Loan Amount", sourceDocument: "Annual Report", sourcePage: 55, sourceExcerpt: "Fixed assets: ₹82cr (net), Loan requested: ₹50cr", benchmarkContext: "Minimum: 1.25x for WC", scoreImpact: 25, reasoning: "Asset coverage of 1.6x provides adequate security margin above minimum threshold.", confidence: 0.95 },
            { module: "COLLATERAL", metricName: "Prior Liens", metricValue: "None", formula: "CERSAI / ROC charge search", sourceDocument: "MCA21 + CERSAI", sourcePage: 0, sourceExcerpt: "No existing charges registered on primary collateral assets.", benchmarkContext: "No prior liens preferred", scoreImpact: 10, reasoning: "Clean title on proposed collateral. No competing secured creditors on primary assets.", confidence: 0.97 },
        ],
    },
    {
        name: "CONDITIONS",
        label: "Conditions",
        maxPositive: 50,
        maxNegative: -50,
        score: 22,
        metrics: [
            { module: "CONDITIONS", metricName: "Sector Outlook", metricValue: "Neutral", formula: "Research intelligence aggregation", sourceDocument: "Research Agent", sourcePage: 0, sourceExcerpt: "Steel sector faces mixed signals: domestic demand up 5%, but Chinese overcapacity creating price pressure.", benchmarkContext: "Positive > Neutral > Negative", scoreImpact: 5, reasoning: "Neutral outlook — neither tailwind nor headwind. Domestic infrastructure spending provides floor.", confidence: 0.88 },
            { module: "CONDITIONS", metricName: "Order Book", metricValue: "₹89cr", formula: "Confirmed orders pipeline", sourceDocument: "Annual Report", sourcePage: 22, sourceExcerpt: "Confirmed order book as of Mar 31, 2025: ₹89cr from 12 customers.", benchmarkContext: "Above 1x annual revenue is strong", scoreImpact: 12, reasoning: "Order book at 28.5% of annual revenue provides reasonable near-term visibility.", confidence: 0.9 },
            { module: "CONDITIONS", metricName: "PLI Benefit", metricValue: "Eligible", formula: "PLI scheme for specialty steel check", sourceDocument: "Research Agent", sourcePage: 0, sourceExcerpt: "XYZ Steel is registered under PLI scheme for specialty steel. Potential incentive: ₹4-6cr over 5 years.", benchmarkContext: "PLI registration is positive", scoreImpact: 5, reasoning: "Government PLI incentive provides additional revenue support.", confidence: 0.85 },
        ],
    },
    {
        name: "COMPOUND",
        label: "Compound Risk",
        maxPositive: 57,
        maxNegative: -130,
        score: -45,
        metrics: [
            { module: "COMPOUND", metricName: "Cascade Risk (Agarwal Holdings)", metricValue: "High", formula: "Graph: RPT exposure × NPA probability × DSCR impact", sourceDocument: "Agent 2.5 Graph Reasoning", sourcePage: 0, sourceExcerpt: "If ₹18.2cr RPT becomes irrecoverable: DSCR drops from 1.38x to 0.97x (below 1.0 hard block).", benchmarkContext: "Any cascade to DSCR < 1.0 is critical", scoreImpact: -30, reasoning: "Significant cascade risk. The ₹18.2cr RPT exposure to an NPA-classified related entity creates a conditional hard block scenario. Mitigated by officer covenant (reduce RPT below ₹10cr in 6 months).", confidence: 0.85 },
            { module: "COMPOUND", metricName: "RPT Concealment Pattern", metricValue: "Detected", formula: "AR disclosure vs actual (Board Minutes + MCA21)", sourceDocument: "Agent 2.5 Graph Reasoning", sourcePage: 0, sourceExcerpt: "1 undisclosed RPT (₹6.1cr). Pattern: selective disclosure of only routine RPTs, concealing financial RPTs.", benchmarkContext: "Zero concealment expected", scoreImpact: -15, reasoning: "While the company argues technical compliance, the pattern of concealing financial RPTs while disclosing only routine trade RPTs indicates intentional selective disclosure.", confidence: 0.82 },
        ],
    },
];

export const mockCAM: CAMSection[] = [
    {
        title: "Executive Summary",
        content: "XYZ Steel Private Limited has applied for a Working Capital facility of ₹50,00,00,000. The company is a steel manufacturing firm incorporated in 2005, promoted by Mr. Rajesh Kumar Agarwal. Based on comprehensive AI-powered analysis of 8 documents, 5 government portal verifications, graph intelligence reasoning, and ML anomaly detection, the application is recommended for CONDITIONAL APPROVAL at ₹42,50,00,000 (85% of requested amount) at MCLR+2.5%.\n\nKey strengths include consistent revenue growth (8.2% YoY), adequate DSCR (1.38x), recent CRISIL upgrade (BBB+), and strong EMI track record (98.2%). Key concerns include high D/E ratio (1.82x), RPT concealment (₹6.1cr), and cascade risk from related party NPA (Agarwal Holdings). Two HIGH severity tickets were raised and resolved with covenants.",
        citations: [
            { document: "Annual Report", page: 42, excerpt: "Revenue FY2025: ₹312.4cr" },
            { document: "CRISIL Rating Report", page: 1, excerpt: "Upgraded to BBB+ (Stable)" },
            { document: "RBI Defaulter List", page: 0, excerpt: "Agarwal Holdings: NPA Oct 2025" },
        ],
    },
    {
        title: "Company Background & Promoter Profile",
        content: "XYZ Steel Private Limited (CIN: U27100MH2005PTC123456) was incorporated in Maharashtra in 2005. The company manufactures structural steel and specialty steel products. Mr. Rajesh Kumar Agarwal (62.4% promoter holding) has 20+ years of experience in the steel industry. The promoter also serves as director in Agarwal Holdings Pvt Ltd, AK Traders, and Steel Logistics India Pvt Ltd.\n\nThe company has an existing banking relationship with State Bank of India. Current credit facility utilization is satisfactory with no SMA classification.",
        citations: [
            { document: "MCA21 Company Master", page: 0, excerpt: "CIN: U27100MH2005PTC123456, Date of Inc: 15/03/2005" },
            { document: "Shareholding Pattern", page: 2, excerpt: "Promoter & Promoter Group: 62.4%" },
        ],
    },
    {
        title: "Financial Analysis",
        content: "Revenue has shown consistent growth over 3 years: ₹261.2cr (FY23) → ₹288.7cr (FY24) → ₹312.4cr (FY25), a CAGR of 9.4%. EBITDA margin is healthy at 13.6% (₹42.6cr on ₹312.4cr revenue). PAT margin is 4.8% (₹15.1cr).\n\nDebt profile shows total borrowings of ₹142.3cr against net worth of ₹78.2cr (D/E: 1.82x). DSCR is 1.38x — adequate but with conditional risk from RPT exposure. Working capital cycle of 87 days is 15 days above the steel sector average, driven by high receivable days (62 days).\n\nCross-verification: Revenue confirmed across 4 sources — AR (₹312.4cr), GST (₹308.7cr), ITR (₹310.1cr), Bank (₹298.6cr). Maximum deviation: 4.4%. ITR figure (₹310.1cr) accepted as primary reference (government source, weight 1.0).",
        citations: [
            { document: "Annual Report", page: 42, excerpt: "P&L: Revenue ₹312.4cr, EBITDA ₹42.6cr" },
            { document: "ITR6", page: 8, excerpt: "Schedule BP: Gross receipts ₹310.1cr" },
            { document: "GST Returns", page: 0, excerpt: "GSTR-3B aggregate: ₹308.7cr" },
            { document: "Bank Statement", page: 15, excerpt: "Annual credit inflows: ₹298.6cr" },
        ],
    },
    {
        title: "Risk Assessment & Fraud Indicators",
        content: "Graph Intelligence identified the following risk patterns:\n\n1. CASCADE RISK (HIGH): Agarwal Holdings (common director) classified as NPA with PNB. XYZ Steel has ₹18.2cr RPT exposure. If irrecoverable, DSCR drops to 0.97x (below 1.0 hard block).\n\n2. RPT CONCEALMENT (MODERATE): Annual Report discloses 2 RPTs (₹12.1cr) while Board Minutes record 3 RPTs (₹18.2cr). The ₹6.1cr inter-corporate deposit was classified as investment rather than RPT.\n\n3. GST ITC MISMATCH (LOW): GSTR-3B ITC (₹4.82cr) exceeds GSTR-2A (₹4.31cr) by ₹0.51cr. Verified as reverse charge + timing difference — no fraud indicated.\n\nML Anomaly Detection: Isolation Forest flagged no anomalies in bank statement transaction patterns. FinBERT analysis of Annual Report identified moderate buried risk language in management discussion section (confidence: 0.73).",
        citations: [
            { document: "Board Minutes", page: 12, excerpt: "Approved RPTs: 3 transactions, ₹18.2cr total" },
            { document: "Annual Report", page: 87, excerpt: "RPT disclosure: 2 transactions, ₹12.1cr" },
            { document: "RBI Defaulter List", page: 0, excerpt: "Agarwal Holdings: NPA" },
        ],
    },
    {
        title: "Score Breakdown & Recommendation",
        content: "Final Score: 677/850 — Band: GOOD\n\nCapacity: +95/150 | Character: +42/120 | Capital: +28/80 | Collateral: +35/60 | Conditions: +22/50 | Compound: -45/57\n\nBase Score: 500 + 95 + 42 + 28 + 35 + 22 + (-45) = 677\n\nRECOMMENDATION: CONDITIONAL APPROVAL\n• Amount: ₹42,50,00,000 (85% of requested ₹50cr)\n• Interest Rate: MCLR + 2.5%\n• Tenure: 12 months (renewable)\n\nCOVENANTS:\n1. RPT exposure to Agarwal Holdings group must reduce below ₹10cr within 6 months\n2. Quarterly D/E certification — must remain below 2.0x\n3. Monthly DSCR reporting for first 6 months\n4. Full RPT disclosure in future filings",
        citations: [
            { document: "Agent 3 — Score Engine", page: 0, excerpt: "Score computation: 500 base + module adjustments" },
        ],
    },
];

export const mockAssessment: Assessment = {
    sessionId: "IC-2026-03-05-001",
    company: mockCompany,
    documents: mockDocuments,
    pipeline: mockPipeline,
    workers: mockWorkers,
    thinkingEvents: mockThinkingEvents,
    tickets: mockTickets,
    finalScore: 677,
    scoreBand: "Good",
    recommendation: "Conditional Approval",
    interestRate: "MCLR + 2.5%",
    approvedAmount: "₹42,50,00,000",
    processingTime: "13m 00s",
    documentsAnalyzed: 8,
    findingsCount: 42,
    ticketsRaised: 3,
    ticketsResolved: 3,
    scoreModules: mockScoreModules,
    cam: mockCAM,
    hardBlocks: [],
    createdAt: "2026-03-05 10:00:00",
    completedAt: "2026-03-05 10:13:00",
    status: "completed",
};

export const mockHistory: HistoryRecord[] = [
    { sessionId: "IC-2026-03-05-001", companyName: "XYZ Steel Pvt Ltd", sector: "Steel Manufacturing", loanAmount: "₹50cr", loanType: "Working Capital", score: 677, scoreBand: "Good", status: "approved", date: "2026-03-05", officer: "Amit Sharma", recommendation: "85% at MCLR+2.5%" },
    { sessionId: "IC-2026-03-02-004", companyName: "Bharat Textiles Ltd", sector: "Textile", loanAmount: "₹25cr", loanType: "Term Loan", score: 742, scoreBand: "Good", status: "approved", date: "2026-03-02", officer: "Priya Nair", recommendation: "Full amount at MCLR+2.0%" },
    { sessionId: "IC-2026-02-28-002", companyName: "Sunrise Pharma Inc", sector: "Pharmaceuticals", loanAmount: "₹80cr", loanType: "Working Capital", score: 812, scoreBand: "Excellent", status: "approved", date: "2026-02-28", officer: "Amit Sharma", recommendation: "Full amount at MCLR+1.5%" },
    { sessionId: "IC-2026-02-25-003", companyName: "Quick Build Infra", sector: "Infrastructure", loanAmount: "₹120cr", loanType: "Term Loan", score: 423, scoreBand: "Poor", status: "rejected", date: "2026-02-25", officer: "Rahul Mehta", recommendation: "Reject — wilful defaulter" },
    { sessionId: "IC-2026-02-20-001", companyName: "Greenfield Agro Ltd", sector: "Agriculture", loanAmount: "₹15cr", loanType: "Working Capital", score: 598, scoreBand: "Fair", status: "approved", date: "2026-02-20", officer: "Priya Nair", recommendation: "65% at MCLR+3.5%" },
    { sessionId: "IC-2026-02-15-005", companyName: "Metro Electronics Pvt Ltd", sector: "Electronics", loanAmount: "₹35cr", loanType: "Letter of Credit", score: 701, scoreBand: "Good", status: "approved", date: "2026-02-15", officer: "Amit Sharma", recommendation: "85% at MCLR+2.5%" },
];

// Helper: Get color for thinking event type
export function getEventColor(eventType: ThinkingEvent["eventType"]): string {
    const colors: Record<string, string> = {
        READ: "text-slate-500",
        FOUND: "text-blue-600",
        COMPUTED: "text-indigo-600",
        ACCEPTED: "text-emerald-600",
        REJECTED: "text-red-600",
        FLAGGED: "text-amber-600",
        CRITICAL: "text-red-700",
        CONNECTING: "text-purple-600",
        CONCLUDING: "text-teal-600",
        QUESTIONING: "text-blue-500",
        DECIDED: "text-teal-700",
    };
    return colors[eventType] ?? "text-slate-500";
}

export function getEventBgColor(eventType: ThinkingEvent["eventType"]): string {
    const colors: Record<string, string> = {
        READ: "bg-slate-50",
        FOUND: "bg-blue-50",
        COMPUTED: "bg-indigo-50",
        ACCEPTED: "bg-emerald-50",
        REJECTED: "bg-red-50",
        FLAGGED: "bg-amber-50",
        CRITICAL: "bg-red-100",
        CONNECTING: "bg-purple-50",
        CONCLUDING: "bg-teal-50",
        QUESTIONING: "bg-blue-50",
        DECIDED: "bg-teal-50",
    };
    return colors[eventType] ?? "bg-slate-50";
}

export function getEventIcon(eventType: ThinkingEvent["eventType"]): string {
    const icons: Record<string, string> = {
        READ: "📄",
        FOUND: "🔍",
        COMPUTED: "🧮",
        ACCEPTED: "✅",
        REJECTED: "❌",
        FLAGGED: "⚠️",
        CRITICAL: "🚨",
        CONNECTING: "🔗",
        CONCLUDING: "💡",
        QUESTIONING: "💬",
        DECIDED: "📊",
    };
    return icons[eventType] ?? "📝";
}

export function getScoreBandColor(band: string): string {
    const colors: Record<string, string> = {
        "Excellent": "text-emerald-600",
        "Good": "text-teal-600",
        "Fair": "text-amber-600",
        "Poor": "text-orange-600",
        "Very Poor": "text-red-600",
        "Default Risk": "text-red-700",
    };
    return colors[band] ?? "text-slate-600";
}

export function getScoreBandBg(band: string): string {
    const colors: Record<string, string> = {
        "Excellent": "bg-emerald-50 border-emerald-200",
        "Good": "bg-teal-50 border-teal-200",
        "Fair": "bg-amber-50 border-amber-200",
        "Poor": "bg-orange-50 border-orange-200",
        "Very Poor": "bg-red-50 border-red-200",
        "Default Risk": "bg-red-100 border-red-300",
    };
    return colors[band] ?? "bg-slate-50 border-slate-200";
}

export function getSeverityColor(severity: string): string {
    const colors: Record<string, string> = {
        LOW: "bg-blue-50 text-blue-700 border-blue-200",
        HIGH: "bg-amber-50 text-amber-700 border-amber-200",
        CRITICAL: "bg-red-50 text-red-700 border-red-200",
    };
    return colors[severity] ?? "bg-slate-50 text-slate-700";
}
