# Todo Tools

**Status**: Code-only reconstruction

`TodoReadTool` and `TodoWriteTool` are name-only `Tool` subclasses named `todo_read` and `todo_write`. Evidence: `src/tinycua/tinycua/tools/todo_tools.py:11-22`.

They are included in task executor and response scopes. Evidence: `src/tinycua/tinycua/config/tool_scopes.py:133-152`, `src/tinycua/tinycua/config/tool_scopes.py:186-212`.

The in-memory todo model is `Todo` / `TodoItem`. Evidence: `src/tinycua/tinycua/models/todo.py:9-98`.
