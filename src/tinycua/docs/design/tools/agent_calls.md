# Agent-to-Agent Calling Tools

> **File:** `docs/design/tools/agent_calls.md`
> **Package:** `tinycua.tools.agent_calls`

---

## Role

Agent-calling tools are SDK `Tool` objects that allow one agent to invoke another through
its wrapper `run()` method. Used by `MainLoop` in the `TinyCUA` wrapper to orchestrate
internal agents.

---

## Tool Contract

**File:** `tinycua/tools/agent_calls.py`

```python
from tinycua_sdk.tools.decorators import Tool
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.types import AgentKind


def call_query_analyst(internal_agents: dict[AgentKind, BaseAgentWrapper]) -> Tool:
    async def execute(user_query: str, chat_history=None, session_context=None) -> dict:
        analyst = internal_agents[AgentKind.QUERY_ANALYST]
        return await analyst.run(
            user_query=user_query,
            chat_history=chat_history or [],
            session_context=session_context or {},
        )

    return Tool(
        name="call_query_analyst",
        description="Classify user query into a mode decision",
        execute=execute,
    )
```

**Rules:**
- Tool receives a **wrapper instance**, not a raw SDK `Agent`
- Tool calls `wrapper.run(...)`, never `wrapper.agent.run(...)`
- Tool must not bypass the target agent's configured loop or validation
- Tool validates and normalizes the returned output

---

## All Seven Tools

| Tool | Target Wrapper | Purpose |
|------|---------------|---------|
| `call_query_analyst(internal_agents)` | `QueryAnalyst` | Classify query → mode decision |
| `call_information_digester(internal_agents)` | `InformationDigester` | Retrieve and digest context |
| `call_task_analyzer(internal_agents)` | `TaskAnalyzer` | Create task roadmap |
| `call_task_assessor(internal_agents)` | `TaskAssessor` | Select tasks for decomposition |
| `call_task_executor(internal_agents)` | `TaskExecutor` | Execute a task |
| `call_result_reviewer(internal_agents)` | `ResultReviewer` | Review task result |
| `call_primary_agent(internal_agents)` | `PrimaryAgent` | Synthesize final response |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tools receive wrapper, not raw Agent | `wrapper.run()` | Preserves validation, state, loop integrity |
| Factory pattern | `call_*(internal_agents) -> Tool` | Late binding of wrapper instances |
| Same interface as production | Tools call `run()` | Tests validate the same path used by MainLoop |
