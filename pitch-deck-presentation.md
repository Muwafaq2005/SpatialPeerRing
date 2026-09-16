# Spatial PeerRing — Hackathon Pitch Deck Content

> **Format:** Formatted specifically according to the Hackathon Presentation Template.  
> **Team Members:** `nad`, `usm`, `muw`  
> **Project:** Spatial PeerRing (Governed Multi-Agent Socratic Tutoring Environment)

---

## Slide 2: Title Slide

# Spatial PeerRing

### TEAM NAME: Team PeerRing (`nad`, `usm`, `muw`)

> **THE ONE-LINER:**  
> **"A governed, multi-agent 3D Socratic tutoring environment that provably withholds answers under adversarial pressure, models peer mistakes, and continuously adapts to student learning."**

---

## Slide 3: The Problem

### The Pain Point
Generic AI tutors act as **answer-vending machines**: under user pressure or prompt injection, they leak terminal solutions (`x = 5`), bypassing productive struggle and failing to build durable problem-solving schemas. Point-in-time fixes (e.g. system prompts) are unprovable and non-auditable at the policy level.

### Target Audience
1. **STEM Students (Secondary & Post-Secondary):** Need active diagnostic practice, mistake identification, and schema building rather than passive answer copying.
2. **Enterprise EdTech Buyers & Institutions:** Require verifiable, policy-compliant, non-disclosure-guaranteed AI tutoring environments for accreditation and compliance.

### The Hook (60-Second Story)
> *"Meet Alex, a high school calculus student. Struggling on a multi-step derivative problem, Alex asks a generic AI tutor for help. In two seconds, the AI gives him the full answer `x = 5`. Alex copies it down, gets an A on his homework, but fails the mid-term because he never learned **why** or **how** to solve it. Current AI tutors solve the homework, but destroy the learning."*

---

## Slide 4: The Solution

### What It Is
**Spatial PeerRing** — an audited, multi-agent 3D study environment combining a Socratic tutor (**Bob**) and two peer avatars (**Alice** & **Charlie**) governed by an out-of-band answer interception layer.

### Core Value
* **Provable Non-Leakage:** Out-of-band Leak Judge blocks terminal solutions across spoken dialogue AND visual blackboard patches before reaching the client.
* **Productive Cognitive Conflict:** Alice (arithmetic mistakes) and Charlie (conceptual mistakes) model realistic peer errors for the student to catch and correct.
* **Behavior-Derived Adaptation:** Continuously tracks concept-level mastery on a curriculum DAG and adjusts assistance without slow upfront testing.

### UX Focus
* **Immersive 3D Study Pod:** Built in React Three Fiber with low-poly Draco-compressed avatars, gesture states, and a real-time KaTeX math blackboard.
* **Live Policy HUD:** Real-time visual trust signal displaying current speaker, leak check status, and mastery progress.

---

## Slide 5: The "Moat" / Competitive Advantage / Key Features

### Current Alternatives
* **Generic LLM Chatbots (ChatGPT / Claude):** Easily manipulated into revealing complete solutions via direct pressure or split-turn prompt injection.
* **Single-Agent AI Tutors (Khanmigo):** Monolithic tutor personas that lack peer interaction, error modeling, and independent governance guarantees.

### Our Edge (Unfair Advantage)
| Dimension | Traditional AI Tutors | Spatial PeerRing Edge |
|---|---|---|
| **Answer Governance** | Vulnerable system prompt instructions | **Out-of-band Leak Judge & Policy Rewriter** (<250ms gate) |
| **Visual Policy** | None (images/text rendered raw) | **Blackboard Leak Protection** (KaTeX patches run through Leak Judge) |
| **Peer Dynamics** | Single tutor response | **Multi-Agent Pod (Bob + Alice + Charlie)** with distinct error taxonomies |
| **Agent Reasoning** | Single-pass completion | **Latent Pólya Deliberation** (`<think>`: Understand → Plan → Execute → Look Back) |
| **Observability** | Opaque log dumps | **Full-Pipeline Telemetry** (7-Pillar Scoring + Trust Pack) |

---

## Slide 6: Under the Hood / System Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│ FRONTEND / CLIENT: Next.js 14 • React Three Fiber • KaTeX • Zustand     │
│   3D Study Pod Scene  │  Dynamic Blackboard  │  Live Policy HUD        │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │ WebSocket Frame Stream
┌───────────────────────────────────▼────────────────────────────────────┐
│ GATEWAY & STATE: FastAPI • Redis 7.2 Mutex (`SETNX session:turn_lock`) │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ CORE ENGINE: LangGraph • Pólya Deliberation (`<think>`)                 │
│   Pedagogical Orchestrator ──► Bob (Tutor) | Alice (Peer) | Charlie    │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│ GOVERNANCE TIER: Leak Judge ──► Help Judge ──► Policy Rewriter         │
└────────────────────────────────────────────────────────────────────────┘
```

* **Tech Stack:** FastAPI, LangGraph, Redis 7.2, Next.js 14, React Three Fiber, KaTeX.
* **What We Actually Built:**
  1. Centralized Pydantic State Schema (`PeerRingState`) & Redis `SETNX` Turn Lock Mutex.
  2. Multi-Agent Engine (Bob, Alice, Charlie) with Latent Pólya Deliberation.
  3. Out-of-band Leak Judge, Help Judge & Policy Rewriter Interceptor pipeline.
  4. 3D Spatial Study Pod with KaTeX blackboard & Live Policy HUD.
* **The Hard Part:** Decoupling deterministic execution safety (Redis mutex FSM preventing race conditions) from dynamic pedagogical selection (candidate-scoring orchestrator), allowing dynamic turn selection without risking split-turn leaks or WebSocket stalls.

---

## Slide 7: Impact & Feasibility / Challenges & Future Scope

### Scalability
* **Stateless Gateway:** FastAPI + Redis turn lock enables horizontal scaling across distributed worker nodes.
* **Low-Latency Interception:** Async evaluation gates running on sub-250ms fast inference endpoints.

### Business Model / Use Case
* **B2B EdTech Licensing:** Sold to online learning platforms, school districts, and universities requiring auditable non-disclosure guarantees.
* **B2C Subscription:** Premium tier for STEM students seeking active Socratic coaching and peer-based learning.

### Challenges & What We Overcame
* **Visual Bypass Vector:** Discovered that agents could leak answers via visual blackboard patches (`blackboard_patch`). Solved by parsing KaTeX patches into Math ASTs and running them through the exact same Leak Judge as spoken text before client rendering.

### Next Steps & Future Scope
* **Voice & Lip Sync (P1/P2):** Web Speech API integration with jaw-bone viseme animations for 3D avatars.
* **Peer Persona Evolution (P2):** Cross-session long-term memory for Alice and Charlie.
* **Recursive Problem Decomposition (P2):** Automated problem granularity shrink engine for deep recovery.

---

## Slide 8: Q&A

# Q & A

### Spatial PeerRing — Governed Multi-Agent Socratic Tutoring

* **GitHub Repository:** [https://github.com/USMANSARIB/peerring](https://github.com/USMANSARIB/peerring)
* **Team:** `nad` (Foundation & Governance) • `usm` (Agent Intelligence & Adaptive) • `muw` (Spatial UI & Observability)
