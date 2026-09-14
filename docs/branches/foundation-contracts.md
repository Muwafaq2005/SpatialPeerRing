# Foundation Layer - Core Contracts and State

**Branch:** `foundation/core-contracts-and-state`  
**Owner:** `nad` (Foundation & Governance Architect)  
**Status:** ✅ **COMPLETE** - Ready for `usm` and `muw` development

## Overview

This foundation layer provides the core contracts and state management that enables `usm` (Agent Intelligence) and `muw` (Spatial UI) to develop their features independently without blocking dependencies.

## What's Implemented

### 1. Core Pydantic State Schema (`app/state/pydantic_state.py`)

- **`PeerRingState`**: Centralized state with dialogue history, curriculum DAG, policy levels, and turn locks
- **`DialogueMessage`**: Individual messages with agent metadata, think blocks, and governance flags
- **`CandidateAction`**: Agent proposals for pedagogical orchestrator scoring
- **`AgentResponse`**: Complete agent responses with Pólya deliberation and blackboard patches
- **`JudgeVerdict`**: Governance evaluation results from leak/help judges
- **`CurriculumNode`**: Curriculum concepts with mastery tracking and DAG relationships
- **`PolicyState`**: Adaptive assistance levels, recovery states, and governance settings

### 2. Abstract Base Contracts (`app/contracts/`)

- **`BaseAgent`**: Abstract interface for Bob, Alice, Charlie with `propose_candidate_action()` and `generate_response()`
- **`BaseJudge`**: Abstract interface for governance judges with fast `evaluate()` method (<250ms target)
- **Full type safety**: All methods use proper Pydantic types for reliable interfaces

### 3. Mock Implementation Registry (`app/contracts/mock_registry.py`)

- **`MockBobAgent`**: Socratic tutor that asks guiding questions (never gives answers)
- **`MockAliceAgent`**: Arithmetic peer with intentional calculation errors  
- **`MockCharlieAgent`**: Conceptual peer with deliberate misconceptions
- **`MockLeakJudge`**: Fast leak detection (fails on complete solutions)
- **`MockHelpJudge`**: Helpfulness evaluation (passes encouraging responses)
- **`MockAgentRegistry`**: Complete registry with `run_mock_turn()` for full pipeline testing

### 4. Comprehensive Test Suite (`tests/contracts/`)

- **State serialization tests**: JSON roundtrip validation for Redis storage
- **Contract compliance tests**: Verify all mocks implement required interfaces  
- **Integration tests**: Complete turn simulation through agent→judge pipeline
- **Performance tests**: Governance evaluation under 250ms target
- **Foundation readiness verification**: Confirms system ready for parallel development

## Directory Structure Created

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Environment settings and constants
│   ├── api/
│   │   ├── __init__.py
│   │   ├── ws_router.py           # WebSocket connection manager (stub)
│   │   └── health_routes.py       # Health checks and setup doctor
│   ├── state/
│   │   ├── __init__.py
│   │   └── pydantic_state.py      # Core PeerRingState schema ⭐
│   └── contracts/
│       ├── __init__.py
│       ├── base_agent.py          # BaseAgent abstract class ⭐
│       ├── base_judge.py          # BaseJudge abstract class ⭐
│       └── mock_registry.py       # Mock implementations ⭐
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest configuration
│   └── contracts/
│       ├── __init__.py
│       ├── test_pydantic_state.py      # State schema tests
│       ├── test_base_contracts.py      # Contract interface tests
│       └── test_foundation_integration.py  # Integration tests
└── pyproject.toml                 # Python project configuration
```

## Key Features for Team Integration

### For `usm` (Agent Intelligence Lead):

✅ **`BaseAgent` contract ready** - Implement Bob, Alice, Charlie by extending `BaseAgent`  
✅ **Mock agents available** - Test orchestrator logic with `MockAgentRegistry`  
✅ **State management** - Access curriculum DAG, struggle scores, policy levels via `PeerRingState`  
✅ **Pólya integration** - `think_block` field ready for `<think>` deliberation  

**Next steps for usm:**
```bash
git checkout foundation/core-contracts-and-state
# Import and extend BaseAgent for your agents
from app.contracts.base_agent import BaseAgent
from app.state.pydantic_state import PeerRingState, CandidateAction, AgentResponse
```

### For `muw` (Spatial UI Lead):

✅ **WebSocket router stub** - Basic WebSocket endpoint ready for enhancement  
✅ **State serialization** - Full JSON roundtrip for real-time UI updates  
✅ **Blackboard integration** - `blackboard_patch` field ready for KaTeX/SVG patches  
✅ **PRISM telemetry hooks** - Metadata fields ready in state and responses  

**Next steps for muw:**
```bash
git checkout foundation/core-contracts-and-state
# Use MockAgentRegistry to test UI without live agents
from app.contracts.mock_registry import mock_registry
result = await mock_registry.run_mock_turn(state, user_input)
```

## Testing and Validation

Run the foundation test suite:

```bash
cd backend
python -m pytest tests/contracts/ -v
```

**Test Coverage:**
- ✅ State serialization (JSON roundtrip)  
- ✅ Contract interface compliance  
- ✅ Mock agent behavior validation  
- ✅ Governance judge performance (<250ms)  
- ✅ Complete turn simulation  
- ✅ Foundation readiness check  

## API Documentation

Access the FastAPI docs once running:
```bash
cd backend  
uvicorn app.main:app --reload
# Visit: http://localhost:8000/docs
```

**Key endpoints:**
- `GET /api/v1/health` - Basic health check
- `GET /api/v1/setup-doctor` - Foundation readiness verification  
- `WS /api/v1/ws/{session_id}` - WebSocket connection (enhanced by muw)

## Integration Points

### Redis Integration (Next: `foundation/redis-turn-mutex`)
- `PeerRingState` ready for Redis serialization  
- `TurnLockStatus` prepared for `SETNX` mutex implementation
- Mock lock methods ready to be replaced with Redis calls

### LLM Integration (For usm's agent implementations)
- `BaseAgent.generate_response()` ready for OpenAI/Anthropic calls
- `think_block` field ready for Pólya `<think>` tags
- `AgentResponse` includes token usage and timing metadata

### PRISM Integration (For muw's telemetry)  
- `prism_session_id` and `prism_trace_metadata` fields in `PeerRingState`
- All response objects include metadata hooks for trace instrumentation
- Performance timing fields ready for 7-pillar scoring

## Foundation Verification ✅

Run the foundation readiness check:
```bash
python -c "
from app.contracts.mock_registry import MockAgentRegistry
registry = MockAgentRegistry()
print(f'✅ Agents: {registry.list_agents()}')  
print(f'✅ Judges: {registry.list_judges()}')
print('✅ Foundation ready for parallel development!')
"
```

## Next Branch: `foundation/redis-turn-mutex`

With contracts complete, `nad` should now implement:
1. Redis connection and turn mutex using `SETNX`
2. State persistence with JSON serialization to Redis
3. WebSocket turn lock coordination  
4. Session cleanup and TTL management

This foundation enables `usm` and `muw` to build their features in parallel branches without merge conflicts or blocking dependencies.

---
**Foundation Layer Status: ✅ COMPLETE**  
**Ready for:** `usm` (agents), `muw` (3D UI + PRISM), `nad` (Redis + governance)