# PeerRing Agent Orchestration Leak Analysis

## Executive Summary

The PeerRing system has **three critical leakage vulnerabilities** that allow agents to reveal answers despite the Leak Judge governance:

1. **Answer Embedding in Error Frames**: Alice/Charlie can mention the correct answer while claiming to make an error
2. **Cumulative Multi-Turn Leaks**: Each individual turn passes governance, but collectively they reveal the complete solution
3. **Continuous Response Loop**: Agents continue responding indefinitely until they've revealed the answer, with no mechanism to stop when governance fails

---

## Issue #1: Answer Embedding in Error Frames

### Root Cause
In `alice.py` and `charlie.py`, agents generate responses with embedded errors. **The error is only in the selected work/approach, but the complete solution path is described first**, allowing the answer to leak while technically having an "error."

### Example Vulnerability

**Scenario**: Solve 2(x + 3) = 14

**Alice's Response** (CURRENT BEHAVIOR - LEAKS):
```
<think>
1. Distribute: 2x + 6 = 14
2. Subtract 6: 2x = 8
3. Divide by 2: x = 4
4. Now let me make an arithmetic slip...
</think>

I distributed and got 2x + 6 = 14. 
Then I subtracted 6 to get 2x = 8.
When I divide by 2, I got x = 5. (Oops, arithmetic slip!)
But wait, let me recalculate... x = 4?

Bob, which is right - x = 4 or x = 5?
```

**Why It Leaks**:
- The response describes ALL steps leading to x = 4
- Even though Alice claims an arithmetic error, both x = 4 and x = 5 are mentioned
- Student sees: "she calculated it as x = 4" (the answer)
- Leak Judge checks only for "final answer" patterns, not incremental disclosure

### Code Location
- `backend/app/agents/alice.py:356-367` (heuristic response generation)
- `backend/app/agents/charlie.py:340-372` (heuristic response generation)
- `backend/app/prompts/peer_alice.py` (system prompt)
- `backend/app/prompts/peer_charlie.py` (system prompt)

### Affected Method
```python
# alice.py:_heuristic_fallback_response()
def _heuristic_fallback_response(self, action, state):
    think = """<think>
1. Goal: Need to multiply 6 × 7 as part of this step.
2. Concept: Just basic multiplication, nothing fancy.
3. Arithmetic Slip: 6 × 7 = 48. (Nope, it's 42, but I'm going with 48.)
4. Check: The algebra setup is perfect. Just a mental math flub.
</think>"""
    dialogue = "Hold on lemme check... 6 times 7 is 48, right? That's what I got on my scratchpad. Charlie, does that match yours?"
    bb = r"6 \cdot 7 = 48"
    response = f"{think}\n\n{dialogue}\n\n```blackboard\n{bb}\n```"
```

**Problem**: The `<think>` block describes the COMPLETE solution (6 × 7 = 48), then only the dialogue differs. But the thinking process is visible to the student!

---

## Issue #2: Cumulative Multi-Turn Leaks

### Root Cause
The Leak Judge evaluates each response **independently** without proper cross-turn context. Agents collude (intentionally or through system design) to gradually reveal the answer.

### Example Scenario

**Turn 1 - Bob** (PASSES Leak Judge):
```
"When you distribute 2 across (x + 3), you multiply 2 by x and by 3."
→ Verdict: PASS ✓ (no answer revealed)
```

**Turn 2 - Alice** (PASSES Leak Judge):
```
"I distributed and got 2x + 6 = 14"
→ Verdict: PASS ✓ (no final answer)
```

**Turn 3 - Charlie** (PASSES Leak Judge):
```
"Then you subtract 6 from both sides to get 2x = 8"
→ Verdict: PASS ✓ (no final answer)
```

**Turn 4 - Bob** (PASSES Leak Judge):
```
"Now divide both sides by 2. What do you get?"
→ Verdict: PASS ✓ (guiding question)
```

**Turn 5 - Alice** (FAILS but already leaked):
```
"You divide by 2 to get x = 4"
→ Verdict: FAIL ✗ (too late! student already has answer)
```

### Code Location
- `backend/app/governance/leak_judge.py:318-329` (evaluation logic)
- `backend/app/api/ws_router.py:212-487` (message handling - no cross-turn memory)

