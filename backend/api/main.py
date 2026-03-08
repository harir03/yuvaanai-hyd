"""
Intelli-Credit — FastAPI Application Entry Point

The main application factory that:
- Configures CORS for frontend communication
- Registers all REST API routes
- Registers WebSocket endpoints for live thinking + progress
- Sets up lifespan events (startup/shutdown) with real infrastructure
- Provides health check endpoint

Run with: uvicorn backend.api.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

# Route imports
from backend.api.routes.upload import router as upload_router
from backend.api.routes.assessment import router as assessment_router
from backend.api.routes.tickets import router as tickets_router
from backend.api.routes.analytics import router as analytics_router
from backend.api.routes.score import router as score_router
from backend.api.routes.decisions import router as decisions_router
from backend.api.routes.pipeline import router as pipeline_router
from backend.api.routes.compliance import router as compliance_router
from backend.api.routes.infrastructure import router as infrastructure_router

# WebSocket handlers
from backend.api.websocket.thinking_ws import thinking_ws_endpoint, get_active_sessions
from backend.api.websocket.progress_ws import progress_ws_endpoint

# Storage clients
from backend.storage.postgres_client import get_db_client
from backend.storage.redis_client import get_redis_client
from backend.storage.neo4j_client import get_neo4j_client
from backend.storage.elasticsearch_client import get_elasticsearch_client
from backend.storage.chromadb_client import get_chromadb_client

# Middleware
from backend.api.middleware.rate_limiter import RateLimitMiddleware

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("  INTELLI-CREDIT API — Starting up")
    logger.info(f"  Environment: {settings.app_env}")
    logger.info(f"  Frontend URL: {settings.frontend_url}")
    logger.info("=" * 60)

    # ── Initialize all infrastructure services ──
    # Each client gracefully falls back to in-memory if the real service is unavailable

    # PostgreSQL
    db = get_db_client(settings.postgres_dsn)
    await db.initialize()
    logger.info(f"  PostgreSQL: {db.backend}")

    # Redis
    rc = get_redis_client(settings.redis_url)
    await rc.initialize()
    logger.info(f"  Redis: {rc.backend}")

    # Neo4j
    nc = get_neo4j_client(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    await nc.initialize()
    logger.info(f"  Neo4j: {nc.backend}")

    # Elasticsearch
    es = get_elasticsearch_client(hosts=[settings.elasticsearch_url])
    await es.initialize()
    logger.info(f"  Elasticsearch: {'connected' if es._use_es else 'memory'}")

    # ChromaDB
    chroma = get_chromadb_client(settings.chromadb_host, settings.chromadb_port)
    await chroma.initialize()
    logger.info(f"  ChromaDB: {chroma.backend}")

    logger.info("=" * 60)
    logger.info("  All infrastructure services initialized")
    logger.info("=" * 60)

    yield

    # ── Shutdown — close all connections ──
    logger.info("INTELLI-CREDIT API — Shutting down")
    await db.close()
    await rc.close()
    await nc.close()
    await es.close()
    await chroma.close()
    logger.info("All connections closed")


# ── App Factory ──
app = FastAPI(
    title="Intelli-Credit API",
    description="AI-Powered Credit Decisioning Engine — Backend API",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Rate Limiting ──
app.add_middleware(RateLimitMiddleware)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST Routes ──
app.include_router(upload_router)
app.include_router(assessment_router)
app.include_router(tickets_router)
app.include_router(analytics_router)
app.include_router(score_router)
app.include_router(decisions_router)
app.include_router(pipeline_router)
app.include_router(compliance_router)
app.include_router(infrastructure_router)


# ── WebSocket Endpoints ──
@app.websocket("/ws/thinking/{session_id}")
async def thinking_websocket(websocket: WebSocket, session_id: str):
    """Live Thinking Chatbot — streams AI reasoning events."""
    await thinking_ws_endpoint(websocket, session_id)


@app.websocket("/ws/progress/{session_id}")
async def progress_websocket(websocket: WebSocket, session_id: str):
    """Pipeline Progress — streams stage transitions."""
    await progress_ws_endpoint(websocket, session_id)


# ── Health Check ──
@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint with infrastructure status."""
    # Quick connectivity check for each service
    infra = {}
    try:
        db = get_db_client()
        infra["postgres"] = db.backend if db.is_initialized else "not_initialized"
    except Exception:
        infra["postgres"] = "error"

    try:
        rc = get_redis_client()
        infra["redis"] = rc.backend if rc.is_initialized else "not_initialized"
    except Exception:
        infra["redis"] = "error"

    try:
        nc = get_neo4j_client()
        infra["neo4j"] = nc.backend if nc.is_initialized else "not_initialized"
    except Exception:
        infra["neo4j"] = "error"

    try:
        es = get_elasticsearch_client()
        infra["elasticsearch"] = "elasticsearch" if es._use_es else "memory"
    except Exception:
        infra["elasticsearch"] = "error"

    try:
        chroma = get_chromadb_client()
        infra["chromadb"] = chroma.backend if chroma.is_initialized else "not_initialized"
    except Exception:
        infra["chromadb"] = "error"

    return {
        "status": "healthy",
        "service": "intelli-credit-api",
        "version": "0.1.0",
        "environment": settings.app_env,
        "active_sessions": get_active_sessions(),
        "infrastructure": infra,
    }


@app.get("/", tags=["system"])
async def root():
    """Root endpoint — API info."""
    return {
        "service": "Intelli-Credit API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
