"""
Intelli-Credit — Infrastructure Status Route

Provides real-time status of all infrastructure services:
PostgreSQL, Redis, Neo4j, Elasticsearch, ChromaDB, Celery, Flower.

GET /api/infrastructure/status  — Full service health report
GET /api/infrastructure/flower  — Flower monitoring status
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends

from backend.api.auth.jwt_handler import optional_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/infrastructure", tags=["infrastructure"], dependencies=[Depends(optional_auth)])


async def _check_postgres() -> Dict[str, Any]:
    """Check PostgreSQL connectivity."""
    try:
        from backend.storage.postgres_client import get_db_client
        db = get_db_client()
        if not db.is_initialized:
            await db.initialize()
        return {
            "status": "connected",
            "backend": db.backend,
            "initialized": db.is_initialized,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_redis() -> Dict[str, Any]:
    """Check Redis connectivity."""
    try:
        from backend.storage.redis_client import get_redis_client
        rc = get_redis_client()
        if not rc.is_initialized:
            await rc.initialize()
        return {
            "status": "connected",
            "backend": rc.backend,
            "initialized": rc.is_initialized,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_neo4j() -> Dict[str, Any]:
    """Check Neo4j connectivity."""
    try:
        from backend.storage.neo4j_client import get_neo4j_client
        nc = get_neo4j_client()
        if not nc.is_initialized:
            await nc.initialize()
        stats = await nc.get_stats()
        return {
            "status": "connected",
            "backend": nc.backend,
            "initialized": nc.is_initialized,
            "stats": stats,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_elasticsearch() -> Dict[str, Any]:
    """Check Elasticsearch connectivity."""
    try:
        from backend.storage.elasticsearch_client import get_elasticsearch_client
        es = get_elasticsearch_client()
        if not es.is_initialized:
            await es.initialize()
        stats = await es.get_stats()
        return {
            "status": "connected",
            "backend": "elasticsearch" if es._use_es else "memory",
            "initialized": es._initialized,
            "indices": stats,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_celery() -> Dict[str, Any]:
    """Check Celery worker availability."""
    try:
        from backend.workers.celery_app import is_celery_available, celery_app
        available = is_celery_available()
        if available and celery_app:
            # Try to inspect active workers
            inspector = celery_app.control.inspect(timeout=2)
            active = inspector.active() or {}
            return {
                "status": "connected",
                "available": True,
                "active_workers": len(active),
                "worker_names": list(active.keys()),
            }
        return {"status": "fallback", "available": False}
    except Exception as e:
        return {"status": "fallback", "available": False, "error": str(e)}


async def _check_flower() -> Dict[str, Any]:
    """Check Flower monitoring availability."""
    try:
        import urllib.request
        import json
        flower_url = "http://localhost:5555/api/workers"
        req = urllib.request.Request(flower_url, method="GET")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=3) as resp:
            workers = json.loads(resp.read().decode())
            return {
                "status": "connected",
                "url": "http://localhost:5555",
                "workers": len(workers),
            }
    except Exception:
        return {
            "status": "unavailable",
            "url": "http://localhost:5555",
            "hint": "Start Flower: celery -A backend.workers.celery_app flower --port=5555",
        }


@router.get("/status")
async def infrastructure_status():
    """
    Full infrastructure health report.
    
    Returns status of all services: PostgreSQL, Redis, Neo4j,
    Elasticsearch, Celery, Flower.
    """
    postgres = await _check_postgres()
    redis = await _check_redis()
    neo4j = await _check_neo4j()
    elasticsearch = await _check_elasticsearch()
    celery = await _check_celery()
    flower = await _check_flower()

    services = {
        "postgres": postgres,
        "redis": redis,
        "neo4j": neo4j,
        "elasticsearch": elasticsearch,
        "celery": celery,
        "flower": flower,
    }

    # Count healthy vs degraded
    connected = sum(1 for s in services.values() if s.get("status") == "connected")
    total = len(services)

    return {
        "overall": "healthy" if connected == total else "degraded",
        "connected": connected,
        "total": total,
        "services": services,
    }


@router.get("/flower")
async def flower_status():
    """Check Flower monitoring availability."""
    return await _check_flower()
