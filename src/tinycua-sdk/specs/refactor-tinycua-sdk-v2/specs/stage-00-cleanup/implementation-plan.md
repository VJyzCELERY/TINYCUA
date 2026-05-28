# Implementation: Stage 0 — Scorched-Earth Cleanup

Remove every dead module, stub, and obsolete concept from tinycua-sdk so subsequent stages build on a clean foundation. Zero backward compatibility is maintained.

## Context

- **Spec Reference**: `specs/refactor-tinycua-sdk-v2/specs/stage-00-cleanup/spec.md`
- **Design Reference**: `specs/refactor-tinycua-sdk-v2/specs/stage-00-cleanup/design.md`
- **Priority**: P0 — prerequisite for all subsequent refactor stages
- **Estimated Effort**: M

## Proposed Changes

### Phase 1: Delete Leaf Modules (no downstream SDK deps)

#### [DELETE] `tinycua_sdk/events/` directory
- **[Description]**: Remove entire empty placeholder directory
- **[Rationale]**: L-16 — Empty placeholder, no functionality

#### [DELETE] `tinycua_sdk/utils/` directory
- **[Description]**: Remove entire empty package directory
- **[Rationale]**: L-17 — Empty package, no functionality

#### [DELETE] `tinycua_sdk/tools/cua/` directory
- **[Description]**: Remove entire out-of-scope directory
- **[Rationale]**: L-04, L-05 — Out of SDK scope and empty

#### [DELETE] `tinycua_sdk/tools/native/context_tools.py`
- **[Description]**: Remove completely empty file
- **[Rationale]****: M-04 — Completely empty module

#### [DELETE] `tinycua_sdk/tools/parser.py`
- **[Description]**: Remove general-purpose utilities in wrong module
- **[Rationale]**: L-18 — General-purpose utilities parked in wrong module

#### [DELETE] `tinycua_sdk/tools/resolver.py`
- **[Description]**: Remove exported but unused resolver
- **[Rationale]**: M-15 — Exported but unused

#### [DELETE] `tinycua_sdk/tools/mcp.py`
- **[Description]**: Remove unused MCP integration
- **[Rationale]**: M-09 — Unused, not integrated into execution path

#### [DELETE] `tinycua_sdk/skills/cache.py`
- **[Description]**: Remove unused cache module
- **[Rationale]**: L-15 — Unused

#### [DELETE] `tinycua_sdk/skills/improver.py`
- **[Description]**: Remove unused improver module
- **[Rationale]**: L-08 — Skill improvement is agent-dev concern, not SDK concern

#### [DELETE] `tinycua_sdk/models/task.py`
- **[Description]**: Remove unused data structures (TaskPlan, TodoItem)
- **[Rationale]**: M-07 — Unused data structures

#### [DELETE] `tinycua_sdk/core/config.py`
- **[Description]**: Remove SDKConfig, LLMConfig, LoopConfig dead configs
- **[Rationale]**: M-14 — Dead config classes

#### [DELETE] `tinycua_sdk/agent/validator.py`
- **[Description]**: Remove obsolete validation checks (KNOWN_MODELS, KNOWN_LOOP_TYPES)
- **[Rationale]**: M-01, M-02, M-13 — Obsolete checks

#### [DELETE] `tinycua_sdk/agent/loader.py`
- **[Description]**: Remove dead loader module
- **[Rationale]**: M-03 — Dead; loading already exists on Agent class

#### [DELETE] `tinycua_sdk/agent/loop_resolver.py`
- **[Description]**: Remove dead loop resolver
- **[Rationale]**: H-03 — Dead; loop.py has its own resolver

#### [DELETE] `tinycua_sdk/agent/tool_resolver.py`
- **[Description]**: Remove unused tool resolver
- **[Rationale]**: H-04 — Dead, unused by agent

#### [DELETE] `tinycua_sdk/agent/skill_resolver.py`
- **[Description]**: Remove dead skill resolver
- **[Rationale]**: H-05, H-09, H-10 — Dead; skills are metadata-only

#### [DELETE] `tinycua_sdk/agent/templates.py`
- **[Description]**: Remove templates module that adds bloat
- **[Rationale]**: H-02, M-11 — Adds bloat; config/YAML is sufficient

