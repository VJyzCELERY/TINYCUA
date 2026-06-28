# Tool Constants and Node Tool Scope

**Status**: Code-only reconstruction

## Observed implementation

Tool scope factories return `NodeToolPolicy` objects. Evidence: `src/tinycua/tinycua/config/tool_scopes.py:30-259`.

| Factory | Node tools | Outer agent tools |
|---------|------------|-------------------|
| `query_analyst_tool_scope()` | `task_inspect` | none |
| `information_digester_tool_scope()` | `enhanced_context_retrieval`, `digest_information` | `EXPLORATORY_AGENT_TOOLS` |
| `worker_tool_scope()` | `task_inspect` | none |
| `task_create_tool_scope()` | `task_init` | none |
| `task_analyzer_tool_scope(mode)` | inspect/update/decompose; init/create only in `task_recreation` | `EXPLORATORY_AGENT_TOOLS` |
| `task_assessor_tool_scope()` | `task_inspect`, `node_handoff` | `EXPLORATORY_AGENT_TOOLS` |
| `task_executor_tool_scope()` | execute/result/context/todo tools | `web_search`, `fetch_url`, `read_file`, `write_file`, `edit_file`, `list_files`, `run_shell`, `run_python` |
| `result_reviewer_tool_scope()` | `task_review_decision`, `task_inspect`, `task_update` | `EXPLORATORY_AGENT_TOOLS` |
| `result_aggregation_tool_scope()` | `task_inspect` | `EXPLORATORY_AGENT_TOOLS` |
| `response_tool_scope(allow_digest)` | final response/context/todo plus optional digest | `web_search`, `fetch_url`, `read_file`, `write_file`, `edit_file`, `list_files`, `run_shell`, `run_python` |

## Tool categories

| Category | Tools | Description |
|----------|-------|-------------|
| `EXPLORATORY_AGENT_TOOLS` | `read_file`, `list_files`, `run_shell_readonly`, `web_search`, `fetch_url` | Strictly read-only, non-internal. Used by information-gathering and assessment nodes. |

## Integration status

The factories exist and tests verify their policies, but default node constructors generally receive a `NodeConfigBase` from callers; the public factory does not visibly apply these scopes. Evidence: `src/tinycua/tinycua/factory.py:45-55`, `src/tinycua/tests/integration/test_tool_scoping_integration.py:30-326`.
