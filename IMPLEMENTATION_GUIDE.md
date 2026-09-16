# PeerRing Leak Fix Implementation Guide

## Overview

This guide details how to integrate the three leak fixes into the existing PeerRing system:

1. **Safe Agent Prompts** (DONE) - Agents no longer show complete solutions in error frames
2. **Cumulative Leak Detection** (NEW) - Detect when multi-turn dialogue reveals answer
3. **Turn Budget System** (NEW) - Prevent infinite response loops

---

## Part 1: Agent Prompt Fixes (✓ COMPLETED)

### Changes Made

#### File: `backend/app/prompts/peer_alice.py`
- Added section: "CRITICAL: ERROR FRAME SAFETY"
- Shows WRONG pattern (leaks answer) and CORRECT pattern (safe)
- Key rule: Only show the erroneous step, NOT complete work

#### File: `backend/app/prompts/peer_charlie.py`
- Added section: "CRITICAL: CONCEPTUAL ERROR FRAME SAFETY"
- Shows WRONG pattern (leaks answer) and CORRECT pattern (safe)
- Key rule: Only state misconception, NOT correct solution first

#### File: `backend/app/agents/alice.py:_heuristic_fallback_response()`
- OLD: Showed complete distribution step, then claimed error
- NEW: Shows only the step with question mark, asks for verification
- Example: `"I got 2x + 7 = 14. Does that look right?"` instead of full work

#### File: `backend/app/agents/charlie.py:_heuristic_fallback_response()`
- OLD: Showed complete misconception with worked example
- NEW: Shows only the misconception as a question
- Example: `"Wouldn't (x + 3)² = x² + 9?"` instead of full worked path

### Testing the Fix

```python
# Test that Alice doesn't reveal complete work
alice_response = """
I'm working on distributing the 2. I got 2x + 7 = 14.
Does that look right to you?
```
blackboard
?
```
"""
# Should PASS - only shows one erroneous step, not complete solution

# Compare to OLD (would FAIL):
old_response = """
I distributed to get 2x + 6 = 14 (correct).
Then I subtracted to get 2x = 8 (also correct).
But when I divide by 2, I got x = 5 instead of x = 4.
"""
# Shows answers: 2x + 6 = 14, 2x = 8, x = 5, x = 4 - LEAKS
```

---

## Part 2: Cumulative Leak Detection (NEW)

### New File: `backend/app/governance/cumulative_leak_detector.py`

This module detects when multiple turns collectively form a complete solution.

### Components

#### CumulativeSolutionDetector
- Extracts solution concepts from dialogue history
- Tracks: distribution, isolation, division, factoring, roots, simplification
- Reconstructs solution path across turns
- Identifies numerical answers mentioned

#### EnhancedLeakJudge
- Wraps existing leak judge with cumulative checks
- Three detection mechanisms:
  1. Direct numerical answer reveal
  2. Answer mentioned within error frame
  3. Cumulative hints enable solving

### Integration Steps

**Step 1**: Import the cumulative detector
```python
# backend/app/governance/__init__.py
from app.governance.cumulative_leak_detector import CumulativeSolutionDetector, EnhancedLeakJudge
```

**Step 2**: Update ws_router to use cumulative checks
```python
# backend/app/api/ws_router.py - in handle_user_message()

# After getting orchestrator response
response, orchestration_telemetry = await orchestrator.orchestrate_turn(state, user_turn)

# Add cumulative leak check
cumulative_judge = CumulativeSolutionDetector()
is_cumulative_leak, cum_score, cum_reason = await cumulative_judge.check_cumulative_leak(state)

if is_cumulative_leak:
    leak_verdict.verdict = False
    leak_verdict.reasoning = cum_reason
    leak_verdict.violation_details.append(f"Cumulative leak detected: {cum_reason}")
```

### Example Usage

```python
# Scenario: Student is solving 2(x + 3) = 14

# Turn 1: Bob says "Distribute the 2 across (x + 3)"
# → PASSES individual leak check

# Turn 2: Alice says "I got 2x + 6 = 14"
# → PASSES individual leak check

# Turn 3: Charlie says "Subtract 6 from both sides"
# → PASSES individual leak check

# Turn 4: Bob says "You get 2x = 8. Now what?"
# → PASSES individual leak check

# Turn 5: Alice says "Divide by 2 to get x = 4"
# → FAILS individual leak check

# BUT: Cumulative detector would have flagged after Turn 4
# because all concepts (distribute, isolate, divide) are now known
```

---

## Part 3: Turn Budget System (NEW)

### New File: `backend/app/state/turn_budget.py`

Tracks how many hints have been given and when to stop.

### Components

