# TodoList Tool

> **File:** `docs/design/tools/todo.md`
> **Package:** `tinycua.tools.todo`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

The `TodoList` tool provides per-session short-term goal tracking. It is **not** a
Task Tree — it is a simple checklist the agent uses as working memory during ReAct
execution. Every agent receives this tool through the `SHARED_AGENT_BASE_TOOLS`
constant.

| Task Tree (Roadmap) | TodoList (Short-Term Goals) |
|---------------------|---------------------------|
| Formal decomposition with hierarchy, task IDs, status, results | Simple flat list with status and todo text |
| Managed by TaskAnalyzer/TaskCreator via task tools | Managed by any agent during execution |
| Represents the full work breakdown | Represents what the agent is currently working on |
| Shared across sessions via `session.task` | Per-session, reset on new task assignment |

---

## Storage

The TodoList is stored on the `Session` as `session.todo_list`:

```text
session.todo_list: list[dict[str, str]] | None = None
    · each item: {"status": "incomplete" | "completed", "todo": str}
    · None means the list has not been initialized yet
    · empty list means the agent has no items (intentionally cleared)
```

It is **reset** when a new task is assigned to the session (new active task execution
starts fresh). It persists across multiple `Agent.run()` invocations within the same
session, so the agent can resume where it left off.

---

## Tool Operations

The `TodoList` tool is a single SDK `Tool` with sub-commands. The agent calls it as:

```text
TodoList(action: str, ...) → None
```

### Actions

| Action | Parameters | Behavior |
|--------|-----------|----------|
| `add` | `todo: str` | Append a new item with `status="incomplete"` |
| `read` | — | Return the current list as formatted markdown |
| `mark_complete` | `index: int` | Set `status="completed"` on item at zero-based index |
| `mark_incomplete` | `index: int` | Set `status="incomplete"` on item at zero-based index |
| `edit` | `index: int, todo: str` | Replace the todo text at index |
| `delete` | `index: int` | Remove item at index |
| `clear` | — | Reset `todo_list` to empty `[]` |

### Return Format

```text
# TodoList(action="read") returns:
## TodoList
- [ ] Install nginx package
- [x] Configure virtual hosts
- [ ] Set up SSL certificates
- [ ] Test configuration
```

Read is the most common action — the agent checks its TodoList at the start of each
ReAct cycle and marks items as it completes them.

---

## Tool Definition

```text
from tinycua_sdk.tools.decorators import tool

@tool(name="TodoList")
def todo_list_tool(session: Session, action: str, index: int | None = None,
                   todo: str | None = None) -> str:
    · if session.todo_list is None: session.todo_list = []
    · dispatch based on action → mutate session.todo_list
    · return "## TodoList\n" + formatted markdown

TODO_LIST_TOOL: Tool = todo_list_tool
```

The tool receives `session` via closure (same pattern as task tools). It reads and
writes `session.todo_list` directly.

---

## Integration

### In Base Agent Tools

```text
SHARED_AGENT_BASE_TOOLS = [
    ShellTool(),
    FileReadTool(),
    FileWriteTool(),
    TODO_LIST_TOOL,   # ← every agent gets this
    # ... other general-purpose tools
]
```

### In Agent Instructions

The base instruction guides the agent to use the TodoList during PLAN phase:

```text
## ReAct Phases

1. ANALYZE: Read the task, examine the current state, identify what tools and
   information you need.
2. PLAN: Break the work into concrete steps. Use the TodoList tool to record
   each step as you plan it.
3. ReAct: Execute each step, calling tools and observing results. Mark steps
   as completed in the TodoList as you finish them. If a step fails or reveals
   new information, revisit your plan and update the TodoList.
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Per-session storage | `session.todo_list` | Each agent's working memory is isolated; child sessions start fresh |
| Reset on task assignment | New task → clear TodoList | Prevents stale items from previous work |
| Flat list, not hierarchical | Simple status + text | Agents don't need full tree management; that's TaskAnalyzer's role |
| Universal tool | Included in `SHARED_AGENT_BASE_TOOLS` | Every agent can track its own progress |
| Markdown output | Formatted checklist | LLMs read markdown natively; clean for both agent and human review |
| Sub-command dispatch | Single tool, action parameter | Keeps tool count low; all list operations through one interface |

---

## See also

- [Session TodoList storage](../state/session.md) — `session.todo_list` field
- [ReAct loop phase structure](../loops/react_agent.md#react-phase-structure) — PLAN phase uses TodoList
- [Task tools (Task Tree management)](task.md) — distinct from TodoList
- [SHARED_AGENT_BASE_TOOLS](../constants/tools.md) — universal tool injection point
