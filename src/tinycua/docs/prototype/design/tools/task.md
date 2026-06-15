# Task Tools

**Status**: Code-only reconstruction

Task tools currently define names only and inherit `Tool` behavior without concrete `__call__()` implementations in these classes.

Implemented names:

- `task_init`
- `task_create`
- `task_inspect`
- `task_update`
- `task_decompose`
- `task_execute`
- `task_result_update`
- `final_response_synthesis`

Evidence: `src/tinycua/tinycua/tools/task_tools.py:12-65`.

Tool scopes arrange these names by node role. Evidence: `src/tinycua/tinycua/config/tool_scopes.py:30-212`.
