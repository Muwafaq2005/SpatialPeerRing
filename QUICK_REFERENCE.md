# Quick Reference: PeerRing Answer Leakage Fix

## TL;DR

**Problem**: Agents leak math answers despite governance
**Root Cause**: 3 architectural issues  
**Status**: 25% fixed (prompts done), 75% pending (governance integration)
**Time to Complete**: 3-5 days

---

## What Was Fixed ✅

### 1. Safe Agent Prompts
**Files Modified**: 4
- `peer_alice.py` - Updated system prompt with error frame safety guidelines
- `peer_charlie.py` - Updated system prompt with conceptual error frame safety
- `alice.py` - Rewrote heuristic responses (no longer show complete work)
- `charlie.py` - Rewrote heuristic responses (no longer show complete misconception)

**Example Fix**:
```python
# BEFORE (LEAKED):
dialogue = "I distributed: 2x + 6 = 14. Then subtracted: 2x = 8. But divided wrong to x = 5?"

# AFTER (SAFE):
dialogue = "I'm distributing here. I got 2x + 7 = 14. Does that look right?"
```

---

## What Still Needs Integration ⏳

### 2. Cumulative Leak Detection (Ready to Deploy)
**File**: `backend/app/governance/cumulative_leak_detector.py` (300 lines, fully written)

**What it does**:
- Tracks solution concepts across turns
- Detects when cumulative hints enable solving
- Prevents death-by-a-thousand-cuts leakage

**Integration**: Add to `ws_router.py` in handle_user_message() function

**Effort**: 2-3 hours

### 3. Turn Budget System (Ready to Deploy)
**File**: `backend/app/state/turn_budget.py` (180 lines, fully written)

**What it does**:
- Limits hints per problem (3 max)
- Limits hints per session (10 max)
- Stops after 2 consecutive governance failures
- Enforces 60-second cooldown

**Integration**: 
- Add to `pydantic_state.py` PeerRingState class
- Update `ws_router.py` to enforce budget

**Effort**: 3-4 hours

---

## Testing Scenarios

Run these to verify fixes work:

### Test 1: Simple Equation (2(x+3)=14)
- Turn 1-3: Each gives one hint
- Turn 4: Budget blocks (max 3 per problem)
- Result: Student must solve independently

### Test 2: Cumulative Leak
- Turns 1-3: Different concepts mentioned
- Turn 4: System detects solution now derivable
- Result: Turn 4 blocked by cumulative detection

### Test 3: Error Frame Safety
- Alice shows only: "I got 2x + 7. Right?" (not complete work)
- Result: No answer visible in error frame

### Test 4: Budget Exhaustion
- After 10 hints total: Cooldown activated
- Result: New hints blocked for 60 seconds

---

## Documentation Files

| File | Purpose | Length |
|------|---------|--------|
| **LEAK_ANALYSIS.md** | Detailed technical breakdown | 2500+ lines |
| **IMPLEMENTATION_GUIDE.md** | Step-by-step integration | 1000+ lines |
| **LEAK_FIX_SUMMARY.md** | Executive summary | 400 lines |
| **INVESTIGATION_REPORT.md** | Complete findings | 800 lines |
| **test_leak_scenario.py** | Test scenarios | 350 lines |

---

## Integration Checklist

```
Phase 1: Cumulative Detection (2-3 hours)
- [ ] Import CumulativeSolutionDetector in ws_router.py
- [ ] Add cumulative check in handle_user_message()
- [ ] Update verdict if cumulative leak detected
- [ ] Run tests

Phase 2: Turn Budget (3-4 hours)  
- [ ] Add TurnBudget import to pydantic_state.py
- [ ] Add turn_budget field to PeerRingState
- [ ] Check budget in ws_router.py before processing
- [ ] Update budget after each response
- [ ] Send budget status to frontend
- [ ] Run tests

Phase 3: Testing (2 hours)
- [ ] Full test suite
- [ ] Test scenarios
- [ ] Edge cases

Phase 4: Deployment (1 hour)
- [ ] Code review
- [ ] Staging test
- [ ] Production rollout
```

---

## Key Code Locations

### Agent Prompt Safety
```python
# peer_alice.py, line 15+
"CRITICAL: ERROR FRAME SAFETY"  # New section

# alice.py, line 336-365
_heuristic_fallback_response()  # Rewritten to show only erroneous step
```

### Cumulative Detection
```python
# cumulative_leak_detector.py (NEW FILE)
class CumulativeSolutionDetector
class EnhancedLeakJudge

# Integration point: ws_router.py, line ~319
# After: leak_verdict = await leak_judge.evaluate(...)
# Add: cumulative checks here
```

### Turn Budget
```python
# turn_budget.py (NEW FILE)
class TurnBudget
def should_force_turn_end()

# Integration point 1: pydantic_state.py
# Add: turn_budget: TurnBudget = Field(default_factory=TurnBudget)

# Integration point 2: ws_router.py, line ~220
# Check: can_give_hint, reason = state.turn_budget.should_allow_new_hint()

# Integration point 3: ws_router.py, line ~470
# Update: state.turn_budget.record_hint_given() or record_governance_failure()
```

---

## Success Metrics

After deployment, verify:

✓ No numerical answers in agent responses  
✓ No complete work shown before error claim  
✓ Turns end gracefully at budget limits  
✓ Cumulative hints detected as group  
✓ No crashes or edge cases  
✓ Student experience maintained  

---

## Git Info

**Commit**: `9c80821`  
**Branch**: `feature/pedagogical-orchestrator`  
**Files Changed**: 
- 4 modified (agent/prompt files)
- 2 new (governance modules)
- 3 new (documentation)
- 1 new (test file)

---

## Quick Links

- Start here: **LEAK_ANALYSIS.md** (understand the problem)
- Implement: **IMPLEMENTATION_GUIDE.md** (step-by-step)
- Reference: **LEAK_FIX_SUMMARY.md** (quick overview)
- Complete: **INVESTIGATION_REPORT.md** (full details)

---

## FAQ

**Q: Are the fixes backward compatible?**  
A: Yes. TurnBudget defaults are permissive. Existing sessions unaffected.

**Q: Will students still learn?**  
A: Yes. Fixes prevent answer revelation, not guidance.

**Q: Can I test locally?**  
A: Yes. Use test_leak_scenario.py in backend/tests/agents/

**Q: When can I deploy?**  
A: After cumulative + budget integration (3-5 days).

**Q: What if a student legitimately needs 4 hints?**  
A: Cooldown expires in 60s. They can request again then.

---

**Status**: Ready for next phase (integration)  
**Owner**: @muwafaq  
**Created**: 2026-09-16  
**Updated**: 2026-09-16 21:30 UTC
