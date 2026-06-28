# Worker Node

**Status**: Code-only reconstruction

`TinyCUAWorkerNode` is a `DecisionNode` with route labels `task_creation`, `task_recreation`, `task_reanalysis`, `passthrough`, and `proceed_execution`. Evidence: `src/tinycua/tinycua/loops/worker.py:23-68`.

It scans its session context in reverse for the most recent `DigestedInformation`. Evidence: `src/tinycua/tinycua/loops/worker.py:70-91`.

If `_current_digest` is set, `propagate()` appends it as an output `SessionContextEntry`. Evidence: `src/tinycua/tinycua/loops/worker.py:93-108`.

`on_complete()` stores the currently retrievable digest in `_current_digest` for propagation. Evidence: `src/tinycua/tinycua/loops/worker.py:110-127`.
