# TinyCUA External Orchestrator

> **File:** `docs/design/agents/tinycua.md`
> **Package:** `tinycua.agents.tinycua`

---

## Role

`TinyCUA` is the top-level orchestrator and the single external entry point. It extends
`BaseAgentOrchestrator[SessionState]` — the same pattern as all internal orchestrators.

`TinyCUA` is **always a root/parent session** (`parent_id = None`). Internal agents
run as child sessions attached to this root.

---

## Orchestrator Class

**File:** `tinycua/agents/tinycua.py`

```python
import json
from collections.abc import AsyncIterator
from uuid import uuid4

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.agents.factory import create_all_orchestrators
from tinycua.config.agents import TinyCUAConfig
from tinycua.config.types import AgentKind
from tinycua.loops.main_loop import MainLoop
from tinycua.state.session import Session
from tinycua.state.information import SessionState
from tinycua.tools.agent_calls import (
    call_query_analyst, call_information_digester,
    call_task_analyzer, call_task_assessor,
    call_task_executor, call_result_reviewer,
    call_primary_agent,
)


class TinyCUA(BaseAgentOrchestrator[Session]):
    """Top-level orchestrator — always a root session.

    Self-referential: self.state IS the Session. Extends
    BaseAgentOrchestrator[Session] so build_instruction(), save_state(),
    and restore_state() are inherited.
    """

    config: TinyCUAConfig

    def __init__(
        self,
        config: TinyCUAConfig | None = None,
        session: Session | None = None,
    ):
        if config is None:
            config = TinyCUAConfig()
        self.config = config

        # Session IS the state. Always a root/parent session.
        if session is None:
            session = Session(
                session_id=str(uuid4()),
                parent_id=None,
            )
        self.state = session  # BaseAgentOrchestrator.state — Session extends StateObject

        # Internal orchestrators
        self.internal_orchestrators = create_all_orchestrators(
            config.internal_orchestrator_overrides
        )

    # ── Instruction ───────────────────────────────────────────────────

    def build_instruction(self, context: dict) -> str:
        """Build system prompt from base instruction + session metadata.

        Overrides the base to inject the session object as metadata into
        the system prompt.
        """
        # Default behavior: base instruction + dynamic context
        return super().build_instruction(context)

    # ── Agent construction helpers ────────────────────────────────────

    def _build_orchestrator_tools(self) -> list:
        """Build SDK Tools that delegate to internal orchestrators."""
        return [
            call_query_analyst(self.internal_orchestrators),
            call_information_digester(self.internal_orchestrators),
            call_task_analyzer(self.internal_orchestrators),
            call_task_assessor(self.internal_orchestrators),
            call_task_executor(self.internal_orchestrators),
            call_result_reviewer(self.internal_orchestrators),
            call_primary_agent(self.internal_orchestrators),
        ]

    # ── Main entry point ──────────────────────────────────────────────

    async def run(self, user_query: str) -> AsyncIterator[dict]:
        """Run TinyCUA for a user query, yielding all SDK stream events.

        The session is pre-loaded in __init__. If resuming a mid-execution
        session, routes directly to the active orchestrator, bypassing
        MainLoop.
        """
        self.state.append_user(user_query)

        # ── Session resume: route directly to the active orchestrator ──
        if self.state.active_agent:
            orchestrator = self.internal_orchestrators.get(
                AgentKind(self.state.active_agent)
            )
            if orchestrator:
                resume_input = self._build_resume_input()
                async for event in orchestrator.run(**resume_input):
                    yield event
                return

        # ── Fresh run: full MainLoop orchestration ────────────────────
        instructions = self.build_instruction({"session": self.state})

        agent = Agent(
            name="tinycua",
            instructions=instructions,
            llm_model=self.config.model,
            tools=self._build_orchestrator_tools(),
            loop=MainLoop(
                state=self.state,  # Session IS the state
                internal_orchestrators=self.internal_orchestrators,
            ),
        )

        text_parts: list[str] = []
        async for event in agent.run(
            query=user_query,
            messages=self.state.get_messages(),
            stream=True,
        ):
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            elif event["type"] == "response.usage":
                self.state.token_usage = event["usage"]
            yield event

        raw = "".join(text_parts)
        self.state.append_assistant(raw)

    # ── Session resume helper ─────────────────────────────────────────

    def _build_resume_input(self) -> dict:
        """Build input for the active orchestrator based on session state."""
        kind = AgentKind(self.state.active_agent)
        if kind == AgentKind.QUERY_ANALYST:
            return {"user_query": self.state.last_query.get("user_query", "")}
        if kind == AgentKind.INFORMATION_DIGESTER:
            return {"context_enhanced_query": self.state.context_enhanced_query}
        if kind == AgentKind.TASK_ANALYZER:
            return {"digested_information": self.state.digested_information}
        if kind == AgentKind.TASK_EXECUTOR:
            return {"task": self.state.last_query.get("task", {})}
        if kind == AgentKind.RESULT_REVIEWER:
            return {
                "task": self.state.last_query.get("task", {}),
                "task_result": self.state.last_query.get("task_result", {}),
            }
        if kind == AgentKind.PRIMARY_AGENT:
            return {
                "input_data": (
                    self.state.worker_results
                    or self.state.context_enhanced_query
                    or {}
                )
            }
        return {}
```

---

## Usage

```python
# New session (generates UUID)
tinycua = TinyCUA(config=TinyCUAConfig(...))
async for event in tinycua.run("Research quantum computing"):
    if event["type"] == "response.output_text.delta":
        print(event["delta"], end="", flush=True)

# Resume existing session
from tinycua.state.session import Session
session = Session.from_dict(state_store.load("session-123"))
tinycua = TinyCUA(config=TinyCUAConfig(...), session=session)
async for event in tinycua.run(...):
    ...
```

---

## Config

`TinyCUAConfig` — `instructions=TINYCUA_MAIN_INSTRUCTION`, `state_store`, `artifact_store`,
`internal_orchestrator_overrides`, `orchestration`.
See [`config/agents.md`](../config/agents.md#tinycuaconfig).

---

## State

`SessionState` — `active_agent: str | None`, `orchestration_phase: str | None`,
`context_enhanced_query`, `digested_information`, `task_tree`, `worker_results`,
`checkpoints`. See [`state/information.md`](../state/information.md#sessionstate).

---

## Session Tree

`TinyCUA` owns the **root session** (`parent_id = None`). Internal orchestrators
(workers, sub-tasks) run as **child sessions** created via `root.create_child(...)`.
Children propagate `chat_history` upward on completion but `session_context` stays
isolated.

```
TinyCUA (root session, parent_id=None)
 ├── Child session: Worker-1
 │    ├── Child: TaskAnalyzer sub-session
 │    └── Child: TaskExecutor sub-session
 └── Child session: Worker-2
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Extends BaseAgentOrchestrator | `BaseAgentOrchestrator[SessionState]` | Same pattern as internal orchestrators; inherits build_instruction, save/restore |
| Always root session | `parent_id = None`, UUID if missing | Single top-level entry point; session tree branches downward |
| Session in constructor | `__init__(session=...)` | Session loaded once, not per-run; survives across calls |
| state = session.state | Same reference | Orchestrator writes state; session persists it via serialization |
| Session resume bypasses MainLoop | Direct `orchestrator.run()` | Skip irrelevant phases when resuming mid-execution |
| Orchestrator-call tools | `call_*` SDK Tools | MainLoop invokes via natural language + tool calls |


---

## See also

Prev : [`PrimaryAgent`](primary_agent.md) | Next : [Orchestrator-Call Tools](../tools/agent_calls.md)
