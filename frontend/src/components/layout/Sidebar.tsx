"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Upload,
    Activity,
    MessageSquare,
    AlertTriangle,
    Target,
    History,
    BarChart3,
    Settings,
    HelpCircle,
    FileText,
    Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const menuItems = [
    { name: "Upload", icon: Upload, href: "/upload" },
    { name: "Processing", icon: Activity, href: "/processing" },
    { name: "Interview", icon: MessageSquare, href: "/interview" },
    { name: "Tickets", icon: AlertTriangle, href: "/tickets" },
    { name: "Results", icon: Target, href: "/results" },
    { name: "History", icon: History, href: "/history" },
    { name: "Analytics", icon: BarChart3, href: "/analytics" },
];

const footerItems = [
    { name: "Documentation", icon: FileText, href: "#" },
    { name: "Help", icon: HelpCircle, href: "#" },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="w-64 bg-slate-50 border-r border-slate-200 flex flex-col h-screen overflow-hidden">
            {/* Brand */}
            <div className="h-16 flex items-center px-6 gap-3 flex-shrink-0 bg-white border-b border-slate-100">
                <div className="w-8 h-8 rounded-lg bg-teal-500 flex items-center justify-center">
                    <Zap className="w-4 h-4 text-white" strokeWidth={3} />
                </div>
                <div className="flex flex-col">
                    <span className="text-slate-800 font-bold text-sm tracking-tight leading-none">Intelli-Credit</span>
                    <span className="text-[9px] text-slate-400 font-medium tracking-wider uppercase">AI Credit Engine</span>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 overflow-y-auto py-4">
                <div className="px-3 mb-2">
                    <p className="px-4 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Pipeline</p>
                    {menuItems.slice(0, 5).map((item) => {
                        const isActive = pathname === item.href || (item.href === "/upload" && pathname === "/");
                        return (
                            <Link
                                key={item.name}
                                href={item.href}
                                className={cn(
                                    "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-semibold transition-all mb-1 group",
                                    isActive
                                        ? "bg-teal-400 text-white shadow-md shadow-teal-400/20"
                                        : "text-slate-600 hover:bg-white hover:text-slate-900"
                                )}
                            >
                                <item.icon className={cn(
                                    "w-5 h-5 shrink-0",
                                    isActive ? "text-white" : "text-slate-400 group-hover:text-slate-600"
                                )} />
                                <span className="flex-1">{item.name}</span>
                            </Link>
                        );
                    })}

                    <p className="px-4 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 mt-6">Intelligence</p>
                    {menuItems.slice(5).map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link
                                key={item.name}
                                href={item.href}
                                className={cn(
                                    "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-semibold transition-all mb-1 group",
                                    isActive
                                        ? "bg-teal-400 text-white shadow-md shadow-teal-400/20"
                                        : "text-slate-600 hover:bg-white hover:text-slate-900"
                                )}
                            >
                                <item.icon className={cn(
                                    "w-5 h-5 shrink-0",
                                    isActive ? "text-white" : "text-slate-400 group-hover:text-slate-600"
                                )} />
                                <span className="flex-1">{item.name}</span>
                            </Link>
                        );
                    })}
                </div>

                <div className="mt-auto pt-8 border-t border-slate-200 px-3">
                    <p className="px-4 text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4">v1.0.0 — Hackathon</p>
                    {footerItems.map((item) => (
                        <Link
                            key={item.name}
                            href={item.href}
                            className="flex items-center gap-3 px-4 py-2.5 text-[13px] font-medium text-slate-500 hover:text-slate-900 transition-colors"
                        >
                            <item.icon className="w-4 h-4 text-slate-400" />
                            {item.name}
                        </Link>
                    ))}
                </div>
            </nav>
        </div>
    );
}
