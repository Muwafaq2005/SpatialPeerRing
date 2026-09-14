# Block Convey PRISM Integration Guide — Spatial PeerRing

**Stack:** Python 3.11+, FastAPI, LangGraph, Redis 7.2, Next.js 14 / React Three Fiber frontend.

> **Correction to the original spec:** the blueprint referenced "Block Convey PRISM SDK (`blockconvey-prism` / OpenTelemetry exporter)." The actual package is **`prismtrace-sdk`** (installs as `pip install prismtrace-sdk`, imported as `import prismtrace`). There is no `blockconvey-prism` package and no npm/TypeScript SDK — the frontend and any non-Python service talk to PRISM over plain HTTP. Use the names below, not the ones in the earlier doc.

---

## 1. Core Purpose

**What PRISM solves:** PeerRing's architecture already makes a strong *design-time* claim — Leak Judge, Help Judge, and Pólya deliberation should stop answer leakage and unhelpful turns. PRISM is what turns that claim into a **provable, continuously-measured fact in production**:

- It records every model exchange (input, output, latency, cost, tokens) as a **trace**, groups traces into **sessions** (one per learner conversation) and **agent runs** (the trajectory of model calls, tool calls, and handoffs inside one turn).
- It **automatically scores** every trace for quality, satisfaction, and hallucination risk — at no cost and with no extra call from us.
- It gives us **alerting** (e.g., latency spikes, quality drops, guardrail blocks) and **root-cause clustering** of recurring failure patterns, instead of us hand-rolling that analysis.

**Why we're using it here specifically:** PeerRing's whole value proposition is "governed, auditable Socratic pedagogy." PRISM is the audit trail. It does **not** replace our own Leak Judge / Help Judge — those stay as the actual policy-enforcement mechanism, because they're domain-specific (they know what "leaking `x=10`" means; PRISM's generic guardrails don't). PRISM's job is to:
1. Give us an independent, timestamped record of every agent turn for compliance/demo evidence (the "Prove" stage of Build → Observe → Improve → Prove).
2. Catch things our own judges might miss over time via its own automatic scoring (hallucination flags, frustration detection, contradiction detection).
3. Alert us in real time if guardrail blocks spike (possible attack), latency degrades, or quality drops — without us building that dashboard ourselves.

---

## 2. Integration Architecture

### 2.1 Where PRISM sits

PeerRing already separates generation from interception:

```
LangGraph Core Engine → Leak Judge → Help Judge → Policy Rewriter → WebSocket dispatch
```

PRISM instrumentation attaches at **two points**, and deliberately does *not* sit inline on the critical path:

```
┌─────────────────────────────────────────────────────────────────────┐
│ CORE AGENTIC ENGINE (LangGraph)                                     │
│   Bob / Alice / Charlie nodes ──► wrap_langgraph(graph, handler) ───┼──► PRISM
│                                     (records full trajectory: model  │   (async,
│                                      calls, tool calls, handoffs)    │    off request
└─────────────────────────────────────────────────────────────────────┘   path)
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│ INTERCEPTION TIER                                                    │
│   Leak Judge / Help Judge / Policy Rewriter                          │
│     └─► manual PRISMtrace.trace_llm() call, agent_id="leak-judge"   ┼──► PRISM
│         metadata: {leak_detected, policy_score, rewrite_applied}     │
└─────────────────────────────────────────────────────────────────────┘
```

- **Path A — LangGraph SDK handler.** Wraps the compiled graph once at startup. Captures the full agent trajectory (which node ran, which model was called, latency, tokens) with zero per-call-site code.
- **Path B — Manual judge traces.** The Leak/Help Judge calls are themselves LLM calls we want visible as their *own* agent (`agent_id="leak-judge"`), with our governance verdict attached as `metadata`, so PRISM shows judge performance separately from tutor/peer performance.

**We do not use the zero-code proxy for the main generation path.** The proxy is the only path where PRISM's *own* guardrails can actually block a call before it reaches the provider — but PeerRing needs sub-250ms judge latency and a response object we control precisely (for blackboard patches, gestures), so routing Bob/Alice/Charlie's calls through an extra network hop and PRISM's generic guardrail engine isn't worth the latency cost. Our own Leak Judge remains the enforcement point; PRISM stays purely observational on the hot path.

### 2.2 Data flow, mapped to PeerRing's existing turn sequence

