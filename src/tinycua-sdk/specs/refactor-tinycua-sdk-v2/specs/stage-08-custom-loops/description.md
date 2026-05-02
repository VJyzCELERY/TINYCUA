# Stage 8: Extensibility — Custom Loops — Description

## Purpose
Make `BaseLoop` a clean extension point for consumers. Custom loops can override execution behavior by subclassing and overriding `run()`, with access to `agent._call_llm()` for LLM calls without reimplementing transport logic. No hook system — customization is done by direct subclassing.

## What You'll Find Here
- **`spec.md`** — Requirements for the `BaseLoop` interface, the protected `_call_llm()` helper, and custom loop examples (`ReActLoop`, `PlanThenExecuteLoop`). Includes 6 success criteria covering override behavior, LLM access, cancellation, iteration limits, ReAct example, and integration tests.
- **`design.md`** — Full implementations: clean `BaseLoop.run()` signature, `_call_llm()` on `Agent`, complete `ReActLoop` and `PlanThenExecuteLoop` examples with reasoning/execution patterns, and design decisions on model config copying for frozen Pydantic models.

## What This Stage Does NOT Do
- It does not add a hook system — that was removed in Stage 0 because it was unwired.
- It does not provide built-in custom loop types beyond the examples — consumers create their own.
- It does not change the default execution behavior — only adds an extension mechanism.

## How to Use These Files
1. Read `spec.md` to understand the exact interface contract and what custom loops can access.
2. Implement using `design.md`, but write integration tests first with minimal loop subclasses.
3. Verify that `_call_llm()` works correctly from a custom loop — this is the primary extension point consumers will use.

## Dependencies
- Depends on: Stages 0–7 (execution loop, permissions, and all value objects must exist).
- Feeds into: Stage 9 (final polish includes verifying custom loops work end-to-end).
