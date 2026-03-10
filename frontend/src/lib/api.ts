// =============================================================================
// Intelli-Credit — API Client
// Typed fetch wrappers for all 28 backend endpoints + 2 WebSocket connections
// Falls back to mock data when backend is unavailable (offline demo mode)
// =============================================================================

import {
    mockAssessment,
    mockPipeline,
    mockWorkers,
    mockThinkingEvents,
    mockCompany,
    mockTickets,
    mockScoreModules,
    mockCAM,
    mockHistory,
    type Assessment,
    type CompanyInfo,
    type DocumentUpload,
    type PipelineStage,
    type WorkerStatus,
    type ThinkingEvent,
    type Ticket,
    type ScoreModule,
    type ScoreBreakdownEntry,
    type CAMSection,
    type HistoryRecord,
} from "./mockData";

// --- Config ------------------------------------------------------------------

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const WS_BASE = API_BASE.replace(/^http/, "ws");

// --- Auth token helper -------------------------------------------------------

function getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("intelli_credit_token");
}

// --- Helpers -----------------------------------------------------------------

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const token = getToken();
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(init?.headers as Record<string, string> ?? {}),
    };
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers,
    });
    if (!res.ok) {
        throw new Error(`API ${res.status}: ${res.statusText}`);
    }
    return res.json() as Promise<T>;
}

// --- Score band mapping (backend UPPER_CASE → frontend Title Case) -----------

const SCORE_BAND_MAP: Record<string, string> = {
    EXCELLENT: "Excellent",
    GOOD: "Good",
    FAIR: "Fair",
    POOR: "Poor",
    VERY_POOR: "Very Poor",
    DEFAULT_RISK: "Default Risk",
};

function mapScoreBand(band: string | null | undefined): string {
    if (!band) return "Unknown";
    return SCORE_BAND_MAP[band] ?? band;
}

// --- Pipeline stage status mapping (backend → frontend) ----------------------

const STAGE_STATUS_MAP: Record<string, PipelineStage["status"]> = {
    PENDING: "pending",
    ACTIVE: "in_progress",
    COMPLETED: "completed",
    FAILED: "failed",
    SKIPPED: "skipped",
};

function mapStageStatus(status: string): PipelineStage["status"] {
    return STAGE_STATUS_MAP[status] ?? "pending";
}

// --- Worker status mapping ---------------------------------------------------

const WORKER_STATUS_MAP: Record<string, WorkerStatus["status"]> = {
    QUEUED: "idle",
    PROCESSING: "processing",
    COMPLETED: "completed",
    FAILED: "error",
};

function mapWorkerStatus(status: string): WorkerStatus["status"] {
    return WORKER_STATUS_MAP[status] ?? "idle";
}

// --- Ticket status mapping ---------------------------------------------------

const TICKET_STATUS_MAP: Record<string, Ticket["status"]> = {
    OPEN: "open",
    RESOLVED: "resolved",
    ESCALATED: "escalated",
};

function mapTicketStatus(status: string): Ticket["status"] {
    return TICKET_STATUS_MAP[status] ?? "open";
}

// --- Stage name mapping (backend stage key → frontend display name) ----------

const STAGE_NAMES: Record<string, { name: string; agent: string }> = {
    UPLOAD: { name: "Document Upload", agent: "Upload Service" },
    WORKERS: { name: "Document Ingestion", agent: "8 Parallel Workers" },
    CONSOLIDATION: { name: "Agent 0.5 — Consolidator", agent: "Agent 0.5 — The Consolidator" },
    VALIDATION: { name: "Validation Gate", agent: "Validator" },
    ORGANIZATION: { name: "Agent 1.5 — Organizer", agent: "Agent 1.5 — The Organizer" },
    RESEARCH: { name: "Agent 2 — Research", agent: "Agent 2 — The Researcher" },
    REASONING: { name: "Agent 2.5 — Reasoning", agent: "Agent 2.5 — 5 Passes" },
    EVIDENCE: { name: "Evidence Packaging", agent: "Evidence Package Builder" },
    TICKETS: { name: "Ticket Resolution", agent: "Ticketing Layer" },
    RECOMMENDATION: { name: "Agent 3 — Scorer & CAM", agent: "Agent 3 — The Judge" },
};

// --- Worker label mapping ----------------------------------------------------

