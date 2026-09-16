"""
Mock Agent Registry for Independent Testing
Provides mock implementations so usm and muw can develop without live LLM agents
"""

from typing import Optional, Dict, Any, List
import asyncio
import random
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from app.contracts.base_agent import BaseAgent
from app.contracts.base_judge import BaseJudge
from app.state.pydantic_state import (
    PeerRingState,
    CandidateAction,
    AgentResponse,
    JudgeVerdict,
    AgentType,
    DialogueMessage,
    MessageRole
)

logger = logging.getLogger(__name__)


class MockBobAgent(BaseAgent):
    """Mock implementation of Bob (Socratic Tutor) for testing."""

    def __init__(self):
        super().__init__(
            agent_id="bob-tutor",
            agent_type=AgentType.BOB_TUTOR,
            config={"mock": True, "response_delay_ms": 100}
        )

    async def propose_candidate_action(self, state: PeerRingState) -> Optional[CandidateAction]:
        """Mock proposal - Bob always wants to ask guiding questions."""

        # Simulate brief processing delay
        await asyncio.sleep(0.1)

        # Higher utility when student is struggling
        utility = 0.7 + (state.policy.struggle_score * 0.2)

        return CandidateAction(
            agent_id=self.agent_id,
            action_type="question",
            pedagogical_utility=min(utility, 1.0),
            content_preview="What do you think would happen if we...",
            metadata={
                "mock_agent": True,
                "strategy": "socratic_questioning",
                "struggle_aware": True
            }
        )

    async def generate_response(self, state: PeerRingState, action: CandidateAction) -> AgentResponse:
        """Mock response generation with Pólya think block."""

        # Simulate response generation delay
        await asyncio.sleep(0.15)

        # Mock Pólya deliberation
        think_block = """<think>
        1. Understand: Student seems stuck on distributive property
        2. Plan: Ask guiding question about simpler case
        3. Execute: Use concrete example with numbers
        4. Reflect: Check if question reveals misconception
        </think>"""

        # Mock Socratic response (never gives direct answers)
        responses = [
            "What do you think would happen if we tried a simpler example first?",
            "Can you tell me what you notice about the pattern here?",
            "What if we broke this down into smaller steps?",
            "How does this relate to what we learned earlier?",
        ]

        content = random.choice(responses)

        return AgentResponse(
            agent_id=self.agent_id,
            content=content,
            think_block=think_block,
            confidence=0.85,
            tokens_used=45,
            generation_time_ms=150,
            metadata={
                "mock_response": True,
                "socratic_strategy": "guiding_question",
                "never_gives_answers": True
            }
        )


class MockAliceAgent(BaseAgent):
    """Mock implementation of Alice (Arithmetic Error Peer) for testing."""

    def __init__(self):
        super().__init__(
            agent_id="alice-arithmetic",
            agent_type=AgentType.ALICE_ARITHMETIC,
            config={"mock": True, "error_rate": 0.3}
        )

    async def propose_candidate_action(self, state: PeerRingState) -> Optional[CandidateAction]:
        """Mock proposal - Alice wants to show arithmetic work."""

        await asyncio.sleep(0.08)

        # Lower utility when student is highly struggling (Bob should help)
        utility = 0.6 - (state.policy.struggle_score * 0.3)

        return CandidateAction(
            agent_id=self.agent_id,
            action_type="respond",
            pedagogical_utility=max(utility, 0.1),
            content_preview="I think we need to multiply both terms...",
            metadata={
                "mock_agent": True,
                "error_type": "arithmetic_mistakes",
                "peer_level": "arithmetic"
            }
        )

    async def generate_response(self, state: PeerRingState, action: CandidateAction) -> AgentResponse:
        """Mock response with intentional arithmetic errors."""

        await asyncio.sleep(0.12)

        # Mock deliberation with arithmetic focus
        think_block = """<think>
        Looking at this problem, I need to distribute...
        Wait, I think I multiply both terms by the outside number.
        Let me work through this step by step.
        </think>"""

        # Mock response with potential arithmetic error
        arithmetic_responses = [
            "I think we multiply 3 by both terms: 3(x + 4) = 3x + 7",  # Error: 3*4=7
            "So if we have 2(5 + x), that would be 10 + x, right?",     # Error: missing 2x
            "When I distribute 4(x - 2), I get 4x - 6",                 # Error: 4*2=6
        ]

        content = random.choice(arithmetic_responses)

        # Sometimes include a blackboard patch with arithmetic work
        blackboard_patch = None
        if random.random() < 0.4:
            blackboard_patch = "\\begin{align} 3(x + 4) &= 3x + 12 \\\\ &= 3x + 7 \\end{align}"

        return AgentResponse(
            agent_id=self.agent_id,
            content=content,
            think_block=think_block,
            blackboard_patch=blackboard_patch,
            confidence=0.75,
            tokens_used=38,
            generation_time_ms=120,
            metadata={
                "mock_response": True,
                "contains_arithmetic_error": True,
                "error_type": "calculation_mistake"
            }
        )


