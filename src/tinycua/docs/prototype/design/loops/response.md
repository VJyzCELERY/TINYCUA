# Response Node

**Status**: Code-only reconstruction

`ResponseNode` is a terminal `ProcessNode` used as the default terminal node for queue bootstrap. Evidence: `src/tinycua/tinycua/loops/response_node.py:15-27`.

It defaults to `node_id="response"`, `NodeConfigBase()` when no config is supplied, instruction `Generate the final response.`, and `is_terminal=True`. Evidence: `src/tinycua/tinycua/loops/response_node.py:29-48`.

Direct `__call__()` delegates to `ProcessNode.__call__()` and captures result content. Evidence: `src/tinycua/tinycua/loops/response_node.py:50-65`.

In the loop path, terminal nodes stop queue iteration. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:198-200`.