const WORKER_LABELS: Record<string, { name: string; label: string }> = {
    W1: { name: "W1 — Annual Report", label: "W1 — Annual Report" },
    W2: { name: "W2 — Bank Statement", label: "W2 — Bank Statement" },
    W3: { name: "W3 — GST Returns", label: "W3 — GST Returns" },
    W4: { name: "W4 — ITR", label: "W4 — ITR" },
    W5: { name: "W5 — Legal Notice", label: "W5 — Legal Notice" },
    W6: { name: "W6 — Board Minutes", label: "W6 — Board Minutes" },
    W7: { name: "W7 — Shareholding", label: "W7 — Shareholding" },
    W8: { name: "W8 — Rating Report", label: "W8 — Rating Report" },
};

// =============================================================================
// Backend response types (snake_case, raw from API)
// =============================================================================

interface ApiCompany {
    name: string;
    cin?: string | null;
    gstin?: string | null;
    pan?: string | null;
    sector: string;
    loan_type: string;
    loan_amount: string;
    loan_amount_numeric: number;
    incorporation_year?: number | null;
    promoter_name?: string | null;
    annual_turnover?: string | null;
}

interface ApiDocument {
    filename: string;
    document_type: string;
    file_size: number;
}

interface ApiPipelineStage {
    stage: string;
    status: string;
    started_at?: string | null;
    completed_at?: string | null;
    message?: string | null;
}

interface ApiWorker {
    worker_id: string;
    document_type: string;
    status: string;
    current_task: string;
}

interface ApiAssessmentSummary {
    session_id: string;
    company: ApiCompany;
    documents: ApiDocument[];
    pipeline_stages: ApiPipelineStage[];
    workers: ApiWorker[];
    outcome: string;
    documents_analyzed: number;
    created_at: string;
    cam_url?: string | null;
    findings_count?: number;
    tickets_raised?: number;
    tickets_resolved?: number;
    completed_at?: string | null;
}

interface ApiHistoryRecord {
    session_id: string;
    company_name: string;
    sector: string;
    loan_type: string;
    loan_amount: string;
    score: number;
    score_band: string;
    outcome: string;
    processing_time?: string | null;
    created_at: string;
}

interface ApiScoreMetric {
    metric_name: string;
    metric_value: string;
    computation_formula: string;
    source_document: string;
    source_page: number;
    source_excerpt: string;
    benchmark_context: string;
    score_impact: number;
    reasoning: string;
    confidence: number;
    human_override: boolean;
}

interface ApiScoreModule {
    module: string;
    score_impact: number;
    metrics: ApiScoreMetric[];
}

interface ApiScoreResponse {
    session_id: string;
    company_name: string;
    score: number;
    score_band: string;
    outcome: string;
    recommendation: string;
    base_score: number;
    modules: ApiScoreModule[];
    hard_blocks: { trigger: string; description: string; score_cap: number }[];
    loan_terms: {
        sanction_pct: number;
        rate: string;
        tenure: string;
        review: string;
    };
    cam_url?: string | null;
    total_metrics: number;
    scored_at?: string | null;
}

interface ApiTicket {
    id: string;
    session_id: string;
    type: string;
    severity: string;
    title: string;
    description: string;
    evidence: {
        documents: string[];
        finding_ids: string[];
        reasoning: string;
    };
    status: string;
    resolution?: string | null;
    resolved_by?: string | null;
    resolved_at?: string | null;
    created_at: string;
    priority: number;
}

interface ApiTicketStats {
    total_tickets: number;
    open_tickets: number;
    resolved_tickets: number;
    escalated_tickets: number;
    by_severity: Record<string, number>;
    by_type: Record<string, number>;
    resolution_rate: number;
    avg_resolution_time: string;
}

interface ApiAnalytics {
    total_assessments: number;
    average_score: number;
    approval_rate: number;
    average_processing_time: string;
    score_distribution: Record<string, number>;
    sector_breakdown: { sector: string; count: number }[];
    outcome_distribution: Record<string, number>;
}

interface ApiPipelineStatus {
    session_id: string;
    is_running: boolean;
    outcome?: string | null;
    score?: number | null;
    score_band?: string | null;
    current_stage?: string | null;
    progress: {
        total: number;
        completed: number;
        failed: number;
        percent: number;
    };
    stages: ApiPipelineStage[];
    error?: string | null;
}

interface ApiComplianceFlag {
    id: string;
    trigger: string;
    severity: string;
    title: string;
    description: string;
    evidence: string;
    requires_notification: boolean;
    regulatory_reference: string;
    created_at: string;
}

