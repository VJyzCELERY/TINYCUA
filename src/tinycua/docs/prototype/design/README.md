# TinyCUA Prototype Design Reconstruction

**Status**: Code-only reconstruction  
**Last updated**: 2026-06-15  
**Constraint**: This tree mirrors the file structure of `src/tinycua/docs/design/`, but the content is reconstructed from implementation and tests only.

## File structure mirror

```text
design/
├── README.md
├── config/
│   ├── node_config.md
│   └── session_config.md
├── constants/
│   ├── instructions.md
│   └── tools.md
├── loops/
│   ├── analysis_effort.md
│   ├── base_loop.md
│   ├── expected_scenarios.md
│   ├── information_digester.md
│   ├── node.md
│   ├── node_queue.md
│   ├── overview.md
│   ├── propagation.md
│   ├── query_analyst.md
│   ├── response.md
│   ├── result_aggregation.md
│   ├── result_reviewer.md
│   ├── route_map.md
│   ├── task_analyzer.md
│   ├── task_assessor.md
│   ├── task_create.md
│   ├── task_executor.md
│   ├── tinycua_loop.md
│   ├── worker.md
│   └── worker_concept.md
├── models/
│   ├── agent_state.md
│   ├── chat_record.md
│   ├── classification.md
│   ├── digested_information.md
│   ├── execution_log.md
│   ├── information.md
│   ├── reviewer_decision.md
│   ├── session.md
│   ├── state_object.md
│   ├── state_store.md
│   ├── task.md
│   ├── todo.md
│   └── worker_result.md
├── tools/
│   ├── digester.md
│   ├── task.md
│   └── todo.md
└── utility/
    └── compaction.md
```

## Code-only headline

The implementation contains a multi-node prototype pipeline, but the public `create_tinycua_agent()` path currently constructs an empty `NodeQueue` plus a default terminal `ResponseNode`. `TinyCUALoop.run()` then appends the terminal node through `ensure_terminal()`, so the default CLI/factory path appears to execute a direct response node unless callers supply a custom queue.

Evidence: `src/tinycua/tinycua/factory.py:45-55`, `src/tinycua/tinycua/loops/tinycua_loop.py:61-65`, `src/tinycua/tinycua/loops/tinycua_loop.py:131-133`, `src/tinycua/tinycua/loops/node_queue.py:186-200`.
