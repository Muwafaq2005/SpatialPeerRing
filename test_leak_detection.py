"""
Simple Leak Test - Checks if leak judge detects basic answer patterns
No LLM calls, just pattern-based detection
"""

import sys
sys.path.insert(0, 'backend')

from app.governance.leak_judge import LeakJudge
from app.state.pydantic_state import PeerRingState, DialogueMessage, MessageRole
from datetime import datetime

def test_basic_leak_patterns():
    """Test basic text pattern detection without LLM"""

    leak_judge = LeakJudge()
    state = PeerRingState(session_id='test-001')

    print("\n" + "="*70)
    print("LEAK JUDGE PATTERN-BASED DETECTION TESTS")
    print("="*70)

    # Test cases: (description, response, should_leak)
    test_cases = [
        (
            "Direct answer: x = 4",
            "The answer is x = 4",
            True
        ),
        (
            "Equation with answer",
            "Solve: 2(x + 3) = 14, so x = 4",
            True
        ),
        (
            "Solution keyword with number",
            "The solution is x = 4",
            True
        ),
        (
            "Complete worked solution",
            """
            Distribute: 2x + 6 = 14
            Isolate: 2x = 8
            Divide: x = 4
            """,
            True
        ),
        (
            "Guiding question (safe)",
            "When you distribute 2 across (x + 3), what do you get?",
            False
        ),
        (
            "Socratic hint (safe)",
            "Try subtracting 6 from both sides. What's left?",
            False
        ),
        (
            "Partial work (safe)",
            "I got 2x + 6 = 14. Does that look right?",
            False
        ),
    ]

    results = []
    for description, response, should_leak in test_cases:
        # Do text pattern analysis (synchronous part)
        text_analysis = leak_judge._analyze_text_patterns(response)
        leak_score = text_analysis["score"]

        detected_leak = leak_score > 0.5
        is_correct = detected_leak == should_leak

        status = "✓ PASS" if is_correct else "✗ FAIL"
        result = {
            'description': description,
            'expected_leak': should_leak,
            'detected_leak': detected_leak,
            'leak_score': leak_score,
            'passed': is_correct,
            'response': response[:50] + "..." if len(response) > 50 else response
        }
        results.append(result)

        print(f"\n{status}")
        print(f"  Test: {description}")
        print(f"  Response: {response[:60]}...")
        print(f"  Expected Leak: {should_leak}")
        print(f"  Detected Leak: {detected_leak}")
        print(f"  Leak Score: {leak_score:.2f}")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    passed = sum(1 for r in results if r['passed'])
    total = len(results)
    print(f"Passed: {passed}/{total}")

    for r in results:
        status = "✓" if r['passed'] else "✗"
        print(f"{status} {r['description']}: score={r['leak_score']:.2f}")

    return passed == total

if __name__ == "__main__":
    success = test_basic_leak_patterns()
    sys.exit(0 if success else 1)
