# Loop Errors

> **File:** `docs/design/exceptions/loops.md`
> **Package:** `tinycua.exceptions.loops`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Error Hierarchy

Thin wrappers around SDK exceptions. Loops do not implement their own retry logic —
they rely on SDK infrastructure and raise these typed errors when SDK retries are
exhausted.

```text
LoopError extends Exception
    Base class for all loop errors.

LoopTransientError extends LoopError
    Transient failure — caller may retry (e.g., rate limit exhausted).

LoopPermanentError extends LoopError
    Permanent failure — caller should not retry (e.g., auth failure).

LoopOutputValidationError extends LoopError
    Output was not valid after all loop-owned retry/repair attempts.
```

---

## Usage

| Error Case | Raised When |
|------------|-------------|
| `LoopTransientError` | SDK's `LLMClient` exhausts its retries on a transient error |
| `LoopPermanentError` | SDK raises a permanent error immediately or a required tool is missing at construction |
| `LoopOutputValidationError` | AgentLoop exhausts retry/repair attempts on invalid structured output |
| `ValueError` | Invalid input received before any LLM call |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Thin wrappers | Extend `Exception`, not custom hierarchy | Callers can catch `LoopError` for all loop errors or specific subtypes |
| No custom retry logic | Rely on SDK | SDK already handles transient retries, backoff, and permanent error raising |
| Separate package | `tinycua.exceptions` | Not coupled to loops, agents, or any specific module |


---


---


---

## See also

Prev : [Agent Instruction Constants](../constants/instructions.md) | Next : [Loop Strategies Overview](../loops/overview.md)


## Related

- [Loop hierarchy — all loops inherit BaseLoop](../loops/overview.md)