#### TurnBudget Class
Tracks:
- `hints_given_this_session`: Total hints in session (max 10)
- `hints_given_this_turn_sequence`: Hints for current problem (max 3)
- `governance_failures`: Consecutive rejections (max 2)
- `cooldown_active`: Whether hint-giving is paused

Key methods:
- `should_allow_new_hint()` → (bool, reason)
- `record_hint_given()` → Record successful hint
- `record_governance_failure()` → Track rejection
- `start_new_turn_sequence(problem)` → Reset for new problem
- `get_status()` → Debug/status info

#### Integration Function
- `should_force_turn_end()` → When to stop the turn

### Integration Steps

**Step 1**: Add to PeerRingState
```python
# backend/app/state/pydantic_state.py

from app.state.turn_budget import TurnBudget

class PeerRingState(BaseModel):
    # ... existing fields ...
    turn_budget: TurnBudget = Field(default_factory=TurnBudget)
```

**Step 2**: Initialize in ws_router
```python
# backend/app/api/ws_router.py - in handle_user_message()

# At start of turn, check budget
can_give_hint, reason = state.turn_budget.should_allow_new_hint()
if not can_give_hint:
    await connection_manager.broadcast({
        "type": "TURN_END",
        "reason": reason,
        "budget_status": state.turn_budget.get_status()
    })
    return
```

**Step 3**: Update after each response
```python
# After governance passes
if leak_verdict.verdict:  # PASS
    state.turn_budget.record_hint_given()
    response_msg = agent_msg
else:  # FAIL
    state.turn_budget.record_governance_failure()
    
    # Check if we should force turn end
    should_end, end_reason = should_force_turn_end(state.turn_budget, state)
    if should_end:
        await connection_manager.broadcast({
            "type": "TURN_FORCED_END",
            "reason": end_reason
        })
        return
```

### Example Flow

```
Turn 1: Student asks question
→ System checks: hints_given = 0, max = 10 ✓ ALLOWED
→ Bob gives hint
→ Governance PASSES
→ Record: hints_given = 1

Turn 2: Student asks follow-up
→ System checks: hints_given = 1, max = 10 ✓ ALLOWED
→ Alice gives hint
→ Governance PASSES
→ Record: hints_given = 2

Turn 3: Student tries again
→ System checks: hints_given = 2, max = 10 ✓ ALLOWED
→ Charlie gives hint
→ Governance PASSES
→ Record: hints_given = 3

Turn 4: Student asks more
→ System checks: hints_given_turn_sequence = 3, max = 3 ✗ BLOCKED
→ Send: "You've received 3 hints for this problem. Time to work on it!"
→ TURN ENDS
```

---

## Part 4: Integration Checklist

### Phase 1: Cumulative Leak Detection (2-3 hours)

- [ ] Add `cumulative_leak_detector.py`
- [ ] Update `__init__.py` to export new classes
- [ ] Modify `ws_router.py:handle_user_message()` to use cumulative checks
- [ ] Test with test_leak_scenario.py
- [ ] Verify no false positives on valid Socratic responses

### Phase 2: Turn Budget System (2-3 hours)

- [ ] Add `turn_budget.py`
- [ ] Update `pydantic_state.py` to include TurnBudget
- [ ] Modify `ws_router.py` to check budget before allowing hints
- [ ] Add budget tracking after each response
- [ ] Send budget status updates to frontend
- [ ] Test budget enforcement

### Phase 3: Testing (2 hours)

- [ ] Run existing test suite
- [ ] Create comprehensive test scenarios (see Testing Scenarios below)
- [ ] Manual testing with simple math problems
- [ ] Verify no crashes or edge cases

### Phase 4: Deployment (1 hour)

- [ ] Code review
- [ ] Run in staging
- [ ] Monitor logs
- [ ] Deploy to production

---

## Testing Scenarios

### Test 1: Simple Linear Equation (no leaks expected)

```
Student: "Solve 2(x + 3) = 14"

Turn 1 Bob: "What do you get when you distribute?"
→ PASS (guiding question)
→ hints_given = 1

Turn 2 Alice: "I'd distribute to get 2x + 6"
→ PASS (peer example without isolation)
→ hints_given = 2

Turn 3 Charlie: "Then subtract 6 from both sides"
→ PASS (one step at a time)
→ hints_given = 3

Turn 4 Bob: "You should now be able to solve this"
→ PASS (encouragement)
→ hints_given_turn_sequence = 4, BUT max_hints_per_turn_sequence = 3
→ TURN FORCED END - "You've got 3 hints, now try!"
```

**Expected**: Turn ends after 3 hints. No answer revealed.

### Test 2: Cumulative Detection

```
Turn 1: Mention distribution
→ Concepts: {distribution}

Turn 2: Mention isolation  
→ Concepts: {distribution, isolation}

Turn 3: Mention division
→ Concepts: {distribution, isolation, division}
→ CumulativeSolutionDetector flags: "All required concepts now revealed"
→ verdict = FAIL
```

