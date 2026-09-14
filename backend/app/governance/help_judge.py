"""
Help Judge — Pedagogical Helpfulness & Scaffolding Governance
Evaluates agent dialogue for constructive Socratic tutoring behavior.
"""

from typing import Optional, Dict, Any, List
import re
import logging
from datetime import datetime, UTC

from app.contracts.base_judge import BaseJudge
from app.state.pydantic_state import PeerRingState, JudgeVerdict

logger = logging.getLogger(__name__)


class HelpJudge(BaseJudge):
    """
    Second-pass governance judge ensuring agent responses provide genuine
    pedagogical assistance, Socratic inquiry, and encouraging scaffolding.

    Prevents:
    - Dismissive or unconstructive responses ("figure it out", "i don't know", "that's wrong")
    - Dead-end statements devoid of diagnostic guidance or next steps
    - Harsh or abrupt communication when students are struggling
    - Mismatch between assistance level and provided hint depth
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        default_config = {
            "helpfulness_threshold": 0.6,
            "performance_target_ms": 200,
        }
        if config:
            default_config.update(config)

        super().__init__(judge_type="help", config=default_config)

        # Rubric indicator definitions
        self.helpful_indicators = [
            # Socratic and probing questions
            r"what\s+(?:do\s+you\s+think|would\s+you|might\s+we|happens\s+if)",
            r"how\s+(?:would\s+you|did\s+you|about|might\s+we|can\s+we)",
            r"why\s+(?:do\s+you|did|is\s+that)",
            r"can\s+you\s+(?:tell\s+me|explain|identify|find)",
            r"could\s+you\s+(?:try|check|explain)",
            r"what\s+step\s+(?:comes\s+next|should\s+we)",
            r"where\s+(?:should\s+we|do\s+we\s+start)",
            # Guidance & scaffolding
            r"let'?s\s+(?:try|work|look|break|explore)",
            r"notice\s+that",
            r"remember\s+(?:that|how)",
            r"think\s+about",
            r"take\s+a\s+look\s+at",
            r"one\s+way\s+to\s+approach",
            # Constructive encouragement
            r"great\s+(?:effort|start|job|observation)",
            r"good\s+(?:try|thinking|question)",
            r"you'?re\s+(?:on\s+the\s+right\s+track|very\s+close)",
            r"almost\s+there",
        ]

        self.unhelpful_indicators = [
            # Dismissive / abandonment
            (r"i\s+don'?t\s+know", "claims_ignorance", 0.35),
            (r"(?:just\s+)?figure\s+it\s+out(?:\s+yourself)?", "dismissive_brush_off", 0.45),
            (r"(?:just\s+)?do\s+it(?:\s+yourself)?", "abrupt_command", 0.35),
            (r"you\s+should\s+already\s+know", "condescending_tone", 0.40),
            (r"obviously|clearly\s+you\s+don'?t", "belittling_tone", 0.40),
            (r"that'?s\s+(?:just\s+)?(?:wrong|incorrect|stupid|bad)", "harsh_negative_critique", 0.35),
            (r"no\s+idea|not\s+my\s+job", "refusal_to_assist", 0.45),
            (r"give\s+up", "defeatist_language", 0.50),
        ]

    async def evaluate(
        self,
        text: str,
        patch: Optional[str],
        state: PeerRingState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> JudgeVerdict:
        """
        Evaluate proposed response text for pedagogical helpfulness and Socratic quality.
        Target: <200ms evaluation latency.
        """
        start_time = datetime.now(UTC)

        try:
            # Determine threshold from current policy
            base_threshold = self.config.get("helpfulness_threshold", 0.6)
            threshold = self.get_sensitivity_threshold(state) if hasattr(self, "get_sensitivity_threshold") else base_threshold

            # In strict mode or high struggle, demand higher helpfulness standards
            if state.policy.strict_mode:
                threshold = min(0.9, threshold + 0.1)
            if state.policy.struggle_score > 0.7:
                threshold = min(0.9, threshold + 0.05)

            text_clean = text.strip()
            text_lower = text_clean.lower()

            violations: List[str] = []
            suggested_fixes: List[str] = []

            # 1. Check for abrupt or empty text
            if len(text_clean) < 8:
                violations.append("Response is excessively terse or empty")
                suggested_fixes.append("Elaborate with a helpful Socratic guiding question")

            # 2. Score positive helpful indicators
            helpful_matches = [
                pattern for pattern in self.helpful_indicators
                if re.search(pattern, text_lower)
            ]
            helpful_score = len(helpful_matches) * 0.15

            # 3. Check for question mark (active dialogic engagement)
            has_question = "?" in text_clean
            if has_question:
                helpful_score += 0.15

            # 4. Score unhelpful / dismissive violations
            unhelpful_penalty = 0.0
            for pattern, indicator_name, penalty in self.unhelpful_indicators:
                if re.search(pattern, text_lower):
                    unhelpful_penalty += penalty
                    violations.append(f"Unconstructive language detected: {indicator_name}")

            # 5. Assistance level alignment check
            current_level = state.policy.assistance_level.current_level
            if current_level >= 4 and not helpful_matches and not has_question:
                unhelpful_penalty += 0.15
                violations.append(f"Assistance level is {current_level} but response lacks concrete scaffolding")
                suggested_fixes.append("Provide a concrete sub-step hint tailored to assistance level")

            # 6. Calculate aggregate score (bounded [0.0, 1.0])
            base_score = 0.6  # Default neutral-positive prior for coherent tutoring text
            raw_score = base_score + helpful_score - unhelpful_penalty
            helpfulness_score = max(0.0, min(1.0, raw_score))

            passes = helpfulness_score >= threshold and len(violations) == 0

            # Confidence based on distance from threshold
            confidence = min(0.95, 0.65 + (abs(helpfulness_score - threshold) * 0.5))

            if not passes:
                if not suggested_fixes:
                    suggested_fixes.append("Add a Socratic guiding question to prompt student reasoning")
                    suggested_fixes.append("Rephrase to be more constructive and supportive")

            # Evaluation time
            eval_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            self.update_performance_stats(int(eval_time))

            reasoning = self._create_reasoning(helpfulness_score, threshold, passes, violations)

            return JudgeVerdict(
                judge_type="help",
                verdict=passes,
                confidence=round(confidence, 2),
                reasoning=reasoning,
                violation_details="; ".join(violations) if violations else None,
                suggested_fixes=suggested_fixes,
                evaluation_time_ms=int(eval_time)
            )

        except Exception as e:
            logger.error(f"Help judge evaluation error: {e}", exc_info=True)
            eval_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            return JudgeVerdict(
                judge_type="help",
                verdict=False,
                confidence=0.5,
                reasoning=f"Evaluation error, failing safe: {str(e)}",
                violation_details="Internal evaluation error",
                suggested_fixes=["Rephrase response with simple guiding question"],
                evaluation_time_ms=int(eval_time)
            )

    def _create_reasoning(
        self,
        score: float,
        threshold: float,
        passes: bool,
        violations: List[str]
    ) -> str:
        """Format human-readable reasoning for Help verdict."""
        if passes:
            return f"Response provides constructive pedagogical scaffolding (score: {score:.2f} >= threshold: {threshold:.2f})"
        else:
            reason = f"Response rejected for low pedagogical helpfulness (score: {score:.2f} < threshold: {threshold:.2f})"
            if violations:
                reason += f". Violations: {', '.join(violations[:2])}"
            return reason
