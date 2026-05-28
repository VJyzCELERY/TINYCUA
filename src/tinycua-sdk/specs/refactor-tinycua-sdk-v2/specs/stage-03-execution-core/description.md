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

## Targets (Test Scenarios)
This stage includes 6 atomic test scenarios in `targets/`:
- **01_run_returns_string.py** — Verify agent.run() returns a string when stream=False
- **02_run_with_history.py** — Verify agent.run() respects prior message history
- **03_instruction_override.py** — Verify runtime instruction override works
- **04_cancellation.py** — Verify agent.cancel() stops an in-flight run
- **05_tool_calling_loop.py** — Verify agent with tools correctly invokes them
- **06_dynamic_add_tools.py** — Verify tools added after creation work on next run

Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

> **Important:** These targets are **MUST-HAVE** requirements for this stage. However, you should write additional integration tests during development as needed. The targets represent the minimum coverage; you may add more tests to ensure robustness.

## Dependencies
- Depends on: Stages 0–2.5 (cleanup, value objects, agent config, backward-compat cleanup).
- Feeds into: Stages 4–9 (all subsequent stages build on a working execution loop).
