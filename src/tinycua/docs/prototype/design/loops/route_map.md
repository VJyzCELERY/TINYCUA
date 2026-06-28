# Route Map

**Status**: Code-only reconstruction

## Implemented route labels

- Query analyst: `worker`, `uncertain`, `passthrough`. Evidence: `src/tinycua/tinycua/loops/query_analyst.py:42`.
- Worker: `task_creation`, `task_recreation`, `task_reanalysis`, `passthrough`, `proceed_execution`. Evidence: `src/tinycua/tinycua/loops/worker.py:34-40`.

## Dispatch behavior

Direct `DecisionNode` validation uses substring containment against allowed labels. Evidence: `src/tinycua/tinycua/loops/node.py:743-784`.

Loop-level `DecisionNode` execution does not use the direct two-call classifier; it wraps raw LLM content as a synthetic `route_label`. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:677-689`.
