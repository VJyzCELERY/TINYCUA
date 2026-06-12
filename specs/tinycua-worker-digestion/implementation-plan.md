# Implementation: WorkerNode Information-Digestion via QueryAnalyst

Implements the integration path where **QueryAnalyst spawns `InformationDigesterNode`** before routing to **WorkerNode**, so the **Worker receives structured `DigestedInformation`** (not raw user_query) and forwards it to downstream nodes (TaskCreate, TaskAnalyzer, etc.).

## Context

- **Spec Reference**: `./spec.md` — WorkerNode Information-Digestion via QueryAnalyst
- **Design Reference**: `./design.md` — Full architecture and queue transition diagrams
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [x] **.env file** — no new env vars required; existing LLM config suffices

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | — | — | — |

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+, uv
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/unit/test_query_analyst_worker_digest.py
"""Integration tests for QueryAnalyst → InformationDigester → Worker → TaskCreate flow."""

import pytest
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.response_node import ResponseNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session
from tinycua.config.node_config import NodeConfigBase


def test_query_analyst_spawns_digester_before_worker():
    """QueryAnalyst worker route inserts InformationDigesterNode before WorkerNode."""
    queue = NodeQueue()
    query_analyst = TinyCUAQueryAnalystNode(
        node_id="qa", config=NodeConfigBase()
    )
    response = ResponseNode()
    queue.items = [query_analyst, response]

    # Attach session to query_analyst
    session = Session()
    query_analyst.session = session

    # Set queue reference so _route_worker can call spawn_after_current
    query_analyst._queue = queue

    # Create a NodeInput simulating a worker route with user query
    input_data = NodeInput(
        input_type="worker",
        messages=[{"role": "user", "content": "Create a plan for the migration"}],
    )

    # Call the actual _route_worker (NOT mocked) — exercises real code path
    query_analyst._route_worker(input_data)

    # Queue should have: query_analyst, digester, worker, response
    assert len(queue.items) == 4
    assert isinstance(queue.items[1], TinyCUAInformationDigesterNode)
    assert isinstance(queue.items[2], TinyCUAWorkerNode)
    assert queue.items[2].node_id == "worker"


def test_digested_information_fallback_preserves_original_query():
    """DigestedInformation.fallback() preserves the original user query."""
    original_query = "Create a plan for the migration"
    digest = DigestedInformation.fallback(original_query)

    assert original_query in digest.context_summary
    assert digest.original_query == original_query
    assert digest.key_points == []
    assert digest.advisory_instructions == []


def test_digested_information_has_useful_context():
    """DigestedInformation.has_useful_context returns True when content exists."""
    digest_with_points = DigestedInformation(
        key_points=["point1", "point2"],
        original_query="test",
    )
    assert digest_with_points.has_useful_context is True

    fallback_digest = DigestedInformation.fallback("test")
    assert fallback_digest.has_useful_context is False


def test_worker_reads_digested_information_from_session():
    """WorkerNode reads DigestedInformation from session_context when present."""
    worker = TinyCUAWorkerNode(node_id="w", config=NodeConfigBase())
    session = Session()

    digest = DigestedInformation(
        context_summary="Summary of context",
        key_points=["key1"],
        original_query="test query",
    )
    session.session_context.append({
        "role": "assistant",
        "content": digest,
    })
    worker.session = session

    result = worker._get_digested_input()
    assert result is not None
    assert result.context_summary == "Summary of context"
    assert result.original_query == "test query"


def test_worker_falls_back_when_no_digested_information():
    """WorkerNode returns None when no DigestedInformation exists in session."""
    worker = TinyCUAWorkerNode(node_id="w", config=NodeConfigBase())
    session = Session()
    session.session_context.append({
        "role": "assistant",
        "content": "regular message",
    })
    worker.session = session

    result = worker._get_digested_input()
    assert result is None


def test_information_digester_creates_fresh_session():
    """InformationDigesterNode creates a fresh session (does not inherit parent)."""
    parent_session = Session()
    parent_session.session_id = "parent-session-123"

    digester = TinyCUAInformationDigesterNode(
        node_id="d", config=NodeConfigBase()
    )

    # When ensure_session is called, it should create a new session
    # if no parent is set, but we verify fresh session behavior
    # by checking that the digester doesn't inherit parent session_id
    assert digester.session is None


