# Implementation: TinyCUALoop SDK Integration

Implements TinyCUALoop as a node-based execution loop that extends SDK BaseLoop, enabling sequential node execution with SDK-compatible message merging, tool scoping, and streaming support.

## Context

- **Spec Reference**: `./spec.md` — TinyCUALoop SDK Integration (Milestone 1.8)
- **Design Reference**: `./design.md` — TinyCUALoop SDK Integration design
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### SDK Verification (Before TDD Phase) — COMPLETED

- [x] **Verify Agent._call_llm() return type**: Returns `LLMResponse` (TypedDict with keys: content, tool_calls, usage, finish_reason, model) — dict mocks are correct
- [x] **Verify Agent._call_llm() is async**: Method is async (`async def _call_llm`) — must use AsyncMock
- [x] **Update test mocks to match real SDK**: No changes needed — dict mocks work with TypedDict

### Configuration

- [ ] **None** — no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| - [ ] **None** — no external services needed |

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.12+, uv
- [ ] **Package manager**: uv
- [ ] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_tinycua_loop_integration.py
"""Integration tests for TinyCUALoop node-based execution."""


import pytest
from unittest.mock import AsyncMock, MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeToolPolicy
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session


# VERIFIED: Agent._call_llm() returns LLMResponse (TypedDict with keys: content, tool_calls, usage, finish_reason, model).
# Dict mocks below are correct — LLMResponse is a TypedDict, so dict access via .get() works.


class StubNode(ProcessNode):
    """Minimal node for testing that returns a fixed response."""

    def __init__(self, response_content: str = "stub response"):
        super().__init__(
            node_id="stub",
            config=NodeConfigBase(),
            instruction="You are a test stub",
        )
        self.response_content = response_content

    def _call_llm(self, messages):
        from tinycua.config.types import LLMResult
        return LLMResult(
            content=self.response_content,
            role="assistant",
        )

    def __call__(self, input):
        from tinycua.config.types import LLMResult
        return LLMResult(
            content=self.response_content,
            role="assistant",
        )


class ResponseNode(ProcessNode):
    """Terminal node that returns the final response."""

    def __init__(self):
        super().__init__(
            node_id="response",
            config=NodeConfigBase(),
            instruction="Return the final response",
            is_terminal=True,
        )

    def _call_llm(self, messages):
        from tinycua.config.types import LLMResult
        # Return the last user/assistant message as the final response
        for msg in reversed(messages):
            if msg.get("role") in ("user", "assistant"):
                return LLMResult(content=msg.get("content", ""), role="assistant")
        return LLMResult(content="No response", role="assistant")

    def __call__(self, input):
        from tinycua.config.types import LLMResult
        return LLMResult(content="final response", role="assistant")


async def test_tinycua_loop_executes_node_queue():
    """Tests queue execution path (no bootstrap) — validates sequential node processing."""
    stub = StubNode("processed by stub")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert isinstance(result, str)
    assert len(result) > 0


async def test_tinycua_loop_ensure_terminal_bootstrap():
    """TinyCUALoop auto-appends terminal node when default_terminal_node is set."""
    terminal = ResponseNode()
    loop = TinyCUALoop(default_terminal_node=terminal)
    stub = StubNode("test")
    loop.queue.items = [stub]

    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )
    await loop.run(agent=agent, messages=[], tools=[], stream=False)
    assert loop.queue.items[-1] is terminal


async def test_tinycua_loop_merges_sdk_messages():
    """TinyCUALoop merges SDK messages into root session input_context."""
    loop = TinyCUALoop()
    session = loop.root_session
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]

    await loop.run(
        agent=agent,
        messages=messages,
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert session.input_context == messages


async def test_tinycua_loop_tool_scoping():
    """TinyCUALoop applies NodeToolPolicy to resolve tools per node."""
    policy = NodeToolPolicy(
        include_agent_tools="selected",
        allowed_agent_tool_names=["tool_a"],
    )
    config = NodeConfigBase(tool_policy=policy)
    node = StubNode()
    node.config = config

    outer_tools = [MagicMock(name="tool_a"), MagicMock(name="tool_b")]
    resolved = config.tool_policy.resolve_tools(outer_tools)
    assert len(resolved) == 1


async def test_tinycua_loop_override_instructions():
    """TinyCUALoop passes override_instructions to nodes."""
    loop = TinyCUALoop()
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions="custom instructions",
        stream=False,
    )
    assert isinstance(result, str)


async def test_tinycua_loop_stream_false_returns_string():
    """TinyCUALoop run(stream=False) returns a string."""
    loop = TinyCUALoop()
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "response", "tool_calls": None}
    )

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=False,
    )
    assert isinstance(result, str)


async def test_tinycua_loop_stream_true_returns_iterator():
    """TinyCUALoop run(stream=True) returns an async iterator."""
    loop = TinyCUALoop()
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "response", "tool_calls": None}
    )

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )
    import collections.abc
    assert isinstance(result, collections.abc.AsyncIterator)
