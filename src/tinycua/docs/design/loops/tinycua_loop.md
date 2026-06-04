# TinyCUALoop

> **Package:** `tinycua.loops.tinycua_loop`
> **Status:** Target architecture

## Role

`TinyCUALoop` is TinyCUA's SDK-compatible execution loop. It extends SDK `BaseLoop`, owns
the root session and NodeQueue, and runs TinyCUA-specific nodes using `agent._call_llm()`.

It replaces the target role of AgentGraph plus per-agent AgentLoop subclasses.

Normal node execution does not create internal SDK Agents. `CompactionStrategy` is the
explicit exception: a session compaction strategy may own/use its own Agent internally
because compaction is strategy-owned summarization, not node execution.

## Execution Flow

Always ensure QueryAnalyst is at the front of the queue and a terminal ResponseNode is at the end.

```text
TinyCUALoop.run(agent, messages, tools, override_instructions, stream):
  1. Merge SDK messages into root session input context according to session policy.
  2. Prepend or ensure TinyCUAQueryAnalystNode as the run entry node.
     - If QueryAnalyst is already current from an interrupted run, do not duplicate it.
  3. Ensure a terminal node exists at the end of the queue.
     - If an existing terminal path exists, do nothing.
     - If no terminal path exists, append default TinyCUAResponseNode.
  4. While queue is not empty:
        node = queue.current
        node_session = node.ensure_session(...)
        node_input = queue.input_for_current()
        input_messages = node.build_messages(root_session, node_input)
        instructions = node.build_instruction(override_instructions)
        scoped_tools = node.tool_policy.resolve(node_tools, outer_agent_tools=tools)
        result = call/stream agent._call_llm(input_messages, scoped_tools)
        validate/retry according to node retry policy
        record chat history and selected session context
        node.on_complete(queue, result)
  5. Return final TinyCUAResponseNode string or stream events.
```

### QueryAnalyst Worker-Route Rule

When `QueryAnalyst` routes to `worker`:
- If an existing `WorkerNode` is already queued before the terminal `ResponseNode`, do not spawn a new `WorkerNode`. Forward/assign the current `NodeInput` to the existing `WorkerNode`. Advance/remove `QueryAnalyst`.
- If no `WorkerNode` exists, spawn a new `WorkerNode` before the terminal `ResponseNode`.

An existing `WorkerNode` counts as part of the worker-owned queue segment for stale detection and clearing.

`node.on_complete()` is responsible for all queue transitions. It calls
`queue.advance()` when the current node is finished, or performs route-specific mutations
such as spawning, clearing, or suspension/prepend. The loop never calls `advance()` after
`on_complete()`; it simply re-reads `queue.current` on the next iteration.

## SDK Messages

SDK-provided `messages` are input context. TinyCUA MUST merge/record them into the root
session according to dedupe and provenance rules. The current external user query is
already included by SDK `Agent.run`.

## Streaming

When `stream=True`, LLM/tool events from every node are visible to the caller. TinyCUA
lifecycle events are controlled separately by `NodeStreamPolicy.emit_internal_events`.

## Monitor Hook

`AgentMonitor` / `NodeMonitor` is an optional transient hook, not a durable queue node.

Trigger points:

1. before a node LLM call, after `build_messages()` and tool resolution
2. after a node LLM/tool result, before validation/retry handling
3. after retry exhaustion, before failure propagation

Inputs include node id/name, session id, attempt number, resolved tools, LLM-bound
messages, raw result or validation error, and stream mode. The hook may return an
assistant-role continuation message or no-op. Returned continuations enter the retry or
next-attempt message flow according to `NodeRetryPolicy`.

Monitor hook invocations are transient: they are not queue nodes, do not create sessions,
and are not written to `chat_history` or `session_context` unless the owning node
explicitly records a derived message according to its normal recording policy.

## Error Handling

Loop/node errors should be handled without changing SDK APIs. Common cases include
invalid node output after retry exhaustion, unknown route labels, invalid NodeInput or
NodePayload targets, tool scope violations, missing terminal response, and SDK stream
cancellation.

Fatal node failures should write failure state to the node session and propagate failure
according to `PropagationRule`.

## Related

- [`base_loop.md`](base_loop.md)
- [`node_queue.md`](node_queue.md)
- [`node.md`](node.md)