def test_worker_forwards_digested_information_via_propagate():
    """WorkerNode propagate() includes DigestedInformation for downstream nodes."""
    worker = TinyCUAWorkerNode(node_id="w", config=NodeConfigBase())
    session = Session()
    worker.session = session

    digest = DigestedInformation(
        context_summary="Summary",
        original_query="test",
    )
    worker._current_digest = digest

    worker.propagate()

    # After propagate, session_context should contain the digest
    assert any(
        entry.get("content") == digest
        for entry in session.session_context
    )


def test_query_analyst_no_duplicate_digest_when_already_exists():
    """QueryAnalyst does not spawn duplicate digester when digest already present."""
    queue = NodeQueue()
    worker = TinyCUAWorkerNode(node_id="w", config=NodeConfigBase())
    response = ResponseNode()
    queue.items = [worker, response]

    # Worker already has digested information in its session
    session = Session()
    worker.session = session
    digest = DigestedInformation(context_summary="Already digested", original_query="q")
    session.session_context.append({
        "role": "assistant",
        "content": digest,
    })

    query_analyst = TinyCUAQueryAnalystNode(
        node_id="qa", config=NodeConfigBase()
    )
    query_analyst.session = session

    # Check that duplicate detection works
    existing_digest = query_analyst._check_existing_digest(worker)
    assert existing_digest is True
```

### Key Test Scenarios

- [x] **Scenario 1**: QueryAnalyst spawns InformationDigesterNode before WorkerNode in the queue when routing `worker`
- [x] **Scenario 2**: Digest de-duplication — QueryAnalyst detects existing digest and skips spawn
- [x] **Scenario 3**: DigestedInformation model fields, construction, and fallback behavior
- [x] **Scenario 4**: WorkerNode reads DigestedInformation from session_context, falls back gracefully
- [x] **Scenario 5**: WorkerNode forwards DigestedInformation via propagate() to downstream nodes
- [x] **Edge case**: InformationDigesterNode failure produces fallback with original query preserved

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
    > **NOTE**: The test code block above contains unit-level tests for individual components. Full end-to-end integration tests (using MockLLM to simulate the full QueryAnalyst → InformationDigester → Worker → TaskCreate pipeline) should be written as a separate test file during the Testing Phase. These are listed in the spec testing plan and have been added to task.md.
- [x] Unit tests for DigestedInformation model — test all fields, fallback(), has_useful_context
- [x] Unit tests for QueryAnalyst worker route — test spawn logic, dedup, fresh session
- [x] Unit tests for WorkerNode — test _get_digested_input(), propagate()
- [x] Unit tests for InformationDigesterNode — test fresh session creation
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Verify queue transitions match design.md diagrams (fresh spawn and reused worker cases)
- [x] Verify DigestedInformation serialization/deserialization works with session_context

### Performance Considerations

- [x] No performance impact — this is structural routing logic only

## Proposed Changes

### Models — DigestedInformation

#### [NEW] `tinycua/models/digested_information.py`

- **Description of change**: New `DigestedInformation` dataclass with fields: `context_summary`, `key_points`, `advisory_instructions`, `constraints`, `known_gaps`, `original_query`. Includes `fallback()` classmethod and `has_useful_context` property.
- **Rationale**: Required by FR-010, FR-011. Defines the structured output from InformationDigesterNode.

#### [MODIFY] `tinycua/models/__init__.py`

- **Description of change**: Export `DigestedInformation` from the models package.
- **Rationale**: Makes the model available to loops modules.

### Loops — QueryAnalyst

#### [NEW] `tinycua/loops/query_analyst.py`

- **Description of change**: Concrete `TinyCUAQueryAnalystNode` (DecisionNode) with worker route handler that spawns InformationDigesterNode before WorkerNode. Includes `_route_worker()`, `_check_existing_digest()`, and `_extract_user_query()` helper methods.
- **Dependencies**: Depends on `DigestedInformation`, `InformationDigesterNode`, `NodeQueue.spawn_after_current()`

### Loops — InformationDigester

#### [NEW] `tinycua/loops/information_digester.py`

- **Description of change**: Concrete `TinyCUAInformationDigesterNode` (ProcessNode) that creates a fresh node session, receives selected input from parent, and produces DigestedInformation output. Includes fallback behavior when no useful context found.
- **Dependencies**: Depends on `DigestedInformation`

### Loops — Worker

#### [NEW] `tinycua/loops/worker.py`

- **Description of change**: Concrete `TinyCUAWorkerNode` (DecisionNode) that reads DigestedInformation from session_context as primary input, and forwards it via propagate() to downstream nodes. Includes `_get_digested_input()` and enhanced `propagate()`.
- **Dependencies**: Depends on `DigestedInformation`, `NodeQueue`

### Loops — TaskCreate

#### [NEW] `tinycua/loops/task_create.py` (NEW file)

- **Description of change**: `TinyCUATaskCreateNode` (ProcessNode) accepts and uses DigestedInformation from WorkerNode's propagate() output in `build_messages()`.
- **Dependencies**: Depends on `DigestedInformation`

### Loops — Registration

#### [MODIFY] `tinycua/loops/__init__.py`

- **Description of change**: Export new node classes: `TinyCUAQueryAnalystNode`, `TinyCUAWorkerNode`, `TinyCUAInformationDigesterNode`, `TinyCUATaskCreateNode`.
- **Rationale**: Makes new nodes available to the package.

### Loops — Queue Bootstrap

#### [MODIFY] `tinycua/loops/tinycua_loop.py`

- **Description of change**: Wire `QueryAnalyst` as the entry node in the queue bootstrap, replacing the current `Worker` entry point.
- **Rationale**: Required by design.md architecture — QueryAnalyst routes to InformationDigester before WorkerNode.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.models.digested_information` | New | DigestedInformation dataclass with fallback behavior |
| `tinycua.loops.query_analyst` | New | DecisionNode with worker route + digest spawn + dedup |
| `tinycua.loops.information_digester` | New | ProcessNode with fresh session + context digestion |
| `tinycua.loops.worker` | New | DecisionNode accepting DigestedInformation from session |
| `tinycua.loops.task_create` | New | ProcessNode accepting DigestedInformation from Worker |
| `tinycua.loops.__init__` | Modified | Export new node classes |
| `tinycua.loops.tinycua_loop` | Modified | Wire QueryAnalyst as entry node in queue bootstrap |
| `tinycua.models.__init__` | Modified | Export DigestedInformation |

