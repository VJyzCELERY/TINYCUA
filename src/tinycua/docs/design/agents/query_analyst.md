# Query Analyst

> **File:** `docs/design/agents/query_analyst.md`
> **Package:** `tinycua.agents.query_analyst`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`QueryAnalyst` is the first agent invoked on every query. It is **transient**
(`is_transient = True`) — never registered in parent's `child_sessions` (only `parent_id` set),
so tree traversal skips it. Its job is to:

1. **Assemble session context** — pull parent + active-agent context into its own `session_context`
2. **Classify the query** — decide passthrough vs worker vs uncertain
3. **Produce context-enhanced query** — enrich the user query with relevant context and keywords

---

## Session

`QueryAnalyst` creates its own transient session.

```python
def __init__(self, config: QueryAnalystConfig | None = None):
    if config is None:
        config = QueryAnalystConfig()
    super().__init__(config=config)  # auto-creates session with agent_state=self.state
    self.session.is_transient = True
```

The session is **never** added to the parent's `child_sessions`. It only has `parent_id`
and `_parent` set for back-reference. When terminated, nothing propagates to the parent.

### Compaction threshold rule

QueryAnalyst's compaction threshold (from `agent_state.agent_config.compaction_strategy`)
should be **greater than or equal to** its parent's threshold. This ensures QueryAnalyst
can always hold at least as much context as the parent, so it never loses information
when the parent session context is full.

---

## `run()` Method

### Signature

```python
async def run(self, user_query: str) -> AsyncIterator[dict]:
```

Takes a single argument: the raw user query string. Session is already owned by the
orchestrator (`self.session`).

### Flow

```
run(user_query)
  │
  ├─ 1. _assemble_session_context()
  │     Pull parent + active-agent context → self.session.session_context
  │     Apply cascading compaction if combined context too large.
  │
  ├─ 2. build_instruction({"user_query": ..., "session": ...})
  │     Base instruction + conditional task tree + conditional active task.
  │
  ├─ 3. Build SDK Agent (per-call)
  │     Tools: always QueryAnalystModeDecision + uncertainty;
  │     + read-only task tools if task exists.
  │
  ├─ 4. Stream → accumulate text + events, yield to caller
  │
  ├─ 5. Probe events for QueryAnalystModeDecision tool call
  │     ├─ Found → extract verdict + response text → DONE
  │     └─ Missing → append follow-up, rebuild agent, re-stream (max 3)
  │
  └─ 6. Store ModeDecision (from tool) + ContextEnhancedQuery (response text)
```

---

## Step 1: Context Assembly

`_assemble_session_context()` loads the parent session and its active descendant to
build a complete picture of the current execution state.

```python
def _assemble_session_context(self) -> None:
    """Load parent + active-agent context into self.session.session_context.

    QueryAnalyst has no history of its own (transient, fresh session).
    It must pull context from the parent session to answer: what is happening
    right now, what is the active task, and what is the active agent doing?
    """
    parent = self.session.parent
    if parent is None:
        return  # standalone / testing

    # 1. Gather source contexts
    parent_context = parent.get_messages()
    active_session = parent.get_active_session()
    active_context = (
        active_session.get_messages()
        if active_session is not parent
        else []
    )

    # 2. Assemble combined context
    combined = parent_context + active_context
    self.session.session_context = self._compact_until_fits(combined)
```

### Cascading Compaction

`_compact_until_fits()` tries increasing levels of compaction until the combined
messages fit within QueryAnalyst's context window:

