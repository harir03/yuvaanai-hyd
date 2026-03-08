"use client";

import { useState } from "react";
import {
    MapPin,
    Calendar,
    User,
    Camera,
    Clipboard,
    Factory,
    Package,
    Users,
    Star,
    CheckCircle2,
    Save,
    ChevronDown,
    ChevronUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mockSiteVisit, type SiteVisitData } from "@/lib/mockData";

interface SiteVisitFormProps {
    initialData?: SiteVisitData;
    readOnly?: boolean;
    onSubmit?: (data: SiteVisitData) => void;
}

const PLANT_CONDITIONS: SiteVisitData["plantCondition"][] = ["Excellent", "Good", "Fair", "Poor"];
const INVENTORY_LEVELS: SiteVisitData["inventoryLevel"][] = ["Adequate", "Excess", "Low", "Critical"];

export function SiteVisitForm({ initialData, readOnly = false, onSubmit }: SiteVisitFormProps) {
    const [data, setData] = useState<SiteVisitData>(initialData ?? mockSiteVisit);
    const [newObservation, setNewObservation] = useState("");
    const [submitted, setSubmitted] = useState(false);
    const [isExpanded, setIsExpanded] = useState(true);

    const update = <K extends keyof SiteVisitData>(key: K, value: SiteVisitData[K]) => {
        setData((prev) => ({ ...prev, [key]: value }));
    };

    const addObservation = () => {
        if (!newObservation.trim()) return;
        update("keyObservations", [...data.keyObservations, newObservation.trim()]);
        setNewObservation("");
    };

    const removeObservation = (index: number) => {
        update("keyObservations", data.keyObservations.filter((_, i) => i !== index));
    };

    const handleSubmit = () => {
        onSubmit?.(data);
        setSubmitted(true);
    };

    const conditionColor = (c: string) => {
        const m: Record<string, string> = { Excellent: "text-emerald-600 bg-emerald-50 border-emerald-200", Good: "text-teal-600 bg-teal-50 border-teal-200", Fair: "text-amber-600 bg-amber-50 border-amber-200", Poor: "text-red-600 bg-red-50 border-red-200" };
        return m[c] ?? "text-slate-600 bg-slate-50 border-slate-200";
    };

    const inventoryColor = (l: string) => {
        const m: Record<string, string> = { Adequate: "text-emerald-600 bg-emerald-50", Excess: "text-amber-600 bg-amber-50", Low: "text-orange-600 bg-orange-50", Critical: "text-red-600 bg-red-50" };
        return m[l] ?? "text-slate-600 bg-slate-50";
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
            {/* Header */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-500/10 rounded-lg">
                        <Factory className="w-5 h-5 text-emerald-600" />
                    </div>
                    <div className="text-left">
                        <h2 className="text-sm font-bold text-slate-800">Site Visit Report (W9)</h2>
                        <p className="text-[11px] text-slate-400">Factory / office inspection observations</p>
                    </div>
                </div>
                {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
            </button>

            {isExpanded && (
                <div className="px-6 pb-6 space-y-5">
                    {/* Visit Meta */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold text-slate-500 uppercase flex items-center gap-1">
                                <Calendar className="w-3 h-3" /> Visit Date
                            </label>
                            <input
                                type="date"
                                value={data.visitDate}
                                onChange={(e) => update("visitDate", e.target.value)}
                                disabled={readOnly}
                                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 disabled:opacity-60"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold text-slate-500 uppercase flex items-center gap-1">
                                <User className="w-3 h-3" /> Visited By
                            </label>
                            <input
                                type="text"
                                value={data.visitedBy}
                                onChange={(e) => update("visitedBy", e.target.value)}
                                disabled={readOnly}
                                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 disabled:opacity-60"
                            />
                        </div>
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold text-slate-500 uppercase flex items-center gap-1">
                                <MapPin className="w-3 h-3" /> Location
                            </label>
                            <input
                                type="text"
                                value={data.location}
                                onChange={(e) => update("location", e.target.value)}
                                disabled={readOnly}
                                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 disabled:opacity-60"
                            />
                        </div>
                    </div>

                    {/* Condition Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {/* Plant Condition */}
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold text-slate-500 uppercase">Plant Condition</label>
                            <div className="flex flex-wrap gap-1.5">
                                {PLANT_CONDITIONS.map((c) => (
                                    <button
                                        key={c}
                                        onClick={() => !readOnly && update("plantCondition", c)}
                                        className={cn(
                                            "text-[10px] font-bold px-2.5 py-1 rounded-full border transition-all",
                                            data.plantCondition === c ? conditionColor(c) : "text-slate-400 bg-white border-slate-200"
                                        )}
                                    >
                                        {c}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Capacity Utilization */}
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold text-slate-500 uppercase">Capacity Utilization</label>
                            <div className="flex items-center gap-2">
                                <input
                                    type="range"
                                    min={0}
                                    max={100}
                                    value={data.capacityUtilization}
                                    onChange={(e) => update("capacityUtilization", Number(e.target.value))}
                                    disabled={readOnly}
                                    className="flex-1 accent-teal-500"
                                />
                                <span className="text-sm font-black text-teal-600 w-10 text-right">{data.capacityUtilization}%</span>
                            </div>
                        </div>

                        {/* Inventory Level */}
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold text-slate-500 uppercase">Inventory Level</label>
                            <div className="flex flex-wrap gap-1.5">
                                {INVENTORY_LEVELS.map((l) => (
                                    <button
                                        key={l}
                                        onClick={() => !readOnly && update("inventoryLevel", l)}
                                        className={cn(
                                            "text-[10px] font-bold px-2.5 py-1 rounded-full transition-all",
                                            data.inventoryLevel === l ? inventoryColor(l) : "text-slate-400 bg-slate-50"
                                        )}
                                    >
                                        {l}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Staff Count */}
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold text-slate-500 uppercase flex items-center gap-1">
                                <Users className="w-3 h-3" /> Staff Count
                            </label>
                            <input
                                type="number"
                                value={data.staffCount}
                                onChange={(e) => update("staffCount", Number(e.target.value))}
                                disabled={readOnly}
                                min={0}
                                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 disabled:opacity-60"
                            />
                        </div>
                    </div>

                    {/* Key Observations */}
                    <div className="space-y-2">
                        <label className="text-[11px] font-bold text-slate-500 uppercase flex items-center gap-1">
                            <Clipboard className="w-3 h-3" /> Key Observations
                        </label>
                        <div className="space-y-1.5">
                            {data.keyObservations.map((obs, i) => (
                                <div key={i} className="flex items-start gap-2 bg-slate-50 rounded-lg px-3 py-2">
                                    <span className="text-[10px] font-black text-teal-600 mt-0.5 shrink-0">#{i + 1}</span>
                                    <p className="text-xs text-slate-700 flex-1 leading-relaxed">{obs}</p>
                                    {!readOnly && (
                                        <button
                                            onClick={() => removeObservation(i)}
                                            className="text-[10px] text-slate-300 hover:text-red-400 shrink-0 mt-0.5"
                                        >
                                            ×
                                        </button>
                                    )}
                                </div>
                            ))}
                        </div>
                        {!readOnly && (
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={newObservation}
                                    onChange={(e) => setNewObservation(e.target.value)}
                                    onKeyDown={(e) => e.key === "Enter" && addObservation()}
                                    placeholder="Add observation..."
                                    className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 placeholder:text-slate-400"
                                />
                                <button
                                    onClick={addObservation}
                                    disabled={!newObservation.trim()}
                                    className="px-3 py-2 bg-teal-500 text-white rounded-lg text-xs font-bold hover:bg-teal-600 disabled:opacity-40 transition-colors"
                                >
                                    Add
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Management Impressions */}
                    <div className="space-y-1.5">
                        <label className="text-[11px] font-bold text-slate-500 uppercase">Management Impressions</label>
                        <textarea
                            rows={4}
                            value={data.managementImpressions}
                            onChange={(e) => update("managementImpressions", e.target.value)}
                            disabled={readOnly}
                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 resize-none disabled:opacity-60 leading-relaxed"
                        />
                    </div>

                    {/* Overall Rating */}
                    <div className="flex items-center justify-between bg-slate-50 rounded-lg p-4">
                        <div className="flex items-center gap-2">
                            <Star className="w-4 h-4 text-amber-500" />
                            <span className="text-xs font-bold text-slate-700">Overall Site Rating</span>
                        </div>
                        <div className="flex items-center gap-3">
                            <input
                                type="range"
                                min={0}
                                max={10}
                                step={0.5}
                                value={data.overallRating}
                                onChange={(e) => update("overallRating", Number(e.target.value))}
                                disabled={readOnly}
                                className="w-28 accent-amber-500"
                            />
                            <span className="text-lg font-black text-amber-600 w-10 text-right">{data.overallRating}</span>
                            <span className="text-[10px] text-slate-400">/10</span>
                        </div>
                    </div>

                    {/* Photographs */}
                    {data.photographs.length > 0 && (
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold text-slate-500 uppercase flex items-center gap-1">
                                <Camera className="w-3 h-3" /> Photographs ({data.photographs.length})
                            </label>
                            <div className="flex flex-wrap gap-2">
                                {data.photographs.map((photo, i) => (
                                    <div key={i} className="flex items-center gap-1.5 bg-slate-50 rounded-lg px-3 py-1.5">
                                        <Camera className="w-3 h-3 text-slate-400" />
                                        <span className="text-[11px] text-slate-600">{photo}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Submit */}
                    {!readOnly && (
                        <div className="pt-3 border-t border-slate-100">
                            <button
                                onClick={handleSubmit}
                                disabled={submitted}
                                className={cn(
                                    "flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-bold transition-all",
                                    submitted
                                        ? "bg-emerald-100 text-emerald-700"
                                        : "bg-teal-500 text-white hover:bg-teal-600 shadow-lg shadow-teal-500/20"
                                )}
                            >
                                {submitted ? (
                                    <><CheckCircle2 className="w-4 h-4" /> Saved</>
                                ) : (
                                    <><Save className="w-4 h-4" /> Save Site Visit Report</>
                                )}
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