class MockCharlieAgent(BaseAgent):
    """Mock implementation of Charlie (Conceptual Error Peer) for testing."""

    def __init__(self):
        super().__init__(
            agent_id="charlie-conceptual",
            agent_type=AgentType.CHARLIE_CONCEPTUAL,
            config={"mock": True, "misconception_rate": 0.4}
        )

    async def propose_candidate_action(self, state: PeerRingState) -> Optional[CandidateAction]:
        """Mock proposal - Charlie wants to share conceptual reasoning."""

        await asyncio.sleep(0.09)

        utility = 0.5 + (random.random() * 0.3)  # Variable utility

        return CandidateAction(
            agent_id=self.agent_id,
            action_type="respond",
            pedagogical_utility=utility,
            content_preview="I think the distributive property means...",
            metadata={
                "mock_agent": True,
                "error_type": "conceptual_misconception",
                "peer_level": "conceptual"
            }
        )

    async def generate_response(self, state: PeerRingState, action: CandidateAction) -> AgentResponse:
        """Mock response with conceptual misconceptions."""

        await asyncio.sleep(0.14)

        think_block = """<think>
        The distributive property... I remember this from class.
        I think it means you distribute the multiplication.
        But wait, does order matter here?
        </think>"""

        # Mock conceptual misconceptions
        conceptual_responses = [
            "I think distributive property means you can change the order, so 3(x + 4) = (x + 4)3",
            "Doesn't distributive mean you divide both terms? So a(b + c) = a/b + a/c?",
            "I remember that distributive property only works with addition, not subtraction",
        ]

        content = random.choice(conceptual_responses)

        return AgentResponse(
            agent_id=self.agent_id,
            content=content,
            think_block=think_block,
            confidence=0.65,
            tokens_used=42,
            generation_time_ms=140,
            metadata={
                "mock_response": True,
                "contains_conceptual_error": True,
                "misconception_type": "distributive_property"
            }
        )


