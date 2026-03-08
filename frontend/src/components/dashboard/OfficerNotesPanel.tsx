"use client";

import { useState } from "react";
import {
    StickyNote,
    Plus,
    Trash2,
    Tag,
    User,
    Clock,
    MessageSquare,
    AlertCircle,
    Eye,
    ArrowUpRight,
    FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mockOfficerNotes, type OfficerNote } from "@/lib/mockData";

const CATEGORIES: OfficerNote["category"][] = [
    "Observation",
    "Concern",
    "Follow-up",
    "Override Justification",
    "General",
];

function categoryStyle(cat: OfficerNote["category"]): string {
    const m: Record<string, string> = {
        Observation: "bg-blue-50 text-blue-600 border-blue-200",
        Concern: "bg-red-50 text-red-600 border-red-200",
        "Follow-up": "bg-amber-50 text-amber-600 border-amber-200",
        "Override Justification": "bg-purple-50 text-purple-600 border-purple-200",
        General: "bg-slate-50 text-slate-600 border-slate-200",
    };
    return m[cat] ?? m.General;
}

function categoryIcon(cat: OfficerNote["category"]): React.ReactNode {
    const m: Record<string, React.ReactNode> = {
        Observation: <Eye className="w-3 h-3" />,
        Concern: <AlertCircle className="w-3 h-3" />,
        "Follow-up": <ArrowUpRight className="w-3 h-3" />,
        "Override Justification": <FileText className="w-3 h-3" />,
        General: <MessageSquare className="w-3 h-3" />,
    };
    return m[cat] ?? m.General;
}

interface OfficerNotesPanelProps {
    initialNotes?: OfficerNote[];
    readOnly?: boolean;
    onNotesChange?: (notes: OfficerNote[]) => void;
}

