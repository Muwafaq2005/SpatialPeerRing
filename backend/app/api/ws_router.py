"""
WebSocket Router for Real-time Communication
Handles WebSocket connections and Redis-coordinated turn-based message flow
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Set, Optional
import json
import asyncio
import logging
import uuid
from datetime import datetime

from app.config import settings
from app.state.redis_mutex import redis_mutex, TurnLockTimeoutError, RedisConnectionError
from app.state.pydantic_state import PeerRingState, DialogueMessage, MessageRole
from app.contracts.mock_registry import MockAgentRegistry

logger = logging.getLogger(__name__)

router = APIRouter()


class WebSocketConnectionManager:
    """
    Enhanced WebSocket connection manager with Redis turn coordination.

    Provides:
    - Redis-backed turn locking for multi-user coordination
    - State persistence across sessions
    - Real-time message broadcasting
    - Connection lifecycle management
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_owners: Dict[str, str] = {}  # session_id -> connection_id
        self.mock_registry = MockAgentRegistry()

    async def connect(self, websocket: WebSocket, session_id: str) -> str:
        """
        Accept WebSocket connection and register with Redis coordination.

        Args:
            websocket: WebSocket connection
            session_id: Session identifier

        Returns:
            Connection ID for this WebSocket
        """
        await websocket.accept()

        # Generate unique connection ID
        connection_id = f"ws_{session_id}_{str(uuid.uuid4())[:8]}"

        self.active_connections[session_id] = websocket
        self.connection_owners[session_id] = connection_id

        # Initialize Redis connection if needed
        if not redis_mutex._connected:
            try:
                await redis_mutex.connect()
            except RedisConnectionError as e:
                logger.error(f"Redis connection failed for session {session_id}: {e}")
                await websocket.close(code=1011, reason="Redis connection failed")
                return connection_id

        # Load or create session state
        try:
            state = await redis_mutex.load_state(session_id)
            if not state:
                # Create new session
                state = PeerRingState(session_id=session_id)
                await redis_mutex.save_state(state)
                logger.info(f"📝 New session created: {session_id}")
            else:
                logger.info(f"📂 Session restored: {session_id}")

            # Send connection confirmation
            await self.send_personal_message({
                "type": "CONNECTION_ESTABLISHED",
                "session_id": session_id,
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat(),
                "state_summary": {
                    "messages": len(state.messages),
                    "turn_count": state.turn_count,
                    "current_concept": state.current_concept
                }
            }, session_id)

        except Exception as e:
            logger.error(f"Session initialization failed for {session_id}: {e}")
            await websocket.close(code=1011, reason="Session initialization failed")

        logger.info(f"🔗 WebSocket connected: session={session_id}, connection={connection_id}")
        return connection_id

    async def disconnect(self, session_id: str):
        """
        Handle WebSocket disconnection and cleanup.

        Args:
            session_id: Session identifier
        """
        if session_id in self.active_connections:
            del self.active_connections[session_id]

        # Release any turn locks owned by this connection
        if session_id in self.connection_owners:
            connection_id = self.connection_owners[session_id]
            try:
                await redis_mutex.release_turn_lock(session_id, connection_id)
            except Exception as e:
                logger.warning(f"Lock release on disconnect failed: {e}")

            del self.connection_owners[session_id]

        logger.info(f"🔌 WebSocket disconnected: session={session_id}")

    async def send_personal_message(self, message: dict, session_id: str):
        """Send message to specific session."""
        if session_id in self.active_connections:
            try:
                websocket = self.active_connections[session_id]
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send message to {session_id}: {e}")
                # Connection might be dead, clean it up
                await self.disconnect(session_id)

    async def broadcast_to_session_group(self, message: dict, exclude_session: Optional[str] = None):
        """Broadcast message to all connected sessions (except excluded)."""
        for session_id, websocket in self.active_connections.items():
            if session_id != exclude_session:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Broadcast failed to {session_id}: {e}")


