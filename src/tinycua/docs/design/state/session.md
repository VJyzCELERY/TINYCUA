# Session

> **File:** `docs/design/state/session.md`
> **Package:** `tinycua.state.session`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

Our `Session` extends the **existing** `Session(StateObject)` from `tinycua.state.session`.
The existing class provides `session_id`, `name`, `chat_history`, `context`, and
`execution_log`. Our design adds:

| Concern | Where |
|---------|-------|
| Own agent state | `agent_state: AgentState` — this session's state; also stores `agent_config` for context window |
| Transient flag | `is_transient: bool` — if True, never registered in `child_sessions` (only `parent_id` set); nothing propagates upward on termination |
| Shared task | `task: Task \| None` — all sessions in the tree reference the **same** Task object |
| Tree structure | `parent_id`, `child_sessions`, `_parent` |
| Active session | `get_active_session()` — DFS pre-order |
| Filtered messages | `session_context` (vs raw `chat_history`) |
| Compaction | `_check_compaction()` triggered on every session_context mutation; `compaction_strategy` is serializable |
| Token tracking | `total_token_usage` (persistent) + `active_token_usage` (session-context) |
| Child lifecycle | `add_child()`, `terminate_child()`, `can_terminate()` |
| Propagation rules | Natural termination: final response only. Mid-progress: entire session_context. Transient: nothing (child never in tree). |
| Transient tree rule | `is_transient=True` → `parent_id` + `_parent` set, but NOT in `parent.child_sessions` | Tree traversal skips transient nodes; they don't block parent termination |

```
Session tree (hierarchical parent-child structure):

  TinyCUA (root)
   ├── Worker
   │   ├── TaskCreator   (→ TaskAnalyzer → TaskAssessor)
   │   ├── TaskExecutor
   │   └── ResultReviewer
   └── PrimaryAgent

╔══════════════════════════════════════════════════════════════════╗
║ Transient sessions (NOT in tree — only parent_id set):          ║
║   QueryAnalyst                                                  ║
║   InformationDigester                                           ║
╚══════════════════════════════════════════════════════════════════╚

Active session is determined by DFS pre-order traversal.

This tree reflects session nesting (ownership), not TinyCUA's orchestration order.
TinyCUA spawns children sequentially — in practice children would typically be
siblings, not nested. The nesting structure exists for edge cases where a
child agent internally spawns its own child session.
```

---

## Class Contract

**File:** `tinycua/state/session.py`

