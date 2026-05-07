# TINYCUA SDK v2 Refactor Roadmap

> **Status:** In Progress  
> **Scope:** Complete project reset of `tinycua-sdk` targeting the API defined in [`../goals/`](../goals/). This is a clean-slate build — not a migration from v1.  
> **End Goal:** All 16 goal-derived integration tests pass.
>
> ### Progress Summary
>
> | Stage | Status | Tests Targeted |
> |-------|--------|----------------|
> | 0 — Cleanup | ✅ Complete | Sanity imports |
> | 1 — Value Objects | ✅ Complete | `test_gs_01`, `test_int_01`, `test_int_02` |
> | 2 — Agent Config | ✅ Complete | `test_gs_02` |
> | 2.5 — Clear Backward Compat | ✅ Complete | Stage 2 constructor clean |
> | 3 — Execution Core | ✅ Complete | `test_gs_03`, `test_int_03` |
> | 4 — Skills & Composition | 📝 Draft | `test_int_04`, `test_int_05` |
> | 5 — Streaming | 📝 Draft | `test_gs_04` |
> | 6 — Serialization | 📝 Draft | `test_int_06–09` |
> | 7 — Security | 📝 Draft | `test_adv_02`, `test_adv_03` |
> | 8 — Custom Loops | 📝 Draft | `test_adv_01` |
> | 9 — Final Integration | 📝 Draft | All 16 pass |

---

## Principles

1. **Tests First** — Every stage begins by writing the integration tests that define success. Implementation follows.
2. **Clean Slate** — This is a project reset, not a migration. There is no backward compatibility because there is no prior version to be compatible with. Obsolete parameters and dead code are simply not created.
3. **Goals as Test Specs** — Each script in [`../goals/`](../goals/) becomes a comprehensive integration test.
4. **Automated & Mockable** — Tests that call `agent.run()` use a mock OpenAI-compatible transport so they run in CI without an external LLM server.

---

## Reference Documents

| Document | Purpose |
|----------|---------|
| [`REPORT_FINDINGS_TINYCUA_SDK.md`](./REPORT_FINDINGS_TINYCUA_SDK.md) | Full audit of dead code, stubs, and obsolete concepts to remove. Referenced by issue code (e.g., H-01, M-03). |
| [`../goals/getting-started/`](../goals/getting-started/) | API spec for `LanguageModel`, `Agent` creation, calling, and streaming. |
| [`../goals/intermediate/`](../goals/intermediate/) | API spec for `Tool`, `Skill`, composition, serialization, and directory loading. |
| [`../goals/advanced/`](../goals/advanced/) | API spec for custom loops, guardrails, and permission system. |

---

## Integration Test Inventory

Each goal script maps to one integration test file under `tests/integration/goals/`.

