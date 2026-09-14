"""
BaseJudge Abstract Contract
Defines the interface for all PeerRing governance judges (Leak, Help, Adversarial)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import logging

from app.state.pydantic_state import (
    PeerRingState,
    AgentResponse,
    JudgeVerdict
)

logger = logging.getLogger(__name__)


class BaseJudge(ABC):
    """
    Abstract base class for all PeerRing governance judges.

    This contract defines the evaluation interface for leak detection,
    help assessment, and adversarial resistance. All judges must implement
    fast evaluation (<250ms target) for real-time response filtering.
    """

    def __init__(self, judge_type: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the base judge.

        Args:
            judge_type: Type of judge ("leak", "help", "adversarial")
            config: Optional configuration dictionary
        """
        self.judge_type = judge_type
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{judge_type}")

        # Performance tracking
        self.evaluation_count = 0
        self.total_evaluation_time_ms = 0

    @abstractmethod
    async def evaluate(
        self,
        text: str,
        patch: Optional[str],
        state: PeerRingState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> JudgeVerdict:
        """
        Evaluate agent response for policy compliance.

        This is the core evaluation method that must be implemented by all judges.
        It should complete quickly (<250ms target) and return a clear verdict.

        Args:
            text: The agent's text response to evaluate
            patch: Optional blackboard patch (KaTeX/SVG) to evaluate
            state: Current PeerRingState for context
            metadata: Optional evaluation metadata

        Returns:
            JudgeVerdict with pass/fail decision and reasoning

        Raises:
            NotImplementedError: Must be implemented by concrete judges
        """
        raise NotImplementedError("Judges must implement evaluate method")

    async def batch_evaluate(
        self,
        responses: List[AgentResponse],
        state: PeerRingState
    ) -> List[JudgeVerdict]:
        """
        Evaluate multiple responses in batch for efficiency.

        Default implementation calls evaluate() for each response individually.
        Concrete judges can override for optimized batch processing.

        Args:
            responses: List of AgentResponse objects to evaluate
            state: Current PeerRingState

        Returns:
            List of JudgeVerdict objects, one per response
        """
        verdicts = []
        for response in responses:
            verdict = await self.evaluate(
                text=response.content,
                patch=response.blackboard_patch,
                state=state,
                metadata=response.metadata
            )
            verdicts.append(verdict)
        return verdicts

    def get_sensitivity_threshold(self, state: PeerRingState) -> float:
        """
        Get the sensitivity threshold for this judge based on current policy.

        Args:
            state: Current PeerRingState with policy settings

        Returns:
            Sensitivity threshold between 0.0 (permissive) and 1.0 (strict)
        """
        # Default implementation based on judge type and policy state
        if self.judge_type == "leak":
            base_sensitivity = state.policy.leak_sensitivity
        elif self.judge_type == "help":
            base_sensitivity = state.policy.help_sensitivity
        else:
            base_sensitivity = 0.5

        # Increase sensitivity in strict mode (adversarial input detected)
        if state.policy.strict_mode:
            base_sensitivity = min(base_sensitivity + 0.2, 1.0)

        return base_sensitivity

    def should_evaluate(self, state: PeerRingState) -> bool:
        """
        Determine if this judge should evaluate based on current state.

        Args:
            state: Current PeerRingState

        Returns:
            True if judge should evaluate, False to skip
        """
        # Skip evaluation in certain recovery states
        if state.policy.recovery_state in ["micro_teaching"] and self.judge_type == "help":
            # Be more lenient during micro-teaching recovery
            return False

        return True

    async def explain_verdict(
        self,
        verdict: JudgeVerdict,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate human-readable explanation of judge verdict.

        Args:
            verdict: The JudgeVerdict to explain
            context: Optional context for explanation

        Returns:
            Human-readable explanation string
        """
        confidence_str = f"({verdict.confidence:.1%} confidence)"

        if verdict.verdict:
            return f"✅ {self.judge_type.title()} Judge: PASS {confidence_str} - {verdict.reasoning}"
        else:
            explanation = f"❌ {self.judge_type.title()} Judge: FAIL {confidence_str} - {verdict.reasoning}"
            if verdict.violation_details:
                explanation += f"\nViolation: {verdict.violation_details}"
            if verdict.suggested_fixes:
                explanation += f"\nSuggested fixes: {', '.join(verdict.suggested_fixes)}"
            return explanation

    def update_performance_stats(self, evaluation_time_ms: int) -> None:
        """
        Update performance tracking statistics.

        Args:
            evaluation_time_ms: Time taken for this evaluation
        """
        self.evaluation_count += 1
        self.total_evaluation_time_ms += evaluation_time_ms

    def get_average_evaluation_time(self) -> float:
        """
        Get average evaluation time in milliseconds.

        Returns:
            Average evaluation time, or 0.0 if no evaluations yet
        """
        if self.evaluation_count == 0:
            return 0.0
        return self.total_evaluation_time_ms / self.evaluation_count

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for monitoring.

        Returns:
            Dictionary with performance metrics
        """
        return {
            "judge_type": self.judge_type,
            "evaluation_count": self.evaluation_count,
            "total_time_ms": self.total_evaluation_time_ms,
            "average_time_ms": self.get_average_evaluation_time(),
            "target_time_ms": 250,
            "performance_ok": self.get_average_evaluation_time() <= 250
        }

    def __str__(self) -> str:
        """String representation of the judge."""
        return f"{self.__class__.__name__}(type={self.judge_type})"

    def __repr__(self) -> str:
        """Detailed string representation of the judge."""
        avg_time = self.get_average_evaluation_time()
        return f"{self.__class__.__name__}(judge_type='{self.judge_type}', evaluations={self.evaluation_count}, avg_time={avg_time:.1f}ms)"