interface ApiComplianceResult {
    session_id: string;
    flags: ApiComplianceFlag[];
    timestamp: string;
}

interface ApiDecisionRecord {
    session_id: string;
    company_name: string;
    sector: string;
    loan_type: string;
    loan_amount: string;
    score?: number | null;
    score_band?: string | null;
    outcome: string;
    modules: ApiScoreModule[];
    hard_blocks: unknown[];
    loan_terms?: {
        sanction_pct: number;
        rate: string;
        tenure: string;
        review: string;
    } | null;
    cam_url?: string | null;
    documents_analyzed: number;
    findings_count: number;
    tickets_raised: number;
    tickets_resolved: number;
    officer_notes: ApiOfficerNote[];
    processing_time?: string | null;
    created_at: string;
    completed_at?: string | null;
}

interface ApiOfficerNote {
    id: string;
    text: string;
    author: string;
    category: string;
    finding_id?: string | null;
    ticket_id?: string | null;
    created_at: string;
}

// =============================================================================
// Transform helpers (backend → frontend types)
// =============================================================================

function transformCompany(c: ApiCompany): CompanyInfo {
    return {
        name: c.name,
        cin: c.cin ?? "",
        loanAmount: c.loan_amount,
        loanType: c.loan_type,
        sector: c.sector,
        incorporationYear: c.incorporation_year ?? 0,
        promoter: c.promoter_name ?? "",
        existingBanker: "",
    };
}

function transformPipelineStages(stages: ApiPipelineStage[]): PipelineStage[] {
    return stages.map((s, i) => {
        const info = STAGE_NAMES[s.stage] ?? { name: s.stage, agent: s.stage };
        return {
            id: i + 1,
            name: info.name,
            agent: info.agent,
            status: mapStageStatus(s.status),
            progress: s.status === "COMPLETED" ? 100 : s.status === "ACTIVE" ? 50 : 0,
            duration: computeDuration(s.started_at, s.completed_at),
            startTime: s.started_at ? new Date(s.started_at).toLocaleTimeString() : undefined,
            endTime: s.completed_at ? new Date(s.completed_at).toLocaleTimeString() : undefined,
            thinkingCount: 0,
        };
    });
}

function transformWorkers(workers: ApiWorker[]): WorkerStatus[] {
    return workers.map((w) => {
        const info = WORKER_LABELS[w.worker_id] ?? { name: w.worker_id, label: w.worker_id };
        return {
            id: w.worker_id.toLowerCase(),
            name: info.name,
            label: info.label,
            document: w.document_type,
            status: mapWorkerStatus(w.status),
            progress: w.status === "COMPLETED" ? 100 : w.status === "PROCESSING" ? 50 : 0,
            pages: 0,
            currentPage: 0,
            currentTask: w.current_task,
        };
    });
}

function transformScoreModule(m: ApiScoreModule): ScoreModule {
    const MODULE_CONFIG: Record<string, { label: string; maxPositive: number; maxNegative: number }> = {
        CAPACITY: { label: "Capacity", maxPositive: 150, maxNegative: -100 },
        CHARACTER: { label: "Character", maxPositive: 120, maxNegative: -200 },
        CAPITAL: { label: "Capital", maxPositive: 80, maxNegative: -80 },
        COLLATERAL: { label: "Collateral", maxPositive: 60, maxNegative: -40 },
        CONDITIONS: { label: "Conditions", maxPositive: 50, maxNegative: -50 },
        COMPOUND: { label: "Compound Risk", maxPositive: 57, maxNegative: -130 },
    };

    const cfg = MODULE_CONFIG[m.module] ?? { label: m.module, maxPositive: 100, maxNegative: -100 };

    return {
        name: m.module,
        label: cfg.label,
        maxPositive: cfg.maxPositive,
        maxNegative: cfg.maxNegative,
        score: m.score_impact,
        metrics: m.metrics.map((met) => ({
            module: m.module,
            metricName: met.metric_name,
            metricValue: met.metric_value,
            formula: met.computation_formula,
            sourceDocument: met.source_document,
            sourcePage: met.source_page,
            sourceExcerpt: met.source_excerpt,
            benchmarkContext: met.benchmark_context,
            scoreImpact: met.score_impact,
            reasoning: met.reasoning,
            confidence: met.confidence,
        })),
    };
}

