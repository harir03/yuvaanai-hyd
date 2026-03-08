"use client";

import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import {
    Network,
    ZoomIn,
    ZoomOut,
    Maximize2,
    Filter,
    AlertTriangle,
    Building2,
    User,
    Landmark,
    Shield,
    BarChart3,
    Truck,
    ShoppingCart,
    Gavel,
    Info,
    X,
    Eye,
    EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    mockKnowledgeGraph,
    getEdgeColor,
    type GraphNode,
    type GraphEdge,
    type KnowledgeGraphData,
} from "@/lib/mockData";

/* ─── Node positioning (force-directed approximation via static layout) ─── */

interface PositionedNode extends GraphNode {
    x: number;
    y: number;
}

function layoutNodes(nodes: GraphNode[], edges: GraphEdge[], width: number, height: number): PositionedNode[] {
    const cx = width / 2;
    const cy = height / 2;

    // Place central company node at center
    const companyNodes = nodes.filter((n) => n.type === "Company");
    const otherNodes = nodes.filter((n) => n.type !== "Company");

    const positioned: PositionedNode[] = [];

    // Company nodes near center
    companyNodes.forEach((node, i) => {
        const angle = (i / Math.max(companyNodes.length, 1)) * Math.PI * 2;
        const r = companyNodes.length === 1 ? 0 : 80;
        positioned.push({
            ...node,
            x: cx + Math.cos(angle) * r,
            y: cy + Math.sin(angle) * r,
        });
    });

    // Other nodes in rings by type
    const typeGroups: Record<string, GraphNode[]> = {};
    otherNodes.forEach((n) => {
        if (!typeGroups[n.type]) typeGroups[n.type] = [];
        typeGroups[n.type].push(n);
    });

    const typeKeys = Object.keys(typeGroups);
    const ringRadius = Math.min(width, height) * 0.32;

    typeKeys.forEach((type, ti) => {
        const group = typeGroups[type];
        const baseAngle = (ti / typeKeys.length) * Math.PI * 2 - Math.PI / 2;
        group.forEach((node, ni) => {
            const spread = group.length > 1 ? (Math.PI * 0.4) / group.length : 0;
            const angle = baseAngle + (ni - (group.length - 1) / 2) * spread;
            const r = ringRadius + (ni % 2) * 35;
            positioned.push({
                ...node,
                x: cx + Math.cos(angle) * r,
                y: cy + Math.sin(angle) * r,
            });
        });
    });

    return positioned;
}

/* ─── Node icon ─── */
function nodeIcon(type: GraphNode["type"]): React.ElementType {
    const map: Record<string, React.ElementType> = {
        Company: Building2,
        Director: User,
        Supplier: Truck,
        Customer: ShoppingCart,
        Bank: Landmark,
        Auditor: Shield,
        RatingAgency: BarChart3,
        Case: Gavel,
    };
    return map[type] ?? Info;
}

function nodeColor(type: GraphNode["type"]): string {
    const c: Record<string, string> = {
        Company: "#14b8a6",
        Director: "#6366f1",
        Supplier: "#f59e0b",
        Customer: "#10b981",
        Bank: "#3b82f6",
        Auditor: "#a855f7",
        RatingAgency: "#06b6d4",
        Case: "#ef4444",
    };
    return c[type] ?? "#94a3b8";
}

function nodeBg(type: GraphNode["type"]): string {
    const c: Record<string, string> = {
        Company: "bg-teal-50 border-teal-300",
        Director: "bg-indigo-50 border-indigo-300",
        Supplier: "bg-amber-50 border-amber-300",
        Customer: "bg-emerald-50 border-emerald-300",
        Bank: "bg-blue-50 border-blue-300",
        Auditor: "bg-purple-50 border-purple-300",
        RatingAgency: "bg-cyan-50 border-cyan-300",
        Case: "bg-red-50 border-red-300",
    };
    return c[type] ?? "bg-slate-50 border-slate-300";
}

/* ─── Risk Edge Detection ─── */
function isRiskEdge(edge: GraphEdge): boolean {
    const riskTypes = ["FILED_CASE_AGAINST", "OUTSTANDING_RECEIVABLE"];
    const riskLabels = ["hidden RPT", "undisclosed", "NPA", "Default"];
    return (
        riskTypes.includes(edge.type) ||
        riskLabels.some((r) => edge.label.toLowerCase().includes(r.toLowerCase()))
    );
}

/* ─── Main Component ─── */

interface KnowledgeGraphProps {
    data?: KnowledgeGraphData;
}