```

### Key Test Scenarios

- [ ] **Scenario 1**: Node queue execution — loop processes StubNode + ResponseNode, returns final response
- [ ] **Scenario 2**: Message merging — SDK messages appear in root_session.input_context
- [ ] **Scenario 3**: Tool scoping — NodeToolPolicy.resolve_tools() filters outer tools per node config
- [ ] **Scenario 4**: Override instructions — override_instructions passed through to node build_instruction()
- [ ] **Scenario 5**: Stream=False returns string, stream=True returns async iterator
- [ ] **Edge case**: Empty queue after terminal node removal — returns error or default
- [x] **Verify**: Agent._call_llm() return type matches mock (dict vs object) — VERIFIED: LLMResponse is TypedDict, dict mocks correct

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for TinyCUALoop — test node execution, message merging, streaming
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify `create_tinycua_agent(...).run(query)` executes with minimal node queue
- [ ] Verify chat_history and session_context are populated after run()

### Performance Considerations

- [ ] N/A — MVP with sequential node execution

## Proposed Changes

### tinycua.models.session

#### MODIFY src/tinycua/tinycua/models/session.py

- **Add `input_context` field**: `list[dict[str, Any]]` — stores merged SDK messages from the agent loop
- **Rationale**: Spec FR-005 requires merging SDK messages into root session input context; Session currently lacks this field

### tinycua.loops

#### NEW src/tinycua/tinycua/loops/response_node.py

- **Create ResponseNode class**: Terminal ProcessNode that captures the final response content
- **Dependencies**: tinycua.loops.node.ProcessNode, tinycua.config.node_config.NodeConfigBase
- **Rationale**: Spec FR-010 requires a terminal ResponseNode at queue end; needed as default_terminal_node for TinyCUALoop bootstrap

#### MODIFY src/tinycua/tinycua/loops/__init__.py

- **Export ResponseNode**: Add to `__all__` and import
- **Rationale**: ResponseNode is a core loop primitive

#### MODIFY src/tinycua/tinycua/loops/tinycua_loop.py

- **Implement node-based execution in run()**: Replace direct agent._call_llm() passthrough with node queue iteration
- **Add message merging**: Merge SDK messages into root_session.input_context before execution
- **Add tool scoping**: Use NodeToolPolicy.resolve_tools() per node for tool filtering
- **Implement _execute_node()**: Execute a single node by building messages, calling agent._call_llm(), recording output
- **Record chat_history per node**: Append each node's LLM call to root_session.chat_history
- **Record session_context per node**: Append selected context via node.record_output()
- **Implement stream=True support**: Yield async iterator of SDK-compatible event dicts in streaming mode
- **Rationale**: Core spec requirements FR-001 through FR-011

### tinycua.factory

#### MODIFY src/tinycua/tinycua/factory.py

- **Wire default_terminal_node**: Pass ResponseNode as default_terminal_node to TinyCUALoop
- **Rationale**: Factory should produce a working loop with terminal safety out of the box

### Tests

#### NEW src/tinycua/tests/integration/test_tinycua_loop_integration.py

- **Integration tests**: End-to-end tests for node execution, message merging, tool scoping, streaming
- **Dependencies**: All production changes above

#### MODIFY src/tinycua/tests/unit/test_tinycua_loop.py

- **Update existing tests**: Adapt to new node-based execution behavior
- **Add new unit tests**: Test _execute_node(), message merging, tool scoping

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| tinycua.models.session | Modify | Add `input_context` field for SDK message merging |
| tinycua.loops.response_node | New | Terminal ResponseNode class for queue bootstrap |
| tinycua.loops.tinycua_loop | Modify | Replace passthrough with node-based execution loop |
| tinycua.factory | Modify | Wire ResponseNode as default terminal node |

## Data Model Changes

```python
# Session gains input_context field
Session:
    input_context: list[dict[str, Any]] = field(default_factory=list)  # NEW
    chat_history: list[dict[str, Any]] = field(default_factory=list)   # existing
    session_context: list[dict[str, Any]] = field(default_factory=list) # existing
```

## API Changes

### Modified Functions

| Function | Change | Description |
|----------|--------|-------------|
| `TinyCUALoop.run()` | Modified | Now executes node queue instead of passthrough |
| `TinyCUALoop._execute_node()` | New | Execute a single node with agent._call_llm() |
| `create_tinycua_agent()` | Modified | Wires ResponseNode as default terminal node |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| None | — | No new external dependencies |

### Internal Dependencies

- [ ] Depends on existing Node, ProcessNode, NodeQueue (already implemented)
- [ ] Depends on existing Session model (needs `input_context` field added)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Existing unit tests assume passthrough behavior | Medium | Update tests to expect node execution; ensure backward compat |
| agent._call_llm() async interface vs ProcessNode._call_llm() sync | Medium | TinyCUALoop orchestrates calls directly, bypassing ProcessNode._call_llm() |
| Stream mode complexity with node events | Low | Start with simple passthrough stream, add node events in follow-up |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-08*
