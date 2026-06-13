# Implementation: Retry, Validation, Monitor Hook, and Streaming Events

This implementation plan covers two related milestones:

1. **Milestone 4.3 — Retry, Validation, and Monitor Hook**: Completes the retry, validation, and monitor hook contracts for TinyCUA nodes.
2. **Milestone 4.4 — Streaming and Transcript Events**: Adds structured streaming support and lifecycle event hooks to TinyCUALoop.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M

## FR → Task → Test Traceability

| FR | Description | Task | Test |
|----|-------------|------|------|
| FR-001 | `stream=True` returns async iterator of event dicts | id:4 (lifecycle events in `_run_stream`) | `test_lifecycle_events_emitted` |
| FR-002 | `stream=False` returns final string response | id:12 (backward compat verification) | `test_tinycua_loop_stream_false_returns_string` (existing) |
| FR-003 | Emit lifecycle events at node boundaries | id:4 (emit `node.started`, `node.llm_call`, `node.completed`, `node.error`) | `test_lifecycle_events_emitted` |
| FR-004 | Include node metadata when `include_node_metadata=True` | id:6 (metadata enrichment) | `test_node_metadata_in_events` |
| FR-005 | Suppress intermediate events when `final_response_only=True` | id:5 (final_response_only filtering) | `test_final_response_only_suppresses_intermediate` |
| FR-006 | Emit internal lifecycle events when `emit_internal_events=True` | id:7 (emit_internal_events control) | `test_lifecycle_events_emitted` |
| FR-007 | Transcript events serializable to JSONL | id:3 (TranscriptRecord type) | `test_transcript_serialization` |
| FR-008 | Preserve SDK `BaseLoop` contract | id:12 (backward compat verification) | `test_tinycua_loop_stream_false_returns_string`, `test_tinycua_loop_stream_true_returns_iterator` (existing) |

---

## Environment Pre-requisites

### Configuration

- [x] **None** — no additional configuration beyond existing project setup. All tests use mocked LLM responses.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| LLM endpoint | No | Mock via existing test fixtures | N/A |

- [x] **None** — unit tests use mocked LLM responses

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.12+, uv
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_retry_integration.py
"""Integration tests for retry, validation, and monitor hook through TinyCUALoop."""


import pytest
from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node import NodeExecutionError, ProcessNode
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


class MockLLM:
    """Mock LLM returning a sequence of LLMResult responses."""
    def __init__(self, responses):
        self._responses = [
            LLMResult(content=r["content"]) if isinstance(r, dict) else r
            for r in responses
        ]
        self.call_count = 0

    def __call__(self, messages, **kwargs):
        idx = min(self.call_count, len(self._responses) - 1)
        self.call_count += 1
        return self._responses[idx]


class RecordingMonitor:
    """Monitor that records all hook calls for assertion."""
    def __init__(self):
        self.before_calls = []
        self.after_calls = []
        self.exhausted_calls = []

    def on_before_node_call(self, node_id, session_id, attempt, messages, resolved_tools):
        self.before_calls.append({
            "node_id": node_id, "session_id": session_id,
            "attempt": attempt, "message_count": len(messages),
        })
        return None

    def on_after_node_call(self, node_id, session_id, attempt, result, validation_result):
        self.after_calls.append({
            "node_id": node_id, "session_id": session_id,
            "attempt": attempt, "is_valid": validation_result.is_valid,
        })
        return None

    def on_retry_exhausted(self, node_id, session_id, error, attempts):
        self.exhausted_calls.append({
            "node_id": node_id, "session_id": session_id,
            "error": str(error), "attempts": attempts,
        })
        return None


def test_retry_with_validation_fn_integration():
    """End-to-end: node retries when custom validation_fn rejects output."""
    reject_calls = [0]

    def reject_first_call(result):
        reject_calls[0] += 1
        if reject_calls[0] <= 1:
            return ValidationResult(is_valid=False, errors=["Custom validation failed"])
        return ValidationResult(is_valid=True, errors=[])

    mock_llm = MockLLM([
        {"role": "assistant", "content": "bad response"},
        {"role": "assistant", "content": "good response"},
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            validation_fn=reject_first_call,
        ),
    )
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    result = node("input")
    assert result.content == "good response"
    assert mock_llm.call_count == 2


