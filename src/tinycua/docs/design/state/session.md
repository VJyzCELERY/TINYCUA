# Session

> **File:** `docs/design/state/session.md`
> **Package:** `tinycua.state.session`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

Our `Session` extends the **existing** `Session(StateObject)` from `tinycua.state.session`.
The existing class provides `session_id`, `name`, `type`, `chat_history`, `context`, and
`execution_log`. Our design adds:

| Concern | Where |
|---------|-------|
| Tree structure | `parent_id`, `child_sessions`, `_parent` |
| Filtered messages | `session_context` (vs raw `chat_history`) |
| Compaction | `compact()` + `compaction_count` |
| Active task | `task: Task \| None` — current task node, shared with children |
| State container | `states: dict[str, StateObject]` |
| Token tracking | `states["session"]: SessionTracking` |

```
Session
 ├── session_id, parent_id, child_sessions    ← tree structure
 ├── chat_history, session_context            ← messages
 └── states: {
       "session":     SessionTracking(...),
       "query_analyst": QueryAnalystState(...),
       "task_executor": TaskExecutorState(...),
       ...
     }
```

---

## Class Contract

**File:** `tinycua/state/session.py`

```python
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tinycua.state.base import StateObject
from tinycua.state.task import Task


@dataclass
class Session(StateObject):
    """A node in the session tree — extends the existing Session class.

    The existing Session (from tinycua.state.session) provides:
        session_id, name, type, chat_history, context, execution_log


    Our design adds:
        - Tree structure (parent_id, child_sessions, _parent)
        - session_context (filtered messages for LLM, vs raw chat_history)
        - states dict (flexible StateObject container)
        - Compaction (compact + compaction_count)
    """

    # ── From existing Session ─────────────────────────────────────────
    session_id: str
    name: str = ""
    type: str = "primary"  # "primary" | "child"
    chat_history: list[dict[str, Any]] = field(default_factory=list)
    context: str = ""
    execution_log: Any = None  # ExecutionLog | None

    # ── Tree structure (our addition) ─────────────────────────────────
    parent_id: str | None = None
    child_sessions: list["Session"] | None = None

    # ── Filtered messages (our addition) ──────────────────────────────
    session_context: list[dict[str, Any]] = field(default_factory=list)
    compaction_count: int = 0

    # ── Active task (our addition) ────────────────────────────────────
    task: Task | None = None  # current active task node — shared with children

    # ── State container (our addition) ────────────────────────────────
    states: dict[str, StateObject] = field(default_factory=dict)

    # Hidden parent reference
    _parent: "Session | None" = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        """Establish parent references on children."""
        if self.child_sessions is not None:
            for child in self.child_sessions:
                child._parent = self
                child.parent_id = self.session_id

    # ── Tree navigation ─────────────────────────────────────────────

    @property
    def parent(self) -> "Session | None":
        """The parent session via _parent reference."""
        return self._parent

    @property
    def is_root(self) -> bool:
        """True if this is a top-level session (no parent)."""
        return self._parent is None

    def root(self) -> "Session":
        """Walk up to the root session."""
        node = self
        while node._parent is not None:
            node = node._parent
        return node

    def set_parents(self) -> None:
        """Re-establish _parent references after deserialization.
        Walk the tree bottom-up to restore hidden parent links.
        """
        if self.child_sessions is not None:
            for child in self.child_sessions:
                child._parent = self
                child.set_parents()

    # ── Chat history propagation ─────────────────────────────────────

    def propagate_chat_history(self) -> None:
        """Append this session's complete chat_history to the parent.
        
        Called after a child session finishes. The parent inherits the
        auditable record but NOT the session_context.
        """
        if self._parent is not None:
            self._parent.chat_history.extend(self.chat_history)
            self._parent.propagate_chat_history()  # recursive upward

    # ── Turn appending ───────────────────────────────────────────────

    def append_user(self, content: str) -> None:
        """Append a user turn. Always added to both histories."""
        turn = {"role": "user", "content": content}
        self.chat_history.append(turn)
        self.session_context.append(turn)

    def append_assistant(
        self,
        content: str,
        tool_calls: list[dict] | None = None,
        tool_results: list[dict] | None = None,
    ) -> None:
        """Append an assistant turn.

        chat_history: full text + tool_calls + tool_results (verbatim).
        session_context: text only — tool calls and results are discarded
            (their effect is captured in the assistant's next response).
        """
        # Full record in chat_history
        self.chat_history.append({"role": "assistant", "content": content})
        if tool_calls:
            self.chat_history.extend(tool_calls)
        if tool_results:
            self.chat_history.extend(tool_results)

        # Filtered record in session_context
        self.session_context.append({"role": "assistant", "content": content})

    # ── Compaction ────────────────────────────────────────────────────

    def compact(self, summarize_fn: Callable[[list[dict]], str]) -> None:
        """Replace session_context with a single summarized turn.

        summarize_fn receives the current session_context and returns a
        summary string. The caller defines the compaction algorithm — the
        Session only handles the mechanical collapse.

        Called when context-window pressure is detected (background system
        process, not agent-driven). chat_history is never modified.
        """
        summary = summarize_fn(self.session_context)
        self.session_context = [
            {"role": "user", "content": summary}
        ]
        self.compaction_count += 1

    # ── Read helpers ──────────────────────────────────────────────────

    def get_messages(self) -> list[dict[str, Any]]:
        """Return session_context as the messages list for Agent.run()."""
        return list(self.session_context)

    def get_chat_history(self) -> list[dict[str, Any]]:
        """Return the complete chat_history for storage."""
        return list(self.chat_history)

    # ── Per-agent state management ──────────────────────────────────

    def set_state(self, key: str, state: StateObject) -> None:
        """Store an agent-specific state under a key.
        e.g. session.set_state("query_analyst", analyst.state)
        """
        self.states[key] = state

    def get_state(self, key: str) -> StateObject | None:
        """Retrieve an agent-specific state by key."""
        return self.states.get(key)

    # ── Active task ──────────────────────────────────────────────────

    def get_active_task(self) -> Task | None:
        """Return the next executable task, advancing self.task.

        Calls self.task.traverse() if a task is set. Returns None if no
        task is active or the tree is fully completed.
        """
        if self.task is None:
            return None
        self.task = self.task.traverse()
        return self.task

    # ── Child creation ───────────────────────────────────────────────

    def create_child(self, session_id: str) -> "Session":
        """Create a child session attached to this node.

        The child starts with clean context. When it finishes, call
        propagate_chat_history() to push its audit record upward.
        """
        child = Session(
            session_id=session_id,
            parent_id=self.session_id,
        )
        child._parent = self
        if self.child_sessions is None:
            self.child_sessions = []
        self.child_sessions.append(child)
        return child

    # ── Serialization ─────────────────────────────────────────────────

    # Inherited from StateObject:
    #   to_dict() / from_dict() / to_json() / from_json()
    # dataclasses.asdict() recursively serializes all fields including
    # nested StateObject subclasses (task, states dict values, child_sessions).

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Deserialize, then re-establish _parent references."""
        session = super().from_dict(data)
        session.set_parents()
        return session
```

