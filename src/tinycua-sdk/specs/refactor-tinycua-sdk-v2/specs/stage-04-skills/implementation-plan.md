# Stage 4: Skills & Composition — Implementation Plan

**Status**: In Progress
**Created**: 2026-05-07
**Spec**: `spec.md`
**Design**: `design.md`

## Analysis

### What's Already Implemented

The following components are already in place from previous stages:

1. **`Skill` model** (`tinycua_sdk/skills/models.py`) — Frozen Pydantic dataclass with `name`, `description`, `instructions`, `metadata`. Includes `to_dict()`/`from_dict()`.

2. **`SkillRegistry`** (`tinycua_sdk/skills/registry.py`) — In-memory registry with `register()`, `get()`, `list_skills()`. Instances are independent (not a singleton).

3. **`Agent` class** (`tinycua_sdk/agent/agent.py`) — Accepts `skills` and `tools` in constructor. Has `add_skills()` and `add_tools()` methods. Delegates to `BaseLoop.run()`.

4. **`AgentConfig`** (`tinycua_sdk/agent/config.py`) — Stores `skills: list[Skill]`. Serializes/deserializes skills in `to_config()`/`from_config()`.

5. **`BaseLoop._build_system_message()`** (`tinycua_sdk/agent/loop.py:22-31`) — Concatenates agent instructions with skill blocks in `[skill_name]\n{instructions}` format, separated by blank lines. Already supports override_instructions.

6. **Unit tests covering:**
   - Skill construction, serialization, registry (`test_skills.py`, `test_skills_registry.py`)
   - Agent construction with skills, add_skills, add_tools (`test_agent.py`)
   - Loop `_build_system_message` with skills (`test_loop.py`)
   - Agent.run() flow (`test_agent_run.py`)

### What Needs to Be Done

The spec's success criteria (S-4.1 through S-4.5) require two integration test files that do not yet exist:

| File | Covers | Targets |
|------|--------|---------|
| `tests/integration/goals/test_int_04_agent_with_skills.py` | Single skill, multiple skills, dynamic add_skills | 4.1, 4.2, 4.3 |
| `tests/integration/goals/test_int_05_agent_with_tools_and_skills.py` | Combined tools + skills | 4.4 |

No source code changes are needed — the implementation is complete.

## Steps

### Step 1: Create `test_int_04_agent_with_skills.py`

Three test methods covering:

- **test_int_01_single_skill** — Agent with one skill; verify `_build_system_message` includes `[skill_name]` and skill instructions; verify `run()` returns a response.
- **test_int_02_multiple_skills** — Agent with two skills; verify both skill blocks appear in system message in registration order; verify `run()` returns a response.
- **test_int_03_dynamic_add_skills** — Agent created without skills; `add_skills()` called after construction; verify skill is included on next `run()`.

### Step 2: Create `test_int_05_agent_with_tools_and_skills.py`

One test method:

- **test_int_01_combined_tools_and_skills** — Agent constructed with both `tools` and `skills` and `instructions`; verify system message contains all three (instructions + skill blocks); verify `run()` triggers tool call and returns final response.

### Step 3: Verify

- Run all unit tests: `uv run pytest tests/unit/ -v`
- Run all integration tests: `uv run pytest tests/integration/ -v`
- Verify the two new integration test files pass.

## Success Criteria (from spec)

- [ ] S-4.1: Skill Instructions in System Prompt — new test file verifies `[skill_name]\n{instructions}` appears in system message
- [ ] S-4.2: Multiple Skills — new test file verifies both skills appear in registration order
- [ ] S-4.3: Dynamic add_skills — new test file verifies skills added post-construction work
- [ ] S-4.4: Combined Tools + Skills — new test file verifies agent with both works
- [ ] S-4.5: Integration Tests Pass — `pytest -v` shows 2 passed, 0 failed for the two new test files
