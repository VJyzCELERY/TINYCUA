# MainLoop

> **File:** `docs/design/loops/main_loop.md`
> **Package:** `tinycua.loops.main_loop`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`MainLoop` is the top-level orchestration loop for the `TinyCUA` external wrapper.
It extends SDK `BaseLoop` and implements the full TINYCUA flow: classify → route →
delegate to internal agents → synthesize response. Uses agent-calling tools to invoke
internal wrapper instances.

---

## Class Contract

**File:** `tinycua/loops/main_loop.py`

```python
from tinycua_sdk.agent.loop import BaseLoop


class MainLoop(BaseLoop):
    """Top-level orchestration: Query Analyst → route → delegate → synthesize."""

    def __init__(self):
        super().__init__()

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        """Full orchestration flow."""
        # The composed SDK Agent (in TinyCUA wrapper) has agent-calling tools available.
        # MainLoop orchestrates by calling these tools, which delegate to internal wrappers.
        ...
```

---

## Orchestration Flow

```
User Query
  → classify(user_query)           → QueryAnalyst → ModeDecision
      ├── primary_agent
      │     → synthesize(ceq)        → PrimaryAgent → final response
      │
      ├── worker
      │     → digest(ceq)            → InformationDigester → DigestedInformation
      │     → analyze(digest)        → TaskAnalyzer → Task tree
      │     → [assess + create]      → TaskAssessor + Task Creation loop
      │     → execute(task)          → TaskExecutor (per leaf) → TaskResult
      │     → review(result)         → ResultReviewer → ReviewerDecision
      │     → [retry/replan/accept]  → loop back or propagate context
      │     → synthesize(worker_result) → PrimaryAgent → final response
      │
      └── uncertain
            → escalate_user or explore
```

The composed SDK `Agent` uses `call_query_analyst`, `call_information_digester`, etc.
to route to internal wrappers. Each tool delegates to the target wrapper's `run()` method.

---

## Continuation State

`MainLoop` tracks per-session state so an interrupted run can resume. State fields:

- `session_id`
- Current orchestration phase (`query_analysis`, `primary_agent`, `information_digestion`, `worker`, `uncertain`, `final_response`)
- Active internal agent
- Active sub-session / Worker state reference
- Last completed step / checkpoint
- Pending user action
- Current `ContextEnhancedQuery`, `ModeDecision`, `DigestedInformation`
- Active `Task` tree and current task id
- Current `WorkerResult`
- Final response status

State is persisted via the `StateStore` backend (SQLite by default). Checkpoint after each phase.

---

## Integration with TinyCUA Wrapper

```python
class TinyCUA:
    def __init__(self, config: TinyCUAConfig):
        self.internal_agents = create_all_agents(config.internal_agent_overrides)
        self.state_store = config.state_store

        self.agent = Agent(
            name="tinycua",
            instructions=config.instructions,
            llm_model=config.model,
            tools=[*self._build_agent_tools()],
            loop=MainLoop(),
        )

    def _build_agent_tools(self) -> list[Tool]:
        return [
            call_query_analyst(self.internal_agents),
            call_information_digester(self.internal_agents),
            call_task_analyzer(self.internal_agents),
            call_task_assessor(self.internal_agents),
            call_task_executor(self.internal_agents),
            call_result_reviewer(self.internal_agents),
            call_primary_agent(self.internal_agents),
        ]

    async def run(self, user_query: str, session_id: str | None = None) -> Response:
        if session_id:
            await self._restore_state(session_id)
        response = await self.agent.run(query=user_query)
        await self._checkpoint(session_id)
        return response
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent-calling tools as the delegation mechanism | `call_*` SDK Tools on the composed agent | MainLoop can invoke internal agents via natural language + tool calls, not programmatic dispatch |
| Checkpoint after each phase | `orchestration.checkpoint_after_each_phase` | Configurable granularity for resume behavior |
| SQLite-first persistence | `SQLiteStateStore` as default | Durable, transactional, zero-config |
| Per-session state | Tracked in TinyCUA wrapper, persisted via StateStore | One external agent manages multiple sessions |
