"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface RankingItem {
    label: string;
    value: string | number;
    percent: number;
    color?: string;
}

interface ProgressBarCardProps {
    title: string;
    data: RankingItem[];
    className?: string;
    onMore?: () => void;
}

export function ProgressBarCard({ title, data, className, onMore }: ProgressBarCardProps) {
    const [hoverIndex, setHoverIndex] = React.useState<number | null>(null);
    const [mounted, setMounted] = React.useState(false);

    React.useEffect(() => {
        const timer = setTimeout(() => setMounted(true), 100);
        return () => clearTimeout(timer);
    }, []);

    return (
        <div className={cn("sl-card p-6 bg-white flex flex-col h-[320px]", className)}>
            <div className="flex items-center justify-between mb-6">
                <h4 className="text-slate-800 font-bold text-sm uppercase tracking-tight">{title}</h4>
                <button
                    onClick={onMore}
                    className="text-[10px] text-teal-500 font-black uppercase tracking-widest hover:underline"
                >
                    More
                </button>
            </div>

            <div className="space-y-4 flex-1 overflow-hidden">
                {data.map((item, idx) => (
                    <div
                        key={idx}
                        className={cn(
                            "space-y-2 group cursor-pointer transition-all duration-300",
                            hoverIndex !== null && hoverIndex !== idx ? "opacity-40 grayscale" : "opacity-100"
                        )}
                        onMouseEnter={() => setHoverIndex(idx)}
                        onMouseLeave={() => setHoverIndex(null)}
                    >
                        <div className="flex justify-between items-center text-[10px] font-black">
                            <span className={cn(
                                "uppercase tracking-tighter truncate max-w-[80%] block transition-colors",
                                hoverIndex === idx ? "text-slate-900" : "text-slate-400"
                            )}>
                                {item.label || "-"}
                            </span>
                            <span className={cn(
                                "transition-colors",
                                hoverIndex === idx ? "text-teal-600" : "text-slate-900"
                            )}>
                                {item.value}
                            </span>
                        </div>
                        <div className="h-[3px] w-full bg-slate-50 rounded-full overflow-hidden">
                            <div
                                className={cn(
                                    "h-full rounded-full transition-all duration-1000 ease-out",
                                    item.color || "bg-teal-400 shadow-[0_0_8px_rgba(45,212,191,0.4)]",
                                    hoverIndex === idx && "brightness-110"
                                )}
                                style={{ width: mounted ? `${item.percent}%` : "0%" }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