def test_exhaustion_record_failure_integration():
    """End-to-end: retry exhaustion writes failure state to session."""
    mock_llm = MockLLM([
        {"role": "assistant", "content": "bad"},
        {"role": "assistant", "content": "bad again"},
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            required_tool_calls=["required_tool"],
            on_retry_exhausted="record_failure",
        ),
    )
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    node("input")
    # Session should have failure state recorded
    contents = [e.content for e in node.session.session_context]
    assert any("RETRY_EXHAUSTED" in c for c in contents)


def test_exhaustion_raise_integration():
    """End-to-end: retry exhaustion raises NodeExecutionError."""
    mock_llm = MockLLM([
        {"role": "assistant", "content": "bad"},
        {"role": "assistant", "content": "still bad"},
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            required_tool_calls=["required_tool"],
            on_retry_exhausted="raise",
        ),
    )
    node = ProcessNode(node_id="test", config=config, instruction="Do work")
    node.session = Session()
    with pytest.raises(NodeExecutionError, match="Retry exhausted"):
        node("input")


def test_monitor_hook_observes_full_cycle():
    """End-to-end: monitor hook is called at correct trigger points."""
    monitor = RecordingMonitor()
    mock_llm = MockLLM([
        {"role": "assistant", "content": "bad"},
        {"role": "assistant", "content": "good"},
    ])
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(
            max_attempts=2,
            required_tool_calls=["required_tool"],
        ),
        monitor=monitor,
    )
    node = ProcessNode(node_id="test-node", config=config, instruction="Do work")
    node.session = Session()
    node("input")

    assert len(monitor.before_calls) == 2  # 2 attempts
    assert monitor.before_calls[0]["attempt"] == 1
    assert monitor.before_calls[1]["attempt"] == 2
    assert len(monitor.after_calls) == 1  # only 1 failed validation (attempt 1)
    assert monitor.after_calls[0]["is_valid"] is False
    assert len(monitor.exhausted_calls) == 0  # succeeded on attempt 2


# Test file: src/tinycua/tests/integration/test_streaming.py
"""Integration tests for streaming and transcript events.

Covers lifecycle event emission, node metadata enrichment,
final_response_only suppression, and JSONL transcript serialization.
See test_tinycua_loop_integration.py for basic stream=False/stream=True
contract tests (scenarios 1 and 2).
"""

from __future__ import annotations

import json

from unittest.mock import MagicMock

from tinycua.config.node_config import NodeConfigBase, NodeStreamPolicy
from tinycua.config.types import TranscriptRecord
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop

from tests.unit.helpers.tinycua_loop_helpers import StubNode, ResponseNode


def _make_mock_agent(stream_events: list[dict] | None = None) -> MagicMock:
    """Create a MagicMock agent with an async streaming _call_llm.

    Args:
        stream_events: Events to yield. Defaults to a single completed event.
    """
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []

    if stream_events is None:
        stream_events = [
            {"type": "response.output_text.delta", "delta": "Hello"},
            {"type": "response.output_text.delta", "delta": " world"},
            {"type": "response.completed", "finish_reason": "completed"},
        ]

    async def _call_llm(*args, **kwargs):  # noqa: ARG001
        for event in stream_events:
            yield event

    agent._call_llm = _call_llm
    return agent


async def test_lifecycle_events_emitted():
    """Verify node lifecycle transitions emit structured events."""
    stub = StubNode("lifecycle test")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )

    events = [e async for e in result]

    lifecycle_types = [e["type"] for e in events if e["type"].startswith("node.")]
    assert "node.started" in lifecycle_types
    assert "node.completed" in lifecycle_types


