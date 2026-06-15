# Tool Constants and Node Tool Scope

**Status**: Code-only reconstruction

## Observed implementation

Tool scope factories return `NodeToolPolicy` objects. Evidence: `src/tinycua/tinycua/config/tool_scopes.py:30-212`.

| Factory | Node tools | Outer agent tools |
|---------|------------|-------------------|
| `query_analyst_tool_scope()` | `task_inspect` | none |
| `information_digester_tool_scope()` | `enhanced_context_retrieval`, `digest_information` | none |
| `worker_tool_scope()` | `task_inspect` | none |
| `task_create_tool_scope()` | `task_init`, `task_create` | none |
| `task_analyzer_tool_scope(mode)` | inspect/update/decompose; init/create only in `task_recreation` | none |
| `task_assessor_tool_scope()` | `task_inspect`, `task_update` | none |
| `task_executor_tool_scope()` | execute/result/context/todo tools | selected `web_search`, `file_read`, `calculator` |
| `result_reviewer_tool_scope()` | `task_result_update` | none |
| `result_aggregation_tool_scope()` | `task_inspect` | none |
| `response_tool_scope(allow_digest)` | final response/context/todo plus optional digest | selected `web_search`, `file_read`, `calculator` |

## Integration status

The factories exist and tests verify their policies, but default node constructors generally receive a `NodeConfigBase` from callers; the public factory does not visibly apply these scopes. Evidence: `src/tinycua/tinycua/factory.py:45-55`, `src/tinycua/tests/integration/test_tool_scoping_integration.py:30-326`.
