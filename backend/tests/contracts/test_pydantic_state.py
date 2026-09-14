"""
Test Suite for Core Pydantic State Schema
Validates state serialization, curriculum tracking, and policy management
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
import json
from pydantic import ValidationError

from app.state.pydantic_state import (
    PeerRingState,
    DialogueMessage,
    MessageRole,
    AgentType,
    CandidateAction,
    AgentResponse,
    JudgeVerdict,
    CurriculumNode,
    AssistanceLevel,
    PolicyState,
    TurnLockStatus,
    RecoveryState
)


class TestPeerRingState:
    """Test the core PeerRingState schema."""

    def test_empty_state_creation(self):
        """Test creating an empty PeerRingState."""
        state = PeerRingState(session_id="test-session-123")

        assert state.session_id == "test-session-123"
        assert state.user_id is None
        assert len(state.messages) == 0
        assert state.current_step == 0
        assert len(state.curriculum_dag) == 0
        assert state.current_concept is None
        assert state.turn_count == 0
        assert state.version == "0.1.0"
        assert state.foundation_layer == "core-contracts-and-state"

    def test_state_with_messages(self):
        """Test state with dialogue messages."""
        state = PeerRingState(session_id="test-session")

        # Add user message
        user_msg = DialogueMessage(
            role=MessageRole.USER,
            content="What is 3(x + 4)?",
            metadata={"input_method": "text"}
        )
        state.add_message(user_msg)

        # Add agent message
        agent_msg = DialogueMessage(
            role=MessageRole.AGENT,
            agent_id="bob-tutor",
            content="What do you think happens when we distribute the 3?",
            think_block="<think>Student needs guidance on distributive property</think>",
            governance_flags={"leak": True, "help": True}
        )
        state.add_message(agent_msg)

        assert len(state.messages) == 2
        assert state.turn_count == 2
        assert state.messages[0].role == MessageRole.USER
        assert state.messages[1].role == MessageRole.AGENT
        assert state.messages[1].agent_id == "bob-tutor"

    def test_curriculum_dag_operations(self):
        """Test curriculum DAG creation and mastery tracking."""
        state = PeerRingState(session_id="test-session")

        # Add curriculum nodes
        distributive_node = CurriculumNode(
            concept_id="distributive_property",
            name="Distributive Property",
            description="Understanding a(b + c) = ab + ac",
            prerequisites=["multiplication", "addition"],
            unlocks=["factoring", "solving_equations"]
        )

        state.curriculum_dag["distributive_property"] = distributive_node
        state.current_concept = "distributive_property"

        # Test mastery updates
        assert distributive_node.mastery_score == 0.0
        assert distributive_node.attempts == 0

        # Simulate failed attempt
        state.update_mastery("distributive_property", success=False)
        assert distributive_node.attempts == 1
        assert distributive_node.correct_attempts == 0
        assert distributive_node.mastery_score == 0.0

        # Simulate successful attempt
        state.update_mastery("distributive_property", success=True)
        assert distributive_node.attempts == 2
        assert distributive_node.correct_attempts == 1
        assert distributive_node.mastery_score == 0.5

    def test_struggle_score_calculation(self):
        """Test struggle score calculation algorithm."""
        state = PeerRingState(session_id="test-session")

        # Add a curriculum node with some failure history
        node = CurriculumNode(
            concept_id="algebra_basics",
            name="Algebra Basics",
            description="Basic algebraic operations",
            attempts=5,
            correct_attempts=1  # 80% failure rate
        )
        state.curriculum_dag["algebra_basics"] = node
        state.current_concept = "algebra_basics"

        # Set consecutive errors
        state.policy.assistance_level.consecutive_errors = 2

        # Calculate struggle score
        struggle = state.calculate_struggle_score()

        # Should be high due to low success rate and consecutive errors
        assert struggle > 0.5
        assert struggle <= 1.0
        assert state.policy.struggle_score == struggle

    def test_recent_messages_retrieval(self):
        """Test getting recent messages from dialogue history."""
        state = PeerRingState(session_id="test-session")

        # Add multiple messages
        for i in range(10):
            msg = DialogueMessage(
                role=MessageRole.USER if i % 2 == 0 else MessageRole.AGENT,
                content=f"Message {i}",
                agent_id=f"agent-{i}" if i % 2 == 1 else None
            )
            state.add_message(msg)

        # Test recent message retrieval
        recent_5 = state.get_recent_messages(5)
        assert len(recent_5) == 5
        assert recent_5[0].content == "Message 5"
        assert recent_5[-1].content == "Message 9"

        # Test with count larger than available messages
        all_messages = state.get_recent_messages(20)
        assert len(all_messages) == 10

    def test_turn_lock_operations(self):
        """Test turn lock acquisition and release."""
        state = PeerRingState(session_id="test-session")

        # Initially unlocked
        assert not state.is_locked()
        assert state.turn_lock.lock_owner is None

        # Acquire lock
        success = state.acquire_lock("test-owner")
        assert success
        assert state.is_locked()
        assert state.turn_lock.lock_owner == "test-owner"
        assert state.turn_lock.locked

        # Try to acquire again (should fail)
        success2 = state.acquire_lock("other-owner")
        assert not success2
        assert state.turn_lock.lock_owner == "test-owner"  # Unchanged

        # Release lock
        state.release_lock()
        assert not state.is_locked()
        assert state.turn_lock.lock_owner is None

    def test_policy_state_management(self):
        """Test policy state and assistance level management."""
        state = PeerRingState(session_id="test-session")

        # Test initial policy state
        assert state.policy.recovery_state == RecoveryState.NORMAL
        assert state.policy.assistance_level.current_level == 1
        assert not state.policy.strict_mode
        assert state.policy.struggle_score == 0.0

        # Test policy modifications
        state.policy.strict_mode = True
        state.policy.assistance_level.current_level = 3
        state.policy.recovery_state = RecoveryState.SCAFFOLD

        assert state.policy.strict_mode
        assert state.policy.assistance_level.current_level == 3
        assert state.policy.recovery_state == RecoveryState.SCAFFOLD

    def test_state_serialization(self):
        """Test JSON serialization and deserialization."""
        # Create a complex state
        state = PeerRingState(session_id="test-serialization")

        # Add a message
        msg = DialogueMessage(
            role=MessageRole.AGENT,
            agent_id="bob-tutor",
            content="Test message",
            think_block="<think>Test thinking</think>"
        )
        state.add_message(msg)

        # Add curriculum node
        node = CurriculumNode(
            concept_id="test_concept",
            name="Test Concept",
            description="For testing serialization",
            attempts=3,
            correct_attempts=2
        )
        state.curriculum_dag["test_concept"] = node

        # Modify policy
        state.policy.struggle_score = 0.6
        state.policy.strict_mode = True

        # Serialize to JSON
        state_dict = state.model_dump()
        json_str = json.dumps(state_dict, default=str)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["session_id"] == "test-serialization"
        assert len(parsed["messages"]) == 1
        assert "test_concept" in parsed["curriculum_dag"]

        # Deserialize back to PeerRingState
        restored_state = PeerRingState.model_validate(parsed)

        assert restored_state.session_id == state.session_id
        assert len(restored_state.messages) == len(state.messages)
        assert restored_state.policy.struggle_score == state.policy.struggle_score
        assert "test_concept" in restored_state.curriculum_dag


class TestDialogueMessage:
    """Test DialogueMessage model."""

    def test_message_creation(self):
        """Test creating dialogue messages."""
        msg = DialogueMessage(
            role=MessageRole.USER,
            content="Hello, world!"
        )

        assert msg.role == MessageRole.USER
        assert msg.content == "Hello, world!"
        assert msg.agent_id is None
        assert msg.think_block is None
        assert msg.id is not None  # Auto-generated
        assert isinstance(msg.timestamp, datetime)

    def test_agent_message_with_think_block(self):
        """Test agent message with Pólya deliberation."""
        msg = DialogueMessage(
            role=MessageRole.AGENT,
            agent_id="bob-tutor",
            content="What do you think about this?",
            think_block="<think>Student needs gentle guidance</think>",
            blackboard_patch="\\frac{3x + 12}{3} = x + 4",
            governance_flags={"leak": True, "help": True}
        )

        assert msg.agent_id == "bob-tutor"
        assert msg.think_block == "<think>Student needs gentle guidance</think>"
        assert msg.blackboard_patch == "\\frac{3x + 12}{3} = x + 4"
        assert msg.governance_flags["leak"] is True
        assert msg.governance_flags["help"] is True

    def test_message_immutability(self):
        """Test that messages are frozen (immutable)."""
        msg = DialogueMessage(
            role=MessageRole.USER,
            content="Test message"
        )

        # Should not be able to modify frozen model
        with pytest.raises(ValidationError):
            msg.content = "Modified content"


class TestCandidateAction:
    """Test CandidateAction model."""

    def test_candidate_action_creation(self):
        """Test creating candidate actions."""
        action = CandidateAction(
            agent_id="bob-tutor",
            action_type="question",
            pedagogical_utility=0.8,
            content_preview="What do you think would happen if..."
        )

        assert action.agent_id == "bob-tutor"
        assert action.action_type == "question"
        assert action.pedagogical_utility == 0.8
        assert action.cooldown_penalty == 0.0  # Default

    def test_candidate_action_validation(self):
        """Test candidate action field validation."""
        # Test valid utility scores
        action1 = CandidateAction(
            agent_id="test",
            action_type="respond",
            pedagogical_utility=0.0,
            content_preview="Preview"
        )
        assert action1.pedagogical_utility == 0.0

        action2 = CandidateAction(
            agent_id="test",
            action_type="respond",
            pedagogical_utility=1.0,
            content_preview="Preview"
        )
        assert action2.pedagogical_utility == 1.0

        # Test invalid utility scores should be validated by Pydantic
        with pytest.raises(ValidationError):
            CandidateAction(
                agent_id="test",
                action_type="respond",
                pedagogical_utility=1.5,  # > 1.0
                content_preview="Preview"
            )


class TestCurriculumNode:
    """Test CurriculumNode model."""

    def test_curriculum_node_creation(self):
        """Test creating curriculum nodes."""
        node = CurriculumNode(
            concept_id="distributive_property",
            name="Distributive Property",
            description="Understanding a(b + c) = ab + ac"
        )

        assert node.concept_id == "distributive_property"
        assert node.mastery_score == 0.0  # Default
        assert node.attempts == 0  # Default
        assert len(node.prerequisites) == 0  # Default empty list
        assert len(node.unlocks) == 0  # Default empty list

    def test_curriculum_node_with_dag_relationships(self):
        """Test curriculum node with DAG prerequisites and unlocks."""
        node = CurriculumNode(
            concept_id="quadratic_formula",
            name="Quadratic Formula",
            description="Solving ax² + bx + c = 0",
            prerequisites=["factoring", "completing_square"],
            unlocks=["conic_sections", "polynomial_graphs"]
        )

        assert "factoring" in node.prerequisites
        assert "completing_square" in node.prerequisites
        assert "conic_sections" in node.unlocks
        assert "polynomial_graphs" in node.unlocks

    def test_mastery_score_bounds(self):
        """Test mastery score validation bounds."""
        node = CurriculumNode(
            concept_id="test",
            name="Test",
            description="Test node",
            mastery_score=0.5
        )
        assert node.mastery_score == 0.5

        # Test bounds
        node_min = CurriculumNode(
            concept_id="test_min",
            name="Test Min",
            description="Test minimum",
            mastery_score=0.0
        )
        assert node_min.mastery_score == 0.0

        node_max = CurriculumNode(
            concept_id="test_max",
            name="Test Max",
            description="Test maximum",
            mastery_score=1.0
        )
        assert node_max.mastery_score == 1.0