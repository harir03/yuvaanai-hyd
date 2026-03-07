"""
Intelli-Credit — Redis Client

Async Redis client wrapping redis.asyncio for:
- Cache (7-day TTL): scraper results, LLM responses, research findings
- Staging: worker output staging area between Celery and consolidator
- Pub/Sub: ThinkingEvent broadcasting (integrated via redis_publisher.py)

Falls back to in-memory dict when Redis is unavailable — critical for
hackathon demo without Docker.

Usage:
    rc = get_redis_client()
    await rc.initialize()
    await rc.cache_set("scraper:mca21:CIN", data, ttl=604800)
    result = await rc.cache_get("scraper:mca21:CIN")
    await rc.stage_worker_output(session_id, worker_id, output_dict)
    outputs = await rc.get_staged_outputs(session_id)
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Default TTLs (seconds)
CACHE_TTL_SCRAPER = 604800      # 7 days
CACHE_TTL_LLM = 86400           # 24 hours
CACHE_TTL_RESEARCH = 604800     # 7 days
CACHE_TTL_STAGING = 3600        # 1 hour (worker output staging)


class InMemoryStore:
    """In-memory fallback mimicking Redis GET/SET/HSET/HGETALL with TTL support."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._ttls: Dict[str, float] = {}  # key → expiry timestamp
        self._hashes: Dict[str, Dict[str, str]] = {}

    def _is_expired(self, key: str) -> bool:
        if key in self._ttls and time.time() > self._ttls[key]:
            self._store.pop(key, None)
            self._ttls.pop(key, None)
            return True
        return False

    async def get(self, key: str) -> Optional[str]:
        if self._is_expired(key):
            return None
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self._store[key] = value
        if ex:
            self._ttls[key] = time.time() + ex
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                self._ttls.pop(k, None)
                count += 1
            if k in self._hashes:
                del self._hashes[k]
                count += 1
        return count

    async def exists(self, key: str) -> int:
        if self._is_expired(key):
            return 0
        return 1 if key in self._store else 0

    async def hset(self, name: str, key: str, value: str) -> int:
        if name not in self._hashes:
            self._hashes[name] = {}
        self._hashes[name][key] = value
        return 1

    async def hget(self, name: str, key: str) -> Optional[str]:
        return self._hashes.get(name, {}).get(key)

    async def hgetall(self, name: str) -> Dict[str, str]:
        return dict(self._hashes.get(name, {}))

    async def hdel(self, name: str, *keys: str) -> int:
        h = self._hashes.get(name, {})
        count = 0
        for k in keys:
            if k in h:
                del h[k]
                count += 1
        return count

    async def keys(self, pattern: str = "*") -> List[str]:
        """Simple pattern matching (only supports prefix* and *)."""
        if pattern == "*":
            return list(self._store.keys())
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._store if k.startswith(prefix)]
        return [k for k in self._store if k == pattern]

    async def ping(self) -> bool:
        return True

    async def close(self):
        pass

    async def flushdb(self):
        self._store.clear()
        self._ttls.clear()
        self._hashes.clear()