async def test_node_metadata_in_events():
    """Verify stream events include node_id, node_type, attempt when policy enabled."""
    policy = NodeStreamPolicy(include_node_metadata=True)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("metadata test")
    stub.config = config
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )

    events = [e async for e in result]

    metadata_events = [e for e in events if e.get("node_id") is not None]
    assert len(metadata_events) > 0
    for e in metadata_events:
        assert "node_id" in e
        assert "node_type" in e


async def test_final_response_only_suppresses_intermediate():
    """Verify intermediate node events suppressed when final_response_only=True."""
    policy = NodeStreamPolicy(final_response_only=True)
    config = NodeConfigBase(stream_policy=policy)
    stub = StubNode("intermediate node")
    stub.config = config
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )

    events = [e async for e in result]

    # Only ResponseNode events should be present
    node_ids = {e.get("node_id") for e in events if e.get("node_id")}
    # Intermediate stub node should not appear
    assert "stub" not in node_ids


async def test_transcript_serialization():
    """Verify TranscriptRecord wrapping produces valid JSONL output (FR-007)."""
    stub = StubNode("serialization test")
    terminal = ResponseNode()
    queue = NodeQueue()
    queue.items = [stub, terminal]

    loop = TinyCUALoop(queue=queue)
    agent = _make_mock_agent()

    result = await loop.run(
        agent=agent,
        messages=[],
        tools=[],
        override_instructions=None,
        stream=True,
    )

    events = [e async for e in result]

    # Wrap events in TranscriptRecord (validates FR-007)
    records = [
        TranscriptRecord(event=e, run_id="test-run", session_id="test-session", sequence=i)
        for i, e in enumerate(events)
    ]

    # Serialize to JSONL
    jsonl_lines = [json.dumps(r.to_dict()) for r in records]
    # Parse back
    parsed = [json.loads(line) for line in jsonl_lines]
    assert len(parsed) == len(records)
    for original_record, restored in zip(records, parsed):
        assert restored["run_id"] == "test-run"
        assert restored["session_id"] == "test-session"
        assert restored["event"] == original_record.event