| # | Goal Script | Test File | Stage |
|---|-------------|-----------|-------|
| 1 | [`01_language_model_definition.py`](../goals/getting-started/01_language_model_definition.py) | `test_gs_01_language_model_definition.py` | 1 |
| 2 | [`02_agent_creation.py`](../goals/getting-started/02_agent_creation.py) | `test_gs_02_agent_creation.py` | 2 |
| 3 | [`03_agent_calling.py`](../goals/getting-started/03_agent_calling.py) | `test_gs_03_agent_calling.py` | 3 |
| 4 | [`04_agent_streaming.py`](../goals/getting-started/04_agent_streaming.py) | `test_gs_04_agent_streaming.py` | 5 |
| 5 | [`01_tool_creation.py`](../goals/intermediate/01_tool_creation.py) | `test_int_01_tool_creation.py` | 1 |
| 6 | [`02_skills_creation.py`](../goals/intermediate/02_skills_creation.py) | `test_int_02_skills_creation.py` | 1 |
| 7 | [`03_agent_with_tools.py`](../goals/intermediate/03_agent_with_tools.py) | `test_int_03_agent_with_tools.py` | 3 |
| 8 | [`04_agent_with_skills.py`](../goals/intermediate/04_agent_with_skills.py) | `test_int_04_agent_with_skills.py` | 4 |
| 9 | [`05_agent_with_tools_and_skills.py`](../goals/intermediate/05_agent_with_tools_and_skills.py) | `test_int_05_agent_with_tools_and_skills.py` | 4 |
| 10 | [`06_exporting_agent.py`](../goals/intermediate/06_exporting_agent.py) | `test_int_06_exporting_agent.py` | 6 |
| 11 | [`07_loading_agent.py`](../goals/intermediate/07_loading_agent.py) | `test_int_07_loading_agent.py` | 6 |
| 12 | [`08_loading_skills_from_directory.py`](../goals/intermediate/08_loading_skills_from_directory.py) | `test_int_08_loading_skills_from_directory.py` | 6 |
| 13 | [`09_loading_tools_from_directory.py`](../goals/intermediate/09_loading_tools_from_directory.py) | `test_int_09_loading_tools_from_directory.py` | 6 |
| 14 | [`01_custom_agent_loop.py`](../goals/advanced/01_custom_agent_loop.py) | `test_adv_01_custom_agent_loop.py` | 8 |
| 15 | [`02_guardrail_system.py`](../goals/advanced/02_guardrail_system.py) | `test_adv_02_guardrail_system.py` | 7 |
| 16 | [`03_permission_system.py`](../goals/advanced/03_permission_system.py) | `test_adv_03_permission_system.py` | 7 |

**Naming convention:** `test_{cat}_{nn}_{short_name}.py` where `cat` is `gs`, `int`, or `adv`.

---

## Stages

### Stage 0: Cleanup — ✅ Complete

**Objective:** Remove every dead module, stub, and obsolete concept so subsequent stages build on a clean foundation.

**Reference:** [`REPORT_FINDINGS_TINYCUA_SDK.md`](./REPORT_FINDINGS_TINYCUA_SDK.md) — apply every issue marked H-xx, M-xx, and L-xx.

**Key deletions (see report for full list):**
- `backend_kind.py`, `templates.py`, `loader.py`, all resolvers, `hooks.py`
- `tools/cua/`, `tools/mcp.py`, `tools/parser.py`, `tools/resolver.py`
- `skills/cache.py`, `skills/improver.py`
- `events/`, `utils/`, planning models
- Sub-agent code, hook system, `DefaultLoop`, `run_sync()`, `stream_sync()`
- `PermissionSystem` standalone class / `PermissionLevel` enum

**Tests targeted:**
- Sanity import: `from tinycua_sdk import Agent, LLMModel, Tool, tool, Skill` succeeds.
- Deleted-module import raises `ModuleNotFoundError`.

---

### Stage 1: Core Value Objects — ✅ Complete

**Objective:** Implement the three pure value objects that have no I/O dependencies.

**References:**
- [`goals/getting-started/01_language_model_definition.py`](../goals/getting-started/01_language_model_definition.py)
- [`goals/intermediate/01_tool_creation.py`](../goals/intermediate/01_tool_creation.py)
- [`goals/intermediate/02_skills_creation.py`](../goals/intermediate/02_skills_creation.py)

**What to build (test first):**
1. **`LanguageModel`** (rename from `LLMModel`) — add all missing OpenAI-compatible params (`max_tokens`, `top_p`, `frequency_penalty`, `presence_penalty`, `stop`, `seed`, `response_format`, `tool_choice`, `logprobs`, `top_logprobs`, `user`), env-var substitution, serialization. Move `strip_thinking` here.
2. **`Tool` / `@tool`** — schema generation from function signature + docstring, manual `Tool` construction, `to_config()`, `invoke()`, `dependencies` metadata.
3. **`Skill`** — pure value object with `to_dict()` / `from_dict()`. `SkillRegistry` for discovery.

**Tests targeted:** `test_gs_01`, `test_int_01`, `test_int_02`

---

### Stage 2: Agent Configuration & Creation — ✅ Complete

**Objective:** An `Agent` can be instantiated and configured, but cannot yet execute.

