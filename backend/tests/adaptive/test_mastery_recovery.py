"""
Tests for Curriculum Mastery DAG, Struggle Detector, and Recovery State Machine.
"""

import pytest
from datetime import datetime

from app.state.pydantic_state import (
    PeerRingState,
    CurriculumNode,
    RecoveryState,
    AssistanceLevel,
    PolicyState,
)
from app.adaptive.mastery_dag import CurriculumDAGManager
from app.adaptive.struggle_detector import StruggleDetector
from app.recovery.state_machine import RecoveryStateMachine
from app.recovery.prerequisite_backtrack import PrerequisiteBacktracker


@pytest.fixture
def base_state() -> PeerRingState:
    """Create a test state with a 3-tier curriculum DAG."""
    state = PeerRingState(
        session_id="test-mastery-recovery-session",
        user_id="student-42",
        policy=PolicyState(
            assistance_level=AssistanceLevel(current_level=1),
            recovery_state=RecoveryState.NORMAL,
            struggle_score=0.0,
            stuck_threshold=0.70,
        ),
    )

    # Concept hierarchy:
    # arithmetic_ops -> algebraic_factoring -> quadratic_equations
    dag_mgr = CurriculumDAGManager()
    dag_mgr.add_or_update_node(
        state,
        concept_id="arithmetic_ops",
        name="Arithmetic Operations",
        prerequisites=[],
        unlocks=["algebraic_factoring"],
        mastery_score=0.9,
    )
    dag_mgr.add_or_update_node(
        state,
        concept_id="algebraic_factoring",
        name="Algebraic Factoring",
        prerequisites=["arithmetic_ops"],
        unlocks=["quadratic_equations"],
        mastery_score=0.4,  # unmastered prerequisite
    )
    dag_mgr.add_or_update_node(
        state,
        concept_id="quadratic_equations",
        name="Quadratic Equations",
        prerequisites=["algebraic_factoring"],
        unlocks=[],
        mastery_score=0.1,
    )

    state.current_concept = "quadratic_equations"
    return state


class TestCurriculumDAGManager:
    """Unit tests for CurriculumDAGManager."""

    def test_add_and_retrieve_node(self, base_state: PeerRingState):
        dag_mgr = CurriculumDAGManager()
        node = dag_mgr.add_or_update_node(
            base_state,
            concept_id="linear_graphs",
            name="Linear Graphs",
            prerequisites=["arithmetic_ops"],
        )
        assert node.concept_id == "linear_graphs"
        assert "linear_graphs" in base_state.curriculum_dag
        # Symmetrical unlock check
        assert "linear_graphs" in base_state.curriculum_dag["arithmetic_ops"].unlocks

    def test_cycle_detection_valid_and_invalid(self, base_state: PeerRingState):
        dag_mgr = CurriculumDAGManager()
        assert dag_mgr.detect_cycles(base_state) is False

        # Introduce a cycle: arithmetic_ops -> algebraic_factoring -> quadratic_equations -> arithmetic_ops
        base_state.curriculum_dag["arithmetic_ops"].prerequisites.append("quadratic_equations")
        assert dag_mgr.detect_cycles(base_state) is True

    def test_concept_unlock_logic(self, base_state: PeerRingState):
        dag_mgr = CurriculumDAGManager(default_mastery_threshold=0.7)

        # arithmetic_ops has no prerequisites -> always unlocked
        assert dag_mgr.is_concept_unlocked(base_state, "arithmetic_ops") is True

        # algebraic_factoring requires arithmetic_ops (score 0.9 >= 0.7) -> unlocked
        assert dag_mgr.is_concept_unlocked(base_state, "algebraic_factoring") is True

        # quadratic_equations requires algebraic_factoring (score 0.4 < 0.7) -> locked
        assert dag_mgr.is_concept_unlocked(base_state, "quadratic_equations") is False

    def test_missing_prerequisites(self, base_state: PeerRingState):
        dag_mgr = CurriculumDAGManager()
        missing = dag_mgr.get_missing_prerequisites(base_state, "quadratic_equations")
        assert missing == ["algebraic_factoring"]

        missing_arithmetic = dag_mgr.get_missing_prerequisites(base_state, "arithmetic_ops")
        assert missing_arithmetic == []

    def test_all_unmastered_prerequisites_topological(self, base_state: PeerRingState):
        dag_mgr = CurriculumDAGManager()
        # Set arithmetic_ops to unmastered as well
        base_state.curriculum_dag["arithmetic_ops"].mastery_score = 0.2

        unmastered = dag_mgr.get_all_unmastered_prerequisites(base_state, "quadratic_equations")
        # arithmetic_ops should precede algebraic_factoring in foundational order
        assert unmastered == ["arithmetic_ops", "algebraic_factoring"]

    def test_update_mastery_ema(self, base_state: PeerRingState):
        dag_mgr = CurriculumDAGManager(ema_alpha=0.35)
        node = base_state.curriculum_dag["quadratic_equations"]
        initial_score = node.mastery_score  # 0.1

        # Student demonstrates success
        res = dag_mgr.update_mastery(base_state, "quadratic_equations", success=True)
        assert res["prism_event"] == "CURRICULUM_MASTERY_UPDATED"
        assert res["new_score"] > initial_score
        assert node.attempts == 1
        assert node.correct_attempts == 1

        # Student fails next attempt
        score_after_success = node.mastery_score
        res2 = dag_mgr.update_mastery(base_state, "quadratic_equations", success=False)
        assert res2["new_score"] < score_after_success
        assert node.attempts == 2
        assert node.correct_attempts == 1


