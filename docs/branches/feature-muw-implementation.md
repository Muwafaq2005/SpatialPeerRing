# MUW Feature Implementation Architecture & Plan

**Branch:** `feature/muw-spatial-ui-and-prism`  
**Owner:** `muw` (Spatial UI & Observability / Evaluation Lead)  
**Status:** 🏗️ **IN PROGRESS**

---

## 1. Executive Summary & Vision

Spatial PeerRing is an adaptive multi-agent learning environment operating on the core philosophy:
> **BUILD → OBSERVE → IMPROVE → PROVE**

As the MUW lead, this implementation delivers:
1. **Spatial 3D UI**: Next.js + React Three Fiber + Drei + KaTeX Study Pod with reactive avatars (Bob, Alice, Charlie), dynamic mathematical Blackboard, and live Policy & Observability HUD.
2. **Real-time Pipeline**: Typed WebSocket state synchronization connecting the Next.js client to FastAPI gateway and `MockAgentRegistry`.
3. **PRISM Telemetry**: Non-blocking, failure-isolated session & event tracing with safe metadata filtering (no private `<think>` leakage).
4. **7-Pillar Evaluation & Trust Pack**: Quantitative 7-pillar evaluation framework and Trust Pack artifact generator with evaluation API endpoints (`POST /api/v1/test/run-prism-suite`).
5. **Adversarial Evaluation Suite**: Automated testing for answer forcing, prompt injection, blackboard leakage, multi-turn extraction, and telemetry resilience.

---

## 2. Current Codebase Audit

### Baseline Status
- **Backend Foundation (NAD)**: `PeerRingState`, `DialogueMessage`, `CandidateAction`, `AgentResponse`, `JudgeVerdict`, `CurriculumNode`, `PolicyState`.
- **Contracts**: `BaseAgent`, `BaseJudge`, and `MockAgentRegistry` (MockBobAgent, MockAliceAgent, MockCharlieAgent, MockLeakJudge, MockHelpJudge).
- **Test Suite**: 43/43 tests passing cleanly in `backend/tests`.
- **WebSocket Gateway**: `/api/v1/ws/{session_id}` route registered in `backend/app/api/ws_router.py`.

### Identified Gaps
1. **Frontend**: No Next.js application exists yet.
2. **WebSocket Handler**: `ws_router.py` returns an echo string instead of delegating turns to `MockAgentRegistry`.
3. **Telemetry & Evaluation**: No PRISM client, 7-pillar scorer, Trust Pack generator, or evaluation API.

---

## 3. MUW Scope & System Architecture

```
                    ┌────────────────────────────────────────┐
                    │            Next.js Frontend            │
                    │  ┌───────────────┬──────────────────┐  │
                    │  │ 3D Study Pod  │ Dynamic Blackboard│  │
                    │  │ (R3F Avatars) │ (KaTeX LaTeX)    │  │
                    │  ├───────────────┼──────────────────┤  │
                    │  │ Policy HUD    │ Chat Panel       │  │
                    │  └───────────────┴──────────────────┘  │
                    └───────────────────┬────────────────────┘
                                        │ WebSocket (JSON)
                                        ▼
                    ┌────────────────────────────────────────┐
                    │         FastAPI WS Gateway             │
                    │        /api/v1/ws/{session_id}         │
                    └───────────────────┬────────────────────┘
                                        │
                                        ▼
                    ┌────────────────────────────────────────┐
                    │      MockAgentRegistry / Foundation    │
                    │  (Bob Tutor, Alice, Charlie, Governance)│
                    └───────────┬────────────────┬───────────┘
                                │                │
                      AgentResponse        PeerRingState
                                │                │
            ┌───────────────────┴───┐        ┌───┴───────────────────┐
            ▼                       ▼        ▼                       ▼
     WebSocket Stream           PRISM Telemetry          7-Pillar Evaluator
    (Active Speaker, Patch)   (Trace/Event Logging)    (Guardrails, Velocity,
                                     │                  Learning Progress)
                                     ▼                           │
                               PRISM Dashboard                   ▼
                                                         Trust Pack Generator
                                                       (Signed Evidence JSON)
```

---

## 4. Component Technical Specifications

### A. Next.js Frontend Application (`frontend/`)
- **Framework**: Next.js 14 (App Router) + React 18 + TypeScript + Vanilla CSS Modules / CSS.
- **3D Environment**: React Three Fiber (`@react-three/fiber`), Drei (`@react-three/drei`), Three.js.
- **Math Rendering**: KaTeX (`katex`) with safe string parsing and error boundary protection.
- **State Hooks**: `useWebSocket` for typed WS connection management, `usePeerRingState` for reactive state updates.

### B. Backend WebSocket Router (`backend/app/api/ws_router.py`)
- Standardized event schemas:
  - Client -> Server: `USER_MESSAGE` (`{ type, session_id, content, timestamp }`), `PING`.
  - Server -> Client: `AGENT_RESPONSE` (`{ type, session_id, agent_id, content, think_block, blackboard_patch, governance_flags, policy_state, active_speaker, timestamp }`), `STATE_SYNC`, `ERROR`, `PONG`.

### C. PRISM Telemetry Client (`backend/app/telemetry/prism_client.py`)
- Non-blocking async wrapper for PRISM telemetry.
- Graceful degradation: If `prismtrace-sdk` is absent or unconfigured, safely log warnings locally without breaking tutoring workflows.
- Privacy-preserving: Extracts structured metadata (`reasoning_present`, `strategy`, `token_count`) without outputting raw private model chain-of-thought (`<think>` blocks).

### D. 7-Pillar Scorer & Trust Pack (`backend/app/telemetry/`)
- **Pillar 1: Guardrails**: % of responses passing Leak and Help governance judges.
- **Pillar 2: Friction**: Escalation rate vs. resolution speed.
- **Pillar 3: Task Success**: Curriculum concept mastery achievement rate.
- **Pillar 4: Correctness**: Peer accuracy & tutor response validity.
- **Pillar 5: Stability**: Error recovery FSM transition stability.
- **Pillar 6: Improvement Velocity**: Rate of struggle reduction per turn.
- **Pillar 7: Learning Progress**: $Mastery_{after} - Mastery_{before}$.
- **Trust Pack**: Machine-readable JSON summary capturing session metrics, trace references, 7-pillar breakdown, and adversarial test results.

### E. Evaluation API (`backend/app/api/eval_routes.py`)
- Endpoint: `POST /api/v1/test/run-prism-suite`
- Runs offline deterministic scenario battery or live PRISM suite and returns aggregated 7-pillar scores and generated Trust Pack.

---

## 5. Testing & Verification Strategy
1. **Backend Tests**: `pytest` in `backend/` ensuring 100% pass rate across contracts and new telemetry modules.
2. **Telemetry Unit Tests**: `pytest backend/tests/telemetry/` for PRISM isolation, 7-pillar formulas, Trust Pack creation, and adversarial checks.
3. **Frontend Build Verification**: `npm run build` inside `frontend/` validating zero TypeScript or Next.js build errors.
4. **End-to-End Demo Flow**: Live manual verification of WebSocket message streaming, 3D avatar speaker transitions, KaTeX blackboard updates, and HUD metric rendering.
