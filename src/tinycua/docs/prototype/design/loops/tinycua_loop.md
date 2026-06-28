# TinyCUALoop

**Status**: Code-only reconstruction

## Responsibilities

`TinyCUALoop` owns the root session, node queue, session config, optional default terminal node, optional monitor, working transcript messages, and usage events. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:42-69`.

## Run bootstrap

`run()` copies SDK messages to `root_session.input_context`, wires a queue reference into the query analyst when it is current, appends a default terminal node when configured, then dispatches to sync or streaming execution. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:119-138`.

## Sync execution

`_run_sync()` loops over `queue.current`, prepares the node, executes it, appends transcript messages, stops on terminal nodes, and otherwise advances the queue. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:140-206`.

## Streaming execution

`_run_stream()` emits lifecycle events, streams SDK events, captures deltas/tool calls/usage, finalizes each node, and handles terminal output. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:403-589`.

## Important divergence

`_execute_node()` directly invokes `agent._call_llm()` and builds synthetic `DecisionResult` objects for decision nodes; it does not call `ProcessNode.__call__()` or `DecisionNode.__call__()`. Evidence: `src/tinycua/tinycua/loops/tinycua_loop.py:624-689`.
