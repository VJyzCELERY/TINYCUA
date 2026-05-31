# Schema Validator

> **File:** `docs/design/utility/schema_validator.md`
> **Package:** `tinycua.utility.schema_validator`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`SchemaValidator` wraps an SDK `Agent.run()` call with output validation and retry.
On validation failure, it retries the agent with the validation error included in
the prompt context. After max retries exhausted, it raises `LoopOutputValidationError`.

---

## Class Contract

```python
from tinycua_sdk.agent import Agent
from tinycua_sdk.tools.decorators import Tool


class SchemaValidator:
    """Validates structured LLM output against type schemas.

    Uses the SDK's event/model infrastructure for parsing and retry.
    Does NOT implement its own LLM calling or retry logic — it wraps
    an SDK Agent.run() call and validates the result.
    """

    def __init__(
        self,
        validation_fn: Callable[[Any], tuple[bool, str | None]],
        max_validation_retries: int = 2,
    ): ...

    async def validate(
        self,
        agent: Agent,
        messages: list[dict],
        system_prompt: str,
        tools: list[Tool] | None = None,
    ) -> Any:
        """Run Agent, validate output, retry with error context on failure.

        Returns: Validated output (parsed into the expected type).
        Raises: LoopOutputValidationError after max retries exhausted.
        """
```

---

## Usage Pattern

Used in wrapper `run()` methods after calling `self.agent.run()`:

```python
class QueryAnalyst(BaseAgentWrapper):
    async def run(self, user_query, chat_history=None, session_context=None):
        ...
        raw = await self.agent.run(query=str(input_msg))
        result = SchemaValidator(
            validation_fn=validate_classification_output
        ).validate(raw)
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        return result
```

---

## Nested Validation

Supports validating nested structures (e.g., `Task` tree with `child_tasks`).
The `validation_fn` receives the raw output and returns `(passed: bool, error_msg: str | None)`.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Wraps SDK Agent, not standalone | `validate()` takes an `Agent` | Uses SDK's existing LLM calling, retry, and error handling |
| Configurable retries | `max_validation_retries` | Different agents may need different retry thresholds |
| Separate package | `tinycua.utility` | Generic infrastructure; not coupled to loops or agents |
