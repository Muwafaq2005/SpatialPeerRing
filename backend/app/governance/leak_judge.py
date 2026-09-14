"""
Leak Judge Implementation
Fast out-of-band classifier preventing solution disclosure in AI tutoring
"""

import re
import ast
import asyncio
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
import logging
import sympy
from sympy.parsing.sympy_parser import parse_expr
from sympy import simplify, expand, factor, solve, Eq, Symbol

from app.contracts.base_judge import BaseJudge
from app.state.pydantic_state import (
    PeerRingState,
    JudgeVerdict,
    DialogueMessage,
    MessageRole
)

logger = logging.getLogger(__name__)


class MathExpressionAnalyzer:
    """
    Mathematical expression analyzer using AST and SymPy.
    Detects when responses contain complete solutions or final answers.
    """

    def __init__(self):
        """Initialize math analyzer with common solution patterns."""
        self.solution_indicators = {
            # Direct answer patterns
            "direct_answers": [
                r"(?:the\s+)?(?:answer|solution)\s+is\s+([^.!?\n]+)",
                r"(?:x|y|z)\s*=\s*([^.!?\n,]+)",
                r"(?:equals?|is|gives?)\s+([0-9]+(?:\.[0-9]+)?)",
                r"(?:result|final\s+answer)\s*:?\s*([^.!?\n]+)",
                r"therefore\s+([^.!?\n]+)",
                r"so\s+(?:the\s+answer\s+is\s+)?([0-9]+(?:\.[0-9]+)?)"
            ],

            # Complete work patterns
            "complete_work": [
                r"step\s+\d+.*step\s+\d+.*step\s+\d+",  # Multi-step solutions
                r"first.*then.*finally",
                r"(?:substitute|plug\s+in).*(?:solve|calculate).*(?:get|obtain)",
                r"distribute.*combine.*solve"
            ],

            # Mathematical completion indicators
            "completion_markers": [
                r"therefore",
                r"thus",
                r"hence",
                r"so\s+the\s+(?:answer|result)",
                r"final\s+(?:answer|result|step)",
                r"conclusion",
                r"we\s+(?:get|obtain|find)"
            ]
        }

    def extract_mathematical_expressions(self, text: str) -> List[str]:
        """
        Extract mathematical expressions from text.

        Args:
            text: Input text to analyze

        Returns:
            List of mathematical expressions found
        """
        expressions = []

        # Common math expression patterns
        math_patterns = [
            r"[a-zA-Z]\s*=\s*[^.!?\n,]+",  # Variable assignments
            r"\d+\s*[+\-*/]\s*\d+\s*=\s*\d+",  # Arithmetic equations
            r"\([^)]*[+\-*/][^)]*\)\s*=\s*[^.!?\n]+",  # Expressions with parentheses
            r"\d+(?:\.\d+)?\s*[<>=]+\s*\d+(?:\.\d+)?",  # Comparisons
            r"\d+(?:\.\d+)?\s+equals?\s+[^.!?\n,]+",  # "12.5 equals our target"
        ]

        for pattern in math_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            expressions.extend([m.strip() for m in matches])

        return expressions

    def is_complete_solution(self, expressions: List[str], target_solution: Optional[str] = None) -> bool:
        """
        Determine if expressions represent a complete solution.

        Args:
            expressions: Mathematical expressions to analyze
            target_solution: Expected solution (if known)

        Returns:
            True if expressions appear to be a complete solution
        """
        if not expressions:
            return False

        # Check for variable assignments that look like final answers (including negative numbers)
        for expr in expressions:
            cleaned = expr.strip()
            if re.search(r"[a-zA-Z]\s*=\s*-?\d+(?:\.\d+)?$", cleaned):
                return True

        # If we have a target solution, check for equivalence
        if target_solution:
            try:
                target_expr = parse_expr(target_solution)
                for expr in expressions:
                    try:
                        candidate_expr = parse_expr(expr.split('=')[-1].strip())
                        if simplify(target_expr - candidate_expr) == 0:
                            return True
                    except:
                        continue
            except:
                pass

        return False

    def analyze_blackboard_patch(self, patch: str) -> Dict[str, Any]:
        """
        Analyze KaTeX/LaTeX blackboard patches for solution leakage.

        Args:
            patch: KaTeX/LaTeX string to analyze

        Returns:
            Analysis results with leak indicators
        """
        if not patch:
            return {"has_leak": False, "confidence": 0.0}

        analysis = {
            "has_leak": False,
            "confidence": 0.0,
            "indicators": [],
            "expressions": []
        }

        # Handle LaTeX newlines by replacing \\ with actual newlines to split equations
        patch_lines = patch.replace(r'\\', '\n')

        # Strip environment delimiters like \begin{align} and \end{align}
        patch_lines = re.sub(r'\\begin\{[^}]*\}|\\end\{[^}]*\}', '', patch_lines)

        # Remove LaTeX formatting commands to get clean text
        clean_patch = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', patch_lines)
        clean_patch = re.sub(r'[\\&]', ' ', clean_patch)

        # Extract mathematical expressions from each line/clause
        expressions = []
        for line in clean_patch.split('\n'):
            line = line.strip()
            if line:
                expressions.extend(self.extract_mathematical_expressions(line))
        analysis["expressions"] = expressions

        # Check for complete solutions
        if self.is_complete_solution(expressions):
            analysis["has_leak"] = True
            analysis["confidence"] = 0.9
            analysis["indicators"].append("complete_solution_in_patch")

        # Check for multiple equals signs (often indicates worked solution)
        equals_count = patch.count('=')
        if equals_count >= 3:
            analysis["has_leak"] = True
            analysis["confidence"] = max(analysis["confidence"], 0.8)
            analysis["indicators"].append("multiple_equations")

        # Check for final answer formatting
        if re.search(r'\\boxed\{[^}]+\}', patch):
            analysis["has_leak"] = True
            analysis["confidence"] = 0.95
            analysis["indicators"].append("boxed_final_answer")

        return analysis


