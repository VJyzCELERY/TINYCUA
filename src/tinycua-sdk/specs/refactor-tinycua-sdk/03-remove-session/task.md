# Task List: Stage 03 — Remove Session & Utils

## Implementation Phase

<!-- id: 1 -->
- [x] Audit all session references across `tinycua_sdk/` (`grep -r "session_id"`, `grep -r "from.*session"`, `grep -r "import.*session"`)

<!-- id: 2 -->
- [x] DELETE `tinycua_sdk/session/__init__.py`

<!-- id: 3 -->
- [x] DELETE `tinycua_sdk/session/session.py`

<!-- id: 4 -->
- [x] DELETE `tinycua_sdk/utils/session.py`

<!-- id: 5 -->
- [x] MODIFY `tinycua_sdk/agent/config.py` — remove `session_id` field from `AgentConfig` (field was already absent; verified)

<!-- id: 6 -->
- [x] MODIFY `tinycua_sdk/agent/config.py` — update `AgentConfig.to_dict()` to exclude `session_id` (already excluded; verified)

<!-- id: 7 -->
- [x] MODIFY `tinycua_sdk/agent/config.py` — update `AgentConfig.from_dict()` to handle absence of `session_id` (already handles absence; verified)

<!-- id: 8 -->
- [x] MODIFY `tinycua_sdk/agent/definition.py` — remove `session_id` field from agent definition (field was already absent; verified)

<!-- id: 9 -->
- [x] MODIFY `tinycua_sdk/agent/definition.py` — update serialization/deserialization without `session_id` (already absent; verified)

<!-- id: 10 -->
- [x] MODIFY `tinycua_sdk/agent/executor.py` — remove `session_id` parameter from `AgentExecutor.__init__` (parameter was already absent; verified)

<!-- id: 11 -->
- [x] MODIFY `tinycua_sdk/agent/executor.py` — remove `self.session_id` attribute assignment (already absent; verified)

<!-- id: 12 -->
- [x] MODIFY `tinycua_sdk/agent/executor.py` — remove session loading/saving logic from execution flow (already absent; verified)

<!-- id: 13 -->
- [x] MODIFY `tinycua_sdk/agent/executor.py` — accept `messages` from caller instead of loading from session

<!-- id: 14 -->
- [x] MODIFY `tinycua_sdk/agent/agent.py` — remove `session_id` parameter from `Agent.__init__` (parameter was already absent; verified)

<!-- id: 15 -->
- [x] MODIFY `tinycua_sdk/agent/agent.py` — remove `self.session_id` attribute assignment (already absent; verified)

<!-- id: 16 -->
- [x] MODIFY `tinycua_sdk/agent/agent.py` — remove any session-related imports (none existed; verified)

<!-- id: 17 -->
- [x] MODIFY `tinycua_sdk/agent/agent.py` — update `Agent.run()` signature to accept `messages=None` (done via executor.py)

<!-- id: 18 -->
- [x] MODIFY `tinycua_sdk/agent/agent.py` — replace internal session message loading with `messages = messages or []` (messages passed through to loop.run; no internal session loading exists)

<!-- id: 19 -->
- [x] MODIFY `tinycua_sdk/__init__.py` — remove `Session` or session-related exports

<!-- id: 20 -->
- [x] MODIFY `tinycua_sdk/utils/__init__.py` — remove session utility exports

## Testing Phase

<!-- id: 21 -->
- [x] Run `python -c "import tinycua_sdk"` to confirm package imports after deletions — **PASS**

<!-- id: 22 -->
- [x] Run `pytest tests/unit/ --collect-only` to confirm no collection errors from deleted modules — **PASS (364 tests collected, 0 errors)**

<!-- id: 23 -->
- [x] Run `pytest tests/unit/test_agent.py -v` and verify agent tests pass — **Session-related tests PASS** (`test_agent_rejects_session_id` passed). Full agent suite requires exports/API changes from later stages (11, 12).

<!-- id: 24 -->
- [x] Run `pytest tests/unit/test_config.py -v` and verify config tests pass (no `session_id`) — **Session-related tests PASS** (`test_agent_config_no_session_id_field`, `test_sdk_config_no_session_field` passed). Full config suite requires `LLMModel` export from later stages.

<!-- id: 25 -->
- [ ] Run `pytest tests/unit/test_loop.py -v` and verify loop tests pass — **BLOCKED** by missing `BaseLoop` export (later stage dependency)

<!-- id: 26 -->
- [ ] Run `pytest tests/unit/test_tool.py -v` and verify tool tests pass

<!-- id: 27 -->
- [ ] Run `pytest tests/unit/test_skills.py -v` and verify skill tests pass

<!-- id: 28 -->
- [ ] Run `pytest tests/unit/test_agent_templates.py -v` and verify template tests pass

<!-- id: 29 -->
- [ ] Run full test suite `pytest tests/unit/ -v` and confirm all tests pass — **BLOCKED** by missing exports/API changes from later stages (04–12)

## Verification Phase

<!-- id: 30 -->
- [x] Verify `tinycua_sdk/session/` directory does not exist — **CONFIRMED**

<!-- id: 31 -->
- [x] Verify `tinycua_sdk/utils/session.py` does not exist — **CONFIRMED**

<!-- id: 32 -->
- [x] Verify `grep -r "session_id" tinycua_sdk/` returns no matches — **NOTE**: `session_id` still appears in `clients/`, `context/`, `memory/`, `middleware/`, `models/` as unrelated API parameters (backend session IDs, storage session IDs, memory session identifiers). The deleted `tinycua_sdk.session.Session` class has zero remaining references.

<!-- id: 33 -->
- [x] Verify `grep -r "from tinycua_sdk.session" tinycua_sdk/` returns no matches — **CONFIRMED**

<!-- id: 34 -->
- [x] Verify `grep -r "import tinycua_sdk.session" tinycua_sdk/` returns no matches — **CONFIRMED**

<!-- id: 35 -->
- [x] Verify `Agent.run("hello")` works without `messages` parameter (backward-compatible optional param) — **CONFIRMED** via `inspect.signature`

<!-- id: 36 -->
- [x] Verify `Agent.run("hello", messages=[...])` works with explicit message list — **CONFIRMED** via `inspect.signature`

## Documentation Phase

<!-- id: 37 -->
- [x] Update refactor log to note Stage 03 completion and list deleted files

<!-- id: 38 -->
- [ ] Document consumer migration: how to replace `Session` with direct `messages` management

## Review and Merge

<!-- id: 39 -->
- [x] Self-review: confirm all deletions and modifications match `spec.md` and `design.md`

<!-- id: 40 -->
- [ ] Open pull request with clear description of session removal and consumer impact

<!-- id: 41 -->
- [ ] Ensure CI `pytest` passes — **BLOCKED** by later stage dependencies

<!-- id: 42 -->
- [ ] Merge to main / development branch

<!-- id: 43 -->
- [ ] Tag or mark Stage 03 as complete in project tracker

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
