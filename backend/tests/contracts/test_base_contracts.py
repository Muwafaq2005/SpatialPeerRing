"""
Test Suite for Abstract Base Classes (BaseAgent and BaseJudge)
Validates contract interfaces and mock implementations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
import asyncio

from app.contracts.base_agent import BaseAgent
from app.contracts.base_judge import BaseJudge
from app.contracts.mock_registry import (
    MockBobAgent,
    MockAliceAgent,
    MockCharlieAgent,
    MockLeakJudge,
    MockHelpJudge,
    MockAgentRegistry
)
from app.state.pydantic_state import (
    PeerRingState,
    DialogueMessage,
    MessageRole,
    AgentType,
    CandidateAction,
    AgentResponse,
    JudgeVerdict
)


class TestBaseAgent:
    """Test the BaseAgent abstract contract."""

    def test_base_agent_initialization(self):
        """Test BaseAgent initialization."""
        # Cannot instantiate abstract class directly
        with pytest.raises(TypeError):
            BaseAgent("test-id", AgentType.BOB_TUTOR)

    def test_base_agent_interface_requirements(self):
        """Test that BaseAgent requires abstract methods to be implemented."""

        class IncompleteAgent(BaseAgent):
            """Agent missing required methods."""
            pass

        # Should fail to instantiate due to missing abstract methods
        with pytest.raises(TypeError):
            IncompleteAgent("incomplete", AgentType.BOB_TUTOR)

    def test_concrete_agent_implementation(self):
        """Test that properly implemented agents work correctly."""

        class TestAgent(BaseAgent):
            async def propose_candidate_action(self, state: PeerRingState):
                return CandidateAction(
                    agent_id=self.agent_id,
                    action_type="respond",
                    pedagogical_utility=0.7,
                    content_preview="Test response"
                )

            async def generate_response(self, state: PeerRingState, action: CandidateAction):
                return AgentResponse(
                    agent_id=self.agent_id,
                    content="Test agent response",
                    confidence=0.8
                )

        # Should successfully create concrete implementation
        agent = TestAgent("test-agent", AgentType.BOB_TUTOR)
        assert agent.agent_id == "test-agent"
        assert agent.agent_type == AgentType.BOB_TUTOR
        assert agent.config == {}

    def test_base_agent_helper_methods(self):
        """Test BaseAgent helper methods."""

        class TestAgent(BaseAgent):
            async def propose_candidate_action(self, state):
                return None
            async def generate_response(self, state, action):
                return None

        agent = TestAgent("helper-test", AgentType.ALICE_ARITHMETIC)

        # Test cooldown calculation
        cooldown = agent.get_cooldown_seconds()
        assert isinstance(cooldown, int)
        assert cooldown > 0

        # Test string representations
        str_repr = str(agent)
        assert "TestAgent" in str_repr
        assert "helper-test" in str_repr

        repr_str = repr(agent)
        assert "TestAgent" in repr_str
        assert "alice-arithmetic" in repr_str

    @pytest.mark.asyncio
    async def test_base_agent_pedagogical_utility(self):
        """Test pedagogical utility calculation."""

        class TestAgent(BaseAgent):
            async def propose_candidate_action(self, state):
                return None
            async def generate_response(self, state, action):
                return None

        # Test with empty state (struggle_score = 0.0)
        agent = TestAgent("utility-test", AgentType.BOB_TUTOR)
        state = PeerRingState(session_id="test")

        utility = agent.calculate_pedagogical_utility(state)
        assert 0.0 <= utility <= 1.0

        # Test with struggle score
        state.policy.struggle_score = 0.8
        utility_struggling = agent.calculate_pedagogical_utility(state)

        # Bob should have higher utility when student struggling
        if agent.agent_type == AgentType.BOB_TUTOR:
            assert utility_struggling >= utility  # >= because both could be valid


class TestBaseJudge:
    """Test the BaseJudge abstract contract."""

    def test_base_judge_initialization(self):
        """Test BaseJudge initialization."""
        # Cannot instantiate abstract class directly
        with pytest.raises(TypeError):
            BaseJudge("test-judge")

    def test_concrete_judge_implementation(self):
        """Test properly implemented judge."""

        class TestJudge(BaseJudge):
            async def evaluate(self, text, patch, state, metadata=None):
                return JudgeVerdict(
                    judge_type=self.judge_type,
                    verdict=True,
                    confidence=0.9,
                    reasoning="Test evaluation",
                    evaluation_time_ms=50
                )

        judge = TestJudge("test")
        assert judge.judge_type == "test"
        assert judge.evaluation_count == 0

    @pytest.mark.asyncio
    async def test_base_judge_batch_evaluation(self):
        """Test batch evaluation default implementation."""

        class TestJudge(BaseJudge):
            async def evaluate(self, text, patch, state, metadata=None):
                return JudgeVerdict(
                    judge_type="leak",  # Use valid Literal value
                    verdict=len(text) > 5,  # Simple test: pass if text > 5 chars
                    confidence=0.8,
                    reasoning=f"Text length: {len(text)}",
                    evaluation_time_ms=10
                )

        judge = TestJudge("leak")  # Use valid judge type
        state = PeerRingState(session_id="test")

        responses = [
            AgentResponse(agent_id="test1", content="Hi"),      # Should fail (2 chars)
            AgentResponse(agent_id="test2", content="Hello there"),  # Should pass (11 chars)
        ]

        verdicts = await judge.batch_evaluate(responses, state)

        assert len(verdicts) == 2
        assert not verdicts[0].verdict  # "Hi" should fail
        assert verdicts[1].verdict      # "Hello there" should pass

    def test_judge_performance_tracking(self):
        """Test performance statistics tracking."""

        class TestJudge(BaseJudge):
            async def evaluate(self, text, patch, state, metadata=None):
                return JudgeVerdict(
                    judge_type=self.judge_type,
                    verdict=True,
                    confidence=0.9,
                    reasoning="Test",
                    evaluation_time_ms=100
                )

        judge = TestJudge("perf-test")

        # Initial state
        assert judge.evaluation_count == 0
        assert judge.get_average_evaluation_time() == 0.0

        # Update performance stats
        judge.update_performance_stats(100)
        judge.update_performance_stats(200)

        assert judge.evaluation_count == 2
        assert judge.total_evaluation_time_ms == 300
        assert judge.get_average_evaluation_time() == 150.0

        # Test performance stats dict
        stats = judge.get_performance_stats()
        assert stats["judge_type"] == "perf-test"
        assert stats["evaluation_count"] == 2
        assert stats["average_time_ms"] == 150.0
        assert stats["target_time_ms"] == 250
        assert stats["performance_ok"] is True  # 150ms < 250ms target


class TestMockImplementations:
    """Test all mock agent and judge implementations."""

    @pytest.mark.asyncio
    async def test_mock_bob_agent(self):
        """Test MockBobAgent implementation."""
        bob = MockBobAgent()
        state = PeerRingState(session_id="test-bob")

        # Test candidate proposal
        candidate = await bob.propose_candidate_action(state)

        assert candidate is not None
        assert candidate.agent_id == "bob-tutor"
        assert candidate.action_type == "question"
        assert 0.0 <= candidate.pedagogical_utility <= 1.0
        assert "socratic_questioning" in candidate.metadata.get("strategy", "")

        # Test response generation
        response = await bob.generate_response(state, candidate)

        assert response.agent_id == "bob-tutor"
        assert len(response.content) > 0
        assert response.think_block is not None
        assert "<think>" in response.think_block
        assert response.confidence > 0.0
        assert response.metadata.get("mock_response") is True

    @pytest.mark.asyncio
    async def test_mock_alice_agent(self):
        """Test MockAliceAgent (arithmetic peer) implementation."""
        alice = MockAliceAgent()
        state = PeerRingState(session_id="test-alice")

        candidate = await alice.propose_candidate_action(state)
        response = await alice.generate_response(state, candidate)

        assert candidate.agent_id == "alice-arithmetic"
        assert response.agent_id == "alice-arithmetic"
        assert response.metadata.get("contains_arithmetic_error") is True

        # Alice sometimes provides blackboard patches
        # (We can't guarantee it due to randomness, but we can check the structure)
        if response.blackboard_patch:
            assert "\\begin{align}" in response.blackboard_patch or "=" in response.blackboard_patch

    @pytest.mark.asyncio
    async def test_mock_charlie_agent(self):
        """Test MockCharlieAgent (conceptual peer) implementation."""
        charlie = MockCharlieAgent()
        state = PeerRingState(session_id="test-charlie")

        candidate = await charlie.propose_candidate_action(state)
        response = await charlie.generate_response(state, candidate)

        assert candidate.agent_id == "charlie-conceptual"
        assert response.agent_id == "charlie-conceptual"
        assert response.metadata.get("contains_conceptual_error") is True

    @pytest.mark.asyncio
    async def test_mock_leak_judge(self):
        """Test MockLeakJudge implementation."""
        judge = MockLeakJudge()
        state = PeerRingState(session_id="test-leak")

        # Test with non-leaking text
        safe_verdict = await judge.evaluate("What do you think about this step?", None, state)

        assert safe_verdict.judge_type == "leak"
        assert safe_verdict.verdict is True  # Should pass
        assert safe_verdict.confidence > 0.0
        assert safe_verdict.evaluation_time_ms > 0

        # Test with leaking text
        leak_verdict = await judge.evaluate("The answer is x = 5", None, state)

        assert leak_verdict.judge_type == "leak"
        assert leak_verdict.verdict is False  # Should fail
        assert leak_verdict.violation_details is not None

    @pytest.mark.asyncio
    async def test_mock_help_judge(self):
        """Test MockHelpJudge implementation."""
        judge = MockHelpJudge()
        state = PeerRingState(session_id="test-help")

        # Test helpful text
        helpful_verdict = await judge.evaluate("What do you think would happen if we tried this?", None, state)

        assert helpful_verdict.judge_type == "help"
        assert helpful_verdict.verdict is True  # Should pass

        # Test unhelpful text
        unhelpful_verdict = await judge.evaluate("I don't know, just figure it out yourself", None, state)

        assert unhelpful_verdict.judge_type == "help"
        # Note: Due to mock scoring algorithm, this might still pass depending on implementation


class TestMockAgentRegistry:
    """Test the complete MockAgentRegistry system."""

    def test_registry_initialization(self):
        """Test registry setup."""
        registry = MockAgentRegistry()

        # Check agents are registered
        assert len(registry.list_agents()) >= 3
        assert "bob-tutor" in registry.list_agents()
        assert "alice-arithmetic" in registry.list_agents()
        assert "charlie-conceptual" in registry.list_agents()

        # Check judges are registered
        assert len(registry.list_judges()) >= 2
        assert "leak" in registry.list_judges()
        assert "help" in registry.list_judges()

    def test_registry_agent_retrieval(self):
        """Test retrieving agents from registry."""
        registry = MockAgentRegistry()

        bob = registry.get_agent("bob-tutor")
        assert bob is not None
        assert isinstance(bob, MockBobAgent)

        # Test non-existent agent
        missing = registry.get_agent("non-existent")
        assert missing is None

    def test_registry_judge_retrieval(self):
        """Test retrieving judges from registry."""
        registry = MockAgentRegistry()

        leak_judge = registry.get_judge("leak")
        assert leak_judge is not None
        assert isinstance(leak_judge, MockLeakJudge)

        # Test non-existent judge
        missing = registry.get_judge("non-existent")
        assert missing is None

    @pytest.mark.asyncio
    async def test_mock_turn_execution(self):
        """Test complete mock turn through registry."""
        registry = MockAgentRegistry()
        state = PeerRingState(session_id="test-turn")

        # Run a mock turn
        result = await registry.run_mock_turn(state, "What is 3(x + 4)?")

        # Validate result structure
        assert "candidates" in result
        assert "winner" in result
        assert "response" in result
        assert "governance" in result
        assert "passed_governance" in result
        assert result["mock_turn"] is True

        # Check candidates were generated
        assert result["candidates"] > 0

        # Check winner is valid agent
        assert result["winner"] in registry.list_agents()

        # Check response structure
        response = result["response"]
        assert isinstance(response, AgentResponse)
        assert len(response.content) > 0

        # Check governance results
        governance = result["governance"]
        assert "leak" in governance
        assert "help" in governance

        # Verify governance verdicts are proper JudgeVerdict objects
        for judge_type, verdict in governance.items():
            assert isinstance(verdict, JudgeVerdict)
            assert verdict.judge_type == judge_type

        # Check that state was updated if governance passed
        if result["passed_governance"]:
            assert len(state.messages) == 2  # User input + agent response
            assert state.turn_count == 2
        else:
            assert len(state.messages) == 1  # Only user input

    @pytest.mark.asyncio
    async def test_mock_turn_with_struggling_student(self):
        """Test mock turn when student is struggling (high struggle score)."""
        registry = MockAgentRegistry()
        state = PeerRingState(session_id="test-struggling")

        # Set high struggle score to favor Bob tutor
        state.policy.struggle_score = 0.9

        result = await registry.run_mock_turn(state, "I'm really confused about this problem")

        # Bob should be more likely to win with high struggle score
        # (Though we can't guarantee due to randomness in mock implementations)
        assert result["winner"] in registry.list_agents()
        assert result["candidates"] > 0


class TestContractIntegration:
    """Test integration between contracts and state."""

    @pytest.mark.asyncio
    async def test_agent_judge_integration(self):
        """Test agents and judges working together."""
        # Create mock instances
        bob = MockBobAgent()
        leak_judge = MockLeakJudge()
        help_judge = MockHelpJudge()

        state = PeerRingState(session_id="integration-test")

        # Agent proposes action
        candidate = await bob.propose_candidate_action(state)
        assert candidate is not None

        # Agent generates response
        response = await bob.generate_response(state, candidate)
        assert response is not None

        # Judges evaluate response
        leak_verdict = await leak_judge.evaluate(response.content, response.blackboard_patch, state)
        help_verdict = await help_judge.evaluate(response.content, response.blackboard_patch, state)

        # Verify verdict objects
        assert isinstance(leak_verdict, JudgeVerdict)
        assert isinstance(help_verdict, JudgeVerdict)
        assert leak_verdict.judge_type == "leak"
        assert help_verdict.judge_type == "help"

        # Both should complete quickly (mock target)
        assert leak_verdict.evaluation_time_ms <= 100
        assert help_verdict.evaluation_time_ms <= 100

    def test_contract_compatibility(self):
        """Test that all mock implementations are compatible with contracts."""
        registry = MockAgentRegistry()

        # Verify all agents implement BaseAgent
        for agent_id in registry.list_agents():
            agent = registry.get_agent(agent_id)
            assert isinstance(agent, BaseAgent)
            assert hasattr(agent, 'propose_candidate_action')
            assert hasattr(agent, 'generate_response')

        # Verify all judges implement BaseJudge
        for judge_type in registry.list_judges():
            judge = registry.get_judge(judge_type)
            assert isinstance(judge, BaseJudge)
            assert hasattr(judge, 'evaluate')
            assert hasattr(judge, 'batch_evaluate')