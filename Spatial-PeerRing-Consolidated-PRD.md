# Spatial PeerRing — Consolidated PRD & Architecture

## 0. Source Note & Consolidation Method

Three inputs were reviewed and merged:

| Source | Content |
|---|---|
| **Base Spec** (`forgeaiproj.pdf`) | Original architecture: Bob/Alice/Charlie agents, LangGraph FSM, Pólya deliberation, Leak-Judge interceptor, Block Convey PRISM, 3D spatial UI, Redis turn locks. Defines the original P0/P1 scope. |
| **Part A** (`featuress.pdf`, "PARTA") | 53-feature superset adding a cognitive-assessment / adaptive-policy layer on top of the base spec. |
| **Part B** (`featuress.pdf`, "part b") | Restates Part A's themes with a dynamic-orchestrator framing (candidate actions, intervention ladder, strategy memory, peer evolution, stuck recovery). ~85% content overlap with Part A. |

**Method applied:**
1. **Deduplicated** — Part A and Part B describe the same underlying system twice (e.g., "Struggle Detection" = "Stuck Estimation"; "Dynamic Agent Selection" appears in both almost verbatim). Collapsed to single canonical features.
2. **Merged** — overlapping mechanics (hint ladder + intervention ladder + assistance strictness) folded into one **Adaptive Assistance Policy**.
3. **Cut low-value items** — features that add engineering risk without demo/product payoff for a hackathon-scoped build (see §6).
4. **Resolved contradictions** — see §5 (fixed vs. dynamic turn order, upfront IQ-style testing vs. behavior-based inference, duplicated eval frameworks).

Net result: **~100 individually-listed items across the three docs → 8 epics, ~28 consolidated capabilities.**

---

## 1. Problem Statement

Generic AI tutors act as answer-vending machines: they leak solutions under user pressure and offer no peer modeling or productive struggle, so students don't build durable problem-solving schemas. Point-in-time fixes (a stronger system prompt) aren't auditable or provably reliable at the policy level.

## 2. Goal

Ship a governed, multi-agent Socratic tutoring environment that (a) **provably** withholds terminal answers under adversarial pressure, (b) creates productive cognitive conflict via two peer agents with distinct error types, and (c) **adapts** its assistance level to the individual learner — all measurable through a closed-loop observability pipeline (Build → Observe → Improve → Prove).

## 3. Target Users
- Secondary/post-secondary STEM learners needing active, diagnostic practice (not answers).
- Enterprise EdTech buyers requiring auditable, policy-compliant, non-disclosure-guaranteed AI tutoring.

---

## 4. Consolidated Feature Set

### Epic 1 — Core Multi-Agent Socratic Engine `P0`
The pedagogical heart of the product; everything else governs or personalizes it.

| Feature | Description |
|---|---|
| Bob (Socratic Tutor) | Diagnoses state, plans next pedagogical move, never solves the problem directly. |
| Alice (Arithmetic-Error Peer) | Conceptually correct, introduces controlled operational mistakes for the learner to catch. |
| Charlie (Conceptual-Error Peer) | Procedurally correct, introduces controlled theoretical mistakes — a distinct error class from Alice's, by design (no overlap). |
| Latent Pólya Deliberation | Every agent reasons inside a hidden `<think>` block (Understand → Plan → Execute → Look Back) before emitting visible text; this is where policy self-checks happen. |
| Pedagogical Orchestrator | *(merged from Part A "Dynamic Agent Selection" + Part B "Agent Candidate Actions")* — each agent proposes a candidate action; a lightweight orchestrator scores candidates against learner state and picks the next speaker/strategy. Replaces a hardcoded Bob→Alice→Charlie script. |

### Epic 2 — Answer Governance & Guardrails `P0`
Non-negotiable trust layer; this is the product's core differentiator.

| Feature | Description |
|---|---|
| Leak Judge | Out-of-band classifier that blocks any response containing a terminal or reconstructible solution before it reaches the client. |
| Indirect / Cross-Turn Leak Detection | Evaluates leakage across recent dialogue history, not just the current message (catches split leaks, e.g. Alice reveals one step, Charlie the next). |
| Blackboard Leakage Protection | The shared blackboard patch is run through the same Leak Judge as spoken text — visuals can't bypass policy. |
| Help Judge | Second-pass check: did the (non-leaking) response actually move the learner forward, or is it safe-but-useless? |
| Policy Rewriter | On rejection, regenerates the response using the specific violation reason rather than returning a generic error. |
| Adversarial Prompt Resistance | Classifies user intent (`ADVERSARIAL_REQUEST`, `ANSWER_REQUEST`, etc.) and routes high-pressure/injection attempts through stricter policy before generation. |

### Epic 3 — Adaptive Assistance Policy `P0 (lightweight) → P1 (full)`
*Consolidates Part A's Cognitive Assessment/Profile/Hint-Ladder and Part B's Intervention Ladder/Strategy Diversity into one policy engine.*

