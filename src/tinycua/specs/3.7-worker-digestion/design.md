# Design Document: WorkerNode Information-Digestion via QueryAnalyst

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-12
**Milestone**: 3.7 — WorkerNode Information-Digestion via QueryAnalyst

---

## Overview

This design extends `TinyCUAWorkerNode` with context sufficiency detection and the ability to request information digestion via `TinyCUAInformationDigesterNode` before proceeding with task planning and execution routing. When QueryAnalyst classifies user input as `worker` and spawns a WorkerNode, the WorkerNode performs a two-step precheck: (1) deterministic task-exists check (existing), (2) context sufficiency evaluation (new). If context is insufficient, WorkerNode prepends InformationDigesterNode to the queue, suspends itself, and resumes with `DigestedInformation` in its session context before proceeding with its normal routing (task_creation, task_recreation, etc.).

**Subproject(s) affected**: `tinycua` — `tinycua/loops/worker.py`, `tinycua/config/node_config.py`, and associated unit/integration tests.

**Key architectural decision**: Digestion is synchronous and queue-based — InformationDigesterNode is prepended before WorkerNode and executes on the next loop iteration, following the same pattern as ResponseNode's digestion suspension (Milestone 3.5). The WorkerNode then resumes execution with the enriched context.

---

## Architecture

### Component Overview

```
QueryAnalyst ──worker──> ┌──────────────────────────────────┐
                          │         WorkerNode               │
                          │  (DecisionNode with digestion)   │
                          │                                  │
                          │  1. Task exists precheck (det.)  │
                          │  2. Context sufficiency check    │
                          │     ├─ sufficient ──→ route      │
                          │     └─ insufficient              │
                          │         → prepend Information-   │
                          │           DigesterNode to queue  │
                          │         → return "needs_digest"  │
                          └──────────┬───────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  Next loop iteration:            │
                    │  InformationDigesterNode runs    │
                    │  Produces DigestedInformation    │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  WorkerNode resumes              │
                    │  Digested info in session ctx    │
                    │  → route dispatch (task_creation,│
                    │    task_recreation, etc.)        │
                    └────────────────┬────────────────┘
                                     ▼
                          ┌──────────────────────┐
                          │ TaskCreateNode / etc. │
                          │ (enriched context)    │
                          └──────────────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.worker.TinyCUAWorkerNode` | Modified | Add context sufficiency check, digestion request, and digest-aware resumption |
| `tinycua.config.node_config.WorkerNodeConfig` | New | Extends NodeConfigBase with `max_digest_attempts`, `digestion_enabled` |
| `tinycua.loops.tinycua_loop.TinyCUALoop` | Modified | Handle `needs_digest` signal from WorkerNode (queue prepend) |
| `tinycua.loops.information_digester.TinyCUAInformationDigesterNode` | Unchanged | Reused as-is from Milestone 2.5 |
| `tinycua.models.digested_information.DigestedInformation` | Unchanged | Reused as-is from Milestone 2.5 |
| `tinycua.models.session.Session` | Unchanged | Session context can store digested information as entries |

---

## Data Model

### New / Extended Entities

```python
from dataclasses import dataclass
from typing import Any


@dataclass
class ContextSufficiency:
    """Transient result of the context sufficiency check.

    Not stored persistently — used only during worker execution to
    decide whether digestion is needed.

    Attributes:
        sufficient: Whether the current context is sufficient for task planning.
        reason: Human-readable explanation of the sufficiency decision.
    """
    sufficient: bool
    reason: str = ""


@dataclass
class WorkerDigestionState:
    """Tracks digestion state within a single worker execution cycle.

    Stored on the WorkerNode instance as an attribute to persist across
    queue iterations.

    Attributes:
        digest_attempts: Number of digestion attempts made in this cycle.
        pending_digest: Whether a digestion request is currently pending
            (WorkerNode is waiting for InformationDigesterNode to complete).
        last_digested_info: The DigestedInformation from the last completed
            digestion, or None if not yet received.
    """
    digest_attempts: int = 0
    pending_digest: bool = False
    last_digested_info: Any = None  # DigestedInformation | None


@dataclass
class WorkerNodeConfig:
    """Configuration for WorkerNode with digestion support.

    Extends the conceptual NodeConfigBase with digestion-specific settings.
    (Concrete implementation extends the actual NodeConfigBase class.)

    Attributes:
        max_digest_attempts: Maximum number of digestion attempts per
            worker execution cycle (default: 3).
        digestion_enabled: When False, context sufficiency check and
            digestion request are skipped entirely (default: True).
    """
    max_digest_attempts: int = 3
    digestion_enabled: bool = True
```

### Schema Changes

