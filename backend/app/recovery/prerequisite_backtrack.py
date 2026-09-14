"""
Prerequisite Backtrack Manager.

Manages curriculum graph backtracking when a student is blocked by an unmastered
foundational prerequisite. Maintains a recovery stack to navigate back to the original
concept once foundational gaps are repaired.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.state.pydantic_state import PeerRingState, RecoveryState
from app.adaptive.mastery_dag import CurriculumDAGManager

logger = logging.getLogger(__name__)


class PrerequisiteBacktracker:
    """
    Handles automated curriculum backtracking and recovery stack resolution.
    """

    def __init__(self, dag_manager: Optional[CurriculumDAGManager] = None):
        self.dag_manager = dag_manager or CurriculumDAGManager()

    def find_repair_target(
        self, state: PeerRingState, current_concept_id: str, threshold: Optional[float] = None
    ) -> Optional[str]:
        """
        Identify the deepest unmastered prerequisite blocking the current concept.
        Returns the concept_id to backtrack to, or None if all prerequisites are mastered.
        """
        unmastered = self.dag_manager.get_all_unmastered_prerequisites(
            state, current_concept_id, threshold=threshold
        )
        if not unmastered:
            return None
        # Return the earliest/deepest prerequisite in dependency chain
        return unmastered[0]

    def execute_backtrack(
        self, state: PeerRingState, target_concept_id: str
    ) -> Dict[str, Any]:
        """
        Execute curriculum backtrack:
        - Push current concept onto recovery stack
        - Point current_concept to target_concept_id
        - Transition recovery state to PREREQUISITE_REPAIR
        """
        original_concept = state.current_concept
        if original_concept is None:
            raise ValueError("Cannot execute backtrack when state.current_concept is None")

        if target_concept_id not in state.curriculum_dag:
            raise KeyError(f"Target concept '{target_concept_id}' does not exist in curriculum DAG")

        recovery_stack = state.prism_trace_metadata.setdefault("recovery_stack", [])
        recovery_stack.append(original_concept)

        state.current_concept = target_concept_id
        state.policy.recovery_state = RecoveryState.PREREQUISITE_REPAIR
        # Reset assistance ladder for fresh approach at prerequisite concept
        state.policy.assistance_level.current_level = 2
        state.policy.assistance_level.consecutive_errors = 0
        state.last_updated = datetime.utcnow()

        logger.warning(
            f"Curriculum backtracked: '{original_concept}' -> '{target_concept_id}' for prerequisite repair"
        )

        telemetry = {
            "original_concept": original_concept,
            "target_concept": target_concept_id,
            "stack_depth": len(recovery_stack),
            "new_recovery_state": state.policy.recovery_state.value,
            "prism_event": "PREREQUISITE_BACKTRACK_INITIATED",
        }
        return telemetry

    def resolve_repair(
        self, state: PeerRingState, threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Resolve repair session:
        - Check if current repair concept has achieved mastery
        - If mastered, pop original parent concept from recovery stack and restore
        - Transition recovery state back to SCAFFOLD
        """
        thresh = threshold if threshold is not None else self.dag_manager.default_mastery_threshold
        current_id = state.current_concept
        current_node = state.curriculum_dag.get(current_id) if current_id else None

        if not current_node or current_node.mastery_score < thresh:
            return {
                "resolved": False,
                "reason": f"Current repair concept '{current_id}' has not met mastery threshold ({thresh})",
                "current_mastery": current_node.mastery_score if current_node else 0.0,
                "prism_event": "PREREQUISITE_REPAIR_INCOMPLETE",
            }

        recovery_stack: List[str] = state.prism_trace_metadata.get("recovery_stack", [])
        if not recovery_stack:
            # Nothing to pop, transition to SCAFFOLD
            state.policy.recovery_state = RecoveryState.SCAFFOLD
            return {
                "resolved": True,
                "restored_concept": current_id,
                "recovery_state": state.policy.recovery_state.value,
                "reason": "recovery_stack_empty_scaffold_retained",
                "prism_event": "PREREQUISITE_REPAIR_COMPLETED",
            }

        restored_concept = recovery_stack.pop()
        state.current_concept = restored_concept
        state.policy.recovery_state = RecoveryState.SCAFFOLD
        # Set ladder to step-by-step or guiding question for gentle resumption
        state.policy.assistance_level.current_level = 3
        state.policy.assistance_level.consecutive_errors = 0
        state.last_updated = datetime.utcnow()

        logger.info(
            f"Prerequisite repair resolved for '{current_id}'. Restored concept: '{restored_concept}'"
        )

        telemetry = {
            "resolved": True,
            "completed_repair_concept": current_id,
            "restored_concept": restored_concept,
            "remaining_stack_depth": len(recovery_stack),
            "new_recovery_state": state.policy.recovery_state.value,
            "prism_event": "PREREQUISITE_REPAIR_COMPLETED",
        }
        return telemetry
