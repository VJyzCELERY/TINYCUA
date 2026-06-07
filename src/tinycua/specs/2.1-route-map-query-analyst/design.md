# Design Document: RouteMap and Top-Level QueryAnalyst

**Spec**: ./spec.md
**Status**: Complete
**Last Updated**: 2026-06-08
**Milestone**: 2.1 — RouteMap and Top-Level QueryAnalyst

---

## Overview

This design implements RouteMap as a lightweight dispatch table and TinyCUAQueryAnalystNode as the top-level entry DecisionNode for TinyCUA. QueryAnalyst classifies user input into passthrough/worker/uncertain using a two-step decision process and routes the queue accordingly. MandatoryPassthrough provides deterministic continuation routing that overrides LLM classification.

---

## Architecture

### Component Overview

```
TinyCUALoop.run(...)
  └── NodeQueue
       ├── [QueryAnalyst] → RouteMap dispatch → {passthrough, worker, uncertain}
       │    ├── passthrough → forward to target node/session
       │    ├── worker → spawn or reuse WorkerNode
       │    └── uncertain → remain active, wait for continuation
       ├── [WorkerNode] (optional, if worker route)
       └── [ResponseNode] (terminal)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| tinycua.loops.route_map | New | RouteMap dispatch table class |
| tinycua.loops.query_analyst | New | TinyCUAQueryAnalystNode concrete DecisionNode |
| tinycua.models.classification | New | Classification labels and DecisionResult models |
| tinycua.loops.node | Modified | DecisionNode gains route_map attribute |
| tinycua.loops.tinycua_loop | Modified | Queue bootstrap uses QueryAnalyst at front |

---

## Data Model

### New Entities

```python
# Conceptual data shape (not necessarily the final class)

RouteMap:
    routes: dict[str, Route]  # label → Route

Route:
    label: str
    handler: Callable[[NodeQueue, DecisionResult], None]

DecisionResult:
    route_label: str
    analysis_response: LLMResult
    classification_response: LLMResult

MandatoryPassthrough:
    target_node_id: str
    target_session_id: str | None
    reason: str
    payload: NodeInput | NodePayload | None
    allow_query_analyst_restart: bool = True

QueryAnalystResponse:
    user_query: str
    classification: str  # passthrough | worker | uncertain
    rationale: str | None
```

### Schema Changes

- DecisionNode gains optional `route_map: RouteMap` attribute.
- DecisionResult is already defined in `tinycua/loops/node.py:30` with fields `route_label: str`, `analysis_response: LLMResult`, `classification_response: LLMResult`; no schema change needed.
- MandatoryPassthrough is a new dataclass for deterministic continuation.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class RouteMap:
    """
    Lightweight dispatch table for DecisionNode routing.
    Maps validated labels to route handler callables.
    """
    
    def __init__(self) -> None:
        self.routes: dict[str, Route] = {}
    
    def register(self, label: str, handler: Callable) -> None:
        """Register a route handler for a label."""
    
    def dispatch(self, label: str, queue: NodeQueue, result: DecisionResult) -> None:
        """Dispatch to the handler for the given label.
        
        Raises ValueError if label not in routes.
        """


class TinyCUAQueryAnalystNode(DecisionNode):
    """
    Top-level entry DecisionNode for TinyCUA.
    Classifies user input and routes the queue.
    """
    
    def __init__(
        self,
        node_id: str = "query_analyst",
        config: NodeConfigBase | None = None,
        route_map: RouteMap | None = None,
    ):
        """Initialize with classification labels passthrough/worker/uncertain."""
    
    def check_mandatory_passthrough(
        self, input_data: NodeInputLike
    ) -> MandatoryPassthrough | None:
        """Check for a valid MandatoryPassthrough in the input.
        
        Returns the passthrough directive if found and valid, None otherwise.
        """
    
    def find_existing_worker(self, queue: NodeQueue) -> Node | None:
        """Find an existing WorkerNode in the queue before terminal ResponseNode."""
    
    def route_passthrough(
        self, queue: NodeQueue, result: DecisionResult
    ) -> None:
        """Route handler for passthrough label."""
    
    def route_worker(
        self, queue: NodeQueue, result: DecisionResult
    ) -> None:
        """Route handler for worker label. Reuses existing or spawns new."""
    
    def route_uncertain(
        self, queue: NodeQueue, result: DecisionResult
    ) -> None:
        """Route handler for uncertain label. QueryAnalyst stays active."""
    
    def on_complete(self, queue: NodeQueue, result: DecisionResult) -> None:
        """Dispatch route after classification."""
```

### Input Preservation (FR-016)

QueryAnalyst MUST preserve the original input query for downstream nodes. This is handled through:

1. **QueryAnalystResponse.user_query**: The original user query string is captured during analysis and included in the response dataclass. This field is always populated with the user's original input text.

