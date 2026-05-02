# Stage 0: Scorched-Earth Cleanup — Specification

**Status**: Draft | In Progress | Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-02
**Subproject(s) Affected**: tinycua-sdk

## Objective
Remove every dead module, stub, and obsolete concept identified in the review report so subsequent stages build on a clean foundation. Zero backward compatibility is maintained.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md`](../../docs/ROADMAP.md#principles).

## References
- [`REPORT_FINDINGS_TINYCUA_SDK.md`](../docs/REPORT_FINDINGS_TINYCUA_SDK.md) — source of truth for what to delete.

## Scope of Deletion

### Files to Delete Entirely
Apply every issue code (H-xx, M-xx, L-xx) from the report.

| # | File / Directory | Issue Code | Why |
|---|------------------|------------|-----|
| 1 | `agent/backend_kind.py` | H-01, H-15 | SDK is stateless; backend concept is consumer concern. |
| 2 | `agent/templates.py` | H-02, M-11 | Adds bloat; config/YAML is sufficient. |
| 3 | `agent/loader.py` | M-03 | Dead; loading already exists on `Agent` class. |
| 4 | `agent/loop_resolver.py` | H-03 | Dead; `loop.py` has its own resolver. |
| 5 | `agent/tool_resolver.py` | H-04 | Dead; unused by agent. |
| 6 | `agent/skill_resolver.py` | H-05, H-09, H-10 | Dead; skills are metadata-only, no tool auto-resolution. |
| 7 | `agent/hooks.py` | H-16 | Unwired facade; customization via subclassing instead. |
| 8 | `agent/validator.py` | M-01, M-02, M-13 | Obsolete checks (`KNOWN_MODELS`, `KNOWN_LOOP_TYPES`). |
| 9 | `core/config.py` | M-14 | `SDKConfig`, `LLMConfig`, `LoopConfig` are dead. |
| 10 | `tools/cua/` directory | L-04, L-05 | Out of SDK scope and empty. |
| 11 | `tools/mcp.py` | M-09 | Unused; not integrated into execution path. |
| 12 | `tools/parser.py` | L-18 | General-purpose utilities parked in wrong module. |
| 13 | `tools/resolver.py` | M-15 | Exported but unused. |
| 14 | `tools/native/context_tools.py` | M-04 | Completely empty. |
| 15 | `skills/cache.py` | L-15 | Unused. |
| 16 | `skills/improver.py` | L-08 | Unused; skill improvement is agent-dev concern. |
| 17 | `events/` directory | L-16 | Empty placeholder. |
| 18 | `utils/` directory | L-17 | Empty package. |
| 19 | `models/task.py` | M-07 | Unused data structures (`TaskPlan`, `TodoItem`). |
| 20 | Planning stubs in `models/result.py` | M-07 | `PlanningResult`, `PlanRunResult` are unused. |

### Concepts / Code Patterns to Remove from Keeping Files

| # | Location | What to Remove | Issue Code |
|---|----------|----------------|------------|
| 1 | `agent/loop.py` | `VALID_LOOP_TYPES`, `_validate_loop_type()`, `DefaultLoop`, hook manager usage | L-01, M-06, H-16 |
| 2 | `agent/executor.py` | `run_sync()`, `stream()`, `stream_sync()`, static permission methods, `execute_subprocess()`, `_get_global_config()`, sub-agent params | M-10, M-16, L-10, L-11, M-14, H-13 |
| 3 | `agent/config.py` | `temperature` from `AgentPolicy`, `BackendConfig` references, `strip_thinking` | L-07, H-15, L-13 |
| 4 | `agent/definition.py` | All sub-agent methods/fields, `strip_thinking`, `BackendConfig` | H-13, L-13, H-15 |
| 5 | `agent/agent.py` | `_OBSOLETE_PARAMS` and all obsolete parameter handling, `from_template()`, `BackendConfig`, `sub_agents`/`max_depth` params | M-12, M-11, H-15, H-13 |
| 6 | `security/approval.py` | `timeout` param | L-06 |
| 7 | `security/permissions.py` | Hardcoded defaults, `PermissionLevel` enum, standalone `PermissionSystem` class | M-05 |
| 8 | `core/providers.py` | Anthropic stub | L-14 |
| 9 | `__init__.py` | All deleted exports | H-15 |

### What to Keep (and Refactor in Later Stages)

| Module | Stage 0 Action | Future Stage |
|--------|---------------|--------------|
| `agent/llm_model.py` | Keep file, keep class | Stage 1: rename to `LanguageModel`, add params |
| `agent/loop.py` | Keep file, keep `BaseLoop` class, gut dead code | Stage 3: implement real `run()` |
| `agent/executor.py` | Keep file, keep `AgentExecutor` class, gut stubs | Stage 3: wire `ToolExecutor` |
| `agent/config.py` | Keep file, keep `AgentConfig`/`AgentPolicy`, simplify | Stage 2: finalize shape |
| `agent/definition.py` | Keep file, simplify (remove sub-agent code) | Stage 2: collapse into `AgentConfig` |
| `agent/agent.py` | Keep file, simplify constructor | Stage 2: new constructor shape |
| `tools/decorators.py` | Keep `Tool`/`@tool` | Stage 1: enhance schema generation |
| `tools/schema.py` | Keep | Stage 1: use for `@tool` |
| `skills/models.py` | Keep `Skill` | Stage 1: ensure all fields |
| `skills/registry.py` | Keep `SkillRegistry` | Stage 1: ensure API |
| `security/approval.py` | Keep `ApprovalWorkflow`, remove timeout | Stage 3: redesign as ABC |

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] Import Sanity - N/A - prints `OK` - python -c "from tinycua_sdk import Agent, LanguageModel, Tool, tool, Skill; print('OK')"
  Description: `from tinycua_sdk import Agent, LanguageModel, Tool, tool, Skill` succeeds without error.

- [ ] Deleted Modules Raise ImportError - N/A - ModuleNotFoundError - python -c "from tinycua_sdk.agent import backend_kind" 2>&1 | grep "ModuleNotFoundError"
  Description: Any deleted module raises `ModuleNotFoundError` on import.

- [ ] No Obsolete Parameters Accepted - N/A - TypeError - python -c "try: Agent(system_prompt='hello') except TypeError: print('PASS:', e)"
  Description: Passing any obsolete parameter to `Agent()` raises `TypeError`.

- [ ] No NotImplementedError at Import - N/A - exits with code 0 - python -c "import tinycua_sdk"
  Description: Importing the SDK does not trigger any `NotImplementedError`.

- [ ] Ruff Passes (with expected exceptions) - N/A - exits with code 0 - ruff check tinycua_sdk/
  Description: `ruff check` passes on the remaining codebase.
