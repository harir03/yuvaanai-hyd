"use client";

import { Power, ChevronRight, Bell, Wifi, WifiOff } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";

const PAGE_TITLES: Record<string, string> = {
    "/": "Upload Documents",
    "/upload": "Upload Documents",
    "/processing": "Live Processing",
    "/interview": "Management Interview",
    "/tickets": "Ticket Resolution",
    "/results": "Score & CAM Report",
    "/history": "Decision Store",
    "/analytics": "Analytics Dashboard",
};

export function Header() {
    const pathname = usePathname();
    const pageTitle = PAGE_TITLES[pathname] ?? "Dashboard";
    const [wsConnected] = useState(false); // Will be connected to actual WS later

    return (
        <div className="h-16 flex items-center justify-between px-8 bg-white border-b border-slate-100 flex-shrink-0">
            <div className="flex items-center gap-2 overflow-hidden">
                <span className="text-slate-800 font-bold text-sm whitespace-nowrap">Intelli-Credit</span>
                <ChevronRight className="w-4 h-4 text-slate-300" />
                <span className="text-slate-500 font-medium text-sm whitespace-nowrap">{pageTitle}</span>
            </div>

            <div className="flex items-center gap-3">
                {/* WebSocket Connection Status */}
                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-100">
                    {wsConnected ? (
                        <Wifi className="w-3.5 h-3.5 text-emerald-500" />
                    ) : (
                        <WifiOff className="w-3.5 h-3.5 text-slate-400" />
                    )}
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                        {wsConnected ? "Live" : "Offline"}
                    </span>
                </div>

                {/* Notifications */}
                <button className="relative p-2.5 rounded-xl text-slate-400 hover:text-slate-800 hover:bg-slate-50 transition-all cursor-pointer">
                    <Bell className="w-5 h-5" />
                    <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
                </button>

                {/* Logout */}
                <button
                    onClick={() => alert("Logout clicked")}
                    className="p-2.5 rounded-xl text-slate-400 hover:text-slate-800 hover:bg-slate-50 transition-all cursor-pointer"
                >
                    <Power className="w-5 h-5" />
                </button>
            </div>
        </div>
    );
}
