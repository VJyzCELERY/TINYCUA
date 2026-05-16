# Implementation: Custom Loop Creation API Simplification

Restructure `BaseLoop` so that `_run_sync()` and `_run_stream()` are thin orchestrators (~40-55 lines) that delegate to **public helper methods**. Custom loop authors subclassing `BaseLoop` can call these helpers directly in their own `run()` override without accessing private `_` API.

## Context

- **Spec Reference**: [`./spec.md`](./spec.md)
- **Design Reference**: [`./design.md`](./design.md)
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed for unit tests; integration tests need optional LLM server

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python >=3.12
- [x] **Package manager**: uv
- [x] **Additional CLI tools**: pytest

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_custom_agent_loop.py
"""Integration tests for custom loop public helper API."""


def _build_language_model(
    tool_choice: str | dict | None = None,
) -> LanguageModel:
    """Build a LanguageModel from environment variables, with optional tool_choice.

    Uses TINYCUA_* or LLM_* env vars, falling back to localhost defaults.
    When tool_choice is provided, forces the LLM to call a specific tool,
    enabling deterministic tool-calling tests (Option A from design).
    """
    model = LanguageModel(
        provider=os.environ.get("TINYCUA_PROVIDER", "openai-compatible"),
        base_url=os.environ.get(
            "TINYCUA_BASE_URL",
            os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
        ),
        model_name=os.environ.get(
            "TINYCUA_MODEL",
            os.environ.get("LLM_MODEL", "qwen/qwen3.5-9b"),
        ),
        api_key=os.environ.get("TINYCUA_API_KEY", os.environ.get("LLM_API_KEY", "dummy")),
    )
    if tool_choice is not None:
        model = model.model_copy(update={"tool_choice": tool_choice})
    return model


