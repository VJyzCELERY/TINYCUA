# Implementation: Agent Factory Contract (Milestone 1.1)

Provide a factory function `create_tinycua_agent(...)` that constructs a working TinyCUA agent backed by the existing SDK `Agent` and `BaseLoop` contracts, enabling the full TinyCUA node-based execution flow to run without SDK API modifications.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **.env file** — required variables:
  ```
  # No additional env vars needed for Milestone 1.1 (factory contract only)
  ```
- [x] **None** — this feature has no configuration dependencies beyond existing SDK setup

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| [Local LLM] | No | N/A — mocked in tests | N/A |

- [x] **None** — no external services needed for Milestone 1.1

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.12+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these test pass.

```python
# Test file: tests/integration/test_agent_factory.py
"""Integration tests for Agent Factory Contract (Milestone 1.1)."""

import pytest
from tinycua_sdk.agent import Agent, BaseLoop
from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


class TestCreateTinyCUAAgent:
    """Tests for the create_tinycua_agent factory function."""

    def test_factory_returns_agent_with_tinycua_loop(self):
        """Factory returns SDK Agent with TinyCUALoop attached."""
        agent = create_tinycua_agent()
        assert isinstance(agent, Agent)
        assert isinstance(agent.loop, TinyCUALoop)
        assert isinstance(agent.loop, BaseLoop)

    def test_factory_creates_new_session_when_none(self):
        """When no session provided, factory creates a new root session."""
        agent = create_tinycua_agent()
        loop = agent.loop
        assert isinstance(loop.root_session, Session)
        assert loop.root_session.session_id is not None

    def test_factory_uses_provided_session(self):
        """When session is provided, factory uses it."""
        session = Session()
        agent = create_tinycua_agent(session=session)
        assert agent.loop.root_session is session

    def test_factory_applies_session_config(self):
        """Provided SessionConfig is applied to the session."""
        config = SessionConfig(max_context_messages=100)
        agent = create_tinycua_agent(session_config=config)
        assert agent.loop.session_config == config
        assert agent.loop.root_session.session_config == config

    def test_factory_accepts_agent_kwargs(self):
        """Factory passes **agent_kwargs through to SDK Agent."""
        agent = create_tinycua_agent(name="test-agent", instructions="Be helpful")
        assert agent.name == "test-agent"
        assert agent.instructions == "Be helpful"

    def test_tinycua_loop_extends_base_loop(self):
        """TinyCUALoop is a subclass of SDK BaseLoop."""
        session = Session()
        loop = TinyCUALoop(root_session=session)
        assert isinstance(loop, BaseLoop)


class TestTinyCUALoopRun:
    """Tests for TinyCUALoop.run() execution."""

    @pytest.mark.asyncio
    async def test_run_returns_string_when_not_streaming(self):
        """TinyCUALoop.run() returns string when stream=False."""
        session = Session()
        loop = TinyCUALoop(root_session=session)
        agent = Agent(loop=loop)
        # Mock _call_llm to return a simple response
        agent._call_llm = pytest.AsyncMock(return_value={"content": "Hello"})
        result = await loop.run(agent=agent, messages=[], tools=[], stream=False)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_returns_async_iterator_when_streaming(self):
        """TinyCUALoop.run() returns async iterator when stream=True."""
        session = Session()
        loop = TinyCUALoop(root_session=session)
        agent = Agent(loop=loop)
        # For streaming, we need an async iterator mock
        async def mock_stream(*args, **kwargs):
            yield {"type": "response.output_text.delta", "delta": "Hi"}
            yield {"type": "response.completed", "finish_reason": "completed"}
        agent._call_llm = mock_stream
        result = await loop.run(agent=agent, messages=[], tools=[], stream=True)
        # Should be an async iterator
        assert hasattr(result, '__aiter__')
```

### Key Test Scenarios

- [x] **Scenario 1**: Factory creates Agent with TinyCUALoop when called with defaults — primary success criterion
- [x] **Scenario 2**: Factory creates new session when session=None
- [x] **Scenario 3**: Factory uses provided session when session is given
- [x] **Scenario 4**: Factory applies SessionConfig to session
- [x] **Scenario 5**: TinyCUALoop.run() returns string when stream=False
- [x] **Edge case**: Factory with no arguments — all defaults

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for SessionConfig, Session, TinyCUALoop, factory function
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Verify factory output creates a working agent instance
- [x] Verify SessionConfig is applied to session

### Performance Considerations

- [x] N/A for Milestone 1.1 — factory contract only

## Proposed Changes

### tinycua.config (new module)

#### [NEW] src/tinycua/tinycua/config/__init__.py

- **Description**: New package for configuration dataclasses
- **Dependencies**: None

#### [NEW] src/tinycua/tinycua/config/session_config.py

- **Description**: SessionConfig dataclass with compaction_strategy, max_context_messages, max_context_tokens, metadata fields
- **Dependencies**: None (pure dataclass)

### tinycua.models (new module)

#### [NEW] src/tinycua/tinycua/models/__init__.py

