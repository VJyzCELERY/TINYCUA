# Tasks: OpenAI Chat Completions Provider

Implementation tasks for the OpenAI Chat Completions Provider. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests from `implementation-plan.md` for provider resolution, non-streaming normalization, streaming tool calls, and raw event pass-through <!-- id: 0 -->
  - [x] Add `tests/integration/test_openai_chat_completions_provider.py`
  - [x] Mock `AsyncOpenAI.chat.completions.create()` responses and streams
  - [x] Assert `provider="openai-chat-completions"` returns `OpenAIChatCompletionsClient`, `provider="openai"` returns `OpenAIResponsesClient` (via alias), and `provider="openai-responses"` returns `OpenAIResponsesClient`
- [x] Run integration tests and confirm RED failures before implementation <!-- id: 1 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/integration/test_openai_chat_completions_provider.py`
- [x] Write focused unit tests for Chat Completions request/response behavior <!-- id: 2 -->
  - [x] Add `tests/unit/test_openai_chat_client.py`
  - [x] Test Chat Completions payload uses `messages`, `tools`, `max_tokens`, `response_format`, and tool-result `role="tool"`
  - [x] Test non-streaming response normalization with text, usage, finish reason, and tool calls
  - [x] Test streaming content deltas and terminal completion events
  - [x] Test streaming tool-call accumulation across partial chunks
  - [x] Test error translation to `ProviderAuthError` and `ProviderApiError`
  - [x] Test raw-events one-to-many pairing: one chunk producing multiple canonical events asserts first gets raw chunk, follow-on gets `raw=None`
  - [x] Test that `LanguageModel(response_format=...)` produces a Chat Completions request with `response_format` and does not emit the Responses-only `text` field
- [x] Update provider registry tests for new `"openai-chat-completions"` registration and alias preservation, then confirm RED where implementation is missing <!-- id: 3 -->
  - [x] Update `tests/unit/test_provider_registry.py`
  - [x] Update `tests/unit/test_provider_switching.py`
  - [x] Update `tests/integration/test_provider_switching.py`

## Implementation Phase

- [x] Implement Chat Completions payload translation in `tinycua_sdk/agent/llm_client.py` <!-- id: 4 -->
  - [x] Add Chat-specific supported field mapping, including `max_tokens` instead of `max_output_tokens`
  - [x] Map canonical messages to Chat Completions `messages`
  - [x] Map `ToolResultMessage` to Chat Completions tool messages with `tool_call_id`
  - [x] Preserve prior assistant `tool_calls` from Chat Completions response and inject a preceding assistant message with `tool_calls=[{id, type: "function", function: {name, arguments}}]` before tool-result messages in follow-up requests
  - [x] Reuse or adapt tool translation without changing Responses API behavior
- [x] Implement Chat Completions stream accumulators and normalizer <!-- id: 5 -->
  - [x] Add `ChoiceAccumulator` and `ToolCallAccumulator`
  - [x] Add `_normalize_chat_chunk()` and small helper functions for content, usage, lifecycle, and tool-call events
  - [x] Emit `ContentDoneEvent` only when content exists
  - [x] Emit `ToolCallArgumentsDoneEvent` and exactly one `ToolCallReadyEvent` per executable tool call
  - [x] Emit `ResponseUsageEvent` from terminal chunk usage when present
  - [x] Emit `ResponseCompletedEvent` for terminal `finish_reason`
- [x] Implement `OpenAIChatCompletionsClient` in `tinycua_sdk/agent/llm_client.py` <!-- id: 6 -->
  - [x] Initialize and close `AsyncOpenAI` with API key and normalized base URL
  - [x] Implement non-streaming `_chat_impl()` path using `client.chat.completions.create(stream=False)`
  - [x] Implement streaming `_chat_impl()` path using `client.chat.completions.create(stream=True)`
  - [x] Preserve raw event pairing with `RawSseEvent(provider="openai-chat-completions", raw_event=chunk)`
  - [x] Translate provider errors consistently with `OpenAIResponsesClient`
- [x] Register the new provider in `tinycua_sdk/core/providers.py` <!-- id: 7 -->
  - [x] Keep the `"openai" -> "openai-responses"` alias in place
  - [x] Register `"openai-chat-completions"` with `OpenAIChatCompletionsClient`
  - [x] Keep `"openai-responses"` registered with `OpenAIResponsesClient`
- [x] Update public exports <!-- id: 8 -->
  - [x] Export `OpenAIChatCompletionsClient` from `tinycua_sdk/agent/__init__.py`
  - [x] Add `OpenAIChatCompletionsClient` to `tinycua_sdk/agent/llm_client.py::__all__`

## Testing Phase

- [x] Run new Chat Completions integration tests and expect GREEN <!-- id: 9 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/integration/test_openai_chat_completions_provider.py`
- [x] Run new Chat Completions unit tests and expect GREEN <!-- id: 10 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py`
- [x] Run provider registry and provider switching tests <!-- id: 11 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_provider_registry.py tests/unit/test_provider_switching.py tests/integration/test_provider_switching.py`
- [x] Run existing LLM client tests to confirm Responses API behavior did not regress <!-- id: 12 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_llm_client.py`
- [x] Run full SDK test suite <!-- id: 13 -->
  - [x] `cd src/tinycua-sdk && uv run pytest`

## Setup Phase

- [ ] Set up local environment by copying `.env.example` to `.env` <!-- id: 13 -->
  - [ ] Ensure `TINYCUA_BASE_URL=http://localhost:1234/v1` is configured
  - [ ] Ensure `LLM_BASE_URL=http://localhost:1234/v1` is configured (if not already set in `.env`)
