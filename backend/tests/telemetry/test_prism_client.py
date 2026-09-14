"""
Unit tests for PeerRingPRISMClient (prismtrace-sdk integration)
"""

import pytest
import asyncio
from app.telemetry.prism_client import PeerRingPRISMClient
from app.state.pydantic_state import JudgeVerdict


def test_prism_client_initialization():
    client = PeerRingPRISMClient()
    assert hasattr(client, "enabled")
    assert hasattr(client, "ambient_session")
    assert hasattr(client, "trace_agent_turn_async")
    assert hasattr(client, "trace_judge_eval_async")


def test_prism_ambient_session_context():
    client = PeerRingPRISMClient()
    session_id = "test-session-ambient-01"

    with client.ambient_session(session_id) as s_id:
        assert s_id == session_id

    # Verify fallback local buffer tracking
    local_trace = client.get_local_trace(session_id)
    assert local_trace is not None
    assert local_trace["session_id"] == session_id


@pytest.mark.asyncio
async def test_prism_non_blocking_guarantee():
    """Verify that PRISM trace submission never throws or blocks execution."""
    client = PeerRingPRISMClient()
    client.enabled = True
    client._client = None  # Force uninitialized internal client

    # Calling trace method should not raise exception even when client is uninitialized
    client.trace_agent_turn_async(
        session_id="test-non-blocking",
        agent_id="bob-tutor",
        user_input="Help me with distributive property",
        response_text="What happens if we multiply both terms?",
        latency_ms=120
    )

    verdict = JudgeVerdict(
        judge_type="leak",
        verdict=True,
        confidence=0.9,
        reasoning="No answer leaked"
    )

    client.trace_judge_eval_async(
        session_id="test-non-blocking",
        judge_type="leak",
        evaluated_text="What happens if we multiply both terms?",
        verdict=verdict,
        latency_ms=45
    )

    await asyncio.sleep(0.05)  # Allow async tasks to complete safely
