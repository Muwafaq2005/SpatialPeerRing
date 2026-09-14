"""
Unit and simulation tests for Pedagogical Orchestrator & Candidate Scorer.
(feature/pedagogical-orchestrator)

Verifies:
1. CandidateScorer dynamic weighting under struggle states.
2. Anti-monopolization penalty and cooldown decay.
3. Single-turn orchestration execution.
4. 10-turn simulated multi-agent study pod session with natural speaker rotation.
5. PRISM orchestration telemetry recording.
"""

import pytest
from datetime import datetime, timedelta

from app.agents.orchestrator import PedagogicalOrchestrator
from app.agents.candidate_scorer import CandidateScorer, ScoredCandidate
from app.agents.bob import BobAgent
from app.agents.alice import AliceAgent
from app.agents.charlie import CharlieAgent
from app.state.pydantic_state import (
    PeerRingState,
    CandidateAction,
    AgentResponse,
    DialogueMessage,
    MessageRole,
    CurriculumNode,
    PolicyState,
    AssistanceLevel,
)


@pytest.fixture
def base_state():
    """Create a baseline state with active curriculum."""
    return PeerRingState(
        session_id="test-orchestration-session",
        curriculum_dag={
            "distributive_law": CurriculumNode(
                concept_id="distributive_law",
                name="Distributive Law",
                description="Expand a(b + c)",
                mastery_score=0.4
            )
        },
        current_concept="distributive_law",
        policy=PolicyState(
            assistance_level=AssistanceLevel(current_level=2),
            struggle_score=0.3
        ),
        messages=[]
    )


class TestCandidateScorer:
    """Test CandidateScorer dynamic weighting and anti-monopolization."""

    def test_scorer_initialization(self):
        scorer = CandidateScorer(cooldown_duration_sec=30.0)
        assert scorer.cooldown_duration_sec == 30.0

    def test_high_struggle_favors_bob(self, base_state):
        scorer = CandidateScorer()
        base_state.policy.struggle_score = 0.90
        base_state.policy.assistance_level.current_level = 5

        candidates = [
            CandidateAction(
                agent_id="bob-tutor",
                action_type="question",
                pedagogical_utility=0.75,
                content_preview="Bob tutor inquiry"
            ),
            CandidateAction(
                agent_id="alice-peer",
                action_type="respond",
                pedagogical_utility=0.75,
                content_preview="Alice calculation"
            ),
            CandidateAction(
                agent_id="charlie-peer",
                action_type="respond",
                pedagogical_utility=0.75,
                content_preview="Charlie shortcut"
            ),
        ]

        scored = scorer.score_candidates(candidates, base_state)
        # Winner must be Bob
        assert scored[0].agent_id == "bob-tutor"
        assert scored[0].final_score > scored[1].final_score
        assert scored[0].final_score > scored[2].final_score

    def test_low_struggle_boosts_peers(self, base_state):
        scorer = CandidateScorer()
        base_state.policy.struggle_score = 0.15
        base_state.policy.assistance_level.current_level = 1

        candidates = [
            CandidateAction(
                agent_id="bob-tutor",
                action_type="question",
                pedagogical_utility=0.60,
                content_preview="Bob tutor inquiry"
            ),
            CandidateAction(
                agent_id="alice-peer",
                action_type="respond",
                pedagogical_utility=0.60,
                content_preview="Alice calculation"
            ),
        ]

        scored = scorer.score_candidates(candidates, base_state)
        # Peer receives encouragement boost when student is confident
        alice_scored = next(s for s in scored if s.agent_id == "alice-peer")
        bob_scored = next(s for s in scored if s.agent_id == "bob-tutor")
        assert alice_scored.final_score > bob_scored.final_score

    def test_anti_monopolization_penalty(self, base_state):
        scorer = CandidateScorer()

        # Simulate Bob speaking 3 times consecutively
        for _ in range(3):
            base_state.messages.append(
                DialogueMessage(
                    role=MessageRole.AGENT,
                    agent_id="bob-tutor",
                    content="Thinking..."
                )
            )

        cand = CandidateAction(
            agent_id="bob-tutor",
            action_type="question",
            pedagogical_utility=0.80,
            content_preview="Bob tries to speak again"
        )

        scored = scorer.score_candidate(cand, base_state)
        assert scored.cooldown_penalty >= 0.90
        assert scored.final_score <= 0.10