- [ ] Start the local LLM Server on `localhost:1234/v1` (LM Studio, llama.cpp, vLLM, etc.) <!-- id: 13b -->
  - [ ] Verify: `curl http://localhost:1234/v1/models` returns 200

## Verification Phase

- [ ] Verify `provider="openai-chat-completions"` resolves to Chat Completions client <!-- id: 14 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_provider_registry.py -k "test_openai_chat_completions_resolves"`
- [ ] Verify all three providers appear in `ProviderRegistry.list_providers()` <!-- id: 15 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_provider_registry.py -k "test_list_providers_includes_all"`
- [ ] Verify streaming event order for content-only responses: created, delta, done, usage if present, completed <!-- id: 16 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -k "test_streaming_content_events_order"`
- [ ] Verify streaming event order for tool responses: created, started, argument delta, arguments done, ready, usage if present, completed <!-- id: 17 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -k "test_streaming_tool_events_order"`
- [ ] Verify tool-only non-streaming responses return `content is None` and populated `tool_calls` <!-- id: 18 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -k "test_tool_only_response_content_none"`
- [ ] Run a manual local LLM server smoke test with the local server at `http://localhost:1234/v1` and `provider="openai-chat-completions"` <!-- id: 19 -->
  - [ ] `cd src/tinycua-sdk && uv run python -c "from tinycua_sdk.agent.llm_model import LanguageModel; from tinycua_sdk.core.providers import get_provider_registry; r = get_provider_registry(); c = r.create_client(LanguageModel(provider='openai-chat-completions', model_name='<your-model>')); import asyncio; print(asyncio.run(c.chat([{'role': 'user', 'content': 'Hello'}])))"`
- [ ] Optionally run a real-API smoke test with `OPENAI_API_KEY` and `provider="openai-chat-completions"` <!-- id: 19b -->

## Documentation Phase

- [ ] Update `.env.example` if any new env vars are introduced (e.g., new provider-specific base URLs) <!-- id: 20 -->
- [ ] Update SDK docs or examples that describe supported providers, if present <!-- id: 20b -->
- [ ] Document the Stage 2 provider identifier: `openai-chat-completions` is Chat Completions, `openai` (alias) and `openai-responses` are Responses API <!-- id: 21 -->
- [ ] Add a changelog or release-note entry if the project maintains one <!-- id: 22 -->

## Review and Merge

- [ ] Review diffs for accidental Responses API behavior changes (the alias should remain intact) <!-- id: 23 -->
- [ ] Confirm all generated review files, if any, remain untracked under `reviews/` and are not committed <!-- id: 24 -->
- [ ] Create or update the pull request after implementation and tests pass <!-- id: 25 -->
- [ ] Address review feedback and rerun impacted tests <!-- id: 26 -->
- [ ] Merge after approval and successful CI <!-- id: 27 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-19*
