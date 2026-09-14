"""
WebSocket Router for Real-time Communication
Handles WebSocket connections and turn-based message flow
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and broadcasting."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_locks: Set[str] = set()

    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"Session {session_id} connected")

    def disconnect(self, session_id: str):
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        self.session_locks.discard(session_id)
        logger.info(f"Session {session_id} disconnected")

    async def send_personal_message(self, message: dict, session_id: str):
        """Send a message to a specific session."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected sessions."""
        for session_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {session_id}: {e}")


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Main WebSocket endpoint for real-time communication.
    Handles turn-based message flow with Redis locking.
    """
    await manager.connect(websocket, session_id)

    try:
        while True:
            # Wait for incoming message
            data = await websocket.receive_text()
            message = json.loads(data)

            # Basic message validation
            if "type" not in message:
                await manager.send_personal_message(
                    {"type": "error", "message": "Invalid message format"},
                    session_id
                )
                continue

            # Handle different message types
            if message["type"] == "USER_MESSAGE":
                await handle_user_message(session_id, message)
            elif message["type"] == "PING":
                await manager.send_personal_message(
                    {"type": "PONG", "timestamp": message.get("timestamp")},
                    session_id
                )
            else:
                logger.warning(f"Unknown message type: {message['type']}")

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(session_id)


async def handle_user_message(session_id: str, message: dict):
    """
    Handle incoming user messages.
    This is where we'll integrate with the agent pipeline later.
    """
    # TODO: Implement turn locking with Redis
    # TODO: Load PeerRingState from Redis
    # TODO: Route through agent pipeline
    # TODO: Apply governance checks
    # TODO: Stream response back to client

    # For now, send a simple echo response
    response = {
        "type": "AGENT_RESPONSE",
        "session_id": session_id,
        "agent_id": "mock-agent",
        "content": f"Echo: {message.get('content', '')}",
        "timestamp": message.get("timestamp"),
        "metadata": {
            "foundation_layer": "active",
            "mock_response": True
        }
    }

    await manager.send_personal_message(response, session_id)