| Feature | Description |
|---|---|
| Behavior-Derived Assistance Level | Learner starts at a **default "medium" policy** (see §5 for why no upfront test) and the level moves up/down based on live performance signals: consecutive errors, hint dependency, confidence, latency of response. |
| Concept-Level Mastery Tracking | Mastery is tracked per curriculum-DAG node (e.g., `distributive_property: 0.42`), not as one global score. |
| Escalating Hint/Intervention Ladder | 5–6 fixed levels from "conceptual question" to "worked micro-step"; system climbs only as far as needed and steps back down as the learner recovers (**Dynamic Return to Independence**). |
| Struggle / Stuck Detection | Composite score from repeated errors, repeated questions, and lack of mastery movement; triggers Epic 4's recovery flow. |
| Strategy Diversity + Cooldown | Peers/strategies that were just used (or just failed) enter a short cooldown so the same move isn't repeated back-to-back. |

### Epic 4 — Pedagogical Recovery `P1`
Fires only when Epic 3 flags "stuck" — keeps the session from looping.

| Feature | Description |
|---|---|
| Recovery State Machine | `NORMAL → SCAFFOLD → PREREQUISITE_REPAIR → MICRO_TEACHING → REASSESS`, replacing an infinite hint→hint→hint chain. |
| Prerequisite Backtracking | If the blocker is actually a lower-level concept, temporarily drop down the curriculum DAG, remediate, then return. |
| Temporary Tutor Takeover | After repeated failed peer interventions, Bob takes direct (still non-disclosing) control for one micro-step, then hands back to the peer flow. |
| Failed-Strategy Suppression | Tracks which strategies already failed this session and excludes them from the orchestrator's candidate set. |

### Epic 5 — State, Reliability & Real-Time Infra `P0`
| Feature | Description |
|---|---|
| Centralized Pydantic State | Single shared state object (problem, step, mastery, policy, dialogue history) all agents read/write — prevents agents disagreeing about what's happening. |
| Turn Allocator (FSM) + Redis Mutex | `SETNX session:turn_lock` plus a deterministic `AGENT_RESPONSE → CLIENT_ACK → TURN_COMPLETE → release lock` handshake. **This stays fully deterministic even though *who* is selected is now dynamic (Epic 1)** — see §5. |
| Conversation Loop Detection | Hashes (concept + step + misconception + recent actions); repeated-state cycles force a strategy change via Epic 4. |
| Latency Mitigation | Fast inference endpoint + async judges (<250ms) + optimistic "thinking" animation so judge latency doesn't stall the UI. |

### Epic 6 — Spatial Presentation Layer `P0`
| Feature | Description |
|---|---|
| 3D Study Pod | React Three Fiber scene with low-poly GLTF avatars for Bob/Alice/Charlie/User; <15k polys, Draco-compressed, texture-atlased for low-spec devices. |
| Dynamic Blackboard | SVG/KaTeX canvas synced via `blackboard_patch` events, governed by the same Leak Judge as chat. |
| Agent Gestures / Spatial State | `GESTURE_TRIGGER` events map to idle/speaking/thinking/pointing states per active speaker. |
| Live Policy HUD | Shows current speaker, policy status, leak-check result, mastery, and system state in real time (demo/trust signal). |

### Epic 7 — PRISM Observability & Evaluation `P0 core, P1 extensions`
| Feature | Description |
|---|---|
| Full-Pipeline Instrumentation | Every turn logs input, latent trace, visible output, judge verdicts, state transition, and latency to Block Convey PRISM. |
| Six-Pillar Scoring + Learning Outcome | Guardrails, Friction, Task Success, Correctness, Stability, Improvement Velocity — **plus a 7th metric, Learning Progress (`mastery_after − mastery_before`)**, since a system can be 100% leak-free and still fail to teach. |
| Baseline-vs-Upgraded Trust Pack | Automated comparison report (radar chart, before/after scores) for the Build→Observe→Improve→Prove narrative. |
| Adversarial Evaluation Suite | Scripted test suite (`POST /api/v1/test/run-prism-suite`) covering answer-forcing, injection, deadline pressure, repeated requests, and conversational loops. |
| Synthetic Misconception Injector | Background agent that auto-generates adversarial/struggling-student traffic to stress-test live during a demo. |

### Epic 8 — Immersion Polish `P2`
| Feature | Description |
|---|---|
| Voice + Lip Sync | Web Speech API + per-agent voice profile + jaw-bone viseme animation. |
| Peer Persona Evolution | Alice/Charlie remember being corrected and can reference it later ("Last time I forgot to distribute to both terms"). |
| Anti-Pattern-Discovery | Randomizes *when* each peer's error type shows up so students can't game "Alice always messes up arithmetic." |

---

