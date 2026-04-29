# Implementation Plan: Stage 03 — Remove Session & Utils

## Context

| Field | Value |
|-------|-------|
| **Priority** | P0 — Core stateless refactor; removes all session state from the SDK |
| **Effort** | Small (deletion and parameter removal, no new logic) |
| **Dependencies** | Stage 01 (legacy tests removed), Stage 02 (unit tests define stateless contract) |
| **Stage** | 03 of 13 |

This stage removes all session management concerns from the SDK. Session state (conversation history, turn tracking, file-based persistence) is a consumer responsibility. The SDK becomes fully stateless: consumers pass `messages` directly to `Agent.run()`.

---

## Proposed Changes

### Session Package Deletion (DELETE)

<!-- id: 1 -->
- [ ] DELETE `tinycua_sdk/session/__init__.py` — Package init for deleted module
- [ ] DELETE `tinycua_sdk/session/session.py` — File-based session manager (stateful)

**Rationale**: Session management is consumer-level state. The SDK must not hold runtime conversation state or perform file I/O.

### Session Utilities Deletion (DELETE)

<!-- id: 2 -->
- [ ] DELETE `tinycua_sdk/utils/session.py` — Session utility wrappers (stateful)

**Rationale**: Utility wrappers that depend on session state are obsolete once the session package is removed.

### Agent Module — Remove Session References (MODIFY)

<!-- id: 3 -->
- [ ] MODIFY `tinycua_sdk/agent/agent.py`:
  - Remove `session_id` parameter from `Agent.__init__`
  - Remove `self.session_id` attribute assignment
  - Remove any session imports (`from tinycua_sdk.session import ...` or `from ..session import ...`)
  - Update `Agent.run()` signature to accept `messages=None` as optional parameter
  - Replace internal message loading from session state with `messages = messages or []`

<!-- id: 4 -->
- [ ] MODIFY `tinycua_sdk/agent/executor.py`:
  - Remove `session_id` parameter from `AgentExecutor.__init__`
  - Remove `self.session_id` attribute
  - Remove session loading/saving logic from execution flow
  - Ensure `AgentExecutor` accepts `messages` from caller instead of loading from session

<!-- id: 5 -->
- [ ] MODIFY `tinycua_sdk/agent/definition.py`:
  - Remove `session_id` field from agent definition dataclass/model
  - Update any serialization/deserialization that references `session_id`

### Config Module — Remove Session References (MODIFY)

<!-- id: 6 -->
- [ ] MODIFY `tinycua_sdk/agent/config.py`:
  - Remove `session_id` field from `AgentConfig`
  - Update `AgentConfig.to_dict()` to exclude `session_id`
  - Update `AgentConfig.from_dict()` to reject `session_id` if passed (or ignore it)

**Rationale**: Config objects must be pure data. `session_id` is runtime state, not configuration.

### Package Exports Cleanup (MODIFY)

<!-- id: 7 -->
- [ ] MODIFY `tinycua_sdk/__init__.py` (if applicable):
  - Remove any `Session` or session-related exports from top-level package imports

<!-- id: 8 -->
- [ ] MODIFY `tinycua_sdk/utils/__init__.py` (if applicable):
  - Remove any session utility exports

---

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `session/` package | Remove | Entire package deleted; no session management in SDK |
| `utils/session.py` | Remove | Session utility wrappers deleted |
| `Agent` | Modify | `session_id` parameter removed; `run()` accepts `messages` |
| `AgentExecutor` | Modify | `session_id` parameter removed; accepts `messages` from caller |
| `AgentDefinition` | Modify | `session_id` field removed |
| `AgentConfig` | Modify | `session_id` field removed |

---

## Data Model Changes

### `AgentConfig` (Modified)

```python
# BEFORE
class AgentConfig:
    session_id: Optional[str] = None
    # ... other fields

# AFTER
class AgentConfig:
    # session_id removed
    # ... other fields remain
```

### `Agent.run()` Signature (Modified)

```python
# BEFORE
async def run(self, query: str) -> str:
    messages = self._load_session_messages()
    # ...

# AFTER
async def run(self, query: str, messages: Optional[List[dict]] = None) -> str:
    messages = messages or []
    # ...
```

