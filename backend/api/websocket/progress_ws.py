"""
Intelli-Credit — Progress WebSocket Handler

Streams pipeline progress updates to connected UI clients.
Events include stage transitions and worker status updates.
"""

import json
import logging
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Active connections: session_id → set of WebSocket connections
_progress_connections: Dict[str, Set[WebSocket]] = {}


async def progress_ws_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for /ws/progress/{session_id}.

    Streams pipeline stage transitions and worker status updates.
    """
    await websocket.accept()
    logger.info(f"[ProgressWS] Client connected for session {session_id}")

    if session_id not in _progress_connections:
        _progress_connections[session_id] = set()
    _progress_connections[session_id].add(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"[ProgressWS] Received from client: {data[:100]}")
    except WebSocketDisconnect:
        logger.info(f"[ProgressWS] Client disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"[ProgressWS] Error for session {session_id}: {e}")
    finally:
        _progress_connections.get(session_id, set()).discard(websocket)
        if session_id in _progress_connections and not _progress_connections[session_id]:
            del _progress_connections[session_id]


async def broadcast_progress_update(session_id: str, update_data: dict):
    """Broadcast a progress update to all connected clients for a session."""
    connections = _progress_connections.get(session_id, set())
    if not connections:
        return

    message = json.dumps(update_data, default=str)
    disconnected = set()

    for ws in connections:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)

    for ws in disconnected:
        connections.discard(ws)
