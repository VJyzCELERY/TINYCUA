# MainLoop

> **File:** `docs/design/loops/main_loop.md`
> **Package:** `tinycua.loops.main_loop`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`MainLoop` is the top-level orchestration loop for the `TinyCUA` external orchestrator.
It extends SDK `BaseLoop` and implements the full TINYCUA flow: classify → route →
delegate to internal orchestrators → synthesize response.

Receives `SessionState` and all internal orchestrator instances by reference.

---

## Class Contract

**File:** `tinycua/loops/main_loop.py`

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua.state.information import SessionState
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.types import AgentKind


class MainLoop(BaseLoop):
    """Top-level orchestration: Query Analyst → route → delegate → synthesize."""

    def __init__(
        self,
        state: Session,
        internal_orchestrators: dict[AgentKind, BaseAgentOrchestrator],
    ):
        super().__init__()
        self.state = state  # Session IS the state — extends StateObject
        self._orchestrators = internal_orchestrators

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        """Full orchestration flow.

        The composed SDK Agent (in TinyCUA) has orchestrator-call tools available.
        MainLoop orchestrates by calling these tools, which delegate to internal
        orchestrator instances via orchestrator.run(...).
        """
        async for event in super().run(agent, messages, tools, override_instructions, stream=True):
            yield event
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
Each tool calls `orchestrator.run(...)` on the corresponding internal instance, consumes
the stream generator, and returns the final result.

---

## Continuation State

`MainLoop` tracks per-session state via `self.state` (SessionState). Fields:

- `session_id`
- Current orchestration phase (`query_analysis`, `primary_agent`, `information_digestion`, `worker`, `uncertain`, `final_response`)
- Active internal orchestrator (`active_agent`)
- Pending user action
- Current `ContextEnhancedQuery`, `ModeDecision`, `DigestedInformation`
- Active `Task` tree and current task id
- Current `WorkerResult`
- Final response status

State is persisted via the `StateStore` backend (SQLite by default). Checkpoint after each phase.

---

## Integration with TinyCUA Orchestrator

```python
class TinyCUA(BaseAgentOrchestrator[Session]):
    async def run(self, user_query):
        if self.state.active_agent:
            orchestrator = self.internal_orchestrators[AgentKind(self.state.active_agent)]
            async for event in orchestrator.run(**self._build_resume_input()):
                yield event
            return

        agent = Agent(
            name="tinycua",
            instructions=self.build_instruction({"session": self.state}),
            llm_model=self.config.model,
            tools=self._build_orchestrator_tools(),
            loop=MainLoop(
                state=self.state,  # Session IS the state
                internal_orchestrators=self.internal_orchestrators,
            ),
        )
        async for event in agent.run(query=user_query, stream=True):
            yield event
            return

        # Fresh run: full orchestration via MainLoop
        agent = Agent(
            name="tinycua",
            instructions=self.build_instruction({"session": self.session}),
            llm_model=self.config.model,
            tools=self._build_orchestrator_tools(),
            loop=MainLoop(
                state=self.state,
                session=self.session,
                internal_orchestrators=self.internal_orchestrators,
            ),
        )
        async for event in agent.run(query=user_query, stream=True):
            yield event
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestrator-call tools as delegation | `call_*` SDK Tools on the composed agent | MainLoop invokes via natural language + tool calls |
| State via constructor | `MainLoop(state=self.state, ...)` | Direct reference to SessionState for phase tracking |
| Session resume bypasses MainLoop | Direct `orchestrator.run()` in TinyCUA | Skip irrelevant phases on resume |
| SQLite-first persistence | `SQLiteStateStore` as default | Durable, transactional, zero-config |


---

## See also

Prev : [`ResultReviewLoop`](result_review_loop.md) | Next : [`StateObject` Base Class + Serialization](../state/state_object.md)