- **WorkerNode**: New attribute `_digestion_state`: `WorkerDigestionState` — tracks digestion state across queue iterations.
- **WorkerNodeConfig**: New fields `max_digest_attempts` (int, default 3), `digestion_enabled` (bool, default True).
- **Session**: No changes — digested information is stored as entries in `session_context` (list of dicts with `role: "assistant"`, `content: str` containing the structured digest).

---

## API / Interface Contracts

### Modified Function Signatures

```python
class TinyCUAWorkerNode(DecisionNode):
    """Enhanced with context sufficiency check and digestion request."""

    def __init__(
        self,
        node_id: str = "worker",
        config: WorkerNodeConfig | None = None,
        route_map: RouteMap | None = None,
        effort: WorkerEffort = WorkerEffort.none,
    ) -> None:
        """Initialize WorkerNode with digestion config.

        Args:
            node_id: Unique identifier for this node.
            config: WorkerNodeConfig with digestion settings.
            route_map: Optional pre-configured RouteMap.
            effort: WorkerEffort level controlling analysis depth.
        """

    def _check_context_sufficiency(self) -> ContextSufficiency:
        """Evaluate whether current session context is sufficient for task planning.

        Uses an LLM-based heuristic to compare available context against
        the user's request. Can be skipped (returns sufficient=True) when
        high-confidence heuristic signals are met (e.g., rich prior context).

        Returns:
            ContextSufficiency with sufficient flag and reason.
        """

    def _request_digestion(self, queue: NodeQueue) -> None:
        """Request context digestion by prepending InformationDigesterNode.

        Prepends InformationDigesterNode to the queue before WorkerNode,
        sets pending_digest flag, and records the digested information
        target. Does NOT advance the queue — the next loop iteration
        will execute InformationDigesterNode.

        Args:
            queue: The node queue to mutate.

        Raises:
            NodeExecutionError: If InformationDigesterNode is not available.
        """
```

### Digestion Signal Contract

