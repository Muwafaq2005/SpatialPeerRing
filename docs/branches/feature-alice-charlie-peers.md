# Feature Specification: Alice & Charlie Peer Agents (`feature/alice-charlie-peers`)

> **Branch:** `feature/alice-charlie-peers`  
> **Author / Lead:** `usm` (Agent Intelligence & Adaptive Engine Lead)  
> **Parent Branch:** `feature/bob-socratic-tutor`  
> **Status:** Implemented & Verified  

---

## 1. Pedagogical Role & Vicarious Learning

In the Spatial PeerRing virtual study pod, the student is not alone with an intimidating tutor. They study alongside two peer agents:
- **Alice**: An enthusiastic peer who grasps problem context and formulas, but makes careless **arithmetic slips** (multiplication errors, sign flips, off-by-one).
- **Charlie**: A deliberate peer who computes arithmetic with flawless precision, but falls into seductive **structural/conceptual misconceptions** (order of operations shortcuts, freshman's dream, illegal variable cancellation).

### The Cognitive Benefit
- **Metacognitive Vigilance**: Finding errors in someone else's work is less threatening and builds the habit of checking work.
- **Conceptual Defense**: When Charlie proposes an invalid shortcut like $\frac{2x+6}{2} = x+6$, the student is challenged to explain *why* it is wrong, deepening conceptual grounding.
- **Collaborative Camaraderie**: Normalizes mistakes as natural milestones in learning.

---

## 2. Strict Error Taxonomy Matrix (Zero Cross-Contamination)

The system enforces strict error isolation via [`backend/app/prompts/peer_taxonomy.py`](file:///c:/Users/ceusm/peerring/backend/app/prompts/peer_taxonomy.py):

| Peer Agent | Role & Type | Permitted Error Categories | Strictly Forbidden Categories |
|---|---|---|---|
| **Alice** | `AgentType.ALICE_ARITHMETIC` (`alice-peer`) | `sign_flip`<br>`off_by_one`<br>`multiplication_slip`<br>`addition_slip`<br>`distribution_arithmetic` | **Any conceptual error** (order of operations, illegal cancellations, misapplying algebraic theorems). |
| **Charlie** | `AgentType.CHARLIE_CONCEPTUAL` (`charlie-peer`) | `order_of_operations`<br>`freshman_dream`<br>`illegal_cancellation`<br>`like_terms_confusion`<br>`non_linear_distribution` | **Any arithmetic error** (all additions, subtractions, and multiplications are computed with 100% precision). |

---

## 3. Dynamic Candidate Proposal Dynamics

Each peer implements `propose_candidate_action(state: PeerRingState) -> Optional[CandidateAction]`:

### Utility Dynamics vs. Student Struggle
- **Low Student Struggle (`struggle_score < 0.4`)**:
  - Peers have strong pedagogical utility (`utility ~ 0.55 - 0.65`).
  - Peer contributions stimulate discussion, collaborative problem solving, and calculation verification.
- **High Student Struggle (`struggle_score > 0.7`)**:
  - Peer utility decreases (`utility < 0.35`).
  - Bob (the Socratic Tutor) receives dominant pedagogical utility (`utility >= 0.85`), preventing peers from confusing an already struggling student.
- **Turn Cooldowns**:
  - If a peer spoke in the previous turn, a `0.35` cooldown penalty is deducted to prevent conversational monopolization.

---

## 4. PRISM Observability Integration

Both peer agents emit structured telemetry in `AgentResponse.metadata`:
- `agent_id`: `"alice-peer"` or `"charlie-peer"`
- `peer_role`: `"arithmetic_error"` or `"conceptual_error"`
- `error_category`: `"arithmetic"` or `"conceptual"`
- `error_type`: Specific taxonomy value (e.g. `"sign_flip"`, `"order_of_operations"`)
- `contains_arithmetic_error`: Boolean flag
- `contains_conceptual_error`: Boolean flag
- `has_blackboard_patch`: Boolean flag
- `prism_monitored`: `True`

---

## 5. Test Suite Verification

Comprehensive unit tests are located in [`backend/tests/agents/test_peers.py`](file:///c:/Users/ceusm/peerring/backend/tests/agents/test_peers.py):
- Contract compliance (`BaseAgent`)
- Utility curve inversion under struggle states
- Strict taxonomy isolation verification (asserting zero overlap)
- Taxonomy validator rejection of cross-contamination
- `<think>` deliberation and KaTeX blackboard extraction
- Governance rejection recovery