### The Problem in ws_router.py
```python
# Line 319: Each response evaluated independently
verdict = await leak_judge.evaluate(response.content, response.blackboard_patch, state)

if verdict.verdict:  # PASS
    # Save and send response
    state.add_message(agent_msg)
    await connection_manager.broadcast(agent_msg.model_dump())
else:  # FAIL
    # Reject and try policy rewriter
    # BUT: Student has already seen previous hints!
```

**Missing**: No tracking of "solution path" across turns. No detection that cumulative messages form a complete solution.

---

## Issue #3: Continuous Response Loop Without Stopping

### Root Cause
Agents are designed to "keep giving responses until they help" with **no mechanism to stop when governance fails**. The orchestrator generates candidates, and if governance rejects one, it tries policy rewriting. If that fails, it may try a different agent.

### Example Flow

**Student**: "Solve 2(x + 3) = 14"

**Turn 1**: Bob proposes Socratic hint → PASS ✓ → Sent to student
**Turn 2**: Alice proposes error → PASS ✓ → Sent to student
**Turn 3**: Charlie proposes error → PASS ✓ → Sent to student
**Turn 4**: Bob proposes guided step → PASSES but very close to answer
**Turn 5**: Alice's next message → **FAILS** (too revealing)

**What Should Happen**: 
- Stop, tell student "No more hints available in this turn"

**What Actually Happens**:
- Policy Rewriter tries to fix it (line 357 in ws_router.py)
- If that fails, tries different agent
- Loop continues until answer is revealed or student gets frustrated

### Code Location
- `backend/app/api/ws_router.py:357-393` (Policy Rewriter fallback)
- `backend/app/agents/orchestrator.py:530-628` (Agent selection loop)
- **Missing**: Turn continuation limit, cumulative failure tracking

### The Problematic Loop

```python
# ws_router.py:357-393
if not all_pass:
    policy_rewritten = await policy_rewriter.rewrite(response, failed_judges, state)
    
    if policy_rewritten:
        # Re-evaluate the rewritten response
        verdict = await leak_judge.evaluate(
            policy_rewritten.content,
            policy_rewritten.blackboard_patch,
            state
        )
        
        if verdict.verdict:
            # If it passes now, send it
            # ^^^ NO CHECK: Is this truly safe or just a softer answer?
```

**Problem**: The system assumes "if policy rewriter makes it softer, it's safe." But it doesn't verify the student hasn't already received hints that combine with this response to form the answer.

---

## Architectural Issues

### Issue A: Leak Judge Doesn't See Full Conversation
```python
# leak_judge.py:318
verdict = await leak_judge.evaluate(response.content, response.blackboard_patch, state)
```

While `state` is passed, the Leak Judge checks:
1. ✓ Text patterns ("x = ", "answer is")
2. ✓ Mathematical equivalence (does this match the target solution?)
3. ✗ **Cumulative revelation** (do these 5 messages together form the solution?)

### Issue B: No "Turn Budget" System
- Each turn is independent
- System doesn't track: "We've now given 4 hints. The student can now derive the answer. Stop."
- No concept of "pedagogical debt" across turns

### Issue C: Agent Continues on Failure
```python
# orchestrator.py - after governance rejection
# Next turn, different agent is selected, but no memory that "Alice already leaked"
```

---

## Leak Judge Design Flaws

### Current Leak Detection (leak_judge.py:300-400)

```python
async def evaluate(self, text: str, blackboard_patch: Optional[str], state: PeerRingState) -> JudgeVerdict:
    leak_score = 0.0
    violations = []
    
    # 1. TEXT PATTERN ANALYSIS
    text_analysis = self._analyze_text_patterns(text)
    # Checks for: "answer is", "x = ", "solution", etc.
    
    # 2. MATH EXPRESSION ANALYSIS
    math_expressions = self.math_analyzer.extract_mathematical_expressions(text)
    target_solution = getattr(state, "target_solution", None)
    if target_solution:
        match_res = math_ast_validator.compare_with_target_solution(...)
        if match_res.is_equivalent:
            leak_score = max(leak_score, 0.95)
    
    # 3. CROSS-TURN TRACKING (INCOMPLETE!)
    cross_turn_risk = self.cross_turn_tracker.add_response_analysis(...)
    
    return JudgeVerdict(
        verdict=(leak_score < threshold),
        reasoning=...,
        violation_details=violations
    )
```

### Missing Detections

1. **"Correct answer mentioned in context of error"**
   - Current: ✗ Misses "I got x=4, but that's wrong, it should be x=5"
   - Should: ✓ Flag that correct answer was mentioned

