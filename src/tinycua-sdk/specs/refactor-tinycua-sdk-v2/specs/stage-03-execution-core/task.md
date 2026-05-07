# Tasks: Stage 3 — LLM Client & Basic Execution Loop

Implementation tasks for Stage 3. Check off items as completed.

## Implementation Phase

- [x] Create `tinycua_sdk/agent/llm_client.py` with `LLMClient` ABC and `OpenAICompatibleClient` <!-- id: 1 -->
  - [x] ABC with `async def chat()` abstract method
  - [x] `OpenAICompatibleClient` with lazy httpx client
  - [x] Forward model_config fields to request payload
  - [x] Parse and normalize response
- [x] Rewrite `tinycua_sdk/agent/executor.py` with `ToolExecutor` and updated `AgentExecutor` <!-- id: 2 -->
  - [x] `ToolExecutor.execute()` with permission/approval checks
  - [x] `AgentExecutor` with `_cancelled`, `cancel()`, `is_cancelled`, `_get_llm_client()`, `_call_llm()`
  - [x] Remove stub `run()` from AgentExecutor
- [x] Rewrite `tinycua_sdk/agent/loop.py` with full `BaseLoop.run()` implementation <!-- id: 3 -->
  - [x] `_build_system_message()` with instructions + skills
  - [x] Main loop: cancellation check, LLM call, tool call parsing, execution, result appending
  - [x] `override_instructions` parameter
- [x] Rewrite `tinycua_sdk/security/approval.py` with ABC + `DefaultApprovalWorkflow` <!-- id: 4 -->
  - [x] `ApprovalWorkflow(ABC)` with `async def request_approval()`
  - [x] `DefaultApprovalWorkflow` returning `{"approved": True}`
- [x] Add `Agent.run()` method to `tinycua_sdk/agent/agent.py` <!-- id: 5 -->
  - [x] Handle `stream="off"`, raise `NotImplementedError` otherwise
  - [x] Build message list with history and query
  - [x] Delegate to `BaseLoop.run()` with instruction override
- [x] Update exports in `tinycua_sdk/agent/__init__.py` and `tinycua_sdk/security/__init__.py` <!-- id: 6 -->

## Testing Phase

- [x] Write unit tests for `OpenAICompatibleClient.chat()` with mocked httpx <!-- id: 7 -->
- [x] Write unit tests for `ToolExecutor.execute()` (allow/deny/ask paths) <!-- id: 8 -->
- [x] Write unit tests for `BaseLoop.run()` with mocked `_call_llm` <!-- id: 9 -->
- [x] Write unit tests for `Agent.run()`, cancellation <!-- id: 10 -->
- [x] Write unit tests for `DefaultApprovalWorkflow` <!-- id: 11 -->
- [x] Create `tests/integration/goals/test_gs_03_agent_calling.py` with 4 success criteria <!-- id: 12 -->
  - [x] Test: agent.run returns string
  - [x] Test: agent.run with message history
  - [x] Test: agent.run with instruction override
  - [x] Test: cancellation
- [x] Create `tests/integration/goals/test_int_03_agent_with_tools.py` with 2 success criteria <!-- id: 13 -->
  - [x] Test: tool calling loop
  - [x] Test: dynamic add_tools
- [x] Un-skip and update existing loop execution tests in `test_loop_execution.py` <!-- id: 14 -->
- [x] Update `tests/integration/conftest.py` fixtures to patch httpx instead of old LLMClient <!-- id: 15 -->

## Verification Phase

- [x] Run unit tests: `cd src/tinycua-sdk && uv run pytest tests/unit/ -v` <!-- id: 16 -->
- [x] Run all integration tests: `cd src/tinycua-sdk && uv run pytest tests/integration/ -v` <!-- id: 17 -->
- [x] Run lint: `cd src/tinycua-sdk && uv run ruff check tinycua_sdk/ tests/` <!-- id: 18 -->
- [x] Run type check if configured: `cd src/tinycua-sdk && uv run mypy tinycua_sdk/` (if applicable) <!-- id: 19 -->

## Documentation Phase

- [x] Add docstrings to all new public functions/classes <!-- id: 20 -->
- [x] Ensure AGENTS.md references are up to date if needed <!-- id: 21 -->

## Review and Merge

- [ ] Create pull request with summary of Stage 3 changes <!-- id: 22 -->
- [ ] Address review feedback <!-- id: 23 -->
- [ ] Merge to main branch <!-- id: 24 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-05-06*
