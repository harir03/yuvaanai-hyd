"use client";

import { useState } from "react";
import {
    AlertTriangle,
    CheckCircle2,
    Clock,
    MessageSquare,
    ChevronRight,
    ExternalLink,
    FileText,
    Send,
    XCircle,
    Shield,
    User,
    Bot,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mockTickets, getSeverityColor, type Ticket } from "@/lib/mockData";

export default function TicketsPage() {
    const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(mockTickets[0]);
    const [resolutionInput, setResolutionInput] = useState("");
    const [resolvedTickets, setResolvedTickets] = useState<Set<string>>(new Set());

    const handleResolve = (ticketId: string) => {
        if (!resolutionInput.trim()) return;
        setResolvedTickets((prev) => new Set([...prev, ticketId]));
        setResolutionInput("");
        alert(`Ticket ${ticketId} resolved!\n\nIn production, this POSTs to the API, updates the ticket in PostgreSQL, and stores the resolution precedent in ChromaDB for future reference.`);
    };

    return (
        <div className="p-6 space-y-6 max-w-[1600px] mx-auto min-h-screen">
            {/* Page Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-amber-500/10 rounded-xl">
                        <AlertTriangle className="w-6 h-6 text-amber-600" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-slate-800">Ticket Resolution</h1>
                        <p className="text-sm text-slate-500">AI-flagged conflicts requiring human judgement</p>
                    </div>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-red-400" />
                        <span className="text-[11px] font-bold text-slate-500">
                            {mockTickets.filter((t) => t.severity === "CRITICAL").length} Critical
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-amber-400" />
                        <span className="text-[11px] font-bold text-slate-500">
                            {mockTickets.filter((t) => t.severity === "HIGH").length} High
                        </span>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-blue-400" />
                        <span className="text-[11px] font-bold text-slate-500">
                            {mockTickets.filter((t) => t.severity === "LOW").length} Low
                        </span>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Ticket Queue */}
                <div className="lg:col-span-4">
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
                        <div className="px-5 py-3 border-b border-slate-100">
                            <h2 className="text-sm font-bold text-slate-800">
                                Open Tickets ({mockTickets.length})
                            </h2>
                        </div>
                        <div className="divide-y divide-slate-50">
                            {mockTickets.map((ticket) => {
                                const isResolved = resolvedTickets.has(ticket.id);
                                return (
                                    <button
                                        key={ticket.id}
                                        onClick={() => setSelectedTicket(ticket)}
                                        className={cn(
                                            "w-full text-left px-5 py-4 hover:bg-slate-50 transition-colors",
                                            selectedTicket?.id === ticket.id && "bg-teal-50/50 border-r-2 border-teal-500"
                                        )}
                                    >
                                        <div className="flex items-start justify-between gap-2 mb-1.5">
                                            <span className="text-xs font-bold text-slate-800 leading-snug">
                                                {ticket.title}
                                            </span>
                                            <span className={cn(
                                                "text-[9px] font-black uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0",
                                                getSeverityColor(ticket.severity)
                                            )}>
                                                {ticket.severity}
                                            </span>
                                        </div>
                                        <p className="text-[11px] text-slate-400 line-clamp-2 mb-2">{ticket.description}</p>
                                        <div className="flex items-center gap-3">
                                            <span className="text-[10px] text-slate-400 flex items-center gap-1">
                                                <FileText className="w-2.5 h-2.5" /> {ticket.source_agent}
                                            </span>
                                            {isResolved && (
                                                <span className="text-[10px] text-emerald-600 font-bold flex items-center gap-1">
                                                    <CheckCircle2 className="w-2.5 h-2.5" /> Resolved
                                                </span>
                                            )}
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </div>

                {/* Ticket Detail */}
                <div className="lg:col-span-8">
                    {selectedTicket ? (
                        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
                            {/* Ticket Header */}
                            <div className="px-6 py-4 border-b border-slate-100">
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <h3 className="text-base font-bold text-slate-900">{selectedTicket.title}</h3>
                                        <p className="text-sm text-slate-500 mt-0.5">{selectedTicket.description}</p>
                                    </div>
                                    <span className={cn(
                                        "text-[10px] font-black uppercase tracking-wider px-2 py-1 rounded",
                                        getSeverityColor(selectedTicket.severity)
                                    )}>
                                        {selectedTicket.severity}
                                    </span>
                                </div>
                                <div className="flex items-center gap-4 mt-3 text-[11px] text-slate-400">
                                    <span className="flex items-center gap-1"><Bot className="w-3 h-3" /> {selectedTicket.source_agent}</span>
                                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {selectedTicket.created_at}</span>
                                    <span className="flex items-center gap-1"><FileText className="w-3 h-3" /> {selectedTicket.affected_documents.join(", ")}</span>
                                </div>
                            </div>

                            {/* AI Evidence */}
                            <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                                <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-3">AI Evidence & Analysis</h4>
                                <div className="space-y-3">
                                    {selectedTicket.ai_evidence.map((evidence, i) => (
                                        <div key={i} className="bg-white rounded-lg border border-slate-100 p-4">
                                            <div className="flex items-center gap-2 mb-2">
                                                <Bot className="w-4 h-4 text-teal-500" />
                                                <span className="text-xs font-bold text-slate-700">{evidence.source}</span>
                                                <span className="text-[10px] text-slate-400">— {evidence.finding_type}</span>
                                            </div>
                                            <p className="text-sm text-slate-600 leading-relaxed">{evidence.detail}</p>
                                            {evidence.excerpt && (
                                                <div className="mt-2 pl-3 border-l-2 border-teal-200 bg-teal-50/50 rounded-r-md px-3 py-2">
                                                    <p className="text-[11px] text-teal-800 italic">&ldquo;{evidence.excerpt}&rdquo;</p>
                                                    <p className="text-[10px] text-teal-500 mt-1">{evidence.page_ref}</p>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* AI Recommendation */}
                            <div className="px-6 py-4 border-b border-slate-100">
                                <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-2">AI Recommendation</h4>
                                <div className="flex items-start gap-3 bg-indigo-50/50 rounded-lg p-4">
                                    <Shield className="w-5 h-5 text-indigo-500 shrink-0 mt-0.5" />
                                    <p className="text-sm text-indigo-900 leading-relaxed">{selectedTicket.ai_recommendation}</p>
                                </div>
                            </div>

                            {/* Human Resolution */}
                            <div className="px-6 py-4">
                                <h4 className="text-xs font-black text-slate-500 uppercase tracking-wider mb-3">Officer Resolution</h4>
                                {resolvedTickets.has(selectedTicket.id) ? (
                                    <div className="flex items-center gap-2 bg-emerald-50 rounded-lg p-4">
                                        <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                                        <span className="text-sm font-medium text-emerald-800">Ticket resolved — precedent stored for future reference</span>
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        <textarea
                                            rows={3}
                                            value={resolutionInput}
                                            onChange={(e) => setResolutionInput(e.target.value)}
                                            placeholder="Enter your decision and reasoning for resolution..."
                                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all placeholder:text-slate-400 resize-none"
                                        />
                                        <div className="flex items-center gap-3">
                                            <button
                                                onClick={() => handleResolve(selectedTicket.id)}
                                                disabled={!resolutionInput.trim()}
                                                className={cn(
                                                    "flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold transition-all",
                                                    resolutionInput.trim()
                                                        ? "bg-teal-500 text-white hover:bg-teal-600 shadow-lg shadow-teal-500/20"
                                                        : "bg-slate-100 text-slate-400 cursor-not-allowed"
                                                )}
                                            >
                                                <CheckCircle2 className="w-4 h-4" /> Accept & Resolve
                                            </button>
                                            <button className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold text-red-500 bg-red-50 hover:bg-red-100 transition-colors">
                                                <XCircle className="w-4 h-4" /> Override & Reject
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-12 flex flex-col items-center justify-center text-center">
                            <MessageSquare className="w-10 h-10 text-slate-200 mb-3" />
                            <h3 className="text-sm font-bold text-slate-400">Select a ticket</h3>
                            <p className="text-xs text-slate-300 mt-1">Choose a ticket from the queue to review</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
