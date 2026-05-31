# Result Reviewer

> **File:** `docs/design/agents/result_reviewer.md`
> **Package:** `tinycua.agents.result_reviewer`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import ResultReviewerConfig
from tinycua.constants.tools import RESULT_REVIEWER_BASE_TOOLS
from tinycua.loops.result_review_loop import ResultReviewLoop
from tinycua.state.information import ResultReviewerState
from tinycua.state import ReviewerDecision


class ResultReviewer(BaseAgentOrchestrator[ResultReviewerState]):
    """Result review — ResultReviewLoop with direct state reference."""

    config: ResultReviewerConfig

    def __init__(self, config: ResultReviewerConfig | None = None):
        if config is None:
            config = ResultReviewerConfig()
        self.config = config
        self.state = ResultReviewerState()

    async def run(
        self,
        task: dict,
        task_result: dict,
        execution_log: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({})

        # 2. Build query from domain input
        query = json.dumps({
            "task": task,
            "task_result": task_result,
            "execution_log": execution_log or [],
        })

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*RESULT_REVIEWER_BASE_TOOLS, *self.config.extra_tools],
            loop=ResultReviewLoop(
                state=self.state,
                deterministic_rules=self.config.deterministic_rules,
            ),
        )

        # 4. Iterate stream — accumulate text, yield everything to caller
        text_parts: list[str] = []
        async for event in agent.run(query=query, stream=True):
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event

        # 5. After stream ends — parse and store typed state
        raw = "".join(text_parts)
        result = json.loads(raw)
        self.state.reviewer_decision = ReviewerDecision(**result)
        self.state.last_review_status = result.get("status")
        self.state.last_result = result
```

---

## Config

`ResultReviewerConfig` — `name="result-reviewer"`, `instructions=RESULT_REVIEWER_INSTRUCTION`,
`deterministic_rules: list[DeterministicRule]`.
See [`config/agents.md`](../config/agents.md#resultreviewerconfig).

---

## State

`ResultReviewerState` — `reviewer_decision: ReviewerDecision | None`,
`deterministic_failures: list[str]`, `last_review_status: ReviewStatus | None`.
See [`state/information.md`](../state/information.md#resultreviewerstate).

---

## Loop

`ResultReviewLoop(state=self.state, deterministic_rules=...)` — two-phase review.
Phase 1 (deterministic) may write `self.state.deterministic_failures` before skipping Phase 2.
See [`loops/result_review_loop.md`](../loops/result_review_loop.md).

---

## Tools

`RESULT_REVIEWER_BASE_TOOLS = []`. Review criteria in prompt; rules in loop.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deterministic rules in config | `config.deterministic_rules` | Per-deployment customization |
| Deterministic wins conflicts | Skip Phase 2 on failure | Schema authority |


---

## See also

Prev : [`TaskExecutor`](task_executor.md) | Next : [`PrimaryAgent`](primary_agent.md)
