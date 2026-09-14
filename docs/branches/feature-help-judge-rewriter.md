# Help Judge & Policy Rewriter Implementation Guide

**Branch:** `feature/help-judge-rewriter`  
**Owner:** `nad` (Foundation & Governance Architect)  
**Status:** ✅ **COMPLETE** — Second-pass Help Judge & Socratic Policy Rewriter operational  
**Implementation Date:** September 14, 2026  

## Overview

Feature B2 implements the second tier of the Answer Governance subsystem:
1. **`HelpJudge`**: Evaluates whether candidate dialogue provides authentic Socratic inquiry, positive scaffolding, and assistance-level-appropriate guidance while rejecting dismissive, dead-end, or harsh statements.
2. **`PolicyRewriter`**: Transparently regenerates candidate responses that fail either `LeakJudge` or `HelpJudge` using automated heuristic transformations (stripping terminal solutions, scrubbing LaTeX blackboard patches, and enriching dead-ends with Socratic inquiries), with a bounded retry loop (max 2 attempts) and a guaranteed curriculum-anchored Socratic fallback.

---

## Architecture & Turn Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    Candidate Agent Output                   │
│        content + think_block + optional blackboard_patch    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Governance Gate                        │
│         LeakJudge.evaluate()  &  HelpJudge.evaluate()       │
└──────────────────────────────┬──────────────────────────────┘
                               │
               Passes Both? ───┴─── Fails either?
                     │                    │
                    YES                   NO
                     │                    ▼
                     │       ┌─────────────────────────────┐
                     │       │       PolicyRewriter        │
                     │       │  Attempt 1-2 Transformations│
                     │       │   Re-evaluate both judges   │
                     │       └────────────┬────────────────┘
                     │                    │
                     │          Passes? ──┴── Exhausted?
                     │            │                 │
                     │           YES                NO
                     │            │                 ▼
                     │            │   Safe Socratic Fallback
                     │            │   (Guaranteed Clean)
                     ▼            ▼                 │
┌─────────────────────────────────────────────────────────────┐
│                   State Persistence & Stream                │
│    Redis Mutex State Save  ──►  WebSocket Client Stream     │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. `HelpJudge` (`backend/app/governance/help_judge.py`)
- **Inheritance:** Extends `BaseJudge` with `judge_type="help"`.
- **Diagnostic Probing Rubric:**
  - Rewards open inquiry (`what do you think`, `how would you`, `can you explain`, `notice that`).
  - Penalizes dismissive/harsh statements (`"figure it out"`, `"i don't know"`, `"just do it"`, `"that's wrong"`).
  - Penalizes excessively terse statements (<8 characters).
- **Assistance-Level Alignment:**
  - Enforces that higher assistance levels (levels 4+) provide concrete guidance and questions.
- **Latency & Performance:**
  - Targets `<200ms` (measured `<50ms`).
  - Populates `confidence`, `reasoning`, `violation_details`, and `suggested_fixes`.

### 2. `PolicyRewriter` (`backend/app/governance/policy_rewriter.py`)
- **Retry Loop:** Up to 2 automated transformation attempts.
- **Leak Remediation:**
  - Strips terminal answers (`"The answer is x = 5"` $\rightarrow$ `"what value would satisfy this step?"`).
  - Decomposes solved statements into active questions.
  - Cleans blackboard patches by replacing terminal solutions with `?` and removing LaTeX `\boxed{...}`.
- **Help Remediation:**
  - Replaces dismissive language with supportive framing.
  - Ensures a dialogic question mark is present to maintain the Socratic cycle.
- **Safe Fallback Guarantee:**
  - If retries fail, emits curriculum-anchored Socratic inquiry (e.g. distributive property, factoring, linear equations) guaranteed to pass both judges.

### 3. Gateway Integration (`backend/app/api/ws_router.py`)
- Initialized on `WebSocketConnectionManager`.
- Replaces mock help judge with real `HelpJudge`.
- Executes `PolicyRewriter` automatically when `not all_pass` before falling back to `GOVERNANCE_REJECTION`.

---

## Verification & Test Suite

All tests reside in `backend/tests/governance/test_rewriter.py`:
- `TestHelpJudge`:
  - `test_helpful_socratic_responses_pass`: Validates Socratic phrasing passes.
  - `test_unhelpful_dismissive_responses_fail`: Validates unconstructive text rejection.
  - `test_excessively_terse_response_fails`: Validates length thresholding.
  - `test_assistance_level_alignment`: Validates assistance level checks.
  - `test_performance_target`: Confirms latency < 200ms.
- `TestPolicyRewriter`:
  - `test_passing_response_not_modified`: Untouched passthrough for valid turns.
  - `test_rewrite_leaking_response`: Terminal solution scrubbed and converted to inquiry.
  - `test_rewrite_leaking_blackboard_patch`: LaTeX patch cleaned.
  - `test_rewrite_unhelpful_response`: Dismissive text converted to constructive dialogue.
  - `test_fallback_guarantee_on_unfixable_input`: Zero-leak fallback on retry exhaustion.
- `TestGovernancePipelineIntegration`:
  - End-to-end integration test simulating multi-judge interception and rewriting.

To run:
```bash
python -m pytest backend/tests/governance/test_rewriter.py -v
```
