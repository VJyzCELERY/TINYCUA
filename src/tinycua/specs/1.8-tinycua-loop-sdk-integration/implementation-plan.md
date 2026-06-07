# Implementation: TinyCUALoop SDK Integration (Milestone 1.8)

TinyCUALoop that extends SDK BaseLoop and executes a minimal node queue without SDK API modifications.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **.env file** — required variables:
  ```
  # No additional env vars needed for Milestone 1.8 (loop infrastructure only)
  ```
- [x] **None** — this feature has no configuration dependencies beyond existing SDK setup

### Running Services

| Service | Required | Notes |
|---------|----------|-------|
| None | — | All LLM calls mocked in tests |

- [x] **None** — no external services needed for Milestone 1.8

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.12+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Pre-Implementation Verification

- [x] Verify `agent._call_llm` is mockable on the Agent instance:
  ```bash
  cd src/tinycua && uv run python -c "
  from tinycua_sdk.agent import Agent
  a = Agent()
  print('_call_llm attribute:', hasattr(a, '_call_llm'))
  print('type:', type(getattr(a, '_call_llm', None)))
  "
  ```
  If `_call_llm` is on an executor (e.g., `agent._executor.call_llm`), update
  the integration tests to patch `agent._executor.call_llm` or use
  `unittest.mock.patch` on the executor path instead of assigning directly to
  `agent._call_llm`.

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these test pass.

```python
# Test file: src/tinycua/tests/integration/test_tinycua_loop.py
"""Integration tests for TinyCUALoop SDK Integration (Milestone 1.8)."""

import pytest
from unittest.mock import AsyncMock
from tinycua_sdk.agent import Agent, BaseLoop
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


class TestTinyCUALoopConstruction:
    """Tests for TinyCUALoop instantiation and BaseLoop extension."""

    def test_tinycua_loop_extends_base_loop(self):
        """TinyCUALoop is a subclass of SDK BaseLoop."""
        loop = TinyCUALoop()
        assert isinstance(loop, BaseLoop)

    def test_tinycua_loop_creates_root_session_when_none(self):
        """When no session provided, TinyCUALoop creates a new root session."""
        loop = TinyCUALoop()
        assert isinstance(loop.root_session, Session)
        assert loop.root_session.session_id is not None

    def test_tinycua_loop_uses_provided_session(self):
        """When session is provided, TinyCUALoop uses it."""
        session = Session()
        loop = TinyCUALoop(session=session)
        assert loop.root_session is session

    def test_tinycua_loop_owns_node_queue(self):
        """TinyCUALoop owns a NodeQueue."""
        loop = TinyCUALoop()
        assert hasattr(loop, 'node_queue')
        assert hasattr(loop.node_queue, 'items')


class TestTinyCUALoopRun:
    """Tests for TinyCUALoop.run() method."""

    @pytest.mark.asyncio
    async def test_run_returns_string_when_not_streaming(self):
        """run() returns string when stream=False."""
        loop = TinyCUALoop()
        agent = Agent()
        agent._call_llm = AsyncMock(
            return_value={"content": "Hello", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
        )
        result = await loop.run(
            agent=agent,
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
            override_instructions=None,
            stream=False,
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_merges_messages_into_session(self):
        """run() merges SDK messages into root session input_context."""
        loop = TinyCUALoop()
        agent = Agent()
        agent._call_llm = AsyncMock(
            return_value={"content": "Hello", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
        )
        messages = [{"role": "user", "content": "hello"}]
        await loop.run(
            agent=agent,
            messages=messages,
            tools=[],
            override_instructions=None,
            stream=False,
        )
        assert len(loop.root_session.input_context) > 0

    @pytest.mark.asyncio
    async def test_run_records_chat_history(self):
        """run() records messages in session chat history."""
        loop = TinyCUALoop()
        agent = Agent()
        agent._call_llm = AsyncMock(
            return_value={"content": "Hello", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
        )
        await loop.run(
            agent=agent,
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
            override_instructions=None,
            stream=False,
        )
        assert len(loop.root_session.chat_history) > 0

    @pytest.mark.asyncio
    async def test_run_with_stream_true_returns_iterator(self):
        """run() returns async iterator when stream=True."""
        loop = TinyCUALoop()
        agent = Agent()

        async def mock_stream(*args, **kwargs):
            yield {"type": "response.output_text.delta", "delta": "Hi"}
            yield {"type": "response.completed", "finish_reason": "completed"}

        agent._call_llm = mock_stream
        result = await loop.run(
            agent=agent,
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
            override_instructions=None,
            stream=True,
        )
        assert hasattr(result, '__aiter__')

    @pytest.mark.asyncio
    async def test_run_with_override_instructions(self):
        """run() incorporates override instructions when present."""
        loop = TinyCUALoop()
        agent = Agent()
        agent._call_llm = AsyncMock(
            return_value={"content": "Hello", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
        )
        await loop.run(
            agent=agent,
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
            override_instructions="Be extra helpful",
            stream=False,
        )
        assert len(loop.root_session.chat_history) > 0

    @pytest.mark.asyncio
    async def test_run_with_empty_queue_returns_empty(self):
        """run() handles empty queue gracefully."""
        loop = TinyCUALoop()
        agent = Agent()
        agent._call_llm = AsyncMock(
            return_value={"content": "", "tool_calls": None, "usage": None, "finish_reason": "completed", "model": None}
        )
        result = await loop.run(
            agent=agent,
            messages=[{"role": "user", "content": "hello"}],
            tools=[],
            override_instructions=None,
            stream=False,
        )
        assert isinstance(result, str)
```

