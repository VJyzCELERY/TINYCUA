# Orchestrator-Call Tools

> **File:** `docs/design/tools/agent_calls.md`
> **Package:** `tinycua.tools.agent_calls`

---

## Role

Orchestrator-call tools are SDK `Tool` objects that allow one agent to invoke another
through its orchestrator's `run()` method. Used by `MainLoop` in the `TinyCUA` external
orchestrator to delegate to internal orchestrator instances.

Each tool calls `orchestrator.run(...)`, consumes the async generator (stream events
are logged/forwarded), and returns the final validated result from `orchestrator.state.last_result`.

---

## Tool Contract

**File:** `tinycua/tools/agent_calls.py`

```python
from tinycua_sdk.tools.decorators import Tool
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.types import AgentKind


def call_query_analyst(
    internal_orchestrators: dict[AgentKind, BaseAgentOrchestrator],
) -> Tool:
    async def execute(user_query: str, chat_history=None, session_context=None) -> dict:
        analyst = internal_orchestrators[AgentKind.QUERY_ANALYST]
        async for event in analyst.run(
            user_query=user_query,
            chat_history=chat_history or [],
            session_context=session_context or {},
        ):
            pass  # Events can be logged or forwarded here
        return analyst.state.last_result

    return Tool(
        name="call_query_analyst",
        description="Classify user query into a mode decision",
        execute=execute,
    )
```

**Rules:**
- Tool receives an **orchestrator instance**, not a raw SDK `Agent`
- Tool calls `orchestrator.run(...)`, never `agent.run(...)`
- Tool **consumes the async generator** — all stream events are consumed internally
- Tool returns `orchestrator.state.last_result` — the typed, parsed final output
- Tool must not create a raw Agent or bypass the orchestrator's configured loop

---

## All Six Tools

| Tool | Target Orchestrator | Returns |
|------|---------------|---------|
| `call_query_analyst(internal_orchestrators)` | `QueryAnalyst` | `{mode_decision: ModeDecision, context_enhanced_query: ContextEnhancedQuery}` |
| `call_information_digester(internal_orchestrators)` | `InformationDigester` | `DigestedInformation` |
| `call_task_creator(internal_orchestrators)` | `TaskCreator` | `Task` tree with selections |
| `call_task_executor(internal_orchestrators)` | `TaskExecutor` | `TaskResult` |
| `call_result_reviewer(internal_orchestrators)` | `ResultReviewer` | `ReviewerDecision` |
| `call_primary_agent(internal_orchestrators)` | `PrimaryAgent` | `{final_response, citations}` |

---

## Stream Consumption Pattern

Each orchestrator's `run()` is an `async def` that **yields** events (async generator).
The tool consumes the generator, discarding or logging events. The typed result is
accessed via `orchestrator.state.last_result` after the `async for` loop completes:

```python
# Inside the tool's execute():
async for event in orchestrator.run(...):
    # Optionally: log, forward, or inspect events
    pass

# After stream ends — state is populated
result = orchestrator.state.last_result
return result  # SDK sees a normal dict return
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tools receive orchestrator, not raw Agent | `orchestrator.run()` | Preserves typed state, loop integrity, session management |
| Factory pattern | `call_*(internal_orchestrators) -> Tool` | Late binding of orchestrator instances |
| Tool consumes generator | `async for event in orchestrator.run(): pass` | SDK expects a dict return from tool execute |
| Result from state | `orchestrator.state.last_result` | State is populated after stream ends; typed and validated |


---


---

## See also

Prev : [`TinyCUA` External Orchestrator](../agents/tinycua.md)
