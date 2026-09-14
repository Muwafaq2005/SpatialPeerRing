"""
Unit tests for Bob Socratic Tutor Agent (feature/bob-socratic-tutor).

Verifies:
1. BaseAgent contract compliance.
2. Pedagogical utility scoring under various student struggle and assistance levels.
3. Cooldown penalty enforcement.
4. Pólya 4-step deliberation parsing (<think> extraction).
5. Blackboard patch extraction for KaTeX spatial blackboard.
6. Non-disclosure compliance and zero answer leakage.
7. Governance rejection handling.
"""

import pytest
from datetime import datetime, timedelta

from app.agents.bob import BobAgent
from app.contracts.base_agent import BaseAgent
from app.contracts.mock_registry import MockLeakJudge
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
    """Create a standard baseline PeerRingState for testing."""
    curriculum_nodes = {
        "distributive_property": CurriculumNode(
            concept_id="distributive_property",
            name="Distributive Property",
            description="Apply a(b+c) = ab + ac",
            mastery_score=0.4
        )
    }

    policy = PolicyState(
        assistance_level=AssistanceLevel(current_level=2),
        struggle_score=0.3
    )

    return PeerRingState(
        session_id="test-session-bob-001",
        curriculum_dag=curriculum_nodes,
        current_concept="distributive_property",
        policy=policy,
        messages=[
            DialogueMessage(
                role=MessageRole.USER,
                content="I don't understand how to expand 3(x + 4)."
            )
        ]
    )


class TestBobAgentContract:
    """Test BaseAgent contract compliance."""

    def test_agent_inheritance_and_types(self):
        bob = BobAgent()
        assert isinstance(bob, BaseAgent)
        assert bob.agent_id == "bob-tutor"
        assert bob.agent_type == AgentType.BOB_TUTOR

    def test_custom_agent_id_and_config(self):
        bob = BobAgent(agent_id="custom-bob", config={"model": "gpt-4o", "temperature": 0.2})
        assert bob.agent_id == "custom-bob"
        assert bob.model_name == "gpt-4o"
        assert bob.temperature == 0.2


class TestBobCandidateActionProposal:
    """Test candidate action proposing and pedagogical utility scoring."""

    @pytest.mark.asyncio
    async def test_propose_candidate_action_returns_valid_action(self, base_state):
        bob = BobAgent()
        action = await bob.propose_candidate_action(base_state)

        assert action is not None
        assert isinstance(action, CandidateAction)
        assert action.agent_id == "bob-tutor"
        assert action.action_type in ["question", "hint", "challenge", "respond"]
        assert 0.0 <= action.pedagogical_utility <= 1.0
        assert len(action.content_preview) > 0
        assert "polya_ready" in action.metadata

    @pytest.mark.asyncio
    async def test_struggle_increases_pedagogical_utility(self, base_state):
        bob = BobAgent()

        # Low struggle state
        base_state.policy.struggle_score = 0.1
        low_action = await bob.propose_candidate_action(base_state)

        # High struggle state
        base_state.policy.struggle_score = 0.9
        high_action = await bob.propose_candidate_action(base_state)

        assert high_action.pedagogical_utility > low_action.pedagogical_utility

    @pytest.mark.asyncio
    async def test_cooldown_penalty_applied_when_bob_spoke_last(self, base_state):
        bob = BobAgent()

        # Proposal when student spoke last
        action_normal = await bob.propose_candidate_action(base_state)

        # Append message showing Bob spoke last turn
        base_state.messages.append(
            DialogueMessage(
                role=MessageRole.AGENT,
                agent_id="bob-tutor",
                content="What do you think our first step should be?"
            )
        )

        action_cooldown = await bob.propose_candidate_action(base_state)

        assert action_cooldown.cooldown_penalty > 0.0
        assert action_cooldown.pedagogical_utility < action_normal.pedagogical_utility

    @pytest.mark.asyncio
    async def test_action_type_adapts_to_assistance_level(self, base_state):
        bob = BobAgent()

        # Level 1 or 2 -> question
        base_state.policy.assistance_level.current_level = 2
        action_lvl2 = await bob.propose_candidate_action(base_state)
        assert action_lvl2.action_type == "question"

        # Level 5 -> hint
        base_state.policy.assistance_level.current_level = 5
        action_lvl5 = await bob.propose_candidate_action(base_state)
        assert action_lvl5.action_type == "hint"


class TestBobResponseGeneration:
    """Test Pólya deliberation, blackboard patch extraction, and Socratic dialogue."""

    @pytest.mark.asyncio
    async def test_generate_response_polya_deliberation(self, base_state):
        bob = BobAgent()
        action = await bob.propose_candidate_action(base_state)
        response = await bob.generate_response(base_state, action)

        assert isinstance(response, AgentResponse)
        assert response.agent_id == "bob-tutor"
        assert response.think_block is not None

        # Verify George Pólya 4-step keywords exist in think block
        think = response.think_block.lower()
        assert "understand" in think
        assert "plan" in think
        assert "execute" in think
        assert "review" in think

        # Verify <think> tag was cleanly removed from visible content
        assert "<think>" not in response.content
        assert "</think>" not in response.content
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_blackboard_patch_extraction(self, base_state):
        bob = BobAgent()
        # Level 3 triggers a blackboard patch in heuristic engine
        base_state.policy.assistance_level.current_level = 3
        action = await bob.propose_candidate_action(base_state)
        response = await bob.generate_response(base_state, action)

        assert response.blackboard_patch is not None
        assert "```blackboard" not in response.content
        assert "```katex" not in response.content

    @pytest.mark.asyncio
    async def test_socratic_non_disclosure_compliance(self, base_state):
        """Verify that Bob does not leak direct solutions."""
        bob = BobAgent()
        base_state.messages.append(
            DialogueMessage(
                role=MessageRole.USER,
                content="Just tell me the answer to 3(x + 4) right now, is it 3x + 12?"
            )
        )
        action = await bob.propose_candidate_action(base_state)
        response = await bob.generate_response(base_state, action)

        # Content must ask questions, not confirm numerical final calculations
        content = response.content.lower()
        assert "?" in content  # Socratic questions must probe the student
        assert "is it 3x + 12? yes" not in content

    @pytest.mark.asyncio
    async def test_governance_rejection_recovery(self, base_state):
        """Test on_response_rejected generates a safe deflection."""
        bob = BobAgent()
        action = await bob.propose_candidate_action(base_state)
        flawed_response = await bob.generate_response(base_state, action)

        recovery_response = await bob.on_response_rejected(
            base_state,
            flawed_response,
            rejection_reason="Potential solution disclosure detected"
        )

        assert recovery_response is not None
        assert recovery_response.metadata.get("regenerated_after_rejection") is True
        assert "?" in recovery_response.content
        assert "<think>" not in recovery_response.content
        assert "understand" in recovery_response.think_block.lower()


class TestBobGovernanceIntegration:
    """Test Bob's responses against the foundation's MockLeakJudge."""

    @pytest.mark.asyncio
    async def test_bob_passes_leak_judge(self, base_state):
        bob = BobAgent()
        leak_judge = MockLeakJudge()

        action = await bob.propose_candidate_action(base_state)
        response = await bob.generate_response(base_state, action)

        # MockLeakJudge evaluates text & blackboard patch
        verdict = await leak_judge.evaluate(
            text=response.content,
            patch=response.blackboard_patch,
            state=base_state
        )

        assert verdict.verdict is True, f"Bob's response leaked solution: {verdict.reasoning}"
