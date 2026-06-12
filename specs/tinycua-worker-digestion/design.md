# Design Document: WorkerNode Information-Digestion via QueryAnalyst

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-12

---

## Overview

This design implements the integration path where **QueryAnalyst spawns `InformationDigesterNode`** before routing to **WorkerNode**, and the resulting `DigestedInformation` flows through WorkerNode to downstream nodes (TaskCreate, TaskAnalyzer, etc.). The design follows the target architecture in `src/tinycua/docs/design/loops/query_analyst.md`, `src/tinycua/docs/design/loops/worker.md`, `src/tinycua/docs/design/loops/information_digester.md`, and `src/tinycua/docs/design/models/digested_information.md`.

Subproject(s) affected: `tinycua` (loops package — query_analyst, worker, information_digester, task_create modules).

---

## Architecture

### Component Overview

```
User Query
    │
    ▼
QueryAnalyst (DecisionNode)
    │
    │  worker route handler
    │
    ├────► [Check: already digested?]
    │         ├── Yes ──► forward directly to WorkerNode
    │         └── No  ──► spawn InformationDigesterNode
    │                         │
    │                         ▼
    │               InformationDigesterNode (ProcessNode)
    │                         │
    │                    Fresh session
    │                    enhanced_context_retrieval  (lazy)
    │                    digest_information
    │                         │
    │                    DigestedInformation
    │                         │ (selected-output propagation)
    │                         ▼
    │               WorkerNode.session_context ← digest lands here
    │                         │
    │                         ▼
    └────────────────────► WorkerNode (DecisionNode)
                               │
                          Reads DigestedInformation
                          from session_context
                               │
                          Forwards DigestedInformation
                          via propagate() to next node
                               │
                               ▼
                         TaskCreateNode
                         (receives DigestedInformation)
                               │
                               ▼
                         TaskAnalyzerNode (initial analysis)
                               │
                               ▼
                         ... downstream nodes ...
```

### Queue Transition — Worker Route with Digestion

```
Before (QueryAnalyst current):
  [QueryAnalyst|current, ..., WorkerNode(?), ResponseNode]

QueryAnalyst decides worker, no existing digest:
  queue.spawn_after_current([InformationDigesterNode, WorkerNode])
  → [QueryAnalyst, InformationDigesterNode|current, WorkerNode, ResponseNode]

Loop advances past QueryAnalyst:
  → [InformationDigesterNode|current, WorkerNode, ResponseNode]

InformationDigesterNode completes:
  propagate() → DigestOutput lands in WorkerNode.session_context via
                selected-output propagation profile
  on_complete() → advance() → [WorkerNode|current, ResponseNode]

WorkerNode receives DigestedInformation from session_context:
  → Processes routing decision with digested context
  → Forwards DigestedInformation via propagate()
  → on_complete() spawns TaskCreateNode (or other) via route handler
  → [TaskCreateNode(WorkerDigestedInput)|current, ..., ResponseNode]
```

### Queue Transition — Reused Worker with Existing Digest

```
Before (QueryAnalyst current, WorkerNode already queued):
  [QueryAnalyst|current, WorkerNode, TaskExecutor(stale), ResultReviewer, ResponseNode]

QueryAnalyst decides worker:
  WorkerNode session_context already has DigestedInformation
  → No digester spawned
  → advance QueryAnalyst, WorkerNode becomes current with existing digest
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/query_analyst.py` | New | Concrete `TinyCUAQueryAnalystNode` with worker route handler including digest spawn logic |
| `tinycua/loops/worker.py` | New | Concrete `TinyCUAWorkerNode` accepting DigestedInformation from session_context |
| `tinycua/loops/information_digester.py` | New | Concrete `TinyCUAInformationDigesterNode` (ProcessNode) with fresh session, lazy context retrieval |
| `tinycua/loops/task_create.py` | Modified | `TinyCUATaskCreateNode` input updated to receive DigestedInformation from Worker |
| `tinycua/models/digested_information.py` | New | `DigestedInformation` dataclass with context_summary, key_points, etc. |
| `tinycua/loops/__init__.py` | Modified | Export new node classes |
| `tinycua/loops/tinycua_loop.py` | Modified | Queue bootstrap may need to wire QueryAnalyst as entry node |

---

## Data Model

### DigestedInformation

```python
@dataclass
class DigestedInformation:
    """Structured output from InformationDigesterNode.

    Produced by InformationDigesterNode and consumed by WorkerNode
    (or ResponseNode). Preserves original query for downstream use.

    Attributes:
        context_summary: High-level summary of gathered context.
            Contains original user query in fallback case.
        key_points: List of key points extracted from context.
        advisory_instructions: Advisory notes for downstream processing.
        constraints: Known constraints or limitations.
        known_gaps: Gaps identified in gathered context.
        original_query: The original user query, always preserved.
    """

    context_summary: str = ""
    key_points: list[str] = field(default_factory=list)
    advisory_instructions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    known_gaps: list[str] = field(default_factory=list)
    original_query: str = ""

    @classmethod
    def fallback(cls, original_query: str) -> "DigestedInformation":
        """Create a fallback instance when no useful context is found.

        The fallback contains the original query in context_summary
        and a note that no additional context was available.
        """
        return cls(
            context_summary=(
                f"The user asked: {original_query}. "
                "No useful extra information was found. "
                "Downstream should proceed with the user request "
                "and plan carefully before action."
            ),
            original_query=original_query,
        )

    @property
    def has_useful_context(self) -> bool:
        """Whether this digest contains useful context beyond the fallback."""
        return bool(self.key_points or self.advisory_instructions or self.constraints)
```

