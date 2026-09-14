"""
Integration & End-to-End Tests for PRISM & 7-Pillar Telemetry Pipeline
"""

import pytest
import asyncio
from app.state.pydantic_state import PeerRingState, AgentResponse, JudgeVerdict
from app.telemetry.prism_client import PeerRingPRISMClient, prism_client
from app.telemetry.seven_pillar_scorer import seven_pillar_scorer
from app.telemetry.trust_pack_exporter import trust_pack_exporter


@pytest.mark.asyncio
async def test_prism_telemetry_pipeline():
    session_id = "test-pipeline-session"

    with prism_client.ambient_session(session_id) as s_id:
        assert s_id == session_id

        prism_client.trace_agent_turn_async(
            session_id=session_id,
            agent_id="bob-tutor",
            user_input="Explain 3(x + 4)",
            response_text="What happens when we multiply outside number by both terms?",
            latency_ms=140
        )

        verdict = JudgeVerdict(
            judge_type="leak",
            verdict=True,
            confidence=0.95,
            reasoning="No leakage detected"
        )

        prism_client.trace_judge_eval_async(
            session_id=session_id,
            judge_type="leak",
            evaluated_text="What happens when we multiply outside number by both terms?",
            verdict=verdict,
            latency_ms=40
        )

        await asyncio.sleep(0.02)

    state = PeerRingState(session_id=session_id)
    report = seven_pillar_scorer.score_session(state=state, governance_history=[{"leak": verdict}])
    trust_pack = trust_pack_exporter.export_trust_pack(session_id, report)

    assert report.overall_score > 0.0
    assert trust_pack.verification_hash is not None