```python
from dataclasses import dataclass, field
from typing import Any

from tinycua.state.base import StateObject
from tinycua.state.agent_state import AgentState
from tinycua.state.task import Task


@dataclass
class Session(StateObject):
    """A node in the session tree — extends the existing Session class.

    The existing Session (from tinycua.state.session) provides:
        session_id, name, type, chat_history, context, execution_log

    Our design adds:
        - agent_state (this session's own AgentState, including agent_config)
        - is_transient (transient agents propagate nothing on termination)
        - task (shared Task object, all sessions reference the same tree)
        - Tree structure (parent_id, child_sessions, _parent)
        - session_context (filtered messages for LLM, vs raw chat_history)
        - Compaction (_check_compaction triggered on every context mutation;
          compaction_strategy injected as serializable strategy)
        - Child lifecycle (add_child / terminate_child with dual propagation rules)
    """

    # ── From existing Session ─────────────────────────────────────────
    session_id: str
    name: str = ""
    chat_history: list[dict[str, Any]] = field(default_factory=list)
    context: str = ""
    execution_log: Any = None  # ExecutionLog | None

    # ── Own agent state (our addition) ────────────────────────────────
    agent_state: AgentState | None = None
    # Each session stores ONLY its own agent's state.
    # Root (TinyCUA) → agent_state tracks overall system lifecycle.
    # agent_state.agent_config provides the context window for compaction.

    # ── Transient flag (our addition) ─────────────────────────────────
    is_transient: bool = False
    # If True: output by-design consumed by next agent, not persisted.
    # Rule: never registered in parent.child_sessions, only parent_id set.
    # On termination: nothing propagates to parent (not chat_history,
    # not session_context). Used for QueryAnalyst, InformationDigester.

    # ── Compaction strategy (our addition) ────────────────────────────
    compaction_strategy: BaseCompaction | None = None
    # Serialized with the session. Passed as summarize_fn to compact().
    # Subclasses can store persistent data (snapshots, checkpoints).

    # ── Token tracking (our addition) ─────────────────────────────────
    total_token_usage: dict[str, int] | None = None
    # Persistent, accumulates forever (like chat_history). Survives
    # compaction. Child totals propagate upward on terminate_child().

    active_token_usage: dict[str, int] | None = None
    # Dynamic, based on the current session_context. Reset on compaction.
    # Represents the token footprint of the active message window.

    # ── Shared task (our addition) ────────────────────────────────────
    task: Task | None = None
    # Parent and all children reference the SAME Task object.
    # Only the root session creates it; children receive it by reference.
    # Use get_active_task() to advance to the next executable node.

    # ── Tree structure (our addition) ─────────────────────────────────
    parent_id: str | None = None
    child_sessions: list["Session"] = field(default_factory=list)
    # FIFO queue. Children are processed in insertion order.
    # Realistically at most 1 child is active at a time
    # (sequential execution model).

    # ── Filtered messages (our addition) ──────────────────────────────
    session_context: list[dict[str, Any]] = field(default_factory=list)
    compaction_count: int = 0

    # Hidden parent reference
    _parent: "Session | None" = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        """Establish parent references on children."""
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

    def get_active_session(self) -> "Session":
        """Return the currently active session — determined by DFS pre-order.

        If this session has no children, it IS the active session.
        Otherwise, the first child (head of the FIFO queue) is visited next.
        """
        if not self.child_sessions:
            return self
        # FIFO: first child added is first to be processed.
        # In practice only 1 child exists at a time (sequential execution),
        # but the queue handles nested child agents.
        return self.child_sessions[0].get_active_session()

    def set_parents(self) -> None:
        """Re-establish _parent references after deserialization.
        Walk the tree to restore hidden parent links.
        """
        for child in self.child_sessions:
            child._parent = self
            child.set_parents()

    # ── Child session lifecycle ─────────────────────────────────────

    def add_child(self, child: "Session") -> None:
        """Append a child session to the FIFO queue.

        Transient children (is_transient=True): parent_id and _parent are set,
        and task is shared, but the child is NOT registered in child_sessions.
        This means transient children:
          - Don't appear in tree navigation (get_active_session)
          - Don't block parent termination (can_terminate)
          - Don't affect compaction decisions as depth

        Non-transient children are appended to child_sessions as normal.
        """
        child._parent = self
        child.parent_id = self.session_id
        child.task = self.task  # shared reference
        if not child.is_transient:
            self.child_sessions.append(child)

    def terminate_child(self, child: "Session") -> None:
        """Terminate a child session. Propagation depends on termination type.

        Precondition: child.can_terminate() is True (no active grandchildren).

        Propagation rules:
          - Transient agents (is_transient=True): nothing propagates.
            (child was never in child_sessions, so no removal needed.)
          - Natural termination (agent_state.status == "terminated"):
              chat_history + final response (session_context[-1]) propagate.
          - Mid-progress termination (agent_state.status != "terminated"):
              chat_history + entire session_context propagate.
        """
        if not child.can_terminate():
            raise SessionError(
                f"Cannot terminate child session {child.session_id}: "
                f"has active child sessions"
            )

        # Transient agents: skip everything (never in child_sessions)
        if child.is_transient:
            return

        # Always merge chat_history upward
        self.chat_history.extend(child.chat_history)

        # Merge total token usage upward
        if child.total_token_usage and self.total_token_usage:
            for key, value in child.total_token_usage.items():
                self.total_token_usage[key] = (
                    self.total_token_usage.get(key, 0) + value
                )
        elif child.total_token_usage:
            self.total_token_usage = dict(child.total_token_usage)

        # Session_context propagation depends on termination type
        is_natural = (
            child.agent_state
            and child.agent_state.status == "terminated"
        )
        if is_natural and child.session_context:
            # Natural: propagate only the final response
            self.session_context.append(child.session_context[-1])
        elif not is_natural and child.session_context:
            # Mid-progress: propagate entire session_context
            self.session_context.extend(child.session_context)

        # Remove from queue
        self.child_sessions.remove(child)

        # Check compaction after receiving propagated context
        self._check_compaction()

    def can_terminate(self) -> bool:
        """True if this session has no active child sessions.

        A session can only be terminated when all its children have
        been terminated first (bottom-up termination).
        """
        return len(self.child_sessions) == 0

    # ── Shared task access ──────────────────────────────────────────

    def get_active_task(self) -> Task | None:
        """Return the next executable task, advancing the shared tree.

        Calls self.task.traverse() if a task is set. Returns None if no
        task is active or the tree is fully completed.

        Since task is shared, advancing it on any session moves the
        pointer for all sessions in the tree.
        """
        if self.task is None:
            return None
        self.task = self.task.traverse()
        return self.task

    # ── Messages ────────────────────────────────────────────────────

    def append_user(self, content: str) -> None:
        """Append a user turn. Always added to both histories."""
        turn = {"role": "user", "content": content}
        self.chat_history.append(turn)
        self.session_context.append(turn)
        self._check_compaction()

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
        self._check_compaction()

    def get_messages(self) -> list[dict[str, Any]]:
        """Return session_context as the messages list for Agent.run()."""
        return list(self.session_context)

    def get_chat_history(self) -> list[dict[str, Any]]:
        """Return the complete chat_history for storage."""
        return list(self.chat_history)

    # ── Compaction ──────────────────────────────────────────────────

    def _check_compaction(self) -> None:
        """Delegate compaction check to the stored strategy.

        The strategy owns the policy: context window derivation, token
        estimation, threshold comparison, and when to trigger compaction.
        Session only calls the strategy — it has no compaction logic.

        Called automatically after every session_context mutation:
        append_user(), append_assistant(), terminate_child().
        """
        if self.compaction_strategy is not None:
            self.compaction_strategy.check_compaction(self)

    def compact(self) -> None:
        """Replace session_context with a single summarized turn.

        Delegates to self.compaction_strategy.__call__() — the strategy
        compresses session_context and returns the summary.

        Reset active_token_usage on compaction (the active window changed).
        chat_history and total_token_usage are never modified.
        """
        summary = self.compaction_strategy(self.session_context)
        self.session_context = [
            {"role": "user", "content": summary}
        ]
        self.compaction_count += 1

    # ── Serialization ───────────────────────────────────────────────

    # Inherited from StateObject:
    #   to_dict() / from_dict() / to_json() / from_json()
    # dataclasses.asdict() recursively serializes all fields including
    # nested StateObject subclasses (task, agent_state, child_sessions).

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
# _check_compaction() was automatically called during append calls
```