class CrossTurnLeakTracker:
    """
    Tracks potential solution leakage across multiple conversation turns.
    Detects when agents gradually reveal complete solutions.
    """

    def __init__(self):
        """Initialize cross-turn tracking."""
        self.solution_fragments: Dict[str, Set[str]] = {}
        self.cumulative_risk: Dict[str, float] = {}

    def add_response_analysis(self, session_id: str, expressions: List[str], leak_indicators: List[str]) -> float:
        """
        Add response to cross-turn analysis.

        Args:
            session_id: Session identifier
            expressions: Mathematical expressions from this turn
            leak_indicators: Leak indicators detected

        Returns:
            Updated cumulative leak risk score (0.0 - 1.0)
        """
        if session_id not in self.solution_fragments:
            self.solution_fragments[session_id] = set()
            self.cumulative_risk[session_id] = 0.0

        # Add new expressions to fragment set
        for expr in expressions:
            self.solution_fragments[session_id].add(expr.strip().lower())

        # Calculate cumulative risk
        fragment_count = len(self.solution_fragments[session_id])
        indicator_weight = sum(0.25 if any(k in ind.lower() for k in ["direct", "variable", "answer"]) else 0.1 for ind in leak_indicators)

        # Risk increases with more fragments and indicators
        base_risk = min(fragment_count * 0.15, 0.7)
        self.cumulative_risk[session_id] = min(base_risk + indicator_weight, 1.0)

        return self.cumulative_risk[session_id]

    def get_session_risk(self, session_id: str) -> float:
        """Get current cumulative leak risk for session."""
        return self.cumulative_risk.get(session_id, 0.0)

    def reset_session(self, session_id: str):
        """Reset tracking for a session (e.g., new problem started)."""
        self.solution_fragments.pop(session_id, None)
        self.cumulative_risk.pop(session_id, None)


