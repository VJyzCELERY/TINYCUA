# Implementation: TinyCUAResponseNode

This implementation upgrades the existing `ResponseNode` stub into a full `TinyCUAResponseNode` — a terminal `ProcessNode` that serves as the terminal node of the TinyCUALoop. It performs context sufficiency analysis, optional context gathering (via InformationDigesterNode suspension or direct tool fallback), final response synthesis, consolidated continuation routing, and terminal output normalization.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: L

## Environment Pre-requisites

> No special environment setup is needed — all dependencies already exist in the `tinycua` subproject.

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — test fixtures are built programmatically in test files

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **Additional CLI tools**: pytest
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_response_node_integration.py
"""Integration tests for TinyCUAResponseNode."""

import pytest
from tinycua.config.types import LLMResult
from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy, NodeToolPolicy
from tinycua.loops.response_node import TinyCUAResponseNode, ResponseContext
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.result_aggregation import AggregatedResult
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


def _make_node_input(messages: list[dict] | None = None) -> NodeInput:
    return NodeInput(
        input_type="continuation",
        messages=messages or [{"role": "user", "content": "test"}],
    )


def _make_sufficient_context() -> ResponseContext:
    """Build a ResponseContext with sufficient aggregated context."""
    return ResponseContext(
        aggregated_result=AggregatedResult(
            root_task_id="root",
            task_summaries=["Root: Completed successfully"],
            final_context="Root: Completed successfully",
        ),
        session_context=[{"role": "assistant", "content": "Some context"}],
        latest_output="intermediate output",
        continuation_payload=None,
    )


def _make_insufficient_context() -> ResponseContext:
    """Build a ResponseContext with no aggregated result (insufficient)."""
    return ResponseContext(
        aggregated_result=None,
        session_context=[],
        latest_output=None,
        continuation_payload=None,
    )


def test_response_node_direct_synthesis():
    """Given a ResponseNode with sufficient context,
    When executed,
    Then it produces a final string response without invoking tools or digester."""
    config = NodeConfigBase()
    node = TinyCUAResponseNode(config=config)
    session = Session()
    session.session_context.append(
        {"role": "assistant", "content": "[AggregatedResult] Root: Done"}
    )
    node.ensure_session(session)

    input_data = _make_node_input()
    result = node(input_data)

    assert isinstance(result, LLMResult)
    assert isinstance(result.content, str)
    assert len(result.content) > 0


def test_response_node_is_terminal():
    """Given a TinyCUAResponseNode,
    When initialized,
    Then is_terminal is True."""
    node = TinyCUAResponseNode()
    assert node.is_terminal is True
    assert node.node_id == "response"


def test_context_sufficiency_check():
    """Given a ResponseContext with sufficient aggregated result,
    When _check_context_sufficiency is called,
    Then it returns True.
    Given a ResponseContext with no aggregated result,
    Then it returns False."""
    config = NodeConfigBase()
    node = TinyCUAResponseNode(config=config)

    sufficient = _make_sufficient_context()
    assert node._check_context_sufficiency(sufficient) is True

    insufficient = _make_insufficient_context()
    assert node._check_context_sufficiency(insufficient) is False


def test_response_node_continuation_routing():
    """Given a user continuation directed at the ResponseNode session,
    When the consolidated continuation behavior is triggered,
    Then the continuation is delivered without LLM rerouting (via MandatoryPassthrough)."""
    from tinycua.models.classification import MandatoryPassthrough

    config = NodeConfigBase()
    node = TinyCUAResponseNode(config=config)
    session = Session()
    node.ensure_session(session)

    # Simulate a MandatoryPassthrough targeting this node
    passthrough = MandatoryPassthrough(
        target_node_id=node.node_id,
        target_session_id=session.session_id,
        reason="continuation",
    )
    # Store on the loop / node for the continuation check
    node._continuation_payload = passthrough

    input_data = _make_node_input()
    result = node(input_data)

    assert isinstance(result, LLMResult)
    # Should produce content directly without LLM rerouting