1. FastAPI Gateway ingests the WebSocket frame, acquires Redis turn lock, opens `prismtrace.session(session_id)` context (ambient session — see §3.3) using the existing session token.
2. LangGraph executes; `wrap_langgraph` auto-emits spans for whichever node fired (Bob/Alice/Charlie) with `agent_name` set per node.
3. Leak Judge / Help Judge evaluate the proposed output → we manually emit **one trace per judge call** with `agent_id="leak-judge"` / `"help-judge"` and governance metadata.
4. On rejection, Policy Rewriter regenerates; the retry naturally produces its own trace, so PRISM's trajectory view shows the full "generate → reject → rewrite → approve" cycle for that turn.
5. Approved response dispatches over WebSocket. Trace delivery to PRISM happens **after** dispatch, on a background task — it is never awaited on the response path.
6. PRISM's Alerts watch `guardrail_blocks`, `compliance_score`, and `latency` in real time; Root Cause clusters recurring judge rejections.

### 2.3 Endpoints / SDK components used

| Component | Purpose | Used for |
|---|---|---|
| `prismtrace-sdk` (`PRISMtraceLangGraphHandler`, `wrap_langgraph`) | Python SDK, LangGraph integration | Core agent trajectory (Bob/Alice/Charlie) |
| `prismtrace.PRISMtrace` (manual client, `trace_llm`) | Manual trace submission | Leak Judge / Help Judge calls |
| `prismtrace.session()` (ambient session context) | Groups traces without threading an id everywhere | One PeerRing conversation = one PRISM session |
| `POST /api/traces` (HTTP) | Raw ingest endpoint, fallback | Frontend/Next.js telemetry events if we ever want client-side signals in PRISM (optional, not core) |
| `GET /api/setup-doctor`, `POST /api/setup-doctor/handshake` | Diagnostics | CI/CD smoke test that the integration is live |
| Dashboard: **Alerts**, **Guardrails**, **Root Cause** | Platform features | Ops monitoring, not called from our code |

---

## 3. Step-by-Step Implementation

### 3.1 Setup

1. Create a PRISM org/project at `prism.blockconvey.com/signup`. **Create one project per environment** (dev / staging / prod) — this is a hard best practice from PRISM's own docs, and it matters more for us because prod will carry real student conversation content.
2. Settings → Project → copy the Project ID. API keys page → create an **`ingest`-scoped** key (never `read` or `operate` in application code).
3. Add to `.env` (and confirm `.env` is in `.gitignore`):

```bash
# .env
PRISMTRACE_HOST=https://prism.blockconvey.com
PRISMTRACE_PROJECT_ID=00000000-0000-0000-0000-000000000000
PRISMTRACE_API_KEY=pt-sk-...
```

4. Smoke-test the credential before writing any app code:

```bash
curl -sS -X POST "$PRISMTRACE_HOST/api/traces" \
  -H "Content-Type: application/json" \
  -H "X-PRISMtrace-Key: $PRISMTRACE_API_KEY" \
  -d '{
    "project_id":     "'"$PRISMTRACE_PROJECT_ID"'",
    "model":          "claude-sonnet-4-6",
    "input_messages": [{"role":"user","content":"smoke test"}],
    "output_message": "ok",
    "latency_ms":     0
  }'
```

A `200` with a returned `id` confirms the key/project pair works.

### 3.2 Install

```bash
pip install "prismtrace-sdk>=0.4.3"   # 0.4.3+ required for prismtrace.session()
```

### 3.3 Wire the core LangGraph engine (once, at app startup)

```python
# app/telemetry.py
import os
import prismtrace
from prismtrace import PRISMtraceLangGraphHandler, wrap_langgraph, PRISMtrace

_prism_client = PRISMtrace(
    api_key=os.environ["PRISMTRACE_API_KEY"],
    project_id=os.environ["PRISMTRACE_PROJECT_ID"],
    host=os.environ["PRISMTRACE_HOST"],
)

def build_traced_graph(compiled_graph, agent_name: str):
    """Wrap the compiled LangGraph engine so every invoke/stream call
    auto-emits a full trajectory span (per node) to PRISM."""
    handler = PRISMtraceLangGraphHandler(
        api_key=os.environ["PRISMTRACE_API_KEY"],
        project_id=os.environ["PRISMTRACE_PROJECT_ID"],
        host=os.environ["PRISMTRACE_HOST"],
        agent_name=agent_name,           # e.g. "peerring-core-graph"
        # NOTE: no session_id here — session comes from the ambient
        # context opened per WebSocket connection (see 3.4). Passing
        # both would conflict; the ambient one wins for traces emitted
        # inside the `with` block.
    )
    return wrap_langgraph(compiled_graph, handler), handler
```