function transformTicket(t: ApiTicket): Ticket {
    return {
        id: t.id,
        title: t.title,
        severity: t.severity as Ticket["severity"],
        status: mapTicketStatus(t.status),
        source_agent: t.type,
        description: t.description,
        ai_evidence: t.evidence.documents.map((doc, i) => ({
            source: doc,
            finding_type: t.type,
            detail: t.evidence.reasoning,
            excerpt: undefined,
            page_ref: undefined,
        })),
        ai_recommendation: t.evidence.reasoning,
        humanResolution: t.resolution ?? undefined,
        created_at: t.created_at,
        resolvedAt: t.resolved_at ?? undefined,
        affected_documents: t.evidence.documents,
    };
}

function transformHistoryRecord(r: ApiHistoryRecord): HistoryRecord {
    return {
        sessionId: r.session_id,
        companyName: r.company_name,
        sector: r.sector,
        loanAmount: r.loan_amount,
        loanType: r.loan_type,
        score: r.score,
        scoreBand: mapScoreBand(r.score_band),
        status: r.outcome.toLowerCase(),
        date: r.created_at.split("T")[0],
        officer: "",
        recommendation: "",
    };
}

function computeDuration(start?: string | null, end?: string | null): string | undefined {
    if (!start || !end) return undefined;
    const ms = new Date(end).getTime() - new Date(start).getTime();
    const secs = Math.round(ms / 1000);
    if (secs < 60) return `${secs}s`;
    return `${Math.floor(secs / 60)}m ${secs % 60}s`;
}

// =============================================================================
// PUBLIC API FUNCTIONS
// =============================================================================

// --- Upload ------------------------------------------------------------------

export interface UploadParams {
    companyName: string;
    cin: string;
    loanAmount: string;
    loanType: string;
    sector: string;
    promoter: string;
    files: Record<string, File>;
}

export interface UploadResult {
    sessionId: string;
    company: CompanyInfo;
    documents: DocumentUpload[];
    pipeline: PipelineStage[];
    workers: WorkerStatus[];
}

export async function uploadDocuments(params: UploadParams): Promise<UploadResult> {
    const formData = new FormData();
    formData.append("company_name", params.companyName);
    formData.append("cin", params.cin);
    formData.append("loan_amount", params.loanAmount);
    formData.append("loan_type", params.loanType);
    formData.append("sector", params.sector);
    formData.append("promoter_name", params.promoter);

    // Parse numeric amount from display string
    const numericStr = params.loanAmount.replace(/[^\d.]/g, "");
    formData.append("loan_amount_numeric", numericStr || "0");

    const docTypes: string[] = [];
    for (const [docType, file] of Object.entries(params.files)) {
        formData.append("files", file);
        docTypes.push(docType);
    }
    formData.append("document_types", docTypes.join(","));

    const token = getToken();
    const uploadHeaders: Record<string, string> = {};
    if (token) {
        uploadHeaders["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        headers: uploadHeaders,
        body: formData,
    });

    if (!res.ok) {
        throw new Error(`Upload failed: ${res.status} ${res.statusText}`);
    }

    const data: ApiAssessmentSummary = await res.json();

    return {
        sessionId: data.session_id,
        company: transformCompany(data.company),
        documents: data.documents.map((d, i) => ({
            id: `d${i + 1}`,
            type: d.document_type,
            fileName: d.filename,
            status: "uploaded" as const,
            pages: 0,
            confidence: 0,
            workerLabel: `W${i + 1}`,
        })),
        pipeline: transformPipelineStages(data.pipeline_stages),
        workers: transformWorkers(data.workers),
    };
}

// --- Assessment --------------------------------------------------------------

export async function getAssessment(sessionId: string): Promise<Assessment> {
    try {
        const data = await apiFetch<ApiAssessmentSummary>(`/api/assessment/${encodeURIComponent(sessionId)}`);
        return {
            sessionId: data.session_id,
            company: transformCompany(data.company),
            documents: data.documents.map((d, i) => ({
                id: `d${i + 1}`,
                type: d.document_type,
                fileName: d.filename,
                status: "completed" as const,
                pages: 0,
                confidence: 0,
                workerLabel: `W${i + 1}`,
            })),
            pipeline: transformPipelineStages(data.pipeline_stages),
            workers: transformWorkers(data.workers),
            thinkingEvents: [],
            tickets: [],
            finalScore: 0,
            scoreBand: "Unknown",
            recommendation: "",
            interestRate: "",
            approvedAmount: "",
            processingTime: "",
            documentsAnalyzed: data.documents_analyzed,
            findingsCount: data.findings_count ?? 0,
            ticketsRaised: data.tickets_raised ?? 0,
            ticketsResolved: data.tickets_resolved ?? 0,
            scoreModules: [],
            cam: [],
            hardBlocks: [],
            createdAt: data.created_at,
            completedAt: data.completed_at ?? "",
            status: "processing",
        };
    } catch {
        return mockAssessment;
    }
}

