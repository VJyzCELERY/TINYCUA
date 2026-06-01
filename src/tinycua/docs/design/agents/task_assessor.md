# Task Assessor

> **File:** `docs/design/agents/task_assessor.md`
> **Package:** `tinycua.agents.task_assessor`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`TaskAssessor` evaluates the task tree and decides whether further analysis is needed.
It is called **through TaskCreator** — not directly by Worker orchestration. TaskCreator
wraps TaskAnalyzer → TaskAssessor and returns the aggregated result.

Two outputs:
1. `AssessorVerdict` tool call → `"analyze"` (keep analyzing) or `"stop"` (done)
2. Final response text → fed back into TaskAnalyzer as the analysis query

---

## Session

TaskAssessor is a **regular (non-transient) session** — it owns a session node in
the tree. Its `session_context` accumulates across retries (see enforcement below).

---

## `run()` Method

### Signature

```python
async def run(
    self,
    task_tree: dict | str,   # Task tree display or serialized state
    query: str,               # The analysis query (from TaskAnalyzer output)
) -> AsyncIterator[dict]:
```

### Flow

```
run(task_tree, query)
  │
  ├─ 1. Build instruction: base + task tree display
  │
  ├─ 2. Build query from input
  │
  ├─ 3. Build SDK Agent with AssessorVerdict + read-only task tools
  │
  ├─ 4. Stream → collect events
  │
  ├─ 5. Check: was AssessorVerdict called?
  │   ├─ Yes → extract verdict + response text → DONE
  │   └─ No  → append follow-up to session_context
  │             → rebuild Agent → re-stream (go to 3)
  │             → max retries: 3
  │
  └─ 6. Store verdict + response text in state
```

---

## AssessorVerdict Tool

A `ClassificationTool` with two labels — same pattern as QueryAnalyst's tool:

```python
from tinycua.tools.classification import ClassificationTool

# In constants/tools.py:
TASK_ASSESSOR_BASE_TOOLS: list[Tool] = [
    ClassificationTool(
        name="AssessorVerdict",
        labels=["analyze", "stop"],
    ),
]
```

| Label | Meaning |
|-------|---------|
| `"analyze"` | The task tree needs further analysis — loop back to TaskAnalyzer |
| `"stop"` | Assessment is complete — proceed to execution |

---

## Enforcement (Internal Retry)

If the agent finishes its stream without ever calling `AssessorVerdict`, the
orchestrator **internally retries** by appending a follow-up message to the
session context and re-running the agent:

```python
async def run(self, task_tree: dict | str, query: str) -> AsyncIterator[dict]:
    """Assess the task tree with mandatory AssessorVerdict call."""
    instructions = self.build_instruction({"task_tree": task_tree})

    agent = Agent(
        name=self.config.name,
        instructions=instructions,
        llm_model=self.config.model,
        tools=self._get_tools(),
        loop=ReActAgentLoop(state=self.state),
    )

    # ── Initial run ──────────────────────────────────────────────────
    initial_query = self._build_query(task_tree, query)
    events: list[dict] = []

    text_parts: list[str] = []
    async for event in agent.run(query=initial_query, stream=True):
        events.append(event)
        if event["type"] == "response.output_text.delta":
            text_parts.append(event["delta"])
        yield event

    response_text = "".join(text_parts)
    verdict = self._extract_verdict(events)

    if verdict is not None:
        self.session.append_assistant(
            content=response_text,
            metadata={"orchestrator": "task_assessor", "agent_name": self.config.name},
        )
        self.state.verdict = verdict
        self.state.analysis = response_text
        self.state.last_result = {"verdict": verdict, "analysis": response_text}
        return

    # No verdict — record initial response, then retry
    self.session.chat_history.append(ChatRecord(
        id=str(uuid4()), type="agent",
        metadata={"orchestrator": "task_assessor", "agent_name": self.config.name},
        content={"text": response_text},
    ))
    async for event in self._retry_agent(
        agent=agent,
        retry_query=(
            "Based on the assessment above, call AssessorVerdict with "
            "your final decision: 'analyze' or 'stop'."
        ),
    ):
        yield event

    if self.state.verdict is None:
        self.state.verdict = "stop"
        self.state.analysis = "Assessment timed out — no verdict produced."
        self.state.last_result = {"verdict": "stop", "analysis": self.state.analysis}


async def _retry_agent(
    self,
    agent: Agent,
    retry_query: str,
    max_retries: int = 3,
) -> AsyncIterator[dict]:
    """Retry until AssessorVerdict is called. Stores state on success."""
    events: list[dict] = []

    for attempt in range(1, max_retries + 1):
        text_parts: list[str] = []
        async for event in agent.run(query=retry_query, stream=True):
            events.append(event)
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event

        response_text = "".join(text_parts)
        verdict = self._extract_verdict(events)

        if verdict is not None:
            self.session.append_assistant(
                content=response_text,
                metadata={"orchestrator": "task_assessor", "agent_name": self.config.name},
            )
            self.state.verdict = verdict
            self.state.analysis = response_text
            return

        if attempt < max_retries:
            self.session.chat_history.append(ChatRecord(
                id=str(uuid4()), type="agent",
                metadata={"orchestrator": "task_assessor", "agent_name": self.config.name},
                content={"text": response_text or "(no response)"},
            ))


def _extract_verdict(self, events: list[dict]) -> str | None:
    """Extract the latest AssessorVerdict tool call result from events."""
    for event in reversed(events):
        if event.get("type") != "response.tool_call":
            continue
        if event.get("tool_name") != "AssessorVerdict":
            continue
        # ClassificationTool stores the selected label in the output
        label = event.get("output", "")
        if label in ("analyze", "stop"):
            return label
    return None
```