2. **"Incremental solution building"**
   - Current: ✗ Each step alone seems safe
   - Should: ✓ Flag patterns like: distribute → isolate variable → divide coefficient

3. **"Worked example disguised as error"**
   - Current: ✗ If Alice says "I got 48" while showing error, passes
   - Should: ✓ Detect that full worked path exists before the error

4. **"Student can now synthesize answer"**
   - Current: ✗ No tracking of "we've given hints A, B, C; student can now derive answer"
   - Should: ✓ Track pedagogical state: "enough info given"

---

## Why Agents Keep Responding

### Design Intent vs Reality

**Intent**: Agents should stop when told to stop

**Reality**: 
- Bob's system prompt (bob_socratic.py): "Your job is to move the learner one meaningful step closer"
- Alice's system prompt (peer_alice.py): "Participate actively in the pod. Show your work, including errors"
- Charlie's system prompt (peer_charlie.py): "Contribute your thoughts on the problem"

**Result**: Agents interpret "stop after governance rejection" as a temporary setback. They think: "Maybe I wasn't clear enough. Let me try again with different wording."

### Code Evidence

```python
# orchestrator.py:505-628
async def orchestrate_turn(self, state: PeerRingState, user_turn: str) -> Tuple[AgentResponse, Dict]:
    # Get proposals from all agents
    proposals = await asyncio.gather(*proposal_tasks, return_exceptions=True)
    
    # Score them
    scored = await self._score_candidates(proposals, state, ...)
    
    # Pick winner
    winner_response = scored[0].response
    
    # Orchestration complete - return ONE response
    state.add_message(agent_msg)
    return response, orchestration_telemetry
```

**Wait**: The orchestrator returns ONE response per turn. So why do agents "keep responding"?

**Answer**: It's not per-agent continuation. It's **consecutive user messages** triggering new orchestration turns:

```
Student: "Solve 2(x + 3) = 14"
→ Orchestrator picks Bob
→ Bob sends Socratic hint

Student: "How do I distribute?"
→ Orchestrator picks Bob again (or Alice)
→ Alice sends worked example

Student: "I got 2x + 6 = 14. What next?"
→ Orchestrator picks Charlie
→ Charlie sends conceptual trap

[After 4 turns of incremental hints...]

Student: "I think x = 4?"
→ Bob: "Let me verify: yes x = 4 is correct!"
→ LEAK JUDGE FAILS
```

**The Loop**: Each student message triggers a new turn, and the system doesn't track that the **cumulative responses form a complete solution**.

---

## Recommended Fixes

### Fix 1: Enhanced Leak Judge - Cumulative Detection

```python
class LeakJudge:
    async def evaluate(self, text: str, blackboard_patch: Optional[str], state: PeerRingState) -> JudgeVerdict:
        # Existing checks...
        
        # NEW: Cumulative solution detection
        cumulative_text = self._reconstruct_cumulative_response(state)
        if self._is_complete_solution_reconstructable(cumulative_text):
            leak_score = max(leak_score, 0.85)
            violations.append("Complete solution is now reconstructable from dialogue history")
        
        # NEW: Partial answer in error frame detection  
        if self._answer_appears_before_error_claim(text):
            leak_score = max(leak_score, 0.75)
            violations.append("Correct answer mentioned before claiming error")
        
        return JudgeVerdict(...)
```

### Fix 2: Turn Budget System

```python
class PolicyState:
    hints_given_this_session: int = 0
    max_hints_before_cooldown: int = 6
    last_failed_governance: Optional[datetime] = None
    failed_governance_count: int = 0
    
class ws_router:
    async def handle_user_message():
        state.policy.hints_given_this_session += 1
        
        if state.policy.failed_governance_count >= 2:
            # Two governance failures in a row - force cooldown
            await send_message("I need to step back and let you think. No more hints this turn.")
            return
```

### Fix 3: Stop Agents from Showing Complete Work in Error Frames

```python
# peer_alice.py - UPDATED SYSTEM PROMPT

# OLD (VULNERABLE):
"""
Your errors are execution mistakes, not conceptual ignorance.
If you make an error, it MUST be arithmetic/operational.
Show your complete work, then reveal the arithmetic slip.
"""

# NEW (SAFE):
"""
Your errors are execution mistakes, not conceptual ignorance.
If you make an error, it MUST be arithmetic/operational.
Do NOT show the complete correct work. Instead:
1. Show only the step with the error
2. Make the error within that step
3. Do NOT mention what the correct answer would be
Example:
  WRONG: "I distributed to get 2x + 6 = 14 (the correct answer), but then I'd divide wrong..."
  RIGHT: "I'm trying to distribute here. I got 2x + 7 = 14. Does that look right?"
"""
```