export function KnowledgeGraph({ data }: KnowledgeGraphProps) {
    const graphData = data ?? mockKnowledgeGraph;
    const svgRef = useRef<SVGSVGElement>(null);

    const [zoom, setZoom] = useState(1);
    const [pan, setPan] = useState({ x: 0, y: 0 });
    const [selectedNode, setSelectedNode] = useState<PositionedNode | null>(null);
    const [hoveredEdge, setHoveredEdge] = useState<string | null>(null);
    const [showRiskOnly, setShowRiskOnly] = useState(false);
    const [visibleTypes, setVisibleTypes] = useState<Set<string>>(
        new Set(["Company", "Director", "Supplier", "Customer", "Bank", "Auditor", "RatingAgency", "Case"])
    );

    // Panning state
    const [isPanning, setIsPanning] = useState(false);
    const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

    const WIDTH = 900;
    const HEIGHT = 600;

    const positioned = useMemo(
        () => layoutNodes(graphData.nodes, graphData.edges, WIDTH, HEIGHT),
        [graphData.nodes, graphData.edges]
    );

    const nodeMap = useMemo(() => {
        const m = new Map<string, PositionedNode>();
        positioned.forEach((n) => m.set(n.id, n));
        return m;
    }, [positioned]);

    const filteredNodes = useMemo(
        () => positioned.filter((n) => visibleTypes.has(n.type)),
        [positioned, visibleTypes]
    );

    const filteredEdges = useMemo(() => {
        const visibleIds = new Set(filteredNodes.map((n) => n.id));
        let edges = graphData.edges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));
        if (showRiskOnly) edges = edges.filter(isRiskEdge);
        return edges;
    }, [graphData.edges, filteredNodes, showRiskOnly]);

    const toggleType = (type: string) => {
        setVisibleTypes((prev) => {
            const next = new Set(prev);
            if (next.has(type)) next.delete(type);
            else next.add(type);
            return next;
        });
    };

    const handleMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
        if ((e.target as SVGElement).tagName === "svg" || (e.target as SVGElement).closest("[data-pannable]")) {
            setIsPanning(true);
            panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
        }
    }, [pan]);

    const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
        if (!isPanning) return;
        setPan({
            x: panStart.current.panX + (e.clientX - panStart.current.x),
            y: panStart.current.panY + (e.clientY - panStart.current.y),
        });
    }, [isPanning]);

    const handleMouseUp = useCallback(() => setIsPanning(false), []);

    const handleWheel = useCallback((e: React.WheelEvent) => {
        e.preventDefault();
        setZoom((z) => Math.max(0.3, Math.min(3, z - e.deltaY * 0.001)));
    }, []);

    const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

    const allTypes = Array.from(new Set(graphData.nodes.map((n) => n.type)));
    const riskEdges = graphData.edges.filter(isRiskEdge);

    return (
        <div className="space-y-4">
            {/* Stats Bar */}
            <div className="grid grid-cols-4 gap-3">
                {[
                    { label: "Entities", value: graphData.stats.totalNodes, color: "text-teal-600" },
                    { label: "Relationships", value: graphData.stats.totalEdges, color: "text-indigo-600" },
                    { label: "Communities", value: graphData.stats.communities, color: "text-amber-600" },
                    { label: "Risk Paths", value: graphData.stats.riskPaths, color: "text-red-600" },
                ].map((s) => (
                    <div key={s.label} className="bg-white rounded-lg border border-slate-100 p-3 text-center">
                        <p className="text-lg font-black text-slate-800">{s.value}</p>
                        <p className="text-[10px] font-bold text-slate-400 uppercase">{s.label}</p>
                    </div>
                ))}
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 flex-wrap">
                    {allTypes.map((type) => {
                        const active = visibleTypes.has(type);
                        return (
                            <button
                                key={type}
                                onClick={() => toggleType(type)}
                                className={cn(
                                    "text-[10px] font-bold px-2.5 py-1 rounded-full transition-all flex items-center gap-1",
                                    active ? "shadow-sm" : "opacity-40"
                                )}
                                style={{
                                    backgroundColor: active ? `${nodeColor(type as GraphNode["type"])}15` : undefined,
                                    color: nodeColor(type as GraphNode["type"]),
                                    border: `1px solid ${active ? nodeColor(type as GraphNode["type"]) : "transparent"}`,
                                }}
                            >
                                {active ? <Eye className="w-2.5 h-2.5" /> : <EyeOff className="w-2.5 h-2.5" />}
                                {type}
                            </button>
                        );
                    })}
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowRiskOnly(!showRiskOnly)}
                        className={cn(
                            "text-[10px] font-bold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1",
                            showRiskOnly ? "bg-red-50 text-red-600 border border-red-200" : "bg-slate-50 text-slate-500 border border-slate-200"
                        )}
                    >
                        <AlertTriangle className="w-3 h-3" />
                        Risk Paths ({riskEdges.length})
                    </button>
                    <button onClick={() => setZoom((z) => Math.min(3, z + 0.2))} className="p-1.5 bg-white border border-slate-200 rounded-lg hover:bg-slate-50">
                        <ZoomIn className="w-3.5 h-3.5 text-slate-500" />
                    </button>
                    <button onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))} className="p-1.5 bg-white border border-slate-200 rounded-lg hover:bg-slate-50">
                        <ZoomOut className="w-3.5 h-3.5 text-slate-500" />
                    </button>
                    <button onClick={resetView} className="p-1.5 bg-white border border-slate-200 rounded-lg hover:bg-slate-50">
                        <Maximize2 className="w-3.5 h-3.5 text-slate-500" />
                    </button>
                </div>
            </div>

            {/* Graph Canvas */}
            <div className="bg-white rounded-xl border border-slate-100 overflow-hidden relative" style={{ height: HEIGHT }}>
                <svg
                    ref={svgRef}
                    width="100%"
                    height="100%"
                    viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
                    className={cn("cursor-grab", isPanning && "cursor-grabbing")}
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                    onWheel={handleWheel}
                >
                    <defs>
                        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                            <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
                        </marker>
                        {graphData.edges.map((e) => (
                            <marker key={`arrow-${e.id}`} id={`arrow-${e.id}`} markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                                <polygon points="0 0, 8 3, 0 6" fill={getEdgeColor(e.type)} />
                            </marker>
                        ))}
                    </defs>

                    <g data-pannable="true" transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                        {/* Edges */}
                        {filteredEdges.map((edge) => {
                            const src = nodeMap.get(edge.source);
                            const tgt = nodeMap.get(edge.target);
                            if (!src || !tgt) return null;
                            const isRisk = isRiskEdge(edge);
                            const isHovered = hoveredEdge === edge.id;
                            const midX = (src.x + tgt.x) / 2;
                            const midY = (src.y + tgt.y) / 2;

                            return (
                                <g
                                    key={edge.id}
                                    onMouseEnter={() => setHoveredEdge(edge.id)}
                                    onMouseLeave={() => setHoveredEdge(null)}
                                    className="cursor-pointer"
                                >
                                    <line
                                        x1={src.x}
                                        y1={src.y}
                                        x2={tgt.x}
                                        y2={tgt.y}
                                        stroke={getEdgeColor(edge.type)}
                                        strokeWidth={isHovered ? 3 : isRisk ? 2.5 : 1.5}
                                        strokeDasharray={isRisk ? "6 3" : undefined}
                                        opacity={isHovered ? 1 : 0.6}
                                        markerEnd={`url(#arrow-${edge.id})`}
                                    />
                                    {isHovered && (
                                        <g>
                                            <rect
                                                x={midX - 80}
                                                y={midY - 12}
                                                width={160}
                                                height={24}
                                                rx={4}
                                                fill="white"
                                                stroke={getEdgeColor(edge.type)}
                                                strokeWidth={1}
                                            />
                                            <text
                                                x={midX}
                                                y={midY + 4}
                                                textAnchor="middle"
                                                fontSize={9}
                                                fontWeight={600}
                                                fill="#334155"
                                            >
                                                {edge.label.length > 30 ? edge.label.slice(0, 30) + "…" : edge.label}
                                            </text>
                                        </g>
                                    )}
                                </g>
                            );
                        })}

                        {/* Nodes */}
                        {filteredNodes.map((node) => {
                            const isSelected = selectedNode?.id === node.id;
                            const color = nodeColor(node.type);
                            const radius = node.type === "Company" ? 28 : 20;

                            return (
                                <g
                                    key={node.id}
                                    className="cursor-pointer"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setSelectedNode(isSelected ? null : node);
                                    }}
                                >
                                    {/* Glow for selected */}
                                    {isSelected && (
                                        <circle cx={node.x} cy={node.y} r={radius + 6} fill={`${color}20`} stroke={color} strokeWidth={1.5} strokeDasharray="4 2" />
                                    )}
                                    <circle
                                        cx={node.x}
                                        cy={node.y}
                                        r={radius}
                                        fill="white"
                                        stroke={color}
                                        strokeWidth={isSelected ? 3 : 2}
                                    />
                                    <circle cx={node.x} cy={node.y} r={radius - 4} fill={`${color}15`} />

                                    {/* Label */}
                                    <text
                                        x={node.x}
                                        y={node.y + radius + 14}
                                        textAnchor="middle"
                                        fontSize={node.type === "Company" ? 10 : 8}
                                        fontWeight={node.type === "Company" ? 700 : 600}
                                        fill="#334155"
                                    >
                                        {node.label.length > 20 ? node.label.slice(0, 18) + "…" : node.label}
                                    </text>

                                    {/* Type icon text (emoji shorthand) */}
                                    <text
                                        x={node.x}
                                        y={node.y + 4}
                                        textAnchor="middle"
                                        fontSize={radius * 0.7}
                                        fill={color}
                                    >
                                        {node.type === "Company" ? "🏢" : node.type === "Director" ? "👤" :
                                         node.type === "Supplier" ? "🚚" : node.type === "Customer" ? "🛒" :
                                         node.type === "Bank" ? "🏦" : node.type === "Auditor" ? "🛡" :
                                         node.type === "RatingAgency" ? "📊" : "⚖️"}
                                    </text>
                                </g>
                            );
                        })}
                    </g>
                </svg>

                {/* Node Detail Panel */}
                {selectedNode && (
                    <div className="absolute top-4 right-4 w-72 bg-white rounded-xl shadow-lg border border-slate-200 p-4 z-10">
                        <div className="flex items-start justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <div
                                    className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm"
                                    style={{ backgroundColor: nodeColor(selectedNode.type) }}
                                >
                                    {selectedNode.type === "Company" ? "🏢" : selectedNode.type === "Director" ? "👤" :
                                     selectedNode.type === "Supplier" ? "🚚" : selectedNode.type === "Customer" ? "🛒" :
                                     selectedNode.type === "Bank" ? "🏦" : selectedNode.type === "Auditor" ? "🛡" :
                                     selectedNode.type === "RatingAgency" ? "📊" : "⚖️"}
                                </div>
                                <div>
                                    <p className="text-xs font-bold text-slate-800">{selectedNode.label}</p>
                                    <p className="text-[10px] text-slate-400">{selectedNode.type}</p>
                                </div>
                            </div>
                            <button onClick={() => setSelectedNode(null)} className="p-0.5 hover:bg-slate-100 rounded">
                                <X className="w-3.5 h-3.5 text-slate-400" />
                            </button>
                        </div>
                        <div className="space-y-1.5">
                            {Object.entries(selectedNode.properties).map(([key, val]) => (
                                <div key={key} className="flex items-start justify-between gap-2">
                                    <span className="text-[10px] font-bold text-slate-400 uppercase">{key}</span>
                                    <span className={cn(
                                        "text-[11px] text-right font-medium",
                                        val.includes("NPA") || val.includes("Default") ? "text-red-600 font-bold" : "text-slate-700"
                                    )}>
                                        {val}
                                    </span>
                                </div>
                            ))}
                        </div>
                        {/* Connected edges */}
                        <div className="mt-3 pt-3 border-t border-slate-100">
                            <p className="text-[10px] font-black text-slate-400 uppercase mb-1.5">Connections</p>
                            {graphData.edges
                                .filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)
                                .map((e) => {
                                    const other = e.source === selectedNode.id ? nodeMap.get(e.target) : nodeMap.get(e.source);
                                    return (
                                        <div key={e.id} className="flex items-center gap-1.5 py-1">
                                            <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: getEdgeColor(e.type) }} />
                                            <span className="text-[10px] text-slate-600 truncate">
                                                {e.type.replace(/_/g, " ")} → {other?.label ?? "?"}
                                            </span>
                                        </div>
                                    );
                                })}
                        </div>
                    </div>
                )}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 flex-wrap text-[10px] text-slate-500">
                <span className="font-bold text-slate-400">LEGEND:</span>
                {allTypes.map((type) => (
                    <span key={type} className="flex items-center gap-1">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: nodeColor(type as GraphNode["type"]) }} />
                        {type}
                    </span>
                ))}
                <span className="ml-4 flex items-center gap-1">
                    <span className="w-4 h-0.5 bg-red-400" style={{ borderTop: "2px dashed #ef4444" }} />
                    Risk Path
                </span>
            </div>
        </div>
    );
}
