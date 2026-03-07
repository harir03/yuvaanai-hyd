"use client";

import { useState } from "react";
import {
    Archive,
    Search,
    Filter,
    ChevronDown,
    ArrowUpDown,
    ExternalLink,
    Calendar,
    Building2,
    Target,
    FileText,
    Clock,
    CheckCircle2,
    XCircle,
    AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mockHistory, getScoreBandColor, getScoreBandBg, type HistoryRecord } from "@/lib/mockData";

export default function HistoryPage() {
    const [searchQuery, setSearchQuery] = useState("");
    const [bandFilter, setBandFilter] = useState("all");
    const [statusFilter, setStatusFilter] = useState("all");
    const [selectedRecord, setSelectedRecord] = useState<HistoryRecord | null>(null);

    const filtered = mockHistory.filter((r) => {
        if (searchQuery && !r.companyName.toLowerCase().includes(searchQuery.toLowerCase())) return false;
        if (bandFilter !== "all" && r.scoreBand !== bandFilter) return false;
        if (statusFilter !== "all" && r.status !== statusFilter) return false;
        return true;
    });

    const statusIcon = (status: string) => {
        switch (status) {
            case "approved": return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />;
            case "rejected": return <XCircle className="w-3.5 h-3.5 text-red-500" />;
            case "reviewing": return <Clock className="w-3.5 h-3.5 text-amber-500" />;
            case "processing": return <Clock className="w-3.5 h-3.5 text-teal-500 animate-spin" />;
            default: return <AlertTriangle className="w-3.5 h-3.5 text-slate-400" />;
        }
    };

    return (
        <div className="p-6 space-y-6 max-w-[1600px] mx-auto min-h-screen">
            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-slate-500/10 rounded-xl">
                        <Archive className="w-6 h-6 text-slate-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-800">Decision Store</h1>
                        <p className="text-sm text-slate-500">Historical assessments and precedent library</p>
                    </div>
                </div>
                <span className="text-xs font-bold text-slate-400 bg-slate-50 px-3 py-1.5 rounded-lg">
                    {mockHistory.length} assessments
                </span>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-3 flex-wrap">
                <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-300" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search by company name..."
                        className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all placeholder:text-slate-400"
                    />
                </div>
                <select
                    value={bandFilter}
                    onChange={(e) => setBandFilter(e.target.value)}
                    className="px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                >
                    <option value="all">All Bands</option>
                    <option value="Excellent">Excellent</option>
                    <option value="Good">Good</option>
                    <option value="Fair">Fair</option>
                    <option value="Poor">Poor</option>
                    <option value="Very Poor">Very Poor</option>
                </select>
                <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-600 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
                >
                    <option value="all">All Status</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                    <option value="reviewing">Reviewing</option>
                    <option value="processing">Processing</option>
                </select>
            </div>

            {/* Table */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-slate-100">
                                <th className="text-left px-5 py-3 text-[11px] font-black text-slate-400 uppercase tracking-wider">Company</th>
                                <th className="text-left px-5 py-3 text-[11px] font-black text-slate-400 uppercase tracking-wider">Loan</th>
                                <th className="text-center px-5 py-3 text-[11px] font-black text-slate-400 uppercase tracking-wider">Score</th>
                                <th className="text-center px-5 py-3 text-[11px] font-black text-slate-400 uppercase tracking-wider">Band</th>
                                <th className="text-center px-5 py-3 text-[11px] font-black text-slate-400 uppercase tracking-wider">Status</th>
                                <th className="text-left px-5 py-3 text-[11px] font-black text-slate-400 uppercase tracking-wider">Date</th>
                                <th className="text-left px-5 py-3 text-[11px] font-black text-slate-400 uppercase tracking-wider">Officer</th>
                                <th className="px-5 py-3"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {filtered.map((record) => (
                                <tr
                                    key={record.sessionId}
                                    className="hover:bg-slate-50/50 transition-colors cursor-pointer"
                                    onClick={() => setSelectedRecord(record)}
                                >
                                    <td className="px-5 py-3.5">
                                        <div className="flex items-center gap-2">
                                            <Building2 className="w-4 h-4 text-slate-300 shrink-0" />
                                            <div>
                                                <p className="text-xs font-bold text-slate-700">{record.companyName}</p>
                                                <p className="text-[10px] text-slate-400">{record.sector}</p>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <p className="text-xs font-medium text-slate-700">{record.loanAmount}</p>
                                        <p className="text-[10px] text-slate-400">{record.loanType}</p>
                                    </td>
                                    <td className="px-5 py-3.5 text-center">
                                        <span className="text-sm font-black text-slate-800">{record.score}</span>
                                        <span className="text-[10px] text-slate-400">/850</span>
                                    </td>
                                    <td className="px-5 py-3.5 text-center">
                                        <span className={cn("text-[10px] font-black px-2 py-1 rounded-full", getScoreBandBg(record.scoreBand), getScoreBandColor(record.scoreBand))}>
                                            {record.scoreBand}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <div className="flex items-center justify-center gap-1.5">
                                            {statusIcon(record.status)}
                                            <span className="text-[11px] font-bold capitalize text-slate-600">{record.status}</span>
                                        </div>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <span className="text-xs text-slate-500">{record.date}</span>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <span className="text-xs text-slate-500">{record.officer}</span>
                                    </td>
                                    <td className="px-5 py-3.5">
                                        <ExternalLink className="w-3.5 h-3.5 text-slate-300 hover:text-teal-500 transition-colors" />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {filtered.length === 0 && (
                    <div className="py-12 text-center">
                        <Search className="w-8 h-8 text-slate-200 mx-auto mb-2" />
                        <p className="text-sm text-slate-400">No matching assessments found</p>
                    </div>
                )}
            </div>

            {/* Detail Modal */}
            {selectedRecord && (
                <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={() => setSelectedRecord(null)}>
                    <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-start justify-between mb-4">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900">{selectedRecord.companyName}</h3>
                                <p className="text-sm text-slate-500">{selectedRecord.sector} — {selectedRecord.loanType}</p>
                            </div>
                            <button onClick={() => setSelectedRecord(null)} className="p-1 rounded-full hover:bg-slate-100">
                                <XCircle className="w-5 h-5 text-slate-400" />
                            </button>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-slate-50 rounded-lg p-3">
                                <p className="text-[10px] font-black text-slate-400 uppercase mb-1">Score</p>
                                <p className="text-2xl font-black text-slate-800">{selectedRecord.score}<span className="text-sm text-slate-400">/850</span></p>
                                <span className={cn("text-[10px] font-black px-2 py-0.5 rounded-full", getScoreBandBg(selectedRecord.scoreBand), getScoreBandColor(selectedRecord.scoreBand))}>
                                    {selectedRecord.scoreBand}
                                </span>
                            </div>
                            <div className="bg-slate-50 rounded-lg p-3">
                                <p className="text-[10px] font-black text-slate-400 uppercase mb-1">Loan</p>
                                <p className="text-lg font-bold text-slate-800">{selectedRecord.loanAmount}</p>
                                <p className="text-xs text-slate-500">{selectedRecord.loanType}</p>
                            </div>
                            <div className="bg-slate-50 rounded-lg p-3">
                                <p className="text-[10px] font-black text-slate-400 uppercase mb-1">Status</p>
                                <div className="flex items-center gap-1.5">
                                    {statusIcon(selectedRecord.status)}
                                    <span className="text-sm font-bold capitalize text-slate-700">{selectedRecord.status}</span>
                                </div>
                            </div>
                            <div className="bg-slate-50 rounded-lg p-3">
                                <p className="text-[10px] font-black text-slate-400 uppercase mb-1">Assessed</p>
                                <p className="text-sm font-bold text-slate-700">{selectedRecord.date}</p>
                                <p className="text-xs text-slate-500">by {selectedRecord.officer}</p>
                            </div>
                        </div>
                        <button
                            onClick={() => setSelectedRecord(null)}
                            className="w-full mt-4 py-2.5 bg-teal-500 text-white rounded-lg text-xs font-bold hover:bg-teal-600 transition-colors"
                        >
                            View Full Report →
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