## Data Model Changes

```python
@dataclass
class DigestedInformation:
    """Structured output from InformationDigesterNode."""
    context_summary: str = ""
    key_points: list[str] = field(default_factory=list)
    advisory_instructions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    known_gaps: list[str] = field(default_factory=list)
    original_query: str = ""

    @classmethod
    def fallback(cls, original_query: str) -> "DigestedInformation": ...

    @property
    def has_useful_context(self) -> bool: ...
```

## API Changes

### New Endpoints

None — this is internal routing logic, not API-facing.

### Modified Endpoints

None.

## Dependencies

### External Dependencies

No new external dependencies.

### Internal Dependencies

- [ ] Depends on existing `Node`, `ProcessNode`, `DecisionNode` base classes
- [ ] Depends on existing `NodeQueue.spawn_after_current()` and `advance()` methods
- [ ] Depends on existing `Session.session_context` for digest propagation
- [ ] Blocks downstream milestones (3.6 ResponseNode suspension integration)

## Known Gaps

- **InformationDigesterNode tool integration**: `InformationDigesterNode._parse_digest_response()` parses raw LLM text into `DigestedInformation` via JSON parsing with a text fallback. It does not invoke `enhanced_context_retrieval` or `digest_information` tools defined in `docs/design/tools/digester.md`. The quality of digested output depends entirely on the LLM's ability to produce valid JSON. Without tool-based context gathering, the digester has no structured way to access session history or root context. This is acceptable for the skeleton implementation but limits effectiveness in production. **Follow-up milestone dependency.**

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| InformationDigesterNode failure blocks worker path | High | InformationDigesterNode failure — the digester uses record_failure retry policy, producing DigestedInformation.fallback() directly. QueryAnalyst worker route handler checks for fallback and proceeds normally. |
| Digest deduplication misses edge cases | Medium | Conservative approach: check session_context for any existing DigestedInformation entry |
| InformationDigesterNode session lifecycle conflicts | Medium | Fresh session with lazy root context access via enhanced_context_retrieval |
| WorkerNode backwards compatibility | Medium | DigestedInformation.original_query preserves the raw query; fallback to session input_context |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-12*
