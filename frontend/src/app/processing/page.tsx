"use client";

import { useState, useEffect, useRef, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
    Activity,
    Cpu,
    CheckCircle2,
    Circle,
    Loader2,
    XCircle,
    MessageSquare,
    Filter,
    ChevronRight,
    ArrowDown,
    Clock,
    Zap,
    Brain,
    Search,
    Shield,
    FileCheck,
    BarChart3,
    FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    mockPipeline,
    mockWorkers,
    mockThinkingEvents,
    mockCompany,
    getEventColor,
    getEventBgColor,
    getEventIcon,
    type ThinkingEvent,
    type PipelineStage,
    type WorkerStatus,
} from "@/lib/mockData";
import {
    connectThinkingWS,
    getPipelineStatus,
    getAssessment,
    type PipelineStatus,
} from "@/lib/api";
import { FlowerEmbed } from "@/components/dashboard/FlowerEmbed";

const STAGE_ICONS: Record<string, React.ElementType> = {
    "Document Ingestion": FileText,
    "Agent 0.5 — Consolidator": Zap,
    "Validation Gate": Shield,
    "Agent 1.5 — Organizer": Brain,
    "Agent 2 — Research": Search,
    "Agent 2.5 — Reasoning": Brain,
    "Evidence Packaging": FileCheck,
    "Ticket Resolution": MessageSquare,
    "Agent 3 — Scorer & CAM": BarChart3,
};

export default function ProcessingPage() {
    return (
        <Suspense fallback={<div className="min-h-screen bg-slate-50 flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-teal-600" /></div>}>
            <ProcessingContent />
        </Suspense>
    );
}