### InformationDigesterNode Session

```python
# InformationDigesterNode creates a fresh node session:
#   session_id = str(uuid4())
#   session.session_context = []  # empty — lazy access via enhanced_context_retrieval
#   Does NOT inherit parent session_id or root session
#   Stores only new digest output (not copied input messages)
```

---

## API / Interface Contracts

### QueryAnalyst Worker Route Handler

```python
class TinyCUAQueryAnalystNode(DecisionNode):
    """Top-level entry node that classifies user input and routes the queue."""

    ROUTE_LABELS = ["worker", "uncertain", "passthrough"]

    def _route_worker(self, input: NodeInputLike) -> None:
        """Route to WorkerNode with information digestion.

        1. Check if target Worker session already has DigestedInformation
           → If yes, advance to existing Worker (no digest spawn)
        2. Check if InformationDigesterNode is already queued
           → If yes, do nothing (duplicate prevention)
        3. Otherwise, spawn InformationDigesterNode before WorkerNode
           → queue.spawn_after_current([digester, worker_node])
           → Assign NodeInput with selected QueryAnalyst session context
             and original user query to the digester

        The digester's selected-output propagation targets the WorkerNode's
        session_context. After digestion completes, WorkerNode resumes
        with DigestedInformation available in its session.
        """
```

### WorkerNode with DigestedInformation

```python
class TinyCUAWorkerNode(DecisionNode):
    """Decision hub for task planning and execution orchestration.

    Receives DigestedInformation from session_context (populated by
    InformationDigesterNode spawned by QueryAnalyst).

    Attributes:
        ROUTE_LABELS: task_creation, task_recreation, task_reanalysis,
                      passthrough, proceed_execution
    """

    def _get_digested_input(self) -> DigestedInformation | None:
        """Retrieve DigestedInformation from session_context.

        Scans session_context for the most recent DigestedInformation
        entry. Returns None if not found (fallback to raw user_query).
        """

    def propagate(self) -> None:
        """Forward DigestedInformation to downstream nodes.

        Includes DigestedInformation in the propagate() output so
        TaskCreateNode (and subsequent nodes) receive it as context.
        The original query is preserved within DigestedInformation.original_query.
        """
```

### TaskCreateNode with DigestedInformation

```python
class TinyCUATaskCreateNode(ProcessNode):
    """First-time deterministic root task creation.

    Input includes DigestedInformation from WorkerNode, providing
    context for root task creation alongside the original query.
    """

    def build_messages(self, session: Session, input: NodeInputLike) -> list[dict]:
        """Build messages including DigestedInformation from Worker.

        Extracts DigestedInformation from NodeInput (passed through
        Worker propagation) and includes it as context in the LLM
        message assembly.
        """
```

### Existing InformationDigesterNode (interface for this milestone)

