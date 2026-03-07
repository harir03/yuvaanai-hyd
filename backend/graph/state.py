"""
Intelli-Credit — CreditAppraisalState

The master Pydantic v2 model that flows through every LangGraph node.
Each node reads from and writes to this state. Fields are grouped by
the pipeline stage that populates them.

This is the SINGLE SOURCE OF TRUTH for all pipeline state.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime
from decimal import Decimal
from enum import Enum
import operator

from backend.models.schemas import (
    CompanyInfo,
    DocumentMeta,
    PipelineStage,
    WorkerStatus,
    ThinkingEvent,
    Ticket,
    ScoreModuleSummary,
    ScoreBreakdownEntry,
    ScoreBand,
    AssessmentOutcome,
    EventType,
)


# ──────────────────────────────────────────────
# Sub-models used within state
# ──────────────────────────────────────────────

class WorkerOutput(BaseModel):
    """Output from a single document worker."""
    worker_id: str
    document_type: str
    status: str = "completed"
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    pages_processed: int = 0
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NormalizedField(BaseModel):
    """A single field with its value, source, and confidence."""
    value: Any
    source_document: str
    source_page: Optional[int] = None
    source_excerpt: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    unit: Optional[str] = None


class CrossVerificationResult(BaseModel):
    """Result of cross-verifying a field across multiple sources."""
    field_name: str
    sources: Dict[str, NormalizedField] = Field(default_factory=dict)
    max_deviation_pct: float = 0.0
    accepted_value: Optional[Any] = None
    accepted_source: Optional[str] = None
    status: str = "unverified"  # "verified", "flagged", "conflicting"
    note: Optional[str] = None


class RawDataPackage(BaseModel):
    """Consolidated, normalized output from all workers."""
    worker_outputs: Dict[str, WorkerOutput] = Field(default_factory=dict)
    cross_verifications: List[CrossVerificationResult] = Field(default_factory=list)
    completeness_score: float = 0.0
    mandatory_fields_present: bool = False
    contradictions: List[Dict[str, Any]] = Field(default_factory=list)


class ComputedMetrics(BaseModel):
    """Derived financial metrics computed by Agent 1.5."""
    dscr: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_equity_ratio: Optional[float] = None
    working_capital_cycle_days: Optional[int] = None
    revenue_cagr_3yr: Optional[float] = None
    ebitda_margin: Optional[float] = None
    pat_margin: Optional[float] = None
    interest_coverage_ratio: Optional[float] = None
    gst_bank_divergence_pct: Optional[float] = None
    itr_ar_divergence_pct: Optional[float] = None
    promoter_pledge_pct: Optional[float] = None
    promoter_holding_pct: Optional[float] = None


class FiveCsMapping(BaseModel):
    """Data points organized by the 5 Cs framework."""
    capacity: Dict[str, NormalizedField] = Field(default_factory=dict)
    character: Dict[str, NormalizedField] = Field(default_factory=dict)
    capital: Dict[str, NormalizedField] = Field(default_factory=dict)
    collateral: Dict[str, NormalizedField] = Field(default_factory=dict)
    conditions: Dict[str, NormalizedField] = Field(default_factory=dict)


class OrganizedPackage(BaseModel):
    """Output from Agent 1.5 — The Organizer."""
    five_cs: FiveCsMapping = Field(default_factory=FiveCsMapping)
    computed_metrics: ComputedMetrics = Field(default_factory=ComputedMetrics)
    ml_signals: Dict[str, Any] = Field(default_factory=dict)
    graph_entities_created: int = 0
    graph_relationships_created: int = 0


class ResearchFinding(BaseModel):
    """A single research finding from Agent 2."""
    source: str  # "tavily", "exa", "serpapi", "mca21", "njdg", "sebi", "rbi", "gstin"
    source_tier: int = Field(..., ge=1, le=5)
    source_weight: float = Field(..., ge=0.0, le=1.0)
    title: str
    content: str
    url: Optional[str] = None
    published_date: Optional[str] = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    verified: bool = False
    category: str = ""  # "litigation", "regulatory", "financial", "governance", "fraud"


class ResearchPackage(BaseModel):
    """Output from Agent 2 — The Research Agent."""
    findings: List[ResearchFinding] = Field(default_factory=list)
    government_sources: int = 0
    media_sources: int = 0
    total_findings: int = 0
    neo4j_entities_added: int = 0


class CompoundInsight(BaseModel):
    """An insight from Agent 2.5's graph reasoning."""
    pass_name: str  # "contradictions", "cascade", "hidden_relationships", "temporal", "positive"
    insight_type: str
    description: str
    evidence_chain: List[str] = Field(default_factory=list)
    score_impact: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    severity: str = "LOW"  # "LOW", "MEDIUM", "HIGH", "CRITICAL"


