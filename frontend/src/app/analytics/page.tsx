"use client";

import { useState, useEffect } from "react";
import {
    BarChart3,
    TrendingUp,
    Clock,
    Target,
    Users,
    FileText,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Activity,
    Zap,
    PieChart,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mockHistory } from "@/lib/mockData";
import { getAnalytics } from "@/lib/api";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart as RePieChart, Pie } from "recharts";

// Derived analytics data
const monthlyData = [
    { month: "Jan", assessments: 12, approved: 8, rejected: 3, avgScore: 645 },
    { month: "Feb", assessments: 15, approved: 10, rejected: 4, avgScore: 662 },
    { month: "Mar", assessments: 18, approved: 13, rejected: 3, avgScore: 678 },
    { month: "Apr", assessments: 22, approved: 16, rejected: 4, avgScore: 655 },
    { month: "May", assessments: 19, approved: 14, rejected: 3, avgScore: 690 },
    { month: "Jun", assessments: 25, approved: 18, rejected: 5, avgScore: 672 },
];

const scoreBandDistribution = [
    { name: "Excellent (750-850)", value: 8, color: "#10b981" },
    { name: "Good (650-749)", value: 22, color: "#14b8a6" },
    { name: "Fair (550-649)", value: 15, color: "#f59e0b" },
    { name: "Poor (450-549)", value: 9, color: "#f97316" },
    { name: "Very Poor (<450)", value: 4, color: "#ef4444" },
];

const sectorData = [
    { sector: "Steel", count: 14, avgScore: 672 },
    { sector: "Textile", count: 11, avgScore: 638 },
    { sector: "Pharma", count: 9, avgScore: 715 },
    { sector: "Auto", count: 8, avgScore: 691 },
    { sector: "IT", count: 7, avgScore: 735 },
    { sector: "FMCG", count: 5, avgScore: 702 },
];

const processingTimeData = [
    { stage: "Ingestion", avg: 45 },
    { stage: "Consolidation", avg: 30 },
    { stage: "Validation", avg: 15 },
    { stage: "Organization", avg: 40 },
    { stage: "Research", avg: 120 },
    { stage: "Reasoning", avg: 90 },
    { stage: "Evidence", avg: 20 },
    { stage: "Tickets", avg: 60 },
    { stage: "Scoring", avg: 35 },
];

