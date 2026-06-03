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

```text
TinyCUALoop.run(agent, messages, tools, override_instructions, stream):
  1. Merge SDK messages into root session context according to session policy.
  2. Ensure NodeQueue has an entry node and response path.
  3. While queue is not empty:
       node = queue.current
       node.ensure_session(root_session)
       input_messages = node.build_messages(...)
       instructions = node.build_instruction(override_instructions)
       scoped_tools = node.tool_policy.resolve(tools)
       response = agent._call_llm(input_messages, scoped_tools)
       node.validate_or_retry(response)
       node.record_output(response)
       node.propagate()
       node.on_complete(queue, response)
  4. Return final TinyCUAResponseNode output or stream events.
```

## SDK Messages

SDK-provided `messages` are input context. TinyCUA should merge/record them into the root
session according to dedupe and provenance rules. The current external user query is
already included by SDK `Agent.run`.

## Streaming

When `stream=True`, LLM/tool events from every node are visible to the caller. TinyCUA
lifecycle events are controlled separately by `NodeStreamPolicy.emit_internal_events`.

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
