# Implementation Plan: Stage 02 — New Unit Tests

## Context

| Field | Value |
|-------|-------|
| **Priority** | P0 — Defines the contract for Stages 03–12; must precede all implementation |
| **Effort** | Medium (comprehensive test suite, no implementation logic) |
| **Dependencies** | Stage 01 (legacy tests removed to avoid name collisions and confusion) |
| **Stage** | 02 of 13 |

This stage is the TDD foundation for the entire refactor. We write unit tests that define the target public API of the stateless SDK. These tests will initially fail because the implementation does not yet exist. They serve as the success criteria for Stages 03–12.

---

## Proposed Changes

### Shared Test Infrastructure (NEW / MODIFY)

<!-- id: 1 -->
- [ ] NEW `tests/unit/__init__.py` — Package marker for `tests/unit/`
- [ ] MODIFY `tests/unit/conftest.py` — Add fixtures for stateless API:
  - `default_llm` — `LLMModel` instance
  - `default_backend` — `BackendConfig` instance
  - `default_loop` — `BaseLoop` instance
  - `mock_llm_response` — Mock string response for `Agent.run()`

### Agent Tests (MODIFY)

<!-- id: 2 -->
- [ ] MODIFY `tests/unit/test_agent.py` — Replace with stateless Agent tests:
  - **Construction**: minimal, full, rejects obsolete params (`system_prompt`, `model`, `provider`, `session_id`, `memory`, `planning_prompt`)
  - **Tool/Skill composition**: `add_tools()` (single + list), `add_skills()` (single + list)
  - **Config round-trip**: `to_config()`, `from_config()`
  - **Run behavior**: basic, with `messages`, with `instructions`, `stream=True`, with tools
  - **Statelessness**: no internal message history between runs, no singleton registry

### Tool Tests (MODIFY)

<!-- id: 3 -->
- [ ] MODIFY `tests/unit/test_tool.py` — Replace with stateless Tool tests:
  - **Decorator**: returns `Tool` instance, captures dependencies
  - **Schema generation**: parameters inferred from type hints
  - **Invocation**: with args, with defaults, missing required raises error
  - **Bundle support**: `Tool.bundle()`
  - **Statelessness**: no global singleton registry
  - **Config serialization**: `to_config()` returns dict

### Skill Tests (MODIFY)

<!-- id: 4 -->
- [ ] MODIFY `tests/unit/test_skills.py` — Replace with stateless Skill tests:
  - **Construction**: default and full initialization
  - **Markdown loading**: `Skill.load()` parses frontmatter
  - **Dict serialization**: `to_dict()` round-trip
  - **SkillRegistry**: explicit instance (not singleton), `register()`/`get()`, `list_skills()`, filter by category

### Config Tests (MODIFY)

<!-- id: 5 -->
- [ ] MODIFY `tests/unit/test_config.py` — Replace with stateless Config tests:
  - **LLMModel**: defaults, custom values, `to_dict()`, `from_dict()`, immutability, no I/O methods
  - **AgentConfig**: defaults, `to_dict()`, `from_dict()`, rejects `system_prompt`/`session_id`/`memory` fields
  - **BackendConfig**: defaults, remote configuration, `to_dict()`
  - **SDKConfig**: defaults, rejects `memory`/`session`/`environment` fields, `from_env()`, `from_yaml()`
  - **Round-trip**: `LLMModel` and `AgentConfig` serialize and deserialize correctly

### Loop Tests (MODIFY)

<!-- id: 6 -->
- [ ] MODIFY `tests/unit/test_loop.py` — Replace with stateless BaseLoop tests:
  - **Construction**: default `max_iterations`, custom `max_iterations`
  - **Extensibility**: can be subclassed
  - **resolve_loop**: `None` → `BaseLoop()`, instance passthrough, rejects `"react"` string

### Template Tests (MODIFY)

<!-- id: 7 -->
- [ ] MODIFY `tests/unit/test_agent_templates.py` — Replace with stateless template tests:
  - **Built-in templates**: `coder`, `researcher` load successfully via `Agent.from_config()`
  - **LLM override**: template-loaded agent can have LLM overridden
  - **Invalid template**: unknown template name raises `ValueError`

---

## Architecture Changes

There are **no source code architectural changes** in this stage. However, the tests codify the target architecture for Stages 03–12:

