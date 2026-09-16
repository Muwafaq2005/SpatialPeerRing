"""
Enhanced Leak Judge with Cumulative Solution Detection
Detects when multiple turns collectively form a complete solution
"""

import re
from typing import List, Set, Tuple
from app.state.pydantic_state import PeerRingState, MessageRole


class CumulativeSolutionDetector:
    """Detects when dialogue history collectively reveals a complete solution."""

    def __init__(self):
        """Initialize detector with step patterns."""
        self.step_patterns = {
            # For linear equations
            "distribution": r"\b(distribut|multiply|expand)\b.*\(.*[+\-].*\)",
            "isolation": r"\b(subtract|add|move|isolate)\b.*\b(side|both)\b",
            "division": r"\b(divide|split|coefficient)\b",
            "final_answer": r"\bx\s*=\s*[-+]?\d+",

            # For quadratic equations
            "factoring": r"\b(factor|factorize|break down)\b",
            "roots": r"\b(root|solution|x\s*=)\b",

            # For fractions
            "simplify": r"\b(simplify|reduce|cancel)\b",
            "common_factor": r"\b(common factor|GCD)\b",
        }

    def extract_solution_concepts_from_dialogue(self, state: PeerRingState) -> Set[str]:
        """
        Extract what solution concepts have been revealed across all messages.

        Returns: Set of concept keywords found (e.g., {'distribution', 'isolation', 'division'})
        """
        revealed = set()

        for msg in state.messages:
            if msg.role not in [MessageRole.AGENT, MessageRole.SYSTEM]:
                continue

            content = msg.content.lower()

            for concept, pattern in self.step_patterns.items():
                if re.search(pattern, content, re.IGNORECASE):
                    revealed.add(concept)

        return revealed

    def can_student_now_solve_linear_equation(self, state: PeerRingState) -> Tuple[bool, str]:
        """
        Check if cumulative hints enable solving 2-step linear equations.

        Linear equation solving requires:
        1. Distribution (if applicable)
        2. Isolation of variable term
        3. Division by coefficient
        """
        concepts = self.extract_solution_concepts_from_dialogue(state)

        required = {"isolation", "division"}
        has_required = required.issubset(concepts)

        if has_required:
            return True, f"All required steps revealed: {concepts}"

        missing = required - concepts
        return False, f"Missing concepts: {missing}"

    def reconstruct_solution_path(self, state: PeerRingState) -> List[str]:
        """
        Reconstruct the solution steps from dialogue history.

        Returns: Ordered list of solution steps mentioned
        """
        steps = []
        seen = set()

        for msg in state.messages:
            if msg.role not in [MessageRole.AGENT, MessageRole.SYSTEM]:
                continue

            content = msg.content

            for concept in ["distribution", "isolation", "division", "factoring", "roots"]:
                if (
                    concept not in seen
                    and re.search(self.step_patterns[concept], content, re.IGNORECASE)
                ):
                    steps.append(concept)
                    seen.add(concept)

        return steps

    def has_numerical_answer_been_mentioned(self, state: PeerRingState) -> Tuple[bool, List[str]]:
        """
        Check if any numerical answer has been explicitly stated.

        Returns: (answer_found, list_of_answers)
        """
        answers = []
        pattern = r"\bx\s*=\s*([-+]?\d+(?:\.\d+)?)"

        for msg in state.messages:
            content = msg.content
            matches = re.findall(pattern, content)
            for match in matches:
                answers.append(match)

        return len(answers) > 0, answers


class EnhancedLeakJudge:
    """Leak Judge with cumulative detection capabilities."""

    def __init__(self):
        """Initialize with cumulative detector."""
        self.cumulative_detector = CumulativeSolutionDetector()
        self.leak_threshold = 0.75

    async def check_cumulative_leak(self, state: PeerRingState) -> Tuple[bool, float, str]:
        """
        Check if cumulative dialogue reveals the solution.

        Returns: (is_leak, leak_score, reason)
        """
        # Check if answer has been mentioned
        has_answer, answers = self.cumulative_detector.has_numerical_answer_been_mentioned(state)
        if has_answer:
            return (
                True,
                0.95,
                f"Numerical answer(s) mentioned in dialogue: {', '.join(answers)}"
            )

        # Check if cumulative concepts enable solving
        for problem_type in ["linear_equation", "quadratic", "fraction"]:
            if problem_type == "linear_equation":
                can_solve, reason = (
                    self.cumulative_detector.can_student_now_solve_linear_equation(state)
                )
                if can_solve:
                    solution_path = self.cumulative_detector.reconstruct_solution_path(state)
                    return (
                        True,
                        0.85,
                        f"Student can now solve. Steps revealed: {' → '.join(solution_path)}"
                    )

        return False, 0.0, "No cumulative leak detected"

    def check_answer_in_error_frame(self, text: str, state: PeerRingState) -> Tuple[bool, float, str]:
        """
        Check if correct answer is mentioned while claiming an error.

        Pattern: "I got X (correct answer), but I made a mistake and got Y (wrong answer)"
        """
        # Extract all numbers mentioned
        numbers = re.findall(r"\bx\s*=\s*([-+]?\d+(?:\.\d+)?)", text)

        if len(numbers) <= 1:
            return False, 0.0, "No multiple answers in frame"

        # Multiple answers mentioned (correct one may be in the explanation)
        return (
            True,
            0.70,
            f"Multiple numerical values mentioned: {', '.join(set(numbers))} - " +
            "Student can identify correct answer from explanation"
        )

    async def evaluate_with_cumulative_checks(
        self,
        text: str,
        blackboard_patch: str | None,
        state: PeerRingState
    ) -> Tuple[bool, float, List[str]]:
        """
        Enhanced evaluation with cumulative leak detection.

        Returns: (verdict, leak_score, violation_list)
        """
        violations = []
        leak_score = 0.0

        # 1. Check immediate answer reveal
        if re.search(r"\bx\s*=\s*([-+]?\d+)", text):
            leak_score = max(leak_score, 0.90)
            violations.append("Direct numerical answer revealed")

        # 2. Check for answer in error frame
        has_answer_frame, score, reason = self.check_answer_in_error_frame(text, state)
        if has_answer_frame:
            leak_score = max(leak_score, score)
            violations.append(reason)

        # 3. Check cumulative solution construction
        is_cumulative_leak, cum_score, cum_reason = await self.check_cumulative_leak(state)
        if is_cumulative_leak:
            leak_score = max(leak_score, cum_score)
            violations.append(cum_reason)

        verdict = leak_score < self.leak_threshold

        return verdict, leak_score, violations