// --- Score -------------------------------------------------------------------

export interface ScoreResult {
    sessionId: string;
    companyName: string;
    score: number;
    scoreBand: string;
    outcome: string;
    recommendation: string;
    baseScore: number;
    modules: ScoreModule[];
    hardBlocks: string[];
    loanTerms: {
        sanctionPct: number;
        rate: string;
        tenure: string;
        review: string;
    };
    camUrl: string | null;
    totalMetrics: number;
}

export async function getScore(sessionId: string): Promise<ScoreResult> {
    try {
        const data = await apiFetch<ApiScoreResponse>(`/api/score/${encodeURIComponent(sessionId)}`);
        return {
            sessionId: data.session_id,
            companyName: data.company_name,
            score: data.score,
            scoreBand: mapScoreBand(data.score_band),
            outcome: data.outcome,
            recommendation: data.recommendation,
            baseScore: data.base_score,
            modules: data.modules.map(transformScoreModule),
            hardBlocks: data.hard_blocks.map((hb) => hb.description),
            loanTerms: {
                sanctionPct: data.loan_terms.sanction_pct,
                rate: data.loan_terms.rate,
                tenure: data.loan_terms.tenure,
                review: data.loan_terms.review,
            },
            camUrl: data.cam_url ?? null,
            totalMetrics: data.total_metrics,
        };
    } catch {
        return {
            sessionId: mockAssessment.sessionId,
            companyName: mockCompany.name,
            score: mockAssessment.finalScore,
            scoreBand: mockAssessment.scoreBand,
            outcome: "CONDITIONAL",
            recommendation: mockAssessment.recommendation,
            baseScore: 500,
            modules: mockScoreModules,
            hardBlocks: mockAssessment.hardBlocks,
            loanTerms: { sanctionPct: 85, rate: "MCLR+2.5%", tenure: "12 months", review: "6-monthly" },
            camUrl: null,
            totalMetrics: 20,
        };
    }
}

export async function runScoring(sessionId: string): Promise<ScoreResult> {
    const data = await apiFetch<ApiScoreResponse>(`/api/score/${encodeURIComponent(sessionId)}/run`, { method: "POST" });
    return {
        sessionId: data.session_id,
        companyName: data.company_name,
        score: data.score,
        scoreBand: mapScoreBand(data.score_band),
        outcome: data.outcome,
        recommendation: data.recommendation,
        baseScore: data.base_score,
        modules: data.modules.map(transformScoreModule),
        hardBlocks: data.hard_blocks.map((hb) => hb.description),
        loanTerms: {
            sanctionPct: data.loan_terms.sanction_pct,
            rate: data.loan_terms.rate,
            tenure: data.loan_terms.tenure,
            review: data.loan_terms.review,
        },
        camUrl: data.cam_url ?? null,
        totalMetrics: data.total_metrics,
    };
}

// --- CAM ---------------------------------------------------------------------

export async function getCAM(sessionId: string): Promise<string> {
    try {
        const res = await fetch(`${API_BASE}/api/cam/${encodeURIComponent(sessionId)}`);
        if (!res.ok) throw new Error("CAM not found");
        return res.text();
    } catch {
        return mockCAM.map((s) => `## ${s.title}\n\n${s.content}`).join("\n\n---\n\n");
    }
}

// --- Tickets -----------------------------------------------------------------

export async function getTickets(sessionId: string): Promise<Ticket[]> {
    try {
        const data = await apiFetch<ApiTicket[]>(`/api/tickets/${encodeURIComponent(sessionId)}`);
        return data.map(transformTicket);
    } catch {
        return mockTickets;
    }
}

export async function getTicketStats(sessionId: string): Promise<ApiTicketStats> {
    return apiFetch<ApiTicketStats>(`/api/tickets/${encodeURIComponent(sessionId)}/stats`);
}