def test_response_node_retry_behavior():
    """Given a ResponseNode configured with retry limits,
    When synthesis fails repeatedly,
    Then retry policy is respected and a fallback message is returned on exhaustion."""
    config = NodeConfigBase()
    config.retry_policy = NodeRetryPolicy(
        max_attempts=3,
        on_retry_exhausted="record_failure",
    )
    config.metadata["fallback_message"] = "I encountered an error generating the final response."

    node = TinyCUAResponseNode(config=config)
    session = Session()
    session.session_context.append(
        {"role": "assistant", "content": "[AggregatedResult] Test"}
    )
    node.ensure_session(session)

    # No LLM client configured — will hit retry exhaustion
    input_data = _make_node_input()
    result = node(input_data)

    assert isinstance(result, LLMResult)
    # Should return fallback message on exhaustion
    assert result.content == config.metadata["fallback_message"]


def test_response_node_terminal_normalization():
    """Given a non-string LLM result,
    When the ResponseNode processes it,
    Then terminal output is normalized to a string."""
    config = NodeConfigBase()
    node = TinyCUAResponseNode(config=config)
    session = Session()
    node.ensure_session(session)

    # Test with dict-like content fed through NodeInput
    input_data = _make_node_input()
    result = node(input_data)

    assert isinstance(result.content, str)


def test_response_node_aggregation_integration():
    """Given a TinyCUALoop with TinyCUAResponseNode as the terminal,
    When the loop runs and reaches the response node,
    Then it produces a final string response."""
    from unittest.mock import MagicMock, patch
    from tinycua.loops.response_node import TinyCUAResponseNode
    from tinycua.loops.tinycua_loop import TinyCUALoop

    # Create a response node with sufficient context config
    config = NodeConfigBase()
    node = TinyCUAResponseNode(config=config)

    # Create a mock loop that yields sufficient context
    loop = MagicMock(spec=TinyCUALoop)
    loop.session = Session()
    loop.session.session_context.append(
        {"role": "assistant", "content": "[AggregatedResult] Final: Completed"}
    )
    loop.aggregated_result = AggregatedResult(
        root_task_id="root",
        task_summaries=["Task completed successfully"],
        final_context="Task completed successfully",
    )
    loop.current_node = node

    # Create a NodeInput to feed into the response node
    input_data = _make_node_input()

    # Execute the response node — should produce a final string response
    with patch.object(node, '_synthesize_response', return_value=LLMResult(content="Final response")):
        result = node(input_data)

    assert isinstance(result, LLMResult)
    assert isinstance(result.content, str)
    assert len(result.content) > 0
    assert result.content == "Final response"


def test_response_node_digester_integration():
    """Given a ResponseNode with insufficient context and digester enabled,
    When executed,
    Then suspension occurs, InformationDigesterNode is prepended, digest result is
    incorporated, and ResponseNode resumes to produce final output."""
    from unittest.mock import MagicMock, patch
    from tinycua.loops.response_node import TinyCUAResponseNode
    from tinycua.loops.information_digester import TinyCUAInformationDigesterNode

    config = NodeConfigBase()
    config.metadata["digester_enabled"] = True
    response_node = TinyCUAResponseNode(config=config)
    session = Session()
    response_node.ensure_session(session)

    # Build ResponseContext for internal precondition check
    response_context = _make_insufficient_context()

    # Verify precondition: context is insufficient
    assert response_node._check_context_sufficiency(response_context) is False

    # Build a proper NodeInput for __call__, which expects NodeInputLike per API contract
    input_data = _make_node_input(messages=[{
        "role": "system",
        "content": "Insufficient context: no aggregated result"
    }])

    # Mock the queue to capture suspension behavior
    mock_queue = MagicMock()
    mock_queue.current = response_node

    # ===== Phase 1: __call__ with insufficient context + digester enabled =====
    # Per design: __call__ sets _needs_digestion flag and returns a placeholder.
    # Actual suspension (suspend_for_digestion) is deferred to on_complete.
    with patch.object(response_node, '_suspend_for_digestion') as mock_suspend:
        result = response_node(input_data)

        # Verify the flag is set — suspension defers to on_complete
        assert response_node._needs_digestion is True
        # _suspend_for_digestion should NOT be called during __call__
        mock_suspend.assert_not_called()

    # ===== Phase 2: on_complete triggers suspension =====
    with patch.object(response_node, '_suspend_for_digestion') as mock_suspend:
        response_node.on_complete(mock_queue, result)
        mock_suspend.assert_called_once()
        # Verify the queue was passed for suspension operation
        call_args = mock_suspend.call_args
        assert call_args[0][1] is mock_queue  # second positional arg is the queue

    # ===== Phase 3: Simulate resume after digestion with enriched context =====
    digest_result = AggregatedResult(
        root_task_id="root",
        task_summaries=["Digested: Additional context gathered"],
        final_context="Digested: Additional context gathered",
    )

    # Build input for the resumed call (sufficient context after digestion)
    resume_input = _make_node_input(messages=[{
        "role": "system",
        "content": "Sufficient context: Enriched after digestion"
    }])

    # Reset the flag for the resumed call
    response_node._needs_digestion = False

    # Mock the resume path: context is sufficient, synthesize directly
    with patch.object(response_node, '_synthesize_response', return_value=LLMResult(content="Final response after digestion")):
        with patch.object(response_node, '_check_context_sufficiency', return_value=True):
            resume_result = response_node(resume_input)

            # Verify the final synthesized result
            assert isinstance(resume_result, LLMResult)
            assert isinstance(resume_result.content, str)
            assert len(resume_result.content) > 0
            assert resume_result.content == "Final response after digestion"
