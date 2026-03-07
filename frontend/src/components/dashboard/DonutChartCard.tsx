"use client";

import React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { cn } from "@/lib/utils";

interface DataPoint {
    name: string;
    value: number;
    color: string;
}

interface DonutChartCardProps {
    title: string;
    data: DataPoint[];
    secondaryData?: DataPoint[];
    className?: string;
    onMore?: () => void;
}

const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-[#4b5563] text-white px-3 py-1.5 rounded-lg text-[10px] font-bold shadow-xl border-none">
                {`${payload[0].name}: ${payload[0].value}`}
            </div>
        );
    }
    return null;
};

export function DonutChartCard({ title, data, secondaryData, className, onMore }: DonutChartCardProps) {
    const [activeState, setActiveState] = React.useState<{ index: number; ring: "inner" | "outer" } | null>(null);

    return (
        <div className={cn("sl-card p-6 bg-white flex flex-col h-[320px]", className)}>
            <div className="flex items-center justify-between mb-6">
                <h4 className="text-slate-900 font-bold text-sm tracking-tight">{title}</h4>
                <button
                    onClick={onMore}
                    className="text-[10px] text-teal-500 font-black uppercase tracking-widest hover:underline"
                >
                    More
                </button>
            </div>

            <div className="flex-1 flex gap-4 items-center min-h-0">
                <div className="w-[150px] h-[150px] relative shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={data}
                                cx="50%"
                                cy="50%"
                                innerRadius={38}
                                outerRadius={activeState?.ring === "inner" ? 50 : 46}
                                paddingAngle={2}
                                dataKey="value"
                                stroke="none"
                                onMouseEnter={(_, index) => setActiveState({ index, ring: "inner" })}
                                onMouseLeave={() => setActiveState(null)}
                                animationBegin={0}
                                animationDuration={800}
                            >
                                {data.map((entry, index) => (
                                    <Cell
                                        key={`cell-inner-${index}`}
                                        fill={entry.color}
                                        style={{
                                            filter: (activeState?.ring === "inner" && activeState?.index === index) ? 'brightness(1.1)' : 'none',
                                            cursor: 'pointer',
                                            transition: 'all 0.3s ease',
                                            scale: (activeState?.ring === "inner" && activeState?.index === index) ? 1.05 : 1,
                                            transformOrigin: '50% 50%'
                                        }}
                                    />
                                ))}
                            </Pie>
                            {secondaryData && (
                                <Pie
                                    data={secondaryData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={56}
                                    outerRadius={activeState?.ring === "outer" ? 68 : 64}
                                    paddingAngle={2}
                                    dataKey="value"
                                    stroke="none"
                                    onMouseEnter={(_, index) => setActiveState({ index, ring: "outer" })}
                                    onMouseLeave={() => setActiveState(null)}
                                >
                                    {secondaryData.map((entry, index) => (
                                        <Cell
                                            key={`cell-outer-${index}`}
                                            fill={entry.color}
                                            opacity={0.6}
                                            style={{
                                                filter: (activeState?.ring === "outer" && activeState?.index === index) ? 'brightness(1.1)' : 'none',
                                                cursor: 'pointer',
                                                transition: 'all 0.3s ease',
                                                scale: (activeState?.ring === "outer" && activeState?.index === index) ? 1.05 : 1,
                                                transformOrigin: '50% 50%'
                                            }}
                                        />
                                    ))}
                                </Pie>
                            )}
                            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'transparent' }} />
                        </PieChart>
                    </ResponsiveContainer>
                </div>

                {/* Legend Area with Background */}
                <div className="flex-1 bg-slate-50 rounded-2xl p-6 h-[240px] flex items-center shadow-inner shadow-slate-100/50">
                    <div className={cn(
                        "grid gap-y-6 w-full",
                        secondaryData ? "grid-cols-2 gap-x-12" : "grid-cols-1"
                    )}>
                        {/* Primary Data List */}
                        <div className="space-y-4">
                            {data.map((item, idx) => (
                                <div
                                    key={idx}
                                    className={cn(
                                        "flex items-center justify-between group cursor-pointer transition-all duration-300",
                                        (activeState?.ring === "inner" && activeState?.index === idx) ? "scale-105" : "opacity-100"
                                    )}
                                    onMouseEnter={() => setActiveState({ index: idx, ring: "inner" })}
                                    onMouseLeave={() => setActiveState(null)}
                                >
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: item.color }} />
                                        <span className={cn(
                                            "text-[11px] font-medium transition-colors whitespace-nowrap",
                                            (activeState?.ring === "inner" && activeState?.index === idx) ? "text-teal-600 font-bold" : "text-slate-500 group-hover:text-slate-700"
                                        )}>
                                            {item.name}
                                        </span>
                                    </div>
                                    <span className={cn(
                                        "text-[12px] font-black transition-colors min-w-[24px] text-right ml-4",
                                        (activeState?.ring === "inner" && activeState?.index === idx) ? "text-teal-600" : "text-slate-900"
                                    )}>
                                        {item.value}
                                    </span>
                                </div>
                            ))}
                        </div>

                        {/* Secondary Data List */}
                        <div className="space-y-4">
                            {secondaryData?.map((item, idx) => (
                                <div
                                    key={`sec-${idx}`}
                                    className={cn(
                                        "flex items-center justify-between group cursor-pointer transition-all duration-300",
                                        (activeState?.ring === "outer" && activeState?.index === idx) ? "scale-105" : "opacity-100"
                                    )}
                                    onMouseEnter={() => setActiveState({ index: idx, ring: "outer" })}
                                    onMouseLeave={() => setActiveState(null)}
                                >
                                    <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: item.color }} />
                                        <span className={cn(
                                            "text-[11px] font-medium transition-colors whitespace-nowrap",
                                            (activeState?.ring === "outer" && activeState?.index === idx) ? "text-teal-600 font-bold" : "text-slate-500 group-hover:text-slate-700"
                                        )}>
                                            {item.name}
                                        </span>
                                    </div>
                                    <span className={cn(
                                        "text-[12px] font-black transition-colors min-w-[24px] text-right ml-4",
                                        (activeState?.ring === "outer" && activeState?.index === idx) ? "text-teal-600" : "text-slate-900"
                                    )}>
                                        {item.value}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
