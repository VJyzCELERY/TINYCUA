# Propagation

> **Package:** `tinycua.loops.propagation`
> **Status:** Target architecture

## Role

Propagation controls what crosses node/session boundaries. It preserves the useful old
`Session.terminate_child(...)` behavior while making it explicit and configurable.

```text
PropagationRule
  · chat_history: none | parent | root
  · session_context_target: none | parent | root | parent_and_root
  · session_context_mode: none | final | full | selected
  · token_usage: none | parent | root | parent_and_root
  · failure: none | parent | root | parent_and_root
  · dedupe: bool
```

## Profiles

| Profile | chat_history | session_context_target | session_context_mode | token_usage | failure |
|---------|--------------|------------------------|----------------------|-------------|---------|
| transient_legacy | parent_and_root | none | none | parent_and_root | parent_and_root |
| natural_termination_legacy | parent_and_root | parent_and_root | final | parent_and_root | parent_and_root |
| mid_progress_legacy | parent_and_root | parent_and_root | full | parent_and_root | parent_and_root |
| selected_internal_output | root | root | selected | root | root |

## Segmented Session Context Model

Each node's session context is segmented for propagation:

```text
session_context = prior_context + input_segment + output_segment

on node termination:
  propagate_to_parent = session_context excluding output_segment
  forward_to_next_node = output_segment
```

- **prior_context**: Context accumulated before this node's input (inherited from
  parent propagation or previous nodes).
- **input_segment**: Records received as `NodeInput` when this node was entered.
- **output_segment**: New records produced by this node's execution.

Records carry segment metadata so implementation does not rely on index slicing:

```text
ChatRecord / SessionContextEntry
  · segment: Literal["prior", "input", "output"]
  · origin_record_id: str | None
  - source_node_id: str | None
  · source_session_id: str | None
  · created_seq: int
```

### Propagation on Node Termination

When a node completes and the queue advances:

1. **Upward propagation (to parent/root)**: The node's `session_context`
   *excluding* `output_segment` propagates to parent and/or root per the
   `PropagationRule`. This commits the node's prior context and input segment
   without duplicating the output that the next node will receive.
2. **Forwarding (to next node)**: The `output_segment` becomes the next node's
   `NodeInput`. The next node then owns it as its `input_segment` and may
   produce additional `output_segment` records.

### Terminal Output Exception

Since the final `ResponseNode` output has no successor node, `TinyCUALoop`
finalization explicitly commits/returns the terminal output. The terminal
`output_segment` is returned to the SDK caller and appended to root
`session_context` as the final durable record.

## Chat History vs Session Context

```text
chat_history    = durable append-only audit transcript (ChatRecord)
session_context = mutable, selected, deduped LLM-reusable context
```

`chat_history` records node I/O provenance and is not the LLM memory itself.
`session_context` is mutable and can compact/lose prior messages; `chat_history`
preserves provenance. Session context entries may carry `chat_record_id` references
back to durable `ChatRecord` entries for traceability.

Node input messages are not automatically stored again. Nodes store new outputs and
selected reusable context only.

## Dedupe

`ChatRecord.origin_record_id` is assigned when a record is copied, propagated, or reused
as input. New records use their own `record_id`; copied records preserve the original
record's id as `origin_record_id`.

Dedupe precedence:

1. `PropagationRule.dedupe` filters writes into parent, root, or parent-and-root
   `session_context` destinations during
   propagation.
2. `NodeMessagePolicy.dedupe_by_origin_record_id` filters the final LLM-bound node input
   before `build_messages()` returns.
3. Both compare `origin_record_id` when present, falling back to `record_id`.
4. When duplicates are found, keep the earliest existing record in the destination and
   skip later duplicates.

## Related

- [`node_queue.md`](node_queue.md)
- [`../models/session.md`](../models/session.md)

## Transient Routing Nodes

`QueryAnalyst` and `Worker` are transient routing/continuation nodes. They
assemble/receive context, decide, and forward selected output to the next node;
they generally do not backward-propagate their own output directly. Their output
becomes durable through the next node's input propagation per the segmented
context model.

```text
QueryAnalyst -> Node1 -> Node2

QueryAnalyst forwards: [user_query, QueryAnalystResponse]
Node1 context: Node1 prior + user_query + QueryAnalystResponse + Node1Output
Node1 termination: parent gets Node1 prior + user_query + QueryAnalystResponse;
                   Node2 gets Node1Output
```

This pattern applies to all transient routing nodes: their output enters the
next node's `input_segment` and only propagates upward when that next node
terminates and commits its non-output segment to the parent.