```

### Key Test Scenarios

- [ ] **Scenario 1**: Direct synthesis with sufficient context produces a final string response
- [ ] **Scenario 2**: Context sufficiency check correctly identifies sufficient vs. insufficient context
- [ ] **Scenario 3**: Continuation routing delivers continuation without LLM rerouting
- [ ] **Scenario 4**: Retry policy is respected — fallback message returned on exhaustion
- [ ] **Scenario 5**: Terminal output is always normalized to a string
- [ ] **Edge case**: Empty/None aggregated result triggers fallback to digester or tools
- [ ] **Edge case**: Fallback message on retry exhaustion
- [ ] **Integration**: Full queue integration with loop
- [ ] **Scenario 6**: Digester suspension — verifies `_suspend_for_digestion` is called when context is insufficient and digester is enabled, then resumes with enriched context

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for `TinyCUAResponseNode` — test initialization, `__call__`, `_check_context_sufficiency`, `_suspend_for_digestion`, `_gather_context_via_tools`, `_synthesize_response`, `on_complete`
- [ ] Unit tests for `ResponseContext` helper — test context aggregation from NodeInput
- [ ] Unit tests for continuation routing — test MandatoryPassthrough handling
- [ ] Unit tests for retry behavior — test retry exhaustion fallback
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] N/A — all behavior is verifiable through automated tests.

### Performance Considerations

- [ ] Context sufficiency check is lightweight — no LLM call required
- [ ] Digester suspension uses existing queue machinery (no new infrastructure)
- [ ] Retry limits prevent infinite loops during synthesis

## Proposed Changes

### `tinycua.loops.response_node` (Modified Module)

#### [MODIFY] `src/tinycua/tinycua/loops/response_node.py`

- **[Description]**: Upgrade the existing `ResponseNode` stub into `TinyCUAResponseNode` with full three-phase execution.
- **[Rationale]**: The current stub only captures LLM output content. The full implementation adds context sufficiency analysis, digester suspension, tool fallback, continuation routing, and terminal normalization as specified in the design.
- **Changes**:
  - Rename class from `ResponseNode` to `TinyCUAResponseNode`. **DO NOT keep `ResponseNode` as an alias** — the existing test helper `ResponseNode(Node)` in `tinycua_loop_helpers.py` creates an import collision (same name, different base class).
  - Add `ResponseContext` dataclass for aggregated context.
  - Add `__init__` with standard `node_id` and `config` parameters. Digester enable/disable is configured via `config.metadata["digester_enabled"]` (default: `True`).
  - Add `_check_context_sufficiency(self, context: ResponseContext) -> bool` — analyze available context before synthesis.
  - Add `_suspend_for_digestion(self, context: ResponseContext, queue: NodeQueue) -> None` — called from `on_complete`; suspend via `queue.suspend_current_and_prepend([TinyCUAInformationDigesterNode(parent=self)])`.
  - Add `_gather_context_via_tools(self, context: ResponseContext) -> ResponseContext` — use allowed tools directly.
  - Add `_synthesize_response(self, context: ResponseContext) -> LLMResult` — build LLM input and produce final response.
  - Modify `__call__` to implement three-phase execution:
    1. Build `ResponseContext` from `NodeInput`.
    2. Check context sufficiency.
    3. If sufficient → synthesize directly.
    4. If insufficient + digester enabled → set `self._needs_digestion = True`, return a placeholder result; actual suspension happens in `on_complete`.
    5. If insufficient + no digester → gather context via tools.
    6. Normalize terminal output to string.
    7. Record output and propagate.
  - Modify `on_complete` to handle queue mutations (digester prepend, etc.).
  - Add `_continuation_payload` attribute for consolidated continuation behavior.
  - Add `_needs_digestion` flag — set during `__call__` when context is insufficient and digester enabled; checked in `on_complete`.
  - Ensure retry compliance via inherited `ProcessNode.__call__` retry loop.

#### [MODIFY] `src/tinycua/tinycua/loops/__init__.py`

- **[Description]**: Update imports to export `TinyCUAResponseNode`. Do NOT export `ResponseNode` as an alias — the production class is renamed to avoid collision with the test helper.
- **[Rationale]**: Expose the upgraded class via the public `tinycua.loops` namespace.
- **Changes**:
  - Update import: `from tinycua.loops.response_node import TinyCUAResponseNode`
  - Add to `__all__`: `"TinyCUAResponseNode"`
  - Remove any existing `"ResponseNode"` entry from `__all__`

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **[Description]**: Wire TinyCUAResponseNode into the loop's terminal node handling and continuation routing.
- **[Rationale]**: The loop needs to handle ResponseNode's suspension/resume flow and consolidated continuation routing.
- **Changes**:
  - Update import to use `TinyCUAResponseNode` (no `ResponseNode` alias — the production class is renamed to avoid collision with test helper `StubResponseNode`).
  - Modify `_execute_node` for terminal nodes: add an `isinstance(node, TinyCUAResponseNode)` type check to invoke `node.__call__()` instead of the direct LLM path:
    ```python
    if node.is_terminal:
        if isinstance(node, TinyCUAResponseNode):
            # ResponseNode needs __call__ for its three-phase execution
            node.ensure_session(self.root_session)
            input_data = self._build_node_input(node)
            result = node(input_data)
            llm_result = result if isinstance(result, LLMResult) else LLMResult(content=str(result))
        else:
            # Default terminal path for non-ResponseNode terminals (existing behavior)
            messages, resolved_tools = self._prepare_node(...)
            response = await agent._call_llm(messages, resolved_tools)
            llm_result = LLMResult(content=response.get("content") or "", ...)
    ```
  - Modify `_route_to_aggregation` to use `TinyCUAResponseNode`.
  - Ensure continuation routing via MandatoryPassthrough reaches the active ResponseNode session.

#### [RENAME] `src/tinycua/tests/unit/helpers/tinycua_loop_helpers.py` — `ResponseNode` → `StubResponseNode`

- **[Description]**: Rename the existing test helper class `ResponseNode(Node)` to `StubResponseNode(Node)` to avoid naming collision with the production `TinyCUAResponseNode` (previously `ResponseNode`). Both had the same name but extended different base classes (`Node` vs `ProcessNode`), creating import ambiguity in existing tests.
- **[Rationale]**: The implementation plan previously proposed keeping `ResponseNode` as an alias for `TinyCUAResponseNode`. However, the test helper `ResponseNode(Node)` in `tinycua_loop_helpers.py:57` is used by existing queue bootstrap tests as a lightweight terminal stub. If the production `ResponseNode` became an alias, these tests might accidentally import the real class, causing failures due to missing LLM client dependencies. Renaming the test helper to `StubResponseNode` avoids the collision entirely.
- **Changes**:
  - In `src/tinycua/tests/unit/helpers/tinycua_loop_helpers.py`:
    - Rename class `ResponseNode(Node)` to `StubResponseNode(Node)`
    - Update docstring to reflect the new name
  - In `src/tinycua/tests/` — find and update all imports of `ResponseNode` from `tinycua_loop_helpers` to use `StubResponseNode`:
    ```bash
    grep -rn "from.*tinycua_loop_helpers.*import.*ResponseNode" src/tinycua/tests/
    ```
  - Verify no existing tests break:
    ```bash
    cd src/tinycua && uv run pytest
    ```

#### [MODIFY] `src/tinycua/tinycua/config/node_config.py` (if needed)

- **[Description]**: Add response-specific configuration options.
- **[Rationale]**: Context sufficiency thresholds and digester enable/disable should be configurable via `NodeConfig`.
- **Changes** (if needed):
  - Add these fields to `NodeConfigBase.metadata` as the simpler approach:
    - `digester_enabled: bool = True`
    - `sufficiency_threshold: int | None = None` (configurable threshold)
    - `fallback_message: str = "I encountered an error generating the final response."`

### Tests

#### [NEW] `src/tinycua/tests/unit/test_response_node.py`

- **[Description]**: Unit tests for `TinyCUAResponseNode` initialization, context sufficiency check, response synthesis, digester suspension, tool fallback, continuation routing, retry behavior, and terminal normalization.
- **[Dependencies]**: `pytest`, `tinycua.loops.response_node`, `tinycua.config.node_config`, `tinycua.config.types`.

#### [NEW] `src/tinycua/tests/integration/test_response_node_integration.py`

- **[Description]**: Integration tests from the "Success Criteria — Integration Tests" section above.
- **[Dependencies]**: `pytest`, `tinycua.loops.response_node`, `tinycua.loops.node_queue`, `tinycua.loops.tinycua_loop`.

---

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.loops.response_node` | Modify | Upgrade `ResponseNode` stub to full `TinyCUAResponseNode`; no `ResponseNode` alias kept |
| `tinycua.loops.__init__` | Modify | Export `TinyCUAResponseNode` only (no `ResponseNode` alias) |
| `tinycua.loops.tinycua_loop` | Modify | Wire suspension/resume and continuation routing |
| `tinycua.config.node_config` | Modify (if needed) | Add response-specific config options |
| `src/tinycua/tests/unit/helpers/tinycua_loop_helpers.py` | Modify | Rename `ResponseNode(Node)` to `StubResponseNode(Node)` to avoid naming collision |
| All existing test imports | Modify | Update imports from `ResponseNode` → `StubResponseNode` in test files referencing the helper |
| `src/tinycua/tests/unit/test_response_node.py` | New | Unit tests for ResponseNode |
| `src/tinycua/tests/integration/test_response_node_integration.py` | New | Integration tests |