#### [DELETE] `tinycua_sdk/agent/backend_kind.py`
- **[Description]**: Remove backend kind enum/module
- **[Rationale]**: H-01, H-15 — SDK is stateless; backend concept is consumer concern

#### [DELETE] `tinycua_sdk/agent/hooks.py`
- **[Description]**: Remove unwired hooks facade
- **[Rationale]**: H-16 — Unwired facade; customization via subclassing instead

### Phase 2: Gut Keeping Files

#### [MODIFY] `tinycua_sdk/agent/loop.py`
- **[Description]**: Remove VALID_LOOP_TYPES, _validate_loop_type(), DefaultLoop class, HookManager usage, add_pre_hook/add_post_hook methods. Keep BaseLoop class with minimal stub run().
- **[Rationale]**: L-01, M-06, H-16 — Loop type validation and hooks are dead code; loop implementation deferred to Stage 3

#### [MODIFY] `tinycua_sdk/agent/executor.py`
- **[Description]**: Remove run_sync(), stream()/stream_sync(), check_tool_permission(), check_tool_approval_required(), execute_subprocess(), _get_global_config(). Remove sub_agents, max_depth, current_depth from __init__. Keep AgentExecutor class skeleton with run() and _call_llm() stubs.
- **[Rationale]**: M-10, M-16, L-10, L-11, M-14, H-13 — All removed methods are stubs or unused; sub-agent params deferred

#### [MODIFY] `tinycua_sdk/agent/config.py`
- **[Description]**: Remove temperature from AgentPolicy. Remove BackendConfig import and field from AgentConfig. Remove strip_thinking field. Keep AgentConfig/AgentPolicy with simplified shape.
- **[Rationale]**: L-07, H-15, L-13 — Temperature and backend config are consumer concerns; strip_thinking deferred

#### [MODIFY] `tinycua_sdk/agent/definition.py`
- **[Description]**: Remove sub_agents, max_depth, current_depth, keywords fields. Remove add_sub_agent(), _get_all_sub_agents(), _find_sub_agent_for_task(), _pass_context_to_sub_agent(), _aggregate_results() methods. Remove BackendConfig and strip_thinking references. Keep AgentDefinition data container.
- **[Rationale]**: H-13, L-13 — Sub-agent code is not wired; deferred to later stages

#### [MODIFY] `tinycua_sdk/agent/agent.py`
- **[Description]**: Remove from_template() classmethod. Remove BackendConfig import. Remove sub_agents, max_depth, backend, strip_thinking parameters from __init__. Apply new constructor signature with name, instructions, llm_model, tools, skills, policy, metadata, loop.
- **[Rationale]**: M-11, H-15, H-13 — Clean unused v1 artifacts from constructor; backward-compat validation is handled separately in Stage 2.5

#### [MODIFY] `tinycua_sdk/security/approval.py`
- **[Description]**: Remove timeout parameter from ApprovalWorkflow.__init__. Remove any method referencing self.timeout. Keep ApprovalWorkflow class.
- **[Rationale]**: L-06 — Timeout not wired into approval flow

#### [MODIFY] `tinycua_sdk/security/permissions.py`
- **[Description]**: Remove PermissionLevel enum, PermissionSystem class, _setup_default_permissions(). File can be kept as empty module or deleted entirely.
- **[Rationale]**: M-05 — Hardcoded defaults and standalone PermissionSystem are dead

#### [MODIFY] `tinycua_sdk/core/providers.py`
- **[Description]**: Remove Anthropic stub provider entry from providers dict.
- **[Rationale]**: L-14 — Stub provider not integrated

#### [MODIFY] `tinycua_sdk/__init__.py`
- **[Description]**: Replace all deleted exports with new minimal __all__ list: Agent, AgentConfig, AgentDefinition, AgentExecutor, AgentPolicy, BaseLoop, LLMModel, Skill, SkillRegistry, Tool, tool. Update imports accordingly.
- **[Rationale]**: H-15 — Exports must reflect only kept modules

### Phase 3: Clean Old Tests

