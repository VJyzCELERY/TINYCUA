# Stage 5: Streaming — Description

## Purpose
Implement raw SSE passthrough streaming so that `agent.run()` can return either a final string (`stream=False`) or an async iterator of raw OpenAI SSE events (`stream=True`). This stage adds SSE-based streaming to the LLM client and loop, with no mode filtering — every LLM event passes through as-is.

## What You'll Find Here
- **`spec.md`** — Requirements for `stream=False` and `stream=True` modes, event shapes, tool-call behavior during streams, and loop integration. Includes success criteria.
- **`design.md`** — Async generator architecture: `_run_stream()` vs `_run_sync()`, `LLMClient.chat(stream=True)` SSE parsing, raw event passthrough, and cumulative usage.

## What This Stage Does NOT Do
- It does not change non-streaming behavior — `stream=False` is identical to previous stages.
- It does not emit synthetic events (`response.output_item.added`, `response.output_text.done`, etc.) — only raw LLM events and lifecycle bookends.
- It does not implement custom loop streaming support beyond the default.

## How to Use These Files
1. Read `spec.md` to understand the return types and event shapes.
2. Implement using `design.md`.
3. Test tool-call streaming carefully — partial JSON across chunks is the hardest edge case.

## Dependencies
- Depends on: Stages 0–4 (execution loop must exist).
- Feeds into: Stages 6-9.