| Principle | How Tests Enforce It |
|-----------|----------------------|
| **Statelessness** | `test_no_internal_message_history`, `test_agent_run_stateless` assert no memory between runs |
| **Explicit Composition** | `add_tools()` and `add_skills()` are instance methods; no global registration |
| **Config as Data** | `to_config()` / `from_config()` round-trips on `Agent`, `LLMModel`, `AgentConfig` |
| **No Singletons** | `test_no_singleton_registry`, `test_skill_registry_not_singleton` assert independent instances |
| **LLM Config Isolation** | `system_prompt` lives on `LLMModel`, not `Agent`; `Agent` rejects obsolete params |
| **No Legacy Concepts** | Tests assert absence of `session_id`, `memory`, `planning_prompt`, `model` string on `Agent` |

---

## Verification Plan

| Step | Command / Action | Expected Result |
|------|------------------|-----------------|
| 1 | `python -c "import tinycua_sdk"` | Package imports successfully |
| 2 | `pytest tests/unit/ --collect-only` | All tests collected without import/syntax errors |
| 3 | `pytest tests/unit/test_agent.py -v` | All tests fail (expected TDD state) |
| 4 | `pytest tests/unit/test_tool.py -v` | All tests fail (expected TDD state) |
| 5 | `pytest tests/unit/test_skills.py -v` | All tests fail (expected TDD state) |
| 6 | `pytest tests/unit/test_config.py -v` | All tests fail (expected TDD state) |
| 7 | `pytest tests/unit/test_loop.py -v` | All tests fail (expected TDD state) |
| 8 | `pytest tests/unit/test_agent_templates.py -v` | All tests fail (expected TDD state) |
| 9 | `pytest tests/unit/ -v` | Test suite runs; majority fail, no import errors |
| 10 | `pytest tests/unit/ --cov=tinycua_sdk --cov-report=term-missing` | Coverage baseline captured (will be low) |

---

## Dependencies

| Dependency | Reason |
|------------|--------|
| **Stage 01** | Legacy tests must be removed first so that old test files do not conflict with new ones, and old imports do not cause collection errors |

**Downstream impact:** Stages 03–12 (implementation) are blocked until this stage completes. The tests created here define the acceptance criteria for all implementation work.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Old test files contain useful tests that are hard to replicate | Medium | Medium | Review old tests before overwriting; extract any unique edge cases into the new suite |
| `conftest.py` fixtures conflict with new stateless API | Medium | Medium | Audit existing fixtures; rename or remove obsolete ones; ensure new fixtures use only new imports |
| Tests accidentally depend on old singletons or global state | Medium | High | Code review: verify no imports from `core/registry`, `memory/`, `session/`, `storage/` |
| Tests are too tightly coupled to implementation details | Medium | Medium | Follow design.md philosophy: test public API contract, not internals; mock only at executor/LLM boundary |
| Name collisions between old and new APIs cause import ambiguity | Low | High | Use explicit imports in tests (`from tinycua_sdk import X`); avoid star imports |
| Partial overlap between old and new test coverage | Medium | Low | Accept some duplication initially; deduplicate during implementation stages |
| pytest collection errors from missing new imports | High | Low | Expected — `pytest --collect-only` should surface these; fix import paths if they reference wrong modules |

---

## Order of Operations

1. **Update `conftest.py`** — Establish shared fixtures first so all test files can use them.
2. **Write config tests** (`test_config.py`) — Config is the foundation; Agent and other classes depend on it.
3. **Write loop tests** (`test_loop.py`) — BaseLoop is a dependency for Agent.run().
4. **Write tool tests** (`test_tool.py`) — Tools are composed into Agent.
5. **Write skill tests** (`test_skills.py`) — Skills are composed into Agent.
6. **Write agent tests** (`test_agent.py`) — Agent depends on all above.
7. **Write template tests** (`test_agent_templates.py`) — Templates depend on Agent and Config.
8. **Run verification** — Execute full verification plan.

---

## Acceptance Criteria

- [ ] All test files exist in `tests/unit/`.
- [ ] `tests/unit/__init__.py` exists.
- [ ] `tests/unit/conftest.py` provides fixtures for `default_llm`, `default_backend`, `default_loop`, `mock_llm_response`.
- [ ] `pytest tests/unit/ --collect-only` completes with no syntax or import errors.
- [ ] Tests initially fail because target code does not exist yet.
- [ ] Each test has a clear, descriptive name explaining the behavior it validates.
- [ ] Tests use only the new stateless API (no singletons, no stores, no session/memory references).
- [ ] Tests mock LLM calls (no external server required).
- [ ] Test suite is organized by component (one test file per module).