---

## API Changes

### Removed Concepts

| Concept | Replacement |
|---------|-------------|
| `Session` class | Consumer-managed message lists |
| `session_id` parameter on `Agent` | Direct `messages` parameter on `Agent.run()` |
| File-based session persistence | Consumer's own storage (DB, cache, etc.) |

### Consumer Migration

**Before (SDK manages session):**
```python
from tinycua_sdk import Agent, Session

session = Session.create("user-123")
agent = Agent(session_id=session.id)
response = await agent.run("Hello")
```

**After (Consumer manages session):**
```python
from tinycua_sdk import Agent, LLMModel

messages = []
agent = Agent(llm_model=LLMModel())
response = await agent.run("Hello", messages=messages)
messages.append({"role": "user", "content": "Hello"})
messages.append({"role": "assistant", "content": response})
```

---

## Verification Plan

| Step | Command / Action | Expected Result |
|------|------------------|-----------------|
| 1 | `ls tinycua_sdk/session/` | Directory does not exist |
| 2 | `ls tinycua_sdk/utils/session.py` | File does not exist |
| 3 | `grep -r "session_id" tinycua_sdk/` | No matches (except possibly in comments) |
| 4 | `grep -r "from tinycua_sdk.session" tinycua_sdk/` | No matches |
| 5 | `grep -r "import tinycua_sdk.session" tinycua_sdk/` | No matches |
| 6 | `python -c "import tinycua_sdk"` | Package imports successfully |
| 7 | `pytest tests/unit/ -v` | All tests pass (or expected TDD failures if implementation lags) |
| 8 | `pytest tests/unit/test_agent.py -v` | Agent tests pass / expected behavior |
| 9 | `pytest tests/unit/test_config.py -v` | Config tests pass; no `session_id` references |

---

## Dependencies

| Dependency | Reason |
|------------|--------|
| **Stage 01** | Legacy tests and examples removed to avoid import errors |
| **Stage 02** | Unit tests define the stateless contract that this stage implements |

**Downstream impact:** Stages 04–07 can proceed in parallel. Stages 08–12 assume a stateless SDK.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hidden session imports in unexpected files | Medium | High | Use `grep -r` across entire `tinycua_sdk/` to find all references before deleting |
| `Agent.run()` consumers break if signature changes | Medium | Medium | Ensure `messages` is optional (`messages=None`); existing calls without `messages` still work |
| Circular imports after removing session references | Low | Medium | Check import graph after changes; resolve any broken imports |
| Tests reference deleted session modules | Medium | High | Stage 02 tests should already be stateless; if any remain, update them |
| `AgentConfig` deserialization fails with legacy `session_id` field | Medium | Medium | `from_dict()` should ignore or explicitly reject `session_id` with a clear error |

---

## Order of Operations

1. **Audit all session references** — Run `grep -r` to find every import and usage of `session_id`, `Session`, and `session/`.
2. **Delete files** — Remove `session/__init__.py`, `session/session.py`, `utils/session.py`.
3. **Update `agent/config.py`** — Remove `session_id` from `AgentConfig`.
4. **Update `agent/definition.py`** — Remove `session_id` field.
5. **Update `agent/executor.py`** — Remove `session_id` parameter and session loading logic.
6. **Update `agent/agent.py`** — Remove `session_id` parameter; add `messages` to `run()`.
7. **Update package exports** — Remove session exports from `__init__.py` files.
8. **Run verification** — Execute full verification plan.

---

## Acceptance Criteria

- [ ] `tinycua_sdk/session/` directory does not exist.
- [ ] `tinycua_sdk/utils/session.py` does not exist.
- [ ] `Agent.__init__` does not accept `session_id` parameter.
- [ ] `Agent.run()` accepts `messages` as an optional parameter.
- [ ] `AgentConfig` does not contain `session_id` field.
- [ ] `AgentDefinition` does not contain `session_id` field.
- [ ] No references to `session` in `tinycua_sdk/` (except possibly in comments).
- [ ] `pytest` still passes for remaining tests.
- [ ] Package imports successfully after changes.

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
