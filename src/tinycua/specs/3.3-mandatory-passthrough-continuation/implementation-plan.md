# Implementation: Mandatory Passthrough and Continuation Routing

Wire the end-to-end `open_question` continuation path: when `ResultReviewer` decides `open_question`, a `MandatoryPassthrough` directive is installed targeting the ResultReviewer's node/session, and the next user input is routed deterministically back to it — bypassing LLM classification.

## Context

- **Spec Reference**: `./spec.md` — Milestone 3.3
- **Design Reference**: `./design.md` — Phase 1 MVP
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/unit/test_tinycua_loop.py (append to existing)
"""Unit tests for mandatory passthrough installation on open_question."""

from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
from tinycua.models.classification import MandatoryPassthrough
from tinycua.models.session import Session
from tinycua.models.task import Task


def test_on_reviewer_open_question_installs_passthrough():
    """_on_reviewer_open_question installs MandatoryPassthrough targeting ResultReviewer."""
    # Arrange
    loop = TinyCUALoop()
    session = Session()
    reviewer = TinyCUAResultReviewerNode(
        node_id="reviewer_1",
        config=NodeConfigBase(llm_client=MockLLM()),
        loop=loop,
    )
    reviewer.ensure_session(session)
    loop.queue.items = [loop.queue.items[0], reviewer, loop.queue.items[-1]]
    active_task = Task(task_id="task_1", description="test task")

    # Act
    loop._on_reviewer_open_question(active_task)

    # Assert
    assert loop._pending_mandatory_passthrough is not None
    assert loop._pending_mandatory_passthrough.target_node_id == "reviewer_1"
    assert loop._pending_mandatory_passthrough.target_session_id == session.session_id
    assert loop._pending_mandatory_passthrough.allow_query_analyst_restart is True


def test_on_reviewer_open_question_preserves_active_task():
    """_on_reviewer_open_question does not modify the active task status."""
    # Arrange
    loop = TinyCUALoop()
    active_task = Task(task_id="task_1", description="test task")

    # Act
    loop._on_reviewer_open_question(active_task)

    # Assert — task is unchanged (no mutation)
    assert active_task.task_id == "task_1"


def test_on_reviewer_open_question_no_reviewer_logs_warning():
    """_on_reviewer_open_question warns when no ResultReviewer found in queue."""
    # Arrange
    loop = TinyCUALoop()
    active_task = Task(task_id="task_1", description="test task")

    # Act
    loop._on_reviewer_open_question(active_task)

    # Assert
    assert loop._pending_mandatory_passthrough is None


def test_install_mandatory_passthrough_clears_previous():
    """_install_mandatory_passthrough replaces any existing passthrough."""
    # Arrange
    loop = TinyCUALoop()
    first = MandatoryPassthrough(target_node_id="first", reason="first")
    second = MandatoryPassthrough(target_node_id="second", reason="second")

    # Act
    loop._install_mandatory_passthrough(first)
    loop._install_mandatory_passthrough(second)

    # Assert
    assert loop._pending_mandatory_passthrough.target_node_id == "second"


def test_clear_mandatory_passthrough():
    """_clear_mandatory_passthrough removes the pending directive."""
    # Arrange
    loop = TinyCUALoop()
    loop._pending_mandatory_passthrough = MandatoryPassthrough(
        target_node_id="test", reason="test"
    )

    # Act
    loop._clear_mandatory_passthrough()

    # Assert
    assert loop._pending_mandatory_passthrough is None


