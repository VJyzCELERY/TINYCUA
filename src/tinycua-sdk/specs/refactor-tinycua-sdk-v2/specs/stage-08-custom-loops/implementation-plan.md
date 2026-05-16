# Implementation: Stage 8 Custom Loops

Make `BaseLoop` a stable extension point for SDK consumers by validating custom loop subclassing, protected LLM access through `agent._call_llm()`, cancellation/iteration contracts, and complete OpenAI Responses streaming lifecycle events.

## Context

- **Spec Reference**: `spec.md`
- **Design Reference**: `design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

Runtime services are handled differently per test layer:

- **Unit/contract tests** (`tests/unit/test_loop_custom.py`): Use mocked `_call_llm()` for fast deterministic control-flow coverage. No runtime services required.
- **Integration contract tests** (`tests/integration/goals/test_adv_01_custom_agent_loop.py`): Tests that don't call `_call_llm()` (override, cancellation, max_iterations) require no server.
- **Real integration tests** (`tests/integration/goals/test_adv_01_custom_agent_loop.py` with `@pytest.mark.integration`): Require a local OpenAI-compatible server. Automatically skipped when the server is unreachable (handled by `tests/integration/conftest.py`).

### Configuration

- [x] **None** - unit/contract tests use mocked SDK LLM responses; real integration tests use environment configuration.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Local OpenAI-compatible server | No | Optional for manual target scripts only | `curl http://localhost:1234/v1/models` |

### Data / Fixtures

- [x] **None** - tests can define inline fixtures and fake stream generators.

### Access / Permissions

- [x] **None** - no external accounts or secrets are required for automated verification.

### Developer Tooling

- [x] **Runtime**: Python 3.12 via the `tinycua-sdk` project environment.
- [x] **Package manager**: `uv`.
- [x] **Test runner**: `pytest` through `uv run`.

---

## Success Criteria - Integration Tests (TDD First)

Write the integration test first at `tests/integration/goals/test_adv_01_custom_agent_loop.py`. The tests should mock `_call_llm()` where possible so Stage 8 does not require a local model server in CI.