**Key details:**
- The follow-up message appended to `session_context` is a direct instruction to call the tool
- Each retry rebuilds the Agent with the updated `session_context`
- Latest `AssessorVerdict` call wins (reversed iteration in `_extract_verdict`)
- Max 3 retries; if all fail, default to `"stop"` to prevent infinite loops

---

## Output Parsing

After a successful run:

```python
# Verdict from tool call
self.state.verdict  # "analyze" or "stop"

# Response text — becomes the query for TaskAnalyzer
self.state.analysis  # agent's markdown response
```

---

## Complete Orchestrator

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import TaskAssessorConfig
from tinycua.constants.tools import TASK_ASSESSOR_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.state.information import TaskAssessorState


class TaskAssessor(BaseAgentOrchestrator[TaskAssessorState]):
    """Task assessment with mandatory AssessorVerdict tool call.

    Evaluates the task tree and decides whether further analysis is
    needed. Internally retries if the agent fails to call AssessorVerdict.
    Called through TaskCreator.
    """

    config: TaskAssessorConfig

    def __init__(self, config: TaskAssessorConfig | None = None):
        if config is None:
            config = TaskAssessorConfig()
        super().__init__(config=config, session=None)

    # ── Main entry point ─────────────────────────────────────────────

    async def run(
        self,
        task_tree: dict | str,
        query: str,
    ) -> AsyncIterator[dict]:
        instructions = self.build_instruction({"task_tree": task_tree})

        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=self._get_tools(),
            loop=ReActAgentLoop(state=self.state),
        )

        # ── Initial run ──────────────────────────────────────────────
        initial_query = self._build_query(task_tree, query)
        events: list[dict] = []

        text_parts: list[str] = []
        async for event in agent.run(query=initial_query, stream=True):
            events.append(event)
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event

        response_text = "".join(text_parts)
        verdict = self._extract_verdict(events)

        if verdict is not None:
            self.session.append_assistant(
                content=response_text,
                metadata={"orchestrator": "task_assessor", "agent_name": self.config.name},
            )
            self.state.verdict = verdict
            self.state.analysis = response_text
            self.state.last_result = {"verdict": verdict, "analysis": response_text}
            return

        # No verdict — record initial response, then retry
        self.session.chat_history.append(ChatRecord(
            id=str(uuid4()), type="agent",
            metadata={"orchestrator": "task_assessor", "agent_name": self.config.name},
            content={"text": response_text},
        ))
        async for event in self._retry_agent(
            agent=agent,
            retry_query=(
                "Based on the assessment above, call AssessorVerdict with "
                "your final decision: 'analyze' or 'stop'."
            ),
        ):
            yield event

        if self.state.verdict is None:
            self.state.verdict = "stop"
            self.state.analysis = "Assessment timed out — no verdict produced."
            self.state.last_result = {
                "verdict": "stop",
                "analysis": self.state.analysis,
            }

    # ── Retry loop ────────────────────────────────────────────────────

    async def _retry_agent(
        self,
        agent: Agent,
        retry_query: str,
        max_retries: int = 3,
    ) -> AsyncIterator[dict]:
        events: list[dict] = []

        for attempt in range(1, max_retries + 1):
            text_parts: list[str] = []
            async for event in agent.run(query=retry_query, stream=True):
                events.append(event)
                if event["type"] == "response.output_text.delta":
                    text_parts.append(event["delta"])
                yield event

            response_text = "".join(text_parts)
            verdict = self._extract_verdict(events)

            if verdict is not None:
                self.session.append_assistant(
                    content=response_text,
                    metadata={"orchestrator": "task_assessor", "agent_name": self.config.name},
                )
                self.state.verdict = verdict
                self.state.analysis = response_text
                return

            if attempt < max_retries:
                self.session.chat_history.append(ChatRecord(
                    id=str(uuid4()), type="agent",
                    metadata={"orchestrator": "task_assessor", "agent_name": self.config.name},
                    content={"text": response_text or "(no response)"},
                ))

    # ── Verdict extraction ───────────────────────────────────────────

    def _extract_verdict(self, events: list[dict]) -> str | None:
        """Extract the latest AssessorVerdict tool call from events."""
        for event in reversed(events):
            if event.get("type") != "response.tool_call":
                continue
            if event.get("tool_name") != "AssessorVerdict":
                continue
            label = event.get("output", "")
            if label in ("analyze", "stop"):
                return label
        return None

    # ── Query construction ───────────────────────────────────────────

    def _build_query(self, task_tree: dict | str, query: str) -> str:
        """Build the initial query for the agent."""
        if isinstance(task_tree, dict):
            tree_str = json.dumps(task_tree, indent=2)
        else:
            tree_str = task_tree

        return (
            f"## Task Tree\n\n{tree_str}\n\n"
            f"## Analysis Query\n\n{query}\n\n"
            f"Assess which tasks need further analysis. "
            f"Call AssessorVerdict with 'analyze' or 'stop'."
        )

    # ── Tools ────────────────────────────────────────────────────────

    def _get_tools(self) -> list:
        return [
            *TASK_ASSESSOR_BASE_TOOLS,    # AssessorVerdict
            *self.config.extra_tools,
        ]

    # ── Instruction ──────────────────────────────────────────────────

    def build_instruction(self, context: dict[str, Any]) -> str:
        base = self.config.instructions  # TASK_ASSESSOR_INSTRUCTION
        task_tree = context.get("task_tree", "No task tree provided.")
        return f"{base}\n\n---\n## Task Tree\n{task_tree}"
