# TinyCUA External Orchestrator

> **File:** `docs/design/agents/tinycua.md`
> **Package:** `tinycua.agents.tinycua`

---

## Role

`TinyCUA` is the top-level orchestrator and the single external entry point. It extends
`BaseAgentOrchestrator[Session]` — the same pattern as all internal orchestrators.

`TinyCUA` is **always a root/parent session**. All queries route through QueryAnalyst
first, which decides between passthrough (→ PrimaryAgent or active agent) and worker
(→ fresh InformationDigester → Worker chain).

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
    call_task_creator, call_task_executor,
    call_result_reviewer, call_primary_agent,
)


class TinyCUA(BaseAgentOrchestrator[Session]):
    """Top-level orchestrator — always a root session.

    All queries route through QueryAnalyst. Based on the mode decision:
      - Passthrough: route to active agent (PrimaryAgent or current active agent)
      - Worker: terminate all children, abort task, spawn fresh chain
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
            call_task_creator(self.internal_orchestrators),
            call_task_executor(self.internal_orchestrators),
            call_result_reviewer(self.internal_orchestrators),
            call_primary_agent(self.internal_orchestrators),
        ]

    # ── Main entry point ──────────────────────────────────────────────

    async def run(self, user_query: str) -> AsyncIterator[dict]:
        """Run TinyCUA for a user query, yielding all SDK stream events.

        All queries go through QueryAnalyst first. QueryAnalyst decides:
          - Passthrough → route to active agent (PrimaryAgent or current active)
          - Worker → terminate all children, abort task, spawn fresh chain

        QueryAnalyst is transient — its output is not stored in the session.
        """
        self.state.append_user(user_query)

        # ── Always route through QueryAnalyst ─────────────────────────
        analyst = self.internal_orchestrators[AgentKind.QUERY_ANALYST]
        analyst.session.is_transient = True
        self.state.add_child(analyst.session)

        async for event in analyst.run(
            user_query=user_query,
            session=self.state,
        ):
            yield event

        # QueryAnalyst is transient — terminate without propagation
        self.state.terminate_child(analyst.session)

        # ── Route based on QueryAnalyst decision ──────────────────────
        mode = analyst.state.mode_decision.mode if analyst.state.mode_decision else "passthrough"

        if mode == "passthrough":
            active = self.state.get_active_session()
            if active is self.state or self.state.task is None:
                # No active task — go to PrimaryAgent
                async for event in self._run_primary_agent():
                    yield event
            else:
                # Active task exists — route to active agent
                async for event in self._route_to_active_agent(active):
                    yield event

        elif mode == "worker":
            # Terminate all existing children, abort task
            self._abort_all_children()
            self.state.task = None

            # Spawn fresh chain: InfoDigester → Worker
            async for event in self._run_worker_chain(analyst.state.context_enhanced_query):
                yield event

        elif mode == "uncertain":
            async for event in self._handle_uncertain():
                yield event

    # ── Routing helpers ───────────────────────────────────────────────

    async def _run_primary_agent(self) -> AsyncIterator[dict]:
        """Route passthrough to PrimaryAgent."""
        primary = self.internal_orchestrators[AgentKind.PRIMARY_AGENT]
        self.state.add_child(primary.session)
        async for event in primary.run(input_data={}):
            yield event
        self.state.terminate_child(primary.session)

    async def _route_to_active_agent(self, active_session: Session) -> AsyncIterator[dict]:
        """Pass user query through to the currently active agent."""
        # The active agent handles the query directly
        pass

    async def _run_worker_chain(
        self,
        context_enhanced_query,
    ) -> AsyncIterator[dict]:
        """Spawn fresh InformationDigester → Worker chain."""
        # InformationDigester (transient)
        digester = self.internal_orchestrators[AgentKind.INFORMATION_DIGESTER]
        digester.session.is_transient = True
        self.state.add_child(digester.session)
        async for event in digester.run(context_enhanced_query):
            yield event
        self.state.terminate_child(digester.session)

        # Worker
        worker = self.internal_orchestrators[AgentKind.TASK_CREATOR]  # Worker via tools
        # ... continued in MainLoop via orchestrator-call tools ...
        # The composed Agent handles the full Worker chain via tool calls

    async def _handle_uncertain(self) -> AsyncIterator[dict]:
        """Ask user for clarification."""
        yield {"type": "text", "content": "I need more information to proceed."}

    def _abort_all_children(self) -> None:
        """Terminate all child sessions, propagating context upward."""
        for child in list(self.state.child_sessions):
            self.state.terminate_child(child)
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

`TinyCUA`'s state is the `Session` itself (`self.state`). The session tree holds all
agent states via `agent_state` on each node. No separate `SessionTracking` — token usage
is on `Session.total_token_usage`/`active_token_usage`.

See [`state/session.md`](../state/session.md) for the full Session API.

---

## Session Tree

`TinyCUA` owns the **root session**. All agents run as child sessions created via
`self.state.add_child(...)`. Children propagate `chat_history` and `session_context`
upward on termination (except transient agents).

```
TinyCUA (root)
 ├── QueryAnalyst      [transient — nothing propagates]
 ├── InformationDigester [transient — nothing propagates]
 ├── Worker
 │   ├── TaskCreator   (→ TaskAnalyzer → TaskAssessor)
 │   ├── TaskExecutor
 │   └── ResultReviewer
 └── PrimaryAgent
```

Only Worker and PrimaryAgent final responses propagate to TinyCUA's session_context.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Extends BaseAgentOrchestrator | `BaseAgentOrchestrator[Session]` | Same pattern as internal orchestrators; inherits build_instruction, save/restore |
| Always root session | `parent_id = None`, UUID if missing | Single top-level entry point; session tree branches downward |
| All queries through QueryAnalyst | QueryAnalyst always called first | Central routing decision; passthrough vs worker |
| No session resume bypass | Removed `active_agent` check | QueryAnalyst always consulted; routing is always fresh |
| Transient QueryAnalyst | `is_transient = True` → not in `child_sessions` | Output consumed inline; only classification + CEQ passed forward |
| Transient InformationDigester | `is_transient = True` → not in `child_sessions` | DigestedInformation consumed by Worker inline |
| Worker mode aborts task | `self.state.task = None` | Fresh task tree created from scratch |
| Orchestrator-call tools | `call_*` SDK Tools | Worker chain invoked via natural language + tool calls |


---


---


---

## See also

Prev : [`PrimaryAgent`](primary_agent.md) | Next : [Orchestrator-Call Tools](../tools/agent_calls.md)


## Related

- [Always called first for routing](query_analyst.md)
- [Spawned in worker mode (transient)](information_digester.md)
- [Passthrough target](primary_agent.md)
- [MainLoop orchestration](../loops/main_loop.md)
- [Session IS the state](../state/session.md)
- [Orchestrator-call tools for delegation](../tools/agent_calls.md)