export async function resolveTicket(ticketId: string, resolution: string, resolvedBy: string = "Credit Officer"): Promise<Ticket> {
    const data = await apiFetch<ApiTicket>(`/api/tickets/${encodeURIComponent(ticketId)}/resolve`, {
        method: "POST",
        body: JSON.stringify({ resolution, resolved_by: resolvedBy }),
    });
    return transformTicket(data);
}

export async function escalateTicket(ticketId: string, reason: string, escalatedBy: string = "Credit Officer"): Promise<Ticket> {
    const data = await apiFetch<ApiTicket>(`/api/tickets/${encodeURIComponent(ticketId)}/escalate`, {
        method: "POST",
        body: JSON.stringify({ reason, escalated_by: escalatedBy }),
    });
    return transformTicket(data);
}

// --- Decisions ---------------------------------------------------------------

export async function getDecisions(params?: {
    sector?: string;
    outcome?: string;
    score_band?: string;
    search?: string;
    limit?: number;
    offset?: number;
}): Promise<HistoryRecord[]> {
    try {
        const query = new URLSearchParams();
        if (params?.sector) query.set("sector", params.sector);
        if (params?.outcome) query.set("outcome", params.outcome);
        if (params?.score_band) query.set("score_band", params.score_band);
        if (params?.search) query.set("search", params.search);
        if (params?.limit) query.set("limit", String(params.limit));
        if (params?.offset) query.set("offset", String(params.offset));

        const qs = query.toString();
        const data = await apiFetch<ApiHistoryRecord[]>(`/api/decisions${qs ? `?${qs}` : ""}`);
        return data.map(transformHistoryRecord);
    } catch {
        return mockHistory;
    }
}

export async function getDecisionDetail(sessionId: string): Promise<ApiDecisionRecord> {
    return apiFetch<ApiDecisionRecord>(`/api/decisions/${encodeURIComponent(sessionId)}`);
}

// --- Officer Notes -----------------------------------------------------------

export async function addNote(sessionId: string, text: string, category: string = "General", author: string = "Credit Officer"): Promise<ApiOfficerNote> {
    return apiFetch<ApiOfficerNote>(`/api/decisions/${encodeURIComponent(sessionId)}/notes`, {
        method: "POST",
        body: JSON.stringify({ text, category, author }),
    });
}

export async function getNotes(sessionId: string): Promise<ApiOfficerNote[]> {
    return apiFetch<ApiOfficerNote[]>(`/api/decisions/${encodeURIComponent(sessionId)}/notes`);
}

export async function deleteNote(sessionId: string, noteId: string): Promise<void> {
    await apiFetch<unknown>(`/api/decisions/${encodeURIComponent(sessionId)}/notes/${encodeURIComponent(noteId)}`, {
        method: "DELETE",
    });
}

// --- Analytics ---------------------------------------------------------------

export async function getAnalytics(): Promise<ApiAnalytics> {
    return apiFetch<ApiAnalytics>("/api/analytics");
}

// --- Pipeline ----------------------------------------------------------------

export async function runPipeline(sessionId: string): Promise<{ sessionId: string; status: string; message: string }> {
    const data = await apiFetch<{ session_id: string; status: string; message: string }>(
        `/api/pipeline/${encodeURIComponent(sessionId)}/run`,
        { method: "POST" }
    );
    return { sessionId: data.session_id, status: data.status, message: data.message };
}

export interface PipelineStatus {
    sessionId: string;
    isRunning: boolean;
    outcome: string | null;
    score: number | null;
    scoreBand: string | null;
    currentStage: string | null;
    progress: { total: number; completed: number; failed: number; percent: number };
    stages: PipelineStage[];
    error: string | null;
}

export async function getPipelineStatus(sessionId: string): Promise<PipelineStatus> {
    try {
        const data = await apiFetch<ApiPipelineStatus>(`/api/pipeline/${encodeURIComponent(sessionId)}/status`);
        return {
            sessionId: data.session_id,
            isRunning: data.is_running,
            outcome: data.outcome ?? null,
            score: data.score ?? null,
            scoreBand: data.score_band ? mapScoreBand(data.score_band) : null,
            currentStage: data.current_stage ?? null,
            progress: data.progress,
            stages: transformPipelineStages(data.stages),
            error: data.error ?? null,
        };
    } catch {
        return {
            sessionId,
            isRunning: false,
            outcome: null,
            score: null,
            scoreBand: null,
            currentStage: null,
            progress: { total: 9, completed: 0, failed: 0, percent: 0 },
            stages: mockPipeline,
            error: null,
        };
    }
}