```

---

## Config

`TaskAssessorConfig` — `name="task-assessor"`, `instructions=TASK_ASSESSOR_INSTRUCTION`.
See [`config/agents.md`](../config/agents.md#taskassessorconfig).

---

## State

`TaskAssessorState`:

```python
@dataclass
class TaskAssessorState(StateObject):
    verdict: str | None = None     # "analyze" or "stop"
    analysis: str | None = None    # agent's markdown response (→ TaskAnalyzer query)
```

See [`state/information.md`](../state/information.md#taskassessorstate).

---

## Loop

`ReActAgentLoop(state=self.state)` — shared loop with state reference.
No custom loop — enforcement is in the orchestrator, not the loop.

See [`loops/react_agent.md`](../loops/react_agent.md).

---

## Tools

`TASK_ASSESSOR_BASE_TOOLS = [AssessorVerdict]` — a `ClassificationTool` with labels
`["analyze", "stop"]`. The orchestrator enforces that it must be called.

See [`constants/tools.md`](../constants/tools.md).

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Mandatory verdct via retry | Orchestrator probes tool calls, retries with follow-up | Guarantees a verdict is produced; no custom loop needed |
| Latest call wins | Reversed iteration over events | Agent may refine its decision across retries |
| Follow-up in session_context | Append instruction message before re-stream | Agent gets context of what was already discussed |
| Max 3 retries | Hard cap, default to `"stop"` | Prevents infinite loops; safe default on failure |
| No custom loop | `ReActAgentLoop` | Enforcement at orchestrator level keeps loop simple |
| Verdict as ClassificationTool | `AssessorVerdict(labels=["analyze", "stop"])` | Same pattern as QueryAnalyst; consistent tool interface |
| Analysis feeds TaskAnalyzer | `self.state.analysis` becomes the query for the next TaskAnalyzer.run() | Creates the analysis → assessment → (loop back) cycle |


---


---


---

## See also

Prev : [`TaskAnalyzer`](task_analyzer.md) | Next : [`TaskCreator`](task_creator.md)


## Related

- [Called through TaskCreator](task_creator.md)
- [AssessorVerdict ClassificationTool](../constants/tools.md)
- [QueryAnalyst — same verdict pattern](query_analyst.md)
- [Task tree from TaskAnalyzer](../state/task.md)
