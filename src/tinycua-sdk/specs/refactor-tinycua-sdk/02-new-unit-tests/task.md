# Task List: Stage 02 — New Unit Tests

## Implementation Phase

<!-- id: 1 -->
- [x] Audit existing `tests/unit/` files (`test_agent.py`, `test_tool.py`, `test_skills.py`, `test_config.py`, `test_loop.py`, `test_agent_templates.py`, `conftest.py`) to identify reusable vs. obsolete content

<!-- id: 2 -->
- [x] NEW `tests/unit/__init__.py`

<!-- id: 3 -->
- [x] MODIFY `tests/unit/conftest.py` — add `default_llm` fixture (`LLMModel`)

<!-- id: 4 -->
- [x] MODIFY `tests/unit/conftest.py` — add `default_backend` fixture (`BackendConfig`)

<!-- id: 5 -->
- [x] MODIFY `tests/unit/conftest.py` — add `default_loop` fixture (`BaseLoop`)

<!-- id: 6 -->
- [x] MODIFY `tests/unit/conftest.py` — add `mock_llm_response` fixture (mocked LLM response string)

<!-- id: 7 -->
- [x] MODIFY `tests/unit/conftest.py` — remove or rename obsolete fixtures referencing deleted modules

<!-- id: 8 -->
- [x] MODIFY `tests/unit/test_config.py` — write LLMModel tests (defaults, custom values, `to_dict`, `from_dict`, immutable, no I/O methods)

<!-- id: 9 -->
- [x] MODIFY `tests/unit/test_config.py` — write AgentConfig tests (defaults, `to_dict`, `from_dict`, rejects obsolete fields)

<!-- id: 10 -->
- [x] MODIFY `tests/unit/test_config.py` — write BackendConfig tests (defaults, remote, `to_dict`)

<!-- id: 11 -->
- [x] MODIFY `tests/unit/test_config.py` — write SDKConfig tests (defaults, rejects obsolete fields, `from_env`, `from_yaml`)

<!-- id: 12 -->
- [x] MODIFY `tests/unit/test_config.py` — write round-trip tests (`LLMModel`, `AgentConfig`)

<!-- id: 13 -->
- [x] MODIFY `tests/unit/test_loop.py` — write BaseLoop construction tests (default and custom `max_iterations`)

<!-- id: 14 -->
- [x] MODIFY `tests/unit/test_loop.py` — write BaseLoop extensibility test (subclassing)

<!-- id: 15 -->
- [x] MODIFY `tests/unit/test_loop.py` — write `resolve_loop` tests (`None`, instance passthrough, rejects `"react"`)

<!-- id: 16 -->
- [x] MODIFY `tests/unit/test_tool.py` — write `@tool` decorator tests (returns `Tool`, captures dependencies)

<!-- id: 17 -->
- [x] MODIFY `tests/unit/test_tool.py` — write `Tool.invoke()` tests (with args, with defaults, missing required)

<!-- id: 18 -->
- [x] MODIFY `tests/unit/test_tool.py` — write Tool schema generation tests

<!-- id: 19 -->
- [x] MODIFY `tests/unit/test_tool.py` — write Tool config serialization tests (`to_config`)

<!-- id: 20 -->
- [x] MODIFY `tests/unit/test_tool.py` — write Tool statelessness tests (no global singleton registry)

<!-- id: 21 -->
- [x] MODIFY `tests/unit/test_skills.py` — write Skill construction tests (default and full)

<!-- id: 22 -->
- [x] MODIFY `tests/unit/test_skills.py` — write `Skill.load()` markdown parsing tests

<!-- id: 23 -->
- [x] MODIFY `tests/unit/test_skills.py` — write SkillRegistry tests (explicit instance, not singleton, register/get, list, filter)

<!-- id: 24 -->
- [x] MODIFY `tests/unit/test_agent.py` — write Agent construction tests (minimal, full, rejects obsolete params)

<!-- id: 25 -->
- [x] MODIFY `tests/unit/test_agent.py` — write Agent tool/skill composition tests (`add_tools`, `add_skills`)

<!-- id: 26 -->
- [x] MODIFY `tests/unit/test_agent.py` — write Agent config serialization tests (`to_config`, `from_config`, round-trip)

<!-- id: 27 -->
- [x] MODIFY `tests/unit/test_agent.py` — write `Agent.run()` mocked tests (basic, with messages, with instructions, stream, with tools)

<!-- id: 28 -->
- [x] MODIFY `tests/unit/test_agent.py` — write Agent statelessness tests (no internal history, no singleton)

<!-- id: 29 -->
- [x] MODIFY `tests/unit/test_agent_templates.py` — write template loading tests (coder, researcher, LLM override, invalid template)

## Testing Phase

<!-- id: 30 -->
- [x] Run `python -c "import tinycua_sdk"` to confirm package imports

<!-- id: 31 -->
- [x] Run `pytest tests/unit/ --collect-only` to confirm no collection errors

<!-- id: 32 -->
- [x] Run `pytest tests/unit/test_config.py -v` and verify all tests fail as expected

<!-- id: 33 -->
- [x] Run `pytest tests/unit/test_loop.py -v` and verify all tests fail as expected

<!-- id: 34 -->
- [x] Run `pytest tests/unit/test_tool.py -v` and verify all tests fail as expected

<!-- id: 35 -->
- [x] Run `pytest tests/unit/test_skills.py -v` and verify all tests fail as expected

<!-- id: 36 -->
- [x] Run `pytest tests/unit/test_agent.py -v` and verify all tests fail as expected

<!-- id: 37 -->
- [x] Run `pytest tests/unit/test_agent_templates.py -v` and verify all tests fail as expected

## Verification Phase

<!-- id: 38 -->
- [x] Verify no test imports `memory`, `session`, `storage`, `cli`, `clients`, or `core/registry` modules

<!-- id: 39 -->
- [x] Verify no test uses global singletons (e.g., `ToolRegistry`, implicit registries)

<!-- id: 40 -->
- [x] Verify all `Agent.run()` tests mock the LLM call (no external server dependency)

<!-- id: 41 -->
- [x] Verify each test has a descriptive docstring or comment explaining the behavior under test

<!-- id: 42 -->
- [x] Run `pytest tests/unit/ --cov=tinycua_sdk --cov-report=term-missing` and capture baseline coverage

<!-- id: 43 -->
- [x] Confirm tests align with `spec.md` requirements list (cross-reference checklist)

## Documentation Phase

<!-- id: 44 -->
- [ ] Update refactor log to note Stage 02 completion and list new test files

<!-- id: 45 -->
- [ ] Document TDD baseline: note that tests are expected to fail until Stages 03–12

## Review and Merge

<!-- id: 46 -->
- [ ] Self-review: confirm all tests match `spec.md` and `design.md` requirements

<!-- id: 47 -->
- [ ] Open pull request with clear description of TDD approach and expected test failures

<!-- id: 48 -->
- [ ] Ensure CI `pytest --collect-only` passes (collection, not execution)

<!-- id: 49 -->
- [ ] Merge to main / development branch

<!-- id: 50 -->
- [ ] Tag or mark Stage 02 as complete in project tracker
