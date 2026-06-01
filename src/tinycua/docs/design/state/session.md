# Session

> **File:** `docs/design/state/session.md`
> **Package:** `tinycua.state.session`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

Our `Session` extends the **existing** `Session(StateObject)` from `tinycua.state.session`.
The existing class provides `session_id`, `name`, `chat_history`, `context`, and
`execution_log`. Our design adds graph/node state, filtered LLM messages, task sharing,
token tracking, compaction, and parent/child lifecycle management.

| Concern | Where |
|---------|-------|
| Own agent state/config | `agent_state: AgentState` — this node's lifecycle/output state and config source of truth (`agent_config`) |
| Transient flag | `is_transient: bool` — never in `child_sessions`; chat_history + token_usage propagate, session_context does NOT |
| Task | `task: Task \| None` — explicit inheritance only. Child sessions do NOT auto-inherit unless graph assigns it. |
| Task sharing scope | `share_parent_task: bool = True` — controls whether task replacement propagates through this session's task-sharing group |
| Tree structure | `parent_id`, `child_sessions`, `_parent` |
| Active graph node | `graph.queue[0]` — owned by AgentGraph, not Session |
| Filtered messages | `session_context` (vs raw `chat_history`) |
| **User-input-only rule** | **Only external human input** → `role="user"` / `type="user"`. All internal agent conversation → `role="assistant"` / `type="agent"` or `type="tools"`. Internal `Agent.run()` queries are NEVER stored. |
| **TodoList** | `todo_list: list[dict]` — per-session short-term goal tracking. Each item: `{"status": "completed" \| "incomplete", "todo": str}`. Distinct from Task Tree. |
| Failure propagation | `agent_state.failure` accumulates child failures on termination: `parent.failure += child.failure` |
| Compaction | `_check_compaction()` triggered on every session_context mutation; strategy from `agent_state.agent_config.compaction_strategy` |
| Token tracking | `total_token_usage` (persistent) + `active_token_usage` (session-context) |
| Child lifecycle | `add_child()`, `terminate_child()`, `can_terminate()` |
| Propagation rules | Natural: final response only. Mid-progress: entire session_context. Transient: chat_history only (no session_context). |

```text
Session tree (hierarchical parent-child structure):

  TinyCUA root
   ├── TinyCUAWorker                 # AgentGraph subgraph, may share parent task
   │   ├── TaskAnalyzer
   │   ├── TaskAssessor
   │   ├── TaskExecutor
   │   └── ResultReviewer
   └── PrimaryAgent

╔══════════════════════════════════════════════════════════════════╗
║ Transient sessions (NOT in tree — only parent_id set):          ║
║   QueryAnalyst input gates                                      ║
║   InformationDigester                                           ║
║   Enhanced-context retrieval inner agents                       ║
╚══════════════════════════════════════════════════════════════════╝

Execution-active node is determined by the AgentGraph queue. The session tree records
persistent ownership/history; it is not the execution queue.
```

---

## Class Contract

**File:** `tinycua/state/session.py`

```text
Session <: StateObject   ── extends tinycua_sdk.state.session.Session

# ── Fields inherited from existing Session ──
  · session_id: str
  · name: str
  · chat_history: list[ChatRecord]
  · context: str
  · execution_log: ExecutionLog | None

# ── Fields added by our design ──

  · agent_state: AgentState                  # node lifecycle/output state + config
                                             #   agent_state.type identifies node kind
                                             #   agent_state.agent_config → model, compaction_strategy, extra_tools
  · is_transient: bool = False               # True → not in parent.child_sessions; chat_history propagates, session_context does NOT
  · total_token_usage: dict[str,int] | None  # persistent, survives compaction, propagates upward on terminate_child()
  · active_token_usage: dict[str,int] | None # dynamic (based on session_context), reset on compaction
  · task: Task | None                        # explicit assignment only
  · share_parent_task: bool = True           # participates in parent's task-sharing group unless set False
  · todo_list: list[dict[str,str]] | None     # per-session short-term goals
  · parent_id: str | None                    # FK to parent session
  · child_sessions: list[Session]            # persisted session tree children, not the graph execution queue
  · session_context: list[dict[str,Any]]     # filtered messages for LLM consumption
  · compaction_count: int = 0
  · _parent: Session | None                  # hidden reference, excluded from serialization
```

---

## Tree Navigation

```text
parent → Session | None
is_root → bool
root() → Session
get_active_session() → Session              # session-tree helper only; graph active node is graph.queue[0]
set_parents() → None                        # re-establish _parent after deserialization
```

