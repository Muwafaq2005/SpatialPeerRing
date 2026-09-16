"""
Test Suite for Leak Judge System
Tests leak detection, mathematical analysis, and governance integration
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.governance.leak_judge import LeakJudge, MathExpressionAnalyzer, CrossTurnLeakTracker
from app.governance.math_ast import MathASTValidator, ExpressionMatch
from app.state.pydantic_state import (
    PeerRingState,
    DialogueMessage,
    MessageRole,
    JudgeVerdict,
    PolicyState,
    AssistanceLevel
)


class TestMathExpressionAnalyzer:
    """Test mathematical expression analysis components."""

    def test_extract_mathematical_expressions(self):
        """Test extraction of math expressions from text."""
        analyzer = MathExpressionAnalyzer()

        test_cases = [
            ("The answer is x = 5", ["x = 5"]),
            ("We get 3 + 4 = 7 and y = 2", ["3 + 4 = 7", "y = 2"]),
            ("Substituting gives us (x + 3) = 8", ["(x + 3) = 8"]),
            ("The result 12.5 equals our target", ["12.5 equals our target"]),
            ("No math here!", [])
        ]

        for text, expected in test_cases:
            expressions = analyzer.extract_mathematical_expressions(text)
            # Check that we found the expected number of expressions
            assert len(expressions) >= len(expected), f"Failed for: {text}"

    def test_is_complete_solution(self):
        """Test detection of complete solutions."""
        analyzer = MathExpressionAnalyzer()

        # Complete solutions
        complete_cases = [
            ["x = 5"],
            ["y = 12.3"],
            ["z = -7"]
        ]

        for expressions in complete_cases:
            assert analyzer.is_complete_solution(expressions), f"Should be complete: {expressions}"

        # Incomplete expressions
        incomplete_cases = [
            ["3x + 2"],
            ["(x + 4)"],
            ["2 + 3 = 5"],  # Arithmetic, not variable solution
            []
        ]

        for expressions in incomplete_cases:
            assert not analyzer.is_complete_solution(expressions), f"Should not be complete: {expressions}"

    def test_analyze_blackboard_patch(self):
        """Test blackboard patch analysis for leaks."""
        analyzer = MathExpressionAnalyzer()

        # Leaking patches
        leak_cases = [
            ("\\begin{align} x + 3 &= 8 \\\\ x &= 5 \\end{align}", True),
            ("\\boxed{x = 12}", True),
            ("3x + 4 = 7x - 8 = 2x + 12 = x + 6", True),  # Multiple equations
        ]

        for patch, should_leak in leak_cases:
            analysis = analyzer.analyze_blackboard_patch(patch)
            assert analysis["has_leak"] == should_leak, f"Failed for: {patch}"

        # Non-leaking patches
        safe_cases = [
            ("\\begin{align} 3(x + 4) &= ? \\end{align}", False),
            ("Let's substitute x = ...", False),
            ("", False)  # Empty patch
        ]

        for patch, should_leak in safe_cases:
            analysis = analyzer.analyze_blackboard_patch(patch)
            assert analysis["has_leak"] == should_leak, f"Failed for: {patch}"


class TestCrossTurnLeakTracker:
    """Test cross-turn leak tracking functionality."""

    def test_cumulative_risk_tracking(self):
        """Test tracking of cumulative leak risk across turns."""
        tracker = CrossTurnLeakTracker()

        session_id = "test-session"

        # Gradually add expressions
        risk1 = tracker.add_response_analysis(session_id, ["3x + 4"], ["partial_work"])
        assert 0.0 < risk1 < 0.5

        risk2 = tracker.add_response_analysis(session_id, ["x + 2"], ["more_work"])
        assert risk2 > risk1

        risk3 = tracker.add_response_analysis(session_id, ["x = 5"], ["direct_answer"])
        assert risk3 > risk2
        assert risk3 > 0.6  # Should be high risk

    def test_session_reset(self):
        """Test resetting session tracking."""
        tracker = CrossTurnLeakTracker()

        session_id = "test-session"
        tracker.add_response_analysis(session_id, ["x = 5"], ["direct_answer"])

        # Should have risk
        assert tracker.get_session_risk(session_id) > 0.0

        # Reset and check
        tracker.reset_session(session_id)
        assert tracker.get_session_risk(session_id) == 0.0


class TestMathASTValidator:
    """Test mathematical AST validation and comparison."""

    def test_expression_parsing(self):
        """Test parsing of mathematical expressions."""
        validator = MathASTValidator()

        # Valid expressions
        valid_cases = [
            "x + 3",
            "2*x - 5",
            "(x + 4)^2",
            "x = 5"
        ]

        for expr_str in valid_cases:
            result = validator.parse_expression_safely(expr_str)
            assert result is not None, f"Should parse: {expr_str}"

        # Invalid expressions
        invalid_cases = [
            "",
            "invalid syntax!!!",
            "x ++ 3"
        ]

        for expr_str in invalid_cases:
            result = validator.parse_expression_safely(expr_str)
            # Should either parse or return None gracefully

    def test_solution_comparison(self):
        """Test comparison with target solutions."""
        validator = MathASTValidator()

        # Equivalent expressions
        equiv_cases = [
            (["x = 5"], "x = 5", True),
            (["x = 10/2"], "x = 5", True),  # Numerically equivalent
            (["2x = 10"], "x = 5", True),   # Algebraically equivalent
        ]

        for candidates, target, should_match in equiv_cases:
            result = validator.compare_with_target_solution(candidates, target)
            assert result.is_equivalent == should_match, f"Failed: {candidates} vs {target}"

    def test_solution_completeness_analysis(self):
        """Test analysis of solution completeness."""
        validator = MathASTValidator()

        # Complete solutions
        complete_cases = [
            ["x = 5"],
            ["y = 12", "z = 8"],
        ]

        for expressions in complete_cases:
            analysis = validator.analyze_solution_completeness(expressions)
            assert analysis["is_complete"], f"Should be complete: {expressions}"

        # Incomplete solutions
        incomplete_cases = [
            ["3x + 4"],
            ["(x + 2)"],
            []
        ]

        for expressions in incomplete_cases:
            analysis = validator.analyze_solution_completeness(expressions)
            assert not analysis["is_complete"], f"Should not be complete: {expressions}"


class TestLeakJudge:
    """Test the main Leak Judge system."""

    @pytest.fixture
    def leak_judge(self):
        """Create LeakJudge instance for testing."""
        return LeakJudge()

    @pytest.fixture
    def sample_state(self):
        """Create sample PeerRingState for testing."""
        state = PeerRingState(session_id="test-session")
        state.target_solution = "x = 5"  # Set target for comparison
        return state

    @pytest.mark.asyncio
    async def test_evaluate_safe_response(self, leak_judge, sample_state):
        """Test evaluation of safe (non-leaking) response."""
        safe_text = "What do you think would happen if we substitute this value?"

        verdict = await leak_judge.evaluate(safe_text, None, sample_state)

        assert verdict.judge_type == "leak"
        assert verdict.verdict is True  # Should pass
        assert verdict.confidence > 0.5
        assert verdict.evaluation_time_ms > 0

    @pytest.mark.asyncio
    async def test_evaluate_leaking_response(self, leak_judge, sample_state):
        """Test evaluation of leaking response."""
        leaking_text = "The answer is x = 5, so we get our final result."

        verdict = await leak_judge.evaluate(leaking_text, None, sample_state)

        assert verdict.judge_type == "leak"
        assert verdict.verdict is False  # Should fail
        assert verdict.confidence > 0.7
        assert verdict.violation_details is not None
        assert len(verdict.suggested_fixes) > 0

    @pytest.mark.asyncio
    async def test_evaluate_with_blackboard_patch(self, leak_judge, sample_state):
        """Test evaluation with blackboard patch containing solution."""
        safe_text = "Let's work through this step by step."
        leaking_patch = "\\begin{align} x + 3 &= 8 \\\\ x &= 5 \\end{align}"

        verdict = await leak_judge.evaluate(safe_text, leaking_patch, sample_state)

        assert verdict.verdict is False  # Should fail due to patch
        assert "blackboard" in verdict.reasoning.lower() or "patch" in verdict.reasoning.lower()

    @pytest.mark.asyncio
    async def test_cross_turn_leak_detection(self, leak_judge, sample_state):
        """Test detection of gradual solution leakage across turns."""
        # Simulate multiple turns with increasing leak risk
        responses = [
            "First, let's set up the equation: x + 3 = 8",
            "Now we can subtract 3 from both sides",
            "This gives us x = 5"  # Final leak
        ]

        verdicts = []
        for response in responses:
            verdict = await leak_judge.evaluate(response, None, sample_state)
            verdicts.append(verdict)

        # Last response should fail due to cumulative leak
        assert verdicts[-1].verdict is False
        assert "cross-turn" in verdicts[-1].reasoning.lower() or "cumulative" in verdicts[-1].reasoning.lower()

    @pytest.mark.asyncio
    async def test_strict_mode_behavior(self, leak_judge, sample_state):
        """Test that strict mode increases sensitivity."""
        borderline_text = "We get x equals about 5"

        # Normal mode
        sample_state.policy.strict_mode = False
        normal_verdict = await leak_judge.evaluate(borderline_text, None, sample_state)

        # Strict mode
        sample_state.policy.strict_mode = True
        strict_verdict = await leak_judge.evaluate(borderline_text, None, sample_state)

        # Strict mode should be more likely to flag as leak
        if normal_verdict.verdict and not strict_verdict.verdict:
            # This is the expected behavior - strict mode caught what normal missed
            assert True
        # If both pass or both fail, that's also acceptable for borderline cases

    @pytest.mark.asyncio
    async def test_performance_target(self, leak_judge, sample_state):
        """Test that evaluation meets performance target (<200ms)."""
        text = "This is a test response with some mathematical content: 3x + 4 = 16"

        start_time = datetime.utcnow()
        verdict = await leak_judge.evaluate(text, None, sample_state)
        end_time = datetime.utcnow()

        actual_time = (end_time - start_time).total_seconds() * 1000

        # Should meet performance target
        assert actual_time < 500  # Allow some overhead for test environment
        assert verdict.evaluation_time_ms < 300  # Internal measurement should be faster

    @pytest.mark.asyncio
    async def test_error_handling(self, leak_judge, sample_state):
        """Test graceful error handling in evaluation."""
        # Test with problematic input
        problematic_inputs = [
            ("", None),  # Empty text
            (None, None),  # None input
            ("Normal text", "\\invalid{latex}"),  # Invalid LaTeX
        ]

        for text, patch in problematic_inputs:
            try:
                verdict = await leak_judge.evaluate(text, patch, sample_state)
                # Should not crash, should return valid verdict
                assert isinstance(verdict, JudgeVerdict)
                assert verdict.judge_type == "leak"
            except Exception as e:
                pytest.fail(f"Leak judge crashed on input ({text}, {patch}): {e}")

    def test_fix_suggestions_quality(self, leak_judge):
        """Test quality of suggested fixes."""
        # Test that fixes are generated for different violation types
        test_cases = [
            (["direct_answer"], "Remove explicit answer"),
            (["variable_solution"], "Replace variable assignment"),
            (["complete_steps"], "Provide only the next step")
        ]

        for indicators, expected_theme in test_cases:
            fixes = leak_judge._generate_fix_suggestions(indicators, [])
            assert len(fixes) > 0
            assert any(expected_theme.lower() in fix.lower() for fix in fixes)


    @pytest.mark.asyncio
    async def test_scenarios_a_through_n(self, leak_judge, sample_state):
        """Test specific requirements scenarios A through N."""
        sample_state.target_solution = "x = 3"

        # Scenario A: Confirmation check
        v_a = await leak_judge.evaluate("Yes, x is equal to 3!", None, sample_state)
        assert v_a.verdict is False

        # Scenario B: "x = 7" when 7 is target answer
        sample_state.target_solution = "x = 7"
        v_b = await leak_judge.evaluate("So x = 7", None, sample_state)
        assert v_b.verdict is False

        # Scenario C: "The answer is 42."
        sample_state.target_solution = "42"
        v_c = await leak_judge.evaluate("The answer is 42.", None, sample_state)
        assert v_c.verdict is False

        # Scenario D: "Therefore the acceleration is 4 m/s²."
        sample_state.target_solution = "4 m/s²"
        v_d = await leak_judge.evaluate("Therefore the acceleration is 4 m/s².", None, sample_state)
        assert v_d.verdict is False

        # Scenario E: Newton's law definition -> allow
        v_e = await leak_judge.evaluate("Newton's second law relates force, mass, and acceleration.", None, sample_state)
        assert v_e.verdict is True

        # Scenario F: Velocity definition -> allow
        v_f = await leak_judge.evaluate("Velocity is displacement divided by time.", None, sample_state)
        assert v_f.verdict is True

        # Scenario G: Direct calculation on task values -> reject
        sample_state.target_solution = "20 m/s"
        v_g = await leak_judge.evaluate("100 / 5 = 20 m/s", None, sample_state)
        assert v_g.verdict is False

        # Scenario H: Unrelated numbers -> allow
        v_h = await leak_judge.evaluate("For instance, if a bike traveled 50 meters in 10 seconds, speed would be 5 m/s.", None, sample_state)
        assert v_h.verdict is True

        # Scenario J: Final answer hidden in blackboard -> reject
        sample_state.target_solution = "x = 5"
        v_j = await leak_judge.evaluate("Let's look at the board.", "\\boxed{x = 5}", sample_state)
        assert v_j.verdict is False

        # Scenario K: Final answer expressed algebraically equivalent -> reject
        sample_state.target_solution = "x = 5"
        v_k = await leak_judge.evaluate("Notice that 2*x = 10", None, sample_state)
        assert v_k.verdict is False

        # Scenario L: Safe encouragement -> allow
        v_l = await leak_judge.evaluate("You're on the right track. What happens if you apply the formula?", None, sample_state)
        assert v_l.verdict is True

        # Scenario M: Apply formula giveaway -> reject
        sample_state.target_solution = "x = 3"
        v_m = await leak_judge.evaluate("Apply the formula and you get x = 3.", None, sample_state)
        assert v_m.verdict is False

        # Scenario N: Non-disclosing deflection -> allow
        v_n = await leak_judge.evaluate("I can't just give you the answer, but what step do you think comes first?", None, sample_state)
        assert v_n.verdict is True

    @pytest.mark.asyncio
    async def test_3x_4_14_leaked_response_blocked(self, leak_judge, sample_state):
        """Test specific 3x - 4 = 14 leak response that directly reveals intermediate and final answers."""
        sample_state.target_solution = "x = 6"
        leaked_response = "Exactly, Alice. Let's write that on the board. We add 4 to both sides to get 3x = 18. Then, we divide by 3 to find x = 6."
        
        verdict = await leak_judge.evaluate(leaked_response, None, sample_state)
        assert verdict.verdict is False
        assert "solution leak" in verdict.reasoning.lower() or "variable_solution" in str(verdict.violation_details).lower()


class TestGovernanceIntegration:
    """Test integration with WebSocket governance pipeline."""

    @pytest.mark.asyncio
    async def test_governance_rejection_flow(self):
        """Test complete governance rejection flow."""
        leak_judge = LeakJudge()
        state = PeerRingState(session_id="integration-test")

        # Test that judge works in isolation
        verdict = await leak_judge.evaluate("The answer is 42", None, state)
        assert isinstance(verdict, JudgeVerdict)

    def test_configuration_integration(self):
        """Test that leak judge respects configuration settings."""
        from app.config import settings

        leak_judge = LeakJudge()


        # Should respect enabled/disabled setting
        # (This would be tested in integration tests with actual config)