---

## Integration with Agent

### Root session (TinyCUA)
```python
session = self.session_store.load(session_id)  # root session
session.append_user(user_query)

text_parts = []
async for event in agent.run(
    query=user_query,
    messages=session.get_messages(),  # session_context, not chat_history
    stream=True,
): ...

session.append_assistant(response_text)
self.session_store.save(session)
```

### Child session (Worker/internal agent)
```python
# TinyCUA creates a child for an internal worker:
child = root_session.create_child(f"{session_id}-worker-1")

# Worker runs internal agents on this child...
child.append_user(task_description)
async for event in task_executor.run(task):
    yield event
child.append_assistant(execution_result)

# Worker done — propagate chat_history upward:
child.propagate_chat_history()
# root_session.chat_history now includes child's full audit trail
# root_session.session_context is unchanged (child context NOT inherited)
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tree structure | `parent_id` + `child_sessions` + `_parent` | Mirrors Task tree; recursive nesting; upward propagation |
| Parent inherits chat_history only | `propagate_chat_history()` appends upward | Architecture rule: context is isolated per session |
| Child context is clean | `create_child()` starts empty | Internal agents don't leak into parent's model context |
| Two histories, one format | Both `list[{"role", "content"}]` | Same serialization format; simple filtering during append |
| chat_history never passed to LLM | Only `session_context` as `messages` | Full tool traces would bloat prompts; audit record stays clean |
| Compaction collapses to single turn | `session_context` → `[{"role": "user", "content": summary}]` | Preserves context continuity; model sees summary + recent turns |
| summarize_fn injected by caller | `compact(summarize_fn)` parameter | Compaction algorithm is flexible; Session only handles mechanics |
| Re-parent after deserialization | `set_parents()` in `from_dict()` | `_parent` excluded from serialization; re-established on load |
| Session is the state container | `states: dict[str, StateObject]` | All tracking and per-agent state lives in dict — no inline type fields |
| Per-agent states in dict | Keyed by agent kind | Flexible; any StateObject subclass stored by key |
| Token usage in SessionTracking | `states["session"].token_usage` | Updated from stream events; survives compaction; never reset |
| Self-serializing | Inherited `StateObject.to_dict()` / `from_dict()` | `dataclasses.asdict()` handles everything; only `set_parents()` override needed |


---

## See also

Prev : [`ExecutionLog` + `ExecutionLogEntry`](execution_log.md) | Next : [Continuation State Store](state_store.md)