class ReasoningPackage(BaseModel):
    """Output from Agent 2.5 — Graph Reasoning."""
    insights: List[CompoundInsight] = Field(default_factory=list)
    total_compound_score_impact: int = 0
    passes_completed: int = 0


class EvidencePackage(BaseModel):
    """
    The FINAL package that Agent 3 reads.
    Agent 3 reads ONLY this. It never touches raw documents, Neo4j, or the Insight Store directly.
    """
    session_id: str = ""
    company: Optional[CompanyInfo] = None
    five_cs: FiveCsMapping = Field(default_factory=FiveCsMapping)
    computed_metrics: ComputedMetrics = Field(default_factory=ComputedMetrics)
    cross_verifications: List[CrossVerificationResult] = Field(default_factory=list)
    research_findings: List[ResearchFinding] = Field(default_factory=list)
    compound_insights: List[CompoundInsight] = Field(default_factory=list)
    ml_signals: Dict[str, Any] = Field(default_factory=dict)
    verified_findings: List[Dict[str, Any]] = Field(default_factory=list)
    uncertain_findings: List[Dict[str, Any]] = Field(default_factory=list)
    rejected_findings: List[Dict[str, Any]] = Field(default_factory=list)
    conflicting_findings: List[Dict[str, Any]] = Field(default_factory=list)
    tickets_raised: List[str] = Field(default_factory=list)  # ticket IDs


class HardBlock(BaseModel):
    """A hard block that caps the score."""
    trigger: str
    score_cap: int
    evidence: str
    source: str


# ──────────────────────────────────────────────
# Reducer helper for appending to lists in state
# ──────────────────────────────────────────────

def merge_lists(left: list, right: list) -> list:
    """Reducer that merges two lists (used for ThinkingEvents, Tickets)."""
    return left + right


# ──────────────────────────────────────────────
# CreditAppraisalState — The Master State Object
# ──────────────────────────────────────────────

class CreditAppraisalState(BaseModel):
    """
    Master state flowing through the entire LangGraph pipeline.

    Every node receives this, reads what it needs, writes its outputs,
    and returns the updated state. Fields accumulate progressively as
    the pipeline advances.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ── Session Identity ──
    session_id: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # ── Stage 0: Upload ──
    company: Optional[CompanyInfo] = None
    documents: List[DocumentMeta] = Field(default_factory=list)

    # ── Stage 1: Workers ──
    worker_outputs: Dict[str, WorkerOutput] = Field(default_factory=dict)
    workers_completed: int = 0
    workers_total: int = 0

    # ── Stage 2: Consolidation (Agent 0.5) ──
    raw_data_package: Optional[RawDataPackage] = None

    # ── Stage 3: Validation ──
    validation_passed: bool = False
    validation_errors: List[str] = Field(default_factory=list)

    # ── Stage 4: Organization (Agent 1.5) ──
    organized_package: Optional[OrganizedPackage] = None

    # ── Stage 5: Research (Agent 2) ──
    research_package: Optional[ResearchPackage] = None

    # ── Stage 6: Graph Reasoning (Agent 2.5) ──
    reasoning_package: Optional[ReasoningPackage] = None

    # ── Stage 7: Evidence Package Builder ──
    evidence_package: Optional[EvidencePackage] = None

    # ── Stage 8: Tickets ──
    tickets: List[Ticket] = Field(default_factory=list)
    tickets_blocking: bool = False  # True if HIGH/CRITICAL tickets unresolved

    # ── Stage 9: Recommendation (Agent 3) ──
    hard_blocks: List[HardBlock] = Field(default_factory=list)
    score: Optional[int] = None
    score_band: Optional[ScoreBand] = None
    score_modules: List[ScoreModuleSummary] = Field(default_factory=list)
    score_breakdown: List[ScoreBreakdownEntry] = Field(default_factory=list)
    outcome: AssessmentOutcome = AssessmentOutcome.PENDING
    cam_path: Optional[str] = None

    # ── Pipeline Tracking ──
    pipeline_stages: List[PipelineStage] = Field(default_factory=list)
    workers: List[WorkerStatus] = Field(default_factory=list)
    thinking_events: List[ThinkingEvent] = Field(default_factory=list)

    # ── Metadata ──
    processing_time: Optional[str] = None
    langsmith_trace_url: Optional[str] = None
    error: Optional[str] = None