```python
# Test file: tests/integration/goals/test_adv_01_custom_agent_loop.py
"""Integration tests for Stage 8 custom agent loops."""

import asyncio
import json
from collections.abc import AsyncIterator

import pytest

from tinycua_sdk import Agent, BaseLoop, LanguageModel, tool
from tinycua_sdk.agent.executor import ToolExecutor


@pytest.mark.asyncio
async def test_custom_loop_overrides_default_execution():
    """Passing a BaseLoop subclass to Agent uses that loop for run()."""

    class MyLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            return "custom result"

    agent = Agent(llm_model=LanguageModel(), loop=MyLoop())

    assert await agent.run("Hello") == "custom result"


@pytest.mark.asyncio
async def test_custom_loop_can_call_agent_call_llm():
    """Custom loops can reuse the agent LLM transport helper."""

    class LLMLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            response = await agent._call_llm(messages, tools)
            return response.get("content", "")

    agent = Agent(llm_model=LanguageModel(), loop=LLMLoop())

    async def fake_call_llm(messages, tools=None, stream=False):
        assert messages[-1] == {"role": "user", "content": "Say hi."}
        assert tools == []
        return {"content": "hi", "tool_calls": None, "usage": None}

    agent._call_llm = fake_call_llm

    assert await agent.run("Say hi.") == "hi"


@pytest.mark.asyncio
async def test_custom_loop_can_respect_agent_cancellation():
    """A custom loop can observe agent.is_cancelled and exit cooperatively."""

    class SlowLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            for _ in range(100):
                if agent.is_cancelled:
                    return "[cancelled]"
                await asyncio.sleep(0.001)
            return "done"

    agent = Agent(llm_model=LanguageModel(), loop=SlowLoop())
    task = asyncio.create_task(agent.run("Wait"))

    await asyncio.sleep(0.01)
    agent.cancel()

    assert await task == "[cancelled]"


@pytest.mark.asyncio
async def test_custom_loop_can_use_max_iterations():
    """Custom loops inherit and can rely on self.max_iterations."""

    class CountingLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            count = 0
            for _ in range(self.max_iterations):
                count += 1
            return f"ran {count} times"

    agent = Agent(llm_model=LanguageModel(), loop=CountingLoop(max_iterations=3))

    assert await agent.run("Hello") == "ran 3 times"


@pytest.mark.asyncio
async def test_react_style_custom_loop_can_execute_tool_and_continue():
    """A ReAct-style loop can call the LLM, execute a tool, and continue."""

    @tool
    def weather(city: str) -> str:
        """Get weather for a city."""
        return f"Sunny in {city}."

    class ReActLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            response = await agent._call_llm(messages, tools)
            if response.get("tool_calls"):
                tc = response["tool_calls"][0]
                tool_obj = next(t for t in tools if t.name == tc["name"])
                arguments = json.loads(tc["arguments"])
                result = await ToolExecutor.execute(tool_obj, arguments, agent)
                call_id = tc.get("call_id", tc["id"])
                messages.append(
                    {
                        "type": "function_call",
                        "call_id": call_id,
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    }
                )
                messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": str(result),
                    }
                )
                final = await agent._call_llm(messages)
                return final.get("content", "")
            return response.get("content", "")

    agent = Agent(llm_model=LanguageModel(), tools=[weather], loop=ReActLoop())
    calls = []

    async def fake_call_llm(messages, tools=None, stream=False):
        calls.append((messages, tools))
        if len(calls) == 1:
            return {
                "content": "Act: weather",
                "tool_calls": [{"id": "call_1", "name": "weather", "arguments": "{\"city\": \"Tokyo\"}"}],
            }
        return {"content": "It is sunny in Tokyo.", "tool_calls": None}

    agent._call_llm = fake_call_llm

    assert await agent.run("What is the weather in Tokyo?") == "It is sunny in Tokyo."


@pytest.mark.asyncio
async def test_plan_then_execute_loop_works():
    """A PlanThenExecuteLoop can produce a plan and execute steps."""

    @tool
    def search(query: str) -> str:
        """Search for information."""
        return f"Results for {query}."

    class PlanThenExecuteLoop(BaseLoop):
        def __init__(self, max_iterations=5, plan_temperature=0.3):
            super().__init__(max_iterations=max_iterations)
            self.plan_temperature = plan_temperature

        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            # Phase 1: Planning
            plan_messages = messages + [{
                "role": "system",
                "content": "First, outline a step-by-step plan. Do not execute yet.",
            }]
            plan_model = agent.llm_model.model_copy(update={"temperature": self.plan_temperature})
            plan_response = await agent._call_llm(plan_messages, llm_model=plan_model)
            plan = plan_response.get("content", "")

            # Phase 2: Execution
            exec_messages = messages + [
                {"role": "assistant", "content": plan},
                {"role": "system", "content": "Now execute the plan above step by step."},
            ]

            for _ in range(self.max_iterations):
                if agent.is_cancelled:
                    return "[cancelled]"

                response = await agent._call_llm(exec_messages, tools)
                content = response.get("content", "")
                exec_messages.append({"role": "assistant", "content": content})

                if not response.get("tool_calls"):
                    return content

                for tc in response["tool_calls"]:
                    tool_name = tc["name"]
                    arguments = json.loads(tc["arguments"])
                    for t in tools:
                        if t.name == tool_name:
                            result = await ToolExecutor.execute(t, arguments, agent)
                            call_id = tc.get("call_id", tc["id"])
                            exec_messages.append(
                                {
                                    "type": "function_call",
                                    "call_id": call_id,
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                }
                            )
                            exec_messages.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": str(result),
                                }
                            )
                            break

            return "[max iterations reached]"

    agent = Agent(llm_model=LanguageModel(), tools=[search], loop=PlanThenExecuteLoop(max_iterations=3))
    calls = []

    async def fake_call_llm(messages, tools=None, stream=False, llm_model=None):
        calls.append((messages, tools))
        if len(calls) == 1:
            # Phase 1: return a plan with model override assertion
            assert llm_model is not None
            assert llm_model.temperature == 0.3
            return {"content": "Plan: 1. Search for Tokyo weather.", "tool_calls": None}
        if len(calls) == 2:
            # Phase 2: execute tool
            return {
                "content": "",
                "tool_calls": [{"id": "call_1", "name": "search", "arguments": '{"query": "Tokyo weather"}'}],
            }
        # Phase 2 follow-up: final answer
        return {"content": "Tokyo has sunny weather.", "tool_calls": None}

    agent._call_llm = fake_call_llm

    result = await agent.run("What is the weather in Tokyo?")
    assert result == "Tokyo has sunny weather."


@pytest.mark.asyncio
async def test_default_streaming_loop_emits_in_progress_event():
    """BaseLoop stream output includes the deferred response.in_progress event."""

    async def fake_call_llm(messages, tools=None, stream=False):
        assert stream is True

        async def chunks() -> AsyncIterator[dict]:
            yield {"type": "response.output_text.delta", "delta": "Hello", "item_id": "msg_1"}

        return chunks()

    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = fake_call_llm

    stream = await agent.run("Hello", stream=True)
    events = [event async for event in stream]
    event_types = [event["type"] for event in events]

    assert event_types.index("response.created") < event_types.index("response.in_progress")
    assert event_types.index("response.in_progress") < event_types.index("response.output_text.delta")
    assert "response.usage" in event_types
    assert "response.completed" in event_types
```

