# Feature Specification: Assistance Hint Ladder (`feature/assistance-hint-ladder`)

> **Branch:** `feature/assistance-hint-ladder`  
> **Author / Lead:** `usm` (Agent Intelligence & Adaptive Engine Lead)  
> **Parent Branch:** `feature/pedagogical-orchestrator`  
> **Status:** Implemented & Verified  

---

## 1. Overview & Pedagogical Objective

The **Assistance Hint Ladder** is an adaptive scaffolding protocol that dynamically adjusts the granularity and directness of guidance provided in the Spatial PeerRing virtual study pod.

The system prevents:
1. **Student Abandonment**: When a student struggles, the ladder escalates to provide progressive hints before frustration sets in.
2. **Hint Dependency & Learned Helplessness**: As the student demonstrates competence, the ladder systematically fades scaffolding, guiding them back to autonomous problem-solving.

---

## 2. Six Assistance Levels

| Level | Level Name | Pedagogical Description | Agent Behavior |
|---|---|---|---|
| **1** | **Independent** | Autonomous student work with high-level encouragement. | Open diagnostic questions (e.g., *"What are we trying to find?"*). Peers active. |
| **2** | **Gentle Nudge** | Direct attention to an invariant pattern or observed fact. | Focus questions on known constants or patterns without prescribing steps. |
| **3** | **Guiding Question** | Focus on the immediate next mathematical operation. | Targeted queries on algebraic relationships (e.g., *"What operation cancels this?"*). |
| **4** | **Worked Example** | Parallel analogous sub-problem with different numbers. | Demonstrates structure on an equivalent problem. Blackboard patch enabled. |
| **5** | **Step-by-Step** | Structured micro-steps with binary choices. | Deconstructs the formula into small sequential operations. Peer activity suppressed. |
| **6** | **Direct Instruction** | Foundational conceptual and theoretical explanation. | Explicit review of the fundamental definition/law. Full Bob tutor leadership. |

---

## 3. Dynamic Transition Logic

The `AssistanceLadderController` dynamically calculates ladder transitions:

### Escalation (`step_up`)
- **Explicit Help Demands**: If the student states *"I need help"*, *"Give me a hint"*, or *"I'm stuck"*, immediate $+1$ escalation.
- **Consecutive Error Threshold**: $2$ consecutive incorrect responses $\to$ $+1$ escalation.
- **Hesitation Latency**: Response latency $> 45$ seconds during early levels $\to$ $+1$ gentle escalation.
- **Ceiling**: Clamped at Level 6 (Direct Instruction).

### De-Escalation & Fading (`step_down`)
- **Demonstrated Competence**: $2$ consecutive successful responses at levels $> 1$ $\to$ $-1$ de-escalation towards independence.
- **Floor**: Clamped at Level 1 (Independent).

### Return to Independence (`return_to_independence`)
- Resets directly to Level 1 and clears consecutive error counters upon curriculum concept mastery.

---

## 4. PRISM Telemetry Integration

Every ladder transition emits structured telemetry under `ASSISTANCE_LADDER_TRANSITION`:
- `initial_level`: Integer level before evaluation.
- `final_level`: Integer level after evaluation.
- `level_name`: Human-readable string.
- `transition_occurred`: Boolean flag.
- `action_taken`: `"escalated"`, `"de-escalated"`, or `"maintained"`.
- `reason`: Machine-readable causal identifier (e.g. `"consecutive_errors_threshold_reached"`).
- `consecutive_errors`: Current consecutive error count.
- `transitions_today`: Total ladder movements in the session.

---

## 5. Test Suite Verification

Comprehensive test coverage in [`backend/tests/adaptive/test_hint_ladder.py`](file:///c:/Users/ceusm/peerring/backend/tests/adaptive/test_hint_ladder.py):
- Level bounds checking ($1 \le \text{level} \le 6$).
- Progressive escalation and fading rules.
- Return to independence on mastery.
- **Complete Learning Trajectory Simulation**: Proves escalation up to Level 4 under struggle and graceful fading back down to Level 1 upon concept mastery.
