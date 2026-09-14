"""
Mathematical AST Validator for Leak Detection
Advanced mathematical expression comparison and solution equivalence checking
"""

import ast
import re
import sympy
from sympy import Symbol, Eq, solve, simplify, expand, factor, latex
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExpressionMatch:
    """Result of expression comparison."""
    is_equivalent: bool
    confidence: float
    transformation_used: Optional[str] = None
    symbolic_form: Optional[str] = None
    reason: Optional[str] = None


class MathASTValidator:
    """
    Advanced mathematical expression validator using SymPy AST comparison.

    Detects when agent responses contain mathematically equivalent expressions
    to target solutions, even when presented in different forms.
    """

    def __init__(self):
        """Initialize mathematical validator with SymPy configuration."""
        # SymPy parsing transformations
        self.transformations = (
            standard_transformations +
            (implicit_multiplication_application,)
        )

        # Common variable symbols used in algebra problems
        self.common_variables = {
            Symbol('x'), Symbol('y'), Symbol('z'), Symbol('t'),
            Symbol('a'), Symbol('b'), Symbol('c'), Symbol('n')
        }

        # Mathematical equivalence patterns
        self.equivalence_checks = [
            self._check_direct_equality,
            self._check_expanded_form,
            self._check_factored_form,
            self._check_simplified_form,
            self._check_solved_form
        ]

    def extract_expressions_from_text(self, text: str) -> List[str]:
        """
        Extract mathematical expressions from natural language text.

        Args:
            text: Input text containing mathematical expressions

        Returns:
            List of extracted mathematical expressions
        """
        expressions = []

        # Patterns for mathematical expressions
        math_patterns = [
            # Equations with variables
            r'[a-zA-Z]\s*=\s*[^,.\n!?]+',

            # Expressions with operators
            r'\d+\s*[+\-*/^]\s*\d+\s*=\s*\d+',
            r'\([^)]+\)\s*=\s*[^,.\n!?]+',

            # Algebraic expressions
            r'[a-zA-Z]\s*[+\-]\s*\d+\s*=\s*\d+',
            r'\d+\s*[a-zA-Z]\s*[+\-]\s*\d+',

            # Fractions and complex expressions
            r'\d+/\d+\s*=\s*[^,.\n!?]+',
            r'[a-zA-Z]\^?\d*\s*[+\-*/]\s*[a-zA-Z]\^?\d*'
        ]

        for pattern in math_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            expressions.extend([match.strip() for match in matches if match.strip()])

        return list(set(expressions))  # Remove duplicates

    def parse_expression_safely(self, expr_str: str) -> Optional[sympy.Basic]:
        """
        Safely parse mathematical expression string into SymPy object.

        Args:
            expr_str: Expression string to parse

        Returns:
            SymPy expression object or None if parsing fails
        """
        try:
            # Clean the expression string
            cleaned = self._clean_expression_string(expr_str)

            if not cleaned:
                return None

            # Handle equations with '='
            if '=' in cleaned:
                parts = cleaned.split('=', 1)
                lhs_str = parts[0].strip()
                rhs_str = parts[1].strip()
                if not lhs_str or not rhs_str:
                    return None
                lhs = self.parse_expression_safely(lhs_str)
                rhs = self.parse_expression_safely(rhs_str)
                if lhs is not None and rhs is not None:
                    return sympy.Eq(lhs, rhs)
                return None

            # Convert ^ to ** for exponentiation
            cleaned_pow = cleaned.replace('^', '**')

            # Try parsing with different strategies
            parsing_strategies = [
                lambda x: parse_expr(x, transformations=self.transformations),
                lambda x: parse_expr(x, evaluate=False),
                lambda x: sympy.sympify(x, evaluate=False)
            ]

            for strategy in parsing_strategies:
                try:
                    result = strategy(cleaned_pow)
                    if result is not None:
                        return result
                except:
                    continue

            logger.debug(f"Failed to parse expression: {expr_str}")
            return None

        except Exception as e:
            logger.debug(f"Expression parsing error for '{expr_str}': {e}")
            return None

    def _clean_expression_string(self, expr_str: str) -> str:
        """
        Clean expression string for parsing.

        Args:
            expr_str: Raw expression string

        Returns:
            Cleaned expression string
        """
        # Remove common text artifacts
        cleaned = expr_str.strip()

        # Remove leading/trailing punctuation
        cleaned = re.sub(r'^[^\w\d\(\-\+]+|[^\w\d\)]+$', '', cleaned)

        # Handle common text patterns
        cleaned = re.sub(r'\bequals?\s+', '= ', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bis\s+', '= ', cleaned, flags=re.IGNORECASE)

        # Replace common Unicode symbols
        cleaned = cleaned.replace('×', '*').replace('÷', '/')
        cleaned = cleaned.replace('−', '-').replace('–', '-')

        # Fix spacing around operators
        cleaned = re.sub(r'\s*([+\-*/=])\s*', r' \1 ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def compare_with_target_solution(
        self,
        candidate_expressions: List[str],
        target_solution: str,
        tolerance: float = 1e-10
    ) -> ExpressionMatch:
        """
        Compare candidate expressions with target solution for equivalence.

        Args:
            candidate_expressions: List of expressions to check
            target_solution: Expected solution to compare against
            tolerance: Numerical tolerance for floating point comparisons

        Returns:
            ExpressionMatch with comparison results
        """
        if not candidate_expressions or not target_solution:
            return ExpressionMatch(
                is_equivalent=False,
                confidence=0.0,
                reason="Empty input"
            )

        # Parse target solution
        target_expr = self.parse_expression_safely(target_solution)
        if target_expr is None:
            return ExpressionMatch(
                is_equivalent=False,
                confidence=0.0,
                reason="Could not parse target solution"
            )

        best_match = ExpressionMatch(is_equivalent=False, confidence=0.0)

        # Check each candidate expression
        for candidate_str in candidate_expressions:
            candidate_expr = self.parse_expression_safely(candidate_str)
            if candidate_expr is None:
                continue

            # Apply equivalence checks
            for check_func in self.equivalence_checks:
                try:
                    match_result = check_func(candidate_expr, target_expr, tolerance)
                    if match_result.confidence > best_match.confidence:
                        best_match = match_result
                        best_match.symbolic_form = str(candidate_expr)

                    # Early return for high-confidence matches
                    if match_result.is_equivalent and match_result.confidence > 0.9:
                        return match_result

                except Exception as e:
                    logger.debug(f"Equivalence check error: {e}")
                    continue

        return best_match

    def _check_direct_equality(
        self,
        expr1: sympy.Basic,
        expr2: sympy.Basic,
        tolerance: float
    ) -> ExpressionMatch:
        """Check direct symbolic equality."""
        try:
            if expr1.equals(expr2):
                return ExpressionMatch(
                    is_equivalent=True,
                    confidence=1.0,
                    transformation_used="direct_equality",
                    reason="Expressions are directly equal"
                )

            # Check numerical equality for expressions with no variables
            if not (expr1.free_symbols or expr2.free_symbols):
                try:
                    val1 = float(expr1.evalf())
                    val2 = float(expr2.evalf())
                    if abs(val1 - val2) < tolerance:
                        return ExpressionMatch(
                            is_equivalent=True,
                            confidence=0.95,
                            transformation_used="numerical_equality",
                            reason=f"Numerically equal: {val1} ≈ {val2}"
                        )
                except:
                    pass

            return ExpressionMatch(is_equivalent=False, confidence=0.0)

        except Exception:
            return ExpressionMatch(is_equivalent=False, confidence=0.0)

    def _check_expanded_form(
        self,
        expr1: sympy.Basic,
        expr2: sympy.Basic,
        tolerance: float
    ) -> ExpressionMatch:
        """Check equality after expansion."""
        try:
            expanded1 = expand(expr1)
            expanded2 = expand(expr2)

            if expanded1.equals(expanded2):
                return ExpressionMatch(
                    is_equivalent=True,
                    confidence=0.9,
                    transformation_used="expanded_form",
                    reason="Equal after expansion"
                )

            return ExpressionMatch(is_equivalent=False, confidence=0.0)

        except Exception:
            return ExpressionMatch(is_equivalent=False, confidence=0.0)

    def _check_factored_form(
        self,
        expr1: sympy.Basic,
        expr2: sympy.Basic,
        tolerance: float
    ) -> ExpressionMatch:
        """Check equality after factoring."""
        try:
            factored1 = factor(expr1)
            factored2 = factor(expr2)

            if factored1.equals(factored2):
                return ExpressionMatch(
                    is_equivalent=True,
                    confidence=0.9,
                    transformation_used="factored_form",
                    reason="Equal after factoring"
                )

            return ExpressionMatch(is_equivalent=False, confidence=0.0)

        except Exception:
            return ExpressionMatch(is_equivalent=False, confidence=0.0)

    def _check_simplified_form(
        self,
        expr1: sympy.Basic,
        expr2: sympy.Basic,
        tolerance: float
    ) -> ExpressionMatch:
        """Check equality after simplification."""
        try:
            simplified1 = simplify(expr1)
            simplified2 = simplify(expr2)

            if simplified1.equals(simplified2):
                return ExpressionMatch(
                    is_equivalent=True,
                    confidence=0.85,
                    transformation_used="simplified_form",
                    reason="Equal after simplification"
                )

            # Check if difference simplifies to zero
            diff = simplify(simplified1 - simplified2)
            if diff == 0:
                return ExpressionMatch(
                    is_equivalent=True,
                    confidence=0.9,
                    transformation_used="difference_zero",
                    reason="Difference simplifies to zero"
                )

            return ExpressionMatch(is_equivalent=False, confidence=0.0)

        except Exception:
            return ExpressionMatch(is_equivalent=False, confidence=0.0)

    def _check_solved_form(
        self,
        expr1: sympy.Basic,
        expr2: sympy.Basic,
        tolerance: float
    ) -> ExpressionMatch:
        """Check if expressions represent the same solution when solved."""
        try:
            def _solve_for_var(expr, var):
                if isinstance(expr, sympy.Equality):
                    return solve(expr, var)
                elif not expr.is_number:
                    return solve(Eq(expr, 0), var)
                else:
                    return [expr]

            # Try to interpret as equations and solve
            for var in self.common_variables:
                if var in expr1.free_symbols or var in expr2.free_symbols:
                    try:
                        sols1 = _solve_for_var(expr1, var)
                        sols2 = _solve_for_var(expr2, var)

                        if sols1 and sols2:
                            # Check if solution sets are equivalent
                            for s1 in sols1:
                                for s2 in sols2:
                                    if simplify(s1 - s2) == 0:
                                        return ExpressionMatch(
                                            is_equivalent=True,
                                            confidence=0.8,
                                            transformation_used="solved_form",
                                            reason=f"Same solution for {var}: {s1}"
                                        )
                    except:
                        continue

            return ExpressionMatch(is_equivalent=False, confidence=0.0)

        except Exception:
            return ExpressionMatch(is_equivalent=False, confidence=0.0)

    def analyze_solution_completeness(self, expressions: List[str], context: str = "") -> Dict[str, Any]:
        """
        Analyze whether expressions represent a complete solution.

        Args:
            expressions: List of mathematical expressions
            context: Contextual information about the problem

        Returns:
            Analysis of solution completeness
        """
        analysis = {
            "is_complete": False,
            "completeness_score": 0.0,
            "indicators": [],
            "missing_elements": []
        }

        if not expressions:
            return analysis

        parsed_expressions = []
        for expr_str in expressions:
            parsed = self.parse_expression_safely(expr_str)
            if parsed is not None:
                parsed_expressions.append((expr_str, parsed))

        if not parsed_expressions:
            return analysis

        # Check for solution indicators
        completeness_indicators = [
            ("variable_assignment", self._has_variable_assignment),
            ("numerical_result", self._has_numerical_result),
            ("equation_solved", self._has_solved_equation),
            ("final_form", self._has_final_form)
        ]

        total_score = 0.0
        for indicator_name, check_func in completeness_indicators:
            if check_func(parsed_expressions):
                analysis["indicators"].append(indicator_name)
                total_score += 0.25

        analysis["completeness_score"] = min(total_score, 1.0)
        analysis["is_complete"] = total_score >= 0.5

        return analysis

    def _has_variable_assignment(self, expressions: List[Tuple[str, sympy.Basic]]) -> bool:
        """Check if expressions contain variable assignments like x = 5."""
        for expr_str, parsed in expressions:
            if '=' in expr_str and re.search(r'[a-zA-Z]\s*=\s*-?\d+', expr_str):
                return True
        return False

    def _has_numerical_result(self, expressions: List[Tuple[str, sympy.Basic]]) -> bool:
        """Check if expressions contain numerical results."""
        for expr_str, parsed in expressions:
            try:
                if parsed.is_number and abs(float(parsed)) > 1e-10:
                    return True
                if isinstance(parsed, sympy.Equality) and parsed.rhs.is_number:
                    return True
            except:
                continue
        return False

    def _has_solved_equation(self, expressions: List[Tuple[str, sympy.Basic]]) -> bool:
        """Check if expressions represent solved equations."""
        for expr_str, parsed in expressions:
            if parsed.free_symbols:
                # Try to solve for each variable
                for var in parsed.free_symbols:
                    try:
                        solutions = solve(parsed, var)
                        if solutions and any(sol.is_number for sol in solutions):
                            return True
                    except:
                        continue
        return False

    def _has_final_form(self, expressions: List[Tuple[str, sympy.Basic]]) -> bool:
        """Check if expressions are in final, simplified form."""
        for expr_str, parsed in expressions:
            simplified = simplify(parsed)
            if simplified != parsed and simplified.is_number:
                return True
        return False


# Global instance for use across the application
math_ast_validator = MathASTValidator()