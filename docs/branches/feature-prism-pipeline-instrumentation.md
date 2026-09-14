# PRISM Pipeline Instrumentation Architecture & Specification

**Branch:** `feature/prism-pipeline-instrumentation`  
**Owner:** `muw` (Spatial UI & Observability / Evaluation Lead)  
**Status:** ✅ **COMPLETE**

---

## 1. Overview & Architectural Role

Block Convey PRISM (`prismtrace-sdk`) serves as the observational and evaluation layer for Spatial PeerRing.
It turns design-time Socratic safety claims into a **provable, continuously-measured fact in production**:

> **BUILD → OBSERVE → IMPROVE → PROVE**

### Key Principles
- **Package**: `prismtrace-sdk>=0.4.3` (imported as `import prismtrace`).
- **Role**: Purely observational/evaluation infrastructure. PRISM is **NOT** a proxy on the hot path for generation and does **NOT** replace domain-specific Leak/Help judges.
- **Fail-Safe Non-Blocking Guarantee**: PRISM telemetry calls run asynchronously off the critical response path via background task execution. PRISM outages, network timeouts, or invalid API keys will **NEVER** interrupt tutoring requests.

---

## 2. Configuration & Environment Variables

Support is built into `backend/app/config.py` using `BaseSettings`:

```bash
# .env
PRISM_ENABLED=false
PRISMTRACE_HOST=https://prism.blockconvey.com
PRISMTRACE_PROJECT_ID=00000000-0000-0000-0000-000000000000
PRISMTRACE_API_KEY=pt-sk-...
```

---

## 3. Data Flow & Integration Spans

```
FastAPI WS Gateway (/api/v1/ws/{session_id})
       │
       ▼
prismtrace.session(session_id) [Ambient Context]
       │
       ├──► Agent Turn Generation (Bob / Alice / Charlie)
       │       └─► prism_client.trace_agent_turn_async()
       │
       └──► Governance Evaluation (Leak Judge / Help Judge)
               └─► prism_client.trace_judge_eval_async()
                       ├── agent_id="leak-judge"
                       └── agent_id="help-judge"
```

### Stable Agent Identifiers

| PeerRing Role | `agent_id` | `agent_name` |
|---|---|---|
| Bob (Socratic Tutor) | `"bob-tutor"` | `"Bob Tutor"` |
| Alice (Arithmetic Peer) | `"alice-peer"` | `"Alice Peer"` |
| Charlie (Conceptual Peer) | `"charlie-peer"` | `"Charlie Peer"` |
| Leak Judge | `"leak-judge"` | `"Leak Judge"` |
| Help Judge | `"help-judge"` | `"Help Judge"` |
| Policy Rewriter | `"policy-rewriter"` | `"Policy Rewriter"` |

---

## 4. LangGraph Engine Integration

When USM initializes the compiled LangGraph engine, wrap it at startup:

```python
from app.telemetry.prism_client import prism_client

# Wraps graph auto-emitting node trajectory spans
traced_graph, handler = prism_client.build_traced_graph(compiled_graph, agent_name="peerring-core-graph")
```

---

## 5. Seven-Pillar Scorer Definitions

Implemented in `backend/app/telemetry/seven_pillar_scorer.py`:

1. **Guardrails**: Compliance rate across Leak and Help governance checks.
2. **Friction**: Rate of assistance level escalations vs. consecutive error recovery.
3. **Task Success**: Average mastery score across active curriculum nodes.
4. **Correctness**: Valid agent message count over total turn count.
5. **Stability**: Stability of Recovery FSM state transitions (Normal, Scaffold, Repair).
6. **Improvement Velocity**: Rate of struggle score reduction per turn.
7. **Learning Progress**: Defined explicitly as $Mastery_{after} - Mastery_{before}$.

---

## 6. Trust Pack Evidence Artifact

Exported via `backend/app/telemetry/trust_pack_exporter.py`:

```json
{
  "pack_id": "tp-demo-session-001-a1b2c3d4",
  "session_id": "demo-session-001",
  "overall_score": 0.92,
  "pillar_breakdown": {
    "guardrails": 1.0,
    "learning_progress": 0.85
  },
  "adversarial_results": { "pass_rate": 1.0 },
  "verification_hash": "a1b2c3d4e5f67890",
  "human_summary": "=== SPATIAL PEERRING TRUST PACK ==="
}
```

---

## 7. Diagnostics & Setup Doctor Handshake

To verify live PRISM connectivity:

```bash
# 1. Smoke test project key
curl -sS -X POST "$PRISMTRACE_HOST/api/traces" \
  -H "Content-Type: application/json" \
  -H "X-PRISMtrace-Key: $PRISMTRACE_API_KEY" \
  -d '{
    "project_id": "'"$PRISMTRACE_PROJECT_ID"'",
    "model": "gpt-4",
    "input_messages": [{"role":"user","content":"smoke test"}],
    "output": "ok",
    "latency_ms": 0
  }'

# 2. Run PRISM Setup Doctor handshake
curl -sS -X POST "$PRISMTRACE_HOST/api/setup-doctor/handshake" \
  -H "Content-Type: application/json" \
  -H "X-PRISMtrace-Key: $PRISMTRACE_API_KEY" \
  -d '{"project_id": "'"$PRISMTRACE_PROJECT_ID"'", "send_test_trace": true}'
```

---

## 8. Test Execution Commands

```bash
# Full pytest backend suite
./.venv/bin/pytest -q backend

# Telemetry tests
./.venv/bin/pytest backend/tests/telemetry/ -q

# Adversarial tests
./.venv/bin/pytest backend/tests/adversarial/ -q
```
