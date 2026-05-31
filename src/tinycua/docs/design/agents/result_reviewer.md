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
from tinycua.constants.prompts import RESULT_REVIEWER_PROMPT
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
        self.state.last_query = {"task": task, "task_result": task_result}
        self.state.accumulated_text = []

        input_msg = json.dumps({
            "task": task,
            "task_result": task_result,
            "execution_log": execution_log or [],
        })

        agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*RESULT_REVIEWER_BASE_TOOLS, *self.config.extra_tools],
            loop=ResultReviewLoop(
                state=self.state,
                deterministic_rules=self.config.deterministic_rules,
            ),
        )

        async for event in agent.run(query=input_msg, stream=True):
            if event["type"] == "response.output_text.delta":
                self.state.accumulated_text.append(event["delta"])
            elif event["type"] == "response.usage":
                self.state.token_usage = event["usage"]
            yield event

        raw = "".join(self.state.accumulated_text)
        result = json.loads(raw)
        self.state.reviewer_decision = ReviewerDecision(**result)
        self.state.last_review_status = result.get("status")
        self.state.last_result = result
```

---

## Config

`ResultReviewerConfig` — `name="result-reviewer"`, `instructions=RESULT_REVIEWER_PROMPT`,
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