2. **NodeInput.messages forwarding**: When routing to downstream nodes, the original `NodeInput` (containing `messages` with the user's query) is passed through the route handlers. Specifically:
   - `route_passthrough`: Forwards the original `NodeInput` to the target node/session via `MandatoryPassthrough.payload` or by passing the input directly to the target.
   - `route_worker`: Passes the original input to the spawned/reused WorkerNode so it can process the user's request.
   - `route_uncertain`: QueryAnalyst remains active with the original input still in context, awaiting user continuation.

3. **Downstream access**: WorkerNode and ResponseNode access the original user input via `NodeInput.messages` — the same structure that was provided to QueryAnalyst. No transformation or loss of the original query occurs during routing.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Unknown route label | ValueError from RouteMap.dispatch | Retry per NodeRetryPolicy |
| No existing WorkerNode for reuse | Spawn new WorkerNode | Normal behavior |
| Stale MandatoryPassthrough | Fallback to restart or silent drop | Per allow_query_analyst_restart |
| No session attached | NodeExecutionError | Existing behavior from DecisionNode |
| LLM classification failure | Retry per NodeRetryPolicy | Existing behavior |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create RouteMap class with register() and dispatch()
- [ ] Create Route dataclass
- [ ] Create MandatoryPassthrough dataclass
- [ ] Create TinyCUAQueryAnalystNode with classification labels
- [ ] Implement mandatory_passthrough precheck
- [ ] Implement two-step decision process (analysis → classification → dispatch)
- [ ] Implement route_passthrough handler
- [ ] Implement route_worker handler with existing WorkerNode detection
- [ ] Implement route_uncertain handler
- [ ] Implement on_complete for RouteMap dispatch
- [ ] Update TinyCUALoop queue bootstrap to use QueryAnalyst at front
- [ ] Add QueryAnalyst deduplication check

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Classification tool call integration (verdict tool)
- [ ] Read-only task inspection tool for QueryAnalyst
- [ ] Advanced context assembly with node context priority

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

### Known Deviations from Target Architecture

Phase 1 implements a simplified subset of the target behavior defined in `query_analyst.md` and `route_map.md`. The following behaviors are **deferred** to later milestones:

| Target Architecture Behavior | Status | Milestone |
|------------------------------|--------|-----------|
| Worker LLM decision (task_recreation, task_reanalysis, etc.) | Deferred | 2.3 |
| Worker-owned queue segment detection | Deferred | 2.2 |
| Full classification tool call integration | Deferred | Phase 2 |
| Read-only task inspection tools | Deferred | Phase 2 |
| Transient context assembly with node priority | Deferred | Phase 2 |

**Phase 1 scope**: RouteMap dispatch, QueryAnalyst classification (passthrough/worker/uncertain), mandatory_passthrough precheck, worker reuse/spawn, uncertain behavior, and queue bootstrap with QueryAnalyst at front.

---

## Technical Decisions

1. **Decision**: RouteMap as a separate class (not inline dict on DecisionNode)
   - **Reason**: Testability, reusability, and clear ownership semantics. Each concrete DecisionNode can have its own RouteMap instance.
   - **Alternatives Considered**: Inline dict — rejected because it mixes routing logic with node logic.

2. **Decision**: MandatoryPassthrough as a dataclass (not a method parameter)
   - **Reason**: Structured representation allows precheck to be a clean method call. Payload and metadata travel together.
   - **Alternatives Considered**: Tuple or dict — rejected for clarity.

3. **Decision**: QueryAnalyst always checks mandatory_passthrough before LLM classification
   - **Reason**: Deterministic continuation must not depend on LLM classification. This is a hard requirement from the design doc.
   - **Alternatives Considered**: Parallel check — rejected; ordering matters.

4. **Decision**: Worker reuse by finding existing WorkerNode in queue before terminal ResponseNode
   - **Reason**: Matches the design doc's "Worker-Route Rule" — if WorkerNode exists before terminal, reuse it.
   - **Alternatives Considered**: Always spawn — rejected; creates duplicate workers.

5. **Decision**: Uncertain handler is a no-op (QueryAnalyst stays active)
   - **Reason**: When classification is uncertain, QueryAnalyst remains the current node and waits for user continuation. Queue does not advance.
   - **Alternatives Considered**: Spawn a clarifier node — rejected; out of scope for 2.1.

6. **Decision**: Replace StubNode with QueryAnalyst in queue bootstrap
   - **Reason**: QueryAnalyst is the true entry point; StubNode was a placeholder from Milestone 1.8.
   - **Alternatives Considered**: Keep both — rejected; unnecessary complexity.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| QueryAnalyst two-step process makes 2 LLM calls per input | High | Medium | Acceptable for prototype; optimize later with classification tool |
| Worker reuse detection may miss edge cases | Medium | Low | Simple linear scan of queue; test with various queue states |
| MandatoryPassthrough stale guard may be too strict | Low | Medium | allow_query_analyst_restart provides safe fallback |
| LLM may not reliably classify into exact labels | Medium | Medium | NodeRetryPolicy handles retries; fallback to uncertain |

---

## Open Questions _(optional)_

1. **Should QueryAnalyst use a classification tool or free-text classification?**
   - **Status**: Deferred to Phase 2 — Phase 1 uses free-text classification with label matching.

2. **How should QueryAnalyst assemble context from active/queued nodes?**
   - **Status**: Deferred to Phase 2 — Phase 1 uses root session context only.

---

## References

- Spec: `./spec.md`
- RouteMap target architecture: `src/tinycua/docs/design/loops/route_map.md`
- QueryAnalyst target architecture: `src/tinycua/docs/design/loops/query_analyst.md`
- Classification model: `src/tinycua/docs/design/models/classification.md`
- DecisionNode base: `src/tinycua/tinycua/loops/node.py`
- NodeQueue: `src/tinycua/tinycua/loops/node_queue.py`
- TinyCUALoop: `src/tinycua/tinycua/loops/tinycua_loop.py`
- Milestone 1.8 spec: `src/tinycua/specs/1.8-tinycua-loop-sdk-integration/spec.md`
