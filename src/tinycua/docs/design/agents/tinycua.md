# TinyCUA External Orchestrator

> **File:** `docs/design/agents/tinycua.md`
> **Package:** `tinycua.agents.tinycua`

---

## Role

`TinyCUA` is the single external entry point and top-level orchestrator. It owns all
internal orchestrator instances, manages session persistence, and can route directly
to a specific agent when resuming a mid-session execution.

Users interact with `async for event in tinycua.run(...)` — streaming token-by-token
output with session continuity.

---

## Orchestrator Class

**File:** `tinycua/agents/tinycua.py`

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.factory import create_all_orchestrators
from tinycua.config.agents import TinyCUAConfig
from tinycua.config.types import AgentKind
from tinycua.loops.main_loop import MainLoop
from tinycua.state.information import SessionState
from tinycua.tools.agent_calls import (
    call_query_analyst, call_information_digester,
    call_task_analyzer, call_task_assessor,
    call_task_executor, call_result_reviewer,
    call_primary_agent,
)


class TinyCUA:
    """Top-level orchestrator — manages internal orchestrators and session state."""

    def __init__(self, config: TinyCUAConfig):
        self.config = config
        self.internal_orchestrators = create_all_orchestrators(
            config.internal_orchestrator_overrides
        )
        self.state_store = config.state_store
        self.artifact_store = config.artifact_store
        self.state: SessionState = SessionState()

    # ── Orchestrator call tools ──────────────────────────────────────

    def _build_orchestrator_tools(self) -> list:
        """Build SDK Tools that delegate to internal orchestrator instances."""
        return [
            call_query_analyst(self.internal_orchestrators),
            call_information_digester(self.internal_orchestrators),
            call_task_analyzer(self.internal_orchestrators),
            call_task_assessor(self.internal_orchestrators),
            call_task_executor(self.internal_orchestrators),
            call_result_reviewer(self.internal_orchestrators),
            call_primary_agent(self.internal_orchestrators),
        ]

    # ── Main entry point ─────────────────────────────────────────────

    async def run(
        self,
        user_query: str,
        session_id: str | None = None,
    ) -> AsyncIterator[dict]:
        """Run TinyCUA for a user query, yielding all SDK stream events.

        On session resume: loads previous state and routes directly to the
        active orchestrator, bypassing MainLoop.
        On fresh run: executes full orchestration via MainLoop.
        """
        # Restore session if resuming
        if session_id:
            await self._restore_state(session_id)

        self.state.accumulated_text = []

        # ── Session resume: route directly to the active orchestrator ──
        if self.state.active_agent and session_id:
            orchestrator = self.internal_orchestrators.get(
                AgentKind(self.state.active_agent)
            )
            if orchestrator:
                # Build input from saved state
                resume_input = self._build_resume_input()
                async for event in orchestrator.run(**resume_input):
                    if event["type"] == "response.output_text.delta":
                        self.state.accumulated_text.append(event["delta"])
                    elif event["type"] == "response.usage":
                        self.state.token_usage = event["usage"]
                    yield event
                await self._checkpoint(session_id)
                return

        # ── Fresh run: full MainLoop orchestration ────────────────────
        agent = Agent(
            name="tinycua",
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=self._build_orchestrator_tools(),
            loop=MainLoop(
                state=self.state,
                internal_orchestrators=self.internal_orchestrators,
            ),
        )

        async for event in agent.run(query=user_query, stream=True):
            if event["type"] == "response.output_text.delta":
                self.state.accumulated_text.append(event["delta"])
            elif event["type"] == "response.usage":
                self.state.token_usage = event["usage"]
            yield event

        raw = "".join(self.state.accumulated_text)
        self.state.last_result = json.loads(raw) if raw else {}
        if session_id:
            await self._checkpoint(session_id)

    # ── Session helpers ───────────────────────────────────────────────

    def _build_resume_input(self) -> dict:
        """Build the input dict for the active orchestrator based on state."""
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
            return {"input_data": self.state.worker_results or self.state.context_enhanced_query or {}}
        return {}

    async def _restore_state(self, session_id: str):
        state = await self.state_store.load(session_id, "main_loop_state")
        if state:
            self.state = SessionState(**state)

    async def _checkpoint(self, session_id: str):
        if session_id and self.state_store:
            await self.state_store.save(
                session_id, "main_loop_state", self.state.__dict__
            )

    def save_state(self, store) -> None:
        """Save orchestrator state and all internal orchestrator states."""

    def restore_state(self, store) -> None:
        """Restore orchestrator state and all internal orchestrator states."""
```

---

## Config

`TinyCUAConfig` — `instructions=TINYCUA_MAIN_PROMPT`, `state_store`, `artifact_store`,
`internal_orchestrator_overrides`, `orchestration`.
See [`config/agents.md`](../config/agents.md#tinycuaconfig).

---

## State

`SessionState` — `active_agent: str | None`, `orchestration_phase: str | None`,
`context_enhanced_query`, `digested_information`, `task_tree`, `worker_results`,
`checkpoints`. See [`state/information.md`](../state/information.md#sessionstate).

---

## Orchestrator-Call Tools

`_build_orchestrator_tools()` builds SDK `Tool` objects that delegate to internal
orchestrators. Each tool calls `orchestrator.run(...)`, consumes the stream generator,
and returns the final result from `orchestrator.state.last_result`.

```python
# Inside MainLoop, the LLM can call:
#   call_query_analyst(user_query="...")
#   call_information_digester(context_enhanced_query={...})
#   call_task_analyzer(digested_information={...})
#   etc.
```

Key rule: **Tool calls `orchestrator.run(...)`, never creates a raw Agent.** This
preserves typed state management and loop integrity.

---

## Session Continuity

```
Run 1: tinycua.run("Research quantum computing", session_id="abc")
  → MainLoop → QueryAnalyst → InformationDigester → TaskAnalyzer
  → Checkpoint after each phase
  → Interrupted mid-TaskAnalyzer

Run 2: tinycua.run(..., session_id="abc")
  → state_store.load("abc")
  → state.active_agent == "task_analyzer"
  → task_analyzer.run(digested_information=state.digested_information)  ← skip MainLoop
  → Continue from where TaskAnalyzer left off
```

---

## State Store Integration

Default: `SQLiteStateStore(db_path="tinycua.db")`.

```python
tinycua = TinyCUA(
    TinyCUAConfig(
        state_store=SQLiteStateStore(db_path="tinycua.db"),
        artifact_store=FileSystemArtifactStore(base_dir="./tinycua_artifacts"),
    )
)
async for event in tinycua.run("Research quantum computing", session_id="session-123"):
    if event["type"] == "response.output_text.delta":
        print(event["delta"], end="", flush=True)
# State is checkpointed after each orchestration phase
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| One external entry point | `async for event in tinycua.run(...)` | Internal orchestrators remain implementation details |
| Agent built per-call | `Agent(...)` in `run()` | Loop receives fresh state reference each call |
| No self.agent | Local variable in `run()` | Agent is configuration, not state |
| Session resume bypasses MainLoop | Direct `orchestrator.run()` call | Faster resume; skip irrelevant phases |
| Orchestrator-call tools as delegation | `call_*` SDK Tools | MainLoop invokes via natural language + tool calls |
| Tools consume generator internally | `async for event in orchestrator.run(): pass` | SDK sees a normal dict return from the tool |
| SQLite-first persistence | `SQLiteStateStore` as default | Durable, transactional, zero-config |
