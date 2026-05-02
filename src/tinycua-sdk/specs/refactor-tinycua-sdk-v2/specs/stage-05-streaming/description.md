# Stage 5: Streaming — Description

## Purpose
Implement all four streaming modes (`off`, `token`, `event`, `all`) so that `agent.run()` can return either a final string or an async iterator of events. This stage adds SSE-based token/event streaming to the LLM client and loop, with proper filtering by mode.

## What You'll Find Here
- **`spec.md`** — Requirements for all four modes, event shapes (token deltas and agent events), tool-call behavior during streams, and loop integration. Includes 6 success criteria covering each mode individually, tool call events in streams, and the integration test.
- **`design.md`** — Async generator architecture: `_run_stream()` vs `_run_sync()`, `LLMClient.chat(stream=True)` SSE parsing, event filtering logic, and stream accumulation for partial tool calls.

## What This Stage Does NOT Do
- It does not change non-streaming behavior — `stream="off"` is identical to Stage 3.
- It does not implement custom loop streaming support beyond the default — that's covered by Stage 8's extensibility model.
- It does not add new event types beyond OpenAI Responses API shapes.

## How to Use These Files
1. Read `spec.md` to understand the exact return types and event shapes for each mode.
2. Implement using `design.md`, but write integration tests first with a mock SSE stream.
3. Test tool-call streaming carefully — partial JSON across chunks is the hardest edge case.

## Targets (Test Scenarios)
This stage includes 4 atomic test scenarios in `targets/`:
- **01_stream_off.py** — Verify stream='off' returns a plain string
- **02_stream_token.py** — Verify stream='token' yields token delta events
- **03_stream_event.py** — Verify stream='event' yields agent events without token deltas
- **04_stream_all.py** — Verify stream='all' yields interleaved token deltas and agent events

Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

## Dependencies
- Depends on: Stages 0–4 (execution loop must exist).
- Feeds into: Stage 9 (final polish includes verifying all modes work end-to-end).
