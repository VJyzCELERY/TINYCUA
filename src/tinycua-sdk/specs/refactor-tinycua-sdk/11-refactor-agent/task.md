# Tasks: Stage 11 — Refactor Agent

Implementation tasks for refactoring the Agent class to be stateless and fully runnable. Check off items as completed.

## Implementation Phase

- [ ] Create `agent/llm_model.py` — `LLMModel` value object <!-- id: 0 -->
  - [ ] Define Pydantic model with `ConfigDict(frozen=True)`
  - [ ] Add fields: provider, model_name, base_url, api_key, max_context, temperature, system_prompt
  - [ ] Implement `to_dict()` and `from_dict()`
  - [ ] Add unit tests
- [ ] Create `agent/backend_kind.py` — `BackendConfig` and `BackendKind` <!-- id: 1 -->
  - [ ] Define `BackendKind` enum (`LOCAL`, `REMOTE`)
  - [ ] Define `BackendConfig` Pydantic model with `ConfigDict(frozen=True)`
  - [ ] Add fields: kind, url, api_key, headers
  - [ ] Implement `to_dict()` and `from_dict()`
  - [ ] Add unit tests
- [ ] Refactor `agent/agent.py` — new constructor and methods <!-- id: 2 -->
  - [ ] Update `__init__` to accept new parameter set
  - [ ] Implement `add_tools()` (single + list)
  - [ ] Implement `add_skills()` (single + list)
  - [ ] Implement `run()` (async, returns `str` or `AsyncIterator[str]`)
  - [ ] Implement `from_config()` (dict, JSON, YAML)
  - [ ] Implement `to_config()` (serialization-friendly dict)
  - [ ] Reject old parameters explicitly
- [ ] Refactor `agent/config.py` — update `AgentConfig` <!-- id: 3 -->
  - [ ] Add `llm_model`, `backend`, `loop`, `strip_thinking` fields
  - [ ] Remove obsolete fields if any
  - [ ] Update `to_dict()` / `from_dict()`
- [ ] Refactor `agent/definition.py` — remove obsolete fields <!-- id: 4 -->
  - [ ] Strip `system_prompt`, `model`, `provider`, `base_url`, etc.
- [ ] Refactor `agent/executor.py` — remove remote/memory references <!-- id: 5 -->
  - [ ] Remove remote execution paths
  - [ ] Remove session/memory references
- [ ] Refactor `agent/loop.py` — remove `ReactLoop` <!-- id: 6 -->
  - [ ] Keep only `BaseLoop`
  - [ ] Ensure `BaseLoop.run()` signature matches design
- [ ] Refactor `agent/loop_resolver.py` — simplify resolution <!-- id: 7 -->
  - [ ] Only accept `None`, `BaseLoop`, or `dict` with `max_iterations`
  - [ ] Raise `ValueError` for string types like `"react"`
- [ ] Refactor `agent/validator.py` — remove `"react"` <!-- id: 8 -->
  - [ ] Update valid loop types to exclude `"react"`
- [ ] Refactor `agent/templates.py` — use new config structure <!-- id: 9 -->
  - [ ] Update prompt templates to source `system_prompt` from `llm_model`

## Testing Phase

- [ ] Unit tests for `LLMModel` and `BackendConfig` <!-- id: 10 -->
- [ ] Unit tests for new `Agent` constructor <!-- id: 11 -->
- [ ] Unit tests for `Agent` rejecting old parameters <!-- id: 12 -->
- [ ] Unit tests for `add_tools()` and `add_skills()` <!-- id: 13 -->
- [ ] Unit tests for `Agent.run()` (sync return and streaming) <!-- id: 14 -->
- [ ] Unit tests for `Agent.from_config()` with dict, JSON, YAML <!-- id: 15 -->
- [ ] Unit tests for `Agent.to_config()` <!-- id: 16 -->
- [ ] Unit tests for `BaseLoop` and `resolve_loop()` <!-- id: 17 -->
- [ ] Run full test suite and confirm all Stage 02 tests pass <!-- id: 18 -->

## Verification Phase

- [ ] Verify prompt construction uses `llm_model.system_prompt` + `instructions` <!-- id: 19 -->
- [ ] Verify `Agent` is stateless and fully runnable <!-- id: 20 -->

## Documentation Phase

- [ ] Update docstrings for all new/modified public methods <!-- id: 21 -->
- [ ] Update AGENTS.md if project conventions changed <!-- id: 22 -->

## Review and Merge

- [ ] Create pull request <!-- id: 23 -->
- [ ] Address review feedback <!-- id: 24 -->
- [ ] Merge to main branch <!-- id: 25 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
