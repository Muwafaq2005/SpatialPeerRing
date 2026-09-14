# Feature Specification: Bob Socratic Tutor (`feature/bob-socratic-tutor`)

> **Branch:** `feature/bob-socratic-tutor`  
> **Author / Lead:** `usm` (Agent Intelligence & Adaptive Engine Lead)  
> **Parent Branch:** `main` (Foundation Merged)  
> **Status:** Implemented & Verified  

---

## 1. Overview & Pedagogical Role

**Bob** is the foundational Socratic Tutor in the Spatial PeerRing virtual study pod. Within the three-agent pod (Bob, Alice, Charlie), Bob serves as the guiding teacher figure.

Bob's core objectives:
1. **Diagnostic Probing**: Determine what the student currently understands, where misconceptions lie, and what cognitive barriers are present.
2. **Strict Non-Disclosure**: Prevent answer disclosure. Bob will never confirm numerical shortcuts or hand down final answers.
3. **Latent Pólya 4-Step Deliberation**: Internalize problem breakdown using George Pólya's methodology inside a hidden `<think>` block before emitting visible dialogue.
4. **Assistance Ladder Awareness**: Seamlessly adapt scaffolding across 6 tiered levels (from high-level conceptual questions to structured step-by-step guidance).
5. **Dynamic Blackboard Interaction**: Propose KaTeX / SVG blackboard patches (`blackboard_patch`) when spatial math or formula visualization accelerates understanding.

---

## 2. Architecture & Contract Conformance

Bob directly subclasses the frozen foundation contract [`BaseAgent`](file:///c:/Users/ceusm/peerring/backend/app/contracts/base_agent.py):

```python
class BobAgent(BaseAgent):
    def __init__(self, agent_id: str = "bob-tutor", config: Optional[Dict[str, Any]] = None):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.BOB_TUTOR,
            config=config or {}
        )
```

### Key Methods Implemented

| Method | Role | Contract Details |
|---|---|---|
| `propose_candidate_action(state)` | Proposes action with utility scoring for Pedagogical Orchestrator. | Returns `CandidateAction` with `pedagogical_utility` scaled by `struggle_score` and cooldown penalty. |
| `generate_response(state, action)` | Executes Pólya reasoning and generates student-facing dialogue. | Returns `AgentResponse` with `think_block`, cleaned `content`, and optional `blackboard_patch`. |
| `on_response_rejected(state, resp, reason)` | Governance fallback handler. | Regenerates safe deflection dialogue if intercepted by `LeakJudge` or `HelpJudge`. |

---

## 3. Pólya 4-Step Deliberation Protocol (`<think>`)

Bob encapsulates George Pólya's problem-solving heuristics in an internal `<think>` block:

```xml
<think>
1. Understand the Problem:
   - Identify the active curriculum concept, student's latest utterance, and mental model.
2. Devise a Plan:
   - Determine which Socratic move is warranted based on current Assistance Ladder (1-6).
3. Execute the Plan:
   - Formulate diagnostic inquiry or guiding analogy.
4. Review & Governance Self-Check:
   - Ensure zero leak of final values or shortcuts.
</think>
```

The visible response emitted to the client WebSocket strips `<think>...</think>`, preserving student focus while streaming the deliberation to **Block Convey PRISM** for transparency and evaluation.

---

## 4. PRISM Observability Integration

Bob attaches rich metadata in `AgentResponse.metadata`:
- `agent_id`: `"bob-tutor"`
- `polya_deliberation_captured`: `bool`
- `socratic_strategy`: Name of active scaffolding strategy (e.g., `"Guiding Question"`)
- `assistance_level`: Current integer level (1–6)
- `struggle_score`: Float (0.0 to 1.0)
- `has_blackboard_patch`: `bool`

---

## 5. Test Suite & Verification

The feature is verified by tests in [`backend/tests/agents/test_bob.py`](file:///c:/Users/ceusm/peerring/backend/tests/agents/test_bob.py):
- Contract compliance and inheritance
- Struggle-aware utility scoring
- Turn cooldown penalty enforcement
- Pólya `<think>` tag extraction and structure verification
- Blackboard patch extraction and content separation
- Non-disclosure compliance under adversarial prompting
- Governance rejection recovery and `MockLeakJudge` integration
