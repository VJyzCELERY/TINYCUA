# Worker Result Model

**Status**: Code-only reconstruction

No dedicated `WorkerResult` model was found in `src/tinycua/tinycua/models/` during code exploration.

The worker currently communicates through route labels, `DecisionResult`, and propagated `DigestedInformation`. Evidence: `src/tinycua/tinycua/loops/worker.py:34-40`, `src/tinycua/tinycua/loops/node.py:78-94`, `src/tinycua/tinycua/loops/worker.py:93-108`.
