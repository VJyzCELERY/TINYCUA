# Tasks: Stage 8 Custom Loops

Implementation tasks for Stage 8 Custom Loops. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write `tests/integration/goals/test_adv_01_custom_agent_loop.py` covering custom override, `_call_llm()` access, cancellation, `max_iterations`, ReAct-style tool execution, PlanThenExecute two-phase loop with tool execution, and streaming `response.in_progress` lifecycle ordering. <!-- id: 0 -->
- [x] Run the new integration test and confirm RED for any missing Stage 8 behavior: `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_01_custom_agent_loop.py -v`. <!-- id: 1 -->
- [x] Add focused unit tests in `tests/unit/test_loop.py` for `response.in_progress` insertion and non-duplication across SDK-created, provider-created, provider-completed, and provider-failed stream paths. <!-- id: 2 -->
- [x] Update `tests/unit/test_agent_streaming.py` expectations so `Agent.run(stream=True)` requires `response.in_progress`. <!-- id: 3 -->
- [x] Run the affected unit tests and confirm RED where behavior is not yet implemented: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py tests/unit/test_agent_run.py tests/unit/test_agent_streaming.py -v`. <!-- id: 4 -->

## Implementation Phase

- [x] Modify `tinycua_sdk/agent/loop.py` so `BaseLoop._run_stream()` emits `response.in_progress` after `response.created` and before first content/tool event when the provider does not emit it. <!-- id: 5 -->
- [x] Guard against duplicate `response.in_progress` when the provider already emits that event. <!-- id: 6 -->
- [x] Preserve existing terminal behavior: do not synthesize `response.completed` after provider `response.failed`, raw `error`, cancellation, or provider-emitted `response.completed`. <!-- id: 7 -->
- [x] Add `ResponseInProgressEvent` to `tinycua_sdk/agent/events.py` and include it in `__all__`. <!-- id: 8 -->
- [x] Re-export `ResponseInProgressEvent` from `tinycua_sdk/agent/__init__.py` if event exports remain package-level. <!-- id: 9 -->
- [x] Verify `tinycua_sdk/agent/agent.py` still delegates custom loops exactly once per `Agent.run()` call and passes the `stream` argument through. <!-- id: 10 -->
- [x] Modify `tinycua_sdk/agent/executor.py` to extend `_call_llm()` with `llm_model: LanguageModel | None = None` parameter and use `llm_model or self.config.llm_model` when calling `client.chat()`. <!-- id: 11 -->
- [x] Add integration test verifying PlanThenExecute-style loop can pass a copied `LanguageModel` via `llm_model` into `_call_llm()`. <!-- id: 11b -->

## Testing Phase

- [x] Run integration tests and expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_01_custom_agent_loop.py -v`. <!-- id: 12 -->
- [x] Run affected unit tests and expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py tests/unit/test_agent_run.py tests/unit/test_agent_streaming.py -v`. <!-- id: 13 -->
- [x] Run import sanity tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_import_sanity.py -v`. <!-- id: 14 -->
- [x] Run the full SDK suite: `cd src/tinycua-sdk && uv run pytest`. <!-- id: 15 -->
- [x] Run lint if code changes touch public modules: `cd src/tinycua-sdk && uv run ruff check tinycua_sdk tests`. <!-- id: 16 -->

## Verification Phase

- [x] Confirm `from tinycua_sdk import Agent, BaseLoop, LanguageModel, tool` works in tests or import sanity coverage. <!-- id: 17 -->
- [x] Confirm a custom loop returning a string bypasses the default loop and does not call `_call_llm()` unless the custom loop does so. <!-- id: 18 -->
- [x] Confirm a custom loop can call `agent._call_llm(messages, tools, llm_model=copied_model)` and receive the normalized response dict with the overridden model. <!-- id: 19 -->
- [x] Confirm streaming event order is `response.created`, `response.in_progress`, provider deltas, `response.usage`, then `response.completed` for SDK-synthesized streams. <!-- id: 20 -->
- [ ] Optionally run target scripts in `specs/refactor-tinycua-sdk-v2/specs/stage-08-custom-loops/targets/` against a local OpenAI-compatible server if one is available. <!-- id: 21 -->

## Documentation Phase

- [x] Update `src/tinycua-sdk/docs/examples/07_custom_loop.py` to replace `LLMModel` with `LanguageModel`, use the current `BaseLoop.run()` signature, pass `tools` directly to `_call_llm()`, and use `ToolExecutor.execute()` for tool execution. <!-- id: 22 -->
- [ ] Update `src/tinycua-sdk/README.md` only if it documents loop extension points or stream event contracts. <!-- id: 23 -->
- [ ] Update Stage 8 `spec.md` or `targets.md` only if implementation reveals a contradiction between the spec and executable target scenarios. <!-- id: 24 -->

## Review and Merge

- [x] Review the final diff for minimality: tests first, only Stage 8 loop/event/export changes, no hook-system reintroduction. <!-- id: 25 -->
- [x] Ensure no files under `reviews/` or local-only artifacts are staged. <!-- id: 26 -->
- [ ] Create a commit only after explicit user approval. <!-- id: 27 -->
- [ ] Open or update the PR using `.agents/scripts/gh.py` only after explicit user approval. <!-- id: 28 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-16*