export function OfficerNotesPanel({ initialNotes, readOnly = false, onNotesChange }: OfficerNotesPanelProps) {
    const [notes, setNotes] = useState<OfficerNote[]>(initialNotes ?? mockOfficerNotes);
    const [isAdding, setIsAdding] = useState(false);
    const [newText, setNewText] = useState("");
    const [newCategory, setNewCategory] = useState<OfficerNote["category"]>("General");
    const [filterCategory, setFilterCategory] = useState<string>("all");

    const updateNotes = (updated: OfficerNote[]) => {
        setNotes(updated);
        onNotesChange?.(updated);
    };

    const addNote = () => {
        if (!newText.trim()) return;
        const note: OfficerNote = {
            id: `note-${Date.now()}`,
            author: "Current Officer",
            category: newCategory,
            text: newText.trim(),
            createdAt: new Date().toLocaleString("en-IN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }),
        };
        updateNotes([note, ...notes]);
        setNewText("");
        setNewCategory("General");
        setIsAdding(false);
    };

    const deleteNote = (id: string) => {
        updateNotes(notes.filter((n) => n.id !== id));
    };

    const filtered = filterCategory === "all" ? notes : notes.filter((n) => n.category === filterCategory);

    const categoryCount = (cat: string) => notes.filter((n) => n.category === cat).length;

    return (
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
            {/* Header */}
            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <StickyNote className="w-4 h-4 text-amber-500" />
                    <h2 className="text-sm font-bold text-slate-800">Officer Notes</h2>
                    <span className="text-[10px] font-bold text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full">
                        {notes.length}
                    </span>
                </div>
                {!readOnly && (
                    <button
                        onClick={() => setIsAdding(!isAdding)}
                        className={cn(
                            "flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all",
                            isAdding ? "bg-slate-100 text-slate-600" : "bg-teal-50 text-teal-600 hover:bg-teal-100"
                        )}
                    >
                        <Plus className="w-3 h-3" />
                        {isAdding ? "Cancel" : "Add Note"}
                    </button>
                )}
            </div>

            {/* New Note Form */}
            {isAdding && (
                <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50 space-y-3">
                    {/* Category Selector */}
                    <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[10px] font-bold text-slate-400 uppercase mr-1">Category:</span>
                        {CATEGORIES.map((cat) => (
                            <button
                                key={cat}
                                onClick={() => setNewCategory(cat)}
                                className={cn(
                                    "text-[10px] font-bold px-2.5 py-1 rounded-full border transition-all flex items-center gap-1",
                                    newCategory === cat ? categoryStyle(cat) : "bg-white text-slate-400 border-slate-200"
                                )}
                            >
                                {categoryIcon(cat)}
                                {cat}
                            </button>
                        ))}
                    </div>
                    <textarea
                        rows={3}
                        value={newText}
                        onChange={(e) => setNewText(e.target.value)}
                        placeholder="Enter your note..."
                        className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all placeholder:text-slate-400 resize-none"
                        autoFocus
                    />
                    <div className="flex justify-end">
                        <button
                            onClick={addNote}
                            disabled={!newText.trim()}
                            className="flex items-center gap-1.5 px-4 py-2 bg-teal-500 text-white rounded-lg text-xs font-bold hover:bg-teal-600 disabled:opacity-40 transition-colors shadow-sm"
                        >
                            <Plus className="w-3.5 h-3.5" /> Save Note
                        </button>
                    </div>
                </div>
            )}

            {/* Filter Bar */}
            <div className="px-5 py-2 border-b border-slate-50 flex items-center gap-1.5 overflow-x-auto">
                <button
                    onClick={() => setFilterCategory("all")}
                    className={cn(
                        "text-[10px] font-bold px-2.5 py-1 rounded-full whitespace-nowrap transition-all",
                        filterCategory === "all" ? "bg-teal-500 text-white shadow-sm" : "bg-slate-50 text-slate-400 hover:bg-slate-100"
                    )}
                >
                    All ({notes.length})
                </button>
                {CATEGORIES.map((cat) => {
                    const count = categoryCount(cat);
                    if (count === 0) return null;
                    return (
                        <button
                            key={cat}
                            onClick={() => setFilterCategory(cat)}
                            className={cn(
                                "text-[10px] font-bold px-2.5 py-1 rounded-full whitespace-nowrap transition-all flex items-center gap-1",
                                filterCategory === cat ? categoryStyle(cat) : "bg-slate-50 text-slate-400 hover:bg-slate-100"
                            )}
                        >
                            {categoryIcon(cat)}
                            {cat} ({count})
                        </button>
                    );
                })}
            </div>

            {/* Notes List */}
            <div className="divide-y divide-slate-50 max-h-[400px] overflow-y-auto">
                {filtered.length === 0 ? (
                    <div className="py-8 text-center">
                        <StickyNote className="w-8 h-8 text-slate-200 mx-auto mb-2" />
                        <p className="text-sm text-slate-400">No notes yet</p>
                    </div>
                ) : (
                    filtered.map((note) => (
                        <div key={note.id} className="px-5 py-3 hover:bg-slate-50/50 transition-colors group">
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1.5">
                                        <span className={cn(
                                            "text-[9px] font-black px-2 py-0.5 rounded-full border flex items-center gap-1",
                                            categoryStyle(note.category)
                                        )}>
                                            {categoryIcon(note.category)}
                                            {note.category}
                                        </span>
                                        <span className="text-[10px] text-slate-400 flex items-center gap-1">
                                            <User className="w-2.5 h-2.5" /> {note.author}
                                        </span>
                                        <span className="text-[10px] text-slate-300 flex items-center gap-1">
                                            <Clock className="w-2.5 h-2.5" /> {note.createdAt}
                                        </span>
                                    </div>
                                    <p className="text-xs text-slate-700 leading-relaxed">{note.text}</p>
                                </div>
                                {!readOnly && (
                                    <button
                                        onClick={() => deleteNote(note.id)}
                                        className="p-1 opacity-0 group-hover:opacity-100 hover:bg-red-50 rounded transition-all"
                                        title="Delete note"
                                    >
                                        <Trash2 className="w-3.5 h-3.5 text-red-400" />
                                    </button>
                                )}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