## 5. Contradictions Resolved

| Conflict | Resolution |
|---|---|
| **Fixed script** (base spec: "Bob → Alice → Charlie deterministic turn sequence") **vs. dynamic speaker selection** (Part A/B: orchestrator picks the next speaker) | Split the concern: the **FSM + Redis mutex stays deterministic** (it enforces *one speaker at a time, clean handoff* — this is a stability requirement, not a pedagogy one). The **orchestrator decides *who* is next** as a policy decision layered on top of that same lock. Dynamic selection, deterministic execution. |
| **Upfront psychometric assessment** (Part A: `POST /assessment/start`, cognitive-band test battery labeling learners HIGH/MED/LOW) | Cut from P0. An explicit IQ-adjacent test before a student even starts is (a) slow for a live demo, (b) ethically sensitive for a product used by minors, and (c) redundant — continuous evaluation infers the same signal from real problem-solving behavior within 2–3 turns. Default every session to a "medium" policy and adapt from there. |
| **Two overlapping evaluation frameworks** (base spec's 6-pillar PRISM vs. Part A/B's separate "Learning Progress Metric" and expanded metric lists) | Merged into one instrumentation layer: PRISM's 6 pillars **+ Learning Progress as a 7th pillar**. No parallel metrics pipeline. |
| **"Confidence" as a standalone tracked dimension** (Part B) vs. mastery/struggle scoring (Part A) | Folded into the existing struggle-score inputs rather than maintaining a separate confidence model — the marginal signal doesn't justify a second model. |

## 6. Cut or Deferred (and why)

| Feature | Why deferred |
|---|---|
| Full cognitive-assessment battery + `cognitive_band` classifier | Replaced by behavior-based policy adaptation (§5). Revisit only if enterprise buyers require a formal placement test. |
| Problem Granularity Adaptation (recursive problem decomposition engine) | Real pedagogical value, but a generative "auto-shrink this problem" engine is its own R&D project — P2/post-hackathon. |
| Peer Persona Evolution (long-term cross-session memory) | Great narrative polish, high build cost for demo-window payoff — P2. |
| Anti-Pattern-Discovery persona randomization | Only matters over many sessions; irrelevant to a 90-second demo — P2. |
| Voice + Lip Sync | Already P1/P2 in the base spec; unchanged. |
| Standalone Confidence Model | Merged into struggle score (§5). |

---

## 7. High-Level Technical Architecture

```
CLIENT TIER (Next.js 14 / React Three Fiber)
   3D Study Pod  |  Dynamic Blackboard (KaTeX)  |  Policy/PRISM HUD
                         ▲  WebSocket (JSON events)  │
GATEWAY TIER (FastAPI)
   Connection mgr, auth, session handshake, event dispatch
                         ▲                            │
CORE AGENTIC ENGINE (LangGraph)
   Turn Allocator (FSM + Redis mutex) ── deterministic execution
   Pedagogical Orchestrator ─────────── dynamic speaker/strategy choice
   Agent Nodes: Bob | Alice | Charlie ─ candidate-action generation
   Adaptive Policy Engine ──────────── mastery / struggle / hint-ladder state
   Latent Pólya Deliberation layer ─── <think> self-policing pass
                         ▲                            │
INTERCEPTION & OBSERVABILITY TIER
   Leak Judge → Help Judge → Policy Rewriter (loop until approved)
   Block Convey PRISM SDK (trace ingestion, Trust Pack builder)
                         ▲                            │
STORAGE TIER
   Redis 7.2 (turn locks, dialogue window, PRISM run IDs, cooldowns)
   PostgreSQL/SQLite (curriculum DAG, per-concept mastery, session stats)
```

**Data flow per turn:**
1. User message → Gateway acquires Redis turn lock, updates shared state.
2. Adaptive Policy Engine refreshes struggle/mastery/assistance-level signals.
3. Orchestrator collects a candidate action from each eligible agent, picks one (respecting cooldowns/failed-strategy suppression).
4. Selected agent runs Pólya deliberation (`<think>`) then emits visible text + optional blackboard patch.
5. Leak Judge → Help Judge evaluate; on rejection, Policy Rewriter regenerates with the violation reason.
6. Approved output + full trace (latent reasoning, judge scores, state diff) streamed to PRISM and to the client over WebSocket.
7. Client renders avatar animation, blackboard update, and HUD status; releases turn lock on `TURN_COMPLETE`.
8. Post-turn: mastery/struggle updated → if "stuck," Epic 4's recovery state machine engages on the next cycle.

**Key architectural decision carried through from §5:** the FSM/mutex layer and the orchestrator are deliberately separate components — one guarantees *safety* (no cross-talk, clean handoff), the other owns *pedagogy* (who should speak, what strategy). This keeps the dynamic-selection features from Part A/B additive rather than a rewrite of the base spec's stability guarantees.
