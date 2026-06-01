# Primary Agent

> **File:** `docs/design/agent_node/primary_agent.md`
> **Package:** `tinycua.agent_nodes.primary_agent`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`PrimaryAgent` is the general-purpose passthrough / final-response agent. It handles
small tasks, chat, direct user requests, and final user-facing synthesis.

Unlike transient analyzers, PrimaryAgent directly inherits the parent session. It is
not a throwaway context wrapper; it writes its responses into the parent session's
history/context.

---

## Session Policy

PrimaryAgent receives the parent/root session directly:

```text
primary = PrimaryAgent(config=config, session=parent_session)
primary.session is parent_session
```

It does not create a separate transient analysis session for normal passthrough. This
ensures direct user-facing work happens in the main conversation context.

---

## `run()` Method

```text
run(query: str) -> AsyncIterator[dict]
```

`query` may be plain user text or `QueryAnalystState` YAML front-matter.

```text
parsed = AgentState.from_string(query)
if isinstance(parsed, QueryAnalystState):
    if parsed.context:
        session.append_assistant(parsed.context)  # role changed to assistant
    agent_query = parsed.query                    # original user query
else:
    agent_query = query

agent.run(query=agent_query, messages=session.session_context, stream=True)
```

The CEQ/query part must not be appended as a duplicate user message. `TinyCUA.run()`
already called `session.append_user(user_query)`.

---

## Tools

```text
PRIMARY_AGENT_BASE_TOOLS = [
    *SHARED_AGENT_BASE_TOOLS,
]
```

PrimaryAgent shares the general execution surface with TaskExecutor (shell, file,
search, TodoList, etc.) but has no task-result write tools by default.

---

## ReAct Phase Structure

PrimaryAgent follows the same **Analyze → Plan → ReAct** behavioral phases:

1. **ANALYZE**: Read relevant session context and any appended QueryAnalyst context.
2. **PLAN**: Use TodoList for multi-step direct tasks.
3. **ReAct**: Execute tool calls and mark TodoList items completed.

---

## Output: PrimaryAgentState

```text
PrimaryAgentState(
  type="primary_agent",
  status="terminated",
  failure=0,
  final_response="...",
  citations=[...],
)
```

The final response is appended to the session as assistant output and may pass through
an optional OutputGate for response-envelope formatting.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Inherits parent session | `PrimaryAgent.session is parent_session` | User-facing passthrough belongs in main conversation context |
| Parses QueryAnalystState | Reads YAML front-matter | Can consume InputGate context without graph-specific coupling |
| Append context as assistant | QA context is agent-produced | Avoids incorrectly storing internal context as user input |
| Do not duplicate query | Use CEQ query as `agent.run(query=...)` only | External user query already exists in session context |
| Shared tools | `SHARED_AGENT_BASE_TOOLS` | Direct tasks need general tool surface |
| AgentState output | `PrimaryAgentState` | Typed final response and citations |

---

## See also

Prev : [`ResultReviewer`](result_reviewer.md) | Next : [`Base AgentNode`](base.md)

## Related

- [TinyCUA passthrough routing](../orchestration/tinycua.md#passthrough-routing)
- [QueryAnalystState](../state/information.md#queryanalyststate)
- [ContextEnhancedQuery safety](../state/classification.md#contextenhancedquery-methods)
- [PrimaryAgentLoop](../loops/primary_agent_loop.md)
