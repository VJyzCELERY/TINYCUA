# Tasks: Stage 0 — Scorched-Earth Cleanup

Implementation tasks for Stage 0: Scorched-Earth Cleanup. Check off items as completed.

## Implementation Phase

### Phase 1: Delete Leaf Modules

- [ ] Delete empty and unused directories/files from tinycua_sdk/ <!-- id: 0 -->
  - [ ] Remove `tinycua_sdk/events/` directory <!-- id: 1 -->
  - [ ] Remove `tinycua_sdk/utils/` directory <!-- id: 2 -->
  - [ ] Remove `tinycua_sdk/tools/cua/` directory <!-- id: 3 -->
  - [ ] Remove `tinycua_sdk/tools/native/context_tools.py` <!-- id: 4 -->
  - [ ] Remove `tinycua_sdk/tools/parser.py` <!-- id: 5 -->
  - [ ] Remove `tinycua_sdk/tools/resolver.py` <!-- id: 6 -->
  - [ ] Remove `tinycua_sdk/tools/mcp.py` <!-- id: 7 -->
  - [ ] Remove `tinycua_sdk/skills/cache.py` <!-- id: 8 -->
  - [ ] Remove `tinycua_sdk/skills/improver.py` <!-- id: 9 -->
  - [ ] Remove `tinycua_sdk/models/task.py` <!-- id: 10 -->

- [ ] Delete dead config and agent modules <!-- id: 11 -->
  - [ ] Remove `tinycua_sdk/core/config.py` <!-- id: 12 -->
  - [ ] Remove `tinycua_sdk/agent/validator.py` <!-- id: 13 -->
  - [ ] Remove `tinycua_sdk/agent/loader.py` <!-- id: 14 -->
  - [ ] Remove `tinycua_sdk/agent/loop_resolver.py` <!-- id: 15 -->
  - [ ] Remove `tinycua_sdk/agent/tool_resolver.py` <!-- id: 16 -->
  - [ ] Remove `tinycua_sdk/agent/skill_resolver.py` <!-- id: 17 -->
  - [ ] Remove `tinycua_sdk/agent/templates.py` <!-- id: 18 -->
  - [ ] Remove `tinycua_sdk/agent/backend_kind.py` <!-- id: 19 -->
  - [ ] Remove `tinycua_sdk/agent/hooks.py` <!-- id: 20 -->

- [ ] Verify Phase 1 — import sanity check <!-- id: 21 -->
  - [ ] Run `python -c "import tinycua_sdk"` and confirm exit code 0 <!-- id: 22 -->

### Phase 2: Gut Keeping Files

- [ ] Simplify `tinycua_sdk/agent/config.py` — remove temperature, BackendConfig, strip_thinking <!-- id: 23 -->

- [ ] Simplify `tinycua_sdk/agent/definition.py` — remove sub-agent fields and methods, BackendConfig references <!-- id: 24 -->

- [ ] Simplify `tinycua_sdk/agent/loop.py` — remove VALID_LOOP_TYPES, DefaultLoop, HookManager usage, hook methods <!-- id: 25 -->

- [ ] Simplify `tinycua_sdk/agent/executor.py` — remove stub methods (run_sync, stream, stream_sync, check_tool_permission, execute_subprocess, _get_global_config), remove sub-agent params from __init__ <!-- id: 26 -->

- [ ] Simplify `tinycua_sdk/agent/agent.py` — remove from_template(), BackendConfig import, obsolete constructor params; apply new constructor signature <!-- id: 27 -->

- [ ] Simplify `tinycua_sdk/security/approval.py` — remove timeout parameter and references <!-- id: 28 -->

- [ ] Simplify `tinycua_sdk/security/permissions.py` — remove PermissionLevel enum, PermissionSystem class, _setup_default_permissions() <!-- id: 29 -->

- [ ] Simplify `tinycua_sdk/core/providers.py` — remove Anthropic stub provider entry <!-- id: 30 -->

- [ ] Rewrite `tinycua_sdk/__init__.py` with minimal public API exports <!-- id: 31 -->
  - [ ] Update imports to reference only kept modules <!-- id: 32 -->
  - [ ] Set __all__ = ["Agent", "AgentConfig", "AgentDefinition", "AgentExecutor", "AgentPolicy", "BaseLoop", "LLMModel", "Skill", "SkillRegistry", "Tool", "tool"] <!-- id: 33 -->

- [ ] Verify Phase 2 — import and constructor sanity check <!-- id: 34 -->
  - [ ] Run `python -c "from tinycua_sdk import Agent, LLMModel, Tool, tool, Skill; print('OK')"` <!-- id: 35 -->
  - [ ] Confirm `Agent(system_prompt='hello')` raises TypeError <!-- id: 36 -->

### Phase 3: Clean Old Tests

- [ ] Delete orphaned test files from tests/unit/ <!-- id: 37 -->
  - [ ] Remove `test_backend_config.py` <!-- id: 38 -->
  - [ ] Remove `test_agent_templates.py` <!-- id: 39 -->
  - [ ] Remove `test_loop_resolver.py` <!-- id: 40 -->
  - [ ] Remove `test_tool_resolver.py` <!-- id: 41 -->
  - [ ] Remove `test_mcp.py` <!-- id: 42 -->
  - [ ] Remove `test_skills_cache.py` <!-- id: 43 -->
  - [ ] Remove `test_skills_improver.py` <!-- id: 44 -->
  - [ ] Remove `test_command_parser.py` <!-- id: 45 -->
  - [ ] Remove `test_agent_hooks.py` <!-- id: 46 -->
  - [ ] Remove `test_middleware_hooks.py` <!-- id: 47 -->
  - [ ] Remove `test_injection_detection.py` <!-- id: 48 -->
  - [ ] Remove `test_context_discovery.py` <!-- id: 49 -->
  - [ ] Remove `test_sanitizer.py` <!-- id: 50 -->

## Testing Phase

- [ ] Run ruff check on remaining codebase — `ruff check tinycua_sdk/` passes <!-- id: 51 -->
- [ ] Run full test suite on remaining tests — `pytest tests/unit/ -x` passes (excluding deleted test files) <!-- id: 52 -->

## Verification Phase

- [ ] Verify all success criteria from spec.md pass <!-- id: 53 -->
  - [ ] Import Sanity: `from tinycua_sdk import Agent, LanguageModel, Tool, tool, Skill; print('OK')` prints OK <!-- id: 54 -->
  - [ ] Deleted Modules Raise ImportError: importing deleted module raises ModuleNotFoundError <!-- id: 55 -->
  - [ ] No Obsolete Parameters Accepted: `Agent(system_prompt='hello')` raises TypeError <!-- id: 56 -->
  - [ ] No NotImplementedError at Import: `import tinycua_sdk` exits with code 0 <!-- id: 57 -->
  - [ ] Ruff Passes: `ruff check tinycua_sdk/` exits with code 0 <!-- id: 58 -->

- [ ] Verify no dangling imports in kept files — grep for references to deleted modules <!-- id: 59 -->
- [ ] Verify __init__.py exports match the new minimal API surface <!-- id: 60 -->

## Documentation Phase

- [ ] Update spec.md status from "Draft" to "Complete" <!-- id: 61 -->

## Review and Merge

- [ ] Create single atomic commit — "Stage 0: Remove dead code, stubs, and obsolete concepts" <!-- id: 62 -->
- [ ] Address review feedback if any <!-- id: 63 -->
- [ ] Merge to main branch <!-- id: 64 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-05-03*
