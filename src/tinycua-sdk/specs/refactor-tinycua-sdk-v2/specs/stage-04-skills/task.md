# Stage 4: Skills & Composition — Tasks

## Task 1: Create `test_int_04_agent_with_skills.py`

**File**: `tests/integration/goals/test_int_04_agent_with_skills.py`

### Subtasks

1.1 ✅ **test_int_01_single_skill** — Agent with one skill; mock LLM; assert system message contains `[skill_name]` and skill text; assert `run()` returns a string.

1.2 ✅ **test_int_02_multiple_skills** — Agent with two skills; mock LLM; assert both `[s1]` + `[s2]` blocks appear in system message in order; assert `run()` returns a string.

1.3 ✅ **test_int_03_dynamic_add_skills** — Agent created without skills; `add_skills(skill)` after construction; mock LLM; assert skill block appears in system message; assert `run()` returns a string.

**Sources**: `targets/01_single_skill.py`, `targets/02_multiple_skills.py`, `targets/03_dynamic_add_skills.py`

---

## Task 2: Create `test_int_05_agent_with_tools_and_skills.py`

**File**: `tests/integration/goals/test_int_05_agent_with_tools_and_skills.py`

### Subtasks

2.1 ✅ **test_int_01_combined_tools_and_skills** — Agent with instructions, tools, AND skills; use mock LLM that returns a tool call then a response; assert system message has instructions + skill block; assert `run()` triggers tool then returns final answer.

**Sources**: `targets/04_combined_tools_and_skills.py`

---

## Task 3: Verify

- ✅ Run `uv run pytest tests/unit/ -v` — all 151 tests pass.
- ✅ Run `uv run pytest tests/integration/ -v` — all 74 tests pass (72 existing + 2 new).
- ✅ Confirm both new test files show `PASSED`.
