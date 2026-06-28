# DigestedInformation Model

**Status**: Code-only reconstruction

`DigestedInformation` is a dataclass containing `context_summary`, `key_points`, `advisory_instructions`, `constraints`, `known_gaps`, and `original_query`. Evidence: `src/tinycua/tinycua/models/digested_information.py:8-30`.

It has a `fallback(original_query)` constructor used when no useful context is found. Evidence: `src/tinycua/tinycua/models/digested_information.py:32-53`.

`has_useful_context` is true when key points, advisory instructions, or constraints exist. Evidence: `src/tinycua/tinycua/models/digested_information.py:55-58`.

Produced by `TinyCUAInformationDigesterNode` and consumed by `TinyCUAWorkerNode`/`TinyCUATaskCreateNode`. Evidence: `src/tinycua/tinycua/loops/information_digester.py:70-128`, `src/tinycua/tinycua/loops/worker.py:70-91`, `src/tinycua/tinycua/loops/task_create.py:84-125`.
