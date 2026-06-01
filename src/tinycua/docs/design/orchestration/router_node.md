# Router Node

> **File:** `docs/design/orchestration/router_node.md`
> **Package:** `tinycua.orchestration.router_node`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`RouterNode` is a transient, stateless graph node that maps an input string to a
route output using exact string matching. It has **no Session** and does not call an
SDK `Agent`. It is used when graph policy needs deterministic routing rather than LLM
classification.

---

## Contract

```text
RouterNode
  · route: dict[str, Any]

run(input: str) → Any:
  · if input in route: return route[input]
  · else: return route["default"]
```

`route` values are intentionally `Any` because a router may return:

- another node reference
- an action enum/string
- a callable graph transition
- a precomputed state/output object

---

## Matching Semantics

Routing uses **exact match + default** only.

```text
router = RouterNode(route={
    "passthrough": PrimaryAgentNode,
    "worker": TinyCUAWorkerGraph,
    "default": PrimaryAgentNode,
})

router.run("worker")      → TinyCUAWorkerGraph
router.run("unknown")     → PrimaryAgentNode
```

No substring, prefix, regex, or predicate matching is performed. If richer routing is
needed, build a dedicated `DecisionNode` or use a QueryAnalyst with a configurable
ClassificationTool.

---

## Session Policy

`RouterNode` has no session:

| Property | Value |
|----------|-------|
| `has_session` | `False` |
| `is_transient` | N/A — not a Session owner |
| `chat_history` | None |
| `session_context` | None |
| `Agent.run()` | Never called |

Graph code may record router decisions through the parent session's
`append_graph_action(...)` if the decision should be audit-visible.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Exact match only | `route[input]` or `route["default"]` | Predictable, deterministic, no ambiguous matching |
| No session | Stateless process node | Router output is policy, not agent conversation |
| `dict[str, Any]` | Values may be nodes or actions | Enables simple routing without requiring a node wrapper for every action |
| Default required | `"default"` key | Prevents unhandled routes |

---

## See also

Prev : [`TinyCUA AgentGraph`](tinycua.md) | Next : [`TinyCUAWorker AgentGraph`](worker.md)

## Related

- [Node types overview](overview.md#node-types)
- [TinyCUA routes QueryAnalyst classification through RouterNode](tinycua.md)
- [TinyCUAWorker input gate uses configurable QueryAnalyst](worker.md)
