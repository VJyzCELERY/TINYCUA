# Stage 3: LLM Client & Basic Execution Loop — Description

## Purpose
Give the agent the ability to actually call an LLM and return a response. This is the most critical stage — it implements the real `LLMClient` (not a stub), the full execution loop in `BaseLoop.run()`, tool execution with permission/approval checks, and cancellation support. Non-streaming only; streaming comes in Stage 5.

## What You'll Find Here
- **`spec.md`** — Requirements for `LLMClient` ABC, `OpenAICompatibleClient`, `BaseLoop.run()` execution flow, `ToolExecutor` with permissions/approvals, `ApprovalWorkflow` redesign, and `Agent.run()`. Includes 7 success criteria covering basic calling, history, instruction override, cancellation, tool calling, dynamic tools, and integration tests.
- **`design.md`** — Full implementations: `OpenAICompatibleClient` using `httpx`, the complete loop algorithm with message building and tool call parsing, `ToolExecutor.execute()` with permission/approval flow, and `ApprovalWorkflow` ABC.

## What This Stage Does NOT Do
- It does not implement streaming — that's Stage 5.
- It does not handle directory loading or file serialization — that's Stage 6.
- It does not support custom loops beyond the default — that's Stage 8.

## How to Use These Files
1. Read `spec.md` to understand the execution flow and all requirements.
2. Implement using `design.md`, but write integration tests first with a mock LLM client.
3. This is the highest-risk stage — verify tool-calling works end-to-end before proceeding.

## Dependencies
- Depends on: Stages 0–2 (cleanup, value objects, agent config).
- Feeds into: Stages 4–9 (all subsequent stages build on a working execution loop).
