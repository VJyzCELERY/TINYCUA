# Result Reviewer

> **File:** `docs/design/result-reviewer.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **Architecture reference:** [`../architecture/result-reviewer.md`](../architecture/result-reviewer.md)
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Role

The Result Reviewer evaluates a completed `TaskResult` and produces a `ReviewerDecision`
with one of four statuses: `accepted`, `retry`, `replan`, or `escalate_user`. Uses a
two-phase approach: pluggable deterministic checks followed by LLM semantic review.

---

## Wrapper Class

**File:** `tinycua/agents/result_reviewer.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import ResultReviewerConfig
from tinycua.constants.tools import RESULT_REVIEWER_BASE_TOOLS
from tinycua.loops.result_review_loop import ResultReviewLoop
from tinycua.loops.schema_validator import SchemaValidator
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
            loop=ResultReviewLoop(
                deterministic_rules=self.config.deterministic_rules,
            ),
        )

    async def run(
        self, task: dict, task_result: dict, execution_log: list[dict] | None = None
    ) -> dict:
        self.state.last_query = {"task": task, "task_result": task_result}
        input_msg = json.dumps({
            "task": task,
            "task_result": task_result,
            "execution_log": execution_log or [],
        })
        raw = await self.agent.run(query=input_msg)
        result = SchemaValidator(validation_fn=validate_reviewer_decision).validate(raw)
        self.state.reviewer_decision = ReviewerDecision(**result)
        self.state.last_review_status = result.get("status")
        self.state.last_result = result
        return result
```

---

## Config

**File:** `tinycua/config/agents.py`

```python
@dataclass
class ResultReviewerConfig(AgentConfigBase):
    name: str = "result-reviewer"
    instructions: str = RESULT_REVIEWER_PROMPT
    deterministic_rules: list[DeterministicRule] = field(
        default_factory=lambda: [DEFAULT_SCHEMA_RULE, DEFAULT_FIELDS_RULE]
    )
```

---

## State

**File:** `tinycua/state/information.py`

```python
@dataclass
class ResultReviewerState(StateInformation):
    reviewer_decision: ReviewerDecision | None = None
    deterministic_failures: list[str] = field(default_factory=list)
    last_review_status: ReviewStatus | None = None
```

---

## Loop

`ResultReviewLoop` — two-phase execution.
See [`loop-strategies.md`](loop-strategies.md#resultreviewloop).

---

## Tools

**File:** `tinycua/constants/tools.py`

```python
RESULT_REVIEWER_BASE_TOOLS: list[Tool] = []
```

No inherent tools. Review criteria are in the prompt; deterministic rules are in the loop.

---

## Deterministic Rules

Pluggable rules registered at construction time. Default rules provided:

| Rule | Check | Severity on Failure |
|------|-------|---------------------|
| `SchemaValidity` | TaskResult matches expected schema | `escalate` |
| `RequiredFields` | Required fields present and non-null | `replan` |

Custom rules can be added via `ResultReviewerConfig.deterministic_rules`:

```python
ResultReviewerConfig(
    deterministic_rules=[
        DeterministicRule(name="SchemaValidity", check=check_schema),
        DeterministicRule(name="RequiredFields", check=check_fields),
        DeterministicRule(name="CustomCheck", check=my_custom_check),
    ],
)
```

---

## Prompt Contract

**File:** `tinycua/agents/prompts.py`

The prompt must include:
- **Role**: Result review agent — evaluate task output and decide next step
- **Input contract**: `task`, `task_result`, `execution_log`
- **Output schema**: `ReviewerDecision` with `task_id`, `status`, `reason`, `confidence`, optional `context_updates`, `retry_instructions`
- **Status semantics**:
  - `accepted` → compute `context_updates` for unfinished/upcoming tasks
  - `retry` → include `retry_instructions` for the executor
  - `replan` → record rationale for roadmap revision
  - `escalate_user` → include clear user-facing explanation
- **Guardrails**: LLM review handles semantic evaluation; deterministic phase handles schema-level validation

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deterministic rules first | Phase 1 before LLM | Schema failures should not waste an LLM call |
| Deterministic wins conflicts | Skip Phase 2 on deterministic failure | Safety: deterministic checks are the authority |
| Pluggable rules | Constructor parameter, not hardcoded | Different reviewer configs can add/replace rules without subclassing |
