# Result Reviewer

> **File:** `docs/design/agents/result_reviewer.md`
> **Package:** `tinycua.agents.result_reviewer`

---

## Wrapper Class

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import ResultReviewerConfig
from tinycua.constants.tools import RESULT_REVIEWER_BASE_TOOLS
from tinycua.loops.result_review_loop import ResultReviewLoop
from tinycua.utility.schema_validator import SchemaValidator
from tinycua.state.information import ResultReviewerState
from tinycua.state import ReviewerDecision


class ResultReviewer(BaseAgentWrapper[ResultReviewerState]):
    """Result review agent — ResultReviewLoop."""

    state: ResultReviewerState

    def __init__(self, config: ResultReviewerConfig):
        super().__init__(config, state_factory=ResultReviewerState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*RESULT_REVIEWER_BASE_TOOLS, *self.config.extra_tools],
            loop=ResultReviewLoop(deterministic_rules=self.config.deterministic_rules),
        )

    async def run(self, task: dict, task_result: dict, execution_log=None) -> dict:
        self.state.last_query = {"task": task, "task_result": task_result}
        input_msg = json.dumps({"task": task, "task_result": task_result, "execution_log": execution_log or []})
        raw = await self.agent.run(query=input_msg)
        result = SchemaValidator(validation_fn=validate_reviewer_decision).validate(raw)
        self.state.reviewer_decision = ReviewerDecision(**result)
        self.state.last_review_status = result.get("status")
        self.state.last_result = result
        return result
```

## Config

`ResultReviewerConfig` — `name="result-reviewer"`, `instructions=RESULT_REVIEWER_PROMPT`, `deterministic_rules: list[DeterministicRule]`.
See [`config/agents.md`](../config/agents.md#resultreviewerconfig).

## State

`ResultReviewerState` — `reviewer_decision: ReviewerDecision | None`, `deterministic_failures: list[str]`, `last_review_status: ReviewStatus | None`.
See [`state/information.md`](../state/information.md#resultreviewerstate).

## Loop

`ResultReviewLoop` — two-phase review. See [`loops/result_review_loop.md`](../loops/result_review_loop.md).

## Tools

`RESULT_REVIEWER_BASE_TOOLS = []`. Review criteria in prompt; rules in loop.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deterministic rules in config | `config.deterministic_rules` | Per-deployment customization |
| Deterministic wins conflicts | Skip Phase 2 on failure | Schema authority |
