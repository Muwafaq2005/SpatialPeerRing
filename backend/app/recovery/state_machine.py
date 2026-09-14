"""
Recovery State Machine.

Orchestrates pedagogical recovery states for struggling students:
- NORMAL: Standard peer-ring socratic dialogue
- SCAFFOLD: Elevated assistance ladder hints and guided peer models
- PREREQUISITE_REPAIR: Curriculum backtrack when missing foundational concepts
- MICRO_TEACHING: Focused 1-on-1 concept walkthrough when stuck despite ladder escalation
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.state.pydantic_state import PeerRingState, RecoveryState
from app.adaptive.mastery_dag import CurriculumDAGManager

logger = logging.getLogger(__name__)


class RecoveryStateMachine:
    """
    Finite state machine governing adaptive pedagogical recovery.
    """

    def __init__(
        self,
        dag_manager: Optional[CurriculumDAGManager] = None,
        recovery_exit_threshold: float = 0.35,
        severe_struggle_threshold: float = 0.85,
    ):
        self.dag_manager = dag_manager or CurriculumDAGManager()
        self.recovery_exit_threshold = recovery_exit_threshold
        self.severe_struggle_threshold = severe_struggle_threshold

    def evaluate_transition(
        self,
        state: PeerRingState,
        prerequisite_repaired: bool = False,
        micro_teaching_completed: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate current learning state and trigger appropriate recovery transitions.
        """
        curr_state = state.policy.recovery_state
        new_state = curr_state
        reason = "no_transition_condition_met"
        transition_occurred = False

        struggle = state.policy.struggle_score
        stuck_thresh = state.policy.stuck_threshold
        ladder_level = state.policy.assistance_level.current_level

        # Check for missing direct prerequisites in current concept
        missing_prereqs = []
        if state.current_concept:
            missing_prereqs = self.dag_manager.get_missing_prerequisites(
                state, state.current_concept
            )

        if curr_state == RecoveryState.NORMAL:
            if struggle >= stuck_thresh:
                if ladder_level >= 5 and missing_prereqs:
                    new_state = RecoveryState.PREREQUISITE_REPAIR
                    reason = f"severe_struggle_with_missing_prereqs ({', '.join(missing_prereqs)})"
                elif ladder_level >= 5 and not missing_prereqs:
                    new_state = RecoveryState.MICRO_TEACHING
                    reason = "severe_struggle_isolated_concept"
                else:
                    new_state = RecoveryState.SCAFFOLD
                    reason = f"struggle_threshold_breached ({struggle:.2f} >= {stuck_thresh:.2f})"

        elif curr_state == RecoveryState.SCAFFOLD:
            if struggle < self.recovery_exit_threshold and ladder_level <= 2:
                new_state = RecoveryState.NORMAL
                reason = f"struggle_resolved ({struggle:.2f} < {self.recovery_exit_threshold:.2f})"
            elif ladder_level >= 5 or struggle >= self.severe_struggle_threshold:
                if missing_prereqs:
                    new_state = RecoveryState.PREREQUISITE_REPAIR
                    reason = f"scaffolding_insufficient_missing_prereqs ({', '.join(missing_prereqs)})"
                else:
                    new_state = RecoveryState.MICRO_TEACHING
                    reason = "scaffolding_insufficient_needs_micro_teaching"

        elif curr_state == RecoveryState.PREREQUISITE_REPAIR:
            if prerequisite_repaired or (state.current_concept and not missing_prereqs):
                new_state = RecoveryState.SCAFFOLD
                reason = "prerequisite_repaired_returning_to_scaffold"

        elif curr_state == RecoveryState.MICRO_TEACHING:
            if micro_teaching_completed or struggle < self.recovery_exit_threshold:
                new_state = RecoveryState.SCAFFOLD
                reason = "micro_teaching_completed_stepping_down"

        if new_state != curr_state:
            transition_occurred = True
            state.policy.recovery_state = new_state
            state.last_updated = datetime.utcnow()
            logger.info(
                f"Recovery FSM transition: {curr_state.value} -> {new_state.value} (Reason: {reason})"
            )

        telemetry = {
            "initial_state": curr_state.value,
            "final_state": new_state.value,
            "transition_occurred": transition_occurred,
            "reason": reason,
            "struggle_score": struggle,
            "ladder_level": ladder_level,
            "missing_prerequisites": missing_prereqs,
            "prism_event": "RECOVERY_STATE_TRANSITION",
        }

        return telemetry

    def force_state(self, state: PeerRingState, target_state: RecoveryState, reason: str) -> None:
        """
        Manually override recovery state (e.g. for testing or teacher overrides).
        """
        old_state = state.policy.recovery_state
        state.policy.recovery_state = target_state
        state.last_updated = datetime.utcnow()
        logger.warning(
            f"Recovery FSM forced transition: {old_state.value} -> {target_state.value} (Reason: {reason})"
        )
