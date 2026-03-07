"""
Intelli-Credit — FastAPI Application Entry Point

The main application factory that:
- Configures CORS for frontend communication
- Registers all REST API routes
- Registers WebSocket endpoints for live thinking + progress
- Sets up lifespan events (startup/shutdown)
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

# WebSocket handlers
from backend.api.websocket.thinking_ws import thinking_ws_endpoint, get_active_sessions
from backend.api.websocket.progress_ws import progress_ws_endpoint

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

    # TODO: Initialize database connections (T0.4, T0.5)
    # await postgres_client.connect()
    # await redis_client.connect()
    # await neo4j_client.connect()

    yield

    logger.info("INTELLI-CREDIT API — Shutting down")
    # TODO: Close database connections
    # await postgres_client.disconnect()
    # await redis_client.disconnect()
    # await neo4j_client.disconnect()


# ── App Factory ──
app = FastAPI(
    title="Intelli-Credit API",
    description="AI-Powered Credit Decisioning Engine — Backend API",
    version="0.1.0",
    lifespan=lifespan,
)


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
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "intelli-credit-api",
        "version": "0.1.0",
        "environment": settings.app_env,
        "active_sessions": get_active_sessions(),
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