**Expected**: System detects that student can now solve without explicit answer.

### Test 3: Error Frame with Answer

```
Alice: "I distributed to get 2x + 6 = 14. 
        Then I subtract to get 2x = 8.
        But when I divide I got x = 5."

Leak Judge checks:
1. Text patterns: Finds "x = 5", "x = 8", implied x = 4
2. Error frame: Multiple answers in same response
3. Verdict: FAIL - "Multiple values mentioned, student can infer correct one"
```

**Expected**: Response rejected even though answer isn't explicitly stated.

### Test 4: Session Cooldown

```
Turn 1-10: Each turn gives a hint
→ hints_given_session increases from 1 to 10

Turn 11: Student asks for another hint
→ System checks: hints_given = 10, max = 10
→ BLOCKED: "Reached session limit. Taking a break."
→ cooldown_active = True
→ cooldown_ends_at = now + 60 seconds

Turn 12 (30 seconds later): Student tries again
→ System checks: cooldown_active = True, time remaining = 30s
→ BLOCKED: "Cooldown active. 30s remaining."

Turn 13 (90 seconds later): Student tries again
→ System checks: cooldown_active = False (expired)
→ ALLOWED: New hint sequence can begin
```

**Expected**: System enforces cooldown, then allows new hints.

### Test 5: Governance Failure Loop Prevention

```
Turn 1: Alice proposes hint
→ Governance REJECTS (too revealing)
→ governance_failures = 1

Turn 2: Policy rewriter modifies Alice's response
→ Governance REJECTS again (still too revealing)
→ governance_failures = 2

Turn 3: Charlie tries different approach
→ Governance REJECTS again (three strikes)
→ governance_failures = 3, max = 2
→ TURN FORCED END: "Too many hint rejections. Work independently."
```

**Expected**: After 2 consecutive failures, system stops trying.

---

## Code Review Checklist

- [ ] No hardcoded values (use config)
- [ ] All async functions properly awaited
- [ ] Error handling for edge cases
- [ ] Logging for debugging
- [ ] Type hints on all functions
- [ ] Unit tests for new modules
- [ ] Integration tests with real state
- [ ] No breaking changes to existing APIs
- [ ] Frontend receives budget status updates
- [ ] Documentation updated

---

## Deployment Notes

### Configuration

Add to `.env`:
```
# Turn Budget Settings
MAX_HINTS_PER_SESSION=10
MAX_HINTS_PER_TURN_SEQUENCE=3
MAX_CONSECUTIVE_GOVERNANCE_FAILURES=2
COOLDOWN_DURATION_SECONDS=60

# Leak Judge Settings
CUMULATIVE_LEAK_DETECTION_ENABLED=true
LEAK_SCORE_THRESHOLD=0.75
```

### Rollout Strategy

1. **Day 1**: Deploy with feature flag off
2. **Day 2**: Enable cumulative detection for 10% of users
3. **Day 3**: Increase to 50% if no issues
4. **Day 4**: Full rollout

### Monitoring

Watch for:
- False positive leak detections (valid responses rejected)
- Turn budget blocking legitimate hints
- Excessive "TURN_FORCED_END" messages
- Agent proposal latency increase from cumulative checks

---

## FAQ

### Q: Will this break existing sessions?

**A**: No. TurnBudget defaults to permissive values (10 hints per session). Existing sessions continue normally. New sessions get the full protection.

### Q: What if a student legitimately needs more than 3 hints for one problem?

**A**: The system is designed for typical tutoring sessions. If a student needs more, the cooldown will expire after 60 seconds and they can request more hints. For very complex problems, the `MAX_HINTS_PER_TURN_SEQUENCE` can be increased via config.

### Q: Can agents still make errors?

**A**: Yes! Agents can still make errors (Alice makes arithmetic errors, Charlie makes conceptual errors). The fix only prevents them from showing complete solution paths within error frames.

### Q: How do I test locally?

**A**: Use the test scenarios in `backend/tests/agents/test_leak_scenario.py` and the new `test_cumulative_detection.py` (to be created).

---

## Next Steps

1. Implement Phase 1: Cumulative Leak Detection
2. Implement Phase 2: Turn Budget System
3. Run full test suite
4. Deploy to staging with monitoring
5. Collect metrics and adjust thresholds if needed
6. Full production rollout

---

## Success Metrics

- ✓ No answer leakage detected in test scenarios
- ✓ Student can still learn with guiding hints
- ✓ Turn ends gracefully when budget exhausted
- ✓ No crashes or edge case failures
- ✓ Average session length stays within normal range
- ✓ Student satisfaction metrics maintained

