# Agent-to-Agent Calling Tools

> **File:** `docs/design/agent-calls.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **See also:** [`overview.md`](overview.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Role

Agent-to-agent calling tools allow one internal agent to invoke another through its
wrapper `run()` method. These are SDK `Tool` objects receivable by the composed
SDK `Agent`, enabling agents to delegate sub-tasks to other agents.

---

## Tool Contract

Each `call_*` function is a factory that returns an SDK `Tool`:

```python
from tinycua_sdk.tools.decorators import Tool
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.types import AgentKind


def call_query_analyst(internal_agents: dict[AgentKind, BaseAgentWrapper]) -> Tool:
    """SDK Tool that delegates to the QueryAnalyst wrapper."""

    async def execute(
        user_query: str,
        chat_history: list[dict] | None = None,
        session_context: dict | None = None,
    ) -> dict[str, Any]:
        analyst = internal_agents[AgentKind.QUERY_ANALYST]
        return await analyst.run(
            user_query=user_query,
            chat_history=chat_history or [],
            session_context=session_context or {},
        )

    return Tool(
        name="call_query_analyst",
        description="Classify user query into a mode decision",
        input_schema=...,  # accepted by SDK Tool
        execute=execute,
    )
```

**Key contract rules:**
- The tool receives the target wrapper instance, NOT a raw SDK `Agent`
- The tool calls `wrapper.run(...)`, not `wrapper.agent.run(...)` — preserving the wrapper's validation and state management
- The tool must not bypass the target agent's configured loop
- The tool validates and normalizes the returned output

---

## All Seven Calling Tools

**File:** `tinycua/tools/agent_calls.py`

| Tool Factory | Target Wrapper | Purpose |
|-------------|---------------|---------|
| `call_query_analyst(internal_agents)` | `QueryAnalyst` | Classify query → mode decision |
| `call_information_digester(internal_agents)` | `InformationDigester` | Retrieve and digest context |
| `call_task_analyzer(internal_agents)` | `TaskAnalyzer` | Create task roadmap |
| `call_task_assessor(internal_agents)` | `TaskAssessor` | Select tasks for decomposition |
| `call_task_executor(internal_agents)` | `TaskExecutor` | Execute a task |
| `call_result_reviewer(internal_agents)` | `ResultReviewer` | Review task result |
| `call_primary_agent(internal_agents)` | `PrimaryAgent` | Synthesize final response |

---

## Usage in Future MainLoop

The future `TinyCUA` wrapper will hold `self.internal_agents: dict[AgentKind, BaseAgentWrapper]`
and pass this registry to the calling tools. The composed SDK `Agent` (with `MainLoop`) will
have these tools available, allowing the orchestration agent to invoke internal agents
through `call_query_analyst(...)`, etc.

```python
# Future usage pattern:
tinycua = TinyCUA(config=TinyCUAConfig(...))
# MainLoop's composed SDK Agent has agent-calling tools available
# When MainLoop decides to classify, it calls call_query_analyst(user_query=...)
# which delegates to tinycua.internal_agents[AgentKind.QUERY_ANALYST].run()
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tools receive wrapper, not raw Agent | `wrapper.run()` | Preserves validation, state management, and loop integrity |
| Factory pattern | `call_*(internal_agents) -> Tool` | Allows late binding of wrapper instances |
| Same interface as production | Tools call `run()` just like MainLoop would | Tests validate the same path used in production |
