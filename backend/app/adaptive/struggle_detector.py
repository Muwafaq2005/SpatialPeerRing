"""
Adaptive Struggle Detector.

Calculates composite struggle scores combining:
1. Error frequency & consecutive failures
2. Assistance ladder escalation level
3. Response latency (hesitation detection)
4. Explicit student help requests

Emits PRISM telemetry when student breaches stuckness thresholds.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.state.pydantic_state import PeerRingState

logger = logging.getLogger(__name__)


class StruggleDetector:
    """
    Multi-signal struggle detection engine for adaptive intervention.
    """

    def __init__(
        self,
        weight_error: float = 0.35,
        weight_ladder: float = 0.30,
        weight_latency: float = 0.15,
        weight_help: float = 0.20,
        latency_saturation_sec: float = 60.0,
    ):
        self.w_error = weight_error
        self.w_ladder = weight_ladder
        self.w_latency = weight_latency
        self.w_help = weight_help
        self.latency_saturation_sec = latency_saturation_sec

    def compute_struggle_score(
        self,
        state: PeerRingState,
        latency_sec: Optional[float] = None,
        explicit_help_requested: bool = False,
    ) -> Dict[str, Any]:
        """
        Compute the real-time composite struggle score (0.0 to 1.0) and update state.
        """
        ladder = state.policy.assistance_level

        # Factor 1: Error factor (combination of consecutive errors & concept failure rate)
        consecutive_errors = ladder.consecutive_errors
        error_streak_score = min(consecutive_errors / 3.0, 1.0)

        concept_failure_score = 0.0
        if state.current_concept and state.current_concept in state.curriculum_dag:
            node = state.curriculum_dag[state.current_concept]
            if node.attempts > 0:
                concept_failure_score = 1.0 - (node.correct_attempts / node.attempts)

        error_factor = (error_streak_score * 0.6) + (concept_failure_score * 0.4)

        # Factor 2: Ladder factor (level 1 = 0.0, level 6 = 1.0)
        ladder_factor = max(0.0, min((ladder.current_level - 1) / 5.0, 1.0))

        # Factor 3: Latency factor
        latency_factor = 0.0
        if latency_sec is not None and latency_sec > 0:
            latency_factor = min(latency_sec / self.latency_saturation_sec, 1.0)

        # Factor 4: Explicit help factor
        help_factor = 1.0 if explicit_help_requested else 0.0

        # Composite score calculation
        raw_score = (
            (self.w_error * error_factor)
            + (self.w_ladder * ladder_factor)
            + (self.w_latency * latency_factor)
            + (self.w_help * help_factor)
        )

        composite_score = round(max(0.0, min(1.0, raw_score)), 4)
        prev_score = state.policy.struggle_score
        state.policy.struggle_score = composite_score
        state.last_updated = datetime.utcnow()

        threshold = state.policy.stuck_threshold
        threshold_breached = composite_score >= threshold
        newly_breached = prev_score < threshold <= composite_score

        event_name = "STRUGGLE_THRESHOLD_BREACHED" if newly_breached else "STRUGGLE_SCORE_EVALUATED"

        telemetry = {
            "struggle_score": composite_score,
            "previous_score": prev_score,
            "stuck_threshold": threshold,
            "threshold_breached": threshold_breached,
            "newly_breached": newly_breached,
            "components": {
                "error_factor": round(error_factor, 3),
                "ladder_factor": round(ladder_factor, 3),
                "latency_factor": round(latency_factor, 3),
                "help_factor": round(help_factor, 3),
            },
            "prism_event": event_name,
        }

        if newly_breached:
            logger.warning(
                f"Student entered STUCK state! Score: {composite_score:.3f} >= Threshold: {threshold:.3f}"
            )
        else:
            logger.debug(f"Struggle evaluated: {composite_score:.3f} (prev: {prev_score:.3f})")

        return telemetry

    def is_stuck(self, state: PeerRingState) -> bool:
        """
        Check if the student is currently in a stuck state.
        """
        return state.policy.struggle_score >= state.policy.stuck_threshold
