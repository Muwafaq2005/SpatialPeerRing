"""
Direct Agent Heuristic Response Test
Tests if agents leak answers in their fallback responses
"""

import sys
sys.path.insert(0, 'backend')

from app.agents.alice import AliceAgent
from app.agents.charlie import CharlieAgent
from app.state.pydantic_state import PeerRingState, DialogueMessage, MessageRole
from app.governance.leak_judge import LeakJudge
from datetime import datetime

def test_heuristic_responses():
    """Test raw heuristic responses without orchestration"""

    print("\n" + "="*70)
    print("AGENT HEURISTIC RESPONSE LEAK TEST")
    print("="*70)

    state = PeerRingState(session_id='heuristic-test-001')
    state.add_message(DialogueMessage(
        role=MessageRole.SYSTEM,
        content="Algebra: Solve 2(x + 3) = 14",
        timestamp=datetime.now()
    ))

    leak_judge = LeakJudge()
    alice = AliceAgent()
    charlie = CharlieAgent()

    # Test 1: Alice with error injection
    print("\n" + "-"*70)
    print("TEST 1: ALICE HEURISTIC - WITH ARITHMETIC ERROR")
    print("-"*70)

    try:
        response, tokens, error_type = alice._heuristic_fallback_response_with_error()
        print(f"Response:\n{response}\n")

        text_analysis = leak_judge._analyze_text_patterns(response)
        leak_score = text_analysis["score"]

        print(f"Leak Score: {leak_score:.2f}")
        print(f"Violations: {text_analysis['violations']}")
        print(f"Result: {'⚠️ LEAKS ANSWER' if leak_score > 0.5 else '✓ SAFE'}")
    except Exception as e:
        print(f"Method not found: {e}")
        print("Let me check available methods...")
        print(f"Alice methods: {[m for m in dir(alice) if not m.startswith('_')]}")

    # Test 2: Charlie with error
    print("\n" + "-"*70)
    print("TEST 2: CHARLIE HEURISTIC - WITH CONCEPTUAL ERROR")
    print("-"*70)

    try:
        response, tokens, error_type = charlie._heuristic_fallback_response_with_error()
        print(f"Response:\n{response}\n")

        text_analysis = leak_judge._analyze_text_patterns(response)
        leak_score = text_analysis["score"]

        print(f"Leak Score: {leak_score:.2f}")
        print(f"Violations: {text_analysis['violations']}")
        print(f"Result: {'⚠️ LEAKS ANSWER' if leak_score > 0.5 else '✓ SAFE'}")
    except Exception as e:
        print(f"Method not found: {e}")

if __name__ == "__main__":
    test_heuristic_responses()