```python
# app/main.py  (FastAPI startup)
from app.telemetry import build_traced_graph
from app.graph import compiled_peerring_graph   # your existing LangGraph build

traced_graph, prism_handler = build_traced_graph(
    compiled_peerring_graph, agent_name="peerring-core-graph"
)
```

### 3.4 Group a conversation: one PRISM session per WebSocket session

PeerRing already generates a `session_token` at WebSocket handshake — reuse it verbatim as PRISM's `session_id` so a conversation reads end-to-end in the dashboard (this cannot be backfilled later, so get it right from turn one).

```python
# app/ws_handler.py
import prismtrace
from app.telemetry import traced_graph, prism_handler

async def handle_turn(ws, session_token: str, state: PeerRingState):
    with prismtrace.session(session_token):
        result = await traced_graph.ainvoke(
            {"messages": state.dialogue_history, "state": state},
        )
    # Everything emitted inside the `with` block — including judge
    # traces fired later in this same turn (3.5) — is filed under
    # session_token automatically.
    return result
```

At shutdown, or at minimum on graceful app shutdown, flush buffered spans:

```python
prism_handler.flush()
```

### 3.5 Trace the Leak Judge / Help Judge as their own agent

These calls matter most for PeerRing's "Prove" story, so give them their own `agent_id` and attach the governance verdict as metadata — this is what lets us later filter PRISM by `agent_id=leak-judge` and see judge performance in isolation from tutor/peer performance.

```python
# app/judges.py
import time
from app.telemetry import _prism_client

async def run_leak_judge(proposed_text: str, blackboard_patch: str | None,
                          context, session_token: str):
    start = time.monotonic()
    verdict = await leak_judge_model.evaluate(proposed_text, blackboard_patch, context)
    latency_ms = int((time.monotonic() - start) * 1000)

    # Fire-and-forget: never await this on the response path (see §4.1)
    asyncio.create_task(
        _prism_client.trace_llm(
            model=LEAK_JUDGE_MODEL_NAME,
            input_messages=[{"role": "user", "content": proposed_text}],
            output_message=verdict.reason or "approved",
            latency_ms=latency_ms,
            session_id=session_token,
            agent_id="leak-judge",
            agent_name="Leak Judge",
            metadata={
                "leak_detected": verdict.leak_detected,
                "policy_score": verdict.policy_score,   # e.g. r_ped
                "checked_blackboard": blackboard_patch is not None,
                "concept": context.active_step,
            },
        )
    )
    return verdict
```

Do the same for `Help Judge` (`agent_id="help-judge"`) and for `Policy Rewriter` invocations (`agent_id="policy-rewriter"`, metadata `{"violation_type": ..., "original_trace_id": ...}` using the `trace_id` of the rejected attempt — PRISM de-duplicates on `trace_id`, so re-sending the same rejected trace never creates a duplicate).

### 3.6 Map agents to `agent_id` consistently

This is the single most consequential field for PeerRing's dashboard usability: a changing `agent_id` splits one logical agent into several dashboard entries.

| PeerRing role | `agent_id` |
|---|---|
| Bob (tutor) | `"bob-tutor"` |
| Alice (arithmetic peer) | `"alice-peer"` |
| Charlie (conceptual peer) | `"charlie-peer"` |
| Leak Judge | `"leak-judge"` |
| Help Judge | `"help-judge"` |
| Policy Rewriter | `"policy-rewriter"` |

Set these as fixed constants, not derived at runtime — never generate an `agent_id` per session or per user.

### 3.7 Verify

```bash
curl -sS -X POST "$PRISMTRACE_HOST/api/setup-doctor/handshake" \
  -H "Content-Type: application/json" \
  -H "X-PRISMtrace-Key: $PRISMTRACE_API_KEY" \
  -d '{"project_id": "'"$PRISMTRACE_PROJECT_ID"'", "send_test_trace": true}'

# then, after a real conversation has run through the app:
curl -sS "$PRISMTRACE_HOST/api/setup-doctor?project_id=$PRISMTRACE_PROJECT_ID" \
  -H "X-PRISMtrace-Key: $PRISMTRACE_API_KEY"
```

Check `live_connected: true` and, ideally, `app_connected: true` (proves it came from the real app, not a curl test). Wire this into CI as a post-deploy smoke check against the staging project.

### 3.8 Dashboard configuration (one-time, no code)