#### [DELETE] `tests/unit/test_backend_config.py`
- **[Description]**: Remove test for deleted backend config module
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_agent_templates.py`
- **[Description]**: Remove test for deleted templates module
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_loop_resolver.py`
- **[Description]**: Remove test for deleted loop resolver
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_tool_resolver.py`
- **[Description]**: Remove test for deleted tool resolver
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_mcp.py`
- **[Description]**: Remove test for deleted MCP module
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_skills_cache.py`
- **[Description]**: Remove test for deleted skills cache
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_skills_improver.py`
- **[Description]**: Remove test for deleted skills improver
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_command_parser.py`
- **[Description]**: Remove test for deleted parser module
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_agent_hooks.py`
- **[Description]**: Remove test for deleted hooks module
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_middleware_hooks.py`
- **[Description]**: Remove test for deleted hooks-related code
- **[Rationale]**: Tests the deleted code

#### [DELETE] `tests/unit/test_injection_detection.py`
- **[Description]**: Remove orphaned injection detection test
- **[Rationale]**: Not relevant to cleaned SDK

#### [DELETE] `tests/unit/test_context_discovery.py`
- **[Description]**: Remove orphaned context discovery test
- **[Rationale]**: Not relevant to cleaned SDK

#### [DELETE] `tests/unit/test_sanitizer.py`
- **[Description]**: Remove orphaned sanitizer test
- **[Rationale]**: Not relevant to cleaned SDK

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `agent/` package | Modify | Delete 10 files, gut 5 files (loop.py, executor.py, config.py, definition.py, agent.py) |
| `tools/` package | Modify | Delete 4 files (mcp.py, parser.py, resolver.py, context_tools.py), remove cua/ directory |
| `skills/` package | Modify | Delete 2 files (cache.py, improver.py) |
| `security/` package | Modify | Gut approval.py and permissions.py |
| `core/` package | Modify | Delete config.py, gut providers.py |
| `models/` package | Modify | Delete task.py |
| `events/`, `utils/` packages | Delete | Entire empty directories removed |
| `__init__.py` | Modify | Minimal public API exports only |
| `tests/unit/` | Modify | Delete 13 orphaned test files |

## Verification Plan

### Automated Tests

- [ ] Import Sanity — `python -c "from tinycua_sdk import Agent, LanguageModel, Tool, tool, Skill; print('OK')"` prints OK
- [ ] Deleted Modules Raise ImportError — `python -c "from tinycua_sdk.agent import backend_kind" 2>&1 | grep "ModuleNotFoundError"` succeeds
- [ ] No Obsolete Parameters Accepted — `Agent(system_prompt='hello')` raises TypeError
- [ ] No NotImplementedError at Import — `python -c "import tinycua_sdk"` exits with code 0
- [ ] Ruff Passes — `ruff check tinycua_sdk/` exits with code 0

### Manual Verification

- [ ] Verify all kept files still have valid Python syntax (no dangling imports)
- [ ] Verify __init__.py exports match the new minimal API surface
- [ ] Confirm no remaining file references any deleted module or class

## Rollout Strategy

1. **Phase 1** — Delete leaf modules, verify `import tinycua_sdk` still works after each batch
2. **Phase 2** — Gut keeping files in dependency order (config.py → definition.py → loop.py → executor.py → agent.py → security/ → core/), verify import and constructor sanity after each file
3. **Phase 3** — Delete orphaned test files, run remaining test suite

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| ruff | latest | Lint verification |
| pytest | latest | Test execution |

### Internal Dependencies

- [ ] Blocks all subsequent refactor stages (Stage 1–7)
- [ ] Depends on REPORT_FINDINGS_TINYCUA_SDK.md for issue codes and deletion scope

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Import chain breakage when deleting files mid-phase | High — broken imports cascade | Follow dependency order from design.md; fix kept files immediately when a deleted import is encountered |
| Accidentally removing code needed by external consumers | High — zero backward compat is intentional per spec | Strictly follow the deletion list in spec.md and design.md; do not delete anything not explicitly listed |
| Stale __init__.py exports after deletions | Medium — ImportError on public API | Rewrite __init__.py last (Phase 2 end) with only kept module exports |
| Test suite failures from deleted tests | Low — expected, tests are being removed intentionally | Delete corresponding test files in Phase 3; verify remaining tests pass |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-03*