```

### Key Test Scenarios

#### Retry, Validation, and Monitor Hook (Milestone 4.3)

- [ ] **Scenario 1**: Node retries with custom `validation_fn` — first call rejected, second accepted
- [ ] **Scenario 2**: Retry exhaustion with `record_failure` writes failure state to session
- [ ] **Scenario 3**: Retry exhaustion with `raise` raises `NodeExecutionError`
- [ ] **Scenario 4**: Monitor hook observes correct trigger points and arguments across retries
- [ ] **Edge case**: Monitor hook exception does not break node execution
- [ ] **Edge case**: Custom `retry_continuation_builder` produces retry message
- [ ] **Edge case**: `max_attempts=0` results in 1 attempt (no retry)

#### Streaming and Transcript Events (Milestone 4.4)

- [ ] **Scenario 1**: Lifecycle events emitted — proves node boundary events (`node.started`, `node.completed`) work correctly
- [ ] **Scenario 2**: Node metadata enrichment — proves `NodeStreamPolicy.include_node_metadata` populates `node_id`, `node_type` fields
- [ ] **Scenario 3**: `final_response_only` suppression — proves intermediate node events are filtered when `final_response_only=True`
- [ ] **Scenario 4**: JSONL serialization roundtrip — proves transcript export compatibility (parseable back to original dicts)

> **Note**: Basic `stream=False` returns string and `stream=True` returns async iterator contract tests already exist in `test_tinycua_loop_integration.py` (`test_tinycua_loop_stream_false_returns_string`, `test_tinycua_loop_stream_true_returns_iterator`).

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for `validate_output()` with custom `validation_fn`
- [ ] Unit tests for `_build_retry_text()` with custom builder
- [ ] Unit tests for `_handle_exhaustion()` with all three policies
- [ ] Unit tests for `DecisionNode` classification validation and retry
- [ ] Unit tests for `NodeMonitor` hook trigger points and exception handling
- [ ] Unit tests for `AgentMonitor` and `NodeMonitor` independent hook behavior
- [ ] Unit tests for `StreamEvent` model creation and validation
- [ ] Unit tests for `make_lifecycle_event()` and `enrich_stream_event()` helpers
- [ ] Unit tests for `NodeStreamPolicy` enforcement in `_run_stream()`
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify monitor hooks do not write to `chat_history` or `session_context`
- [ ] Verify `record_failure` propagation works with configured `PropagationRule.failure`
- [ ] Verify stream events visually in a test harness that prints events as they arrive
- [ ] Confirm lifecycle events appear at correct node boundaries in multi-node execution

### Performance Considerations

- [ ] Monitor hook overhead is negligible (optional, lightweight, exception-safe)
- [ ] Events are yielded, not accumulated — consumer controls memory usage
- [ ] No additional threading or async infrastructure needed

## Proposed Changes

### Phase 1 — Validation and Retry Completion

#### [MODIFY] `src/tinycua/tinycua/loops/node.py`

- **Wire `retry_continuation_builder` into `ProcessNode.__call__()`**: In the retry loop, check if `retry_policy.retry_continuation_builder` is set and use it instead of `self.build_retry_continuation()` when building the retry text.
- **Implement `_handle_exhaustion()` method**: Extract exhaustion logic into a dedicated method handling `raise`, `record_failure`, and `route_failure` policies.
- **Implement `_record_failure()` method**: Write a `SessionContextEntry` with `segment="output"` containing failure metadata (node_id, attempt count, errors) and call `self.propagate()` if a propagation rule exists.
- **Implement `_call_failure_route()` method**: Check if `on_complete()` defines a failure route and call it; return `True` if called, `False` otherwise.

#### [MODIFY] `src/tinycua/tinycua/loops/node.py` (DecisionNode)

- **Add classification validation**: In `DecisionNode.__call__()`, after the classification call, verify the returned label matches one of `classification_labels`. If invalid, treat as validation failure.
- **Add classification retry loop**: Wrap the classification step in a retry loop that applies the same exhaustion behavior as `ProcessNode`.

### Phase 2 — Monitor Hook Protocol

#### [NEW] `NodeMonitor` protocol in `src/tinycua/tinycua/config/types.py`

- **Define `NodeMonitor` Protocol**: With `on_before_node_call`, `on_after_node_call`, `on_retry_exhausted` methods matching the design spec.
- **Define `AgentMonitor` Protocol**: With the same method signatures, delegating to `NodeMonitor`.

#### [MODIFY] `src/tinycua/tinycua/config/node_config.py`

- **Add `monitor: NodeMonitor | None = None` field to `NodeConfigBase`**: Allows nodes to be configured with a monitor hook.

#### [MODIFY] `src/tinycua/tinycua/loops/node.py`

- **Add `_safe_call()` helper**: Exception-safe monitor hook caller that logs and swallows exceptions.
- **Wire monitor hooks into `ProcessNode.__call__()` and `DecisionNode.__call__()`**: Call `monitor.on_before_node_call()` before LLM call, `monitor.on_after_node_call()` after validation failure, `monitor.on_retry_exhausted()` before exhaustion handling.
- **Incorporate monitor continuations**: If a monitor hook returns a string, append it as an assistant-role continuation to the messages.

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Add `agent_monitor: AgentMonitor | None = None` field to `TinyCUALoop.__init__()`**: Loop-level monitor configuration.
- **Wire `agent_monitor` in `_execute_node()`**: Call `agent_monitor.on_before_node_call()` before LLM call and `agent_monitor.on_after_node_call()` after; delegate to node monitor if configured.

### Phase 3 — Streaming and Transcript Events

#### [NEW] `src/tinycua/tinycua/models/stream_event.py`

- **Description**: New module containing `StreamEvent`, `LifecycleEvent` models and helper functions
- **Dependencies**: `time`, `typing`

#### [MODIFY] `src/tinycua/tinycua/models/__init__.py`

- **Description**: Export new `StreamEvent` and `LifecycleEvent` models
- **Breaking changes**: None (additive)

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Description**: Modify `_run_stream()` to emit lifecycle events at node boundaries, apply `NodeStreamPolicy` filtering, and enrich events with node metadata
- **Breaking changes**: None (streaming behavior enhanced, non-streaming unchanged)
- **Specific changes**:
  - Emit `node.started` event before `agent._call_llm()`
  - Emit `node.completed` event after LLM call completes
  - Emit `node.error` event on exception during node execution
  - Apply `final_response_only` filter to suppress intermediate node events
  - Apply `include_node_metadata` to enrich events with node info
  - Apply `emit_internal_events` to control lifecycle event emission

#### [MODIFY] `src/tinycua/tinycua/config/types.py`

- **Description**: Add `TranscriptRecord` type for WildClawBench-compatible event records
- **Breaking changes**: None (additive)

### Phase 4 — Tests

#### [NEW] `src/tinycua/tests/unit/test_retry_validation.py`

- Unit tests for `validate_output()` with custom `validation_fn` (valid, invalid, exception)
- Unit tests for `_build_retry_text()` with default and custom builder
- Unit tests for `_handle_exhaustion()` with `raise`, `record_failure`, `route_failure`
- Unit tests for `max_attempts=0` (1 attempt, immediate exhaustion)

#### [NEW] `src/tinycua/tests/unit/test_decision_node_retry.py`

- Unit tests for `DecisionNode` classification validation (valid label, invalid label)
- Unit tests for classification retry loop (retry on invalid, exhaustion)

#### [NEW] `src/tinycua/tests/unit/test_monitor_hook.py`

- Unit tests for `NodeMonitor` hook trigger points
- Unit tests for hook exception handling (logged, does not break execution)
- Unit tests for hook continuation message entering retry flow
- Unit tests for `AgentMonitor` and `NodeMonitor` independent hook behavior

#### [NEW] `src/tinycua/tests/integration/test_retry_integration.py`

- Integration tests for retry through `ProcessNode.__call__()`
- Integration tests for monitor hook observing full cycle
- Integration tests for `DecisionNode` classification retry

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/config/types.py` | Modify | Add `NodeMonitor` and `AgentMonitor` protocols, `TranscriptRecord` type |
| `tinycua/config/node_config.py` | Modify | Add `monitor` field to `NodeConfigBase` |
| `tinycua/loops/node.py` | Modify | Wire `retry_continuation_builder`, exhaustion behavior, monitor hooks; add `_safe_call()`, `_handle_exhaustion()`, `_record_failure()`, `_call_failure_route()` |
| `tinycua/loops/tinycua_loop.py` | Modify | Accept optional `AgentMonitor`, wire in `_execute_node()`; lifecycle event emission in `_run_stream()` |
| `tinycua/models/stream_event.py` | New | StreamEvent, LifecycleEvent models and factory functions |
| `tinycua/models/__init__.py` | Modify | Export new models |
| `tests/unit/test_retry_validation.py` | New | Unit tests for retry, validation, exhaustion |
| `tests/unit/test_decision_node_retry.py` | New | Unit tests for DecisionNode classification retry |
| `tests/unit/test_monitor_hook.py` | New | Unit tests for monitor hook behavior |
| `tests/integration/test_retry_integration.py` | New | Integration tests for retry through the loop |