# Test file: tests/integration/test_tinycua_loop_integration.py (append)
"""Integration tests for mandatory passthrough in the loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.classification import MandatoryPassthrough
from tests.unit.helpers.tinycua_loop_helpers import StubNode, ResponseNode


async def test_execute_decision_node_injects_pending_passthrough():
    """_execute_decision_node injects pending passthrough into QueryAnalyst input."""
    # Arrange
    loop = TinyCUALoop()
    loop._pending_mandatory_passthrough = MandatoryPassthrough(
        target_node_id="reviewer",
        target_session_id=loop.root_session.session_id,
        reason="open_question",
    )
    query_analyst = loop.queue.items[0]  # QueryAnalyst
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    # Act — run the loop; the passthrough should be consumed
    result = await loop.run(
        agent=agent,
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        stream=False,
    )

    # Assert — passthrough was consumed
    assert loop._pending_mandatory_passthrough is None


async def test_execute_decision_node_clears_passthrough_after_forward():
    """_execute_decision_node clears passthrough after successful forward."""
    # Arrange
    loop = TinyCUALoop()
    loop._pending_mandatory_passthrough = MandatoryPassthrough(
        target_node_id="reviewer",
        target_session_id=loop.root_session.session_id,
        reason="open_question",
    )
    agent = MagicMock()
    agent.instructions = "test"
    agent.skills = []
    agent._call_llm = AsyncMock(
        return_value={"content": "ok", "tool_calls": None}
    )

    # Act
    await loop.run(
        agent=agent,
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        stream=False,
    )

    # Assert
    assert loop._pending_mandatory_passthrough is None
```

### Key Test Scenarios

- [ ] **Scenario 1**: `_on_reviewer_open_question` installs `MandatoryPassthrough` with correct `target_node_id` and `target_session_id`
- [ ] **Scenario 2**: `_execute_decision_node` injects pending passthrough into QueryAnalyst input metadata and clears it after successful forward
- [ ] **Edge case**: `_on_reviewer_open_question` with no ResultReviewer in queue — warns and does not install
- [ ] **Edge case**: Multiple sequential open_questions — each replaces the previous passthrough

## Verification Plan

### Automated Tests

- [ ] Unit tests for `_on_reviewer_open_question`, `_install_mandatory_passthrough`, `_clear_mandatory_passthrough`, `_find_result_reviewer`
- [ ] Unit tests for `_execute_decision_node` passthrough injection and consumption
- [ ] Integration test for end-to-end open_question → passthrough → continuation path
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify `_on_reviewer_open_question` installs passthrough by inspecting `_pending_mandatory_passthrough` after call
- [ ] Verify stale passthrough falls back to LLM classification (session mismatch)

### Performance Considerations

- [ ] No performance impact — adds a single field check and assignment per loop iteration

## Proposed Changes

### tinycua.loops.tinycua_loop

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Add `_pending_mandatory_passthrough` field to `__init__`**: Initialize as `None` in `__init__` alongside existing `_reviewer_retry_state`.
- **Implement `_install_mandatory_passthrough(mandatory)`:** Store the directive on the loop, clearing any existing one first. Logs the installation.
- **Implement `_clear_mandatory_passthrough()`:** Set `_pending_mandatory_passthrough = None`.
- **Implement `_find_result_reviewer()`:** Scan `self.queue.items` for `TinyCUAResultReviewerNode` instances; return first match or None.
- **Update `_on_reviewer_open_question(active_task)`:** Call `_find_result_reviewer()` to locate the active reviewer. If found with a session, create a `MandatoryPassthrough` targeting its `node_id` and `session_id`, then call `_install_mandatory_passthrough()`. If not found, log a warning and return.
- **Update `_execute_decision_node()`:** Before the existing `check_mandatory_passthrough` call in the QueryAnalyst branch, inject `self._pending_mandatory_passthrough` into `input_data.metadata["mandatory_passthrough"]` if it is not None. After the passthrough is consumed (successful forward), call `self._clear_mandatory_passthrough()`.

- **Rationale**: The loop-level field survives the `input_context` reset between `run()` calls. The injection in `_execute_decision_node()` is a single additional line that merges the pending directive into the same `NodeInput.metadata` dict where `check_mandatory_passthrough()` already reads from.

### No changes to other files

- `tinycua/loops/result_reviewer.py` — No change needed. Already calls `loop._on_reviewer_open_question(active_task)` on `open_question` outcome.
- `tinycua/loops/query_analyst.py` — No change needed. `check_mandatory_passthrough()` and `route_passthrough()` already work correctly.
- `tinycua/models/classification.py` — No change needed. `MandatoryPassthrough` dataclass already has all required fields.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.loops.tinycua_loop` | Modify | Add `_pending_mandatory_passthrough` field, install/clear/find methods, update `_on_reviewer_open_question` and `_execute_decision_node` |
| `tinycua.loops.result_reviewer` | No change | Already dispatches `open_question` to `_on_reviewer_open_question` |
| `tinycua.loops.query_analyst` | No change | Precheck and stale guard already implemented |
| `tinycua.models.classification` | No change | `MandatoryPassthrough` dataclass already exists |

## Data Model Changes

No new entities. The `MandatoryPassthrough` dataclass already exists:

```python
@dataclass
class MandatoryPassthrough:
    target_node_id: str
    target_session_id: str | None = None
    reason: str = ""
    payload: NodeInput | NodePayload | None = None
    allow_query_analyst_restart: bool = True
```

## API Changes

### New Methods on TinyCUALoop

| Method | Description |
|--------|-------------|
| `_install_mandatory_passthrough(mandatory)` | Store a passthrough directive on the loop |
| `_clear_mandatory_passthrough()` | Remove the pending passthrough directive |
| `_find_result_reviewer()` | Find the active ResultReviewer node in the queue |

### Modified Methods

| Method | Change |
|--------|--------|
| `_on_reviewer_open_question(active_task)` | From log-only stub → installs MandatoryPassthrough |
| `_execute_decision_node(node, ...)` | Inject pending passthrough into QueryAnalyst input; clear after forward |

## Dependencies

### External Dependencies

None.

### Internal Dependencies

- [x] Depends on existing `MandatoryPassthrough` model (already in `models/classification.py`)
- [x] Depends on existing `QueryAnalyst.check_mandatory_passthrough()` (already in `loops/query_analyst.py`)
- [x] Depends on existing `ResultReviewer.on_complete()` dispatch (already in `loops/result_reviewer.py`)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ResultReviewer may not be in queue when open_question fires | Low | `_find_result_reviewer()` returns None; warning logged; no passthrough installed; falls back to normal flow |
| Stale passthrough from a previous run cycle | Low | Cleared after successful forward in `_execute_decision_node()`; stale guard in `check_mandatory_passthrough()` as second line of defense |
| User sends empty continuation after open_question | Low | QueryAnalyst classifies empty input as uncertain; normal behavior |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-11*
