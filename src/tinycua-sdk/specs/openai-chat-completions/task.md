# Tasks: OpenAI Chat Completions Provider

Implementation tasks for the OpenAI Chat Completions Provider. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests from `implementation-plan.md` for provider resolution, non-streaming normalization, streaming tool calls, and raw event pass-through <!-- id: 0 -->
  - [ ] Add `tests/integration/test_openai_chat_completions_provider.py`
  - [ ] Mock `AsyncOpenAI.chat.completions.create()` responses and streams
  - [ ] Assert `provider="openai"` returns `OpenAIChatClient` and `provider="openai-responses"` still returns `OpenAIResponsesClient`
- [ ] Run integration tests and confirm RED failures before implementation <!-- id: 1 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/integration/test_openai_chat_completions_provider.py`
- [ ] Write focused unit tests for Chat Completions request/response behavior <!-- id: 2 -->
  - [ ] Add `tests/unit/test_openai_chat_client.py`
  - [ ] Test Chat Completions payload uses `messages`, `tools`, `max_tokens`, and tool-result `role="tool"`
  - [ ] Test non-streaming response normalization with text, usage, finish reason, and tool calls
  - [ ] Test streaming content deltas and terminal completion events
  - [ ] Test streaming tool-call accumulation across partial chunks
  - [ ] Test error translation to `ProviderAuthError` and `ProviderApiError`
  - [ ] Test raw-events one-to-many pairing: one chunk producing multiple canonical events asserts first gets raw chunk, follow-on gets `raw=None`
- [ ] Update provider registry tests for alias removal and default registration behavior, then confirm RED where implementation is missing <!-- id: 3 -->
  - [ ] Update `tests/unit/test_provider_registry.py`
  - [ ] Update `tests/unit/test_provider_switching.py`
  - [ ] Update `tests/integration/test_provider_switching.py`

## Implementation Phase

- [ ] Implement Chat Completions payload translation in `tinycua_sdk/agent/llm_client.py` <!-- id: 4 -->
  - [ ] Add Chat-specific supported field mapping, including `max_tokens` instead of `max_output_tokens`
  - [ ] Map canonical messages to Chat Completions `messages`
  - [ ] Map `ToolResultMessage` to Chat Completions tool messages with `tool_call_id`
  - [ ] Preserve prior assistant `tool_calls` from Chat Completions response and inject a preceding assistant message with `tool_calls=[{id, type: "function", function: {name, arguments}}]` before tool-result messages in follow-up requests
  - [ ] Reuse or adapt tool translation without changing Responses API behavior
- [ ] Implement Chat Completions stream accumulators and normalizer <!-- id: 5 -->
  - [ ] Add `ChoiceAccumulator` and `ToolCallAccumulator`
  - [ ] Add `_normalize_chat_chunk()` and small helper functions for content, usage, lifecycle, and tool-call events
  - [ ] Emit `ContentDoneEvent` only when content exists
  - [ ] Emit `ToolCallArgumentsDoneEvent` and exactly one `ToolCallReadyEvent` per executable tool call
  - [ ] Emit `ResponseUsageEvent` from terminal chunk usage when present
  - [ ] Emit `ResponseCompletedEvent` for terminal `finish_reason`
- [ ] Implement `OpenAIChatClient` in `tinycua_sdk/agent/llm_client.py` <!-- id: 6 -->
  - [ ] Initialize and close `AsyncOpenAI` with API key and normalized base URL
  - [ ] Implement non-streaming `_chat_impl()` path using `client.chat.completions.create(stream=False)`
  - [ ] Implement streaming `_chat_impl()` path using `client.chat.completions.create(stream=True)`
  - [ ] Preserve raw event pairing with `RawSseEvent(provider="openai", raw_event=chunk)`
  - [ ] Translate provider errors consistently with `OpenAIResponsesClient`
- [ ] Register the new provider in `tinycua_sdk/core/providers.py` <!-- id: 7 -->
  - [ ] Remove the `"openai" -> "openai-responses"` alias
  - [ ] Ensure `resolve_provider("openai")` returns `"openai"`
  - [ ] Register `"openai"` with `OpenAIChatClient`
  - [ ] Keep `"openai-responses"` registered with `OpenAIResponsesClient`
- [ ] Update public exports <!-- id: 8 -->
  - [ ] Export `OpenAIChatClient` from `tinycua_sdk/agent/__init__.py`
  - [ ] Add `OpenAIChatClient` to `tinycua_sdk/agent/llm_client.py::__all__`

## Testing Phase

- [ ] Run new Chat Completions integration tests and expect GREEN <!-- id: 9 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/integration/test_openai_chat_completions_provider.py`
- [ ] Run new Chat Completions unit tests and expect GREEN <!-- id: 10 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py`
- [ ] Run provider registry and provider switching tests <!-- id: 11 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_provider_registry.py tests/unit/test_provider_switching.py tests/integration/test_provider_switching.py`
- [ ] Run existing LLM client tests to confirm Responses API behavior did not regress <!-- id: 12 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_llm_client.py`
- [ ] Run full SDK test suite <!-- id: 13 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest`

## Verification Phase

- [ ] Verify `provider="openai"` no longer emits a deprecation warning or resolves to `openai-responses` <!-- id: 14 -->
- [ ] Verify both default providers appear in `ProviderRegistry.list_providers()` <!-- id: 15 -->
- [ ] Verify streaming event order for content-only responses: created, delta, done, usage if present, completed <!-- id: 16 -->
- [ ] Verify streaming event order for tool responses: started, argument delta, arguments done, ready, usage if present, completed <!-- id: 17 -->
- [ ] Verify tool-only non-streaming responses return `content is None` and populated `tool_calls` <!-- id: 18 -->
- [ ] Optionally run a manual real-API smoke test with `OPENAI_API_KEY` and `provider="openai"` <!-- id: 19 -->

## Documentation Phase

- [ ] Update SDK docs or examples that describe supported providers, if present <!-- id: 20 -->
- [ ] Document the Stage 2 provider identifier change: `openai` is Chat Completions, `openai-responses` is Responses API <!-- id: 21 -->
- [ ] Add a changelog or release-note entry if the project maintains one <!-- id: 22 -->

## Review and Merge

- [ ] Review diffs for accidental Responses API behavior changes outside explicit registry alias removal <!-- id: 23 -->
- [ ] Confirm all generated review files, if any, remain untracked under `reviews/` and are not committed <!-- id: 24 -->
- [ ] Create or update the pull request after implementation and tests pass <!-- id: 25 -->
- [ ] Address review feedback and rerun impacted tests <!-- id: 26 -->
- [ ] Merge after approval and successful CI <!-- id: 27 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-19*
