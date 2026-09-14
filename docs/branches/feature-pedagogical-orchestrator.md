# Feature Specification: Pedagogical Orchestrator (`feature/pedagogical-orchestrator`)

> **Branch:** `feature/pedagogical-orchestrator`  
> **Author / Lead:** `usm` (Agent Intelligence & Adaptive Engine Lead)  
> **Parent Branch:** `feature/alice-charlie-peers`  
> **Status:** Implemented & Verified  

---

## 1. Overview & Architecture

The **Pedagogical Orchestrator** is the dynamic coordinating engine of the Spatial PeerRing virtual study pod. Rather than following a deterministic turn sequence, the pod runs a multi-agent candidate auction on every turn:
1. When the student speaks, **Bob (Tutor)**, **Alice (Arithmetic Peer)**, and **Charlie (Conceptual Peer)** concurrently submit candidate actions.
2. The **`CandidateScorer`** evaluates the pedagogical utility of each action, adapting to the student's real-time struggle state and enforcing conversational flow.
3. The winning agent generates a response (complete with Pólya `<think>` deliberation and optional KaTeX blackboard patches).
4. The orchestrator registers comprehensive PRISM telemetry and updates turn cooldowns.

```
                  ┌──────────────────────────────┐
                  │        Student Message       │
                  └──────────────┬───────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
    ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
    │  Bob Tutor  │       │ Alice Peer  │       │Charlie Peer │
    └──────┬──────┘       └──────┬──────┘       └──────┬──────┘
           │ CandidateAction     │ CandidateAction     │ CandidateAction
           └─────────────────────┼─────────────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │       CandidateScorer        │
                  │ Score = (Util * W) * (1 - CD)│
                  └──────────────┬───────────────┘
                                 │ Top Scorer
                                 ▼
                  ┌──────────────────────────────┐
                  │    Winning Agent Generates   │
                  │   Response + Pólya + KaTeX   │
                  └──────────────┬───────────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
┌──────────────────────┐                    ┌──────────────────────┐
│  State Dialogue Log  │                    │ PRISM Telemetry Sync │
└──────────────────────┘                    └──────────────────────┘
```

---

## 2. Dynamic Candidate Scoring Algorithm

The candidate scoring formula balances **pedagogical necessity** with **natural conversational variety**:

$$\text{FinalScore} = (\text{RawUtility} \times \text{StruggleWeight}) \times (1.0 - \text{CooldownPenalty})$$

### Struggle Weights
| Student Condition | Bob (Tutor) Weight | Peer (Alice/Charlie) Weight | Pedagogical Intent |
|---|---|---|---|
| **High Struggle ($\ge 0.70$)** | **$1.30\times$** | **$0.45\times$** | Direct teacher guidance needed; suppress peer mistakes to avoid cognitive overload. |
| **Moderate Struggle ($0.35 - 0.70$)** | **$1.10\times$** | **$0.95\times$** | Balanced guidance and collaborative inquiry. |
| **Low Struggle ($< 0.35$)** | **$0.90\times$** | **$1.25\times$** | Student confident; peer mistakes stimulate error-spotting and metacognitive defense. |

### Anti-Monopolization & Cooldowns
- **Previous Speaker**: $-0.45$ penalty.
- **2 Consecutive Turns**: $-1.00$ penalty ($\text{Score} = 0.0$, strictly preventing 3 consecutive turns by any agent).
- **Time-decay**: Continuous linear decay over 20 seconds for agents who have not spoken in the last 2 turns.

---

## 3. PRISM Observability Integration

The orchestrator logs structured PRISM event data under `ORCHESTRATOR_SPEAKER_SELECTED`:
- `winner_id`: Selected agent ID (`"bob-tutor"`, `"alice-peer"`, `"charlie-peer"`).
- `winner_score`: Floating-point composite score of the winning candidate.
- `winning_action_type`: Action type (`"question"`, `"hint"`, `"challenge"`, `"respond"`).
- `all_candidate_scores`: Dictionary mapping all evaluated agent IDs to their final scores.
- `scoring_rationales`: Explicit derivation strings for auditability.
- `struggle_score_at_turn`: Active student struggle score.
- `turn_number`: Global turn counter.

---

## 4. Test Suite Verification

Verified in [`backend/tests/agents/test_orchestrator.py`](file:///c:/Users/ceusm/peerring/backend/tests/agents/test_orchestrator.py):
- `CandidateScorer` struggle weighting and anti-monopolization penalties.
- Single-turn full execution and state recording.
- High struggle tutor takeover verification.
- **10-Turn Multi-Agent Session Simulation**: Proves rotation among all 3 pod members with max consecutive streak $\le 2$.