### Key Test Scenarios

- [ ] **Custom override**: a `BaseLoop` subclass passed to `Agent(loop=...)` controls `Agent.run()` output.
- [ ] **Protected LLM helper**: a custom loop can call inherited `agent._call_llm()` without reimplementing transport.
- [ ] **Cancellation contract**: custom loops can observe `agent.is_cancelled` and return cooperatively.
- [ ] **Iteration contract**: custom loops inherit and can enforce `self.max_iterations`.
- [ ] **ReAct-style loop**: a custom loop can execute a tool through SDK primitives and continue the interaction.
- [ ] **PlanThenExecute-style loop**: a custom loop can implement a two-phase plan-then-execute flow with tool execution.
- [ ] **Streaming event completeness**: the default streaming loop emits `response.created`, `response.in_progress`, deltas, `response.usage`, and `response.completed` in order.

## Verification Plan

### Automated Tests

- [ ] Contract tests (always run): `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_01_custom_agent_loop.py -v -k "not integration"`.
- [ ] Real integration tests (require server): `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_01_custom_agent_loop.py -v -m integration`.
- [ ] Unit loop contract tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop_custom.py tests/unit/test_agent_guardrail_propagation.py -v`.
- [ ] Unit loop tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py tests/unit/test_agent_run.py tests/unit/test_agent_streaming.py -v`.
- [ ] Full SDK suite: `cd src/tinycua-sdk && uv run pytest`.

### Manual Verification

- [ ] Run target scripts under `specs/refactor-tinycua-sdk-v2/specs/stage-08-custom-loops/targets/` only if a local OpenAI-compatible server is available.
- [ ] Confirm public imports still work: `from tinycua_sdk import Agent, BaseLoop, LanguageModel, tool`.

### Performance Considerations

- [ ] Confirm `response.in_progress` insertion is constant-time and does not buffer the full stream.
- [ ] Confirm custom loop dispatch does not add extra LLM calls beyond the subclass implementation.

## Proposed Changes

### Integration Coverage (Split into Unit Contract Tests + Real Integration Tests)

As part of the Stage 8 cleanup (ISSUE-001), fake-LLM integration tests were split into two layers:

**Layer 1: Unit/Contract Tests** (`tests/unit/test_loop_custom.py`)
- **Description**: Deterministic fake-LLM contract tests verifying `_call_llm()` access, ReAct tool execution, PlanThenExecute flow, and streaming lifecycle event completeness using stubs.
- **Rationale**: Fast control-flow coverage without requiring a live LLM server. These are the unit-style tests that validate the BaseLoop subclassing contract.

**Layer 2: Real Integration Tests** (`tests/integration/goals/test_adv_01_custom_agent_loop.py` with `@pytest.mark.integration`)
- **Description**: End-to-end tests using the SDK's actual `LanguageModel` transport without monkeypatching `_call_llm()`. Covers custom loop LLM access, ReAct loops, streaming lifecycle, and PlanThenExecute with model override against a real OpenAI-compatible endpoint.
- **Rationale**: Verifies the transport boundary — message shape, tool-call normalization, streaming lifecycle, and model override path — against a live LLM server. Marked with `@pytest.mark.integration` and skipped when no server is available.

**Layer 3: Integration Contract Tests** (in same file, no marker)
- **Description**: Tests that don't require LLM calls at all (custom loop override, cancellation, max_iterations). Always run as part of the integration test suite.

### Agent Loop Runtime

#### [MODIFY] `tinycua_sdk/agent/loop.py`

- **Description**: Ensure `BaseLoop.run()` remains the single subclass extension point and `BaseLoop._run_stream()` emits `response.in_progress` after `response.created` and before first content/tool/error terminal event when the provider does not already emit it.
- **Rationale**: Custom loops should inherit complete default streaming semantics, and R-8.4 requires `response.in_progress` coverage.

#### [MODIFY] `tinycua_sdk/agent/events.py`

- **Description**: Add `ResponseInProgressEvent` TypedDict and export it if typed event definitions are maintained for stream events.
- **Rationale**: Runtime event coverage and typed event coverage should stay aligned.

#### [MODIFY] `tinycua_sdk/agent/__init__.py`

- **Description**: Re-export `ResponseInProgressEvent` from the agent package if `events.py` adds it.
- **Rationale**: Existing event types are exported from `tinycua_sdk.agent`; the new event should follow that pattern.

### Agent Dispatch Contract

#### [VERIFY] `tinycua_sdk/agent/agent.py`

