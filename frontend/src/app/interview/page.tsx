"use client";

import { useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
    Users,
    MessageCircle,
    CheckCircle2,
    AlertCircle,
    ChevronRight,
    Save,
    Send,
    Building2,
    TrendingUp,
    Shield,
    Landmark,
    BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mockCompany } from "@/lib/mockData";
import { submitInterview } from "@/lib/api";
import { SiteVisitForm } from "@/components/dashboard/SiteVisitForm";

interface InterviewQuestion {
    id: string;
    category: string;
    question: string;
    placeholder: string;
    importance: "critical" | "high" | "medium";
}

const INTERVIEW_SECTIONS: { title: string; icon: React.ElementType; color: string; questions: InterviewQuestion[] }[] = [
    {
        title: "Capacity — Revenue & Repayment",
        icon: TrendingUp,
        color: "teal",
        questions: [
            { id: "c1", category: "CAPACITY", question: "What is the primary revenue driver and how has it trended over 3 years?", placeholder: "e.g., Steel coil manufacturing accounts for 70% of revenue, grew from ₹180cr to ₹248cr...", importance: "critical" },
            { id: "c2", category: "CAPACITY", question: "What is the current order book position and pipeline visibility?", placeholder: "e.g., Confirmed orders worth ₹85cr for next 6 months...", importance: "high" },
            { id: "c3", category: "CAPACITY", question: "How does the company plan to service the proposed debt?", placeholder: "e.g., Monthly EBITDA of ₹3.5cr against proposed EMI of ₹1.2cr...", importance: "critical" },
            { id: "c4", category: "CAPACITY", question: "What is the working capital cycle and any concentration risks?", placeholder: "e.g., Average WC cycle 90 days, top 3 customers are 40% of revenue...", importance: "high" },
        ],
    },
    {
        title: "Character — Promoter & Management",
        icon: Shield,
        color: "indigo",
        questions: [
            { id: "ch1", category: "CHARACTER", question: "What is the promoter's industry experience and track record?", placeholder: "e.g., Rajesh Agarwal has 22 years in steel, previously managed ₹200cr turnover...", importance: "critical" },
            { id: "ch2", category: "CHARACTER", question: "Are there any related party transactions and their nature?", placeholder: "e.g., RPTs with 2 group companies for raw material supply at market rates...", importance: "critical" },
            { id: "ch3", category: "CHARACTER", question: "Has the promoter or any director faced regulatory action?", placeholder: "e.g., No SEBI/RBI/MCA adverse orders. One tax dispute settled in 2021...", importance: "high" },
            { id: "ch4", category: "CHARACTER", question: "What is the succession plan and key-person dependency?", placeholder: "e.g., CFO and VP Operations can handle day-to-day, promoter's son being groomed...", importance: "medium" },
        ],
    },
    {
        title: "Capital — Net Worth & Structure",
        icon: Landmark,
        color: "amber",
        questions: [
            { id: "ca1", category: "CAPITAL", question: "What is the current D/E ratio and how will this loan impact it?", placeholder: "e.g., Current D/E is 1.2x, after proposed loan will be 1.8x...", importance: "critical" },
            { id: "ca2", category: "CAPITAL", question: "Has the promoter infused additional equity recently?", placeholder: "e.g., ₹10cr equity infused in FY24 from promoter's personal funds...", importance: "high" },
        ],
    },
    {
        title: "Collateral — Security Offered",
        icon: Building2,
        color: "emerald",
        questions: [
            { id: "co1", category: "COLLATERAL", question: "What collateral is being offered and its current valuation?", placeholder: "e.g., Factory land Bhiwandi 2 acres (₹40cr), Plant & machinery (₹25cr)...", importance: "high" },
            { id: "co2", category: "COLLATERAL", question: "Are there any existing charges or liens on the proposed security?", placeholder: "e.g., First charge to SBI on land (₹15cr outstanding), to be released...", importance: "critical" },
        ],
    },
    {
        title: "Conditions — Market & Sector",
        icon: BarChart3,
        color: "purple",
        questions: [
            { id: "cn1", category: "CONDITIONS", question: "What is the sector outlook and any headwinds/tailwinds?", placeholder: "e.g., Steel sector benefits from PLI scheme, infra push, but China dumping risk...", importance: "high" },
            { id: "cn2", category: "CONDITIONS", question: "Any regulatory changes that could impact the business?", placeholder: "e.g., New BIS quality standards being implemented, company already compliant...", importance: "medium" },
        ],
    },
];

export default function InterviewPage() {
    return (
        <Suspense fallback={<div className="p-6 text-slate-400">Loading...</div>}>
            <InterviewContent />
        </Suspense>
    );
}

