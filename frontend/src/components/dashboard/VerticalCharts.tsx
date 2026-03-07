"use client";

import React from "react";

import {
    BarChart, Bar, ResponsiveContainer,
    LineChart, Line, XAxis, YAxis, Tooltip, AreaChart, Area
} from "recharts";
import { History, LayoutGrid, RotateCcw } from "lucide-react";

const qpsData = Array.from({ length: 24 }, (_, i) => ({ value: Math.floor(Math.random() * 50) + 20 }));
const statusData = Array.from({ length: 24 }, () => ({
    time: "",
    value: 0
}));

const blockData = Array.from({ length: 24 }, () => ({
    time: "",
    value: 0
}));

const CustomTooltip = ({ active, payload, label, color = "#2dd4bf", title = "Value" }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-white p-4 border border-slate-50 rounded-xl shadow-[0_8px_30px_rgb(0,0,0,0.06)] min-w-[140px]">
                <p className="text-[12px] text-slate-400 font-medium mb-2">{label || "01:48:25"}</p>
                <div className="flex items-center gap-2">
                    <div className="w-[10px] h-[10px] rounded-full" style={{ backgroundColor: color }} />
                    <span className="text-[14px] font-medium text-slate-500">{title}</span>
                    <span className="text-[14px] font-medium text-slate-700 ml-auto pl-4">{payload[0].value}</span>
                </div>
            </div>
        );
    }
    return null;
};

export function VerticalCharts() {
    return null;
}

// Re-implementing QPSChart to internalize fetching or accept props.
// To avoid breaking changes, I'll make them self-fetching or accept props if passed. Needs a bit of logic.
// Simplest approach: Modify each chart component in this file to fetch its own data (or share a swr/context, but sticking to simple fetch).

export function QPSChart() {
    const chartData = qpsData;

    return (
        <div className="sl-card p-6 bg-white flex flex-col h-[260px] relative overflow-hidden">
            {/* ... header ... */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                    <h4 className="text-slate-900 font-bold text-base">Query Per Second</h4>
                    <div className="flex items-center px-2 py-1 bg-slate-50 border border-slate-100 rounded-md gap-2">
                        <span className="text-[11px] font-black text-slate-900">{chartData.length > 0 ? chartData[chartData.length - 1].value : 0}</span>
                    </div>
                </div>
                <div className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-slate-50 transition-colors cursor-pointer group">
                    <History className="w-5 h-5 text-teal-500 group-hover:rotate-[-45deg] transition-transform" />
                </div>
            </div>

            <div className="flex-1 w-full relative outline-none flex flex-col min-w-0">
                <div className="flex-1 min-h-0">
                    <ResponsiveContainer width="99%" height="100%" minWidth={0}>
                        <BarChart data={chartData}>
                            <XAxis dataKey="name" hide />
                            <Bar dataKey="value" fill="#2dd4bf" radius={[1, 1, 0, 0]} barSize={4} />
                            <Tooltip cursor={{ fill: 'rgba(241, 245, 249, 0.6)' }} content={<CustomTooltip color="#2dd4bf" title="QPS" />} wrapperStyle={{ outline: "none" }} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
                <div className="w-full flex gap-[3px] mt-2 overflow-hidden px-1">
                    {Array.from({ length: 50 }).map((_, i) => (
                        <div key={i} className="w-2 h-[3px] bg-teal-500 rounded-full shrink-0" />
                    ))}
                </div>
            </div>
        </div>
    );
}

export function RequestsStatusChart() {
    const chartData = statusData;

    return (
        <div className="sl-card p-4 bg-white flex flex-col h-[232px]">
            <div className="flex items-center justify-between mb-6">
                <h4 className="text-slate-800 font-black text-[12px] uppercase tracking-tight">Requests Status</h4>
            </div>
            <div className="flex-1 w-full outline-none min-w-0">
                <ResponsiveContainer width="99%" height="100%" minWidth={0}>
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorStatus" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.1} />
                                <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <XAxis dataKey="time" hide />
                        <Tooltip content={<CustomTooltip color="#14b8a6" title="Requests Status" />} wrapperStyle={{ outline: "none" }} />
                        <Area type="monotone" dataKey="value" stroke="#14b8a6" strokeWidth={2.5} fillOpacity={1} fill="url(#colorStatus)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}

export function BlockingStatusChart() {
    const chartData = blockData;

    return (
        <div className="sl-card p-4 bg-white flex flex-col h-[232px]">
            <div className="flex items-center justify-between mb-6">
                <h4 className="text-slate-800 font-black text-[12px] uppercase tracking-tight">Blocking Status</h4>
            </div>
            <div className="flex-1 w-full outline-none min-w-0">
                <ResponsiveContainer width="99%" height="100%" minWidth={0}>
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorBlock" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.1} />
                                <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <XAxis dataKey="time" hide />
                        <Tooltip content={<CustomTooltip color="#f43f5e" title="Blocking Status" />} wrapperStyle={{ outline: "none" }} />
                        <Area type="monotone" dataKey="value" stroke="#f43f5e" strokeWidth={2.5} fillOpacity={1} fill="url(#colorBlock)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