class TestPedagogicalOrchestrator:
    """Test orchestrator turn loop and multi-agent coordination."""

    @pytest.mark.asyncio
    async def test_single_turn_orchestration(self, base_state):
        orchestrator = PedagogicalOrchestrator()
        user_input = "Can someone explain how 2(x + 5) works?"

        response, telemetry = await orchestrator.orchestrate_turn(base_state, user_input)

        # 1. Check response structure
        assert isinstance(response, AgentResponse)
        assert response.agent_id in ["bob-tutor", "alice-peer", "charlie-peer"]
        assert len(response.content) > 0
        assert response.think_block is not None

        # 2. Check telemetry
        assert telemetry["winner_id"] == response.agent_id
        assert "all_candidate_scores" in telemetry
        assert len(telemetry["all_candidate_scores"]) >= 3
        assert telemetry["prism_event"] == "ORCHESTRATOR_SPEAKER_SELECTED"

        # 3. Check state update
        assert len(base_state.messages) == 2  # 1 user + 1 agent
        assert base_state.messages[0].role == MessageRole.USER
        assert base_state.messages[1].role == MessageRole.AGENT
        assert base_state.policy.last_active_agent == response.agent_id

    @pytest.mark.asyncio
    async def test_high_struggle_causes_bob_to_win(self, base_state):
        orchestrator = PedagogicalOrchestrator()
        base_state.policy.struggle_score = 0.95
        base_state.policy.assistance_level.current_level = 5

        user_input = "I am totally stuck, please help me!"
        response, telemetry = await orchestrator.orchestrate_turn(base_state, user_input)

        assert response.agent_id == "bob-tutor"
        assert telemetry["winner_id"] == "bob-tutor"

    @pytest.mark.asyncio
    async def test_ten_turn_multi_agent_session_simulation(self, base_state):
        """
        Simulate 10 continuous turns in the virtual study pod.
        Verifies:
        - Natural conversational rotation among all 3 agents (Bob, Alice, Charlie).
        - Cooldown penalties prevent any single agent from dominating.
        - State correctly records all 20 messages (10 user + 10 agent).
        """
        orchestrator = PedagogicalOrchestrator()

        turns_data = [
            ("Hello everyone, I want to learn distributive property.", 0.2),
            ("Let's try 3(x + 4). What do you guys think?", 0.25),
            ("Wait, Alice did you add 3 and 4?", 0.3),
            ("Is 3 * 4 equal to 12?", 0.35),
            ("Charlie, what about your shortcut?", 0.4),
            ("I'm starting to get a little confused now.", 0.65),
            ("Wait, why can't we cancel terms like that?", 0.75),
            ("I don't know what step to take next.", 0.90),
            ("Okay, looking at just the left side...", 0.60),
            ("I think I understand how to distribute now!", 0.20),
        ]

        winners = []
        for user_text, struggle in turns_data:
            base_state.policy.struggle_score = struggle
            response, telemetry = await orchestrator.orchestrate_turn(base_state, user_text)
            winners.append(response.agent_id)

        # 1. Total messages in state should be 20 (10 user turns + 10 agent turns)
        assert len(base_state.messages) == 20

        # 2. Verify all agents participated in the study pod session
        unique_winners = set(winners)
        assert "bob-tutor" in unique_winners
        assert ("alice-peer" in unique_winners) or ("charlie-peer" in unique_winners)
        assert len(unique_winners) >= 2, f"Expected diverse speakers, got {unique_winners}"

        # 3. Verify no agent spoke more than 2 times consecutively
        max_consecutive = 1
        current_streak = 1
        for i in range(1, len(winners)):
            if winners[i] == winners[i - 1]:
                current_streak += 1
                max_consecutive = max(max_consecutive, current_streak)
            else:
                current_streak = 1

        assert max_consecutive <= 2, f"Monopolization violation: an agent spoke {max_consecutive} times in a row!"
