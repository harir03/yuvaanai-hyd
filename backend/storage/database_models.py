"""
Intelli-Credit — PostgreSQL Database Models (SQLAlchemy 2.0)

Defines all database tables for the structured storage layer.
Uses SQLAlchemy's declarative mapping with async support.

Tables (per architecture Section 7.2):
- assessments         — Master record, one per loan application
- score_breakdown     — Every point in the 0–850 score
- findings_store      — Every research + compound finding
- tickets             — Every conflict and its resolution
- decision_outcomes   — Filled AFTER loan matures
- thinking_events     — Complete AI thought log
- rejection_events    — All rejections with evidence snapshots
- fraud_investigations — All fraud detections with graph snapshots

All tables link to assessments via session_id FK.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SAEnum,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


# ──────────────────────────────────────────────
# 1. Assessments — Master record
# ──────────────────────────────────────────────

class AssessmentDB(Base):
    """
    Master assessment record — one per loan application.
    All other tables FK to this via session_id.
    """
    __tablename__ = "assessments"

    session_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Company info
    company_name = Column(String(256), nullable=False)
    cin = Column(String(64), nullable=True)
    gstin = Column(String(32), nullable=True)
    pan = Column(String(16), nullable=True)
    sector = Column(String(128), nullable=False)
    loan_type = Column(String(64), nullable=False)
    loan_amount = Column(String(64), nullable=False)
    loan_amount_numeric = Column(Float, nullable=False)

    # Pipeline status
    status = Column(String(32), default="processing", nullable=False)  # processing, completed, failed, rejected
    current_stage = Column(String(64), default="upload")
    pipeline_stages_json = Column(JSON, nullable=True)

    # Score output
    score = Column(Integer, nullable=True)
    score_band = Column(String(32), nullable=True)
    outcome = Column(String(32), default="PENDING")  # APPROVED, CONDITIONAL, REJECTED, PENDING
    cam_path = Column(String(512), nullable=True)

    # Metadata
    processing_time = Column(String(32), nullable=True)
    langsmith_trace_url = Column(String(512), nullable=True)
    documents_json = Column(JSON, nullable=True)  # List of DocumentMeta dicts
    error = Column(Text, nullable=True)

    # Relationships
    score_entries = relationship("ScoreBreakdownDB", back_populates="assessment", cascade="all, delete-orphan")
    findings = relationship("FindingDB", back_populates="assessment", cascade="all, delete-orphan")
    tickets = relationship("TicketDB", back_populates="assessment", cascade="all, delete-orphan")
    thinking_events = relationship("ThinkingEventDB", back_populates="assessment", cascade="all, delete-orphan")
    rejection_events = relationship("RejectionEventDB", back_populates="assessment", cascade="all, delete-orphan")
    fraud_investigations = relationship("FraudInvestigationDB", back_populates="assessment", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_assessments_status", "status"),
        Index("idx_assessments_created", "created_at"),
        Index("idx_assessments_company", "company_name"),
    )


# ──────────────────────────────────────────────
# 2. Score Breakdown — Every point in 0–850
# ──────────────────────────────────────────────

class ScoreBreakdownDB(Base):
    """Every single scored point in the 0–850 score."""
    __tablename__ = "score_breakdown"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("assessments.session_id", ondelete="CASCADE"), nullable=False)

    module = Column(String(32), nullable=False)  # CAPACITY, CHARACTER, CAPITAL, COLLATERAL, CONDITIONS, COMPOUND
    metric_name = Column(String(128), nullable=False)
    metric_value = Column(String(128), nullable=False)
    computation_formula = Column(Text, nullable=True)
    source_document = Column(String(256), nullable=True)
    source_page = Column(Integer, nullable=True)
    source_excerpt = Column(Text, nullable=True)
    benchmark_context = Column(Text, nullable=True)
    score_impact = Column(Integer, nullable=False)
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)
    human_override = Column(Boolean, default=False)

    assessment = relationship("AssessmentDB", back_populates="score_entries")

    __table_args__ = (
        Index("idx_score_session", "session_id"),
        Index("idx_score_module", "module"),
    )


# ──────────────────────────────────────────────
# 3. Findings Store — Research + Compound
# ──────────────────────────────────────────────

class FindingDB(Base):
    """Every research finding and compound insight."""
    __tablename__ = "findings_store"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("assessments.session_id", ondelete="CASCADE"), nullable=False)

    finding_type = Column(String(32), nullable=False)  # "research" or "compound"
    source = Column(String(64), nullable=True)  # tavily, exa, mca21, etc.
    source_tier = Column(Integer, nullable=True)
    source_weight = Column(Float, nullable=True)
    category = Column(String(64), nullable=True)  # litigation, regulatory, financial, etc.
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    url = Column(String(1024), nullable=True)
    relevance_score = Column(Float, default=0.0)
    verified = Column(Boolean, default=False)
    score_impact = Column(Integer, default=0)
    confidence = Column(Float, default=0.0)
    severity = Column(String(16), default="LOW")
    evidence_chain_json = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assessment = relationship("AssessmentDB", back_populates="findings")

    __table_args__ = (
        Index("idx_findings_session", "session_id"),
        Index("idx_findings_type", "finding_type"),
        Index("idx_findings_category", "category"),
    )


# ──────────────────────────────────────────────
# 4. Tickets — Conflicts + Resolution
# ──────────────────────────────────────────────

class TicketDB(Base):
    """Every conflict ticket and its resolution history."""
    __tablename__ = "tickets"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("assessments.session_id", ondelete="CASCADE"), nullable=False)

    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False)  # LOW, HIGH, CRITICAL
    status = Column(String(16), default="OPEN")  # OPEN, IN_REVIEW, RESOLVED, ESCALATED
    category = Column(String(64), nullable=True)
    raised_by = Column(String(128), nullable=True)  # agent name
    assigned_to = Column(String(128), nullable=True)
    resolution = Column(Text, nullable=True)
    resolved_by = Column(String(128), nullable=True)
    evidence_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    assessment = relationship("AssessmentDB", back_populates="tickets")

    __table_args__ = (
        Index("idx_tickets_session", "session_id"),
        Index("idx_tickets_status", "status"),
        Index("idx_tickets_severity", "severity"),
    )


# ──────────────────────────────────────────────
# 5. Decision Outcomes — Post-loan maturity
# ──────────────────────────────────────────────

class DecisionOutcomeDB(Base):
    """Filled AFTER the loan matures — for model feedback loop."""
    __tablename__ = "decision_outcomes"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("assessments.session_id", ondelete="CASCADE"), nullable=False, unique=True)

    actual_outcome = Column(String(32), nullable=True)  # PERFORMING, NPA, RESTRUCTURED, DEFAULT
    actual_default_date = Column(DateTime, nullable=True)
    dpd_max = Column(Integer, nullable=True)  # Days Past Due maximum
    recovery_rate = Column(Float, nullable=True)
    model_accuracy_notes = Column(Text, nullable=True)
    feedback_incorporated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ──────────────────────────────────────────────
# 6. Thinking Events — AI thought log
# ──────────────────────────────────────────────

class ThinkingEventDB(Base):
    """Complete log of AI reasoning events for audit trail."""
    __tablename__ = "thinking_events"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("assessments.session_id", ondelete="CASCADE"), nullable=False)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    agent = Column(String(128), nullable=False)
    event_type = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    source_document = Column(String(256), nullable=True)
    source_page = Column(Integer, nullable=True)
    source_excerpt = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    assessment = relationship("AssessmentDB", back_populates="thinking_events")

    __table_args__ = (
        Index("idx_thinking_session", "session_id"),
        Index("idx_thinking_agent", "agent"),
        Index("idx_thinking_type", "event_type"),
        Index("idx_thinking_timestamp", "timestamp"),
    )


# ──────────────────────────────────────────────
# 7. Rejection Events — With evidence snapshots
# ──────────────────────────────────────────────

class RejectionEventDB(Base):
    """All rejections with full evidence snapshot for audit."""
    __tablename__ = "rejection_events"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("assessments.session_id", ondelete="CASCADE"), nullable=False)

    rejection_reason = Column(Text, nullable=False)
    rejection_stage = Column(String(64), nullable=False)  # which pipeline stage triggered rejection
    hard_block_trigger = Column(String(128), nullable=True)
    score_at_rejection = Column(Integer, nullable=True)
    evidence_snapshot_json = Column(JSON, nullable=True)  # Full state snapshot at rejection time
    created_at = Column(DateTime, default=datetime.utcnow)

    assessment = relationship("AssessmentDB", back_populates="rejection_events")

    __table_args__ = (
        Index("idx_rejection_session", "session_id"),
    )


# ──────────────────────────────────────────────
# 8. Fraud Investigations — Graph snapshots
# ──────────────────────────────────────────────

class FraudInvestigationDB(Base):
    """All fraud detections with graph reasoning snapshots."""
    __tablename__ = "fraud_investigations"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("assessments.session_id", ondelete="CASCADE"), nullable=False)

    fraud_type = Column(String(64), nullable=False)  # circular_trading, shell_company, revenue_inflation, etc.
    detection_method = Column(String(64), nullable=False)  # GNN, isolation_forest, graph_reasoning, cross_verification
    confidence = Column(Float, nullable=False)
    severity = Column(String(16), nullable=False)
    description = Column(Text, nullable=False)
    evidence_chain_json = Column(JSON, nullable=True)
    graph_snapshot_json = Column(JSON, nullable=True)  # Neo4j subgraph snapshot
    ml_model_details_json = Column(JSON, nullable=True)
    score_impact = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    assessment = relationship("AssessmentDB", back_populates="fraud_investigations")

    __table_args__ = (
        Index("idx_fraud_session", "session_id"),
        Index("idx_fraud_type", "fraud_type"),
    )


# ──────────────────────────────────────────────
# 9. Users — Authentication & Authorization
# ──────────────────────────────────────────────

class UserDB(Base):
    """Application users for JWT authentication."""
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(256), nullable=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="officer", nullable=False)  # admin, officer
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_users_role", "role"),
    )