function ProcessingContent() {
    const searchParams = useSearchParams();
    const sessionId = searchParams.get("session");

    const [activeFilter, setActiveFilter] = useState<string>("all");
    const [visibleEvents, setVisibleEvents] = useState<ThinkingEvent[]>([]);
    const [autoScroll, setAutoScroll] = useState(true);
    const [pipeline, setPipeline] = useState<PipelineStage[]>(mockPipeline);
    const [workers, setWorkers] = useState<WorkerStatus[]>(mockWorkers);
    const [companyName, setCompanyName] = useState(mockCompany.name);
    const [loanInfo, setLoanInfo] = useState(`${mockCompany.loanAmount} ${mockCompany.loanType}`);
    const [wsConnected, setWsConnected] = useState(false);
    const chatRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<WebSocket | null>(null);

    // Connect WebSocket for thinking events when session is available
    useEffect(() => {
        if (!sessionId) {
            // No session — fall back to mock simulation
            let index = 0;
            const interval = setInterval(() => {
                if (index < mockThinkingEvents.length) {
                    const current = index;
                    setVisibleEvents((prev) => [...prev, mockThinkingEvents[current]]);
                    index++;
                } else {
                    clearInterval(interval);
                }
            }, 800);
            return () => clearInterval(interval);
        }

        // Real session — connect WebSocket
        const ws = connectThinkingWS(
            sessionId,
            (event) => setVisibleEvents((prev) => [...prev, event]),
            () => setWsConnected(true),
            () => setWsConnected(false),
            () => setWsConnected(false),
        );
        wsRef.current = ws;

        return () => {
            ws.close();
            wsRef.current = null;
        };
    }, [sessionId]);

    // Poll pipeline status when we have a session
    useEffect(() => {
        if (!sessionId) return;

        const poll = async () => {
            try {
                const status = await getPipelineStatus(sessionId);
                setPipeline(status.stages);
            } catch {
                // Keep mock data on error
            }
        };

        poll();
        const interval = setInterval(poll, 3000);
        return () => clearInterval(interval);
    }, [sessionId]);

    // Fetch assessment company info
    useEffect(() => {
        if (!sessionId) return;

        getAssessment(sessionId).then((a) => {
            setCompanyName(a.company.name);
            setLoanInfo(`${a.company.loanAmount} ${a.company.loanType}`);
            setWorkers(a.workers);
        }).catch(() => {});
    }, [sessionId]);

    // Auto-scroll chatbot
    useEffect(() => {
        if (autoScroll && chatRef.current) {
            chatRef.current.scrollTop = chatRef.current.scrollHeight;
        }
    }, [visibleEvents, autoScroll]);

    const filteredEvents = (
        activeFilter === "all"
            ? visibleEvents
            : visibleEvents.filter((e) => e?.agent?.includes(activeFilter))
    ).filter(Boolean);

    const overallProgress = pipeline.filter((s) => s.status === "completed").length / pipeline.length;

    const agentFilters = [
        { key: "all", label: "All Agents" },
        { key: "Worker", label: "Workers" },
        { key: "Consolidator", label: "Agent 0.5" },
        { key: "Organizer", label: "Agent 1.5" },
        { key: "Research", label: "Agent 2" },
        { key: "Reasoning", label: "Agent 2.5" },
        { key: "Scorer", label: "Agent 3" },
    ];

    return (
        <div className="p-6 space-y-6 max-w-[1800px] mx-auto min-h-screen">
            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-teal-500/10 rounded-xl">
                        <Activity className="w-6 h-6 text-teal-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-800">Processing Dashboard</h1>
                        <p className="text-sm text-slate-500">
                            {companyName} — {loanInfo}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <div className={cn("h-2.5 w-2.5 rounded-full", wsConnected ? "bg-emerald-400 animate-pulse" : "bg-slate-300")} />
                    <span className={cn("text-xs font-bold", wsConnected ? "text-emerald-600" : "text-slate-400")}>
                        {wsConnected ? "LIVE" : sessionId ? "CONNECTING..." : "DEMO"}
                    </span>
                </div>
            </div>

            {/* Overall Progress */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-black text-slate-400 uppercase tracking-wider">Pipeline Progress</span>
                    <span className="text-sm font-bold text-teal-600">{Math.round(overallProgress * 100)}%</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-teal-400 to-teal-500 rounded-full transition-all duration-1000"
                        style={{ width: `${overallProgress * 100}%` }}
                    />
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
                {/* Left Column — Pipeline + Workers */}
                <div className="xl:col-span-6 space-y-6">
                    {/* Pipeline Stages */}
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                        <h2 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                            <Cpu className="w-4 h-4 text-slate-400" />
                            Pipeline Stages
                        </h2>
                        <div className="space-y-1">
                            {pipeline.map((stage, i) => {
                                const Icon = STAGE_ICONS[stage.name] || Circle;
                                return (
                                    <div key={stage.name} className="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-slate-50 transition-colors">
                                        <div className="relative">
                                            {stage.status === "completed" && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                                            {stage.status === "in_progress" && <Loader2 className="w-5 h-5 text-teal-500 animate-spin" />}
                                            {stage.status === "pending" && <Circle className="w-5 h-5 text-slate-200" />}
                                            {stage.status === "failed" && <XCircle className="w-5 h-5 text-red-500" />}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className={cn(
                                                "text-xs font-bold truncate",
                                                stage.status === "completed" ? "text-slate-600" :
                                                stage.status === "in_progress" ? "text-teal-700" : "text-slate-400"
                                            )}>
                                                {stage.name}
                                            </p>
                                            {stage.status === "in_progress" && (
                                                <div className="mt-1 h-1 bg-slate-100 rounded-full overflow-hidden">
                                                    <div className="h-full bg-teal-400 rounded-full animate-pulse" style={{ width: `${stage.progress}%` }} />
                                                </div>
                                            )}
                                            {stage.duration && (
                                                <p className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                                                    <Clock className="w-2.5 h-2.5" /> {stage.duration}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] gap-3 items-start">
                        {/* Worker Status Panel */}
                        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                            <h2 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                                <Zap className="w-4 h-4 text-slate-400" />
                                Document Workers
                            </h2>
                            <div className="space-y-3">
                                {workers.map((worker) => (
                                    <div key={worker.name} className="space-y-1.5">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[11px] font-bold text-slate-700">{worker.name}</span>
                                            <span className={cn(
                                                "text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded",
                                                worker.status === "completed" ? "bg-emerald-50 text-emerald-600" :
                                                worker.status === "processing" ? "bg-teal-50 text-teal-600" :
                                                worker.status === "error" ? "bg-red-50 text-red-500" :
                                                "bg-slate-50 text-slate-400"
                                            )}>
                                                {worker.status}
                                            </span>
                                        </div>
                                        <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                            <div
                                                className={cn(
                                                    "h-full rounded-full transition-all duration-500",
                                                    worker.status === "completed" ? "bg-emerald-400" :
                                                    worker.status === "processing" ? "bg-teal-400" :
                                                    worker.status === "error" ? "bg-red-400" : "bg-slate-200"
                                                )}
                                                style={{ width: `${worker.progress}%` }}
                                            />
                                        </div>
                                        {worker.currentTask && (
                                            <p className="text-[10px] text-slate-400 truncate">{worker.currentTask}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Flower Embed */}
                        <FlowerEmbed />
                    </div>
                </div>

                {/* Right Column — Live Thinking Chatbot */}
                <div className="xl:col-span-6">
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 flex flex-col h-[calc(100vh-300px)] min-h-[500px]">
                        {/* Chatbot Header */}
                        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
                            <div className="flex items-center gap-2">
                                <MessageSquare className="w-4 h-4 text-teal-500" />
                                <h2 className="text-sm font-bold text-slate-800">Live AI Reasoning</h2>
                                <span className="text-[10px] font-bold text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full">
                                    {visibleEvents.length} events
                                </span>
                            </div>
                            <button
                                onClick={() => setAutoScroll(!autoScroll)}
                                className={cn(
                                    "text-[10px] font-bold px-2 py-1 rounded transition-colors",
                                    autoScroll ? "bg-teal-50 text-teal-600" : "bg-slate-50 text-slate-400"
                                )}
                            >
                                <ArrowDown className="w-3 h-3 inline mr-1" />
                                {autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
                            </button>
                        </div>

                        {/* Agent Filter Bar */}
                        <div className="px-5 py-2 border-b border-slate-50 flex items-center gap-2 overflow-x-auto shrink-0">
                            <Filter className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                            {agentFilters.map((f) => (
                                <button
                                    key={f.key}
                                    onClick={() => setActiveFilter(f.key)}
                                    className={cn(
                                        "text-[10px] font-bold px-2.5 py-1 rounded-full whitespace-nowrap transition-all",
                                        activeFilter === f.key
                                            ? "bg-teal-500 text-white shadow-sm"
                                            : "bg-slate-50 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                                    )}
                                >
                                    {f.label}
                                </button>
                            ))}
                        </div>

                        {/* Event Stream */}
                        <div ref={chatRef} className="flex-1 overflow-y-auto px-5 py-3 space-y-2 custom-scrollbar">
                            {filteredEvents.map((event, i) => (
                                <div
                                    key={`${event.timestamp}-${i}`}
                                    className={cn(
                                        "flex gap-3 py-2 px-3 rounded-lg border-l-2 animate-in fade-in slide-in-from-bottom-2",
                                        getEventBgColor(event.eventType),
                                        `border-l-${getEventColor(event.eventType).replace("text-", "")}`
                                    )}
                                    style={{ borderLeftColor: getEventBorderColor(event.eventType) }}
                                >
                                    <span className="text-base shrink-0 mt-0.5">{getEventIcon(event.eventType)}</span>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-0.5">
                                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-wider">
                                                {event.agent}
                                            </span>
                                            <span className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded uppercase", getEventBgColor(event.eventType), getEventColor(event.eventType))}>
                                                {event.eventType}
                                            </span>
                                            <span className="text-[9px] text-slate-300 ml-auto shrink-0">
                                                {event.timestamp}
                                            </span>
                                        </div>
                                        <p className="text-xs text-slate-700 leading-relaxed">{event.message}</p>
                                        {event.source && (
                                            <p className="text-[10px] text-slate-400 mt-1 flex items-center gap-1">
                                                <FileText className="w-2.5 h-2.5" />
                                                {event.source}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            ))}
                            {visibleEvents.length < mockThinkingEvents.length && (
                                <div className="flex items-center justify-center py-4">
                                    <Loader2 className="w-4 h-4 text-teal-400 animate-spin mr-2" />
                                    <span className="text-[11px] text-slate-400 font-medium">AI is thinking...</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

/** Map event type to a concrete border color for the left accent */
function getEventBorderColor(type: string): string {
    const map: Record<string, string> = {
        READ: "#94a3b8",
        FOUND: "#14b8a6",
        COMPUTED: "#8b5cf6",
        ACCEPTED: "#10b981",
        REJECTED: "#ef4444",
        FLAGGED: "#f59e0b",
        CRITICAL: "#ef4444",
        CONNECTING: "#6366f1",
        CONCLUDING: "#14b8a6",
        QUESTIONING: "#3b82f6",
        DECIDED: "#10b981",
    };
    return map[type] || "#94a3b8";
}