@pytest.mark.integration
@pytest.mark.asyncio
async def test_custom_loop_uses_public_helpers():
    """Custom loop using public helpers produces correct tool-calling result.

    This test uses the deterministic forcing strategy (Option A from design):
    - tool_choice on the LanguageModel forces the LLM to call the named tool
    - The custom loop overrides run() using self.build_system_message(),
      self.process_tool_calls(), and self.last_assistant_content()
    - Observable flags on the loop class prove each helper was invoked.
    - Asserts at least one function_call_output message was produced.
    """
    @tool
    def get_weather(city: str) -> str:
        """Get weather for a city."""
        return f"Weather in {city}: sunny"

    class CustomToolLoop(BaseLoop):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.called_build_system_message = False
            self.called_process_tool_calls = False
            self.called_last_assistant_content = False
            self.last_working_messages: list[dict] = []

        async def run(self, agent, messages, tools,
                      override_instructions=None, stream=False):
            system_msg = self.build_system_message(agent, override_instructions)
            self.called_build_system_message = True
            working = [system_msg] + list(messages)
            tool_call_count = 0

            for _ in range(self.max_iterations):
                if agent.is_cancelled:
                    raise asyncio.CancelledError()

                response = await agent._call_llm(working, tools)
                content = response.get("content")
                tool_calls = response.get("tool_calls")

                if tool_calls:
                    if content:
                        working.append({"role": "assistant", "content": content or ""})
                    tool_call_count, max_reached = await self.process_tool_calls(
                        agent, tools, tool_calls, working, tool_call_count,
                    )
                    self.called_process_tool_calls = True
                    if max_reached:
                        self.last_working_messages = list(working)
                        self.called_last_assistant_content = True
                        return self.last_assistant_content(working) or "[max tool calls]"
                else:
                    if content:
                        working.append({"role": "assistant", "content": content})
                    self.last_working_messages = list(working)
                    return content or ""

            self.last_working_messages = list(working)
            self.called_last_assistant_content = True
            return self.last_assistant_content(working) or "[max iterations]"

    llm_model = _build_language_model(
        tool_choice={"type": "function", "function": {"name": "get_weather"}},
    )
    loop = CustomToolLoop()
    agent = Agent(
        llm_model=llm_model,
        tools=[get_weather],
        loop=loop,
    )

    result = await agent.run("What is the weather in Tokyo?")
    assert isinstance(result, str)
    assert len(result) > 0

    # Prove the custom loop path was taken (not the default BaseLoop)
    assert loop.called_build_system_message, "build_system_message was not called"
    assert loop.called_process_tool_calls, "process_tool_calls was not called"
    assert loop.called_last_assistant_content, "last_assistant_content was not called"

    # Prove at least one function_call_output message was produced
    helper_call_msgs = [
        m for m in loop.last_working_messages
        if isinstance(m, dict) and m.get("type") == "function_call_output"
    ]
    assert len(helper_call_msgs) > 0, (
        "No function_call_output messages found — helpers did not execute tool calls"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_custom_streaming_loop_uses_public_helpers():
    """Custom streaming loop using public helpers works end-to-end.

    This test provides tools and tool_choice so the streaming loop actually
    exercises process_stream_tool_calls(), not just content streaming.
    """
    @tool
    def get_weather(city: str) -> str:
        """Get weather for a city."""
        return f"Weather in {city}: sunny"

    class CustomStreamingLoop(BaseLoop):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.called_build_system_message = False
            self.called_process_stream_iteration = False
            self.called_process_stream_tool_calls = False
            self.last_working_messages: list[dict] = []

        async def run(self, agent, messages, tools,
                      override_instructions=None, stream=False):
            system_msg = self.build_system_message(agent, override_instructions)
            self.called_build_system_message = True
            working = [system_msg] + list(messages)
            tool_call_count = 0
            cumulative_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            usage_settled_ids = set()
            finish_reason = "completed"
            has_tool_calls = False

            try:
                for _ in range(self.max_iterations):
                    if agent.is_cancelled:
                        yield {"type": "response.cancelled"}
                        break

                    content_parts = []
                    tool_calls_buffer = {}
                    usage_settled_ids.clear()

                    llm_stream = await agent._call_llm(working, tools, stream=True)

                    cancelled = False
                    provider_failed = False
                    async for event in self.process_stream_iteration(
                        llm_stream, agent, content_parts, tool_calls_buffer,
                        cumulative_usage, usage_settled_ids,
                    ):
                        self.called_process_stream_iteration = True
                        if event["type"] == "response.cancelled":
                            cancelled = True
                        elif event["type"] in ("response.failed", "error"):
                            provider_failed = True
                        yield event

                    if cancelled or provider_failed:
                        break

                    combined = "".join(content_parts)
                    tool_calls_list = list(tool_calls_buffer.values())

                    if tool_calls_list:
                        has_tool_calls = True
                        tool_call_count, max_reached = await self.process_stream_tool_calls(
                            agent, tools, tool_calls_list, working, tool_call_count,
                            combined_content=combined,
                        )
                        self.called_process_stream_tool_calls = True
                        if max_reached:
                            finish_reason = "max_tool_calls"
                            break
                    else:
                        working.append({"role": "assistant", "content": combined})
                        break
                else:
                    finish_reason = "max_iterations"
            except Exception as e:
                self.last_working_messages = list(working)
                yield {"type": "response.failed", "error": {"message": str(e)}}
                return

            self.last_working_messages = list(working)
            yield {"type": "response.usage", "usage": dict(cumulative_usage)}
            yield {"type": "response.completed", "finish_reason": finish_reason}

    llm_model = _build_language_model(
        tool_choice={"type": "function", "function": {"name": "get_weather"}},
    )
    loop = CustomStreamingLoop()
    agent = Agent(llm_model=llm_model, tools=[get_weather], loop=loop)

    stream = await agent.run("What is the weather in Tokyo?", stream=True)
    events = [e async for e in stream]
    event_types = [e["type"] for e in events]

    assert "response.created" in event_types
    assert "response.completed" in event_types

    # Prove the streaming helper path was taken
    assert loop.called_build_system_message, "build_system_message was not called"
    assert loop.called_process_stream_iteration, (
        "process_stream_iteration was not called"
    )
    assert loop.called_process_stream_tool_calls, (
        "process_stream_tool_calls was not called"
    )

    # Prove at least one function_call_output message was produced
    helper_call_msgs = [
        m for m in loop.last_working_messages
        if isinstance(m, dict) and m.get("role") == "function_call_output"
    ]
    assert len(helper_call_msgs) > 0, (
        "No function_call_output messages found — streaming helpers did not execute tool calls"
    )
```

### Key Test Scenarios

- [x] **Scenario 1**: Custom sync loop using `build_system_message()`, `process_tool_calls()`, and `last_assistant_content()` — verifies tool execution with a real LLM call
- [x] **Scenario 2**: Custom streaming loop using `process_stream_iteration()` and `process_stream_tool_calls()` — verifies streaming lifecycle events from a subclass
- [x] **Edge case**: All existing unit/contract tests pass after private method renames

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for new public helpers (in `tests/unit/test_loop_custom.py`)
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest`

### Manual Verification

- [ ] Review `_run_sync()` body is ≤45 lines after refactoring
- [ ] Review `_run_stream()` body is ≤60 lines after refactoring
- [ ] Confirm no `_`-prefixed helpers are called from outside `BaseLoop`

### Performance Considerations

- [ ] No significant performance impact — refactoring is reorganizational with same logical operations

## Proposed Changes

### `tinycua_sdk/agent/loop.py`

#### [MODIFY] `tinycua_sdk/agent/loop.py`

- **[Rename to public]**: `_build_system_message` → `build_system_message` — no signature change, all internal references updated
- **[Rename to public]**: `_last_assistant_content` → `last_assistant_content` — static method, pure function
- **[NEW]**: `async process_tool_calls()` — extracted from inline loop in `_run_sync()`, handles tool call iteration, JSON parsing, tool lookup, `ToolExecutor.execute()`, cancellation checks, and message appending. Returns `(updated_tool_call_count, max_tool_calls_reached)`
- **[NEW]**: `process_stream_iteration()` — async generator combining `_yield_first_chunk_events` + `_yield_stream_body_events` into a single public method. Yields raw SSE events plus synthetic lifecycle events. Returns cancellation/provider status via yielded events
- **[NEW]**: `async process_stream_tool_calls()` — cleaned-up version of `_execute_tools_stream()`, returns `(tool_call_count, max_tool_calls_reached)` instead of tuple with internal state
- **[DELETE]**: `_IterStreamState` dataclass — no longer needed
- **[DELETE]**: `_yield_first_chunk_events()` — replaced by `process_stream_iteration()`
- **[DELETE]**: `_yield_stream_body_events()` — replaced by `process_stream_iteration()`
- **[DELETE]**: `_execute_tools_stream()` — replaced by `process_stream_tool_calls()`
- **[KEEP private]**: `_accumulate_chunk()` — internal only
- **[KEEP private]**: `_read_stream_chunk()` — internal only
- **[KEEP private]**: `_iter_llm_events()` — internal only
- **[RESTRUCTURE]**: `_run_sync()` — ~40 lines, delegates to `build_system_message()` and `process_tool_calls()`
- **[RESTRUCTURE]**: `_run_stream()` — ~55 lines, delegates to `build_system_message()`, `process_stream_iteration()`, and `process_stream_tool_calls()`. Tracks `cancelled`, `provider_failed`, `completed_by_provider` as local variables instead of `_IterStreamState`

### Test Files

#### [MODIFY] `tests/unit/test_loop.py`

- **Update references**: Change `loop._build_system_message(...)` to `loop.build_system_message(...)` in `TestBaseLoopBuildSystemMessage` tests
- **Rename test class**: `TestBaseLoopBuildSystemMessage` → `TestBaseLoopBuildSystemMessage` (or keep as-is since build_system_message is the new name)

#### [MODIFY] `tests/unit/test_loop_custom.py`

- **Add new tests**: Unit tests for each new public helper called from a custom subclass:
  - `test_custom_loop_calls_build_system_message`
  - `test_custom_loop_calls_process_tool_calls`
  - `test_custom_loop_calls_process_stream_iteration` — uses a fake async LLM stream to cover lifecycle event ordering, content accumulation, tool-call buffering, cancellation, provider failure, and usage settlement behavior
  - `test_custom_loop_calls_process_stream_tool_calls`
  - `test_custom_loop_calls_last_assistant_content`

#### [MODIFY] `tests/integration/test_custom_agent_loop.py`

- **Add integration tests**: Custom loop using public helpers with real LLM (as defined in Success Criteria above)
- **Existing contract tests**: Should pass without modification since `Agent.run()` dispatch is unchanged

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `BaseLoop.build_system_message()` | Rename | `_build_system_message` → `build_system_message` |
| `BaseLoop.last_assistant_content()` | Rename | `_last_assistant_content` → `last_assistant_content` |
| `BaseLoop.process_tool_calls()` | New | Extracted from `_run_sync()` inline loop |
| `BaseLoop.process_stream_iteration()` | New | Combines `_yield_first_chunk_events` + `_yield_stream_body_events` |
| `BaseLoop.process_stream_tool_calls()` | New | Cleaned up from `_execute_tools_stream()` |
| `_IterStreamState` | Remove | Replaced by local boolean tracking |
| `_yield_first_chunk_events()` | Remove | Replaced by `process_stream_iteration()` |
| `_yield_stream_body_events()` | Remove | Replaced by `process_stream_iteration()` |
| `_execute_tools_stream()` | Remove | Replaced by `process_stream_tool_calls()` |
| `_run_sync()` | Restructure | ~40 lines, thin orchestrator |
| `_run_stream()` | Restructure | ~55 lines, thin orchestrator |

## Data Model Changes

```python
# New interfaces on BaseLoop:
class BaseLoop:
    def build_system_message(self, agent, override_instructions=None) -> dict: ...
    
    async def process_tool_calls(self, agent, tools, tool_calls,
                                  working_messages, tool_call_count) -> tuple[int, bool]: ...
    
    async def process_stream_iteration(self, llm_stream, agent,
                                        content_parts, tool_calls_buffer,
                                        cumulative_usage,
                                        usage_settled_ids) -> AsyncIterator[dict]: ...
    
    async def process_stream_tool_calls(self, agent, tools,
                                         tool_calls_list, working_messages,
                                         tool_call_count,
                                         combined_content="") -> tuple[int, bool]: ...
    
    @staticmethod
    def last_assistant_content(messages) -> str: ...
```

## API Changes

No new endpoints. The `Agent` public API (`agent.run()`, `agent.tool_permissions`, `agent.tools`, `agent.skills`) stays unchanged.

### Modified Methods on `BaseLoop`

| Method | Change |
|--------|--------|
| `_build_system_message()` | Renamed to `build_system_message()` (public) |
| `_last_assistant_content()` | Renamed to `last_assistant_content()` (public) |
| `_execute_tools_stream()` | Superseded by `process_stream_tool_calls()` (public, different return type) |

### New Methods on `BaseLoop`

| Method | Description |
|--------|-------------|
| `process_tool_calls()` | Process LLM tool calls: parse args, execute tools, append messages |
| `process_stream_iteration()` | Process one LLM stream iteration, yield events |
| `process_stream_tool_calls()` | Process accumulated stream tool calls, append messages |

## Dependencies

### External Dependencies

None new.

### Internal Dependencies

- [ ] Depends on: `tinycua_sdk/agent/executor.py` (ToolExecutor — already imported)
- [ ] Depends on: `tinycua_sdk/tools/decorators.py` (Tool type — already imported)
- [ ] Blocks: Custom loop author experience improvement

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Renaming `_build_system_message` breaks external code that calls private method | Low | Intentional pre-release breaking change — SDK has not been publicly released |
| `process_stream_iteration()` changes event ordering vs current two-phase approach | High | Existing stream tests validate exact ordering; they must pass without modification |
| Integration test requires a real LLM key | Low | Use same mock/skip infrastructure as existing integration tests; Option C (split strategy) as fallback |
| Line count targets for `_run_sync()`/`_run_stream()` are aspirational | Medium | Count lines after refactoring; if slightly over, document trade-off. But current design gives exact counts |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-17*