WorkerNode signals a digestion request by returning a `DecisionResult` with a special `route_label` value of `"needs_digest"`. The loop detects this label and, instead of dispatching via RouteMap (which doesn't handle this label), prepends `InformationDigesterNode` to the queue.

```python
@dataclass
class DecisionResult:
    """Extended: route_label can be 'needs_digest' for digestion requests."""
    route_label: str
    analysis_response: LLMResult
    classification_response: LLMResult
    # New attribute for digestion request context:
    digestion_context: dict[str, Any] | None = None  # Messages to pass to digester
```

### Loop Integration

`TinyCUALoop._execute_decision_node` is modified to detect the `"needs_digest"` route_label:

```python
# In _execute_decision_node, after WorkerNode returns DecisionResult:
if isinstance(node, TinyCUAWorkerNode) and decision.route_label == "needs_digest":
    # Prep InformationDigesterNode
    digester = TinyCUAInformationDigesterNode()
    # WorkerNode is at queue front; prepend digester before it
    queue.prepend(digester)
    # Do NOT advance (digester runs next) but mark WorkerNode's digestion state
    node._digestion_state.pending_digest = True
    logger.info(
        "worker_digestion: prepended InformationDigesterNode for context gathering"
    )
    return content, False, decision  # should_advance=False
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| InformationDigesterNode disabled | `WARNING` log, skip digestion | WorkerNode proceeds with available context |
| Digestion execution fails | Retry per `NodeRetryPolicy`, then max_attempts check | Falls through to normal routing |
| Max digest attempts reached | `INFO` log, skip digestion | Prevents infinite loops per FR-006 |
| No useful context from digester | Treat as no-op, proceed with existing context | `INFO` log "digestion returned no useful context" |
| Double-prepend detected (digester already in queue) | `INFO` log, skip request | NodeQueue.inspect() or queue contains check |
| Null/empty session context | `sufficient=False` → triggers digestion | If digestion disabled, proceed with minimal context |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] **PH1-1**: Add `WorkerDigestionState` dataclass and `_digestion_state` attribute to `TinyCUAWorkerNode`.
- [ ] **PH1-2**: Implement `ContextSufficiency` dataclass and `_check_context_sufficiency()` method on WorkerNode using LLM-based heuristic.
- [ ] **PH1-3**: Implement `_request_digestion()` method that prepends `InformationDigesterNode` to the queue via `NodeQueue.prepend()`.
- [ ] **PH1-4**: Modify `__call__()` to perform context sufficiency check after deterministic task-exists precheck and before LLM routing.
- [ ] **PH1-5**: Return `DecisionResult(route_label="needs_digest")` when digestion is requested.
- [ ] **PH1-6**: Modify `TinyCUALoop._execute_decision_node()` to detect `"needs_digest"` label and prepend `InformationDigesterNode`.
- [ ] **PH1-7**: Modify `TinyCUALoop._execute_decision_node()` to provide `WorkerNode` with digestion context from completed `InformationDigesterNode` output.
- [ ] **PH1-8**: Add `max_digest_attempts` counter logic with loop prevention.
- [ ] **PH1-9**: Add `digestion_enabled` guard to skip sufficiency check when disabled.
- [ ] **PH1-10**: Logging for all digestion requests, attempts, and outcomes.

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] **PH2-1**: High-confidence heuristic pre-filter to skip LLM-based sufficiency check when context is trivially sufficient (e.g., prior task has rich context, or user request includes all necessary detail).
- [ ] **PH2-2**: Configurable sufficiency thresholds (e.g., minimum session context messages before considering context sufficient).

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use `"needs_digest"` as a special route_label for signaling digestion requests.
   - **Reason**: Minimizes changes to the existing `DecisionNode`/`DecisionResult` contract. The loop already handles `DecisionResult.route_label` for route dispatch; adding one special value avoids a new signal mechanism.
   - **Alternatives Considered**: (a) New method on Node for digestion signals — rejected because it would require changes to the base `Node` class. (b) Side-effect in `on_complete` — rejected because the queue prepend needs loop-level coordination.

2. **Decision**: Digestion is synchronous via queue prepend (same pattern as ResponseNode).
   - **Reason**: The queue-based execution model naturally supports this pattern. InformationDigesterNode executes on the next loop iteration, and WorkerNode resumes when the queue cycles back. This avoids async coordination complexity.
   - **Alternatives Considered**: Async digestion with callbacks — rejected because it's inconsistent with the existing synchronous queue model.

3. **Decision**: Context sufficiency check is LLM-based, with an optional high-confidence pre-filter.
   - **Reason**: LLM-based evaluation provides the most accurate assessment of context sufficiency for arbitrary user requests. The pre-filter (Phase 2) optimizes for common cases where context is clearly sufficient.
   - **Alternatives Considered**: (a) Heuristic-only (message count, token thresholds) — rejected because it's unreliable for complex queries. (b) Always digest — rejected because it's wasteful when context is already rich.

4. **Decision**: Digested information is stored in session_context as message entries.
   - **Reason**: Reuses the existing session context mechanism. Downstream nodes (TaskCreateNode, TaskAnalyzerNode, TaskExecutorNode) already read from session_context and will automatically have access to the digested information without changes to message building.

5. **Decision**: WorkerNode does not block or wait — it returns `"needs_digest"` and the loop handles queue prepend.
   - **Reason**: WorkerNode's `__call__()` must return a `DecisionResult` synchronously. Queue mutation happens in `on_complete` / loop handler, not during `__call__`. The loop handles the actual queue prepend, keeping WorkerNode's call contract unchanged.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Infinite digestion loop | Low | High | `max_digest_attempts` counter with hard limit (default 3); logged warnings |
| Performance overhead of LLM sufficiency check | Medium | Low | High-confidence pre-filter (Phase 2) skips LLM call for trivially sufficient cases; digestion can be disabled entirely |
| Queue corruption from prepend | Low | High | `NodeQueue.prepend()` must validate queue state; unit tests verify queue integrity after prepend |
| Regression in existing worker routing | Medium | Medium | All existing WorkerNode route tests must pass unchanged; new tests cover digestion path |
| InformationDigesterNode prepend when already in queue | Low | Medium | Guard check (FR-013) prevents double-prepend; `Queue.contains()` or `Queue.find()` check |

---

## Open Questions _(optional)_

1. **Should `NodeQueue.prepend()` be a new method or reuse `spawn_after_current` with position parameter?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-14
   - **Status**: Proposed
   - **Proposed Answer**: New `prepend()` method for clarity. `spawn_after_current` inserts after the current node; prepend inserts at position 0. These are semantically different operations.

2. **Should the high-confidence pre-filter (Phase 2) be part of MVP or deferred?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-14
   - **Status**: Proposed
   - **Proposed Answer**: Deferred to Phase 2. The MVP should implement the full LLM-based check to ensure correctness; optimization can follow once the feature is stable.

---

## References

- Spec: `./spec.md`
- WorkerNode (existing): `src/tinycua/tinycua/loops/worker.py`
- InformationDigesterNode (Milestone 2.5): `src/tinycua/specs/2.5-information-digester-node/`
- ResponseNode Digestion (Milestone 3.5): `src/tinycua/tinycua/loops/response_node.py`
- NodeQueue: `src/tinycua/tinycua/loops/node_queue.py`
