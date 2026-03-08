"use client";

import { useState } from "react";
import {
    Flower2,
    ExternalLink,
    RefreshCw,
    Maximize2,
    Minimize2,
    AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface FlowerEmbedProps {
    flowerUrl?: string;
}

export function FlowerEmbed({ flowerUrl = "http://localhost:5555" }: FlowerEmbedProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [loadError, setLoadError] = useState(false);
    const [refreshKey, setRefreshKey] = useState(0);

    return (
        <div className={cn(
            "bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden transition-all",
            isExpanded ? "fixed inset-4 z-50 shadow-2xl" : ""
        )}>
            {/* Header */}
            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Flower2 className="w-4 h-4 text-teal-500" />
                    <h2 className="text-sm font-bold text-slate-800">Celery Worker Monitor</h2>
                    <span className="text-[10px] font-bold text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full">
                        Flower
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => { setRefreshKey((k) => k + 1); setLoadError(false); }}
                        className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                        title="Refresh"
                    >
                        <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
                    </button>
                    <a
                        href={flowerUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                        title="Open in new tab"
                    >
                        <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                    </a>
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
                        title={isExpanded ? "Minimize" : "Maximize"}
                    >
                        {isExpanded ? (
                            <Minimize2 className="w-3.5 h-3.5 text-slate-400" />
                        ) : (
                            <Maximize2 className="w-3.5 h-3.5 text-slate-400" />
                        )}
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className={cn("relative", isExpanded ? "h-[calc(100%-52px)]" : "h-[320px]")}>
                {loadError ? (
                    <div className="flex flex-col items-center justify-center h-full text-center p-6">
                        <AlertCircle className="w-10 h-10 text-slate-200 mb-3" />
                        <h3 className="text-sm font-bold text-slate-500 mb-1">Flower Not Available</h3>
                        <p className="text-xs text-slate-400 mb-4 max-w-xs">
                            Celery Flower monitor is not running. Start it with:
                        </p>
                        <code className="text-[11px] bg-slate-800 text-emerald-400 px-4 py-2 rounded-lg font-mono">
                            celery -A workers.celery_app flower --port=5555
                        </code>
                        <div className="mt-6 grid grid-cols-3 gap-4 w-full max-w-md">
                            {[
                                { label: "Active Workers", value: "8", status: "demo" },
                                { label: "Tasks Completed", value: "247", status: "demo" },
                                { label: "Tasks Failed", value: "2", status: "demo" },
                            ].map((stat) => (
                                <div key={stat.label} className="bg-slate-50 rounded-lg p-3 text-center">
                                    <p className="text-lg font-black text-slate-300">{stat.value}</p>
                                    <p className="text-[9px] font-bold text-slate-400 uppercase">{stat.label}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    <iframe
                        key={refreshKey}
                        src={flowerUrl}
                        className="w-full h-full border-0"
                        title="Flower - Celery Monitor"
                        sandbox="allow-same-origin allow-scripts allow-forms"
                        onError={() => setLoadError(true)}
                        onLoad={(e) => {
                            // Detect if iframe failed to load actual content
                            try {
                                const iframe = e.target as HTMLIFrameElement;
                                if (!iframe.contentDocument?.title) {
                                    setLoadError(true);
                                }
                            } catch {
                                // Cross-origin — Flower is actually loaded
                            }
                        }}
                    />
                )}
            </div>
        </div>
    );
}