---

## Child Lifecycle

```text
add_child(child: Session) → None:
  · child._parent = self
  · child.parent_id = self.session_id
  · child.task is NOT auto-assigned (Task inheritance is explicit)
  · if NOT child.is_transient → self.child_sessions.append(child)

terminate_child(child: Session) → None:
  · precondition: child.can_terminate() is True
  · Always: child.chat_history → extend parent chat_history
  · Always: child.total_token_usage → merge into parent total_token_usage
  · Always: parent.agent_state.failure += child.agent_state.failure
  · If child.is_transient:
      session_context → NOT propagated (output consumed inline)
      return
  · Else propagation depends on child.agent_state.status:
      - Natural ("terminated"):
          session_context[-1] only (final response) → append to parent
      - Mid-progress (not "terminated"):
          entire session_context → extend parent
  · Remove child from child_sessions
  · _check_compaction()

can_terminate() → bool:
  · return len(self.child_sessions) == 0
```

### Failure propagation

`failure` is stored on `agent_state`, not on `Session` directly. The parent session
monitors aggregate failure by accumulating child failures on termination:

```text
parent.agent_state.failure += child.agent_state.failure
```

There is no global threshold. Each AgentNode decides how to interpret the aggregate
value. For example, `ResultReviewer` may implement special behavior at `failure >= 5`,
while `InformationDigester` may ignore the same value.

---

## Task Sharing and Propagation

By default, child sessions do **not** auto-inherit the parent's `Task`. A graph must
explicitly assign a shared reference:

```text
child.session.task = parent.session.task               # full shared reference
child.session.task = parent.session.task.get_active_subtree()
child.session.task = parent.session.task.get_active_task()
```

Once a shared reference exists, `share_parent_task` controls **replacement propagation**
when a node creates a new task tree.

```text
share_parent_task: bool = True
```

### Propagation algorithm

When `source_session` replaces its task with `new_task`:

```text
propagate_task_replacement(source_session, new_task):
  · Walk upward while the CURRENT session has share_parent_task=True
  · Include the parent reached through that True edge
  · If the newly reached parent has share_parent_task=False, stop before crossing to its parent
  · The highest included ancestor is the task-sharing group root
  · Replace task on every session in that group root's subtree where:
      - session is the group root, OR
      - every descendant edge is entered only through a child whose share_parent_task=True
  · Do NOT cross into any descendant with share_parent_task=False
```

### Example

```text
Node1 (share_parent_task=False)
 ├── Node2 (True)
 │    └── Node5 (True)
 ├── Node3 (True)
 └── Node4 (False)
      └── Node6 (True)
```

If `Node3` updates the task, the update propagates to `Node1`, `Node2`, and `Node5`.
It does not propagate to `Node4` because `Node4.share_parent_task=False` creates a
task-sharing boundary.

If `Node6` updates the task, the update propagates only to `Node4` and `Node6`; it
does not cross upward to `Node1` because `Node4.share_parent_task=False` cuts the group.

---

## Messages (chat_history + session_context)

```text
# RULE: ONLY external human input → "user" role/type.
#       All internal agent conversation → "agent"/"assistant" or "tools".
#       Internal Agent.run() queries are NEVER stored.

append_user(content: str) → None:
  · STRICT: only called for actual external user input (TinyCUA receives a query)
  · ChatRecord(type="user", content={"query": content}) → chat_history
  · {"role":"user", "content": content} → session_context
  · _check_compaction()

append_assistant(content, tool_calls?, tool_results?, metadata?) → None:
  · ChatRecord(type="agent", metadata={agent_node, agent_name, model}) → chat_history
  · for each tool_call: ChatRecord(type="tools", direction="call") → chat_history
  · for each tool_result: ChatRecord(type="tools", direction="result") → chat_history
  · {"role":"assistant", "content": content} → session_context
  · _check_compaction()

append_graph_action(action, result, graph_node_name?) → None:
  · ChatRecord(type="agent_graph") → chat_history ONLY

get_messages() → list[dict]:
  · return copy of session_context

get_chat_history() → list[ChatRecord]:
  · return copy of chat_history
```

### ContextEnhancedQuery safety