# Global connection manager instance
connection_manager = WebSocketConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Enhanced WebSocket endpoint with Redis turn coordination.
    Handles real-time communication with atomic turn locking.
    """
    connection_id = await connection_manager.connect(websocket, session_id)

    try:
        while True:
            # Wait for incoming message
            data = await websocket.receive_text()
            message = json.loads(data)

            # Message validation
            if "type" not in message:
                await connection_manager.send_personal_message(
                    {
                        "type": "ERROR",
                        "message": "Invalid message format - missing 'type' field",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    session_id
                )
                continue

            # Handle different message types
            message_type = message["type"]

            if message_type == "USER_MESSAGE":
                await handle_user_message(session_id, connection_id, message)
            elif message_type == "PING":
                await handle_ping(session_id, message)
            elif message_type == "GET_STATE":
                await handle_get_state(session_id)
            elif message_type == "RELEASE_LOCK":
                await handle_release_lock(session_id, connection_id)
            else:
                logger.warning(f"Unknown message type: {message_type} from session {session_id}")
                await connection_manager.send_personal_message(
                    {
                        "type": "ERROR",
                        "message": f"Unknown message type: {message_type}",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    session_id
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally: {session_id}")
        await connection_manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        await connection_manager.disconnect(session_id)


async def handle_user_message(session_id: str, connection_id: str, message: dict):
    """
    Handle user messages with Redis turn coordination.

    Implements the complete turn flow:
    1. Acquire turn lock
    2. Load state from Redis
    3. Process through agent pipeline (mock for now)
    4. Save updated state
    5. Release turn lock
    6. Stream response to client
    """
    start_time = datetime.utcnow()

    try:
        # Step 1: Acquire turn lock
        lock_acquired = await redis_mutex.acquire_turn_lock(session_id, connection_id)

        if not lock_acquired:
            # Turn is locked by another process
            lock_status = await redis_mutex.get_lock_status(session_id)
            await connection_manager.send_personal_message(
                {
                    "type": "TURN_LOCKED",
                    "message": "Another user is currently taking a turn",
                    "lock_owner": lock_status.lock_owner,
                    "retry_after_ms": 2000,
                    "timestamp": datetime.utcnow().isoformat()
                },
                session_id
            )
            return

        # Step 2: Load current state
        state = await redis_mutex.load_state(session_id)
        if not state:
            # This shouldn't happen if connection was established properly
            logger.error(f"No state found for session {session_id} during message handling")
            await redis_mutex.release_turn_lock(session_id, connection_id)
            return

        # Step 3: Add user message to state
        user_content = message.get("content", "")
        if not user_content.strip():
            await connection_manager.send_personal_message(
                {
                    "type": "ERROR",
                    "message": "Empty message content",
                    "timestamp": datetime.utcnow().isoformat()
                },
                session_id
            )
            await redis_mutex.release_turn_lock(session_id, connection_id)
            return

        user_msg = DialogueMessage(
            role=MessageRole.USER,
            content=user_content,
            metadata=message.get("metadata", {})
        )
        state.add_message(user_msg)

        # Step 4: Process through agent pipeline (using mock for now)
        try:
            # Send processing notification
            await connection_manager.send_personal_message(
                {
                    "type": "PROCESSING",
                    "message": "Processing your message...",
                    "timestamp": datetime.utcnow().isoformat()
                },
                session_id
            )

            # Run through mock agent pipeline
            turn_result = await connection_manager.mock_registry.run_mock_turn(
                state, user_content
            )

            # Step 5: Save updated state to Redis
            await redis_mutex.save_state(state)

            # Step 6: Stream response back to client
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            response = {
                "type": "AGENT_RESPONSE",
                "session_id": session_id,
                "agent_id": turn_result["winner"],
                "content": turn_result["response"].content,
                "think_block": turn_result["response"].think_block,
                "blackboard_patch": turn_result["response"].blackboard_patch,
                "governance": {
                    judge_type: {
                        "verdict": verdict.verdict,
                        "confidence": verdict.confidence,
                        "reasoning": verdict.reasoning
                    }
                    for judge_type, verdict in turn_result["governance"].items()
                },
                "metadata": {
                    "candidates": turn_result["candidates"],
                    "passed_governance": turn_result["passed_governance"],
                    "processing_time_ms": round(processing_time, 2),
                    "turn_count": state.turn_count,
                    "mock_response": turn_result["mock_turn"]
                },
                "timestamp": datetime.utcnow().isoformat()
            }

            await connection_manager.send_personal_message(response, session_id)

            logger.info(
                f"✅ Turn completed: session={session_id}, "
                f"winner={turn_result['winner']}, "
                f"processing_time={processing_time:.1f}ms"
            )

        except Exception as e:
            logger.error(f"Agent pipeline error for session {session_id}: {e}")
            await connection_manager.send_personal_message(
                {
                    "type": "ERROR",
                    "message": "Agent processing failed",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                },
                session_id
            )

    except Exception as e:
        logger.error(f"Turn handling error for session {session_id}: {e}")
        await connection_manager.send_personal_message(
            {
                "type": "ERROR",
                "message": "Turn processing failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            session_id
        )

    finally:
        # Always release the turn lock
        try:
            await redis_mutex.release_turn_lock(session_id, connection_id)
        except Exception as e:
            logger.error(f"Lock release error for session {session_id}: {e}")


async def handle_ping(session_id: str, message: dict):
    """Handle ping/pong for connection keepalive."""
    await connection_manager.send_personal_message(
        {
            "type": "PONG",
            "timestamp": datetime.utcnow().isoformat(),
            "echo": message.get("timestamp")
        },
        session_id
    )


async def handle_get_state(session_id: str):
    """Handle state information request."""
    try:
        state = await redis_mutex.load_state(session_id)
        lock_status = await redis_mutex.get_lock_status(session_id)

        if state:
            response = {
                "type": "STATE_INFO",
                "session_id": session_id,
                "state": {
                    "messages": len(state.messages),
                    "turn_count": state.turn_count,
                    "current_concept": state.current_concept,
                    "struggle_score": state.policy.struggle_score,
                    "assistance_level": state.policy.assistance_level.current_level,
                    "recovery_state": state.policy.recovery_state.value
                },
                "lock_status": {
                    "locked": lock_status.locked,
                    "lock_owner": lock_status.lock_owner,
                    "ttl_seconds": lock_status.lock_ttl_seconds
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            response = {
                "type": "STATE_INFO",
                "session_id": session_id,
                "state": None,
                "message": "No state found for session",
                "timestamp": datetime.utcnow().isoformat()
            }

        await connection_manager.send_personal_message(response, session_id)

    except Exception as e:
        logger.error(f"Get state error for session {session_id}: {e}")
        await connection_manager.send_personal_message(
            {
                "type": "ERROR",
                "message": "Failed to retrieve state",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            session_id
        )


async def handle_release_lock(session_id: str, connection_id: str):
    """Handle manual lock release request."""
    try:
        released = await redis_mutex.release_turn_lock(session_id, connection_id)
        await connection_manager.send_personal_message(
            {
                "type": "LOCK_RELEASED" if released else "LOCK_NOT_OWNED",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            session_id
        )
    except Exception as e:
        logger.error(f"Lock release error for session {session_id}: {e}")
        await connection_manager.send_personal_message(
            {
                "type": "ERROR",
                "message": "Lock release failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            },
            session_id
        )