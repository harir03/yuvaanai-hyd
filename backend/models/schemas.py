"""
Intelli-Credit — Core Pydantic v2 Schemas

All data structures used across the API, pipeline, and storage.
Every field is typed, described, and validated.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
from decimal import Decimal
import uuid


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class DocumentType(str, Enum):
    """8 document types processed by workers."""
    ANNUAL_REPORT = "ANNUAL_REPORT"
    BANK_STATEMENT = "BANK_STATEMENT"
    GST_RETURNS = "GST_RETURNS"
    ITR = "ITR"
    LEGAL_NOTICE = "LEGAL_NOTICE"
    BOARD_MINUTES = "BOARD_MINUTES"
    SHAREHOLDING_PATTERN = "SHAREHOLDING_PATTERN"
    RATING_REPORT = "RATING_REPORT"


class PipelineStageEnum(str, Enum):
    """9 pipeline stages."""
    UPLOAD = "UPLOAD"
    WORKERS = "WORKERS"
    CONSOLIDATION = "CONSOLIDATION"
    VALIDATION = "VALIDATION"
    ORGANIZATION = "ORGANIZATION"
    RESEARCH = "RESEARCH"
    REASONING = "REASONING"
    EVIDENCE = "EVIDENCE"
    TICKETS = "TICKETS"
    RECOMMENDATION = "RECOMMENDATION"


class PipelineStageStatus(str, Enum):
    """Status for each pipeline stage."""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkerStatusEnum(str, Enum):
    """Worker status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TicketSeverity(str, Enum):
    LOW = "LOW"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class ScoreModule(str, Enum):
    CAPACITY = "CAPACITY"
    CHARACTER = "CHARACTER"
    CAPITAL = "CAPITAL"
    COLLATERAL = "COLLATERAL"
    CONDITIONS = "CONDITIONS"
    COMPOUND = "COMPOUND"