- **Alerts** (works on Free tier): `latency` > 5000ms; `compliance_score` < 60; `guardrail_blocks` > 10/window (possible adversarial-prompt attack against Bob); `error_rate` > 5%; `evaluation_failed` > 0.
- **Guardrails** (Builder tier only): turn on **Prompt Injection → block** as a second, generic layer behind our own Adversarial Prompt Resistance classifier — belt-and-suspenders, not a replacement. Turn on **PII/PHI Detection → flag** first (watch it for a few days before switching to block), relevant since learners may paste homework containing names/school info.
- **Root Cause / Remediation**: use this instead of hand-building the "baseline vs. upgraded Trust Pack" — it clusters recurring Leak Judge rejections and points back at the responsible prompt/node, which is effectively the automated version of the demo's "Prove" stage.

---

## 4. Best Practices

### 4.1 Error handling

- **Never await PRISM calls on the WebSocket response path.** Every `trace_llm`/handler call in this guide is either fired via `asyncio.create_task(...)` or buffered by the SDK's own background flush — PRISM being slow or down must never add latency to a tutoring turn or block a leak-judge decision.
- **Treat PRISM outages as non-fatal.** Wrap manual trace calls in try/except and log locally (e.g., to stdout/your existing logger) rather than raising — losing an observability trace is acceptable; losing a tutoring turn is not.
- **Handle `429` (200 req/min ingest limit) with backoff, not a crash.** At PeerRing's expected concurrency (multiple judge calls + graph spans per turn), a burst of simultaneous sessions can approach this. Either queue traces client-side and drain at a controlled rate, or batch judge traces where the SDK supports it.
- **Handle `402` distinctly from `401`/`403`.** A `402` means a credit-metered *dashboard* action failed (e.g., a Root Cause run someone triggered manually) — it never affects ingest, scoring, or guardrails, which stay free. Don't treat it as an integration failure.
- **`ADK-style silent failures don't apply here** (we're not on Google ADK), but the equivalent risk exists: if a judge call throws before we reach the `trace_llm` call, that turn is silently missing from PRISM. Wrap judge execution so exceptions are traced too (`metadata={"error": str(exc)}`) before re-raising, mirroring the ADK guidance in PRISM's own docs.

### 4.2 Security / key management

- **`ingest`-scoped key only** in the FastAPI service. It cannot read data back or spend credits even if compromised.
- **Separate PRISM project per environment** (dev/staging/prod) — this contains blast radius if a staging key leaks, and matches PeerRing's own environment separation.
- Key goes in the platform secret manager in production (not `.env` — that's local-only), **never** the request body (`api_key` in the JSON body is deprecated and gets logged by any proxy/WAF in front of the API — always the `X-PRISMtrace-Key` header).
- **Rotate, don't swap**: PRISM's rotation keeps the old key working for a grace period, so roll the new key into secrets, redeploy, confirm `live_connected`, then revoke the old one — no downtime window.
- **Strongly consider Content-Free Ingest** (Settings → Data handling) for the production project, given PeerRing's learners may be minors. This drops prompt/response text at ingest while keeping structure, timing, token counts, cost, and outcome. Trade-off: content-free traces get **no** automatic PRISM quality/hallucination scoring (our own Leak/Help Judge remains the actual enforcement either way, so this loses a secondary signal, not the safety mechanism). Decide this explicitly with the team rather than defaulting to full content capture.
- Audit the **Before you go to production** checklist in PRISM's own docs before the hackathon demo goes live against real traffic (stable `session_id`/`agent_id`, ingest-scoped keys, trace delivery off request path, alerts configured, connection health green).

### 4.3 Performance considerations

- **Free tier ceiling is 25,000 traces/month.** PeerRing emits *multiple* traces per turn (graph trajectory + leak judge + help judge + occasional rewrite) — estimate volume before the demo: a 10-turn conversation could easily generate 30–40 traces. Budget accordingly; move to Builder (250,000/mo) if running a multi-day public demo or load test.
- **14-day retention on Free** — if the PRISM dashboard is part of the judge-facing demo narrative (Trust Pack screenshots), capture/export what you need (CSV via Data Export) rather than relying on the dashboard staying populated.
- **Guardrails-as-prevention require the proxy path**, which we're deliberately not using on the hot path (§2.1) — don't expect PRISM's dashboard guardrails to block a live tutor response; they flag/audit only on the SDK path. If real-time blocking via PRISM specifically is ever wanted for a narrow slice (e.g., only the Leak Judge's own model call), that call alone could go through the Anthropic proxy route (`https://prism.blockconvey.com/proxy/anthropic`) since it's not on the critical latency path in the same way Bob/Alice/Charlie's user-facing generation is — evaluate the added ~5–15ms hop against the judge's <250ms budget before adopting.
- **Ambient `prismtrace.session()` over manual threading** — cleaner than passing `session_id` through every judge/orchestrator call site, and matches PeerRing's existing per-turn `async with` style around the Redis turn lock.
