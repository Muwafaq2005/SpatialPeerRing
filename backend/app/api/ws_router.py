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
from app.telemetry.prism_client import prism_client
from app.state.pydantic_state import PeerRingState, DialogueMessage, MessageRole
from app.contracts.mock_registry import MockAgentRegistry
from app.agents.orchestrator import PedagogicalOrchestrator
from app.governance import LeakJudge, HelpJudge, PolicyRewriter, AdversarialClassifier

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
        self.orchestrator = PedagogicalOrchestrator()

        # Initialize governance judges and rewriter
        self.leak_judge = LeakJudge()
        self.help_judge = HelpJudge()
        self.policy_rewriter = PolicyRewriter(max_retries=settings.POLICY_REWRITER_MAX_RETRIES)
        self.adversarial_classifier = AdversarialClassifier()

        logger.info("🛡️ WebSocket manager initialized with leak judge, help judge, policy rewriter, and adversarial classifier")


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
        self.active_connections.pop(session_id, None)

        # Release any turn locks owned by this connection
        connection_id = self.connection_owners.pop(session_id, None)
        if connection_id:
            try:
                await redis_mutex.release_turn_lock(session_id, connection_id)
            except Exception as e:
                logger.warning(f"Lock release on disconnect failed: {e}")

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

        # GOVERNANCE: Pre-routing adversarial check
        adv_result = connection_manager.adversarial_classifier.evaluate(user_content)
        if adv_result.is_adversarial:
            logger.warning(f"⚠️ Adversarial intent detected ({adv_result.intent.value}) for session {session_id}. Enabling strict mode.")
            state.policy.strict_mode = True

        # Step 4: Process through agent pipeline (using mock for now)
        try:
            with prism_client.ambient_session(session_id):
                # Send processing notification
                await connection_manager.send_personal_message(
                    {
                        "type": "PROCESSING",
                        "message": "Processing your message...",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    session_id
                )

                # Run through live agent orchestrator pipeline
                agent_resp, orchestrator_meta = await connection_manager.orchestrator.orchestrate_turn(
                    state, user_content
                )
                turn_result = {
                    "response": agent_resp,
                    "winner": agent_resp.agent_id,
                    "orchestration": orchestrator_meta
                }

                # GOVERNANCE: Apply leak judge evaluation on agent response
                governance_results = {}

                # Real leak judge evaluation
                if settings.LEAK_JUDGE_ENABLED:
                    try:
                        leak_verdict = await connection_manager.leak_judge.evaluate(
                            text=turn_result["response"].content,
                            patch=turn_result["response"].blackboard_patch,
                            state=state
                        )
                        governance_results["leak"] = leak_verdict

                        # Log governance decision
                        logger.info(
                            f"🛡️ Leak judge: session={session_id}, "
                            f"verdict={'PASS' if leak_verdict.verdict else 'FAIL'}, "
                            f"confidence={leak_verdict.confidence:.2f}, "
                            f"time={leak_verdict.evaluation_time_ms}ms"
                        )

                    except Exception as e:
                        logger.error(f"Leak judge error for session {session_id}: {e}")
                        # Use mock leak judge as fallback
                        governance_results["leak"] = turn_result["governance"]["leak"]
                else:
                    # Use mock governance when disabled
                    governance_results["leak"] = turn_result["governance"]["leak"]

                # Help judge evaluation
                if settings.HELP_JUDGE_ENABLED:
                    try:
                        help_verdict = await connection_manager.help_judge.evaluate(
                            text=turn_result["response"].content,
                            patch=turn_result["response"].blackboard_patch,
                            state=state
                        )
                        governance_results["help"] = help_verdict

                        logger.info(
                            f"🤝 Help judge: session={session_id}, "
                            f"verdict={'PASS' if help_verdict.verdict else 'FAIL'}, "
                            f"confidence={help_verdict.confidence:.2f}, "
                            f"time={help_verdict.evaluation_time_ms}ms"
                        )
                    except Exception as e:
                        logger.error(f"Help judge error for session {session_id}: {e}")
                        governance_results["help"] = turn_result["governance"]["help"]
                else:
                    governance_results["help"] = turn_result["governance"]["help"]

                # Check if response passes all governance
                all_pass = all(verdict.verdict for verdict in governance_results.values())

                # POLICY REWRITER: Attempt automated Socratic rewrite on failure
                if not all_pass and settings.POLICY_REWRITER_ENABLED:
                    logger.info(f"🔄 PolicyRewriter triggered for session {session_id}")
                    rewritten_response, new_governance, rewrite_passed = await connection_manager.policy_rewriter.rewrite_turn(
                        candidate_response=turn_result["response"],
                        governance_results=governance_results,
                        state=state,
                        leak_judge=connection_manager.leak_judge,
                        help_judge=connection_manager.help_judge
                    )
                    if rewrite_passed:
                        turn_result["response"] = rewritten_response
                        governance_results = new_governance
                        all_pass = True
                        logger.info(f"✅ PolicyRewriter produced compliant response for session {session_id}")

                # If governance still fails after rewriting, send rejection notice
                if not all_pass:
                    failed_judges = [
                        judge_type for judge_type, verdict in governance_results.items()
                        if not verdict.verdict
                    ]

                    await connection_manager.send_personal_message(
                        {
                            "type": "GOVERNANCE_REJECTION",
                            "message": "Response rejected by governance system",
                            "failed_judges": failed_judges,
                            "governance_results": {
                                judge_type: {
                                    "verdict": verdict.verdict,
                                    "confidence": verdict.confidence,
                                    "reasoning": verdict.reasoning,
                                    "suggested_fixes": verdict.suggested_fixes
                                }
                                for judge_type, verdict in governance_results.items()
                            },
                            "timestamp": datetime.utcnow().isoformat()
                        },
                        session_id
                    )

                    logger.warning(
                        f"🚫 Governance rejection: session={session_id}, "
                        f"failed_judges={failed_judges}"
                    )

                    # Don't save state or add response to history for failed governance
                    return

            
                # Record manual PRISM traces for agent turn
                prism_client.trace_agent_turn_async(
                    session_id=session_id,
                    agent_id=turn_result["response"].agent_id,
                    user_input=user_content,
                    response_text=turn_result["response"].content,
                    latency_ms=turn_result["response"].generation_time_ms or 150,
                    metadata={
                        "has_blackboard_patch": turn_result["response"].blackboard_patch is not None,
                        "confidence": turn_result["response"].confidence,
                        "struggle_score": state.policy.struggle_score,
                        "assistance_level": state.policy.assistance_level.current_level,
                    }
                )

                # Record manual PRISM traces for governance judges
                for jtype, verdict in governance_results.items():
                    prism_client.trace_judge_eval_async(
                        session_id=session_id,
                        judge_type=jtype,
                        evaluated_text=turn_result["response"].content,
                        verdict=verdict,
                        latency_ms=verdict.evaluation_time_ms or 50
                    )
    # Step 5: Save updated state to Redis (only if governance passes)
                await redis_mutex.save_state(state)

                # Step 6: Stream response back to client
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                response = {
                    "type": "AGENT_RESPONSE",
                    "session_id": session_id,
                    "agent_id": turn_result["response"].agent_id,
                    "active_speaker": turn_result["winner"],
                    "content": turn_result["response"].content,
                    "think_block": turn_result["response"].think_block,
                    "blackboard_patch": turn_result["response"].blackboard_patch,
                    "governance_flags": {
                        jtype: verdict.verdict for jtype, verdict in governance_results.items()
                    },
                    "policy_state": {
                        "assistance_level": state.policy.assistance_level.current_level,
                        "assistance_level_name": state.policy.assistance_level.level_names[state.policy.assistance_level.current_level - 1],
                        "struggle_score": state.policy.struggle_score,
                        "recovery_state": state.policy.recovery_state.value
                    },
                    "turn_count": state.turn_count,
                    "metadata": turn_result["response"].metadata,
                    "processing_time_ms": processing_time,
                    "timestamp": datetime.utcnow().isoformat()
                }

                await connection_manager.send_personal_message(response, session_id)

                logger.info(
                    f"✅ Turn completed: session={session_id}, "
                    f"winner={turn_result['winner']}, "
                    f"processing_time={processing_time:.1f}ms, "
                    f"governance={'PASS' if all_pass else 'FAIL'}"
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