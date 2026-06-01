# ReActAgentLoop

> **File:** `docs/design/loops/react_agent.md`
> **Package:** `tinycua.loops.react_agent`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`ReActAgentLoop` is the shared base/helper loop for agents that use standard ReAct
behavior. It receives a `Session`, not a duplicated AgentNode state object.

Agent-specific loops may subclass or wrap this behavior to add:

- required tool enforcement
- internal retry/repair
- final result event formatting
- session history writes
- lifecycle status updates

---

## ReAct Phase Structure

All ReAct agents operate in three conceptual phases. These are **not enforced by code
step-dispatch** — they are embedded in the agent's base instruction as behavioral
guidance. The agent freely moves between phases as needed within the standard ReAct
loop (observe → think → act → observe).

```text
1. ANALYZE
   · Read and understand the task/query in full
   · Identify what information is missing and what tools are available
   · Examine the current task tree, session context, and TodoList
   · Determine success criteria and constraints

2. PLAN
   · Break the work into concrete, ordered steps
   · Record short-term goals in the TodoList tool for tracking
   · Identify dependencies between steps
   · Decide which tools are needed for each step

3. ReAct
   · Execute each step: call tool → observe result → decide next action
   · Mark TodoList items as completed as they are done
   · Revisit PLAN if a step fails or reveals new information
   · Revisit ANALYZE if fundamental assumptions change
```

### Enforcement

These phases exist in the agent's **base instruction** (`TASK_EXECUTOR_INSTRUCTION`,
`PRIMARY_AGENT_INSTRUCTION`, etc.) as natural language guidance. The loop does **not**
enforce phase transitions, count steps, or validate phase ordering. The agent is free to:

- Jump directly to PLAN from ANALYZE without explicit tool calls
- Start executing while still refining the plan
- Return to ANALYZE mid-execution when blocked or redirected
- Skip PLAN for trivial single-step tasks

### TodoList Tool

Every ReAct agent has access to the `TodoList` tool (stored per-session on
`session.todo_list`). The TodoList is a **short-term working memory** — distinct from
the Task Tree:

| Task Tree (Roadmap) | TodoList (Short-Term Goals) |
|---------------------|---------------------------|
| Owned by session, managed by TaskAnalyzer/TaskCreator | Owned by session, managed by the executing agent |
| Formal decomposition with structure, status, result | Simple list with status and text |
| Represents the full work breakdown | Represents what the agent is currently working on |
| Only specialized agents modify it | Every agent can read/write their own |

The agent uses the TodoList during PLAN phase to enumerate concrete steps, then checks
off items during ReAct execution.

---

## Class Contract

```text
ReActAgentLoop(BaseLoop)  ← extends tinycua_sdk.agent.loop.BaseLoop

__init__(session: Session) -> None
  · holds a reference to the TinyCUA Session
  · loop has access to session.todo_list for TodoList tool integration

run(agent, messages, tools, override_instructions=None, stream=False) -> AsyncIterator
  · delegates to super().run(...) for standard SDK ReAct behavior
  · establishes the session-owned state/config pattern for all loops
```

This base loop can remain thin, but it establishes the session-owned state/config
pattern for all internal loops.

---

## Agent-Specific Extension Pattern

```text
class SpecificAgentLoop(ReActAgentLoop):
    async run(agent, messages, tools, ...) -> AsyncIterator:
        → delegated streaming with required tool retry
        → format final structured result
        → self.session.agent_state = <AgentState subclass result>
        → yield {"type": "tinycua.final_result", "result": result}
```

The exact helper names are implementation details. The important rule is that retry and
output formatting live inside the loop, not in the AgentNode.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Session via constructor | `ReActAgentLoop(session=session)` | Loop can access config, state, task tree, and history from one source |
| Shared base | Reusable for simple ReAct agents | Avoids duplicating SDK delegation logic |
| Agent-specific subclasses | Query/assessor/executor/etc. specialize behavior | Required tool retry and output formatting differ per agent |
| Final result event | Loop emits `tinycua.final_result` | AgentNode does not parse raw tool-call events |

---

## See also

Prev : [Loop Strategies Overview](overview.md) | Next : [`QueryAnalystLoop`](query_analyst_loop.md)

## Related

- [Loop hierarchy overview](overview.md)
- [AgentGraph system overview](../orchestration/overview.md)
- [Base AgentNode responsibility split](../agent_node/base.md)
