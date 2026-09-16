"""
Policy Rewriter — Automated Pedagogical Response Regeneration
Regenerates candidate outputs that violate Leak or Help governance policies.
"""

from typing import Dict, Any, List, Optional, Tuple
import re
import logging
from datetime import datetime, UTC

from app.contracts.base_judge import BaseJudge
from app.state.pydantic_state import PeerRingState, AgentResponse, JudgeVerdict

logger = logging.getLogger(__name__)


class PolicyRewriter:
    """
    Automated response regeneration engine.
    When a candidate action is rejected by LeakJudge or HelpJudge, PolicyRewriter
    transforms the response into a compliant, constructive Socratic intervention.
    """

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

        # Standard concept-based Socratic prompts for safe fallbacks
        self.concept_prompts = {
            "distributive_property": "Let's look at the parentheses. What happens when you distribute the multiplier to each term inside?",
            "solving_equations": "What operation could we apply to both sides to get the variable by itself?",
            "factoring": "Can you spot any common factors we can pull out of these terms?",
            "fractions": "What common denominator could we use to combine these fractions?",
        }
        self.default_fallback = (
            "Let's work through this together step by step. "
            "What part of the expression would you like to examine first?"
        )

    async def rewrite_turn(
        self,
        candidate_response: AgentResponse,
        governance_results: Dict[str, JudgeVerdict],
        state: PeerRingState,
        leak_judge: BaseJudge,
        help_judge: BaseJudge,
    ) -> Tuple[AgentResponse, Dict[str, JudgeVerdict], bool]:
        """
        Rewrite a candidate response that failed governance evaluation.

        Args:
            candidate_response: The failing AgentResponse.
            governance_results: Map of judge_type -> JudgeVerdict from initial evaluation.
            state: Current PeerRingState session context.
            leak_judge: Active LeakJudge instance for re-testing.
            help_judge: Active HelpJudge instance for re-testing.

        Returns:
            Tuple of (final_response, final_governance_results, passed_all)
        """
        # If everything already passes, return untouched
        if all(v.verdict for v in governance_results.values()):
            return candidate_response, governance_results, True

        original_content = candidate_response.content
        original_patch = candidate_response.blackboard_patch
        current_content = original_content
        current_patch = original_patch

        violations: List[str] = []
        for judge_type, verdict in governance_results.items():
            if not verdict.verdict and verdict.violation_details:
                violations.append(f"[{judge_type.upper()}] {verdict.violation_details}")

        logger.info(
            f"🔄 PolicyRewriter initiated for session {state.session_id}: "
            f"violations={violations}"
        )

        # Attempt up to max_retries rewrites
        for attempt in range(1, self.max_retries + 1):
            rewritten_text, rewritten_patch = self._apply_rewrite_transformations(
                text=current_content,
                patch=current_patch,
                governance_results=governance_results,
                state=state,
                attempt=attempt
            )

            current_content = rewritten_text
            current_patch = rewritten_patch

            # Re-evaluate rewritten candidate
            new_governance: Dict[str, JudgeVerdict] = {}

            # Evaluate with LeakJudge
            new_governance["leak"] = await leak_judge.evaluate(
                text=current_content,
                patch=current_patch,
                state=state
            )

            # Evaluate with HelpJudge
            new_governance["help"] = await help_judge.evaluate(
                text=current_content,
                patch=current_patch,
                state=state
            )

            all_passed = all(v.verdict for v in new_governance.values())

            if all_passed:
                logger.info(
                    f"✅ PolicyRewriter succeeded on attempt {attempt} for session {state.session_id}"
                )
                rewritten_response = AgentResponse(
                    agent_id=candidate_response.agent_id,
                    content=current_content,
                    think_block=candidate_response.think_block,
                    blackboard_patch=current_patch,
                    confidence=candidate_response.confidence,
                    metadata={
                        **candidate_response.metadata,
                        "rewritten": True,
                        "rewrite_attempts": attempt,
                        "original_violations": violations,
                        "original_content_length": len(original_content)
                    }
                )
                return rewritten_response, new_governance, True

            governance_results = new_governance

        # If all retries exhausted, produce a safe Socratic fallback with zero solution disclosure
        logger.warning(
            f"⚠️ PolicyRewriter retries exhausted ({self.max_retries}) for session {state.session_id}. "
            f"Emitting safe curriculum fallback."
        )

        fallback_text = "Let's slow down and focus on the step you're working on. What operation would undo the constant term while keeping the equation balanced?"
        fallback_patch = None  # Clear visual patch on fallback to eliminate leak vector

        fallback_governance = {
            "leak": await leak_judge.evaluate(text=fallback_text, patch=fallback_patch, state=state),
            "help": await help_judge.evaluate(text=fallback_text, patch=fallback_patch, state=state),
        }

        fallback_passed = all(v.verdict for v in fallback_governance.values())

        fallback_response = AgentResponse(
            agent_id=candidate_response.agent_id,
            content=fallback_text,
            think_block=candidate_response.think_block,
            blackboard_patch=fallback_patch,
            confidence=0.85,
            metadata={
                **candidate_response.metadata,
                "rewritten": True,
                "rewrite_attempts": self.max_retries,
                "fallback_used": True,
                "original_violations": violations
            }
        )

        return fallback_response, fallback_governance, fallback_passed

    def _apply_rewrite_transformations(
        self,
        text: str,
        patch: Optional[str],
        governance_results: Dict[str, JudgeVerdict],
        state: PeerRingState,
        attempt: int
    ) -> Tuple[str, Optional[str]]:
        """Apply targeted heuristic transformations to address specific violations."""
        transformed_text = text
        transformed_patch = patch

        leak_verdict = governance_results.get("leak")
        help_verdict = governance_results.get("help")

        # 1. Address Leak Violations
        if leak_verdict and not leak_verdict.verdict:
            # Strip explicit answer declarations e.g. "x = 6"
            transformed_text = re.sub(
                r"(?:the\s+)?(?:answer|solution)\s+is\s+(?:[a-zA-Z]\s*=\s*)?-?\d+(?:\.\d+)?(?:[.,;!?\s]|$)",
                "what step comes next?",
                transformed_text,
                flags=re.IGNORECASE
            )

            # Strip full solution sentences containing step calculations e.g. "We add 4 to both sides to get 3x = 18..."
            transformed_text = re.sub(
                r"(?:we\s+)?(?:add|subtract|multiply|divide)\s+.*?(?:to\s+find|to\s+get|giving|is)\s+[a-zA-Z0-9\s=]+(?:\.|\b)",
                "What operation do you think we should try first to isolate the variable?",
                transformed_text,
                flags=re.IGNORECASE
            )

            # Strip standalone variable assignments e.g. "x = 6" or "3x = 18"
            transformed_text = re.sub(
                r"\b(?:\d+)?[a-zA-Z]\s*=\s*-?\d+(?:\.\d+)?\b",
                "what value would that give?",
                transformed_text
            )

            # Convert worked concluding steps into probing questions
            transformed_text = re.sub(
                r"(?:so\s+we\s+get|giving\s+us|which\s+equals?|then\s+divide\s+by\s+\d+\s+to\s+find)\s+.*$",
                "What do you think we get when we complete this step?",
                transformed_text,
                flags=re.IGNORECASE
            )

            # Scrub blackboard patch
            if transformed_patch:
                # Remove \boxed{...}
                transformed_patch = re.sub(r"\\boxed\{([^}]*)\}", r"\1", transformed_patch)
                # Replace answer assignments in LaTeX with ?
                transformed_patch = re.sub(r"=\s*-?\d+(?:\.\d+)?", "= ?", transformed_patch)

        # 2. Address Help Violations
        if help_verdict and not help_verdict.verdict:
            # Remove dismissive phrases
            dismissive_patterns = [
                r"i\s+don'?t\s+know",
                r"(?:just\s+)?figure\s+it\s+out(?:\s+yourself)?",
                r"(?:just\s+)?do\s+it(?:\s+yourself)?",
                r"that'?s\s+(?:just\s+)?wrong",
                r"you\s+should\s+know\s+this"
            ]
            for pattern in dismissive_patterns:
                transformed_text = re.sub(pattern, "let's look at this carefully", transformed_text, flags=re.IGNORECASE)

            # Ensure text is not excessively short
            if len(transformed_text.strip()) < 15:
                concept_hint = self.concept_prompts.get(
                    state.current_concept or "",
                    "What step would you like to try next?"
                )
                transformed_text = f"Let's work through this together. {concept_hint}"

            # Ensure there is an active guiding question
            if "?" not in transformed_text:
                transformed_text = transformed_text.rstrip(". ") + ". What do you think is our next move?"

        # Fallback question if text became empty
        if not transformed_text.strip():
            transformed_text = self._generate_safe_fallback(state)

        return transformed_text.strip(), transformed_patch

    def _generate_safe_fallback(self, state: PeerRingState) -> str:
        """Generate a safe, pedagogically sound Socratic guiding question."""
        concept = state.current_concept
        if concept and concept in self.concept_prompts:
            return self.concept_prompts[concept]
        return self.default_fallback