export async function cancelPipeline(sessionId: string): Promise<void> {
    await apiFetch<unknown>(`/api/pipeline/${encodeURIComponent(sessionId)}/cancel`, { method: "POST" });
}

// --- Compliance --------------------------------------------------------------

// --- Interview ---------------------------------------------------------------

export async function submitInterview(
    sessionId: string,
    answers: Record<string, string>,
): Promise<{ status: string }> {
    return apiFetch<{ status: string }>(`/api/assessment/${encodeURIComponent(sessionId)}/interview`, {
        method: "POST",
        body: JSON.stringify({ answers }),
    });
}

// --- Compliance (continued) --------------------------------------------------

export async function getCompliance(sessionId: string): Promise<ApiComplianceResult> {
    return apiFetch<ApiComplianceResult>(`/api/compliance/${encodeURIComponent(sessionId)}`);
}

export async function runComplianceScan(sessionId: string): Promise<ApiComplianceResult> {
    return apiFetch<ApiComplianceResult>(`/api/compliance/${encodeURIComponent(sessionId)}/scan`, { method: "POST" });
}

export async function getComplianceFlags(sessionId: string, severity?: string): Promise<ApiComplianceFlag[]> {
    const query = severity ? `?severity=${encodeURIComponent(severity)}` : "";
    return apiFetch<ApiComplianceFlag[]>(`/api/compliance/${encodeURIComponent(sessionId)}/flags${query}`);
}

// =============================================================================
// WebSocket helpers
// =============================================================================

export function connectThinkingWS(
    sessionId: string,
    onMessage: (event: ThinkingEvent) => void,
    onOpen?: () => void,
    onClose?: () => void,
    onError?: (err: Event) => void,
): WebSocket {
    const token = getToken();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
    const ws = new WebSocket(`${WS_BASE}/ws/thinking/${encodeURIComponent(sessionId)}${tokenParam}`);

    ws.onopen = () => onOpen?.();

    ws.onmessage = (evt) => {
        try {
            const raw = JSON.parse(evt.data);
            const event: ThinkingEvent = {
                id: raw.id ?? raw.event_id ?? crypto.randomUUID(),
                timestamp: raw.timestamp ?? new Date().toLocaleTimeString(),
                agent: raw.agent ?? raw.agent_name ?? "Unknown",
                eventType: raw.event_type ?? raw.eventType ?? "READ",
                message: raw.message ?? raw.content ?? "",
                source: raw.source ?? raw.source_document ?? undefined,
                confidence: raw.confidence ?? undefined,
            };
            onMessage(event);
        } catch {
            // Ignore malformed messages
        }
    };

    ws.onclose = () => onClose?.();
    ws.onerror = (err) => onError?.(err);

    return ws;
}

export function connectProgressWS(
    sessionId: string,
    onMessage: (status: PipelineStatus) => void,
    onOpen?: () => void,
    onClose?: () => void,
): WebSocket {
    const token = getToken();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
    const ws = new WebSocket(`${WS_BASE}/ws/progress/${encodeURIComponent(sessionId)}${tokenParam}`);

    ws.onopen = () => onOpen?.();

    ws.onmessage = (evt) => {
        try {
            const raw = JSON.parse(evt.data);
            const status: PipelineStatus = {
                sessionId: raw.session_id ?? sessionId,
                isRunning: raw.is_running ?? true,
                outcome: raw.outcome ?? null,
                score: raw.score ?? null,
                scoreBand: raw.score_band ? mapScoreBand(raw.score_band) : null,
                currentStage: raw.current_stage ?? null,
                progress: raw.progress ?? { total: 9, completed: 0, failed: 0, percent: 0 },
                stages: raw.stages ? transformPipelineStages(raw.stages) : [],
                error: raw.error ?? null,
            };
            onMessage(status);
        } catch {
            // Ignore malformed messages
        }
    };

    ws.onclose = () => onClose?.();

    return ws;
}

// =============================================================================
// Convenience: check if backend is reachable
// =============================================================================

export async function isBackendAvailable(): Promise<boolean> {
    try {
        const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
        return res.ok;
    } catch {
        return false;
    }
}
