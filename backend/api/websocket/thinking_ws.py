"""
Intelli-Credit — Thinking WebSocket Handler

Streams ThinkingEvents from the message bus to connected UI clients.
One WebSocket per session_id. Events are JSON-serialized ThinkingEvent models.

Flow: Agent → ThinkingEventEmitter → RedisPublisher → this handler → UI
"""

import json
import logging
import asyncio
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

from backend.thinking.redis_publisher import get_publisher
from backend.thinking.event_formatter import enrich_event_dict

logger = logging.getLogger(__name__)

# Active WebSocket connections: session_id → set of WebSocket connections
_thinking_connections: Dict[str, Set[WebSocket]] = {}


async def thinking_ws_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for /ws/thinking/{session_id}.

    Accepts the connection, subscribes to the session's event bus,
    replays any missed events, and streams new events until disconnect.
    """
    await websocket.accept()
    logger.info(f"[ThinkingWS] Client connected for session {session_id}")

    # Register connection
    if session_id not in _thinking_connections:
        _thinking_connections[session_id] = set()
    _thinking_connections[session_id].add(websocket)

    publisher = get_publisher()

    # Replay missed events (for reconnection)
    event_log = publisher.get_event_log(session_id)
    if event_log:
        logger.info(f"[ThinkingWS] Replaying {len(event_log)} events for session {session_id}")
        for event in event_log:
            try:
                await websocket.send_text(json.dumps(event, default=str))
            except Exception:
                break

    # Subscribe to new events via in-memory bus
    async def on_event(event: dict):
        """Callback: forward event from bus to this WebSocket."""
        try:
            await websocket.send_text(json.dumps(event, default=str))
        except Exception:
            pass  # Will be cleaned up on disconnect

    await publisher.subscribe(session_id, on_event)

    try:
        # Keep connection alive — wait for client messages
        while True:
            data = await websocket.receive_text()
            # Client can send filter preferences or pings
            logger.debug(f"[ThinkingWS] Received from client: {data[:100]}")
    except WebSocketDisconnect:
        logger.info(f"[ThinkingWS] Client disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"[ThinkingWS] Error for session {session_id}: {e}")
    finally:
        # Clean up subscription
        await publisher.unsubscribe(session_id, on_event)
        # Clean up connection registry
        _thinking_connections.get(session_id, set()).discard(websocket)
        if session_id in _thinking_connections and not _thinking_connections[session_id]:
            del _thinking_connections[session_id]


async def broadcast_thinking_event(session_id: str, event_data: dict):
    """
    Broadcast a ThinkingEvent to all connected clients for a session.

    This is the LEGACY direct-push path. Prefer using ThinkingEventEmitter
    which goes through the bus. Kept for backward compatibility and testing.
    """
    connections = _thinking_connections.get(session_id, set())
    if not connections:
        return

    message = json.dumps(event_data, default=str)
    disconnected = set()

    for ws in connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)

    # Clean up disconnected
    for ws in disconnected:
        connections.discard(ws)


def get_active_sessions() -> list:
    """Return list of session_ids with active WebSocket connections."""
    return list(_thinking_connections.keys())


def get_connection_count(session_id: str) -> int:
    """Return number of active connections for a session."""
    return len(_thinking_connections.get(session_id, set()))