- **Description**: Verify `Agent.run()` continues to pass `(agent, messages, tools, instructions, stream=stream)` into the configured loop and falls back to `BaseLoop()` when `loop` is unset.
- **Rationale**: This is the core assignment mechanism from R-8.5 and appears already wired.

#### [MODIFY] `tinycua_sdk/agent/executor.py`

- **Description**: Extend `_call_llm()` with `llm_model: LanguageModel | None = None` parameter. When provided, use `llm_model` instead of `self.config.llm_model` when calling `client.chat()`, so custom loops can pass a `model_copy()` override for model overrides without calling the LLM client directly.
- **Rationale**: The protected helper is the supported transport reuse point for advanced custom loops; the `llm_model` parameter ensures custom loops never need to import or call the LLM client directly.

### Unit Coverage

#### [MODIFY] `tests/unit/test_loop.py`

- **Description**: Add focused unit coverage for `response.in_progress` ordering, including provider-created, SDK-created, provider-failed, and provider-completed first-chunk paths.
- **Rationale**: Streaming event insertion has multiple branches and should not produce duplicate or out-of-order lifecycle events.

#### [NEW] `tests/unit/test_loop_custom.py`

- **Description**: Contract tests for BaseLoop subclassing using deterministic fake LLM responses. Covers `_call_llm()` access, ReAct tool execution, PlanThenExecute with model override, and streaming lifecycle events. Moved from `tests/integration/goals/test_adv_01_custom_agent_loop.py` as part of ISSUE-001 cleanup.
- **Rationale**: Fake-LLM scenarios belong in unit tests for fast control-flow coverage; they validate the extension point contract, not live transport integration.

#### [NEW] `tests/unit/test_agent_guardrail_propagation.py`

- **Description**: Tests that denied tool results propagate through `Agent.run()` as denied response messages using fake `_call_llm()` responses. Moved from `tests/integration/goals/test_adv_02_guardrail_system.py` as part of ISSUE-001 cleanup.
- **Rationale**: This test validates control flow against stubs, not integration with a live LLM endpoint.

#### [MODIFY] `tests/unit/test_agent_run.py`

- **Description**: Update streaming lifecycle expectations to include `response.in_progress`.
- **Rationale**: Agent-level tests should enforce the public stream behavior exposed through `Agent.run(stream=True)`.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `BaseLoop` | Modify | Keeps subclass-driven customization and completes default stream lifecycle event emission. |
| `Agent` | Verify | Continues to delegate all execution to configured loop instances. |
| `AgentExecutor` | Modify | Extends `_call_llm()` with `llm_model` parameter for model overrides in custom loops. |
| Event type definitions | Modify | Adds a typed representation for `response.in_progress` if event TypedDicts remain exhaustive. |
| Integration tests | New | Adds deterministic Stage 8 success coverage. |

## Data Model Changes

No persisted data model changes are required.

```python
class ResponseInProgressEvent(TypedDict):
    """Emitted after response.created when streaming is active."""

    type: Literal["response.in_progress"]
```

## API Changes

### New Endpoints

N/A - this SDK stage does not add HTTP endpoints.

### Modified Endpoints

N/A - this SDK stage does not modify HTTP endpoints.

### Python API Surface

| Symbol | Change |
|--------|--------|
| `BaseLoop.run()` | Stable subclass extension point with existing signature. |
| `Agent(loop=...)` | Existing loop injection path validated by integration tests. |
| `agent._call_llm()` | Existing protected helper extended with `llm_model` parameter for model overrides; validated for custom loop use. |
| Stream events | Adds/validates `response.in_progress` in default stream output. |

## Dependencies

### External Dependencies

No new external dependencies are required.

### Internal Dependencies

- [ ] Depends on Stages 0-7: default loop, tool execution, streaming, permissions, and public value objects must already exist.
- [ ] Feeds Stage 9: final public API polish should include custom loop smoke coverage.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `response.in_progress` is emitted twice when providers already emit it | Medium | Track whether the event was seen before injecting the SDK event; add unit tests for provider-emitted event paths. |
| Inserting `response.in_progress` after terminal first chunks changes failure semantics | Medium | Preserve failure/completed behavior and test first chunk `response.failed`, `error`, and `response.completed` branches. |
| Custom loop tests become flaky if they require a local model server | High | Mock `_call_llm()` for automated integration tests; leave target scripts for optional manual verification. |
| ReAct example uses provider-specific tool call shapes | Medium | Normalize integration test fake responses to the SDK's current `BaseLoop` tool call shape (`name`, `arguments`, `id`). |
| Cancellation behavior differs between default loop and custom loops | Low | Keep custom loop cancellation cooperative and document that subclasses check `agent.is_cancelled`. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-16*