function InterviewContent() {
    const searchParams = useSearchParams();
    const sessionId = searchParams.get("session");

    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [currentSection, setCurrentSection] = useState(0);
    const [submitted, setSubmitted] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const totalQuestions = INTERVIEW_SECTIONS.flatMap((s) => s.questions).length;
    const answeredCount = Object.values(answers).filter((a) => a.trim().length > 0).length;

    const updateAnswer = (id: string, value: string) => {
        setAnswers((prev) => ({ ...prev, [id]: value }));
    };

    const handleSubmit = async () => {
        setSubmitting(true);
        try {
            if (sessionId) {
                await submitInterview(sessionId, answers);
            }
        } catch {
            // API unavailable — proceed with local state for demo
        }
        setSubmitted(true);
        setSubmitting(false);
    };

    return (
        <div className="p-6 space-y-6 max-w-[1400px] mx-auto min-h-screen">
            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-indigo-500/10 rounded-xl">
                        <Users className="w-6 h-6 text-indigo-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-800">Management Interview</h1>
                        <p className="text-sm text-slate-500">
                            Structured 5 Cs interview — {mockCompany.name}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-slate-400">
                        {answeredCount}/{totalQuestions} answered
                    </span>
                    <div className="h-2 w-24 bg-slate-100 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-indigo-400 rounded-full transition-all"
                            style={{ width: `${(answeredCount / totalQuestions) * 100}%` }}
                        />
                    </div>
                </div>
            </div>

            {/* Section Navigation */}
            <div className="flex gap-2 overflow-x-auto pb-1">
                {INTERVIEW_SECTIONS.map((section, i) => {
                    const sectionAnswered = section.questions.filter((q) => answers[q.id]?.trim()).length;
                    const Icon = section.icon;
                    return (
                        <button
                            key={section.title}
                            onClick={() => setCurrentSection(i)}
                            className={cn(
                                "flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-bold whitespace-nowrap transition-all shrink-0",
                                currentSection === i
                                    ? "bg-white shadow-sm border border-slate-100 text-slate-800"
                                    : "text-slate-400 hover:bg-white/50 hover:text-slate-600"
                            )}
                        >
                            <Icon className="w-4 h-4" />
                            {section.title.split("—")[0].trim()}
                            {sectionAnswered === section.questions.length && (
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                            )}
                            {sectionAnswered > 0 && sectionAnswered < section.questions.length && (
                                <span className="text-[9px] bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded font-black">
                                    {sectionAnswered}/{section.questions.length}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* Current Section */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
                <div className="flex items-center gap-2 mb-6">
                    {(() => { const Icon = INTERVIEW_SECTIONS[currentSection].icon; return <Icon className="w-5 h-5 text-slate-400" />; })()}
                    <h2 className="text-base font-bold text-slate-900">
                        {INTERVIEW_SECTIONS[currentSection].title}
                    </h2>
                </div>

                <div className="space-y-6">
                    {INTERVIEW_SECTIONS[currentSection].questions.map((q) => (
                        <div key={q.id} className="space-y-2">
                            <div className="flex items-start justify-between gap-2">
                                <label className="text-sm font-semibold text-slate-700 leading-relaxed">
                                    {q.question}
                                </label>
                                <span className={cn(
                                    "text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0",
                                    q.importance === "critical" ? "bg-red-50 text-red-500" :
                                    q.importance === "high" ? "bg-amber-50 text-amber-600" :
                                    "bg-slate-50 text-slate-400"
                                )}>
                                    {q.importance}
                                </span>
                            </div>
                            <textarea
                                rows={3}
                                value={answers[q.id] || ""}
                                onChange={(e) => updateAnswer(q.id, e.target.value)}
                                disabled={submitted}
                                placeholder={q.placeholder}
                                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all placeholder:text-slate-400 resize-none disabled:opacity-60"
                            />
                        </div>
                    ))}
                </div>

                {/* Navigation */}
                <div className="flex items-center justify-between mt-8 pt-4 border-t border-slate-100">
                    <button
                        onClick={() => setCurrentSection(Math.max(0, currentSection - 1))}
                        disabled={currentSection === 0}
                        className="px-4 py-2 text-xs font-bold text-slate-400 hover:text-slate-700 disabled:opacity-30 transition-colors"
                    >
                        ← Previous Section
                    </button>

                    {currentSection < INTERVIEW_SECTIONS.length - 1 ? (
                        <button
                            onClick={() => setCurrentSection(currentSection + 1)}
                            className="flex items-center gap-1 px-5 py-2.5 bg-slate-800 text-white rounded-lg text-xs font-bold hover:bg-slate-700 transition-colors"
                        >
                            Next Section <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                    ) : (
                        <button
                            onClick={handleSubmit}
                            disabled={submitted || submitting || answeredCount === 0}
                            className={cn(
                                "flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-bold transition-all uppercase tracking-wide",
                                submitted
                                    ? "bg-emerald-100 text-emerald-700"
                                    : "bg-teal-500 text-white hover:bg-teal-600 shadow-lg shadow-teal-500/20"
                            )}
                        >
                            {submitted ? (
                                <><CheckCircle2 className="w-4 h-4" /> Submitted</>
                            ) : submitting ? (
                                <>Submitting...</>
                            ) : (
                                <><Send className="w-4 h-4" /> Submit Interview</>
                            )}
                        </button>
                    )}
                </div>
            </div>

            {/* Site Visit Report */}
            <SiteVisitForm />
        </div>
    );
}
