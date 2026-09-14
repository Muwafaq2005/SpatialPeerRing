"""
PRISM Telemetry Client - Block Convey PRISM Observability Layer

Provides asynchronous, non-blocking trace instrumentation, ambient session management,
and LangGraph integration wrappers. Guaranteed fail-safe: telemetry operations
never block or break PeerRing tutoring workflows.
"""

from typing import Dict, Any, Optional, List
import logging
import asyncio
import time
from contextlib import contextmanager
from datetime import datetime

import prismtrace
from prismtrace import PRISMtrace, PRISMtraceLangGraphHandler, wrap_langgraph
from app.config import settings
from app.state.pydantic_state import PeerRingState, AgentResponse, JudgeVerdict

logger = logging.getLogger(__name__)


class PeerRingPRISMClient:
    """
    Abstractions around Block Convey PRISM SDK (`prismtrace-sdk`).
    Handles ambient sessions, manual trace logging, and fail-safe tracing.
    """

    def __init__(self):
        self.enabled = settings.PRISM_ENABLED
        self.host = getattr(settings, "PRISMTRACE_HOST", "https://prism.blockconvey.com")
        self.project_id = getattr(settings, "PRISMTRACE_PROJECT_ID", "")
        self.api_key = getattr(settings, "PRISMTRACE_API_KEY", "")

        self._client: Optional[PRISMtrace] = None
        self._local_buffers: Dict[str, Dict[str, Any]] = {}

        if self.enabled and self.api_key and self.project_id:
            try:
                self._client = PRISMtrace(
                    api_key=self.api_key,
                    project_id=self.project_id,
                    host=self.host,
                )
                logger.info("PRISM Client initialized successfully.")
            except Exception as e:
                logger.warning(f"PRISM Client initialization warning (operating in fallback mode): {e}")

    @contextmanager
    def ambient_session(self, session_id: str):
        """
        Ambient session context manager.
        Groups all turns and traces emitted inside this context under session_id.
        """
        if self.enabled and self._client:
            try:
                with prismtrace.session(session_id) as s_id:
                    yield s_id
                return
            except Exception as e:
                logger.warning(f"PRISM ambient_session error (isolated): {e}")

        # Local fallback tracking when disabled or unconfigured
        if session_id not in self._local_buffers:
            self._local_buffers[session_id] = {
                "session_id": session_id,
                "start_time": datetime.utcnow().isoformat(),
                "turns": [],
                "metrics": {}
            }
        yield session_id

    def trace_agent_turn_async(
        self,
        session_id: str,
        agent_id: str,
        user_input: str,
        response_text: str,
        latency_ms: int = 150,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Fire-and-forget manual trace logging for agent turns.
        Non-blocking: Never awaits on response path.
        """
        if not self.enabled or not self._client:
            self._record_local_turn(session_id, agent_id, user_input, response_text, latency_ms, metadata)
            return

        asyncio.create_task(
            self._submit_trace_safe(
                model=settings.DEFAULT_MODEL,
                input_messages=[{"role": "user", "content": user_input}],
                output=response_text,
                latency_ms=latency_ms,
                session_id=session_id,
                agent_id=agent_id,
                agent_name=agent_id.replace("-", " ").title(),
                metadata=metadata or {}
            )
        )

    def trace_judge_eval_async(
        self,
        session_id: str,
        judge_type: str,
        evaluated_text: str,
        verdict: JudgeVerdict,
        latency_ms: int
    ) -> None:
        """
        Fire-and-forget manual trace logging for governance judges (Leak Judge, Help Judge).
        Stable IDs: 'leak-judge', 'help-judge'.
        Does NOT log hidden chain-of-thought; captures structured metadata only.
        """
        agent_id = f"{judge_type}-judge"
        metadata = {
            "verdict_pass": verdict.verdict,
            "confidence": verdict.confidence,
            "reasoning_summary": verdict.reasoning,
            "violation_details": verdict.violation_details,
            "evaluation_time_ms": verdict.evaluation_time_ms
        }

        if not self.enabled or not self._client:
            self._record_local_turn(session_id, agent_id, evaluated_text, str(verdict.verdict), latency_ms, metadata)
            return

        asyncio.create_task(
            self._submit_trace_safe(
                model=f"{judge_type}-evaluator",
                input_messages=[{"role": "user", "content": evaluated_text}],
                output=verdict.reasoning or ("PASS" if verdict.verdict else "FAIL"),
                latency_ms=latency_ms,
                session_id=session_id,
                agent_id=agent_id,
                agent_name=agent_id.replace("-", " ").title(),
                metadata=metadata
            )
        )

    async def _submit_trace_safe(self, **kwargs) -> None:
        """Internal helper to safely invoke PRISMtrace.trace_llm with exception catching."""
        try:
            if self._client:
                # Runs synchronous SDK call in thread pool to avoid blocking async loop
                await asyncio.to_thread(self._client.trace_llm, **kwargs)
        except Exception as e:
            logger.warning(f"PRISM trace_llm submission exception (non-fatal): {e}")

    def build_traced_graph(self, compiled_graph: Any, agent_name: str = "peerring-core-graph"):
        """
        LangGraph wrapper for auto-emitting trajectory spans per node.
        Used by USM when real compiled graph is initialized.
        """
        if not self.enabled or not self.api_key or not self.project_id:
            logger.info("PRISM disabled/unconfigured; returning un-wrapped LangGraph.")
            return compiled_graph, None

        try:
            handler = PRISMtraceLangGraphHandler(
                api_key=self.api_key,
                project_id=self.project_id,
                host=self.host,
                agent_name=agent_name,
            )
            traced_graph = wrap_langgraph(compiled_graph, handler)
            return traced_graph, handler
        except Exception as e:
            logger.warning(f"Failed to wrap LangGraph with PRISM handler (returning base graph): {e}")
            return compiled_graph, None

    def flush(self) -> None:
        """Flush buffered spans to PRISM backend."""
        if self.enabled and self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.warning(f"PRISM flush exception (non-fatal): {e}")

    def _record_local_turn(
        self,
        session_id: str,
        agent_id: str,
        user_input: str,
        output: str,
        latency_ms: int,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Internal fallback memory buffer when PRISM is offline/disabled."""
        if session_id not in self._local_buffers:
            self._local_buffers[session_id] = {
                "session_id": session_id,
                "start_time": datetime.utcnow().isoformat(),
                "turns": [],
                "metrics": {}
            }

        self._local_buffers[session_id]["turns"].append({
            "agent_id": agent_id,
            "user_input_length": len(user_input),
            "output_length": len(output),
            "latency_ms": latency_ms,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_local_trace(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve local buffer for offline inspection/eval."""
        return self._local_buffers.get(session_id)


# Global PRISM telemetry client instance
prism_client = PeerRingPRISMClient()
