# Task Create Node

**Status**: Code-only reconstruction

`TinyCUATaskCreateNode` is a `ProcessNode` intended to create structured tasks from user requests and digested context. Evidence: `src/tinycua/tinycua/loops/task_create.py:15-51`.

It overrides `build_messages()` to append formatted `DigestedInformation` context if present in the session. Evidence: `src/tinycua/tinycua/loops/task_create.py:53-82`.

`_extract_digest_context()` formats context summary, key points, advisory instructions, constraints, known gaps, and original query. Evidence: `src/tinycua/tinycua/loops/task_create.py:84-125`.

Tests exercise digest formatting in `src/tinycua/tests/unit/test_pipeline_integration.py:173-198`.
