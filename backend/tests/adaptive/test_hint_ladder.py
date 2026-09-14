"""
Unit and trajectory tests for Assistance Ladder Controller.
(feature/assistance-hint-ladder)

Verifies:
1. Ladder level bounds and human-readable names.
2. Progressive scaffolding escalation (step_up) and fading (step_down).
3. Return to independence on concept mastery.
4. Behavior-driven turn evaluation (errors, explicit requests, latency).
5. Multi-turn student trajectory simulation.
"""

import pytest
from datetime import datetime

from app.adaptive.hint_ladder import AssistanceLadderController
from app.state.pydantic_state import (
    PeerRingState,
    PolicyState,
    AssistanceLevel,
    CurriculumNode,
)


@pytest.fixture
def base_state():
    """Create a state fixture with default AssistanceLevel (Level 1)."""
    return PeerRingState(
        session_id="test-ladder-session",
        policy=PolicyState(
            assistance_level=AssistanceLevel(current_level=1),
            struggle_score=0.2
        )
    )


class TestAssistanceLadderController:
    """Test core ladder state manipulation."""

    def test_level_bounds_and_names(self, base_state):
        controller = AssistanceLadderController()
        assert controller.get_current_level(base_state) == 1
        assert controller.get_level_name(base_state) == "Independent"

    def test_step_up_escalation_and_bounds(self, base_state):
        controller = AssistanceLadderController()

        # Step up from 1 to 2
        lvl = controller.step_up(base_state, "test_reason")
        assert lvl == 2
        assert controller.get_current_level(base_state) == 2
        assert controller.get_level_name(base_state) == "Gentle Nudge"
        assert base_state.policy.assistance_level.transitions_today == 1
        assert base_state.policy.assistance_level.last_escalation is not None

        # Escalate to maximum (Level 6)
        for _ in range(10):
            controller.step_up(base_state, "escalate_to_max")

        assert controller.get_current_level(base_state) == 6
        assert controller.get_level_name(base_state) == "Direct Instruction"

    def test_step_down_fading_and_bounds(self, base_state):
        controller = AssistanceLadderController()
        base_state.policy.assistance_level.current_level = 4

        # Step down from 4 to 3
        lvl = controller.step_down(base_state, "test_fading")
        assert lvl == 3
        assert controller.get_level_name(base_state) == "Guiding Question"

        # De-escalate past minimum (Level 1)
        for _ in range(10):
            controller.step_down(base_state, "deescalate_to_min")

        assert controller.get_current_level(base_state) == 1
        assert controller.get_level_name(base_state) == "Independent"

    def test_return_to_independence(self, base_state):
        controller = AssistanceLadderController()
        base_state.policy.assistance_level.current_level = 5
        base_state.policy.assistance_level.consecutive_errors = 3

        reset_lvl = controller.return_to_independence(base_state, "concept_mastered")
        assert reset_lvl == 1
        assert controller.get_current_level(base_state) == 1
        assert base_state.policy.assistance_level.consecutive_errors == 0


class TestTurnEvaluationTransitions:
    """Test turn-by-turn metric analysis and automatic transitions."""

    def test_explicit_help_causes_immediate_escalation(self, base_state):
        controller = AssistanceLadderController()
        assert controller.get_current_level(base_state) == 1

        telem = controller.evaluate_turn_interaction(
            base_state, explicit_help_requested=True
        )

        assert telem["transition_occurred"] is True
        assert telem["action_taken"] == "escalated"
        assert telem["reason"] == "explicit_help_requested"
        assert controller.get_current_level(base_state) == 2

    def test_consecutive_errors_trigger_escalation(self, base_state):
        controller = AssistanceLadderController(error_threshold_to_escalate=2)
        assert controller.get_current_level(base_state) == 1

        # Error 1: Does not reach threshold of 2
        telem1 = controller.evaluate_turn_interaction(base_state, student_success=False)
        assert telem1["transition_occurred"] is False
        assert controller.get_current_level(base_state) == 1

        # Error 2: Reaches threshold -> escalates to Level 2
        telem2 = controller.evaluate_turn_interaction(base_state, student_success=False)
        assert telem2["transition_occurred"] is True
        assert telem2["action_taken"] == "escalated"
        assert controller.get_current_level(base_state) == 2

    def test_consecutive_successes_trigger_deescalation(self, base_state):
        controller = AssistanceLadderController(success_threshold_to_deescalate=2)
        base_state.policy.assistance_level.current_level = 3

        # Success 1: Does not reach threshold of 2
        telem1 = controller.evaluate_turn_interaction(base_state, student_success=True)
        assert telem1["transition_occurred"] is False
        assert controller.get_current_level(base_state) == 3

        # Success 2: Reaches threshold -> fades scaffolding to Level 2
        telem2 = controller.evaluate_turn_interaction(base_state, student_success=True)
        assert telem2["transition_occurred"] is True
        assert telem2["action_taken"] == "de-escalated"
        assert controller.get_current_level(base_state) == 2

    def test_hesitation_latency_escalation(self, base_state):
        controller = AssistanceLadderController(hesitation_latency_sec=40.0)
        base_state.policy.assistance_level.current_level = 1

        telem = controller.evaluate_turn_interaction(base_state, latency_sec=45.0)
        assert telem["transition_occurred"] is True
        assert telem["action_taken"] == "escalated"
        assert controller.get_current_level(base_state) == 2


class TestStudentTrajectorySimulation:
    """Simulate a complete student trajectory through scaffolding escalation and fading."""

    def test_full_learning_trajectory(self, base_state):
        controller = AssistanceLadderController(
            error_threshold_to_escalate=2,
            success_threshold_to_deescalate=2
        )

        trajectory_events = [
            # 1. Starts Independent
            ("initial_attempt", True, False, 15.0),    # success -> Level 1
            # 2. Encounters harder problem, fails twice
            ("hard_step_err1", False, False, 20.0),    # error 1 -> Level 1
            ("hard_step_err2", False, False, 25.0),    # error 2 -> Level 2 (Gentle Nudge)
            # 3. Asks for explicit hint
            ("asks_for_hint", None, True, 10.0),       # explicit -> Level 3 (Guiding Question)
            # 4. Fails again twice
            ("still_stuck_1", False, False, 30.0),     # error 1 -> Level 3
            ("still_stuck_2", False, False, 35.0),     # error 2 -> Level 4 (Worked Example)
            # 5. Understands worked example, succeeds twice
            ("success_1", True, False, 18.0),          # success 1 -> Level 4
            ("success_2", True, False, 12.0),          # success 2 -> Level 3 (Guiding Question)
            ("success_3", True, False, 10.0),          # success 1 -> Level 3
            ("success_4", True, False, 8.0),           # success 2 -> Level 2 (Gentle Nudge)
        ]

        observed_levels = []
        for name, success, explicit_help, latency in trajectory_events:
            telem = controller.evaluate_turn_interaction(
                base_state,
                student_success=success,
                explicit_help_requested=explicit_help,
                latency_sec=latency
            )
            observed_levels.append(telem["final_level"])

        # Verify progression peaked at Level 4 (Worked Example) and faded back down to Level 2
        assert max(observed_levels) == 4
        assert observed_levels[-1] == 2

        # Concept master reset to Level 1
        controller.return_to_independence(base_state, "distributive_law_mastered")
        assert controller.get_current_level(base_state) == 1