## Data Model Changes

```python
# NodeMonitor Protocol in tinycua/config/types.py
@runtime_checkable
class NodeMonitor(Protocol):
    def on_before_node_call(self, node_id: str, session_id: str, attempt: int,
                            messages: list[dict], resolved_tools: list) -> str | None: ...
    def on_after_node_call(self, node_id: str, session_id: str, attempt: int,
                           result: LLMResult, validation_result: ValidationResult) -> str | None: ...
    def on_retry_exhausted(self, node_id: str, session_id: str,
                           error: ValidationError, attempts: int) -> str | None: ...

@runtime_checkable
class AgentMonitor(Protocol):
    def on_before_node_call(self, node_id: str, session_id: str, attempt: int,
                            messages: list[dict], resolved_tools: list) -> str | None: ...
    def on_after_node_call(self, node_id: str, session_id: str, attempt: int,
                           result: LLMResult, validation_result: ValidationResult) -> str | None: ...
    def on_retry_exhausted(self, node_id: str, session_id: str,
                           error: ValidationError, attempts: int) -> str | None: ...

# StreamEvent — base event dict yielded during streaming
StreamEvent:
    type: str                    # "node.started", "node.completed", "response.output_text.delta", etc.
    node_id: str | None          # ID of the node producing this event
    node_type: str | None        # "ProcessNode", "DecisionNode", etc.
    timestamp: float             # time.time() when event was created
    metadata: dict               # additional context (attempt, route_label, etc.)

# LifecycleEvent — node boundary events
LifecycleEvent(StreamEvent):
    type: Literal["node.started", "node.llm_call", "node.completed", "node.error", "node.retry"]
    attempt: int                 # current attempt number (1-based)
    content: str | None          # final content for completed/error events
    finish_reason: str | None    # "completed", "error", "retry", "empty"

# TranscriptRecord — serializable event for WildClawBench export
TranscriptRecord:
    event: StreamEvent           # the original event
    run_id: str                  # unique run identifier
    session_id: str              # root session ID
    sequence: int                # monotonically increasing sequence number
```

