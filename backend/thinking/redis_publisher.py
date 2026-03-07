"""
Intelli-Credit — Redis Pub/Sub Publisher

Publishes ThinkingEvents to Redis Pub/Sub channels.
Falls back to in-memory broadcast when Redis is unavailable.

Channel naming: thinking:{session_id}
"""

import json
import asyncio
import logging
from typing import Optional, Dict, List, Callable, Awaitable, Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# In-Memory Fallback (no Redis required)
# ──────────────────────────────────────────────

# Subscribers: channel_name → list of async callback functions
_memory_subscribers: Dict[str, List[Callable[[dict], Awaitable[None]]]] = {}

# Event log: session_id → list of events (for replay on reconnect)
_event_log: Dict[str, List[dict]] = {}

# Max events to keep per session (prevent memory leak)
MAX_EVENTS_PER_SESSION = 5000


class RedisPublisher:
    """
    Publishes ThinkingEvents to a message bus.

    Uses Redis Pub/Sub when available, falls back to in-memory
    pub/sub for development/demo without Redis.

    Usage:
        publisher = RedisPublisher()
        await publisher.publish("session-123", event_dict)
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url
        self._redis = None
        self._use_redis = False
        self._initialized = False

    async def initialize(self):
        """Try to connect to Redis. Fall back to in-memory if unavailable."""
        if self._initialized:
            return

        if self._redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                )
                # Test connection
                await self._redis.ping()
                self._use_redis = True
                logger.info("[RedisPublisher] Connected to Redis Pub/Sub")
            except Exception as e:
                logger.warning(f"[RedisPublisher] Redis unavailable ({e}), using in-memory fallback")
                self._redis = None
                self._use_redis = False
        else:
            logger.info("[RedisPublisher] No Redis URL configured, using in-memory fallback")

        self._initialized = True

    async def publish(self, session_id: str, event: dict) -> int:
        """
        Publish a ThinkingEvent to the bus.

        Args:
            session_id: Target session
            event: Serialized ThinkingEvent dict

        Returns:
            Number of subscribers that received the event
        """
        if not self._initialized:
            await self.initialize()

        channel = f"thinking:{session_id}"

        # Always log to memory (for replay)
        if session_id not in _event_log:
            _event_log[session_id] = []
        _event_log[session_id].append(event)
        # Trim if too many
        if len(_event_log[session_id]) > MAX_EVENTS_PER_SESSION:
            _event_log[session_id] = _event_log[session_id][-MAX_EVENTS_PER_SESSION:]

        if self._use_redis and self._redis:
            try:
                message = json.dumps(event, default=str)
                receivers = await self._redis.publish(channel, message)
                return receivers
            except Exception as e:
                logger.error(f"[RedisPublisher] Publish failed: {e}, falling back to memory")
                self._use_redis = False

        # In-memory fallback
        subscribers = _memory_subscribers.get(channel, [])
        for callback in subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"[RedisPublisher] Memory subscriber error: {e}")

        return len(subscribers)

    async def subscribe(
        self,
        session_id: str,
        callback: Callable[[dict], Awaitable[None]],
    ):
        """
        Subscribe to ThinkingEvents for a session (in-memory mode).

        For Redis mode, the WebSocket handler subscribes via Redis directly.
        This is used for the in-memory fallback.
        """
        channel = f"thinking:{session_id}"
        if channel not in _memory_subscribers:
            _memory_subscribers[channel] = []
        _memory_subscribers[channel].append(callback)
        logger.debug(f"[RedisPublisher] Subscriber added for {channel}")

    async def unsubscribe(
        self,
        session_id: str,
        callback: Callable[[dict], Awaitable[None]],
    ):
        """Remove a subscriber."""
        channel = f"thinking:{session_id}"
        subs = _memory_subscribers.get(channel, [])
        if callback in subs:
            subs.remove(callback)
        if not subs and channel in _memory_subscribers:
            del _memory_subscribers[channel]

    def get_event_log(self, session_id: str) -> List[dict]:
        """Get all stored events for a session (for replay on reconnect)."""
        return _event_log.get(session_id, [])

    def clear_event_log(self, session_id: str):
        """Clear event log for a session."""
        _event_log.pop(session_id, None)

    async def close(self):
        """Close Redis connection if open."""
        if self._redis:
            await self._redis.close()
            logger.info("[RedisPublisher] Redis connection closed")


# ── Singleton ──
_publisher: Optional[RedisPublisher] = None


def get_publisher(redis_url: Optional[str] = None) -> RedisPublisher:
    """Get or create the singleton RedisPublisher."""
    global _publisher
    if _publisher is None:
        _publisher = RedisPublisher(redis_url)
    return _publisher


def reset_publisher():
    """Reset the singleton (for testing)."""
    global _publisher
    _publisher = None
    _memory_subscribers.clear()
    _event_log.clear()
