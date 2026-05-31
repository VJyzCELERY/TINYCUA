# ResultReviewLoop

> **File:** `docs/design/loops/result_review_loop.md`
> **Package:** `tinycua.loops.result_review_loop`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

Two-phase review loop for the Result Reviewer. Receives `ResultReviewerState` by reference.
Phase 1 writes `self.state.deterministic_failures` on failure.

1. **Phase 1 (deterministic)**: Pluggable rules for schema validity, required fields, etc.
2. **Phase 2 (LLM)**: SDK `BaseLoop` for semantic review — correctness, sufficiency, context propagation.

Produces a `ReviewerDecision` with status: `accepted`, `retry`, `replan`, or `escalate_user`.

---

## Class Contract

**File:** `tinycua/loops/result_review_loop.py`

```python
from dataclasses import dataclass
from typing import Callable
from tinycua_sdk.agent.loop import BaseLoop
from tinycua.state.information import ResultReviewerState


@dataclass
class DeterministicRule:
    name: str
    check: Callable[[dict, dict, dict], DeterministicRuleResult]


@dataclass
class DeterministicRuleResult:
    passed: bool
    reason: str | None = None
    severity: str | None = None  # "escalate" | "replan"


class ResultReviewLoop(BaseLoop):
    """Two-phase review: deterministic checks + LLM semantic review."""

    def __init__(
        self,
        state: ResultReviewerState,
        deterministic_rules: list[DeterministicRule],
    ):
        super().__init__()
        self.state = state
        self.deterministic_rules = deterministic_rules

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        # Phase 1: Deterministic checks
        task, task_result, execution_log = self._extract_from_messages(messages)
        for rule in self.deterministic_rules:
            result = rule.check(task, task_result, execution_log)
            if not result.passed and result.severity in ("escalate", "replan"):
                self.state.deterministic_failures.append(result.reason)
                return  # Skip Phase 2 — deterministic failure

        # Phase 2: LLM semantic review via SDK BaseLoop
        async for event in super().run(agent, messages, tools, override_instructions, stream=True):
            yield event
```

---

## Deterministic Rules

Default rules provided:

| Rule | Check | Severity on Failure |
|------|-------|---------------------|
| `SchemaValidity` | Output matches expected TaskResult schema | `escalate` |
| `RequiredFields` | Required fields present and non-null | `replan` |

Custom rules are added via `ResultReviewerConfig.deterministic_rules`.

---

## Decision Outputs

| Status | Condition | Output Fields |
|--------|-----------|---------------|
| `accepted` | All checks pass + LLM confirms | `context_updates` for unfinished/upcoming tasks |
| `retry` | Semantic concerns, recoverable | `retry_instructions` for the executor |
| `replan` | Decomposition insufficient | Rationale for roadmap revision |
| `escalate_user` | Cannot resolve automatically | User-facing explanation |

---

## Conflict Resolution

If Phase 1 (deterministic) fails with `escalate` or `replan`, Phase 2 (LLM) is **skipped entirely**.
Deterministic checks are the authority for schema-level validation. Failures are stored in
`self.state.deterministic_failures`.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deterministic first | Phase 1 before Phase 2 | Schema failures shouldn't waste an LLM call |
| Deterministic wins conflicts | Skip Phase 2 on failure | Safety: deterministic checks are the authority |
| Pluggable rules | Constructor parameter | Different reviewer configs can add/replace rules |
| State via constructor | `ResultReviewLoop(state=self.state)` | Phase 1 writes failures to state directly |


---

## See also

Prev : [`InformationDigestionLoop`](information_digestion_loop.md) | Next : [`MainLoop` Orchestration](main_loop.md)
