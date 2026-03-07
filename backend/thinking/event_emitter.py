"""
Intelli-Credit — ThinkingEvent Emitter

The primary interface for agent nodes to emit ThinkingEvents.
Every agent creates a ThinkingEventEmitter and calls emit() for
each significant reasoning step. Events flow through:

    Agent → ThinkingEventEmitter → RedisPublisher → WebSocket → UI Chatbot

Usage in a LangGraph node:
    emitter = ThinkingEventEmitter(session_id, "Agent 0.5 — The Consolidator")
    await emitter.emit(EventType.READ, "Reading annual report...")
    await emitter.emit(EventType.FOUND, "Revenue FY2023: ₹142.3 crores", 
                       source_document="annual_report.pdf", source_page=42)
"""

import logging
from typing import Optional, Dict, Any, List

from backend.models.schemas import ThinkingEvent, EventType
from backend.thinking.redis_publisher import get_publisher
from backend.thinking.event_formatter import (
    enrich_event_dict,
    format_source_citation,
)

logger = logging.getLogger(__name__)


class ThinkingEventEmitter:
    """
    Emitter for ThinkingEvents — used by every agent node.

    Creates properly structured ThinkingEvent objects and publishes
    them to the message bus (Redis Pub/Sub or in-memory fallback).

    Each instance is bound to a session_id and agent_name.
    """

    def __init__(self, session_id: str, agent_name: str):
        self.session_id = session_id
        self.agent_name = agent_name
        self._publisher = get_publisher()
        self._event_count = 0

    async def emit(
        self,
        event_type: EventType,
        message: str,
        source_document: Optional[str] = None,
        source_page: Optional[int] = None,
        source_excerpt: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ThinkingEvent:
        """
        Emit a ThinkingEvent.

        Args:
            event_type: Type of reasoning event (READ, FOUND, FLAGGED, etc.)
            message: Human-readable reasoning step
            source_document: Optional source document filename
            source_page: Optional page number in source document
            source_excerpt: Optional text excerpt from source
            confidence: Optional confidence score (0.0–1.0)
            metadata: Optional additional metadata dict

        Returns:
            The created ThinkingEvent
        """
        # Build the event
        event = ThinkingEvent(
            session_id=self.session_id,
            agent=self.agent_name,
            event_type=event_type,
            message=message,
            source_document=source_document,
            source_page=source_page,
            source_excerpt=source_excerpt,
            confidence=confidence,
            metadata=metadata,
        )

        # Serialize for bus
        event_dict = event.model_dump(mode="json")

        # Enrich with display metadata (icon, color, label)
        enriched = enrich_event_dict(event_dict)

        # Publish
        try:
            await self._publisher.publish(self.session_id, enriched)
        except Exception as e:
            logger.error(f"[ThinkingEmitter] Failed to publish event: {e}")

        self._event_count += 1

        logger.debug(
            f"[{self.agent_name}] {event_type.value}: {message}"
        )

        return event

    async def read(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a READ event."""
        return await self.emit(EventType.READ, message, **kwargs)

    async def found(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a FOUND event."""
        return await self.emit(EventType.FOUND, message, **kwargs)

    async def computed(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a COMPUTED event."""
        return await self.emit(EventType.COMPUTED, message, **kwargs)

    async def accepted(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a ACCEPTED event."""
        return await self.emit(EventType.ACCEPTED, message, **kwargs)

    async def rejected(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a REJECTED event."""
        return await self.emit(EventType.REJECTED, message, **kwargs)

    async def flagged(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a FLAGGED event."""
        return await self.emit(EventType.FLAGGED, message, **kwargs)

    async def critical(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a CRITICAL event."""
        return await self.emit(EventType.CRITICAL, message, **kwargs)

    async def connecting(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a CONNECTING event."""
        return await self.emit(EventType.CONNECTING, message, **kwargs)

    async def concluding(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a CONCLUDING event."""
        return await self.emit(EventType.CONCLUDING, message, **kwargs)

    async def questioning(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a QUESTIONING event."""
        return await self.emit(EventType.QUESTIONING, message, **kwargs)

    async def decided(self, message: str, **kwargs) -> ThinkingEvent:
        """Shorthand for emitting a DECIDED event."""
        return await self.emit(EventType.DECIDED, message, **kwargs)

    @property
    def event_count(self) -> int:
        """Number of events emitted by this emitter."""
        return self._event_count

    def get_event_log(self) -> List[dict]:
        """Get all events emitted for this session (from the publisher's log)."""
        return self._publisher.get_event_log(self.session_id)