### Key Test Scenarios

- [ ] **Scenario 1**: TinyCUALoop extends BaseLoop — primary structural requirement
- [ ] **Scenario 2**: TinyCUALoop creates root session when session=None
- [ ] **Scenario 3**: TinyCUALoop uses provided session when session is given
- [ ] **Scenario 4**: run() returns string when stream=False (FR-008)
- [ ] **Scenario 5**: run() merges SDK messages into root session (FR-005)
- [ ] **Scenario 6**: run() records chat history (FR-007)
- [ ] **Scenario 7**: run() returns async iterator when stream=True (FR-009)
- [ ] **Scenario 8**: run() incorporates override instructions (FR-005)
- [ ] **Edge case**: Empty queue handling

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for TinyCUALoop construction and run() behavior
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify TinyCUALoop creates a working agent instance
- [ ] Verify agent.run("hello") executes without SDK API changes

### Performance Considerations

- [ ] N/A for Milestone 1.8 — loop infrastructure only

## Documentation

### README Update

- [ ] Update `src/tinycua/README.md` with TinyCUALoop usage example
  - **File**: `src/tinycua/README.md`
  - **Content**: Add a "Quick Start" or "Usage" section showing TinyCUALoop usage
  - **Verification**: `grep -c "TinyCUALoop" src/tinycua/README.md` returns ≥1

## Proposed Changes

### tinycua.loops (modified module)

#### [MODIFY] src/tinycua/tinycua/loops/tinycua_loop.py

- **Description**: TinyCUALoop extending SDK BaseLoop, owns root_session and NodeQueue, implements run() with stream support, message merging, queue bootstrapping, and node execution loop
- **Dependencies**: tinycua_sdk.agent.BaseLoop, tinycua.models.session.Session, tinycua.loops.node_queue.NodeQueue

#### [MODIFY] src/tinycua/tinycua/loops/node_queue.py

- **Description**: NodeQueue with ensure_terminal() method for ResponseNode guarantee, entry node placement
- **Dependencies**: tinycua.loops.node

### tinycua.models (modified module)

#### [MODIFY] src/tinycua/tinycua/models/session.py

- **Description**: Session class gains input_context field for merged SDK messages
- **Dependencies**: None

### Tests

#### [NEW] src/tinycua/tests/integration/test_tinycua_loop.py

- **Description**: Integration tests proving TinyCUALoop extends BaseLoop and executes minimal queue
- **Dependencies**: tinycua_sdk.agent, tinycua.loops.tinycua_loop

#### [NEW] src/tinycua/tests/unit/test_tinycua_loop_v2.py

- **Description**: Unit tests for TinyCUALoop construction, run() method, stream behavior
- **Dependencies**: tinycua.loops.tinycua_loop

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.loops.tinycua_loop` | Modified | TinyCUALoop gains run() implementation, message merging, queue bootstrapping |
| `tinycua.loops.node_queue` | Modified | NodeQueue gains ensure_terminal() and entry node support |
| `tinycua.models.session` | Modified | Session gains input_context field |
| `tinycua-sdk` | No change | SDK public APIs remain untouched |

## Data Model Changes

See design.md Data Model section for the canonical M1.8 data model. Summary:

- **Session**: session_id, parent_id, session_config, chat_history, session_context, input_context (new)
- **TinyCUALoop(BaseLoop)**: root_session, node_queue
- **NodeQueue**: items, ensure_terminal(), entry node placement

## API Changes

### New Endpoints

None — TinyCUALoop is used via `Agent(loop=TinyCUALoop(...)).run(query)`.

### Modified Endpoints

None — SDK APIs are not modified.

## Dependencies

### External Dependencies

None — all dependencies already in pyproject.toml.

### Internal Dependencies

- [x] Depends on `tinycua-sdk` (already a dependency)
- [x] Blocks downstream milestones (concrete node implementations)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| BaseLoop contract changes in SDK | High | Pin SDK version; loop extension is minimal surface area |
| agent._call_llm() interface mismatch | High | Verify SDK version compatibility before implementation |
| Stream mode compatibility issues | Medium | Test both stream=True and stream=False thoroughly |
| Session context propagation complexity | Low | Keep session model simple; defer advanced propagation to later milestones |

## Requirement Coverage

| FR | Description | Implementation |
|----|-------------|----------------|
| FR-001 | TinyCUALoop extends BaseLoop | `tinycua/loops/tinycua_loop.py` |
| FR-002 | TinyCUALoop implements run() | `tinycua/loops/tinycua_loop.py` |
| FR-003 | TinyCUALoop creates and owns root session | `tinycua/loops/tinycua_loop.py` |
| FR-004 | TinyCUALoop owns NodeQueue | `tinycua/loops/tinycua_loop.py` |
| FR-005 | TinyCUALoop merges SDK messages | `tinycua/loops/tinycua_loop.py` |
| FR-006 | TinyCUALoop calls agent._call_llm() | `tinycua/loops/tinycua_loop.py` |
| FR-007 | TinyCUALoop records chat history | `tinycua/loops/tinycua_loop.py` |
| FR-008 | TinyCUALoop preserves stream=False | `tinycua/loops/tinycua_loop.py` |
| FR-009 | TinyCUALoop preserves stream=True | `tinycua/loops/tinycua_loop.py` |
| FR-010 | TinyCUALoop ensures terminal ResponseNode | `tinycua/loops/node_queue.py` |
| FR-011 | TinyCUALoop ensures entry node | `tinycua/loops/node_queue.py` |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-07*
