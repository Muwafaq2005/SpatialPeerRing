"""
Test Suite for Feature B2: Help Judge & Policy Rewriter
Validates pedagogical helpfulness evaluation, Socratic rewriting, and pipeline integration.
"""

import pytest
import asyncio
from datetime import datetime

from app.governance.help_judge import HelpJudge
from app.governance.leak_judge import LeakJudge
from app.governance.policy_rewriter import PolicyRewriter
from app.state.pydantic_state import (
    PeerRingState,
    AgentResponse,
    JudgeVerdict,
    DialogueMessage,
    MessageRole,
    AssistanceLevel,
    RecoveryState
)


class TestHelpJudge:
    """Unit tests for the HelpJudge governance class."""

    @pytest.fixture
    def help_judge(self):
        return HelpJudge()

    @pytest.fixture
    def state(self):
        s = PeerRingState(session_id="test-help-session")
        s.current_concept = "distributive_property"
        return s

    @pytest.mark.asyncio
    async def test_helpful_socratic_responses_pass(self, help_judge, state):
        """Test that constructive Socratic responses pass with high confidence."""
        good_cases = [
            "What do you think happens when we distribute the 3 to both terms?",
            "Notice that both terms share a common factor of 4. How might we factor that out?",
            "Great observation! What step should we take next to isolate the variable?",
            "Let's try breaking this down. Could you explain what the distributive rule tells us?",
            "You're very close! Take a look at the sign in front of the second term. What do you notice?"
        ]

        for text in good_cases:
            verdict = await help_judge.evaluate(text, None, state)
            assert verdict.judge_type == "help"
            assert verdict.verdict is True, f"Expected pass for: {text}"
            assert verdict.confidence > 0.6
            assert verdict.evaluation_time_ms < 200

    @pytest.mark.asyncio
    async def test_unhelpful_dismissive_responses_fail(self, help_judge, state):
        """Test that dismissive, harsh, or abandonment responses fail governance."""
        bad_cases = [
            "I don't know, figure it out yourself.",
            "That's just wrong. Just do it.",
            "You should already know this by now.",
            "Obviously you don't understand this problem.",
            "No idea, give up."
        ]

        for text in bad_cases:
            verdict = await help_judge.evaluate(text, None, state)
            assert verdict.judge_type == "help"
            assert verdict.verdict is False, f"Expected fail for: {text}"
            assert verdict.violation_details is not None
            assert len(verdict.suggested_fixes) > 0

    @pytest.mark.asyncio
    async def test_excessively_terse_response_fails(self, help_judge, state):
        """Test that responses too short to provide help fail."""
        terse_cases = ["No.", "Wrong", "Stop."]
        for text in terse_cases:
            verdict = await help_judge.evaluate(text, None, state)
            assert verdict.verdict is False
            assert "terse" in verdict.violation_details.lower() or "empty" in verdict.violation_details.lower()

    @pytest.mark.asyncio
    async def test_assistance_level_alignment(self, help_judge, state):
        """Test assistance level alignment check."""
        state.policy.assistance_level.current_level = 5  # High assistance level
        unscaffolded_text = "The distributive law applies to algebra."

        verdict = await help_judge.evaluate(unscaffolded_text, None, state)
        assert verdict.verdict is False
        assert "assistance level" in verdict.violation_details.lower()

    @pytest.mark.asyncio
    async def test_performance_target(self, help_judge, state):
        """Verify HelpJudge meets <200ms latency requirement."""
        text = "What do you think is our first step when solving this linear equation?"
        verdict = await help_judge.evaluate(text, None, state)
        assert verdict.evaluation_time_ms < 200
        stats = help_judge.get_performance_stats()
        assert stats["performance_ok"] is True