```python
def _compact_until_fits(self, messages: list[dict]) -> list[dict]:
    """Apply cascading compaction until messages fit within our context window.

    Strategy (from agent_state.agent_config.compaction_strategy) provides:
      - check_compaction() decides IF compaction is needed
      - __call__() produces a summary from messages
    """
    strategy = self.agent_state.agent_config.compaction_strategy
    if strategy is None:
        return messages  # no compaction available

    context_window = strategy._get_context_window(self.session)
    if context_window is None:
        return messages  # can't determine window

    # If already fits, return as-is
    if strategy._estimate_tokens(messages) <= context_window:
        return messages

    # Split into parent portion and active-agent portion
    parent = self.session.parent
    active = parent.get_active_session()
    parent_msgs = parent.get_messages()
    active_msgs = (
        active.get_messages() if active is not parent else []
    )

    # Cascading attempts (each progressively more aggressive):
    candidates = [
        # 1. Compact active agent context only
        self._summarize(active_msgs, strategy) if active_msgs else None,
        # 2. Compact parent context only
        self._summarize(parent_msgs, strategy) if parent_msgs else None,
        # 3. Compact both separately
        self._double_summarize(parent_msgs, active_msgs, strategy),
        # 4. Compact everything together
        self._summarize(parent_msgs + active_msgs, strategy),
    ]

    for candidate in candidates:
        if candidate is None:
            continue
        if strategy._estimate_tokens(candidate) <= context_window:
            return candidate

    # Last resort: keep compacting the combined result
    result = messages
    while strategy._estimate_tokens(result) > context_window:
        result = strategy(result)
    return result

def _summarize(
    self, messages: list[dict], strategy: BaseCompaction
) -> list[dict]:
    """Compact messages into a single summary turn."""
    summary = strategy(messages)
    return [{"role": "user", "content": f"[Compacted context]\n{summary}"}]

def _double_summarize(
    self,
    parent_msgs: list[dict],
    active_msgs: list[dict],
    strategy: BaseCompaction,
) -> list[dict] | None:
    """Compact both parent and active agent context separately."""
    if not parent_msgs or not active_msgs:
        return None
    compacted_parent = (
        self._summarize(parent_msgs, strategy)
        if strategy._estimate_tokens(parent_msgs) > 256
        else parent_msgs
    )
    compacted_active = (
        self._summarize(active_msgs, strategy)
        if strategy._estimate_tokens(active_msgs) > 256
        else active_msgs
    )
    return compacted_parent + compacted_active
```

**Why cascading?** QueryAnalyst needs the *most informative* context possible.
Compacting too aggressively loses detail. The cascading approach tries the
least-destructive option first (compact the active agent only), then escalates
only as necessary.

---

## Step 2: Instruction Construction

```python
def build_instruction(self, context: dict[str, Any]) -> str:
    """Build the full system prompt: base + dynamic context."""
    base = self.config.instructions  # QUERY_ANALYST_INSTRUCTION

    parent = self.session.parent
    task = parent.task if parent else None

    dynamic = self._build_dynamic_context(task)
    return f"{base}\n\n{dynamic}"

def _build_dynamic_context(self, task: Task | None) -> str:
    """Build conditional context sections."""
    if task is None:
        return "---\nNo active task.\n"

    active_task = task.get_active_task() if hasattr(task, 'get_active_task') else task

    parts = [
        "---",
        "## Task Tree",
        task.display(),
    ]
    if active_task and active_task is not task:  # non-root active task
        parts.extend([
            "",
            "## Current Task",
            str(active_task),
        ])
    return "\n".join(parts)
```

The instruction includes:
1. **Base role instruction** (always) — from `QUERY_ANALYST_INSTRUCTION` constant
2. **Task Tree display** (when `parent.task is not None`) — `Task.display()` showing
   task hierarchy with status markers (`[ ]` not_started, `[*]` inprogress, `[x]` completed)
3. **Current Task** (when active task exists and is not the root) — the task the
   active agent is currently working on

When there is no active task, only "No active task." is appended.

---

## Step 3: Tools

Tools are selected dynamically based on whether an active task exists:

