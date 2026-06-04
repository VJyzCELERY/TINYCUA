# RouteMap

> **Package:** `tinycua.loops.route_map`
> **Status:** Target architecture

## Role

`RouteMap` is a lightweight dispatch table owned by concrete `DecisionNode` classes. It
maps validated decision labels to named route handlers that mutate `NodeQueue`.

It replaces `RouterNode` without becoming a standalone orchestration layer.

```text
DecisionResult
  · label: str
  · confidence: float | None
  · rationale: str | None
  · raw_output: str | dict | None
  · metadata: dict

Route
  · label: str
  · handler: Callable[[NodeQueue, DecisionResult], None]

RouteMap
  · routes: dict[str, Route]
  · dispatch(label, queue, result)
```

`DecisionResult.label` is the validated route label. Decision nodes may keep raw LLM or
deterministic decision output in `raw_output`, but route dispatch uses only labels present
in the owning `RouteMap.routes` table.

## Examples

```text
TinyCUAQueryAnalystNode.route_map:
  passthrough → route_passthrough()
  worker      → route_worker()

TinyCUAWorkerNode.route_map:
  task_recreation   → route_task_recreation()
  task_reanalysis   → route_task_reanalysis()
  passthrough       → route_passthrough()
  proceed_execution → route_proceed_execution()
```

Route handlers are callables. By convention they are named methods on the concrete
`DecisionNode`, but standalone callables are valid when tests and ownership are clear.

## Mandatory Passthrough

`mandatory_passthrough` is a deterministic continuation directive available to every node.
It overrides LLM classification to route the next user input directly to a target
node/session.

```text
MandatoryPassthrough
  · target_node_id: str
  · target_session_id: str | None
  · reason: str
  · payload: NodeInput | NodePayload | None
  · allow_query_analyst_restart: bool = true
```

### QueryAnalyst Prechecks

Before LLM classification, `TinyCUAQueryAnalystNode` runs deterministic prechecks. QueryAnalyst prechecks run before LLM classification:

1. If a valid `mandatory_passthrough` exists, forward the user continuation to the target node/session.
2. If no valid mandatory passthrough exists, run normal `QueryAnalyst` classification.

This ensures continuation and HITL flows are deterministic. Relying on LLM classification
to choose passthrough can drop or reroute user input away from the intended active node/session.

## Related

- [`node.md`](node.md)
- [`worker_concept.md`](worker_concept.md)
