"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
    BarChart3,
    TrendingUp,
    TrendingDown,
    FileText,
    Download,
    ChevronDown,
    ChevronRight,
    Target,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Info,
    ExternalLink,
    Minus,
    Shield,
    Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    mockAssessment,
    mockScoreModules,
    mockCAM,
    mockCompany,
    getScoreBandColor,
    getScoreBandBg,
    type ScoreModule,
    type CAMSection,
} from "@/lib/mockData";
import { getScore, getAssessment, type ScoreResult } from "@/lib/api";
import { KnowledgeGraph } from "@/components/dashboard/KnowledgeGraph";

export default function ResultsPage() {
    return (
        <Suspense fallback={<div className="p-6 text-slate-400">Loading...</div>}>
            <ResultsContent />
        </Suspense>
    );
}

function ResultsContent() {
    const searchParams = useSearchParams();
    const sessionId = searchParams.get("session");

    const [activeTab, setActiveTab] = useState<"score" | "cam" | "graph">("score");
    const [expandedModule, setExpandedModule] = useState<string | null>("CAPACITY");
    const [expandedCAM, setExpandedCAM] = useState<string | null>(null);
    const [loading, setLoading] = useState(!!sessionId);

    // Score data (from API or mock)
    const [scoreData, setScoreData] = useState<ScoreResult | null>(null);
    const [companyName, setCompanyName] = useState(mockCompany.name);
    const [sessionLabel, setSessionLabel] = useState(mockAssessment.sessionId);
    const [assessmentMeta, setAssessmentMeta] = useState({
        recommendation: mockAssessment.recommendation,
        approvedAmount: mockAssessment.approvedAmount,
        interestRate: mockAssessment.interestRate,
        processingTime: mockAssessment.processingTime,
        documentsAnalyzed: mockAssessment.documentsAnalyzed,
        findingsCount: mockAssessment.findingsCount,
        ticketsRaised: mockAssessment.ticketsRaised,
        ticketsResolved: mockAssessment.ticketsResolved,
    });
    const [camSections, setCamSections] = useState<CAMSection[]>(mockCAM);
    const [modules, setModules] = useState<ScoreModule[]>(mockScoreModules);

    useEffect(() => {
        if (!sessionId) return;
        let cancelled = false;

        async function loadData() {
            try {
                const [score, assessment] = await Promise.all([
                    getScore(sessionId!),
                    getAssessment(sessionId!),
                ]);
                if (cancelled) return;

                setScoreData(score);
                setCompanyName(score.companyName || assessment.company.name);
                setSessionLabel(sessionId!);
                setModules(score.modules.length > 0 ? score.modules : mockScoreModules);
                setAssessmentMeta({
                    recommendation: score.recommendation || mockAssessment.recommendation,
                    approvedAmount: `${score.loanTerms.sanctionPct}% of requested`,
                    interestRate: score.loanTerms.rate || mockAssessment.interestRate,
                    processingTime: assessment.processingTime || mockAssessment.processingTime,
                    documentsAnalyzed: assessment.documentsAnalyzed || mockAssessment.documentsAnalyzed,
                    findingsCount: assessment.findingsCount || mockAssessment.findingsCount,
                    ticketsRaised: assessment.ticketsRaised || mockAssessment.ticketsRaised,
                    ticketsResolved: assessment.ticketsResolved || mockAssessment.ticketsResolved,
                });
                // CAM sections stay mock unless we parse from API
            } catch {
                // Fallback to mock data — already set as defaults
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        loadData();
        return () => { cancelled = true; };
    }, [sessionId]);

    const totalScore = scoreData?.score ?? mockAssessment.finalScore;
    const band = scoreData?.scoreBand ?? mockAssessment.scoreBand;
    const maxScore = 850;
    const scorePercent = (totalScore / maxScore) * 100;

    return (
        <div className="p-6 space-y-6 max-w-[1600px] mx-auto min-h-screen">
            {loading && (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="w-8 h-8 text-teal-500 animate-spin" />
                    <span className="ml-3 text-sm text-slate-500">Loading results...</span>
                </div>
            )}

            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-teal-500/10 rounded-xl">
                        <Target className="w-6 h-6 text-teal-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-800">Assessment Results</h1>
                        <p className="text-sm text-slate-500">
                            {companyName} — Session {sessionLabel.slice(0, 8)}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <button className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors">
                        <Download className="w-3.5 h-3.5" /> Export PDF
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-600 hover:bg-slate-50 transition-colors">
                        <FileText className="w-3.5 h-3.5" /> Export DOCX
                    </button>
                </div>
            </div>

            {/* Tab Switch */}
            <div className="flex bg-white rounded-lg p-0.5 shadow-sm border border-slate-100 w-fit">
                {[
                    { key: "score" as const, label: "SCORE DASHBOARD" },
                    { key: "cam" as const, label: "CREDIT APPRAISAL MEMO" },
                    { key: "graph" as const, label: "KNOWLEDGE GRAPH" },
                ].map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={cn(
                            "px-5 py-2 rounded-md text-[11px] font-black transition-all",
                            activeTab === tab.key
                                ? "bg-teal-500 text-white shadow-md"
                                : "text-slate-400 hover:text-slate-600"
                        )}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {activeTab === "score" ? (
                <ScoreDashboard
                    totalScore={totalScore}
                    maxScore={maxScore}
                    scorePercent={scorePercent}
                    band={band}
                    expandedModule={expandedModule}
                    setExpandedModule={setExpandedModule}
                    modules={modules}
                    meta={assessmentMeta}
                />
            ) : activeTab === "cam" ? (
                <CAMViewer expandedCAM={expandedCAM} setExpandedCAM={setExpandedCAM} camSections={camSections} />
            ) : (
                <KnowledgeGraph />
            )}
        </div>
    );
}

/* ─── Score Dashboard ────────────────────────────────────────── */
function ScoreDashboard({
    totalScore, maxScore, scorePercent, band, expandedModule, setExpandedModule, modules, meta,
}: {
    totalScore: number; maxScore: number; scorePercent: number; band: string;
    expandedModule: string | null; setExpandedModule: (m: string | null) => void;
    modules: ScoreModule[];
    meta: { recommendation: string; approvedAmount: string; interestRate: string; processingTime: string; documentsAnalyzed: number; findingsCount: number; ticketsRaised: number; ticketsResolved: number };
}) {
    return (
        <div className="space-y-6">
            {/* Top Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Score Gauge */}
                <div className="md:col-span-1 bg-white rounded-xl shadow-sm border border-slate-100 p-6 flex flex-col items-center justify-center">
                    <div className="relative w-36 h-36">
                        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                            <circle cx="50" cy="50" r="42" fill="none" stroke="#f1f5f9" strokeWidth="8" />
                            <circle
                                cx="50" cy="50" r="42" fill="none"
                                stroke={totalScore >= 750 ? "#10b981" : totalScore >= 650 ? "#14b8a6" : totalScore >= 550 ? "#f59e0b" : "#ef4444"}
                                strokeWidth="8" strokeLinecap="round"
                                strokeDasharray={`${scorePercent * 2.64} ${264 - scorePercent * 2.64}`}
                            />
                        </svg>
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-3xl font-black text-slate-900">{totalScore}</span>
                            <span className="text-[10px] font-bold text-slate-400">/ {maxScore}</span>
                        </div>
                    </div>
                    <div className={cn("mt-3 px-3 py-1 rounded-full text-xs font-black", getScoreBandBg(band), getScoreBandColor(band))}>
                        {band}
                    </div>
                </div>

                {/* Summary KPIs */}
                <div className="md:col-span-3 grid grid-cols-3 gap-4">
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                        <p className="text-[11px] font-black text-slate-400 uppercase tracking-wider mb-1">Recommendation</p>
                        <p className="text-lg font-bold text-slate-800">{meta.recommendation}</p>
                        <p className="text-xs text-slate-400 mt-1">{meta.approvedAmount}</p>
                    </div>
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                        <p className="text-[11px] font-black text-slate-400 uppercase tracking-wider mb-1">Interest Rate</p>
                        <p className="text-lg font-bold text-slate-800">{meta.interestRate}</p>
                        <p className="text-xs text-slate-400 mt-1">Based on score band</p>
                    </div>
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                        <p className="text-[11px] font-black text-slate-400 uppercase tracking-wider mb-1">Processing Time</p>
                        <p className="text-lg font-bold text-slate-800">{meta.processingTime}</p>
                        <p className="text-xs text-slate-400 mt-1">End-to-end pipeline</p>
                    </div>
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                        <p className="text-[11px] font-black text-slate-400 uppercase tracking-wider mb-1">Documents Analyzed</p>
                        <p className="text-lg font-bold text-slate-800">{meta.documentsAnalyzed}</p>
                        <p className="text-xs text-slate-400 mt-1">Across 8 types</p>
                    </div>
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                        <p className="text-[11px] font-black text-slate-400 uppercase tracking-wider mb-1">Findings</p>
                        <p className="text-lg font-bold text-slate-800">{meta.findingsCount}</p>
                        <p className="text-xs text-slate-400 mt-1">Cross-verified facts</p>
                    </div>
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                        <p className="text-[11px] font-black text-slate-400 uppercase tracking-wider mb-1">Tickets Raised</p>
                        <p className="text-lg font-bold text-slate-800">{meta.ticketsRaised}</p>
                        <p className="text-xs text-slate-400 mt-1">{meta.ticketsResolved} resolved</p>
                    </div>
                </div>
            </div>

            {/* Module Breakdown */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
                <h2 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-slate-400" />
                    Score Breakdown — 5 Cs + Compound
                </h2>
                <div className="space-y-2">
                    {modules.map((mod) => {
                        const isExpanded = expandedModule === mod.name;
                        const isPositive = mod.score >= 0;
                        const positivePoints = mod.metrics.filter(m => m.scoreImpact > 0).reduce((sum, m) => sum + m.scoreImpact, 0);
                        const negativePoints = mod.metrics.filter(m => m.scoreImpact < 0).reduce((sum, m) => sum + m.scoreImpact, 0);
                        return (
                            <div key={mod.name} className="border border-slate-100 rounded-lg overflow-hidden">
                                <button
                                    onClick={() => setExpandedModule(isExpanded ? null : mod.name)}
                                    className="w-full flex items-center gap-4 px-4 py-3 hover:bg-slate-50 transition-colors"
                                >
                                    <ChevronRight className={cn("w-4 h-4 text-slate-300 transition-transform", isExpanded && "rotate-90")} />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-xs font-bold text-slate-700">{mod.name}</span>
                                            <span className={cn(
                                                "text-xs font-black",
                                                isPositive ? "text-emerald-600" : "text-red-500"
                                            )}>
                                                {isPositive ? "+" : ""}{mod.score}
                                            </span>
                                        </div>
                                        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                                            <div className="flex h-full">
                                                <div
                                                    className="bg-emerald-400 h-full"
                                                    style={{ width: `${mod.maxPositive > 0 ? (positivePoints / mod.maxPositive) * 50 : 0}%` }}
                                                />
                                                <div
                                                    className="bg-red-400 h-full"
                                                    style={{ width: `${mod.maxNegative !== 0 ? (Math.abs(negativePoints) / Math.abs(mod.maxNegative)) * 50 : 0}%` }}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                    <span className="text-[10px] text-slate-400 shrink-0 w-24 text-right">
                                        +{positivePoints} / {negativePoints}
                                    </span>
                                </button>

                                {/* Expanded metrics */}
                                {isExpanded && (
                                    <div className="px-4 pb-4 bg-slate-50/50">
                                        <div className="border-t border-slate-100 pt-3 space-y-2">
                                            {mod.metrics.map((metric, i) => (
                                                <div key={i} className="flex items-start gap-3 py-2 px-3 bg-white rounded-lg border border-slate-50">
                                                    <div className={cn("mt-0.5", metric.scoreImpact > 0 ? "text-emerald-500" : metric.scoreImpact < 0 ? "text-red-500" : "text-slate-400")}>
                                                        {metric.scoreImpact > 0 ? <TrendingUp className="w-3.5 h-3.5" /> : metric.scoreImpact < 0 ? <TrendingDown className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center justify-between">
                                                            <span className="text-[11px] font-bold text-slate-700">{metric.metricName}</span>
                                                            <span className={cn(
                                                                "text-[11px] font-black",
                                                                metric.scoreImpact > 0 ? "text-emerald-600" : metric.scoreImpact < 0 ? "text-red-500" : "text-slate-400"
                                                            )}>
                                                                {metric.scoreImpact > 0 ? "+" : ""}{metric.scoreImpact}
                                                            </span>
                                                        </div>
                                                        <p className="text-[10px] text-slate-500 mt-0.5">{metric.metricValue} — {metric.reasoning}</p>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <span className="text-[9px] text-slate-400 flex items-center gap-0.5">
                                                                <FileText className="w-2.5 h-2.5" /> {metric.sourceDocument}
                                                            </span>
                                                            <span className="text-[9px] text-slate-300">
                                                                Confidence: {Math.round(metric.confidence * 100)}%
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}

/* ─── CAM Viewer ─────────────────────────────────────────────── */
function CAMViewer({
    expandedCAM, setExpandedCAM, camSections,
}: {
    expandedCAM: string | null; setExpandedCAM: (s: string | null) => void;
    camSections: CAMSection[];
}) {
    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100">
            {/* CAM Header */}
            <div className="px-6 py-5 border-b border-slate-100">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-lg font-bold text-slate-900">Credit Appraisal Memorandum</h2>
                        <p className="text-sm text-slate-500 mt-0.5">AI-generated with full citation tracing</p>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-lg">
                        <Shield className="w-4 h-4 text-teal-500" />
                        <span className="text-[11px] font-bold text-slate-600">Every claim is source-traceable</span>
                    </div>
                </div>
            </div>

            {/* CAM Sections */}
            <div className="divide-y divide-slate-100">
                {camSections.map((section) => {
                    const isExpanded = expandedCAM === section.title;
                    return (
                        <div key={section.title}>
                            <button
                                onClick={() => setExpandedCAM(isExpanded ? null : section.title)}
                                className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-50 transition-colors"
                            >
                                <div className="flex items-center gap-3">
                                    <ChevronRight className={cn("w-4 h-4 text-slate-300 transition-transform", isExpanded && "rotate-90")} />
                                    <div className="text-left">
                                        <h3 className="text-sm font-bold text-slate-800">{section.title}</h3>
                                        <p className="text-[11px] text-slate-400">{section.citations.length} citations</p>
                                    </div>
                                </div>
                            </button>
                            {isExpanded && (
                                <div className="px-6 pb-6 pt-0">
                                    <div className="bg-slate-50 rounded-lg p-5 prose prose-sm prose-slate max-w-none">
                                        {section.content.split("\n").map((para, i) => (
                                            <p key={i} className="text-sm text-slate-700 leading-relaxed mb-3 last:mb-0">
                                                {para}
                                            </p>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