```python
def _get_tools(self) -> list[Tool]:
    """Select tools based on context: always QueryAnalystModeDecision + uncertainty;
    add read-only task tools if an active task exists.
    """
    from tinycua.constants.tools import (
        QUERY_ANALYST_BASE_TOOLS,
        QUERY_ANALYST_UNCERTAINTY_TOOLS,
        READ_ONLY_TASK_TOOLS,
    )

    tools = [
        *QUERY_ANALYST_BASE_TOOLS,          # QueryAnalystModeDecision
        *QUERY_ANALYST_UNCERTAINTY_TOOLS,   # ask_user / explore tools
        *self.config.extra_tools,
    ]

    parent = self.session.parent
    if parent and parent.task is not None:
        tools.extend(READ_ONLY_TASK_TOOLS)

    return tools
```

| Tool Set | When | Purpose |
|----------|------|---------|
| `QUERY_ANALYST_BASE_TOOLS` | Always | `QueryAnalystModeDecision` ClassificationTool (`"passthrough"`, `"worker"`, `"uncertain"`) |
| `QUERY_ANALYST_UNCERTAINTY_TOOLS` | Always | Tools for asking user / exploring when uncertain |
| `READ_ONLY_TASK_TOOLS` | Active task exists | Read-only task inspection (list tasks, get task detail, etc.) |
| `self.config.extra_tools` | Always | Injected by caller (tests, plugins) |

---

## Step 4: Enforcement (Internal Retry)

Like TaskAssessor, QueryAnalyst enforces that its verdict tool (`QueryAnalystModeDecision`)
must be called. If the agent finishes without calling it, the orchestrator retries
internally:

```python
async def run(self, user_query: str) -> AsyncIterator[dict]:
    self._assemble_session_context()
    instructions = self.build_instruction({"user_query": user_query})
    agent_query = json.dumps({"user_query": user_query})

    events: list[dict] = []
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=self._get_tools(),
            loop=QueryAnalystLoop(state=self.state),
        )

        text_parts: list[str] = []
        async for event in agent.run(query=agent_query, stream=True):
            events.append(event)
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event

        # Probe for QueryAnalystModeDecision tool call
        mode_label = self._extract_mode_decision(events)

        if mode_label is not None:
            # Success — verdict was called
            response_text = "".join(text_parts)
            self.session.append_assistant(
                content=response_text,
                metadata={
                    "orchestrator": "query_analyst",
                    "agent_name": self.config.name,
                },
            )
            self.state.mode_decision = ModeDecision(mode=mode_label)
            self.state.context_enhanced_query = ContextEnhancedQuery(
                context=response_text,
                query=user_query,
            )
            self.state.last_result = {
                "mode_decision": mode_label,
                "context": response_text,
            }
            return

        # No verdict — retry
        if attempt < max_retries:
            response_text = "".join(text_parts) or "(no response)"
            self.session.append_assistant(
                content=response_text,
                metadata={
                    "orchestrator": "query_analyst",
                    "agent_name": self.config.name,
                },
                )
            agent_query = (
                "Based on your analysis above, call QueryAnalystModeDecision "
                "with your final decision: 'passthrough', 'worker', or 'uncertain'."
            )
            events = []  # reset for next attempt

    # Max retries exhausted — default to passthrough
    self.state.mode_decision = ModeDecision(mode="passthrough")
    self.state.context_enhanced_query = ContextEnhancedQuery(
        context="(no verdict produced)",
        query=user_query,
    )
    self.state.last_result = {"mode_decision": "passthrough"}


def _extract_mode_decision(self, events: list[dict]) -> str | None:
    """Extract the latest QueryAnalystModeDecision tool call from events."""
    for event in reversed(events):
        if event.get("type") != "response.tool_call":
            continue
        if event.get("tool_name") != "QueryAnalystModeDecision":
            continue
        label = event.get("output", "")
        if label in ("passthrough", "worker", "uncertain"):
            return label
    return None
```

---

## Step 5: Output

Two outputs stored on `self.state`:

| Object | Source | Purpose |
|--------|--------|---------|
| `ModeDecision` | `QueryAnalystModeDecision` tool call output | Routing verdict for TinyCUA |
| `ContextEnhancedQuery` | Agent's final text response (markdown context) | Passed to InformationDigester in worker path |