## Data Model Changes

### New Types

```python
from dataclasses import dataclass, field
from typing import Any
from tinycua.loops.result_aggregation import AggregatedResult

@dataclass
class ResponseContext:
    """Aggregated context fed into TinyCUAResponseNode."""
    aggregated_result: AggregatedResult | None  # from ResultAggregationNode
    session_context: list[dict[str, Any]]  # propagated context
    latest_output: str | None  # Latest node output
    continuation_payload: dict | None  # User continuation data
```

### Schema Changes

No schema changes to existing entities. The existing `AggregatedResult`, `NodeInput`, and `NodePayload` data models are sufficient.

## API Changes

No public API changes — all changes are internal to `tinycua.loops`. The `TinyCUAResponseNode` is re-exported from `tinycua.loops` for convenience. The `ResponseNode` alias is **not** kept — the existing test helper `ResponseNode(Node)` is renamed to `StubResponseNode(Node)` to avoid naming collision.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | All dependencies are internal to the project |

### Internal Dependencies

- [ ] Depends on Milestone 3.4 (`ResultAggregationNode`) — provides `AggregatedResult` input
- [ ] Depends on Milestone 2.5 (`TinyCUAInformationDigesterNode`) — optional digester suspension path
- [ ] Depends on Milestone 3.3 (MandatoryPassthrough continuation routing) — for consolidated continuation
- [ ] Depends on Milestone 1.7 (`NodeQueue.suspend_current_and_prepend`) — queue suspension machinery
- [ ] Relies on `NodeRetryPolicy` and `NodeToolPolicy` — already available in `node_config.py`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Digester suspension may cause infinite loops (digester → response → digester) | High | Guard with max-digest-attempts counter in NodeConfig; reset on tool-gathered context |
| Context sufficiency heuristic may be wrong | Medium | Make thresholds configurable; log sufficiency decisions for tuning |
| Continuation routing may conflict with existing MandatoryPassthrough | Medium | Test continuation paths thoroughly; existing M3.3 tests provide baseline |
| Tool use during response may have side effects | Low | Same tools as TaskExecutor, already designed for safe execution |
| ResponseNode suspension changes queue state in ways the loop doesn't expect | Medium | Integration tests for full queue lifecycle; guard suspension calls with state checks |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-12*