**Reference:** [`goals/getting-started/02_agent_creation.py`](../goals/getting-started/02_agent_creation.py)

**What to build (test first):**
1. **`AgentConfig` / `AgentPolicy`** — behavior settings only (`max_tool_calls`, `parallel_tool_calls`). Remove `temperature` from policy.
2. **`Agent` constructor** — matches the spec: `name`, `instructions`, `llm_model`, `tools`, `skills`, `policy`, `metadata`, `loop`, `tool_permissions`, `approval_workflow`. `add_tools()`, `add_skills()`, `to_config()`. Clean constructor with no backward-compatibility validation.

**Tests targeted:** `test_gs_02`

---

### Stage 2.5: Clear Backward Compatibility — ✅ Complete

**Objective:** Strip all backward-compatibility artifacts from the project. This is a spec-and-test cleanup stage with no runtime code changes.

**Reference:** `specs/stage-2.5-clear-backward-compat/`

**What to do:**
1. Remove `_OBSOLETE_PARAMS` and its validation logic from Stage 2's constructor design.
2. Delete the "obsolete params rejected" target from Stage 2.
3. Update all subsequent stages (3–9) to remove any backward-compatibility framing.
4. Renumber remaining Stage 2 targets (2.6→2.5, 2.7→2.6) — completed.

**Tests targeted:** Verify Stage 2 constructor is clean (no custom obsolete-param validation).

---

### Stage 3: LLM Client & Basic Execution Loop — ✅ Complete

**Objective:** The agent can call an LLM and return a response. Non-streaming only.

**References:**
- [`goals/getting-started/03_agent_calling.py`](../goals/getting-started/03_agent_calling.py)
- [`goals/intermediate/03_agent_with_tools.py`](../goals/intermediate/03_agent_with_tools.py)

**What to build (test first):**
1. **`LLMClient` ABC + `OpenAICompatibleClient`** — forwards all `LanguageModel` params to the provider; returns normalized dict.
2. **`BaseLoop.run()`** — full implementation: call LLM → parse `tool_calls` → execute via `ToolExecutor` → append results → re-call → repeat until done or `max_iterations`. Respects cancellation.
3. **`ToolExecutor`** — canonical tool execution path. Checks `tool_permissions` (`allow`/`deny`/`ask`) and optional `ApprovalWorkflow` before invoking.
4. **`ApprovalWorkflow` ABC** — `request_approval(tool_name, arguments) -> dict`. `DefaultApprovalWorkflow` always approves.

**Tests targeted:** `test_gs_03`, `test_int_03`

---

### Stage 4: Skills & Composition

**Objective:** Skills inject instructions into the system prompt. Agents can use both tools and skills together.

**References:**
- [`goals/intermediate/04_agent_with_skills.py`](../goals/intermediate/04_agent_with_skills.py)
- [`goals/intermediate/05_agent_with_tools_and_skills.py`](../goals/intermediate/05_agent_with_tools_and_skills.py)

**What to build (test first):**
1. **Skill prompt injection** — effective system prompt = `instructions` + each skill's `instructions` in order. Skills are metadata-only and do NOT auto-resolve tools.
2. **Combined usage** — `tools` + `skills` accepted simultaneously. Dynamic `add_skills()`.

**Tests targeted:** `test_int_04`, `test_int_05`

---

### Stage 5: Streaming

**Objective:** Implement all four streaming modes.

**Reference:** [`goals/getting-started/04_agent_streaming.py`](../goals/getting-started/04_agent_streaming.py)

**What to build (test first):**
1. **`stream="off"`** → returns `str` (default).
2. **`stream="token"`** → `AsyncIterator[dict]` of token deltas (OpenAI Responses API shape).
3. **`stream="event"`** → `AsyncIterator[dict]` of agent events (no token deltas).
4. **`stream="all"`** → interleaved token deltas + agent events.

**Tests targeted:** `test_gs_04`

---

### Stage 6: Serialization & Directory Loading

**Objective:** Export/import agents, skills, and tools. Bulk-load from directories.

