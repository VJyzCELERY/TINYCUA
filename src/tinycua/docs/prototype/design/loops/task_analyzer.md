# Task Analyzer Node

**Status**: Code-only reconstruction

No concrete `TinyCUATaskAnalyzerNode` implementation was found in `src/tinycua/tinycua/loops/` during code exploration.

Related implemented surface:

- Tool scope factory `task_analyzer_tool_scope(mode)` exists and varies tool availability by mode. Evidence: `src/tinycua/tinycua/config/tool_scopes.py:94-115`.
- Tests verify task analyzer tool scopes for creation/recreation/reanalysis modes. Evidence: `src/tinycua/tests/integration/test_tool_scoping_integration.py:56-92`, `src/tinycua/tests/integration/test_tool_scoping_integration.py:310-326`.
