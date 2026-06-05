# Implementation: Agent Factory Contract (Milestone 1.1)

Implements `create_tinycua_agent(...)` factory function and `TinyCUALoop` class that extends the SDK `BaseLoop`. The factory constructs an SDK `Agent` with a `TinyCUALoop` attached, enabling the full TinyCUA node-based execution flow. No SDK public API modifications required.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | — | — | — |

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python >=3.12
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_agent_factory.py
"""Integration tests for the agent factory contract."""

import pytest
from tinycua_sdk.agent.agent import Agent
from tinycua_sdk.agent.loop import BaseLoop
from tinycua.factory import create_tinycua_agent
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session
from tinycua.config.session_config import SessionConfig


class TestCreateTinyCUAAgent:
    """Tests for the create_tinycua_agent factory function."""

    def test_returns_sdk_agent_instance(self):
        """Factory must return an SDK Agent with TinyCUALoop attached."""
        agent = create_tinycua_agent()
        assert isinstance(agent, Agent)
        assert isinstance(agent.config.loop, TinyCUALoop)

    def test_loop_extends_base_loop(self):
        """TinyCUALoop must be a subclass of SDK BaseLoop."""
        agent = create_tinycua_agent()
        assert isinstance(agent.config.loop, BaseLoop)

    def test_creates_new_session_when_none(self):
        """When session=None, a new root Session must be created."""
        agent = create_tinycua_agent()
        loop = agent.config.loop
        assert isinstance(loop.root_session, Session)

    def test_uses_provided_session(self):
        """When session is provided, factory must use it."""
        session = Session()
        agent = create_tinycua_agent(session=session)
        loop = agent.config.loop
        assert loop.root_session is session

    def test_applies_session_config(self):
        """Provided SessionConfig must be applied to the session."""
        config = SessionConfig(max_context_messages=100)
        agent = create_tinycua_agent(session_config=config)
        loop = agent.config.loop
        assert loop.session_config is config
        assert loop.root_session.config is config

    def test_empty_queue_returns_empty_string(self):
        """When queue is empty, run() must return empty string (not hang)."""
        agent = create_tinycua_agent()
        result = asyncio.get_event_loop().run_until_complete(
            agent.run("hello")
        )
        assert isinstance(result, str)
```

### Key Test Scenarios

- [ ] **Scenario 1**: Factory returns SDK Agent with TinyCUALoop — proves the contract is wired correctly
- [ ] **Scenario 2**: New session created when none provided — proves default session lifecycle
- [ ] **Scenario 3**: SessionConfig applied to session — proves configuration propagation
- [ ] **Scenario 4**: Empty queue graceful behavior — proves no infinite loop on milestone 1.1

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for factory function — test parameter handling, edge cases
- [ ] Unit tests for TinyCUALoop — test construction, run delegation
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify `create_tinycua_agent()` returns a usable Agent instance
- [ ] Verify `agent.run("hello")` completes without error (empty queue path)

### Performance Considerations

- [ ] N/A — factory construction is synchronous and lightweight

## Proposed Changes

### New Module: `tinycua/config/`

#### [NEW] `src/tinycua/tinycua/config/__init__.py`

- **Description**: Package init for config module
- **Rationale**: Standard Python package structure

#### [NEW] `src/tinycua/tinycua/config/session_config.py`

- **Description**: `SessionConfig` dataclass with compaction strategy, context limits, metadata
- **Dependencies**: None (pure data class)

### New Module: `tinycua/models/`

#### [NEW] `src/tinycua/tinycua/models/__init__.py`

- **Description**: Package init for models module
- **Rationale**: Standard Python package structure

#### [NEW] `src/tinycua/tinycua/models/session.py`

- **Description**: `Session` class with session_id, session_context, chat_history, task, todo, config
- **Dependencies**: `tinycua.config.session_config`

### New Module: `tinycua/loops/`

#### [NEW] `src/tinycua/tinycua/loops/__init__.py`

- **Description**: Package init for loops module
- **Rationale**: Standard Python package structure

#### [NEW] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Description**: `TinyCUALoop` extending SDK `BaseLoop` with root_session, NodeQueue placeholder
- **Dependencies**: `tinycua_sdk.agent.loop.BaseLoop`, `tinycua.models.session.Session`

### New Module: `tinycua/factory.py`

#### [NEW] `src/tinycua/tinycua/factory.py`

- **Description**: `create_tinycua_agent()` factory function
- **Dependencies**: `tinycua.loops.tinycua_loop.TinyCUALoop`, `tinycua_sdk.agent.agent.Agent`

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.config.session_config` | New | SessionConfig dataclass |
| `tinycua.models.session` | New | Session class skeleton |
| `tinycua.loops.tinycua_loop` | New | TinyCUALoop extending BaseLoop |
| `tinycua.factory` | New | create_tinycua_agent() factory |
| `tinycua-sdk` | No change | SDK public APIs remain untouched |

## Data Model Changes

```python
# New types

SessionConfig:
    compaction_strategy: CompactionStrategy | None
    max_context_messages: int | None
    max_context_tokens: int | None
    metadata: dict

Session:
    session_id: str
    session_context: list[SessionContextEntry]
    chat_history: list[ChatRecord]
    task: Task | None
    todo: Todo | None
    config: SessionConfig

TinyCUALoop:
    root_session: Session
    queue: NodeQueue  # placeholder
    session_config: SessionConfig | None
```

## API Changes

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| — | — | No API changes; this is an internal factory function |

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| — | — | No existing endpoints modified |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| tinycua-sdk | >=0.1.0 | Provides BaseLoop, Agent (already a dependency) |

### Internal Dependencies

- [ ] Depends on: SDK BaseLoop contract (already exists)
- [ ] Blocks: Milestones 1.5–1.7 (node implementations depend on factory)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Empty NodeQueue causes infinite loop in run() | Medium | Guard: if queue empty, return empty string and log warning |
| SDK BaseLoop interface changes | Low | Pin SDK version; loop extension is minimal surface area |
| Session model drift from SDK conventions | Low | Follow SDK patterns from design docs |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-05*
