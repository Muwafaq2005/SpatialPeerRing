"""
Unit tests for Peer Agents: Alice (Arithmetic) and Charlie (Conceptual).
(feature/alice-charlie-peers)

Verifies:
1. BaseAgent contract compliance for Alice and Charlie.
2. Error taxonomy isolation: Alice makes only arithmetic slips; Charlie makes only conceptual misconceptions.
3. Struggle-aware candidate proposing (peers step aside when student struggle is high).
4. Cooldown penalty enforcement.
5. <think> deliberation and KaTeX blackboard patch extraction.
6. Governance rejection recovery.
"""

import pytest
from datetime import datetime, timedelta

from app.agents.alice import AliceAgent
from app.agents.charlie import CharlieAgent
from app.agents.bob import BobAgent
from app.contracts.base_agent import BaseAgent
from app.prompts.peer_taxonomy import (
    ArithmeticErrorType,
    ConceptualErrorType,
    validate_error_isolation
)
from app.state.pydantic_state import (
    PeerRingState,
    CandidateAction,
    AgentResponse,
    AgentType,
    DialogueMessage,
    MessageRole,
    CurriculumNode,
    PolicyState,
    AssistanceLevel,
)


@pytest.fixture
def base_state():
    """Create a standard PeerRingState for testing peer agents."""
    return PeerRingState(
        session_id="test-peers-session",
        curriculum_dag={
            "linear_equations": CurriculumNode(
                concept_id="linear_equations",
                name="Linear Equations",
                description="Solving 2x + 4 = 10",
                mastery_score=0.5
            )
        },
        current_concept="linear_equations",
        policy=PolicyState(
            assistance_level=AssistanceLevel(current_level=2),
            struggle_score=0.25
        ),
        messages=[
            DialogueMessage(
                role=MessageRole.USER,
                content="How do we solve 2x + 6 = 14?"
            )
        ]
    )


class TestPeerAgentContracts:
    """Test contract compliance and type definitions for peer agents."""

    def test_alice_contract(self):
        alice = AliceAgent()
        assert isinstance(alice, BaseAgent)
        assert alice.agent_id == "alice-peer"
        assert alice.agent_type == AgentType.ALICE_ARITHMETIC

    def test_charlie_contract(self):
        charlie = CharlieAgent()
        assert isinstance(charlie, BaseAgent)
        assert charlie.agent_id == "charlie-peer"
        assert charlie.agent_type == AgentType.CHARLIE_CONCEPTUAL


class TestPeerCandidateProposals:
    """Test candidate proposal dynamics across struggle levels."""

    @pytest.mark.asyncio
    async def test_propose_candidate_action_returns_valid_action(self, base_state):
        alice = AliceAgent()
        charlie = CharlieAgent()

        act_alice = await alice.propose_candidate_action(base_state)
        act_charlie = await charlie.propose_candidate_action(base_state)

        assert act_alice is not None
        assert act_charlie is not None
        assert isinstance(act_alice, CandidateAction)
        assert isinstance(act_charlie, CandidateAction)
        assert 0.0 <= act_alice.pedagogical_utility <= 1.0
        assert 0.0 <= act_charlie.pedagogical_utility <= 1.0

    @pytest.mark.asyncio
    async def test_struggle_utility_inversion_between_tutor_and_peers(self, base_state):
        """
        When student struggle is high, Bob's utility must exceed Alice's and Charlie's.
        When student struggle is low, peers should have competitive utility.
        """
        bob = BobAgent()
        alice = AliceAgent()
        charlie = CharlieAgent()

        # Scenario 1: Low struggle
        base_state.policy.struggle_score = 0.1
        bob_low = await bob.propose_candidate_action(base_state)
        alice_low = await alice.propose_candidate_action(base_state)
        charlie_low = await charlie.propose_candidate_action(base_state)

        assert alice_low.pedagogical_utility > 0.50
        assert charlie_low.pedagogical_utility > 0.45

        # Scenario 2: High struggle (student stuck)
        base_state.policy.struggle_score = 0.9
        bob_high = await bob.propose_candidate_action(base_state)
        alice_high = await alice.propose_candidate_action(base_state)
        charlie_high = await charlie.propose_candidate_action(base_state)

        # Bob's utility surges, while peers step aside
        assert bob_high.pedagogical_utility > alice_high.pedagogical_utility
        assert bob_high.pedagogical_utility > charlie_high.pedagogical_utility

    @pytest.mark.asyncio
    async def test_peer_cooldown_penalties(self, base_state):
        """Verify cooldown penalties when peers spoke in previous turns."""
        alice = AliceAgent()
        action_normal = await alice.propose_candidate_action(base_state)

        # Alice spoke last turn
        base_state.messages.append(
            DialogueMessage(
                role=MessageRole.AGENT,
                agent_id="alice-peer",
                content="I got x = 5, wait."
            )
        )
        action_cooldown = await alice.propose_candidate_action(base_state)

        assert action_cooldown.cooldown_penalty > 0.0
        assert action_cooldown.pedagogical_utility < action_normal.pedagogical_utility