```python
class TinyCUAInformationDigesterNode(ProcessNode):
    """Gathers and digests context for downstream nodes.

    Spawned by QueryAnalyst before routing to WorkerNode, or by
    ResponseNode via suspend_current_and_prepend.

    Key behaviors for QueryAnalyst-spawned path:
    - Creates fresh node session (does not inherit parent)
    - Receives selected QueryAnalyst session context via NodeInput
    - Uses enhanced_context_retrieval lazily
    - Produces DigestedInformation output
    - Propagates to parent (WorkerNode) session_context via
      selected-output propagation rule
    - Falls back to DigestedInformation.fallback(original_query)
      when no useful context found
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| InformationDigesterNode retry exhausted | NodeExecutionError | Digester failure — fallback DigestedInformation used downstream |
| QueryAnalyst cannot determine route | Retry via NodeRetryPolicy | Per existing DecisionNode contract |
| WorkerNode has no DigestedInformation in session | Fallback to raw user_query from session context | Graceful degradation |
| TaskCreateNode receives no DigestedInformation | Use raw user_query from input | Graceful degradation |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Define `DigestedInformation` dataclass with fields: context_summary, key_points, advisory_instructions, constraints, known_gaps, original_query
- [ ] Implement `DigestedInformation.fallback()` classmethod for no-useful-context case
- [ ] Implement `TinyCUAQueryAnalystNode` with worker route handler that spawns InformationDigesterNode before WorkerNode
- [ ] Implement digest deduplication in QueryAnalyst route handler (check session_context for existing digest)
- [ ] Implement `TinyCUAInformationDigesterNode` as ProcessNode with fresh session creation and selected-input propagation profile
- [ ] Implement InformationDigesterNode fallback: produces `DigestedInformation.fallback(original_query)` when no useful context found
- [ ] Implement `TinyCUAWorkerNode` that reads DigestedInformation from session_context as primary input
- [ ] Implement WorkerNode `propagate()` forwarding DigestedInformation to downstream nodes
- [ ] Update `TinyCUATaskCreateNode` input to accept and use DigestedInformation from Worker
- [ ] Register new node classes in `tinycua/loops/__init__.py`
- [ ] Write unit tests for all new and modified components
- [ ] Write integration tests for end-to-end flow

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- None for this milestone. Subsequent milestones will integrate InformationDigesterNode with ResponseNode suspension (Milestone 3.6).

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Digested information detection via `session_context` checking rather than queue position tracking.
   - **Reason**: The InformationDigesterNode output lands in the WorkerNode's `session_context` as a durable record. Checking `session_context` for existing digest entries is simpler and more reliable than checking queue positions, which are transient and change as nodes advance.
   - **Alternatives Considered**: Queue position check — rejected because the digester may have completed and been removed from the queue, making it undetectable by position alone.

2. **Decision**: InformationDigesterNode creates a fresh node session when spawned by QueryAnalyst.
   - **Reason**: Aligns with the `docs/design/loops/information_digester.md` contract. The digester should not inherit QueryAnalyst's session (which contains broad transient context) but should lazily access root context through `enhanced_context_retrieval`.
   - **Alternatives Considered**: Inherit QueryAnalyst session — rejected because it conflicts with the architecture design doc and could cause context pollution.

3. **Decision**: WorkerNode reads DigestedInformation from `session_context` rather than from a dedicated input field.
   - **Reason**: This aligns with the existing pattern where session_context carries reusable context between nodes. The digester's selected-output propagation targets the Worker's session, so the digest naturally lands in session_context.
   - **Alternatives Considered**: Dedicated `digested_information` field on NodeInput — rejected because it would require changing the NodeInput contract and complicate the propagation path.

4. **Decision**: WorkerNode forwards DigestedInformation via `propagate()` rather than via queue path assignments.
   - **Reason**: Propagation already handles upstream context flow. Including DigestedInformation in the propagation output ensures downstream nodes (TaskCreate, TaskAnalyzer) receive it naturally without special queue manipulation.
   - **Alternatives Considered**: Queue-level digest forwarding — rejected because it would couple digestion to queue mechanics and bypass the propagation model.

5. **Decision**: `DigestedInformation` includes `original_query` field to guarantee downstream access to raw user request.
   - **Reason**: Downstream nodes (TaskCreateNode, TaskExecutor, etc.) need the original user query for task creation and execution context. Embedding it in `DigestedInformation` ensures it survives the digestion pipeline intact.
   - **Alternatives Considered**: Separate propagation of raw query — rejected because it would require dual propagation paths and increase complexity.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| InformationDigesterNode failure blocks worker path | Low | High | Fallback DigestedInformation ensures Worker always has valid input (original query preserved) |
| Digest deduplication misses edge cases (e.g., partial digest, stale digest) | Low | Medium | Conservative approach: if any DigestedInformation exists in target Worker session, skip spawn. Stale digests are harmless as context is additive. |
| InformationDigesterNode session lifecycle conflicts with root session | Low | Medium | Fresh session with lazy root context access via enhanced_context_retrieval prevents conflicts |
| WorkerNode backwards compatibility with nodes expecting raw query | Medium | Medium | DigestedInformation.original_query preserves the raw query; nodes can access it via `digest.original_query` or fall back to session input_context |
| TaskCreateNode receives too much context (digest + session + query) | Low | Low | Message building filters context via NodeMessagePolicy; TaskCreateNode tool policy restricts to TaskInit/TaskCreate only |

---

## Open Questions _(optional)_

_(None — all questions resolved. See spec.md Open Questions section for resolved decisions.)_

---

## References

- Spec: `./spec.md`
- Design docs:
  - `src/tinycua/docs/design/loops/query_analyst.md` — QueryAnalyst role, route labels, transient context
  - `src/tinycua/docs/design/loops/worker.md` — WorkerNode role, DigestedInformation input, route queue shapes
  - `src/tinycua/docs/design/loops/information_digester.md` — InformationDigesterNode behavior, fresh session, fallback
  - `src/tinycua/docs/design/loops/task_create.md` — TaskCreateNode input contract
  - `src/tinycua/docs/design/loops/node_queue.md` — spawn_after_current, suspension/prepend, terminal handling
  - `src/tinycua/docs/design/loops/node.md` — Node hierarchy, lifecycle hooks, propagation
  - `src/tinycua/docs/design/models/digested_information.md` — DigestedInformation model fields
  - `src/tinycua/docs/design/tools/digester.md` — enhanced_context_retrieval and digest_information tools
- Existing code:
  - `tinycua/loops/node.py` — Node, ProcessNode, DecisionNode base classes
  - `tinycua/loops/node_queue.py` — NodeQueue with spawn/suspend/terminal methods
  - `tinycua/loops/tinycua_loop.py` — TinyCUALoop execution loop
- Issue: [#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 3.7