**References:**
- [`goals/intermediate/06_exporting_agent.py`](../goals/intermediate/06_exporting_agent.py)
- [`goals/intermediate/07_loading_agent.py`](../goals/intermediate/07_loading_agent.py)
- [`goals/intermediate/08_loading_skills_from_directory.py`](../goals/intermediate/08_loading_skills_from_directory.py)
- [`goals/intermediate/09_loading_tools_from_directory.py`](../goals/intermediate/09_loading_tools_from_directory.py)

**What to build (test first):**
1. **Agent serialization** — `to_json()` / `to_yaml()` with optional secret redaction. `from_json_file()` / `from_yaml_file()` / `from_dict()`. Round-trip parity.
2. **Skill directory loading** — `Skill.load_directory()` discovers `SKILL.md` files per subdirectory. Supporting `.py` files ignored.
3. **Tool directory loading** — `Tool.load_directory()` discovers `@tool` decorators. Supporting files ignored.

**Tests targeted:** `test_int_06`, `test_int_07`, `test_int_08`, `test_int_09`

---

### Stage 7: Security — Guardrails & Permissions

**Objective:** Declarative and custom guardrails control tool execution.

**References:**
- [`goals/advanced/02_guardrail_system.py`](../goals/advanced/02_guardrail_system.py)
- [`goals/advanced/03_permission_system.py`](../goals/advanced/03_permission_system.py)

**What to build (test first):**
1. **`ApprovalWorkflow` integration** — `ToolExecutor` calls `request_approval()` before execution. Denied calls return the denial reason to the agent.
2. **`Agent.tool_permissions`** — `dict[str, Literal["allow", "ask", "deny"]]`. `"deny"` blocks immediately; `"ask"` routes through guardrail; default is `"allow"`. Mutable at runtime.

**Tests targeted:** `test_adv_02`, `test_adv_03`

---

### Stage 8: Extensibility — Custom Loops

**Objective:** `BaseLoop` is a clean extension point for consumers.

**Reference:** [`goals/advanced/01_custom_agent_loop.py`](../goals/advanced/01_custom_agent_loop.py)

**What to build (test first):**
1. **`BaseLoop`** — `__init__(max_iterations=5)`, `async run(agent, messages, tools)`. Default implementation is the standard tool-calling loop. No hook system — customization via subclassing.
2. **Protected helper** — `agent._call_llm(messages, tools)` so custom loops can call the LLM without reimplementing transport.

**Tests targeted:** `test_adv_01`

---

### Stage 9: Final Integration & Polish

**Objective:** All 16 integration tests pass. SDK is coherent and documented.

**What to do:**
1. Run full suite: `pytest tests/integration/goals/ -v`
2. Ensure all 16 goal tests pass.
3. Remove remaining `Any` types that can be concrete.
4. Update `__init__.py` exports to the v2 public API.
5. Update `AGENTS.md` if it references deleted APIs.
6. Delete old unit tests for removed modules.

**Acceptance criteria:**
- `pytest tests/integration/goals/` → 16 passed, 0 failed.
- `ruff check tinycua_sdk/` passes.
- No `NotImplementedError` stubs remain in production code.

---

## Dependency Graph

```
Stage 0 (Cleanup)
    │
    ▼
Stage 1 (Value Objects) ──► test_gs_01, test_int_01, test_int_02
    │
    ▼
Stage 2 (Agent Creation) ──► test_gs_02
    │
    ▼
Stage 2.5 (Clear Backward Compat)
    │
    ▼
Stage 3 (Execution Core) ──► test_gs_03, test_int_03
    │
    ▼
Stage 4 (Skills) ──► test_int_04, test_int_05
    │
    ▼
Stage 5 (Streaming) ──► test_gs_04
    │
    ▼
Stage 6 (Serialization & Loading) ──► test_int_06-09
    │
    ▼
Stage 7 (Security) ──► test_adv_02, test_adv_03
    │
    ▼
Stage 8 (Custom Loops) ──► test_adv_01
    │
    ▼
Stage 9 (Final Integration)
```
