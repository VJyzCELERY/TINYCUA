# Loop Overview

**Status**: Code-only reconstruction

## High-level flow

```text
Agent.run(query)
  -> TinyCUALoop.run(agent, messages, tools, stream)
  -> NodeQueue current node
  -> _prepare_node()
  -> agent._call_llm(...)
  -> _record_node_output()
  -> node.on_complete(...)
  -> propagate_on_termination(...)
  -> queue.advance()
```

Evidence: `src/tinycua-sdk/tinycua_sdk/agent/agent.py:204-243`, `src/tinycua/tinycua/loops/tinycua_loop.py:94-206`, `src/tinycua/tinycua/loops/tinycua_loop.py:591-702`.

## Intended pipeline present in code

The code defines `QueryAnalyst -> InformationDigester -> Worker -> TaskCreate/future nodes -> Response`, and tests manually exercise this flow. Evidence: `src/tinycua/tinycua/loops/query_analyst.py:72-112`, `src/tinycua/tests/unit/test_pipeline_integration.py:200-285`.

## Actual default public path

The public factory path creates an empty queue and a default terminal node, so it appears to run only `ResponseNode` unless a custom queue is provided. Evidence: `src/tinycua/tinycua/factory.py:45-55`, `src/tinycua/tinycua/loops/node_queue.py:186-200`.