class RedisClient:
    """
    Async Redis client with in-memory fallback.

    Provides namespaced caching, worker output staging,
    and key management. Pub/Sub is handled separately
    by redis_publisher.py.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url
        self._client = None
        self._use_redis = False
        self._initialized = False

    async def initialize(self):
        """Connect to Redis or fall back to in-memory."""
        if self._initialized:
            return

        if self._redis_url:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                )
                await self._client.ping()
                self._use_redis = True
                logger.info("[Redis] Connected to Redis")
            except Exception as e:
                logger.warning(f"[Redis] Unavailable ({e}), using in-memory fallback")
                self._client = InMemoryStore()
                self._use_redis = False
        else:
            logger.info("[Redis] No URL configured, using in-memory fallback")
            self._client = InMemoryStore()
            self._use_redis = False

        self._initialized = True

    # ──────────────────────────────────────────────
    # Cache Operations
    # ──────────────────────────────────────────────

    async def cache_set(
        self, key: str, value: Any, ttl: int = CACHE_TTL_SCRAPER,
        namespace: str = "cache",
    ) -> bool:
        """Set a cache value with TTL. Value is JSON-serialized."""
        full_key = f"ic:{namespace}:{key}"
        serialized = json.dumps(value, default=str)
        await self._client.set(full_key, serialized, ex=ttl)
        return True

    async def cache_get(self, key: str, namespace: str = "cache") -> Optional[Any]:
        """Get a cached value. Returns None if expired or missing."""
        full_key = f"ic:{namespace}:{key}"
        raw = await self._client.get(full_key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    async def cache_delete(self, key: str, namespace: str = "cache") -> bool:
        """Delete a cached value."""
        full_key = f"ic:{namespace}:{key}"
        count = await self._client.delete(full_key)
        return count > 0

    async def cache_exists(self, key: str, namespace: str = "cache") -> bool:
        """Check if a cache key exists and is not expired."""
        full_key = f"ic:{namespace}:{key}"
        return (await self._client.exists(full_key)) > 0

    # ──────────────────────────────────────────────
    # Worker Output Staging
    # ──────────────────────────────────────────────

    async def stage_worker_output(
        self, session_id: str, worker_id: str, output: dict,
    ) -> bool:
        """
        Stage a worker's output for the consolidator to collect.

        Uses a Redis hash: staging:{session_id} → {worker_id: output_json}
        """
        hash_key = f"ic:staging:{session_id}"
        serialized = json.dumps(output, default=str)
        await self._client.hset(hash_key, worker_id, serialized)
        return True

    async def get_staged_output(
        self, session_id: str, worker_id: str,
    ) -> Optional[dict]:
        """Get a single worker's staged output."""
        hash_key = f"ic:staging:{session_id}"
        raw = await self._client.hget(hash_key, worker_id)
        if raw is None:
            return None
        return json.loads(raw)

    async def get_all_staged_outputs(self, session_id: str) -> Dict[str, dict]:
        """Get all staged worker outputs for a session."""
        hash_key = f"ic:staging:{session_id}"
        raw_dict = await self._client.hgetall(hash_key)
        return {
            worker_id: json.loads(output_json)
            for worker_id, output_json in raw_dict.items()
        }

    async def clear_staging(self, session_id: str) -> bool:
        """Clear all staged outputs for a session after consolidation."""
        hash_key = f"ic:staging:{session_id}"
        await self._client.delete(hash_key)
        return True

    async def get_staged_worker_count(self, session_id: str) -> int:
        """Count how many workers have staged output for a session."""
        hash_key = f"ic:staging:{session_id}"
        outputs = await self._client.hgetall(hash_key)
        return len(outputs)

    # ──────────────────────────────────────────────
    # Session State
    # ──────────────────────────────────────────────

    async def set_session_state(self, session_id: str, state: dict) -> bool:
        """Save pipeline state snapshot for a session."""
        return await self.cache_set(
            f"session:{session_id}", state,
            ttl=CACHE_TTL_STAGING, namespace="state",
        )

    async def get_session_state(self, session_id: str) -> Optional[dict]:
        """Get pipeline state snapshot for a session."""
        return await self.cache_get(f"session:{session_id}", namespace="state")

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            logger.info("[Redis] Connection closed")

    async def flush(self):
        """Flush all keys — for testing only."""
        if hasattr(self._client, "flushdb"):
            await self._client.flushdb()

    @property
    def backend(self) -> str:
        return "redis" if self._use_redis else "memory"

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# ── Singleton ──
_redis_client: Optional[RedisClient] = None


def get_redis_client(redis_url: Optional[str] = None) -> RedisClient:
    """Get or create the singleton RedisClient."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(redis_url)
    return _redis_client


def reset_redis_client():
    """Reset the singleton (for testing)."""
    global _redis_client
    _redis_client = None