class LeakJudge(BaseJudge):
    """
    Fast leak detection judge implementing pedagogical solution protection.

    Prevents agents from:
    - Revealing final answers directly
    - Showing complete worked solutions
    - Gradually leaking solution components across turns
    - Including complete solutions in blackboard patches
    """

    def __init__(self):
        """Initialize leak judge with analysis components."""
        super().__init__(judge_type="leak", config={
            "strictness_threshold": 0.7,
            "cross_turn_threshold": 0.6,
            "performance_target_ms": 200
        })

        self.math_analyzer = MathExpressionAnalyzer()
        self.cross_turn_tracker = CrossTurnLeakTracker()

        # Common solution leak patterns
        self.leak_patterns = [
            # Direct answer reveals
            (r"(?:the\s+)?(?:answer|solution)\s+is\s+(?:[a-zA-Z]\s*=\s*)?-?\d+", 0.95, "direct_answer"),
            (r"[a-zA-Z]\s*=\s*-?\d+(?:\.\d+)?(?:\b|[.,;!?\s]|$)", 0.9, "variable_solution"),
            (r"(?:equals?|is|gives?)\s+(?:us\s+)?(?:[a-zA-Z]\s*=\s*)?-?\d+(?:\.\d+)?(?:\b|[.,;!?\s]|$)", 0.8, "numeric_result"),

            # Complete process reveals
            (r"(?:substitute|plug\s+in).*(?:get|gives?)\s+\d+", 0.85, "complete_substitution"),
            (r"distribute.*combine.*(?:equals?|is)\s+\d+", 0.8, "complete_distribution"),
            (r"solve.*(?:get|obtain|find)\s+[a-zA-Z]\s*=\s*-?\d+", 0.9, "complete_solve"),

            # Step-by-step completion
            (r"step\s+1.*step\s+2.*step\s+3", 0.75, "complete_steps"),
            (r"first.*then.*finally.*\d+", 0.7, "sequential_completion"),

            # Conclusion indicators
            (r"therefore\s+(?:the\s+answer\s+)?(?:is\s+)?-?\d+", 0.9, "conclusive_answer"),
            (r"so\s+(?:the\s+)?(?:answer|result)\s+(?:is\s+)?-?\d+", 0.85, "casual_conclusion")
        ]

    async def evaluate(
        self,
        text: str,
        patch: Optional[str],
        state: PeerRingState,
        metadata: Optional[Dict[str, Any]] = None
    ) -> JudgeVerdict:
        """
        Fast leak evaluation with mathematical analysis.
        Target: <200ms evaluation time.

        Args:
            text: Agent response text to evaluate
            patch: Optional blackboard patch (KaTeX/SVG)
            state: Current session state for context
            metadata: Additional evaluation context

        Returns:
            JudgeVerdict with leak detection results
        """
        start_time = datetime.utcnow()

        try:
            # Get sensitivity threshold based on policy
            threshold = self.get_sensitivity_threshold(state)

            # Initialize analysis results
            leak_score = 0.0
            violation_details = []
            suggested_fixes = []

            # 1. Pattern-based text analysis (fast)
            text_analysis = self._analyze_text_patterns(text)
            leak_score = max(leak_score, text_analysis["score"])
            violation_details.extend(text_analysis["violations"])

            # 2. Mathematical expression analysis
            math_expressions = self.math_analyzer.extract_mathematical_expressions(text)
            if math_expressions:
                # Check against target solution if available
                target_solution = getattr(state, "target_solution", None)
                if self.math_analyzer.is_complete_solution(math_expressions, target_solution):
                    leak_score = max(leak_score, 0.9)
                    violation_details.append("Complete mathematical solution detected")

            # 3. Blackboard patch analysis
            if patch:
                patch_analysis = self.math_analyzer.analyze_blackboard_patch(patch)
                if patch_analysis["has_leak"]:
                    leak_score = max(leak_score, patch_analysis["confidence"])
                    violation_details.extend([f"Blackboard: {ind}" for ind in patch_analysis["indicators"]])

            # 4. Cross-turn analysis
            cross_turn_risk = self.cross_turn_tracker.add_response_analysis(
                state.session_id,
                math_expressions,
                text_analysis["indicators"]
            )

            if cross_turn_risk > self.config["cross_turn_threshold"]:
                leak_score = max(leak_score, cross_turn_risk)
                violation_details.append(f"Cumulative leak risk: {cross_turn_risk:.1%}")

            # 5. Context-aware adjustment
            if state.policy.strict_mode:
                threshold *= 0.8  # More strict in adversarial mode

            if state.policy.struggle_score > 0.7:
                threshold *= 0.9  # More protective when student struggling

            # Generate verdict
            passes = leak_score < threshold
            confidence = min(0.95, 0.6 + (abs(leak_score - threshold) * 0.8))

            # Generate suggested fixes if failing
            if not passes:
                suggested_fixes = self._generate_fix_suggestions(text_analysis["indicators"], violation_details)

            # Calculate evaluation time
            evaluation_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Log performance
            if evaluation_time > self.config["performance_target_ms"]:
                logger.warning(f"Leak judge evaluation slow: {evaluation_time:.1f}ms (target: {self.config['performance_target_ms']}ms)")

            self.update_performance_stats(int(evaluation_time))

            # Create reasoning explanation
            reasoning = self._create_reasoning(leak_score, threshold, violation_details, cross_turn_risk)

            return JudgeVerdict(
                judge_type="leak",
                verdict=passes,
                confidence=confidence,
                reasoning=reasoning,
                violation_details="; ".join(violation_details) if violation_details else None,
                suggested_fixes=suggested_fixes,
                evaluation_time_ms=int(evaluation_time)
            )

        except Exception as e:
            logger.error(f"Leak judge evaluation error: {e}")

            # Safe fallback - assume potential leak
            evaluation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.update_performance_stats(int(evaluation_time))

            return JudgeVerdict(
                judge_type="leak",
                verdict=False,
                confidence=0.5,
                reasoning=f"Evaluation error, failing safe: {str(e)}",
                violation_details="Internal evaluation error",
                suggested_fixes=["Rephrase response to avoid potential solution disclosure"],
                evaluation_time_ms=int(evaluation_time)
            )

    def _analyze_text_patterns(self, text: str) -> Dict[str, Any]:
        """
        Fast pattern-based analysis of text for common leak indicators.

        Args:
            text: Text to analyze

        Returns:
            Analysis results with score and violations
        """
        analysis = {
            "score": 0.0,
            "violations": [],
            "indicators": []
        }

        text_lower = text.lower()

        # Check each leak pattern
        for pattern, weight, indicator in self.leak_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                analysis["score"] = max(analysis["score"], weight)
                analysis["violations"].append(f"Pattern match: {indicator}")
                analysis["indicators"].append(indicator)

        return analysis

    def _generate_fix_suggestions(self, indicators: List[str], violations: List[str]) -> List[str]:
        """Generate specific fix suggestions based on detected violations."""
        fixes = []

        if "direct_answer" in indicators:
            fixes.append("Remove explicit answer - guide student to discover it")

        if "variable_solution" in indicators:
            fixes.append("Replace variable assignment with guiding question")

        if "complete_substitution" in indicators or "complete_solve" in indicators:
            fixes.append("Show only partial work - let student complete the solution")

        if "complete_steps" in indicators:
            fixes.append("Provide only the next step, not the complete sequence")

        if "Blackboard" in str(violations):
            fixes.append("Remove final answer from blackboard patch")
            fixes.append("Show setup only, not complete worked solution")

        # Default suggestions
        if not fixes:
            fixes = [
                "Rephrase to focus on process rather than answer",
                "Ask guiding questions instead of providing solutions",
                "Show partial work and let student complete"
            ]

        return fixes[:3]  # Limit to top 3 suggestions

    def _create_reasoning(self, leak_score: float, threshold: float, violations: List[str], cross_turn_risk: float) -> str:
        """Create human-readable reasoning for the verdict."""
        if leak_score < threshold:
            return f"No significant solution leakage detected (score: {leak_score:.2f} < threshold: {threshold:.2f})"
        else:
            reason = f"Solution leak detected (score: {leak_score:.2f} >= threshold: {threshold:.2f})"
            if violations:
                reason += f". Violations: {', '.join(violations[:2])}"
            if cross_turn_risk > 0.5:
                reason += f". Cross-turn risk: {cross_turn_risk:.1%}"
            return reason