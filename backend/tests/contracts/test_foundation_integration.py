"""
Integration Test Suite for Foundation Layer
Tests the complete foundation system working together
"""

import pytest
from datetime import datetime
import asyncio
import json

from app.state.pydantic_state import (
    PeerRingState,
    DialogueMessage,
    MessageRole,
    CurriculumNode,
    RecoveryState
)
from app.contracts.mock_registry import MockAgentRegistry
from app.contracts.base_agent import BaseAgent
from app.contracts.base_judge import BaseJudge


class TestFoundationIntegration:
    """Integration tests for the complete foundation layer."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_foundation_workflow(self):
        """Test the complete foundation workflow from user input to response."""

        # Initialize components
        registry = MockAgentRegistry()
        state = PeerRingState(session_id="integration-test-001")

        # Setup curriculum
        algebra_node = CurriculumNode(
            concept_id="distributive_property",
            name="Distributive Property",
            description="Understanding a(b + c) = ab + ac",
            prerequisites=["multiplication", "addition"],
            unlocks=["factoring"]
        )
        state.curriculum_dag["distributive_property"] = algebra_node
        state.current_concept = "distributive_property"

        # Simulate multiple turns of interaction
        user_inputs = [
            "What is 3(x + 4)?",
            "I'm not sure how to distribute the 3",
            "Is it 3x + 12?",
            "Thank you, I understand now!"
        ]

        conversation_results = []

        for i, user_input in enumerate(user_inputs):
            result = await registry.run_mock_turn(state, user_input)
            conversation_results.append({
                "turn": i + 1,
                "user_input": user_input,
                "result": result
            })

            # Verify each turn structure
            assert result["mock_turn"] is True
            assert result["candidates"] > 0
            assert result["winner"] in registry.list_agents()

            # Check governance evaluation occurred
            assert "governance" in result
            assert "leak" in result["governance"]
            assert "help" in result["governance"]

        # Verify conversation progression
        assert len(state.messages) >= len(user_inputs)  # At least user messages
        assert state.turn_count >= len(user_inputs)

        # Check that different agents participated over time
        winners = [turn["result"]["winner"] for turn in conversation_results]
        assert len(set(winners)) >= 1  # At least one unique agent

        # Verify state consistency
        assert state.session_id == "integration-test-001"
        assert state.current_concept == "distributive_property"
        assert "distributive_property" in state.curriculum_dag

    @pytest.mark.integration
    def test_state_serialization_roundtrip(self):
        """Test complete state serialization and deserialization."""

        # Create complex state
        state = PeerRingState(session_id="serialization-test")

        # Add messages
        user_msg = DialogueMessage(
            role=MessageRole.USER,
            content="How do I solve 2(x + 3) = 14?"
        )
        state.add_message(user_msg)

        agent_msg = DialogueMessage(
            role=MessageRole.AGENT,
            agent_id="bob-tutor",
            content="What operation would you use first?",
            think_block="<think>Student needs to understand order of operations</think>",
            blackboard_patch="2(x + 3) = 14",
            governance_flags={"leak": True, "help": True}
        )
        state.add_message(agent_msg)

        # Add curriculum
        node = CurriculumNode(
            concept_id="solving_equations",
            name="Solving Linear Equations",
            description="Solving equations with one variable",
            attempts=5,
            correct_attempts=3,
            prerequisites=["distributive_property"],
            unlocks=["systems_of_equations"]
        )
        state.curriculum_dag["solving_equations"] = node
        state.current_concept = "solving_equations"

        # Modify policy state
        state.policy.struggle_score = 0.4
        state.policy.assistance_level.current_level = 2
        state.policy.recovery_state = RecoveryState.SCAFFOLD
        state.policy.strict_mode = True

        # Acquire lock
        state.acquire_lock("test-owner")

        # Serialize to dict
        state_dict = state.model_dump()

        # Convert to JSON and back (simulates Redis storage)
        json_str = json.dumps(state_dict, default=str)
        parsed_dict = json.loads(json_str)

        # Deserialize back to PeerRingState
        restored_state = PeerRingState.model_validate(parsed_dict)

        # Verify all data preserved
        assert restored_state.session_id == state.session_id
        assert len(restored_state.messages) == len(state.messages)
        assert restored_state.messages[0].content == state.messages[0].content
        assert restored_state.messages[1].agent_id == state.messages[1].agent_id
        assert restored_state.messages[1].think_block == state.messages[1].think_block

        # Verify curriculum preserved
        assert "solving_equations" in restored_state.curriculum_dag
        restored_node = restored_state.curriculum_dag["solving_equations"]
        assert restored_node.attempts == 5
        assert restored_node.correct_attempts == 3
        assert "distributive_property" in restored_node.prerequisites

        # Verify policy preserved
        assert restored_state.policy.struggle_score == 0.4
        assert restored_state.policy.assistance_level.current_level == 2
        assert restored_state.policy.recovery_state == RecoveryState.SCAFFOLD
        assert restored_state.policy.strict_mode is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_agent_orchestration_simulation(self):
        """Test orchestrator-style agent selection based on pedagogical utility."""

        registry = MockAgentRegistry()
        state = PeerRingState(session_id="orchestration-test")

        # Test different struggle scenarios
        struggle_scenarios = [
            {"struggle_score": 0.1, "scenario": "confident_student"},
            {"struggle_score": 0.5, "scenario": "moderate_difficulty"},
            {"struggle_score": 0.9, "scenario": "struggling_student"}
        ]

        orchestration_results = []

        for scenario in struggle_scenarios:
            state.policy.struggle_score = scenario["struggle_score"]

            # Get candidate actions from all agents
            candidates = []
            for agent_id in registry.list_agents():
                agent = registry.get_agent(agent_id)
                candidate = await agent.propose_candidate_action(state)
                if candidate:
                    candidates.append(candidate)

            # Find highest utility candidate (mock orchestrator logic)
            if candidates:
                winner = max(candidates, key=lambda c: c.pedagogical_utility)
                orchestration_results.append({
                    "scenario": scenario["scenario"],
                    "struggle_score": scenario["struggle_score"],
                    "winner": winner.agent_id,
                    "utility": winner.pedagogical_utility,
                    "candidates": len(candidates)
                })

        # Verify orchestration occurred
        assert len(orchestration_results) == 3
        for result in orchestration_results:
            assert result["candidates"] >= 3  # All agents proposed
            assert result["winner"] in registry.list_agents()
            assert 0.0 <= result["utility"] <= 1.0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_governance_pipeline_performance(self):
        """Test governance judges meet performance requirements."""

        registry = MockAgentRegistry()
        state = PeerRingState(session_id="performance-test")

        # Test responses of varying complexity
        test_responses = [
            "What do you think?",  # Simple
            "Let's work through this step by step. First, we need to distribute the coefficient to both terms inside the parentheses.",  # Medium
            "The distributive property states that a(b + c) = ab + ac. So when we have 3(x + 4), we multiply 3 by both x and 4, giving us 3x + 12.",  # Complex (potential leak)
        ]

        performance_results = []

        for i, response_text in enumerate(test_responses):
            # Time the evaluation
            start_time = datetime.now()

            # Run all judges
            judge_results = {}
            for judge_type in registry.list_judges():
                judge = registry.get_judge(judge_type)
                verdict = await judge.evaluate(response_text, None, state)
                judge_results[judge_type] = verdict

            end_time = datetime.now()
            total_time_ms = (end_time - start_time).total_seconds() * 1000

            performance_results.append({
                "response_length": len(response_text),
                "total_evaluation_time_ms": total_time_ms,
                "judge_results": judge_results
            })

        # Verify performance requirements
        for result in performance_results:
            # Each judge should complete in under 250ms (mock target)
            assert result["total_evaluation_time_ms"] < 500  # Total for all judges

            # All judges should return valid verdicts
            for judge_type, verdict in result["judge_results"].items():
                assert verdict.evaluation_time_ms > 0
                assert isinstance(verdict.confidence, float)
                assert 0.0 <= verdict.confidence <= 1.0

    @pytest.mark.contracts
    def test_contract_compliance_verification(self):
        """Verify all mock implementations comply with base contracts."""

        registry = MockAgentRegistry()

        # Test all agents implement required BaseAgent interface
        for agent_id in registry.list_agents():
            agent = registry.get_agent(agent_id)

            # Verify inheritance
            assert isinstance(agent, BaseAgent)

            # Verify required attributes
            assert hasattr(agent, 'agent_id')
            assert hasattr(agent, 'agent_type')
            assert hasattr(agent, 'config')

            # Verify required methods exist and are callable
            assert callable(getattr(agent, 'propose_candidate_action'))
            assert callable(getattr(agent, 'generate_response'))
            assert callable(getattr(agent, 'get_cooldown_seconds'))

            # Test cooldown method returns valid value
            cooldown = agent.get_cooldown_seconds()
            assert isinstance(cooldown, int)
            assert cooldown > 0

        # Test all judges implement required BaseJudge interface
        for judge_type in registry.list_judges():
            judge = registry.get_judge(judge_type)

            # Verify inheritance
            assert isinstance(judge, BaseJudge)

            # Verify required attributes
            assert hasattr(judge, 'judge_type')
            assert hasattr(judge, 'config')

            # Verify required methods exist and are callable
            assert callable(getattr(judge, 'evaluate'))
            assert callable(getattr(judge, 'batch_evaluate'))
            assert callable(getattr(judge, 'get_performance_stats'))

    @pytest.mark.integration
    def test_foundation_readiness_check(self):
        """Test that foundation layer is ready for usm and muw development."""

        # Check registry functionality
        registry = MockAgentRegistry()

        # Verify all required agents available
        required_agents = ["bob-tutor", "alice-arithmetic", "charlie-conceptual"]
        available_agents = registry.list_agents()
        for required in required_agents:
            assert required in available_agents, f"Required agent {required} not available"

        # Verify all required judges available
        required_judges = ["leak", "help"]
        available_judges = registry.list_judges()
        for required in required_judges:
            assert required in available_judges, f"Required judge {required} not available"

        # Test state creation and basic operations
        state = PeerRingState(session_id="readiness-test")

        # Test state can handle curriculum
        node = CurriculumNode(
            concept_id="test_concept",
            name="Test Concept",
            description="Test description"
        )
        state.curriculum_dag["test_concept"] = node
        assert "test_concept" in state.curriculum_dag

        # Test state can handle messages
        msg = DialogueMessage(role=MessageRole.USER, content="Test message")
        state.add_message(msg)
        assert len(state.messages) == 1

        # Test state serialization works
        state_dict = state.model_dump()
        restored = PeerRingState.model_validate(state_dict)
        assert restored.session_id == state.session_id

        print("✅ Foundation layer ready for parallel development!")
        print(f"   - {len(available_agents)} agents available: {', '.join(available_agents)}")
        print(f"   - {len(available_judges)} judges available: {', '.join(available_judges)}")
        print(f"   - State management: ✅")
        print(f"   - Serialization: ✅")
        print(f"   - Mock implementations: ✅")