- **`context`**: The agent's markdown output — relevant context snippets, keywords, task status
- **`query`**: The original `user_query`, passed through unchanged

---

## Complete Orchestrator

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import QueryAnalystConfig
from tinycua.constants.tools import (
    QUERY_ANALYST_BASE_TOOLS,
    QUERY_ANALYST_UNCERTAINTY_TOOLS,
    READ_ONLY_TASK_TOOLS,
)
from tinycua.loops.query_analyst_loop import QueryAnalystLoop
from tinycua.state.information import QueryAnalystState
from tinycua.state.mode_decision import ModeDecision, ContextEnhancedQuery
from tinycua.state.task import Task
from tinycua.utility.compaction import BaseCompaction


class QueryAnalyst(BaseAgentOrchestrator[QueryAnalystState]):
    """Query classification — transient agent whose output is NOT stored.

    Always called first by TinyCUA on every query. Decides:
      - passthrough → PrimaryAgent (no task) or active agent (task exists)
      - worker      → abort children + task, spawn InfoDigester → Worker
      - uncertain   → ask user or explore

    Session: transient (is_transient=True). Not in parent.child_sessions.
    Output: ModeDecision (routing) + ContextEnhancedQuery (context + query).
    """

    config: QueryAnalystConfig

    def __init__(self, config: QueryAnalystConfig | None = None):
        if config is None:
            config = QueryAnalystConfig()
        super().__init__(config=config, session=None)
        self.session.is_transient = True

    # ── Main entry point ─────────────────────────────────────────────

    async def run(self, user_query: str) -> AsyncIterator[dict]:
        # 1. Assemble session context from parent + active agent
        self._assemble_session_context()

        # 2. Build instruction: base + task tree + active task
        instructions = self.build_instruction({"user_query": user_query})

        # 3. Build query with user input only (context is in session_context)
        agent_query = json.dumps({"user_query": user_query})

        events: list[dict] = []
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            # 4. Build SDK Agent per-call with dynamic tool selection
            agent = Agent(
                name=self.config.name,
                instructions=instructions,
                llm_model=self.config.model,
                tools=self._get_tools(),
                loop=QueryAnalystLoop(state=self.state),
            )

            # 5. Stream — accumulate text + events, yield everything
            text_parts: list[str] = []
            async for event in agent.run(query=agent_query, stream=True):
                events.append(event)
                if event["type"] == "response.output_text.delta":
                    text_parts.append(event["delta"])
                yield event

            # 6. Probe for QueryAnalystModeDecision tool call
            mode_label = self._extract_mode_decision(events)

            if mode_label is not None:
                # Success — verdict was called
                response_text = "".join(text_parts)
                self.session.append_assistant(
                    content=response_text,
                    metadata={
                        "orchestrator": "query_analyst",
                        "agent_name": self.config.name,
                    },
                )
                self.state.mode_decision = ModeDecision(mode=mode_label)
                self.state.context_enhanced_query = ContextEnhancedQuery(
                    context=response_text,
                    query=user_query,
                )
                self.state.last_result = {
                    "mode_decision": mode_label,
                    "context": response_text,
                }
                return

            # No verdict — retry with follow-up
            if attempt < max_retries:
                response_text = "".join(text_parts) or "(no response)"
                self.session.append_assistant(
                    content=response_text,
                    metadata={
                        "orchestrator": "query_analyst",
                        "agent_name": self.config.name,
                    },
                )
                agent_query = (
                    "Based on your analysis above, call "
                    "QueryAnalystModeDecision with your final decision: "
                    "'passthrough', 'worker', or 'uncertain'."
                )
                events = []

        # Max retries exhausted — default to passthrough
        self.state.mode_decision = ModeDecision(mode="passthrough")
        self.state.context_enhanced_query = ContextEnhancedQuery(
            context="(no verdict produced)",
            query=user_query,
        )
        self.state.last_result = {"mode_decision": "passthrough"}

    # ── Context assembly ─────────────────────────────────────────────

    def _assemble_session_context(self) -> None:
        """Load parent + active-agent context into self.session.session_context."""
        parent = self.session.parent
        if parent is None:
            return

        parent_context = parent.get_messages()
        active_session = parent.get_active_session()
        active_context = (
            active_session.get_messages()
            if active_session is not parent
            else []
        )

        combined = parent_context + active_context
        self.session.session_context = self._compact_until_fits(combined)

    def _compact_until_fits(self, messages: list[dict]) -> list[dict]:
        """Apply cascading compaction until messages fit the context window."""
        strategy = (
            self.session.agent_state.agent_config.compaction_strategy
        )
        if strategy is None:
            return messages

        context_window = strategy._get_context_window(self.session)
        if context_window is None:
            return messages

        if strategy._estimate_tokens(messages) <= context_window:
            return messages

        parent = self.session.parent
        parent_msgs = parent.get_messages()
        active = parent.get_active_session()
        active_msgs = (
            active.get_messages() if active is not parent else []
        )

        # Try increasingly aggressive compaction
        candidates = [
            self._try_compact_active(active_msgs, parent_msgs, strategy),
            self._try_compact_parent(parent_msgs, active_msgs, strategy),
            self._try_compact_both(parent_msgs, active_msgs, strategy),
            self._compact_to_fit(parent_msgs + active_msgs, strategy),
        ]

        for candidate in candidates:
            if candidate is not None:
                if strategy._estimate_tokens(candidate) <= context_window:
                    return candidate

        # Last resort: keep compacting everything
        return self._compact_to_fit(messages, strategy)

    def _try_compact_active(
        self, active_msgs: list[dict], parent_msgs: list[dict],
        strategy: BaseCompaction,
    ) -> list[dict] | None:
        """Compact active agent context, leave parent as-is."""
        if not active_msgs:
            return None
        compacted = self._summarize(active_msgs, strategy)
        return parent_msgs + compacted

    def _try_compact_parent(
        self, parent_msgs: list[dict], active_msgs: list[dict],
        strategy: BaseCompaction,
    ) -> list[dict] | None:
        """Compact parent context, leave active agent as-is."""
        if not parent_msgs:
            return None
        compacted = self._summarize(parent_msgs, strategy)
        return compacted + active_msgs

    def _try_compact_both(
        self, parent_msgs: list[dict], active_msgs: list[dict],
        strategy: BaseCompaction,
    ) -> list[dict] | None:
        """Compact both parent and active agent context separately."""
        if not parent_msgs or not active_msgs:
            return None
        compacted_parent = self._summarize(parent_msgs, strategy)
        compacted_active = self._summarize(active_msgs, strategy)
        return compacted_parent + compacted_active

    def _compact_to_fit(
        self, messages: list[dict], strategy: BaseCompaction,
    ) -> list[dict]:
        """Keep compacting combined messages until they fit."""
        result = messages
        context_window = strategy._get_context_window(self.session)
        if context_window is None:
            return result
        while strategy._estimate_tokens(result) > context_window:
            result = self._summarize(result, strategy)
        return result

    def _summarize(
        self, messages: list[dict], strategy: BaseCompaction,
    ) -> list[dict]:
        """Compact messages into a single summary turn."""
        summary = strategy(messages)
        return [{"role": "user", "content": f"[Compacted context]\n{summary}"}]

    # ── Instruction ──────────────────────────────────────────────────

    def build_instruction(self, context: dict[str, Any]) -> str:
        base = self.config.instructions

        parent = self.session.parent
        task = parent.task if parent else None

        dynamic = self._build_dynamic_context(task)
        return f"{base}\n\n{dynamic}"

    def _build_dynamic_context(self, task: Task | None) -> str:
        if task is None:
            return "---\nNo active task.\n"

        parts = [
            "---",
            "## Task Tree",
            task.display(),
        ]

        active_task = (
            task.get_active_task() if hasattr(task, 'get_active_task')
            else None
        )
        if active_task and active_task is not task:
            parts.extend(["", "## Current Task", str(active_task)])

        return "\n".join(parts)

    # ── Tools ────────────────────────────────────────────────────────

    def _get_tools(self) -> list:
        tools = [
            *QUERY_ANALYST_BASE_TOOLS,
            *QUERY_ANALYST_UNCERTAINTY_TOOLS,
            *self.config.extra_tools,
        ]

        parent = self.session.parent
        if parent and parent.task is not None:
            tools.extend(READ_ONLY_TASK_TOOLS)

        return tools