### Transient agent (QueryAnalyst)
```python
# QueryAnalyst auto-creates its session, marks it transient:
analyst = QueryAnalyst(config)
analyst.session.is_transient = True  # nothing propagates on termination

# Parent links it, runs it, terminates it:
self.session.add_child(analyst.session)
async for event in analyst.run(user_query):
    yield event
self.session.terminate_child(analyst.session)
# Nothing was propagated — analyst was transient.

# CEQ is passed directly to the next agent, not stored:
next_agent.run(analyst.state.context_enhanced_query)
```

### Regular agent (PrimaryAgent)
```python
# PrimaryAgent auto-creates its session (is_transient defaults to False):
primary = PrimaryAgent(config)
self.session.add_child(primary.session)
# ... run + terminate ...
self.session.terminate_child(primary.session)

# Natural termination: chat_history + final response propagated
# Mid-progress: chat_history + entire session_context propagated
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| One session per agent | Each Session holds its own `agent_state` | No central `states` dict — walk the tree to find who's active |
| Active session via DFS | `get_active_session()` DFS pre-order | Sequential execution means at most 1 active child |
| Shared Task object | `task` field references same object across tree | All agents work on the same task tree; no need to sync |
| Bottom-up termination | `can_terminate()` blocks until children are done | Child agents must finish first; guarantees clean teardown |
| Transient agents | `is_transient=True` → not in `child_sessions`; nothing propagates | QueryAnalyst, InformationDigester: output consumed by next agent inline; parent_id set for reference but tree traversal skips them |
| Chat history always propagates | `terminate_child()` always merges `chat_history` | Full audit trail available at root (except transient agents) |
| Natural termination: final response only | `session_context[-1]` propagated if `status == "terminated"` | Only the result matters; intermediate context is noise |
| Mid-progress termination: full context | Entire `session_context` propagated if `status != "terminated"` | Interrupted agent's full context needed for recovery |
| Compaction trigger | `_check_compaction()` delegates to `self.compaction_strategy.check_compaction(self)` | Strategy owns the policy; Session just delegates |
| Compaction strategy | `Session.compaction_strategy: BaseCompaction` | Serialized with session; callable; extensible via subclass |
| Compaction policy in strategy | `check_compaction(session)` on BaseCompaction | Strategy decides context window, thresholds, token estimation |
| Re-parent after deserialization | `set_parents()` in `from_dict()` | `_parent` excluded from serialization; re-established on load |
| Token usage: persistent | `total_token_usage` on Session | Survives compaction; propagates upward with chat_history; never resets |
| Token usage: active | `active_token_usage` on Session | Based on current session_context; reset on compaction; reflects active window |
| Consecutive assistant messages allowed | chat_history format | Sessions may receive multiple child results in sequence |
| Self-serializing | Inherited `StateObject.to_dict()` / `from_dict()` | `dataclasses.asdict()` handles everything; only `set_parents()` override needed |


---


---


---

## See also

Prev : [`ExecutionLog` + `ExecutionLogEntry`](execution_log.md) | Next : [Continuation State Store](state_store.md)


## Related

- [Session.agent_state per node](agent_state.md)
- [Session.task — shared Task object](task.md)
- [Persistence backend for Session](state_store.md)
- [Compaction strategy stored on Session](../utility/compaction.md)
- [Orchestrators hold self.session](../agents/base.md)