## API Changes

### Modified Endpoints

| Component | Change | Impact |
|-----------|--------|--------|
| `NodeConfigBase` | Added `monitor: NodeMonitor \| None = None` | Backwards compatible (default None) |
| `TinyCUALoop.__init__` | Added `agent_monitor: AgentMonitor \| None = None` | Backwards compatible (default None) |
| `ProcessNode.__call__` | Now wires `retry_continuation_builder` and calls monitor hooks | Backwards compatible (behavioral change only) |
| `DecisionNode.__call__` | Now validates classification and retries | Backwards compatible (behavioral change) |
| `TinyCUALoop._run_stream()` | Emit lifecycle events, apply NodeStreamPolicy filtering, enrich with metadata | Backwards compatible (streaming behavior enhanced) |

### New Functions

| Function | Description |
|----------|-------------|
| `make_lifecycle_event()` | Factory for creating lifecycle event dicts with standard fields |
| `enrich_stream_event()` | Add node metadata to existing stream event dict |

## Dependencies

### External Dependencies

- [ ] No new external dependencies

### Internal Dependencies

- [ ] Depends on existing `NodeRetryPolicy` (Milestone 1.2) — already implemented
- [ ] Depends on existing `validate_output()` (Milestone 1.5) — already implemented
- [ ] Depends on existing `build_retry_continuation()` (Milestone 1.5) — already implemented
- [ ] Depends on `PropagationRule.failure` for `record_failure` propagation — defined in existing codebase (`tinycua/loops/propagation.py`)
- [x] Depends on existing `NodeStreamPolicy` (already implemented in `node_config.py`)
- [x] Depends on existing `BaseLoop` SDK contract (preserved, no changes)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Monitor hook overhead slows node execution | Low | Hooks are optional and lightweight; `_safe_call` catches exceptions fast |
| `record_failure` propagation rule not defined for some nodes | Medium | Default to no propagation; nodes that need failure propagation configure `PropagationRule.failure` |
| DecisionNode retry loop adds latency for invalid classifications | Low | Classification retry is bounded by `max_attempts`; invalid labels are rare |
| Custom `validation_fn` raises unexpected exceptions | Medium | Existing `validate_output()` already catches `ValueError`, `TypeError`, `KeyError`; additional exception types caught via `_safe_call` for monitor hooks |
| Stream event volume causes memory pressure | Medium | Events are yielded, not accumulated; consumer controls consumption |
| LLM endpoint doesn't support streaming | Low | Fallback to single-event yield after collecting full response |
| NodeStreamPolicy filtering breaks existing tests | High | Existing tests use `stream=False`; streaming tests already pass |
| WildClawBench transcript format mismatch | Medium | Design events to be schema-compatible with common JSONL formats |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-13*