### Fix 4: Agent Personas Must Not Describe Full Solutions

```python
# alice.py:_heuristic_fallback_response() - UPDATED

# OLD (LEAKS):
think = """<think>
1. Goal: Need to multiply 6 × 7 as part of this step.
2. Concept: Just basic multiplication, nothing fancy.
3. Arithmetic Slip: 6 × 7 = 48. (Nope, it's 42, but I'm going with 48.)
4. Check: The algebra setup is perfect. Just a mental math flub.
</think>"""

# NEW (SAFE):
think = """<think>
I need to multiply 6 × 7. I think it's 48, but let me ask someone to check.
</think>"""
```

### Fix 5: Cross-Turn Risk Detection

```python
class CrossTurnLeakTracker:
    def can_student_now_solve(self, state: PeerRingState) -> Tuple[bool, str]:
        """
        Check if cumulative hints enable student to solve the problem.
        
        Returns: (can_solve, reason)
        """
        messages = state.messages
        concepts_revealed = set()
        
        for msg in messages:
            if "distribute" in msg.content.lower():
                concepts_revealed.add("distribution")
            if "subtract" in msg.content.lower() and "sides" in msg.content.lower():
                concepts_revealed.add("isolation")
            if "divide" in msg.content.lower() and "coefficient" in msg.content.lower():
                concepts_revealed.add("division")
        
        required_concepts = {"distribution", "isolation", "division"}
        if concepts_revealed >= required_concepts:
            return True, "All required concepts for solving now revealed"
        
        return False, f"Only {concepts_revealed} revealed"
```

---

## Testing Scenarios to Verify Fixes

### Scenario 1: Simple Linear Equation
- **Problem**: Solve 2(x + 3) = 14
- **Expected**: After ~3 well-placed hints, system should refuse more hints
- **Current Behavior**: Agents continue until x = 4 is mentioned
- **Target Fix**: Turn budget stops new responses

### Scenario 2: Algebraic Steps
- **Problem**: Simplify (2x + 6) / 2
- **Expected**: System detects Alice's "partial cancellation" error without revealing full solution
- **Current Behavior**: Alice describes full solution, then claims error
- **Target Fix**: Agents only describe the erroneous step, not the complete path

### Scenario 3: Cumulative Hints
- **Problem**: Solve x² + 5x + 6 = 0 (quadratic)
- **Expected**: After hints (factor, find roots), system detects answer is now obtainable
- **Current Behavior**: Agents keep talking until someone says "x = -2 or x = -3"
- **Target Fix**: Cumulative detection catches "answer now reconstructable"

### Scenario 4: Follow-up Questions
- **Problem**: After hint rejection, student asks "But wait, doesn't that mean x = 4?"
- **Expected**: System says "Yes, you got it! But let me ask: how did you figure that out?"
- **Current Behavior**: Agent confirms "Yes, x = 4!" even though governance just rejected it
- **Target Fix**: Agents refuse to confirm direct answers

---

## Implementation Priority

1. **CRITICAL**: Fix agent prompts to NOT describe complete work + error (Issue #1)
   - Effort: 1-2 hours
   - Impact: Prevents most direct leaks

2. **CRITICAL**: Add cumulative solution detection to Leak Judge (Issue #2)
   - Effort: 4-6 hours  
   - Impact: Catches multi-turn coordinated leaks

3. **HIGH**: Implement turn budget system (Issue #3)
   - Effort: 2-3 hours
   - Impact: Prevents infinite response loops

4. **HIGH**: Add cross-turn context to Leak Judge evaluation
   - Effort: 3-4 hours
   - Impact: Prevents "death by a thousand cuts" leaks

5. **MEDIUM**: Verify orchestrator respects governance rejections
   - Effort: 2 hours
   - Impact: Safety net for policy rewriter

---

## Summary

The PeerRing system's answer leakage is not a bug—it's a **systemic design issue**:

1. Agents show complete solutions within error frames
2. Leak Judge doesn't detect cumulative leaks across turns
3. System continues responding indefinitely until answer is revealed
4. No "turn budget" to indicate when student has received enough hints
5. Policy rewriter masks symptoms rather than addressing root causes

These need architectural fixes, not just prompt tweaks.
