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

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone, UTC
from typing import Any, Literal

from tinycua.state.base import StateObject


ChatRecordType = Literal[
    "agent_orchestrator",  # orchestrator-level action (routing, mode decisions)
    "agent",               # SDK Agent response text
    "tools",               # tool call or tool result
    "user",                # user input
]


@dataclass
class ChatRecord(StateObject):
    """A single entry in the session's audit trail.

    Stored in Session.chat_history — a list of ChatRecord instances.
    Propagated upward to parent on termination (including transient sessions).
    Never compacted — chat_history is append-only and survives compaction.
    """

    id: str                             # unique record ID (UUID)
    type: ChatRecordType                # category of the record
    metadata: dict[str, Any] = field(default_factory=dict)
    # Metadata schema varies by type. See per-type metadata below.
    content: dict[str, Any] = field(default_factory=dict)
    # Content schema varies by type. See per-type content below.
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
```

---

## Per-Type Metadata & Content

### `user`

User input sent to the system.

| Field | Type | Example |
|-------|------|---------|
| `metadata` | `{}` | (empty) |
| `content` | `{"query": str}` | `{"query": "How do I configure nginx?"}` |

### `agent_orchestrator`

Orchestrator-level action (routing decision, mode classification, task creation).

| Field | Type | Example |
|-------|------|---------|
| `metadata` | `{"orchestrator": str, "action": str}` | `{"orchestrator": "query_analyst", "action": "classify"}` |
| `content` | `{"result": ...}` | `{"mode": "worker", "score": 0.92}` |

### `agent`

SDK Agent's text response. The metadata SHOULD include the orchestrator that spawned
the agent and the agent's own identity.

| Field | Type | Example |
|-------|------|---------|
| `metadata` | `{"orchestrator": str, "agent_name": str, "model": str}` | `{"orchestrator": "task_analyzer", "agent_name": "task-analyzer", "model": "gpt-4o"}` |
| `content` | `{"text": str}` | `{"text": "## Task Analysis Summary\n..."}` |

### `tools`

Tool invocation or tool result.

| Field | Type | Example |
|-------|------|---------|
| `metadata` | `{"tool_name": str, "call_id": str, "direction": "call" \| "result"}` | `{"tool_name": "classify", "call_id": "abc", "direction": "call"}` |
| `content` | `{"arguments": ...}` (call) or `{"output": ...}` (result) | `{"arguments": {"mode_index": 1}}` |

---

## Integration with Session

`Session.chat_history` stores `list[ChatRecord]` (formerly `list[dict[str, Any]]`):

```python
# In Session:
chat_history: list[ChatRecord] = field(default_factory=list)

def append_user(self, content: str) -> None:
    """Append a user turn as a ChatRecord."""
    record = ChatRecord(
        id=str(uuid4()),
        type="user",
        content={"query": content},
    )
    self.chat_history.append(record)
    # session_context still uses raw dict for LLM consumption
    self.session_context.append({"role": "user", "content": content})
    self._check_compaction()

def append_assistant(
    self,
    content: str,
    tool_calls: list[dict] | None = None,
    tool_results: list[dict] | None = None,
    metadata: dict | None = None,
) -> None:
    """Append an assistant turn as ChatRecord + tool records."""
    # ChatRecord for the assistant text
    self.chat_history.append(ChatRecord(
        id=str(uuid4()),
        type="agent",
        metadata=metadata or {},
        content={"text": content},
    ))
    # ChatRecords for tool calls
    if tool_calls:
        for tc in tool_calls:
            self.chat_history.append(ChatRecord(
                id=str(uuid4()),
                type="tools",
                metadata={
                    "tool_name": tc.get("name", ""),
                    "call_id": tc.get("id", ""),
                    "direction": "call",
                },
                content={"arguments": tc.get("arguments", {})},
            ))
    # ChatRecords for tool results
    if tool_results:
        for tr in tool_results:
            self.chat_history.append(ChatRecord(
                id=str(uuid4()),
                type="tools",
                metadata={
                    "tool_name": tr.get("name", ""),
                    "call_id": tr.get("id", ""),
                    "direction": "result",
                },
                content={"output": tr.get("output", {})},
            ))
    # session_context still uses raw dict for LLM consumption
    self.session_context.append({"role": "assistant", "content": content})
    self._check_compaction()
```

**Key separation:**
- `chat_history` → `ChatRecord` instances (structured audit, survives everything)
- `session_context` → `{"role": ..., "content": ...}` dicts (LLM-compatible, compacted)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Typed record | `ChatRecord(StateObject)` | Serialization + type safety; no loose dicts |
| Four record types | `user`, `agent_orchestrator`, `agent`, `tools` | Covers all events in execution lifecycle |
| Metadata + content separation | Two dict fields | Metadata identifies who/what; content holds the payload |
| Timestamp per record | ISO 8601 string | Chronological ordering; survives serialization |
| chat_history vs session_context | Separate lists with different formats | LLM needs role/content dicts; audit trail needs structured records |
| Orchestrator metadata on agent records | `metadata.orchestrator` on `type="agent"` ChatRecords | Traces which orchestrator spawned each agent call |
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
