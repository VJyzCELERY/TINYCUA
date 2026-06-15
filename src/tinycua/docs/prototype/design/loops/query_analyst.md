# Query Analyst Node

**Status**: Code-only reconstruction

`TinyCUAQueryAnalystNode` is a `DecisionNode` with route labels `worker`, `uncertain`, and `passthrough`. Evidence: `src/tinycua/tinycua/loops/query_analyst.py:31-70`.

On the worker route, it creates a `TinyCUAWorkerNode`, attaches a new `Session` to it, optionally skips digestion if the worker already has `DigestedInformation`, otherwise spawns `TinyCUAInformationDigesterNode` followed by the worker. Evidence: `src/tinycua/tinycua/loops/query_analyst.py:72-112`.

`on_complete()` dispatches only exact route labels from the response. Evidence: `src/tinycua/tinycua/loops/query_analyst.py:170-197`.

Review note: because loop execution creates a synthetic `DecisionResult` from raw LLM content, query analyst routing depends on the loop LLM output matching these route labels. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:677-689`.