```

---

## Config

`QueryAnalystConfig` — `name="query-analyst"`, `instructions=QUERY_ANALYST_INSTRUCTION`.
No agent-specific fields. See [`config/agents.md`](../config/agents.md#queryanalystconfig).

---

## State

`QueryAnalystState` — `mode_decision: ModeDecision | None`, `context_enhanced_query: ContextEnhancedQuery | None`,
`classification_score: float | None`.
See [`state/information.md`](../state/information.md#queryanalyststate).

---

## Loop

`QueryAnalystLoop(state=self.state)` — receives state by reference. Classification control flow.
No `max_iterations=1`. See [`loops/query_analyst_loop.md`](../loops/query_analyst_loop.md).

---

## Output

Two structured objects stored on `self.state`:

| Object | Fields | Purpose |
|--------|--------|---------|
| `ModeDecision` | `mode`, `score`, `confidence`, `reasons`, `uncertain_next_action?` | Routing verdict for TinyCUA |
| `ContextEnhancedQuery` | `context` (agent markdown output), `query` (original user_query) | Passed to InformationDigester in worker path |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transient session | `is_transient = True`; not in `child_sessions`; chat_history propagates, session_context does not | Output consumed inline by TinyCUA; tree traversal skips; audit trail preserved via chat_history |
| No session on `run()` signature | `run(user_query)` only; session via `self.session` | Session owned by orchestrator; caller links via `add_child` before `run` |
| Parent context assembly | `_assemble_session_context()` pulls parent + active agent | QueryAnalyst has no history — must build its own picture |
| Cascading compaction | Try 4 progressive levels before brute-force | Least destructive first; preserves as much context as possible |
| Compaction threshold >= parent | `compaction_strategy` config must be >= parent's | Ensures QueryAnalyst never loses information the parent could hold |
| Conditional task display | Task tree + current task only when task exists | Avoids polluting instruction with irrelevant task information |
| Conditional read-only task tools | `READ_ONLY_TASK_TOOLS` only when active task exists | QueryAnalyst needs task detail to classify correctly when tasks are active |
| Passthrough sub-routing | `get_active_session()` determines target | No active task → PrimaryAgent; active task → active agent |
| Worker mode aborts | Terminate all children, `session.task = None` | Fresh start for the worker chain |
| ContextEnhancedQuery split | `context` (agent response) + `query` (original) | Downstream agents receive both the analysis and the raw query |
| ModeDecision from tool call | `QueryAnalystModeDecision` tool call, not JSON parsing | Structured verdict guaranteed; no parsing fragility |
| Mandatory verdict via retry | Orchestrator retries up to 3x if verdict not called | Same pattern as TaskAssessor; guarantees decision is always produced |
| Default on exhaustion | `"passthrough"` after max retries | Safe fallback — routes to existing agents rather than starting fresh |


---


---


---

## See also

Prev : [Orchestrator Factory](factory.md) | Next : [`InformationDigester`](information_digester.md)


## Related

- [Classification loop](../loops/query_analyst_loop.md)
- [ModeDecision + ContextEnhancedQuery output](../state/mode_decision.md)
- [QUERY_ANALYST_BASE_TOOLS + UNCERTAINTY_TOOLS](../constants/tools.md)
- [Task.display() for tree rendering](../state/task.md)
- [Called first by TinyCUA](tinycua.md)
- [Session context assembly + cascading compaction](../state/session.md)
