"""
Intelli-Credit — PostgreSQL Client (Async)

Async database client wrapping SQLAlchemy 2.0 async engine.
Falls back to aiosqlite (in-memory or file-based) when PostgreSQL
is unavailable — critical for hackathon demo without Docker.

Usage:
    db = get_db_client()
    await db.initialize()
    await db.save_assessment(assessment_data)
    result = await db.get_assessment(session_id)
    await db.close()
"""

import logging
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from sqlalchemy import select, update, delete, func, text

from backend.storage.database_models import (
    Base,
    AssessmentDB,
    ScoreBreakdownDB,
    FindingDB,
    TicketDB,
    DecisionOutcomeDB,
    ThinkingEventDB,
    RejectionEventDB,
    FraudInvestigationDB,
)

logger = logging.getLogger(__name__)


class DatabaseClient:
    """
    Async PostgreSQL client with SQLite fallback.

    Provides CRUD operations for all 8 tables. Uses SQLAlchemy 2.0
    async engine, automatically falls back to aiosqlite when
    PostgreSQL DSN is not available.
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Args:
            database_url: Async database URL. 
                PostgreSQL: "postgresql+asyncpg://user:pass@host:5432/db"
                SQLite: "sqlite+aiosqlite:///path/to/db.sqlite3"
                None: Uses in-memory SQLite
        """
        if database_url and database_url.startswith("postgresql"):
            self._url = database_url
            self._backend = "postgresql"
        else:
            # In-memory SQLite fallback
            self._url = database_url or "sqlite+aiosqlite://"
            self._backend = "sqlite"

        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._initialized = False

    async def initialize(self):
        """Create engine, session factory, and all tables."""
        if self._initialized:
            return

        try:
            self._engine = create_async_engine(
                self._url,
                echo=False,
                pool_pre_ping=True if self._backend == "postgresql" else False,
            )

            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # Create all tables
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            self._initialized = True
            logger.info(f"[Database] Initialized with {self._backend} backend")

        except Exception as e:
            logger.error(f"[Database] Failed to initialize: {e}")
            # If PostgreSQL fails, fall back to SQLite
            if self._backend == "postgresql":
                logger.warning("[Database] Falling back to in-memory SQLite")
                self._url = "sqlite+aiosqlite://"
                self._backend = "sqlite"
                self._engine = create_async_engine(self._url, echo=False)
                self._session_factory = async_sessionmaker(
                    self._engine, class_=AsyncSession, expire_on_commit=False,
                )
                async with self._engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                self._initialized = True
                logger.info("[Database] Initialized with SQLite fallback")
            else:
                raise

    def _get_session(self) -> AsyncSession:
        """Get a new async session."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_factory()

    # ──────────────────────────────────────────────
    # Assessment CRUD
    # ──────────────────────────────────────────────

    async def save_assessment(self, data: dict) -> AssessmentDB:
        """Create or update an assessment record."""
        async with self._get_session() as session:
            async with session.begin():
                existing = await session.get(AssessmentDB, data.get("session_id"))
                if existing:
                    for key, value in data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    return existing
                else:
                    assessment = AssessmentDB(**data)
                    session.add(assessment)
                    return assessment

    async def get_assessment(self, session_id: str) -> Optional[AssessmentDB]:
        """Get an assessment by session_id."""
        async with self._get_session() as session:
            return await session.get(AssessmentDB, session_id)

    async def list_assessments(
        self, limit: int = 50, offset: int = 0, status: Optional[str] = None,
    ) -> List[AssessmentDB]:
        """List assessments with optional filtering."""
        async with self._get_session() as session:
            stmt = select(AssessmentDB).order_by(AssessmentDB.created_at.desc())
            if status:
                stmt = stmt.where(AssessmentDB.status == status)
            stmt = stmt.limit(limit).offset(offset)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_assessment_status(
        self, session_id: str, status: str, **kwargs
    ) -> bool:
        """Update assessment status and optional fields."""
        async with self._get_session() as session:
            async with session.begin():
                assessment = await session.get(AssessmentDB, session_id)
                if not assessment:
                    return False
                assessment.status = status
                for key, value in kwargs.items():
                    if hasattr(assessment, key):
                        setattr(assessment, key, value)
                return True

    async def get_assessment_count(self, status: Optional[str] = None) -> int:
        """Count assessments with optional status filter."""
        async with self._get_session() as session:
            stmt = select(func.count(AssessmentDB.session_id))
            if status:
                stmt = stmt.where(AssessmentDB.status == status)
            result = await session.execute(stmt)
            return result.scalar() or 0

    # ──────────────────────────────────────────────
    # Score Breakdown
    # ──────────────────────────────────────────────

    async def save_score_entries(self, session_id: str, entries: List[dict]) -> int:
        """Save score breakdown entries for an assessment."""
        async with self._get_session() as session:
            async with session.begin():
                for entry in entries:
                    entry["session_id"] = session_id
                    session.add(ScoreBreakdownDB(**entry))
                return len(entries)

    async def get_score_breakdown(self, session_id: str) -> List[ScoreBreakdownDB]:
        """Get all score breakdown entries for an assessment."""
        async with self._get_session() as session:
            stmt = (
                select(ScoreBreakdownDB)
                .where(ScoreBreakdownDB.session_id == session_id)
                .order_by(ScoreBreakdownDB.module)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ──────────────────────────────────────────────
    # Findings
    # ──────────────────────────────────────────────

    async def save_finding(self, data: dict) -> FindingDB:
        """Save a research or compound finding."""
        async with self._get_session() as session:
            async with session.begin():
                finding = FindingDB(**data)
                session.add(finding)
                return finding

    async def get_findings(
        self, session_id: str, finding_type: Optional[str] = None
    ) -> List[FindingDB]:
        """Get findings for an assessment."""
        async with self._get_session() as session:
            stmt = select(FindingDB).where(FindingDB.session_id == session_id)
            if finding_type:
                stmt = stmt.where(FindingDB.finding_type == finding_type)
            stmt = stmt.order_by(FindingDB.created_at)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ──────────────────────────────────────────────
    # Tickets
    # ──────────────────────────────────────────────

    async def save_ticket(self, data: dict) -> TicketDB:
        """Save a ticket."""
        async with self._get_session() as session:
            async with session.begin():
                ticket = TicketDB(**data)
                session.add(ticket)
                return ticket

    async def get_tickets(
        self, session_id: str, status: Optional[str] = None
    ) -> List[TicketDB]:
        """Get tickets for an assessment."""
        async with self._get_session() as session:
            stmt = select(TicketDB).where(TicketDB.session_id == session_id)
            if status:
                stmt = stmt.where(TicketDB.status == status)
            stmt = stmt.order_by(TicketDB.created_at)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def resolve_ticket(
        self, ticket_id: str, resolution: str, resolved_by: str
    ) -> bool:
        """Resolve a ticket."""
        async with self._get_session() as session:
            async with session.begin():
                ticket = await session.get(TicketDB, ticket_id)
                if not ticket:
                    return False
                ticket.status = "RESOLVED"
                ticket.resolution = resolution
                ticket.resolved_by = resolved_by
                from datetime import datetime
                ticket.resolved_at = datetime.utcnow()
                return True

    # ──────────────────────────────────────────────
    # Thinking Events
    # ──────────────────────────────────────────────

    async def save_thinking_event(self, data: dict) -> ThinkingEventDB:
        """Save a thinking event to the audit log."""
        async with self._get_session() as session:
            async with session.begin():
                event = ThinkingEventDB(**data)
                session.add(event)
                return event

    async def save_thinking_events_batch(self, events: List[dict]) -> int:
        """Save multiple thinking events in one transaction."""
        async with self._get_session() as session:
            async with session.begin():
                for event_data in events:
                    session.add(ThinkingEventDB(**event_data))
                return len(events)

    async def get_thinking_events(
        self, session_id: str, agent: Optional[str] = None, event_type: Optional[str] = None,
    ) -> List[ThinkingEventDB]:
        """Get thinking events for an assessment with optional filters."""
        async with self._get_session() as session:
            stmt = select(ThinkingEventDB).where(ThinkingEventDB.session_id == session_id)
            if agent:
                stmt = stmt.where(ThinkingEventDB.agent == agent)
            if event_type:
                stmt = stmt.where(ThinkingEventDB.event_type == event_type)
            stmt = stmt.order_by(ThinkingEventDB.timestamp)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ──────────────────────────────────────────────
    # Rejection Events
    # ──────────────────────────────────────────────

    async def save_rejection_event(self, data: dict) -> RejectionEventDB:
        """Save a rejection event with evidence snapshot."""
        async with self._get_session() as session:
            async with session.begin():
                event = RejectionEventDB(**data)
                session.add(event)
                return event

    # ──────────────────────────────────────────────
    # Fraud Investigations
    # ──────────────────────────────────────────────

    async def save_fraud_investigation(self, data: dict) -> FraudInvestigationDB:
        """Save a fraud investigation record."""
        async with self._get_session() as session:
            async with session.begin():
                investigation = FraudInvestigationDB(**data)
                session.add(investigation)
                return investigation

    async def get_fraud_investigations(self, session_id: str) -> List[FraudInvestigationDB]:
        """Get fraud investigations for an assessment."""
        async with self._get_session() as session:
            stmt = (
                select(FraudInvestigationDB)
                .where(FraudInvestigationDB.session_id == session_id)
                .order_by(FraudInvestigationDB.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ──────────────────────────────────────────────
    # Analytics
    # ──────────────────────────────────────────────

    async def get_analytics(self) -> dict:
        """Get aggregate analytics across all assessments."""
        async with self._get_session() as session:
            total = (await session.execute(
                select(func.count(AssessmentDB.session_id))
            )).scalar() or 0

            completed = (await session.execute(
                select(func.count(AssessmentDB.session_id))
                .where(AssessmentDB.status == "completed")
            )).scalar() or 0

            avg_score = (await session.execute(
                select(func.avg(AssessmentDB.score))
                .where(AssessmentDB.score.isnot(None))
            )).scalar()

            return {
                "total_assessments": total,
                "completed_assessments": completed,
                "average_score": round(float(avg_score), 1) if avg_score else None,
                "processing": total - completed,
            }

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    async def close(self):
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()
            logger.info("[Database] Connection closed")

    async def drop_all(self):
        """Drop all tables — for testing only."""
        if self._engine:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

    @property
    def backend(self) -> str:
        """Return the active backend type."""
        return self._backend

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# ── Singleton ──
_db_client: Optional[DatabaseClient] = None


def get_db_client(database_url: Optional[str] = None) -> DatabaseClient:
    """Get or create the singleton DatabaseClient."""
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient(database_url)
    return _db_client


def reset_db_client():
    """Reset the singleton (for testing)."""
    global _db_client
    _db_client = None
