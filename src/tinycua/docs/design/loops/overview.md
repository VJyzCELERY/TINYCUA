# AgentLoop Overview

> **File:** `docs/design/loops/overview.md`
> **Package:** `tinycua.loops`
> **Last Updated:** 2026-06-01

---

## Role

AgentLoops are the SDK inner loops passed as `loop=` to `tinycua_sdk.Agent(...)`.
AgentNodes build agents and yield events; AgentLoops enforce required tool calls,
handle retries, append assistant responses, and write typed AgentState subclasses to
`session.agent_state`.

---

## Responsibility Split

| Layer | Responsibility |
|-------|----------------|
| AgentGraph | Route between nodes/subgraphs |
| AgentNode | Build SDK Agent, pass `query` and `messages`, yield events |
| AgentLoop | Retry/enforcement/output formatting; write `session.agent_state` |
| Session | Store AgentState, context, chat history, task, TodoList |

---

## Loop Output Contract

Every loop writes a specific AgentState subclass:

| Loop | Writes |
|------|--------|
| QueryAnalystLoop | `QueryAnalystState` |
| InformationDigestionLoop | `InformationDigesterState` |
| TaskAnalyzerLoop | `TaskAnalyzerState` |
| TaskAssessorLoop | `TaskAssessorState` |
| TaskExecutorLoop | `TaskExecutorState` |
| ResultReviewLoop | `ResultReviewerState` or keeps reviewer active with no terminal decision |
| PrimaryAgentLoop | `PrimaryAgentState` |

The graph consumes `session.agent_state`, not `session.agent_state.last_result`.

---

## Common Rules

1. AgentNodes pass `loop=SomeAgentLoop(session=self.session)`.
2. AgentNodes pass `messages=self.session.session_context` to `agent.run()`.
3. Loops update `session.agent_state` directly.
4. Loops emit one final result event when terminal.
5. AgentNodes yield events transparently and do not parse raw events.
6. Required classification/digest tools are enforced inside loops.

---

## See also

- [Base AgentNode responsibility split](../agent_sessions/base.md)
- [AgentState output serialization](../state/agent_state.md)
- [AgentGraph overview](../orchestration/overview.md)
