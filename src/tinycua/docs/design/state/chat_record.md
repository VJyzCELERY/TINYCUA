# Chat Record

> **File:** `docs/design/state/chat_record.md`
> **Package:** `tinycua.state.chat_record`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`ChatRecord` is a structured entry in `Session.chat_history`. Unlike `session_context`
(which holds role/content dicts for LLM consumption), `chat_history` is a typed audit
trail — each record captures what happened, who produced it, and relevant metadata.

Records are appended by `Session.append_user()` and `Session.append_assistant()`,
and propagated upward to the parent on `terminate_child()` (including transient sessions).

---

## Class Contract

**File:** `tinycua/state/chat_record.py`

```text
ChatRecordType = "agent_graph" | "agent" | "tools" | "user"
  · agent_graph → graph-level action (routing, gates, classifications)
  · agent       → tinycua_sdk.Agent response text
  · tools       → tool call or tool result
  · user        → user input

ChatRecord <: StateObject    ── structured entry in Session.chat_history audit trail
  · id: str                            # unique record ID (UUID)
  · type: ChatRecordType               # category of the record
  · metadata: dict[str, Any]           # schema varies by type
  · content: dict[str, Any]            # schema varies by type
  · timestamp: str                     # ISO 8601, auto-generated

chat_history is append-only — never compacted. Propagates upward on terminate_child()
(including transient sessions).
```

---

## Per-Type Metadata & Content

### `user`

User input sent to the system.

| Field | Type | Example |
|-------|------|---------|
| `metadata` | `{}` | (empty) |
| `content` | `{"query": str}` | `{"query": "How do I configure nginx?"}` |

### `agent_graph`

Graph-level action (routing decision, gate output, task creation).

| Field | Type | Example |
|-------|------|---------|
| `metadata` | `{"graph_node": str, "action": str}` | `{"graph_node": "input_gate", "action": "route"}` |
| `content` | `{"result": ...}` | `{"classification": "worker"}` |

### `agent`

SDK Agent's text response. The metadata SHOULD include the AgentNode that spawned
the agent and the agent's own identity.

| Field | Type | Example |
|-------|------|---------|
| `metadata` | `{"agent_node": str, "agent_name": str, "model": str}` | `{"agent_node": "task_analyzer", "agent_name": "task-analyzer", "model": "gpt-4o"}` |
| `content` | `{"text": str}` | `{"text": "## Task Analysis Summary\n..."}` |

### `tools`

Tool invocation or tool result.

| Field | Type | Example |
|-------|------|---------|
| `metadata` | `{"tool_name": str, "call_id": str, "direction": "call" \| "result"}` | `{"tool_name": "classify", "call_id": "abc", "direction": "call"}` |
| `content` | `{"arguments": ...}` (call) or `{"output": ...}` (result) | `{"arguments": {"classification_index": 1}}` |

---

## Integration with Session

`Session.chat_history` stores `list[ChatRecord]` (formerly `list[dict[str, Any]]`):

```text
# In Session:
chat_history: list[ChatRecord]

append_user(content: str) → None:
    · ChatRecord(id, type="user", content={"query": content}) → chat_history
    · {"role": "user", "content": content} → session_context
    · _check_compaction()

append_assistant(content: str, tool_calls?, tool_results?, metadata?) → None:
    · ChatRecord(id, type="agent", metadata, content={"text": content}) → chat_history
    · for each tool_call: ChatRecord(type="tools", direction="call") → chat_history
    · for each tool_result: ChatRecord(type="tools", direction="result") → chat_history
    · {"role": "assistant", "content": content} → session_context (text only, no tool calls)
    · _check_compaction()
```

**Key separation:**
- `chat_history` → `ChatRecord` instances (structured audit, survives everything)
- `session_context` → `{"role": ..., "content": ...}` dicts (LLM-compatible, compacted)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Typed record | `ChatRecord(StateObject)` | Serialization + type safety; no loose dicts |
| Four record types | `user`, `agent_graph`, `agent`, `tools` | Covers all events in execution lifecycle |
| Metadata + content separation | Two dict fields | Metadata identifies who/what; content holds the payload |
| Timestamp per record | ISO 8601 string | Chronological ordering; survives serialization |
| chat_history vs session_context | Separate lists with different formats | LLM needs role/content dicts; audit trail needs structured records |
| AgentNode metadata on agent records | `metadata.agent_node` on `type="agent"` ChatRecords | Traces which AgentNode spawned each agent call |
| Internal queries not stored | Only `Agent.run()` RESPONSES recorded, never the queries | Queries are internal orchestration detail; only outputs matter for context |
| `user` role only for real input | Only user messages sent to QueryAnalyst get `role="user"` in session_context | Internal agent queries are not user messages — they don't affect context |
| Append-only | Never compacted, never truncated | chat_history is the canonical log; survives compaction |


---


---


---

## See also

Prev : [Design `Session`](session.md) | Next : [Continuation State Store](state_store.md)


## Related

- [Stored on Session.chat_history](session.md)
- [Propagated upward on terminate_child()](session.md)
- [session_context holds LLM-compatible dicts](session.md)
