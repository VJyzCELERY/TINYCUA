# Worker Concept

**Status**: Code-only reconstruction

The implemented worker is a routing hub that consumes `DigestedInformation` and selects a route among task creation, recreation, reanalysis, passthrough, and execution. Evidence: `src/tinycua/tinycua/loops/worker.py:23-68`.

The query analyst worker route creates a worker with a fresh `Session`, optionally inserts an information digester before it, and spawns both after the current node. Evidence: `src/tinycua/tinycua/loops/query_analyst.py:89-112`.

The end-to-end test manually transfers digest state from digester to worker and from worker to task create. Evidence: `src/tinycua/tests/unit/test_pipeline_integration.py:257-285`.
