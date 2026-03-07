"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Info, HelpCircle } from "lucide-react";

interface StatCardProps {
    label: string;
    value: string | number;
    subValue?: string;
    icon?: any;
    iconLabel?: string;
    variant?: "teal" | "orange" | "red" | "gray";
}

const TOOLTIP_TEXTS: Record<string, string> = {
    "Requests": "Total number of HTTP requests processed by MAF in the selected period.",
    "Views (PV)": "Page Views: Total number of page hits recorded.",
    "Visitors(UV)": "Unique Visitors: Number of distinct clients identified by cookie/IP.",
    "Unique IP": "Total number of unique source IP addresses observed.",
    "Blocked": "Number of malicious requests successfully blocked by security rules.",
    "IP Addr": "Current count of active source IP addresses.",
    "4xx Errors": "Count of client-side errors (e.g., 404, 403) observed.",
    "Error Rate": "Percentage of requests resulting in status codes 4xx or 5xx.",
    "4xx Blocked": "Total number of 4xx responses triggered by MAF blocking actions.",
    "Blocked Rate": "Percentage of total traffic currently being blocked.",
    "5xx Errors": "Count of server-side errors (e.g., 500, 502) recorded.",
};

export function StatCard({ label, value, subValue, icon: Icon, iconLabel, variant = "teal" }: StatCardProps) {
    const [showTooltip, setShowTooltip] = useState(false);

    return (
        <div className="sl-card p-3 flex flex-col gap-2 relative transition-all hover:shadow-md h-[112px] bg-white group">
            <div className="flex items-center justify-between">
                <div
                    className="flex items-center gap-1 min-w-0 relative"
                    onMouseEnter={() => setShowTooltip(true)}
                    onMouseLeave={() => setShowTooltip(false)}
                >
                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-tight whitespace-nowrap cursor-help transition-colors group-hover:text-slate-600">{label}</span>
                    <HelpCircle className="w-3 h-3 text-slate-200 flex-shrink-0 cursor-help" />

                    {/* Simple Tooltip */}
                    {showTooltip && (
                        <div className="absolute bottom-full left-0 mb-2 w-48 p-2 bg-slate-800 text-white text-[10px] font-bold rounded-lg shadow-xl z-[100] animate-in fade-in slide-in-from-bottom-1 border border-slate-700 pointer-events-none">
                            {TOOLTIP_TEXTS[label] || "Description for " + label}
                            <div className="absolute top-full left-4 border-8 border-transparent border-t-slate-800" />
                        </div>
                    )}
                </div>

                <div className={cn(
                    "w-6 h-6 rounded-md flex items-center justify-center transition-all group-hover:scale-110",
                    variant === "orange" ? "bg-orange-50" : variant === "red" ? "bg-red-50" : "bg-teal-50"
                )}>
                    {Icon ? (
                        <Icon className={cn(
                            "w-3.5 h-3.5",
                            variant === "orange" ? "text-orange-400" : variant === "red" ? "text-red-400" : "text-teal-400"
                        )} strokeWidth={3} />
                    ) : iconLabel ? (
                        <span className={cn(
                            "text-[8px] font-black leading-none",
                            variant === "orange" ? "text-orange-400" : "text-teal-400"
                        )}>{iconLabel}</span>
                    ) : null}
                </div>
            </div>

            <div className="flex items-baseline gap-1">
                <span className="text-2xl font-black text-slate-900 tracking-tight leading-none">{value}</span>
                {subValue && (
                    <span className="text-[11px] font-bold text-slate-400">{subValue}</span>
                )}
            </div>
        </div>
    );
}