class ScoreBand(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    FAIR = "Fair"
    POOR = "Poor"
    VERY_POOR = "Very Poor"
    DEFAULT_RISK = "Default Risk"


class AssessmentOutcome(str, Enum):
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


class EventType(str, Enum):
    """ThinkingEvent types — used by every agent."""
    READ = "READ"
    FOUND = "FOUND"
    COMPUTED = "COMPUTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"
    CRITICAL = "CRITICAL"
    CONNECTING = "CONNECTING"
    CONCLUDING = "CONCLUDING"
    QUESTIONING = "QUESTIONING"
    DECIDED = "DECIDED"


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────

class CompanyInfo(BaseModel):
    """Company information submitted with the upload."""
    model_config = ConfigDict(strict=True)

    name: str = Field(..., description="Legal company name")
    cin: Optional[str] = Field(None, description="Corporate Identification Number")
    gstin: Optional[str] = Field(None, description="GST Identification Number")
    pan: Optional[str] = Field(None, description="PAN of the company")
    sector: str = Field(..., description="Industry sector")
    loan_type: str = Field(..., description="e.g. Working Capital, Term Loan")
    loan_amount: str = Field(..., description="Requested loan amount as string, e.g. ₹50,00,00,000")
    loan_amount_numeric: float = Field(..., description="Loan amount in numeric form (INR)")
    incorporation_year: Optional[int] = Field(None, description="Year of incorporation")
    promoter_name: Optional[str] = Field(None, description="Primary promoter name")
    annual_turnover: Optional[str] = Field(None, description="Latest annual turnover")


class UploadRequest(BaseModel):
    """Upload endpoint request — company info is sent as form data alongside files."""
    company: CompanyInfo


class DocumentMeta(BaseModel):
    """Metadata for an uploaded document."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    document_type: DocumentType
    file_size: int = Field(..., description="Size in bytes")
    file_path: Optional[str] = Field(default=None, description="Absolute path to uploaded file")
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    page_count: Optional[int] = None
    ocr_required: bool = False


class WorkerStatus(BaseModel):
    """Real-time status of a document worker."""
    worker_id: str
    document_type: DocumentType
    status: WorkerStatusEnum = WorkerStatusEnum.QUEUED
    progress: int = Field(default=0, ge=0, le=100)
    current_task: str = Field(default="Queued")
    pages_processed: int = 0
    pages_total: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class PipelineStage(BaseModel):
    """Status of a single pipeline stage."""
    stage: PipelineStageEnum
    status: PipelineStageStatus = PipelineStageStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message: Optional[str] = None


class ThinkingEvent(BaseModel):
    """A single AI reasoning event for the Live Chatbot."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: str = Field(..., description="Agent name, e.g. 'Agent 0.5 — The Consolidator'")
    event_type: EventType
    message: str = Field(..., description="Human-readable reasoning step")
    source_document: Optional[str] = None
    source_page: Optional[int] = None
    source_excerpt: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None


class ScoreBreakdownEntry(BaseModel):
    """Every single point in the 0–850 score."""
    model_config = ConfigDict(strict=True)

    module: ScoreModule
    metric_name: str = Field(..., description="e.g., 'DSCR'")
    metric_value: str = Field(..., description="e.g., '1.38x'")
    computation_formula: str
    source_document: str
    source_page: int
    source_excerpt: str
    benchmark_context: str
    score_impact: int = Field(..., ge=-200, le=150)
    reasoning: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    human_override: bool = False


class ScoreModuleSummary(BaseModel):
    """Summary for one scoring module."""
    module: ScoreModule
    score: int = Field(..., description="Net score for this module")
    max_positive: int
    max_negative: int
    metrics: List[ScoreBreakdownEntry] = Field(default_factory=list)


class Ticket(BaseModel):
    """A conflict/issue requiring human review."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    title: str
    description: str
    severity: TicketSeverity
    status: TicketStatus = TicketStatus.OPEN
    category: str = Field(..., description="e.g. 'Revenue Discrepancy', 'RPT Concealment'")
    source_a: str = Field(..., description="First claim with source")
    source_b: str = Field(..., description="Contradicting claim with source")
    ai_recommendation: str = Field(..., description="What the AI recommends")
    score_impact: int = Field(..., description="How many points this ticket affects")
    precedents: List[Dict[str, Any]] = Field(default_factory=list)
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TicketResolveRequest(BaseModel):
    """Request to resolve a ticket."""
    resolution: str = Field(..., description="Officer's resolution text")
    resolved_by: str = Field(default="Credit Officer")


class AssessmentSummary(BaseModel):
    """Assessment summary returned by the API."""
    session_id: str
    company: CompanyInfo
    documents: List[DocumentMeta] = Field(default_factory=list)
    pipeline_stages: List[PipelineStage] = Field(default_factory=list)
    workers: List[WorkerStatus] = Field(default_factory=list)
    thinking_events: List[ThinkingEvent] = Field(default_factory=list)
    tickets: List[Ticket] = Field(default_factory=list)
    score: Optional[int] = None
    score_band: Optional[ScoreBand] = None
    score_modules: List[ScoreModuleSummary] = Field(default_factory=list)
    outcome: AssessmentOutcome = AssessmentOutcome.PENDING
    processing_time: Optional[str] = None
    documents_analyzed: int = 0
    findings_count: int = 0
    tickets_raised: int = 0
    tickets_resolved: int = 0
    cam_url: Optional[str] = None
    langsmith_trace_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class HistoryRecord(BaseModel):
    """A historical assessment record for the Decision Store."""
    session_id: str
    company_name: str
    sector: str
    loan_type: str
    loan_amount: str
    score: int
    score_band: ScoreBand
    outcome: AssessmentOutcome
    officer: str = Field(default="System")
    processing_time: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnalyticsData(BaseModel):
    """Aggregated analytics data."""
    total_assessments: int = 0
    average_score: float = 0.0
    approval_rate: float = 0.0
    average_processing_time: str = "0m"
    score_distribution: Dict[str, int] = Field(default_factory=dict)
    monthly_volume: List[Dict[str, Any]] = Field(default_factory=list)
    sector_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    outcome_distribution: Dict[str, int] = Field(default_factory=dict)


class ProgressUpdate(BaseModel):
    """Pipeline progress update sent via WebSocket."""
    session_id: str
    stage: PipelineStageEnum
    status: PipelineStageStatus
    message: Optional[str] = None
    workers: Optional[List[WorkerStatus]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