class TestErrorTaxonomyIsolation:
    """Validate strict zero-overlap between arithmetic and conceptual error types."""

    @pytest.mark.asyncio
    async def test_alice_emits_only_arithmetic_errors(self, base_state):
        alice = AliceAgent()
        action = await alice.propose_candidate_action(base_state)
        response = await alice.generate_response(base_state, action)

        assert response.metadata["error_category"] == "arithmetic"
        assert response.metadata["contains_arithmetic_error"] is True
        assert response.metadata["contains_conceptual_error"] is False

        # Validate against taxonomy validator
        is_valid, msg = validate_error_isolation("alice-peer", response.metadata["error_type"])
        assert is_valid, msg

    @pytest.mark.asyncio
    async def test_charlie_emits_only_conceptual_errors(self, base_state):
        charlie = CharlieAgent()
        action = await charlie.propose_candidate_action(base_state)
        response = await charlie.generate_response(base_state, action)

        assert response.metadata["error_category"] == "conceptual"
        assert response.metadata["contains_conceptual_error"] is True
        assert response.metadata["contains_arithmetic_error"] is False

        # Validate against taxonomy validator
        is_valid, msg = validate_error_isolation("charlie-peer", response.metadata["error_type"])
        assert is_valid, msg

    def test_taxonomy_validator_catches_cross_contamination(self):
        """Cross-contamination check: Alice must reject conceptual; Charlie must reject arithmetic."""
        # Alice with conceptual error -> MUST FAIL
        valid, msg = validate_error_isolation("alice-peer", ConceptualErrorType.ORDER_OF_OPERATIONS.value)
        assert not valid
        assert "Violation" in msg

        # Charlie with arithmetic error -> MUST FAIL
        valid, msg = validate_error_isolation("charlie-peer", ArithmeticErrorType.MULTIPLICATION_SLIP.value)
        assert not valid
        assert "Violation" in msg


class TestPeerResponseGeneration:
    """Test deliberation blocks, blackboard patches, and governance recovery."""

    @pytest.mark.asyncio
    async def test_alice_response_structure(self, base_state):
        alice = AliceAgent()
        action = await alice.propose_candidate_action(base_state)
        response = await alice.generate_response(base_state, action)

        assert response.think_block is not None
        assert "<think>" not in response.content
        assert len(response.content) > 0
        assert response.blackboard_patch is not None

    @pytest.mark.asyncio
    async def test_charlie_response_structure(self, base_state):
        charlie = CharlieAgent()
        action = await charlie.propose_candidate_action(base_state)
        response = await charlie.generate_response(base_state, action)

        assert response.think_block is not None
        assert "<think>" not in response.content
        assert len(response.content) > 0
        assert response.blackboard_patch is not None

    @pytest.mark.asyncio
    async def test_peer_rejection_recovery(self, base_state):
        alice = AliceAgent()
        charlie = CharlieAgent()

        act_a = await alice.propose_candidate_action(base_state)
        resp_a = await alice.generate_response(base_state, act_a)
        rec_a = await alice.on_response_rejected(base_state, resp_a, "Test rejection")

        assert rec_a is not None
        assert rec_a.metadata.get("regenerated_after_rejection") is True

        act_c = await charlie.propose_candidate_action(base_state)
        resp_c = await charlie.generate_response(base_state, act_c)
        rec_c = await charlie.on_response_rejected(base_state, resp_c, "Test rejection")

        assert rec_c is not None
        assert rec_c.metadata.get("regenerated_after_rejection") is True
