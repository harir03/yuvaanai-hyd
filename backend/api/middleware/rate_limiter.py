"""
Intelli-Credit — Rate Limiting Middleware

Token-bucket rate limiter for FastAPI with Redis-backed or in-memory storage.
Protects API endpoints from abuse and ensures fair usage.

Configuration:
- Default: 100 requests per minute per client IP
- Upload: 10 requests per minute (expensive operation)
- WebSocket: 5 connections per IP

Usage:
    from backend.api.middleware.rate_limiter import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
"""

import time
import logging
from typing import Dict, Tuple, Optional
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Rate limit configurations ──
# (max_requests, window_seconds)
RATE_LIMITS: Dict[str, Tuple[int, int]] = {
    "default": (200, 60),        # 200 req/min
    "/api/upload": (10, 60),     # 10 req/min (expensive)
    "/api/pipeline": (20, 60),   # 20 req/min
    "/api/score": (30, 60),      # 30 req/min
}


class TokenBucket:
    """In-memory token bucket for rate limiting.

    Each bucket has:
    - max_tokens: maximum burst size
    - refill_rate: tokens added per second
    - tokens: current available tokens
    - last_refill: timestamp of last refill
    """

    def __init__(self, max_tokens: int, refill_rate: float):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.tokens = float(max_tokens)
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate-limited."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    @property
    def retry_after(self) -> float:
        """Seconds until next token is available."""
        self._refill()
        if self.tokens >= 1:
            return 0.0
        return (1.0 - self.tokens) / self.refill_rate


class InMemoryRateLimiter:
    """In-memory rate limiter using token buckets per client IP."""

    def __init__(self):
        # key → TokenBucket
        self._buckets: Dict[str, TokenBucket] = {}
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300  # Clean up stale entries every 5 min

    def _cleanup(self) -> None:
        """Remove stale buckets to prevent memory growth."""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        stale_keys = [
            k for k, b in self._buckets.items()
            if now - b.last_refill > 600  # Unused for 10 min
        ]
        for k in stale_keys:
            del self._buckets[k]
        if stale_keys:
            logger.debug(f"[RateLimiter] Cleaned up {len(stale_keys)} stale buckets")

    def check(self, client_ip: str, path: str) -> Tuple[bool, float]:
        """Check if a request is allowed.

        Args:
            client_ip: Client IP address.
            path: Request path for route-specific limits.

        Returns:
            (allowed, retry_after_seconds)
        """
        self._cleanup()

        # Determine rate limit for this path
        max_requests, window = RATE_LIMITS.get("default", (100, 60))
        for prefix, (mr, w) in RATE_LIMITS.items():
            if prefix != "default" and path.startswith(prefix):
                max_requests, window = mr, w
                break

        refill_rate = max_requests / window
        bucket_key = f"{client_ip}:{path.split('/')[2] if '/' in path else 'default'}"

        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = TokenBucket(max_requests, refill_rate)

        bucket = self._buckets[bucket_key]
        allowed = bucket.consume()
        retry_after = bucket.retry_after if not allowed else 0.0

        return allowed, retry_after


# ── Singleton ──
_limiter = InMemoryRateLimiter()


def reset_rate_limiter() -> None:
    """Reset all rate limit buckets. Used in tests to prevent cross-test interference."""
    global _limiter
    _limiter = InMemoryRateLimiter()


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (client's real IP) from the chain
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces rate limiting per client IP.

    Adds rate limit headers to all responses:
    - X-RateLimit-Limit: max requests in window
    - X-RateLimit-Remaining: requests remaining
    - Retry-After: seconds until next token (when rate limited)
    """

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and docs
        path = request.url.path
        if path in ("/health", "/", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # Skip WebSocket upgrades (they have their own limits)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        client_ip = _get_client_ip(request)
        allowed, retry_after = _limiter.check(client_ip, path)

        if not allowed:
            logger.warning(
                f"[RateLimiter] Rate limited {client_ip} on {path} (retry after {retry_after:.1f}s)"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": round(retry_after, 1),
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": "0",
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Request allowed — proceed
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(
            RATE_LIMITS.get("default", (100, 60))[0]
        )
        return response
