"""
Assistance Hint Ladder Controller.

Manages dynamic progression and de-escalation across the 6-level Assistance Ladder:
1. Independent: High-level encouragement / open diagnostic question
2. Gentle Nudge: Focus on invariant pattern or constraint
3. Guiding Question: Targeted leading question on immediate next operation
4. Worked Example: Parallel analogous sub-problem
5. Step-by-Step: Binary choices / micro-steps
6. Direct Instruction: Foundational definition / conceptual review

Transitions occur dynamically based on:
- Consecutive student errors
- Explicit help demands
- Response latency (hesitation detection)
- Demonstrated competence (stepping down to prevent hint dependency)
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.state.pydantic_state import PeerRingState, AssistanceLevel

logger = logging.getLogger(__name__)


class AssistanceLadderController:
    """
    Controller for progressive scaffolding and fading in the study pod.
    """

    def __init__(
        self,
        error_threshold_to_escalate: int = 2,
        success_threshold_to_deescalate: int = 2,
        hesitation_latency_sec: float = 45.0,
    ):
        self.error_threshold = error_threshold_to_escalate
        self.success_threshold = success_threshold_to_deescalate
        self.hesitation_latency_sec = hesitation_latency_sec
        self._consecutive_successes: int = 0

    def get_current_level(self, state: PeerRingState) -> int:
        """Get the current assistance level (1 to 6)."""
        return state.policy.assistance_level.current_level

    def get_level_name(self, state: PeerRingState) -> str:
        """Get the human-readable name of the current level."""
        lvl = self.get_current_level(state)
        names = state.policy.assistance_level.level_names
        idx = max(0, min(lvl - 1, len(names) - 1))
        return names[idx]

    def step_up(self, state: PeerRingState, reason: str) -> int:
        """
        Escalate assistance by one level (max level 6).
        """
        ladder = state.policy.assistance_level
        old_level = ladder.current_level

        if old_level < 6:
            ladder.current_level += 1
            ladder.transitions_today += 1
            ladder.last_escalation = datetime.utcnow()
            self._consecutive_successes = 0
            logger.info(
                f"Assistance level escalated: {old_level} -> {ladder.current_level} (Reason: {reason})"
            )

        return ladder.current_level

    def step_down(self, state: PeerRingState, reason: str) -> int:
        """
        De-escalate assistance by one level towards independence (min level 1).
        """
        ladder = state.policy.assistance_level
        old_level = ladder.current_level

        if old_level > 1:
            ladder.current_level -= 1
            ladder.transitions_today += 1
            ladder.consecutive_errors = 0
            logger.info(
                f"Assistance level de-escalated: {old_level} -> {ladder.current_level} (Reason: {reason})"
            )

        return ladder.current_level

    def return_to_independence(
        self, state: PeerRingState, reason: str = "concept_mastered"
    ) -> int:
        """
        Reset assistance ladder directly to Level 1 (Independent).
        """
        ladder = state.policy.assistance_level
        old_level = ladder.current_level

        ladder.current_level = 1
        ladder.consecutive_errors = 0
        ladder.transitions_today += 1
        self._consecutive_successes = 0

        logger.info(
            f"Assistance ladder reset to Independent: {old_level} -> 1 (Reason: {reason})"
        )
        return 1

    def evaluate_turn_interaction(
        self,
        state: PeerRingState,
        student_success: Optional[bool] = None,
        latency_sec: Optional[float] = None,
        explicit_help_requested: bool = False,
    ) -> Dict[str, Any]:
        """
        Evaluate student performance signals from the turn and adjust assistance level.
        """
        ladder = state.policy.assistance_level
        initial_level = ladder.current_level
        transition_occurred = False
        action_taken = "maintained"
        reason = "no_transition_criteria_met"

        # Rule 1: Explicit student call for help -> immediate escalation
        if explicit_help_requested:
            if initial_level < 6:
                self.step_up(state, "explicit_help_requested")
                ladder.consecutive_errors = 0
                transition_occurred = True
                action_taken = "escalated"
                reason = "explicit_help_requested"

        # Rule 2: Student error evaluation
        elif student_success is False:
            ladder.consecutive_errors += 1
            self._consecutive_successes = 0

            if ladder.consecutive_errors >= self.error_threshold:
                if initial_level < 6:
                    self.step_up(state, f"consecutive_errors_{ladder.consecutive_errors}")
                    ladder.consecutive_errors = 0
                    transition_occurred = True
                    action_taken = "escalated"
                    reason = "consecutive_errors_threshold_reached"

        # Rule 3: Student success evaluation (competence demonstration)
        elif student_success is True:
            ladder.consecutive_errors = 0
            self._consecutive_successes += 1

            # When student succeeds multiple times at higher scaffolding, gradually step down
            if self._consecutive_successes >= self.success_threshold and initial_level > 1:
                self.step_down(state, f"consecutive_successes_{self._consecutive_successes}")
                transition_occurred = True
                action_taken = "de-escalated"
                reason = f"demonstrated_competence ({self._consecutive_successes} consecutive successes)"
                self._consecutive_successes = 0

        # Rule 4: High hesitation latency at early levels
        elif latency_sec is not None and latency_sec >= self.hesitation_latency_sec:
            if initial_level in [1, 2]:
                self.step_up(state, f"hesitation_latency_{latency_sec:.1f}s")
                transition_occurred = True
                action_taken = "escalated"
                reason = f"hesitation_latency_exceeded ({latency_sec:.1f}s)"

        final_level = ladder.current_level

        # PRISM Telemetry payload
        telemetry = {
            "initial_level": initial_level,
            "final_level": final_level,
            "level_name": self.get_level_name(state),
            "transition_occurred": transition_occurred,
            "action_taken": action_taken,
            "reason": reason,
            "consecutive_errors": ladder.consecutive_errors,
            "consecutive_successes": self._consecutive_successes,
            "transitions_today": ladder.transitions_today,
            "prism_event": "ASSISTANCE_LADDER_TRANSITION"
        }

        return telemetry
