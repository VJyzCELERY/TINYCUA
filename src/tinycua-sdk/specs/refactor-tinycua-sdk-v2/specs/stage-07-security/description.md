# Stage 7: Security — Guardrails & Permissions — Description

## Purpose
Implement declarative tool execution controls: `tool_permissions` on the agent (`allow`/`deny`/`ask`) and pluggable `ApprovalWorkflow` guardrails. Consumers can define custom guardrails (logging, dangerous-tool blocking, human-in-the-loop) without modifying SDK internals.

## What You'll Find Here
- **`spec.md`** — Requirements for `ApprovalWorkflow` integration in `ToolExecutor`, the `tool_permissions` map with runtime mutation support, and built-in guardrail patterns (`LoggingGuardrail`, `DangerousToolGuardrail`, `SimpleAskGuardrail`). Includes 6 success criteria covering blocking, logging, permission deny/ask, runtime mutation, and integration tests.
- **`design.md`** — Implementation of the enhanced `ToolExecutor.execute()` with permission + approval flow, workflow chaining logic, denial handling in message history, and design decisions on safety defaults.

## What This Stage Does NOT Do
- It does not implement a standalone `PermissionSystem` class — permissions are a plain dict on `Agent`.
- It does not add new guardrail types beyond the ABC — consumers define their own.
- It does not persist permissions or workflows to disk — that's serialization (Stage 6).

## How to Use These Files
1. Read `spec.md` to understand the permission check order and all supported patterns.
2. Implement using `design.md` — this is primarily an enhancement to `ToolExecutor.execute()` from Stage 3.
3. Verify denial flows carefully — ensure denied tools produce clear error messages in the agent's message history.

## Dependencies
- Depends on: Stages 0–6 (execution loop and tool executor must exist).
- Feeds into: Stage 9 (final polish includes verifying all guardrail patterns work end-to-end).