export default function AnalyticsPage() {
    const [kpi, setKpi] = useState({
        totalAssessments: "111",
        approvalRate: "72%",
        avgScore: "667",
        avgProcessing: "7m 35s",
    });

    useEffect(() => {
        let cancelled = false;
        getAnalytics()
            .then((data) => {
                if (cancelled) return;
                setKpi({
                    totalAssessments: String(data.total_assessments),
                    approvalRate: `${Math.round(data.approval_rate)}%`,
                    avgScore: String(Math.round(data.average_score)),
                    avgProcessing: data.average_processing_time || "7m 35s",
                });
            })
            .catch(() => { /* keep defaults */ });
        return () => { cancelled = true; };
    }, []);

    return (
        <div className="p-6 space-y-6 max-w-[1600px] mx-auto min-h-screen">
            {/* Page Header */}
            <div className="flex items-center gap-3">
                <div className="p-2.5 bg-purple-500/10 rounded-xl">
                    <BarChart3 className="w-6 h-6 text-purple-600" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-slate-800">Analytics Dashboard</h1>
                    <p className="text-sm text-slate-500">System-wide credit assessment metrics and trends</p>
                </div>
            </div>

            {/* KPI Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatKPI icon={FileText} label="Total Assessments" value={kpi.totalAssessments} trend="+18% MoM" trendUp={true} />
                <StatKPI icon={CheckCircle2} label="Approval Rate" value={kpi.approvalRate} trend="+3% vs last month" trendUp={true} />
                <StatKPI icon={Target} label="Average Score" value={kpi.avgScore} trend="-8 pts" trendUp={false} />
                <StatKPI icon={Clock} label="Avg Processing" value={kpi.avgProcessing} trend="-12% faster" trendUp={true} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Assessment Volume Trend */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                    <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                        <Activity className="w-4 h-4 text-slate-400" />
                        Assessment Volume (6 months)
                    </h3>
                    <ResponsiveContainer width="100%" height={240}>
                        <AreaChart data={monthlyData}>
                            <defs>
                                <linearGradient id="gradApproved" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
                                </linearGradient>
                                <linearGradient id="gradRejected" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} />
                            <Tooltip
                                contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px" }}
                            />
                            <Area type="monotone" dataKey="approved" stroke="#14b8a6" fill="url(#gradApproved)" strokeWidth={2} />
                            <Area type="monotone" dataKey="rejected" stroke="#ef4444" fill="url(#gradRejected)" strokeWidth={2} />
                        </AreaChart>
                    </ResponsiveContainer>
                    <div className="flex items-center justify-center gap-6 mt-2">
                        <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
                            <span className="w-3 h-1 rounded bg-teal-500" /> Approved
                        </span>
                        <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
                            <span className="w-3 h-1 rounded bg-red-500" /> Rejected
                        </span>
                    </div>
                </div>

                {/* Score Band Distribution */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                    <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                        <PieChart className="w-4 h-4 text-slate-400" />
                        Score Band Distribution
                    </h3>
                    <div className="flex items-center gap-6">
                        <ResponsiveContainer width="50%" height={220}>
                            <RePieChart>
                                <Pie
                                    data={scoreBandDistribution}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={55}
                                    outerRadius={90}
                                    paddingAngle={3}
                                    dataKey="value"
                                >
                                    {scoreBandDistribution.map((entry, i) => (
                                        <Cell key={i} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px" }} />
                            </RePieChart>
                        </ResponsiveContainer>
                        <div className="space-y-2.5 flex-1">
                            {scoreBandDistribution.map((band) => (
                                <div key={band.name} className="flex items-center gap-2">
                                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: band.color }} />
                                    <span className="text-[11px] text-slate-600 flex-1">{band.name}</span>
                                    <span className="text-[11px] font-bold text-slate-800">{band.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Processing Time Breakdown */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                    <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                        <Zap className="w-4 h-4 text-slate-400" />
                        Avg Processing Time by Stage (seconds)
                    </h3>
                    <ResponsiveContainer width="100%" height={240}>
                        <BarChart data={processingTimeData} layout="vertical">
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis type="number" tick={{ fontSize: 10, fill: "#94a3b8" }} />
                            <YAxis dataKey="stage" type="category" tick={{ fontSize: 10, fill: "#94a3b8" }} width={90} />
                            <Tooltip contentStyle={{ borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px" }} />
                            <Bar dataKey="avg" fill="#14b8a6" radius={[0, 4, 4, 0]} barSize={14} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* Sector Performance */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                    <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                        <Users className="w-4 h-4 text-slate-400" />
                        Sector Performance
                    </h3>
                    <div className="space-y-3">
                        {sectorData.map((sector) => (
                            <div key={sector.sector} className="flex items-center gap-4">
                                <span className="text-xs font-bold text-slate-600 w-16 shrink-0">{sector.sector}</span>
                                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                                    <div
                                        className={cn(
                                            "h-full rounded-full",
                                            sector.avgScore >= 700 ? "bg-emerald-400" :
                                            sector.avgScore >= 600 ? "bg-teal-400" :
                                            "bg-amber-400"
                                        )}
                                        style={{ width: `${(sector.avgScore / 850) * 100}%` }}
                                    />
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                    <span className="text-xs font-bold text-slate-800 w-8 text-right">{sector.avgScore}</span>
                                    <span className="text-[10px] text-slate-400 w-12 text-right">{sector.count} apps</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Recent Flags */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
                <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    Recent Critical Flags
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {[
                        { company: "ABC Textiles", flag: "Wilful Defaulter detected on RBI list", severity: "CRITICAL", date: "2 hours ago" },
                        { company: "PQR Pharma", flag: "GSTR-2A vs 3B mismatch ₹2.4cr", severity: "HIGH", date: "5 hours ago" },
                        { company: "LMN Auto", flag: "Director linked to NCLT proceedings", severity: "CRITICAL", date: "1 day ago" },
                    ].map((flag, i) => (
                        <div key={i} className={cn(
                            "rounded-lg border p-4",
                            flag.severity === "CRITICAL" ? "border-red-100 bg-red-50/50" : "border-amber-100 bg-amber-50/50"
                        )}>
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-xs font-bold text-slate-800">{flag.company}</span>
                                <span className={cn(
                                    "text-[9px] font-black uppercase px-1.5 py-0.5 rounded",
                                    flag.severity === "CRITICAL" ? "bg-red-100 text-red-600" : "bg-amber-100 text-amber-600"
                                )}>
                                    {flag.severity}
                                </span>
                            </div>
                            <p className="text-[11px] text-slate-600">{flag.flag}</p>
                            <p className="text-[10px] text-slate-400 mt-1">{flag.date}</p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

/* ─── KPI Card ───────────────────────────────────────────────── */
function StatKPI({ icon: Icon, label, value, trend, trendUp }: {
    icon: React.ElementType; label: string; value: string; trend: string; trendUp: boolean;
}) {
    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5">
            <div className="flex items-center gap-2 mb-2">
                <Icon className="w-4 h-4 text-slate-400" />
                <span className="text-[11px] font-black text-slate-400 uppercase tracking-wider">{label}</span>
            </div>
            <p className="text-2xl font-black text-slate-900">{value}</p>
            <p className={cn("text-[11px] font-bold mt-1 flex items-center gap-1", trendUp ? "text-emerald-600" : "text-red-500")}>
                <TrendingUp className={cn("w-3 h-3", !trendUp && "rotate-180")} />
                {trend}
            </p>
        </div>
    );
}
