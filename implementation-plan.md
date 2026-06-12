# Implementation: Retry, Validation, and Monitor Hook

Completes the retry, validation, and monitor hook contracts for TinyCUA nodes. The `NodeRetryPolicy` dataclass and basic retry loop exist (Milestone 1.5), but custom continuation builders, full exhaustion handling, DecisionNode classification validation, and the transient `NodeMonitor`/`AgentMonitor` hook are not yet wired. This plan fills those gaps.

## Context

- **Spec Reference**: [./spec.md](./spec.md)
- **Design Reference**: [./design.md](./design.md)
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| - [ ] **None** — no external services needed | | | |

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
# Test file: src/tinycua/tests/integration/test_retry_integration.py
"""Integration tests for retry, validation, and monitor hook through TinyCUALoop."""


import pytest
from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node import NodeExecutionError, ProcessNode
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


class MockLLM:
    """Mock LLM returning a sequence of responses."""
    def __init__(self, responses):
        self._responses = list(responses)
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
```

### Key Test Scenarios

- [ ] **Scenario 1**: Node retries with custom `validation_fn` — first call rejected, second accepted
- [ ] **Scenario 2**: Retry exhaustion with `record_failure` writes failure state to session
- [ ] **Scenario 3**: Retry exhaustion with `raise` raises `NodeExecutionError`
- [ ] **Scenario 4**: Monitor hook observes correct trigger points and arguments across retries
- [ ] **Edge case**: Monitor hook exception does not break node execution
- [ ] **Edge case**: Custom `retry_continuation_builder` produces retry message
- [ ] **Edge case**: `max_attempts=0` results in 1 attempt (no retry)

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for `validate_output()` with custom `validation_fn`
- [ ] Unit tests for `_build_retry_text()` with custom builder
- [ ] Unit tests for `_handle_exhaustion()` with all three policies
- [ ] Unit tests for `DecisionNode` classification validation and retry
- [ ] Unit tests for `NodeMonitor` hook trigger points and exception handling
- [ ] Unit tests for `AgentMonitor` delegation to `NodeMonitor`
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify monitor hooks do not write to `chat_history` or `session_context`
- [ ] Verify `record_failure` propagation works with configured `PropagationRule.failure`

### Performance Considerations

- [ ] Monitor hook overhead is negligible (optional, lightweight, exception-safe)

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

### Phase 2 — Monitor Hook

#### [NEW] `NodeMonitor` protocol in `src/tinycua/tinycua/config/types.py`

- **Define `NodeMonitor` Protocol**: With `on_before_node_call`, `on_after_node_call`, `on_retry_exhausted` methods matching the design spec.
- **Define `AgentMonitor` Protocol**: With the same method signatures, delegating to `NodeMonitor`.

#### [MODIFY] `src/tinycua/tinycua/config/node_config.py`

- **Add `monitor: NodeMonitor | None = None` field to `NodeConfigBase`**: Allows nodes to be configured with a monitor hook.

#### [MODIFY] `src/tinycua/tinycua/loops/node.py`

- **Add `_safe_call()` helper**: Exception-safe monitor hook caller that logs and swallows exceptions.
- **Wire monitor hooks into `ProcessNode.__call__()`**: Call `monitor.on_before_node_call()` before LLM call, `monitor.on_after_node_call()` after validation failure, `monitor.on_retry_exhausted()` before exhaustion handling.
- **Incorporate monitor continuations**: If a monitor hook returns a string, append it as an assistant-role continuation to the messages.

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Add `agent_monitor: AgentMonitor | None = None` field to `TinyCUALoop.__init__()`**: Loop-level monitor configuration.
- **Wire `agent_monitor` in `_execute_node()`**: Call `agent_monitor.on_before_node_call()` before LLM call and `agent_monitor.on_after_node_call()` after; delegate to node monitor if configured.

### Phase 3 — Tests

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
- Unit tests for `AgentMonitor` delegation to `NodeMonitor`

#### [NEW] `src/tinycua/tests/integration/test_retry_integration.py`

- Integration tests for retry through `ProcessNode.__call__()`
- Integration tests for monitor hook observing full cycle
- Integration tests for `DecisionNode` classification retry

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/config/types.py` | Modify | Add `NodeMonitor` and `AgentMonitor` protocols |
| `tinycua/config/node_config.py` | Modify | Add `monitor` field to `NodeConfigBase` |
| `tinycua/loops/node.py` | Modify | Wire `retry_continuation_builder`, exhaustion behavior, monitor hooks; add `_safe_call()`, `_handle_exhaustion()`, `_record_failure()`, `_call_failure_route()` |
| `tinycua/loops/tinycua_loop.py` | Modify | Accept optional `AgentMonitor`, wire in `_execute_node()` |
| `tests/unit/test_retry_validation.py` | New | Unit tests for retry, validation, exhaustion |
| `tests/unit/test_decision_node_retry.py` | New | Unit tests for DecisionNode classification retry |
| `tests/unit/test_monitor_hook.py` | New | Unit tests for monitor hook behavior |
| `tests/integration/test_retry_integration.py` | New | Integration tests for retry through the loop |

## Data Model Changes

```python
# New protocol in tinycua/config/types.py
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
```

## API Changes

### Modified Endpoints

| Component | Change | Impact |
|-----------|--------|--------|
| `NodeConfigBase` | Added `monitor: NodeMonitor \| None = None` | Backwards compatible (default None) |
| `TinyCUALoop.__init__` | Added `agent_monitor: AgentMonitor \| None = None` | Backwards compatible (default None) |
| `ProcessNode.__call__` | Now wires `retry_continuation_builder` and calls monitor hooks | Backwards compatible (behavioral change only) |
| `DecisionNode.__call__` | Now validates classification and retries | Backwards compatible (behavioral change) |

## Dependencies

### External Dependencies

- [ ] No new external dependencies

### Internal Dependencies

- [ ] Depends on existing `NodeRetryPolicy` (Milestone 1.2) — already implemented
- [ ] Depends on existing `validate_output()` (Milestone 1.5) — already implemented
- [ ] Depends on existing `build_retry_continuation()` (Milestone 1.5) — already implemented
- [ ] Depends on `PropagationRule.failure` for `record_failure` propagation — already defined in design

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Monitor hook overhead slows node execution | Low | Hooks are optional and lightweight; `_safe_call` catches exceptions fast |
| `record_failure` propagation rule not defined for some nodes | Medium | Default to no propagation; nodes that need failure propagation configure `PropagationRule.failure` |
| DecisionNode retry loop adds latency for invalid classifications | Low | Classification retry is bounded by `max_attempts`; invalid labels are rare |
| Custom `validation_fn` raises unexpected exceptions | Medium | Existing `validate_output()` already catches `ValueError`, `TypeError`, `KeyError`; additional exception types caught via `_safe_call` for monitor hooks |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-13*
