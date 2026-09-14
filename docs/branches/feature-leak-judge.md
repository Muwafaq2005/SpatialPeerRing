# Leak Judge Implementation & Criteria Guide

**Branch:** `feature/leak-judge`  
**Owner:** `nad` (Foundation & Governance Architect)  
**Status:** ✅ **COMPLETE** — Out-of-band Leak Judge and Math AST evaluation operational  
**Implementation Date:** September 14, 2026  

## Overview

The **Leak Judge** is an out-of-band governance gate running with high-speed execution (<200ms target, measured <100ms in benchmarks). It intercepts proposed agent dialogue and KaTeX/LaTeX blackboard patches, evaluating them against the current curriculum step to ensure that students are guided Socratically rather than handed terminal answers.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Agent Turn Output                         │
│       Dialogue Content  +  Optional Blackboard Patch        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    LeakJudge.evaluate()                     │
│  1. Fast Regex Pattern Matching (direct answer, solve, step) │
│  2. Mathematical Expression Extraction & AST Comparison     │
│  3. KaTeX Blackboard Patch Decomposition & Environment Parse │
│  4. Cross-Turn Cumulative Risk Accumulation Tracker          │
│  5. Context-Aware Threshold (Strict Mode / Struggle Score)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
         [ PASS (verdict=True) ]      [ FAIL (verdict=False) ]
         Forward to Client Stream     Trigger Governance Rejection
                                      & Policy Rewriter loop
```

## Core Components

### 1. Fast Pattern Matching (`MathExpressionAnalyzer`)
- Regex-based solution indicators detecting explicit terminal answers (`x = 5`, `answer is ...`), numeric conclusions, and multi-step derivations.
- Mathematical expression extraction isolating variable assignments, equations, and expressions.

### 2. Math AST & SymPy Evaluation (`MathASTValidator`)
- Safe parsing of mathematical expressions into symbolic ASTs (`sympy.Basic`, `sympy.Equality`).
- 5-Way Equivalence checking:
  1. Direct symbolic equality (`expr1.equals(expr2)`)
  2. Expanded form equivalence (`expand(e1) == expand(e2)`)
  3. Factored form equivalence (`factor(e1) == factor(e2)`)
  4. Simplified form equivalence (`simplify(e1 - e2) == 0`)
  5. Solved form equivalence (`solve(eq1, var) == solve(eq2, var)`)
- Solution completeness analysis scoring variable assignments, numerical results, and solved equations.

### 3. Blackboard Patch Protection
- Parses LaTeX/KaTeX environments (`\begin{align} ... \end{align}`, `\boxed{...}`).
- Detects complete derivations, multi-equation progressions, and boxed final answers before they are dispatched to the frontend 3D study pod.

### 4. Cross-Turn Leak Tracking (`CrossTurnLeakTracker`)
- Session-scoped tracking accumulating mathematical fragments revealed across consecutive turns.
- Prevents split leaks where an agent reveals partial steps that together compose the terminal solution.

### 5. WebSocket Turn Flow Integration (`ws_router.py`)
- Evaluates agent output after candidate selection in `handle_user_message()`.
- On governance failure: sends `GOVERNANCE_REJECTION` event with suggested fixes, suppressing state save to preserve Socratic progression.

## Benchmark & Test Suite

All tests reside in `backend/tests/contracts/test_leak_judge.py`:
- `TestMathExpressionAnalyzer`: Expression extraction, complete solution detection, blackboard patch leak parsing.
- `TestCrossTurnLeakTracker`: Multi-turn risk escalation and session reset.
- `TestMathASTValidator`: SymPy parsing, 5-way equivalence, completeness scoring.
- `TestLeakJudge`: Safe response pass, leaking response intercept, blackboard patch blocking, cross-turn detection, strict mode sensitivity.
- `TestGovernanceIntegration`: Rejection flow and configuration toggle integration.

Execution command:
```bash
python -m pytest backend/tests/contracts/test_leak_judge.py -v
```