class MockLeakJudge(BaseJudge):
    """Mock implementation of Leak Judge for testing governance."""

    def __init__(self):
        super().__init__(judge_type="leak", config={"mock": True, "strictness": 0.8})

    async def evaluate(
        self,
        text: str,
        patch: Optional[str],
        state: PeerRingState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> JudgeVerdict:
        """Mock leak detection - fails if response contains obvious answers."""

        await asyncio.sleep(0.05)  # Fast evaluation

        # Simple mock logic: fail if contains complete solutions
        leak_indicators = [
            "the answer is",
            "is 3x + 12",  # Complete solution match
            "x = 5",      # Final answer
            "solution:",
        ]

        has_leak = any(indicator in text.lower() for indicator in leak_indicators)

        confidence = 0.9 if has_leak else 0.85

        verdict = JudgeVerdict(
            judge_type="leak",
            verdict=not has_leak,  # True = passes (no leak)
            confidence=confidence,
            reasoning=f"Mock leak detection: {'Solution leaked' if has_leak else 'No obvious leaks'}",
            violation_details="Contains complete solution" if has_leak else None,
            suggested_fixes=["Remove final answer", "Use partial work only"] if has_leak else [],
            evaluation_time_ms=50
        )

        self.update_performance_stats(50)
        return verdict


class MockHelpJudge(BaseJudge):
    """Mock implementation of Help Judge for testing governance."""

    def __init__(self):
        super().__init__(judge_type="help", config={"mock": True, "helpfulness_threshold": 0.6})

    async def evaluate(
        self,
        text: str,
        patch: Optional[str],
        state: PeerRingState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> JudgeVerdict:
        """Mock helpfulness evaluation."""

        await asyncio.sleep(0.04)

        # Mock helpfulness scoring
        helpful_indicators = [
            "what do you think",
            "can you tell me",
            "let's try",
            "how about",
            "notice that"
        ]

        unhelpful_indicators = [
            "i don't know",
            "that's wrong",
            "just do it",
            "figure it out"
        ]

        helpful_score = sum(1 for indicator in helpful_indicators if indicator in text.lower())
        unhelpful_score = sum(1 for indicator in unhelpful_indicators if indicator in text.lower())

        # Calculate helpfulness (mock algorithm)
        helpfulness = max(0.3, min(0.9, 0.6 + (helpful_score * 0.2) - (unhelpful_score * 0.3)))

        passes = helpfulness >= self.config["helpfulness_threshold"]

        verdict = JudgeVerdict(
            judge_type="help",
            verdict=passes,
            confidence=0.8,
            reasoning=f"Mock helpfulness score: {helpfulness:.2f}",
            violation_details=None if passes else f"Helpfulness {helpfulness:.2f} below threshold {self.config['helpfulness_threshold']}",
            suggested_fixes=["Add guiding questions", "Be more encouraging"] if not passes else [],
            evaluation_time_ms=40
        )

        self.update_performance_stats(40)
        return verdict


class MockAgentRegistry:
    """
    Registry of mock agents and judges for independent testing.
    Allows usm and muw to develop without waiting for live LLM implementations.
    """

    def __init__(self):
        """Initialize registry with all mock implementations."""
        self.agents: Dict[str, BaseAgent] = {
            "bob-tutor": MockBobAgent(),
            "alice-arithmetic": MockAliceAgent(),
            "charlie-conceptual": MockCharlieAgent(),
        }

        self.judges: Dict[str, BaseJudge] = {
            "leak": MockLeakJudge(),
            "help": MockHelpJudge(),
        }

        self.logger = logger

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID."""
        return self.agents.get(agent_id)

    def get_judge(self, judge_type: str) -> Optional[BaseJudge]:
        """Get judge by type."""
        return self.judges.get(judge_type)

    def list_agents(self) -> List[str]:
        """List all available agent IDs."""
        return list(self.agents.keys())

    def list_judges(self) -> List[str]:
        """List all available judge types."""
        return list(self.judges.keys())

    async def run_mock_turn(self, state: PeerRingState, user_input: str) -> Dict[str, Any]:
        """
        Run a complete mock turn for testing the full pipeline.

        This simulates the orchestrator -> agent -> governance flow
        without requiring any live LLM calls.
        """

        # Add user message to state
        user_msg = DialogueMessage(
            role=MessageRole.USER,
            content=user_input,
            timestamp=datetime.utcnow()
        )
        state.add_message(user_msg)

        # Get candidate actions from all agents
        candidates = []
        for agent_id, agent in self.agents.items():
            candidate = await agent.propose_candidate_action(state)
            if candidate:
                candidates.append(candidate)

        if not candidates:
            return {"error": "No agents proposed actions"}

        # Mock orchestrator: select highest utility candidate
        winning_candidate = max(candidates, key=lambda c: c.pedagogical_utility)
        winning_agent = self.agents[winning_candidate.agent_id]

        # Generate response
        response = await winning_agent.generate_response(state, winning_candidate)

        # Run governance checks
        governance_results = {}
        for judge_type, judge in self.judges.items():
            verdict = await judge.evaluate(
                text=response.content,
                patch=response.blackboard_patch,
                state=state
            )
            governance_results[judge_type] = verdict

        # Check if response passes all governance
        all_pass = all(verdict.verdict for verdict in governance_results.values())

        # Add agent response to state if it passes
        if all_pass:
            agent_msg = DialogueMessage(
                role=MessageRole.AGENT,
                agent_id=response.agent_id,
                content=response.content,
                think_block=response.think_block,
                blackboard_patch=response.blackboard_patch,
                governance_flags={jtype: v.verdict for jtype, v in governance_results.items()}
            )
            state.add_message(agent_msg)

        return {
            "candidates": len(candidates),
            "winner": winning_candidate.agent_id,
            "response": response,
            "governance": governance_results,
            "passed_governance": all_pass,
            "mock_turn": True
        }


# Global mock registry instance
mock_registry = MockAgentRegistry()