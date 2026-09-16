"""
Test: Do the agents actually leak answers?
Checks current heuristic responses from Alice and Charlie
"""

import sys
sys.path.insert(0, 'backend')

from app.agents.alice import AliceAgent
from app.agents.charlie import CharlieAgent
from app.state.pydantic_state import (
    PeerRingState, DialogueMessage, MessageRole, CandidateAction, AgentType
)
from app.governance.leak_judge import LeakJudge
from datetime import datetime

def test_agent_responses():
    """Test if agents leak answers in their responses"""

    print("\n" + "="*70)
    print("AGENT RESPONSE LEAK TEST")
    print("="*70)

    # Setup
    state = PeerRingState(session_id='agent-test-001')
    state.add_message(DialogueMessage(
        role=MessageRole.SYSTEM,
        content="Algebra: Solve 2(x + 3) = 14",
        timestamp=datetime.now()
    ))
    state.add_message(DialogueMessage(
        role=MessageRole.USER,
        content="Can you help me solve this?",
        timestamp=datetime.now()
    ))

    leak_judge = LeakJudge()
    alice = AliceAgent()
    charlie = CharlieAgent()

    # Test Alice's heuristic response
    print("\n" + "-"*70)
    print("TEST 1: ALICE HEURISTIC RESPONSE (Arithmetic Error)")
    print("-"*70)

    action = CandidateAction(
        agent_id="alice",
        action_type="arithmetic_error",
        metadata={"inject_error": True, "proposed_error_type": "MULTIPLICATION_SLIP"}
    )

    # Get heuristic response (doesn't call LLM)
    response, tokens, error_type = alice._heuristic_fallback_response(action, state)

    print(f"Response:\n{response}\n")

    # Check for leaks
    text_analysis = leak_judge._analyze_text_patterns(response)
    leak_score = text_analysis["score"]

    print(f"Leak Score: {leak_score:.2f}")
    print(f"Violations: {text_analysis['violations']}")
    print(f"Status: {'⚠️ LEAKS' if leak_score > 0.5 else '✓ SAFE'}")

    # Test Charlie's heuristic response
    print("\n" + "-"*70)
    print("TEST 2: CHARLIE HEURISTIC RESPONSE (Conceptual Error)")
    print("-"*70)

    action = CandidateAction(
        agent_id="charlie",
        action_type="conceptual_trap",
        metadata={"inject_error": True, "proposed_error_type": "FRESHMAN_DREAM"}
    )

    response, tokens, error_type = charlie._heuristic_fallback_response(action, state)

    print(f"Response:\n{response}\n")

    # Check for leaks
    text_analysis = leak_judge._analyze_text_patterns(response)
    leak_score = text_analysis["score"]

    print(f"Leak Score: {leak_score:.2f}")
    print(f"Violations: {text_analysis['violations']}")
    print(f"Status: {'⚠️ LEAKS' if leak_score > 0.5 else '✓ SAFE'}")

    # Test Alice clean response
    print("\n" + "-"*70)
    print("TEST 3: ALICE CLEAN RESPONSE (No Error)")
    print("-"*70)

    action = CandidateAction(
        agent_id="alice",
        action_type="clean_step",
        metadata={"inject_error": False}
    )

    response, tokens, error_type = alice._heuristic_fallback_response(action, state)

    print(f"Response:\n{response}\n")

    # Check for leaks
    text_analysis = leak_judge._analyze_text_patterns(response)
    leak_score = text_analysis["score"]

    print(f"Leak Score: {leak_score:.2f}")
    print(f"Violations: {text_analysis['violations']}")
    print(f"Status: {'⚠️ LEAKS' if leak_score > 0.5 else '✓ SAFE'}")

    # Test Charlie clean response
    print("\n" + "-"*70)
    print("TEST 4: CHARLIE CLEAN RESPONSE (No Error)")
    print("-"*70)

    action = CandidateAction(
        agent_id="charlie",
        action_type="clean_suggestion",
        metadata={"inject_error": False}
    )

    response, tokens, error_type = charlie._heuristic_fallback_response(action, state)

    print(f"Response:\n{response}\n")

    # Check for leaks
    text_analysis = leak_judge._analyze_text_patterns(response)
    leak_score = text_analysis["score"]

    print(f"Leak Score: {leak_score:.2f}")
    print(f"Violations: {text_analysis['violations']}")
    print(f"Status: {'⚠️ LEAKS' if leak_score > 0.5 else '✓ SAFE'}")

if __name__ == "__main__":
    test_agent_responses()
