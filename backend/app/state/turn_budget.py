"""
Turn Budget System - Prevents infinite response loops
Tracks pedagogical "debt" and stops agents when enough hints have been given
"""

from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field


class TurnBudget(BaseModel):
    """Tracks hint budget and failure state across a tutoring session."""

    # Hint tracking
    hints_given_this_session: int = 0
    max_hints_per_session: int = 10  # After 10 hints, enforce cooldown
    hints_given_this_turn_sequence: int = 0
    max_hints_per_turn_sequence: int = 3  # Max 3 hints per problem attempt

    # Failure tracking
    governance_failures: int = 0  # Times Leak Judge rejected a response
    max_consecutive_failures: int = 2  # 2 failures → force turn end

    # Cooldown tracking
    last_hint_timestamp: Optional[datetime] = None
    cooldown_active: bool = False
    cooldown_ends_at: Optional[datetime] = None
    cooldown_duration_seconds: int = 60  # 1 minute cooldown after many hints

    # Reset tracking
    turn_sequence_started_at: Optional[datetime] = None
    turn_sequence_problem: Optional[str] = None  # What problem is being worked on

    def should_allow_new_hint(self) -> tuple[bool, str]:
        """
        Determine if system should allow a new hint right now.

        Returns: (allow_hint, reason)
        """
        # Check if cooldown is active
        if self.cooldown_active:
            if self.cooldown_ends_at and datetime.utcnow() < self.cooldown_ends_at:
                remaining = (self.cooldown_ends_at - datetime.utcnow()).total_seconds()
                return False, f"Cooldown active. {remaining:.0f}s remaining."
            else:
                # Cooldown expired, clear it
                self.cooldown_active = False
                self.cooldown_ends_at = None

        # Check consecutive failures
        if self.governance_failures >= self.max_consecutive_failures:
            return (
                False,
                f"Too many hint rejections ({self.governance_failures}). "
                f"Student should work independently now."
            )

        # Check turn sequence limit
        if self.hints_given_this_turn_sequence >= self.max_hints_per_turn_sequence:
            return (
                False,
                f"Already gave {self.max_hints_per_turn_sequence} hints for this problem. "
                f"Time for student to attempt."
            )

        # Check session limit
        if self.hints_given_this_session >= self.max_hints_per_session:
            # Activate cooldown
            self.cooldown_active = True
            self.cooldown_ends_at = datetime.utcnow() + timedelta(
                seconds=self.cooldown_duration_seconds
            )
            return (
                False,
                f"Reached session hint limit ({self.max_hints_per_session}). "
                f"Taking a break for {self.cooldown_duration_seconds}s."
            )

        return True, "Within budget. New hint allowed."

    def record_hint_given(self):
        """Record that a hint was successfully given."""
        self.hints_given_this_session += 1
        self.hints_given_this_turn_sequence += 1
        self.last_hint_timestamp = datetime.utcnow()
        self.governance_failures = 0  # Reset failure counter on success

    def record_governance_failure(self):
        """Record that Leak Judge rejected a hint."""
        self.governance_failures += 1

    def record_governance_pass(self):
        """Record that Leak Judge approved a hint."""
        self.governance_failures = 0  # Reset on successful pass

    def start_new_turn_sequence(self, problem: str):
        """Start tracking a new problem/turn sequence."""
        self.hints_given_this_turn_sequence = 0
        self.turn_sequence_started_at = datetime.utcnow()
        self.turn_sequence_problem = problem
        self.governance_failures = 0

    def get_status(self) -> dict:
        """Get current budget status."""
        return {
            "hints_given_session": self.hints_given_this_session,
            "hints_available_session": max(0, self.max_hints_per_session - self.hints_given_this_session),
            "hints_given_turn": self.hints_given_this_turn_sequence,
            "hints_available_turn": max(0, self.max_hints_per_turn_sequence - self.hints_given_this_turn_sequence),
            "governance_failures": self.governance_failures,
            "cooldown_active": self.cooldown_active,
            "can_give_hint": self.should_allow_new_hint()[0],
        }


def should_force_turn_end(turn_budget: TurnBudget, state) -> tuple[bool, Optional[str]]:
    """
    Determine if we should force-end this turn due to budget constraints.

    Args:
        turn_budget: Current turn budget state
        state: Current PeerRingState

    Returns:
        (should_end, reason_message)
    """
    # Check 1: Consecutive governance failures
    if turn_budget.governance_failures >= turn_budget.max_consecutive_failures:
        return (
            True,
            f"Governance rejected {turn_budget.governance_failures} consecutive responses. "
            f"Let's stop here and you work on this independently."
        )

    # Check 2: Turn sequence hint limit reached
    if turn_budget.hints_given_this_turn_sequence >= turn_budget.max_hints_per_turn_sequence:
        return (
            True,
            f"I've given {turn_budget.max_hints_per_turn_sequence} hints for this problem. "
            f"Now it's your turn to try!"
        )

    # Check 3: Session hint limit with cooldown needed
    if turn_budget.hints_given_this_session >= turn_budget.max_hints_per_session:
        return (
            True,
            f"We've covered a lot of ground ({turn_budget.max_hints_per_session} hints). "
            f"Let's take a break so you can practice independently."
        )

    return False, None
