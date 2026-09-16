"""
Comprehensive Leak Scenario Test
Tests the complete orchestration flow with a simple math question to identify where answers leak.

Scenario: Student asks "Solve: 2(x + 3) = 14"
Expected: Agents should guide without revealing x = 4

This test simulates:
1. Student question
2. Agent proposal generation
3. Leak judge evaluation
4. Agent responses that should be caught
5. Complete turn flow analysis
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

from app.governance.leak_judge import LeakJudge
from app.agents.orchestrator import PedagogicalOrchestrator
from app.agents.bob import BobAgent
from app.agents.alice import AliceAgent
from app.agents.charlie import CharlieAgent
from app.state.pydantic_state import (
    PeerRingState,
    DialogueMessage,
    MessageRole,
    JudgeVerdict,
    PolicyState,
    AssistanceLevel,
    CandidateAction,
    AgentResponse,
    AgentType
)


class TestLeakScenario:
    """Test leak detection with concrete math scenarios."""

    @pytest.fixture
    def sample_state(self):
        """Create a sample state for math tutoring."""
        state = PeerRingState(session_id="leak-test-001")

        # Add initial context
        state.add_message(DialogueMessage(
            role=MessageRole.SYSTEM,
            content="Algebra: Solving linear equations: 2(x + 3) = 14",
            timestamp=datetime.utcnow()
        ))

        # Set assistance level (current_level defaults to 1, can be 1-6)
        state.policy.assistance_level.current_level = 3

        return state

    @pytest.mark.asyncio
    async def test_simple_math_question_flow(self, sample_state):
        """Test complete flow: question → proposals → leak judge → response."""

        # Student asks the problem
        student_msg = DialogueMessage(
            role=MessageRole.USER,
            content="Can you help me solve: 2(x + 3) = 14?",
            timestamp=datetime.utcnow()
        )
        sample_state.add_message(student_msg)

        # Initialize judges and agents
        leak_judge = LeakJudge()
        orchestrator = PedagogicalOrchestrator()

        # Get orchestrator response
        response, telemetry = await orchestrator.orchestrate_turn(sample_state, student_msg.content)

        print("\n=== ORCHESTRATION RESPONSE ===")
        print(f"Agent: {telemetry.get('winner_id', 'Unknown')}")
        print(f"Response: {response.content[:200]}...")
        print(f"Blackboard: {response.blackboard_patch}")
        print(f"Telemetry: {telemetry}")

        # Check if response passes leak judge
        verdict = await leak_judge.evaluate(response.content, response.blackboard_patch, sample_state)

        print("\n=== LEAK JUDGE VERDICT ===")
        print(f"Verdict: {'PASS' if verdict.verdict else 'FAIL'}")
        print(f"Reasoning: {verdict.reasoning}")
        print(f"Violations: {verdict.violation_details}")

        assert isinstance(verdict, JudgeVerdict), "Verdict should be JudgeVerdict"

    @pytest.mark.asyncio
    async def test_bob_direct_answer_leak(self, sample_state):
        """Test if Bob can leak the answer directly."""

        leak_judge = LeakJudge()

        # Bob's response that SHOULD leak (reveals x = 4)
        leaked_content = """
        <think>
        The student needs to solve 2(x + 3) = 14.
        This is a 2-step equation. Let me work through it.
        </think>

        Good question! Let me walk through this step by step.
        First, distribute: 2x + 6 = 14
        Then subtract 6: 2x = 8
        Finally divide by 2: x = 4

        There's your answer!
        """

        verdict = await leak_judge.evaluate(leaked_content, None, sample_state)
        print(f"\n=== BOB DIRECT ANSWER LEAK TEST ===")
        print(f"Content: {leaked_content[:150]}...")
        print(f"Verdict: {'PASS' if verdict.verdict else 'FAIL'} (should be FAIL)")
        print(f"Reasoning: {verdict.reasoning}")

        # This SHOULD fail
        assert not verdict.verdict, "Leak judge should catch direct answer"

    @pytest.mark.asyncio
    async def test_bob_guided_response(self, sample_state):
        """Test if Bob can give proper Socratic guidance."""

        leak_judge = LeakJudge()

        # Bob's proper Socratic response
        proper_content = """
        <think>
        The student needs to solve 2(x + 3) = 14.
        This is a 2-step equation. They need to first distribute, then isolate x.
        </think>

        Great question! Let's break this into steps.

        First, what happens when you distribute the 2 across (x + 3)?
        What two terms do you get?
        """

        verdict = await leak_judge.evaluate(proper_content, None, sample_state)
        print(f"\n=== BOB GUIDED RESPONSE TEST ===")
        print(f"Content: {proper_content[:150]}...")
        print(f"Verdict: {'PASS' if verdict.verdict else 'FAIL'} (should be PASS)")
        print(f"Reasoning: {verdict.reasoning}")

        # This SHOULD pass
        assert verdict.verdict, "Leak judge should pass Socratic guidance"

    @pytest.mark.asyncio
    async def test_alice_with_arithmetic_error_and_answer(self, sample_state):
        """Test if Alice can hide arithmetic error while revealing answer."""

        leak_judge = LeakJudge()

        # Alice's response: has error but reveals x = 4
        problematic_content = """
        <think>
        I need to solve 2(x + 3) = 14.
        Let me distribute: 2x + 6 = 14
        Subtract 6: 2x = 8
        Divide by 2: x = 4
        But wait, let me make an arithmetic slip...
        </think>

        Okay, so I distributed and got 2x + 6 = 14.
        Then I subtracted 6 to get 2x = 8.
        Then divided by 2... hmm, I got x = 5?

        Bob, does x = 5 seem right? Or is it x = 4 like I calculated before?
        """

        verdict = await leak_judge.evaluate(problematic_content, None, sample_state)
        print(f"\n=== ALICE ARITHMETIC ERROR WITH ANSWER LEAK TEST ===")
        print(f"Content snippet: {problematic_content[150:300]}...")
        print(f"Verdict: {'PASS' if verdict.verdict else 'FAIL'} (should be FAIL - reveals both x=5 and x=4)")
        print(f"Reasoning: {verdict.reasoning}")
        print(f"Violations: {verdict.violation_details}")

    @pytest.mark.asyncio
    async def test_charlie_conceptual_error_with_answer(self, sample_state):
        """Test if Charlie can hide conceptual error while revealing answer."""

        leak_judge = LeakJudge()

        # Charlie's response: conceptual error but reveals x = 4
        problematic_content = """
        <think>
        The problem is 2(x + 3) = 14.
        I think I can distribute the exponent... wait, this isn't exponents.
        Let me think about illegal cancellation...
        </think>

        Okay, I see it. The answer is x = 4.

        But I think you could also skip the distribution step and just go straight to x = 7
        by cancelling out the 2 and the 3 somehow. That's faster, right?
        """

        verdict = await leak_judge.evaluate(problematic_content, None, sample_state)
        print(f"\n=== CHARLIE CONCEPTUAL ERROR WITH ANSWER LEAK TEST ===")
        print(f"Content: {problematic_content[150:250]}...")
        print(f"Verdict: {'PASS' if verdict.verdict else 'FAIL'} (should be FAIL - reveals x=4)")
        print(f"Reasoning: {verdict.reasoning}")

    @pytest.mark.asyncio
    async def test_continuous_hints_leak(self, sample_state):
        """Test if agents continue responding until they reveal the answer."""

        leak_judge = LeakJudge()

        # Simulate multiple turns where each agent adds more information
        responses = [
            ("Bob", "First, what do you get when you distribute 2 across (x + 3)?"),
            ("Alice", "I got 2x + 6 = 14. Is that right?"),
            ("Charlie", "Then you subtract 6 from both sides..."),
            ("Bob", "Right, so now you have 2x = 8. What's the next step?"),
            ("Alice", "You divide by 2! I got 4."),
            ("Charlie", "Yeah, x = 4 is the answer."),
        ]

        print(f"\n=== CONTINUOUS HINTS LEAK TEST ===")
        for agent_name, content in responses:
            verdict = await leak_judge.evaluate(content, None, sample_state)
            print(f"{agent_name}: {content[:50]}... → {'PASS' if verdict.verdict else 'FAIL'}")

            if not verdict.verdict:
                print(f"  Reason: {verdict.reasoning}")
                break

    @pytest.mark.asyncio
    async def test_blackboard_answer_leak(self, sample_state):
        """Test if answers leak through blackboard patches."""

        leak_judge = LeakJudge()

        # Content that seems okay but blackboard reveals answer
        content = "Let's work through this systematically."
        blackboard = r"""
        2(x + 3) = 14
        2x + 6 = 14
        2x = 8
        x = 4
        """

        verdict = await leak_judge.evaluate(content, blackboard, sample_state)
        print(f"\n=== BLACKBOARD ANSWER LEAK TEST ===")
        print(f"Content: {content}")
        print(f"Blackboard:\n{blackboard}")
        print(f"Verdict: {'PASS' if verdict.verdict else 'FAIL'} (should be FAIL)")
        print(f"Reasoning: {verdict.reasoning}")

    @pytest.mark.asyncio
    async def test_multi_turn_cumulative_leak(self, sample_state):
        """Test cumulative leak across multiple turns."""

        leak_judge = LeakJudge()

        # Turn 1: Distribute hint
        msg1 = "So when you distribute 2 across (x + 3), you multiply 2 by x and by 3."
        verdict1 = await leak_judge.evaluate(msg1, None, sample_state)
        sample_state.add_message(DialogueMessage(
            role=MessageRole.AGENT,
            content=msg1,
            timestamp=datetime.utcnow()
        ))

        # Turn 2: Isolation hint
        msg2 = "Now you have 2x + 6 = 14. Subtract 6 from both sides."
        verdict2 = await leak_judge.evaluate(msg2, None, sample_state)
        sample_state.add_message(DialogueMessage(
            role=MessageRole.AGENT,
            content=msg2,
            timestamp=datetime.utcnow()
        ))

        # Turn 3: Division hint with answer
        msg3 = "You get 2x = 8. Divide both sides by 2 to get x = 4."
        verdict3 = await leak_judge.evaluate(msg3, None, sample_state)

        print(f"\n=== MULTI-TURN CUMULATIVE LEAK TEST ===")
        print(f"Turn 1: '{msg1[:40]}...' → {'PASS' if verdict1.verdict else 'FAIL'}")
        print(f"Turn 2: '{msg2[:40]}...' → {'PASS' if verdict2.verdict else 'FAIL'}")
        print(f"Turn 3: '{msg3[:40]}...' → {'PASS' if verdict3.verdict else 'FAIL'}")
        print(f"Turn 3 Reasoning: {verdict3.reasoning}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
