"""
Unit tests for TrustPackExporter
"""

import pytest
from app.state.pydantic_state import PeerRingState
from app.telemetry.seven_pillar_scorer import seven_pillar_scorer
from app.telemetry.trust_pack_exporter import trust_pack_exporter


def test_trust_pack_export():
    state = PeerRingState(session_id="test-trust-pack-session")
    report = seven_pillar_scorer.score_session(state=state, mastery_before=0.1)

    trust_pack = trust_pack_exporter.export_trust_pack(
        session_id="test-trust-pack-session",
        seven_pillar_report=report,
        prism_session_id="prism-test-trust-pack-session"
    )

    assert trust_pack.pack_id.startswith("tp-test-trust-pack-session-")
    assert trust_pack.overall_score == report.overall_score
    assert len(trust_pack.verification_hash) == 16
    assert "=== SPATIAL PEERRING TRUST PACK ===" in trust_pack.human_summary
    assert trust_pack.trace_references["prism_session_id"] == "prism-test-trust-pack-session"