class TestStruggleDetector:
    """Unit tests for StruggleDetector."""

    def test_low_struggle_when_successful(self, base_state: PeerRingState):
        detector = StruggleDetector()
        base_state.policy.assistance_level.current_level = 1
        base_state.policy.assistance_level.consecutive_errors = 0

        res = detector.compute_struggle_score(base_state, latency_sec=5.0)
        assert res["struggle_score"] < 0.2
        assert res["threshold_breached"] is False
        assert res["prism_event"] == "STRUGGLE_SCORE_EVALUATED"

    def test_threshold_breach_on_errors_and_ladder_elevation(self, base_state: PeerRingState):
        detector = StruggleDetector()
        base_state.policy.assistance_level.current_level = 5  # Step-by-Step
        base_state.policy.assistance_level.consecutive_errors = 3
        # Node has failed attempts
        node = base_state.curriculum_dag["quadratic_equations"]
        node.attempts = 4
        node.correct_attempts = 0

        res = detector.compute_struggle_score(
            base_state, latency_sec=50.0, explicit_help_requested=True
        )
        assert res["struggle_score"] >= 0.70
        assert res["threshold_breached"] is True
        assert res["newly_breached"] is True
        assert res["prism_event"] == "STRUGGLE_THRESHOLD_BREACHED"
        assert detector.is_stuck(base_state) is True


class TestRecoveryStateMachine:
    """Unit tests for RecoveryStateMachine."""

    def test_normal_to_scaffold_transition(self, base_state: PeerRingState):
        fsm = RecoveryStateMachine()
        base_state.policy.recovery_state = RecoveryState.NORMAL
        base_state.policy.struggle_score = 0.75
        base_state.policy.assistance_level.current_level = 2

        telemetry = fsm.evaluate_transition(base_state)
        assert telemetry["transition_occurred"] is True
        assert telemetry["final_state"] == RecoveryState.SCAFFOLD.value
        assert base_state.policy.recovery_state == RecoveryState.SCAFFOLD

    def test_scaffold_to_prerequisite_repair_when_prereqs_missing(self, base_state: PeerRingState):
        fsm = RecoveryStateMachine()
        base_state.policy.recovery_state = RecoveryState.SCAFFOLD
        base_state.policy.struggle_score = 0.88
        base_state.policy.assistance_level.current_level = 5
        # quadratic_equations has missing prerequisite 'algebraic_factoring'

        telemetry = fsm.evaluate_transition(base_state)
        assert telemetry["transition_occurred"] is True
        assert telemetry["final_state"] == RecoveryState.PREREQUISITE_REPAIR.value
        assert base_state.policy.recovery_state == RecoveryState.PREREQUISITE_REPAIR

    def test_scaffold_to_micro_teaching_when_no_missing_prereqs(self, base_state: PeerRingState):
        fsm = RecoveryStateMachine()
        # Set arithmetic_ops as current concept (it has no prerequisites)
        base_state.current_concept = "arithmetic_ops"
        base_state.policy.recovery_state = RecoveryState.SCAFFOLD
        base_state.policy.struggle_score = 0.88
        base_state.policy.assistance_level.current_level = 5

        telemetry = fsm.evaluate_transition(base_state)
        assert telemetry["transition_occurred"] is True
        assert telemetry["final_state"] == RecoveryState.MICRO_TEACHING.value
        assert base_state.policy.recovery_state == RecoveryState.MICRO_TEACHING

    def test_scaffold_to_normal_recovery(self, base_state: PeerRingState):
        fsm = RecoveryStateMachine()
        base_state.policy.recovery_state = RecoveryState.SCAFFOLD
        base_state.policy.struggle_score = 0.20
        base_state.policy.assistance_level.current_level = 1

        telemetry = fsm.evaluate_transition(base_state)
        assert telemetry["transition_occurred"] is True
        assert telemetry["final_state"] == RecoveryState.NORMAL.value
        assert base_state.policy.recovery_state == RecoveryState.NORMAL


class TestPrerequisiteBacktrackIntegration:
    """Integration test suite for Prerequisite Backtracking and Remediation."""

    def test_backtrack_and_resolution_flow(self, base_state: PeerRingState):
        dag_mgr = CurriculumDAGManager()
        backtracker = PrerequisiteBacktracker(dag_mgr)

        assert base_state.current_concept == "quadratic_equations"

        # 1. Identify target
        target = backtracker.find_repair_target(base_state, "quadratic_equations")
        assert target == "algebraic_factoring"

        # 2. Execute backtrack
        bt_res = backtracker.execute_backtrack(base_state, target)
        assert bt_res["prism_event"] == "PREREQUISITE_BACKTRACK_INITIATED"
        assert base_state.current_concept == "algebraic_factoring"
        assert base_state.policy.recovery_state == RecoveryState.PREREQUISITE_REPAIR
        assert base_state.prism_trace_metadata["recovery_stack"] == ["quadratic_equations"]

        # 3. Attempt resolution before mastery -> should fail
        premature_res = backtracker.resolve_repair(base_state)
        assert premature_res["resolved"] is False
        assert premature_res["prism_event"] == "PREREQUISITE_REPAIR_INCOMPLETE"
        assert base_state.current_concept == "algebraic_factoring"

        # 4. Student practices and achieves mastery on prerequisite
        base_state.curriculum_dag["algebraic_factoring"].mastery_score = 0.85

        # 5. Resolve repair
        resolved_res = backtracker.resolve_repair(base_state)
        assert resolved_res["resolved"] is True
        assert resolved_res["prism_event"] == "PREREQUISITE_REPAIR_COMPLETED"
        assert resolved_res["restored_concept"] == "quadratic_equations"
        assert base_state.current_concept == "quadratic_equations"
        assert base_state.policy.recovery_state == RecoveryState.SCAFFOLD
