# Loop Errors

> **File:** `docs/design/exceptions/loops.md`
> **Package:** `tinycua.exceptions.loops`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Error Hierarchy

Thin wrappers around SDK exceptions. Loops do not implement their own retry logic —
they rely on SDK infrastructure and raise these typed errors when SDK retries are
exhausted.

```python
class LoopError(Exception):
    """Base class for all loop errors."""

class LoopTransientError(LoopError):
    """Transient failure — caller may retry (e.g., rate limit exhausted)."""

class LoopPermanentError(LoopError):
    """Permanent failure — caller should not retry (e.g., auth failure)."""

class LoopOutputValidationError(LoopError):
    """Output was not valid JSON after all retry attempts by the orchestrator."""
```

---

## Usage

| Error Case | Raised When |
|------------|-------------|
| `LoopTransientError` | SDK's `LLMClient` exhausts its retries on a transient error |
| `LoopPermanentError` | SDK raises a permanent error immediately or a required tool is missing at construction |
| `LoopOutputValidationError` | Orchestrator exhausts retry attempts on bad JSON output |
| `ValueError` | Invalid input received before any LLM call |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Thin wrappers | Extend `Exception`, not custom hierarchy | Callers can catch `LoopError` for all loop errors or specific subtypes |
| No custom retry logic | Rely on SDK | SDK already handles transient retries, backoff, and permanent error raising |
| Separate package | `tinycua.exceptions` | Not coupled to loops, agents, or any specific module |