- **Description**: New package for domain models
- **Dependencies**: None

#### [NEW] src/tinycua/tinycua/models/session.py

- **Description**: Session class with session_id, parent_id, session_config, chat_history, session_context, agent_state, task, todo, compact_context()
- **Dependencies**: tinycua.config.session_config

### tinycua.loops (new module)

#### [NEW] src/tinycua/tinycua/loops/__init__.py

- **Description**: New package for execution loops
- **Dependencies**: None

#### [NEW] src/tinycua/tinycua/loops/node_queue.py

- **Description**: NodeQueue class with items, current, input_for_current(), advance(), is_empty() — placeholder for Milestone 1.1
- **Dependencies**: None (placeholder)

#### [NEW] src/tinycua/tinycua/loops/tinycua_loop.py

- **Description**: TinyCUALoop extending SDK BaseLoop, owns root_session and NodeQueue, implements run() method
- **Dependencies**: tinycua_sdk.agent.BaseLoop, tinycua.models.session.Session, tinycua.loops.node_queue.NodeQueue

### tinycua.factory (new module)

#### [NEW] src/tinycua/tinycua/factory.py

- **Description**: create_tinycua_agent() factory function
- **Dependencies**: tinycua.loops.tinycua_loop.TinyCUALoop, tinycua.models.session.Session, tinycua_sdk.agent.Agent

### Tests

#### [NEW] src/tinycua/tests/unit/test_session_config.py

- **Description**: Unit tests for SessionConfig dataclass
- **Dependencies**: tinycua.config.session_config

#### [NEW] src/tinycua/tests/unit/test_session.py

- **Description**: Unit tests for Session class
- **Dependencies**: tinycua.models.session

#### [NEW] src/tinycua/tests/unit/test_tinycua_loop.py

- **Description**: Unit tests for TinyCUALoop construction and basic run path
- **Dependencies**: tinycua.loops.tinycua_loop

#### [NEW] src/tinycua/tests/unit/test_factory.py

- **Description**: Unit tests for create_tinycua_agent factory function
- **Dependencies**: tinycua.factory

#### [NEW] src/tinycua/tests/integration/test_agent_factory.py

- **Description**: Integration tests proving the full factory → agent → loop flow works
- **Dependencies**: All of the above

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.config` | New | SessionConfig dataclass |
| `tinycua.models` | New | Session class |
| `tinycua.loops` | New | NodeQueue placeholder, TinyCUALoop extending BaseLoop |
| `tinycua.factory` | New | create_tinycua_agent() factory function |
| `tinycua-sdk` | No change | SDK public APIs remain untouched |

## Data Model Changes

```python
# New types
SessionConfig:
    compaction_strategy: Any | None = None
    max_context_messages: int | None
    max_context_tokens: int | None
    metadata: dict

Session:
    session_id: str
    parent_id: str | None
    session_config: SessionConfig
    chat_history: list[ChatRecord]
    session_context: list[dict]
    agent_state: AgentState | None
    task: Task | None
    todo: Todo | None

TinyCUALoop(BaseLoop):
    root_session: Session
    queue: NodeQueue
    session_config: SessionConfig | None
```

## API Changes

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `create_tinycua_agent(...)` | Factory function | Creates SDK Agent with TinyCUALoop attached |

### Modified Endpoints

None — SDK APIs are not modified.

## Dependencies

### External Dependencies

None — all dependencies already in pyproject.toml.

### Internal Dependencies

- [x] Depends on `tinycua-sdk` (already a dependency)
- [x] Blocks downstream milestones (nodes, queue, loop integration)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SDK BaseLoop interface changes between versions | High | Pin SDK version in pyproject.toml; loop extension is minimal surface area |
| Empty NodeQueue causes infinite loop in TinyCUALoop.run() | Medium | Add guard: if queue is empty, return empty string and log warning |
| Session model drift from SDK conventions | Medium | Follow SDK Session patterns documented in design docs |

## Requirement Coverage

| FR | Description | Implementation |
|----|-------------|----------------|
| FR-001 | Factory returns `create_tinycua_agent(...)` | `tinycua/factory.py` |
| FR-002 | Factory returns SDK Agent with TinyCUALoop | `tinycua/factory.py` |
| FR-003 | session=None creates new root Session | `tinycua/factory.py` |
| FR-004 | session provided uses provided session | `tinycua/factory.py` |
| FR-005 | SessionConfig applied to session | `tinycua/factory.py` |
| FR-006 | Local model endpoint config | Deferred — Phase 2 |
| FR-007 | TinyCUALoop extends BaseLoop | `tinycua/loops/tinycua_loop.py` |
| FR-008 | TinyCUALoop.run() consumes SDK messages | `tinycua/loops/tinycua_loop.py` |
| FR-009 | TinyCUALoop.run() calls local LLM | `tinycua/loops/tinycua_loop.py` |
| FR-010 | TinyCUALoop records chat history | `tinycua/loops/tinycua_loop.py` |
| FR-011 | TinyCUALoop preserves stream=False | `tinycua/loops/tinycua_loop.py` |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-05*