`ContextEnhancedQuery.to_messages()` returns user-role message dicts for temporary
LLM extension, but those messages must not be appended to `session_context` unchanged.
If CEQ context is persisted, append only the context as an assistant message and avoid
adding the query part (it should already exist from `append_user`). See
[ContextEnhancedQuery.to_messages()](mode_decision.md#contextenhancedquery-methods).

---

## Compaction

```text
_check_compaction() → None:
  · strategy = self.agent_state.agent_config.compaction_strategy
  · if strategy: strategy.check_compaction(self)
  · called after every session_context mutation

compact() → None:
  · summary = strategy(self.session_context)
  · self.session_context = [{"role":"user", "content": summary}]
  · compaction_count += 1
  · chat_history and total_token_usage NEVER modified
```

---

## Serialization

```text
Inherited from StateObject: to_dict(), from_dict(), to_json(), from_json()

from_dict(data) → Session:
  · session = super().from_dict(data)
  · session.set_parents()
  · return session
```

---

## Session as Source of Truth

AgentNodes should not duplicate config/state fields that already live on the session.
The canonical access path is:

```text
session.agent_state                 # lifecycle + node-specific output state
session.agent_state.agent_config    # AgentConfigBase source of truth
session.session_context             # messages passed to agent.run(...)
session.task                        # shared task tree reference
session.todo_list                   # short-term working memory
```

Loops receive the `Session` directly so they can update `agent_state`, append chat
history, inspect task state, and format final results without requiring the AgentNode
or AgentGraph to probe raw stream events.

---

## Integration Examples

### Root session (TinyCUA)

```text
session = session_store.load(session_id) or new root Session
session.append_user(user_query)

async for event in tinycua.run(user_query): yield event

session_store.save(session)
```

### Transient QueryAnalyst

```text
analyst = QueryAnalyst(config)
analyst.session.is_transient = True
self.session.add_child(analyst.session)

async for event in analyst.run(query=user_query): yield event
self.session.terminate_child(analyst.session)

# chat_history + token usage + failure propagated.
# session_context did NOT propagate.
# structured output is consumed inline from analyst.session.agent_state.
next_agent.run(query=analyst.session.agent_state.to_yaml() + "\n" + user_query)
```

### PrimaryAgent passthrough

```text
primary = PrimaryAgent(session=self.session)  # inherits parent session directly
async for event in primary.run(query=query_analyst_state.to_yaml() + "\n" + user_query):
    yield event

# PrimaryAgent parses QueryAnalystState, appends CEQ context as assistant,
# and runs the original user query against parent.session_context.
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| One session per persistent node | Each non-transient node has a `Session` holding its `agent_state` | Results are stored on the producing node/session |
| Active node via graph queue | AgentGraph uses `graph.queue[0]`; `get_active_session()` is only a tree helper | Execution order belongs to graph orchestration, not session-tree traversal |
| Shared Task object | `task` field references same object when explicitly assigned | Agents can work on same task tree without sync copies |
| Explicit task inheritance | `add_child()` does not copy task automatically | Prevents accidental task coupling |
| Task-sharing boundary | `share_parent_task: bool = True` | Supports scoped propagation for nested worker graphs |
| Failure propagation | `parent.failure += child.failure` | Parent monitors aggregate failure; nodes define behavior |
| Bottom-up termination | `can_terminate()` blocks until children are done | Child agents finish first; clean teardown |
| Transient agents | `is_transient=True` → not in `child_sessions`; chat_history propagates, session_context does not | QueryAnalyst/InformationDigester output consumed inline |
| Chat history always propagates | `terminate_child()` always merges `chat_history` | Full audit trail at root |
| Natural termination: final response only | `session_context[-1]` propagated if `status == "terminated"` | Only final result matters |
| Mid-progress termination: full context | Entire `session_context` propagated if `status != "terminated"` | Interrupted active node needs full recovery context |
| Internal queries never stored as user | Only real external input gets user role/type | Prevents context pollution from orchestration queries |
| Agent metadata on records | metadata uses `agent_node`, `agent_name`, `model` | Traces which node spawned each SDK Agent call |
| Self-serializing | Inherited `StateObject.to_dict()` / `from_dict()` | `dataclasses.asdict()` handles nested structures; only `set_parents()` override needed |

---

## See also

Prev : [`ExecutionLog` + `ExecutionLogEntry`](execution_log.md) | Next : [`ChatRecord` Audit Trail](chat_record.md)

## Related

- [Session.agent_state per node](agent_state.md)
- [Session.task — shared Task object](task.md)
- [Persistence backend for Session](state_store.md)
- [Compaction strategy inherited from agent_state.agent_config](../utility/compaction.md)
- [AgentNodes hold self.session](../agent_node/base.md)
- [ChatRecord — structured chat_history entries](chat_record.md)