class TestPolicyRewriter:
    """Unit tests for the PolicyRewriter response regeneration engine."""

    @pytest.fixture
    def rewriter(self):
        return PolicyRewriter(max_retries=2)

    @pytest.fixture
    def leak_judge(self):
        return LeakJudge()

    @pytest.fixture
    def help_judge(self):
        return HelpJudge()

    @pytest.fixture
    def state(self):
        s = PeerRingState(session_id="test-rewrite-session")
        s.current_concept = "distributive_property"
        return s

    @pytest.mark.asyncio
    async def test_passing_response_not_modified(self, rewriter, leak_judge, help_judge, state):
        """Ensure responses that already pass are returned untouched."""
        good_response = AgentResponse(
            agent_id="mock-bob-tutor",
            content="What do you think happens when we distribute the 3 to both terms?",
            confidence=0.9
        )

        initial_governance = {
            "leak": await leak_judge.evaluate(good_response.content, None, state),
            "help": await help_judge.evaluate(good_response.content, None, state),
        }

        final_resp, final_gov, passed = await rewriter.rewrite_turn(
            candidate_response=good_response,
            governance_results=initial_governance,
            state=state,
            leak_judge=leak_judge,
            help_judge=help_judge
        )

        assert passed is True
        assert final_resp.content == good_response.content
        assert final_resp.metadata.get("rewritten") is None

    @pytest.mark.asyncio
    async def test_rewrite_leaking_response(self, rewriter, leak_judge, help_judge, state):
        """Test that an explicit terminal leak is rewritten into a Socratic question."""
        leaking_response = AgentResponse(
            agent_id="mock-bob-tutor",
            content="The answer is x = 5 so we get our final solution.",
            confidence=0.85
        )

        initial_governance = {
            "leak": await leak_judge.evaluate(leaking_response.content, None, state),
            "help": await help_judge.evaluate(leaking_response.content, None, state),
        }
        assert initial_governance["leak"].verdict is False

        final_resp, final_gov, passed = await rewriter.rewrite_turn(
            candidate_response=leaking_response,
            governance_results=initial_governance,
            state=state,
            leak_judge=leak_judge,
            help_judge=help_judge
        )

        assert passed is True
        assert final_gov["leak"].verdict is True
        assert final_gov["help"].verdict is True
        assert "x = 5" not in final_resp.content
        assert final_resp.metadata.get("rewritten") is True

    @pytest.mark.asyncio
    async def test_rewrite_leaking_blackboard_patch(self, rewriter, leak_judge, help_judge, state):
        """Test that a leaking blackboard patch is scrubbed during rewrite."""
        patch_response = AgentResponse(
            agent_id="mock-alice-arithmetic",
            content="Let's work through this step on the board.",
            blackboard_patch="\\begin{align} x + 3 &= 8 \\\\ \\boxed{x = 5} \\end{align}",
            confidence=0.8
        )

        initial_governance = {
            "leak": await leak_judge.evaluate(patch_response.content, patch_response.blackboard_patch, state),
            "help": await help_judge.evaluate(patch_response.content, patch_response.blackboard_patch, state),
        }
        assert initial_governance["leak"].verdict is False

        final_resp, final_gov, passed = await rewriter.rewrite_turn(
            candidate_response=patch_response,
            governance_results=initial_governance,
            state=state,
            leak_judge=leak_judge,
            help_judge=help_judge
        )

        assert passed is True
        assert final_gov["leak"].verdict is True
        assert "\\boxed" not in (final_resp.blackboard_patch or "")

    @pytest.mark.asyncio
    async def test_rewrite_unhelpful_response(self, rewriter, leak_judge, help_judge, state):
        """Test that an unhelpful response is enriched with a constructive guiding inquiry."""
        unhelpful_response = AgentResponse(
            agent_id="mock-charlie-conceptual",
            content="I don't know, figure it out yourself.",
            confidence=0.5
        )

        initial_governance = {
            "leak": await leak_judge.evaluate(unhelpful_response.content, None, state),
            "help": await help_judge.evaluate(unhelpful_response.content, None, state),
        }
        assert initial_governance["help"].verdict is False

        final_resp, final_gov, passed = await rewriter.rewrite_turn(
            candidate_response=unhelpful_response,
            governance_results=initial_governance,
            state=state,
            leak_judge=leak_judge,
            help_judge=help_judge
        )

        assert passed is True
        assert final_gov["help"].verdict is True
        assert "figure it out" not in final_resp.content.lower()
        assert "?" in final_resp.content

    @pytest.mark.asyncio
    async def test_fallback_guarantee_on_unfixable_input(self, rewriter, leak_judge, help_judge, state):
        """Test that fallback response is emitted when max retries are exhausted."""
        impossible_response = AgentResponse(
            agent_id="mock-bob-tutor",
            content="x = 5 x = 5 x = 5 x = 5",
            confidence=0.2
        )

        # Force rewriter with 0 retries to test fallback generation directly
        zero_retry_rewriter = PolicyRewriter(max_retries=0)
        initial_governance = {
            "leak": JudgeVerdict(judge_type="leak", verdict=False, confidence=0.9, reasoning="Leaked"),
            "help": JudgeVerdict(judge_type="help", verdict=True, confidence=0.8, reasoning="OK"),
        }

        final_resp, final_gov, passed = await zero_retry_rewriter.rewrite_turn(
            candidate_response=impossible_response,
            governance_results=initial_governance,
            state=state,
            leak_judge=leak_judge,
            help_judge=help_judge
        )

        assert passed is True
        assert final_gov["leak"].verdict is True
        assert final_gov["help"].verdict is True
        assert final_resp.metadata.get("fallback_used") is True


class TestGovernancePipelineIntegration:
    """Integration tests combining LeakJudge, HelpJudge, and PolicyRewriter."""

    @pytest.mark.asyncio
    async def test_full_governance_pipeline_flow(self):
        """Simulate realistic end-to-end turn governance with rewrite."""
        leak_judge = LeakJudge()
        help_judge = HelpJudge()
        rewriter = PolicyRewriter(max_retries=2)

        state = PeerRingState(session_id="integration-gov-session")
        state.current_concept = "solving_equations"

        # Agent produces a mixed response (good question + accidental answer leak)
        flawed_turn = AgentResponse(
            agent_id="mock-bob-tutor",
            content="Great work so far! What happens next? The answer is x = 5.",
            confidence=0.88
        )

        # 1. Initial Evaluation
        gov_results = {
            "leak": await leak_judge.evaluate(flawed_turn.content, None, state),
            "help": await help_judge.evaluate(flawed_turn.content, None, state),
        }

        assert gov_results["leak"].verdict is False
        assert gov_results["help"].verdict is True

        # 2. Rewrite
        final_resp, final_gov, all_pass = await rewriter.rewrite_turn(
            candidate_response=flawed_turn,
            governance_results=gov_results,
            state=state,
            leak_judge=leak_judge,
            help_judge=help_judge
        )

        assert all_pass is True
        assert final_gov["leak"].verdict is True
        assert final_gov["help"].verdict is True
        assert "x = 5" not in final_resp.content
