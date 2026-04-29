# Review Report: Stage 05 — Remove Memory

**Directory Reviewed:** `src/tinycua-sdk/specs/refactor-tinycua-sdk/05-remove-memory/`
**Review Date:** 2026-04-29
**Review Type:** code
**Reviewer:** OpenCode Agent

---

## Summary

The `memory/` package and associated memory tool files have been successfully deleted from `tinycua_sdk/`. `Agent`, `AgentExecutor`, `AgentDefinition`, and `AgentConfig` no longer accept or reference memory parameters. However, `SDKConfig` still retains a `memory: MemoryConfig` field, causing one memory-related test to fail. Additionally, an example script still imports from the deleted memory modules.

- **Total Findings**: 5
- **Critical Issues**: 1
- **Major Issues**: 1
- **Minor Issues**: 2
- **Suggestions**: 1

---

## Findings

### MEM-001 — [CRITICAL] — Example script imports deleted memory modules

**Status**: OPEN

**Severity**: CRITICAL

`examples/03_memory_and_session.py` imports from memory modules that no longer exist, making the example script completely broken.

**Location**: `src/tinycua-sdk/examples/03_memory_and_session.py:20`, `src/tinycua-sdk/examples/03_memory_and_session.py:28`

**Affected Code**:
```python
from tinycua.agent.tools.memory_tools import (
    remember,
    recall,
    forget,
    list_memory,
    set_memory_backend,
    reset_memory_backend,
)
from tinycua_sdk.tools.memory import LocalMemoryBackend
```

**How to Test/Validate**:
```bash
grep -r "tools\.memory\|memory_tools\|from tinycua.*memory" src/tinycua-sdk/tinycua_sdk/ src/tinycua-sdk/examples/ --include="*.py"
```

**Suggested Fix**:
Delete `examples/03_memory_and_session.py` entirely (it was likely meant to be removed in Stage 01 or Stage 05).

**Priority Rank**: 10

---

### MEM-002 — [MAJOR] — SDKConfig still retains MemoryConfig field

**Status**: OPEN

**Severity**: MAJOR

`core/config.py` defines `MemoryConfig` and `SDKConfig` still has a `memory: MemoryConfig` field. The unit test `test_sdk_config_no_memory_field` explicitly asserts that `SDKConfig` should not have a `memory` attribute, and it fails.

**Location**: `src/tinycua-sdk/tinycua_sdk/core/config.py:27-34`, `src/tinycua-sdk/tinycua_sdk/core/config.py:66`

**Affected Code**:
```python
class MemoryConfig(BaseModel):
    """Configuration for memory/storage."""
    model_config = ConfigDict(frozen=True)
    database_url: str = "sqlite:///./tinycua.db"
    embedding_dimension: int = 1536

class SDKConfig(BaseModel):
    ...
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
```

**How to Test/Validate**:
```bash
cd src/tinycua-sdk && python -m pytest tests/unit/test_config.py::TestSDKConfig::test_sdk_config_no_memory_field -v
```

**Suggested Fix**:
1. Remove `MemoryConfig` class from `core/config.py`
2. Remove `memory: MemoryConfig` field from `SDKConfig`
3. Remove the `database_url` env-var loading block in `SDKConfig.from_env()`
4. Remove `MemoryConfig` from `core/__init__.py` exports

**Priority Rank**: 8

---

### MEM-003 — [MINOR] — core/__init__.py still exports MemoryConfig

**Status**: OPEN

**Severity**: MINOR

`core/__init__.py` still exports `MemoryConfig`, which should be removed alongside the class itself.

**Location**: `src/tinycua-sdk/tinycua_sdk/core/__init__.py:3`, `src/tinycua-sdk/tinycua_sdk/core/__init__.py:8`

**Affected Code**:
```python
from tinycua_sdk.core.config import LLMConfig, MemoryConfig, SDKConfig
__all__ = [
    ...
    "MemoryConfig",
    ...
]
```

**How to Test/Validate**:
```bash
grep -n "MemoryConfig" src/tinycua-sdk/tinycua_sdk/core/__init__.py
```

**Suggested Fix**:
Remove `MemoryConfig` from the import and `__all__` list.

**Priority Rank**: 5

---

### MEM-004 — [MINOR] — Docstring mentions of "memory" in modeling files

**Status**: OPEN

**Severity**: MINOR

`modeling/personality.py` and `modeling/user.py` contain docstrings with phrases like "Load personality from memory" and "Save user model to memory". These are harmless comments with no actual memory imports or logic. `modeling/user.py` is scheduled for deletion in Stage 06.

**Location**:
- `src/tinycua-sdk/tinycua_sdk/modeling/personality.py:51`, `src/tinycua-sdk/tinycua_sdk/modeling/personality.py:55`
- `src/tinycua-sdk/tinycua_sdk/modeling/user.py:77`, `src/tinycua-sdk/tinycua_sdk/modeling/user.py:81`

**How to Test/Validate**:
```bash
grep -n "memory" src/tinycua-sdk/tinycua_sdk/modeling/personality.py src/tinycua-sdk/tinycua_sdk/modeling/user.py
```

**Suggested Fix**:
Update docstrings to remove the word "memory" (e.g., "Load personality from storage" or just "Load personality"). Low priority since these are just docstrings.

**Priority Rank**: 2

---

### MEM-005 — [SUGGESTION] — skills/improver.py uses `memory` as generic parameter name

**Status**: OPEN

**Severity**: SUGGESTION

`skills/improver.py` has a method `persist_improvements(self, memory: Any)` where `memory` is a generic storage parameter. This is not an import of the deleted memory system, but the parameter name could be confusing. Consider renaming to `storage` or `backend`.

**Location**: `src/tinycua-sdk/tinycua_sdk/skills/improver.py:176`

**How to Test/Validate**:
```bash
grep -n "memory" src/tinycua-sdk/tinycua_sdk/skills/improver.py
```

**Suggested Fix**:
Rename parameter `memory` to `storage` or `backend` for clarity.

**Priority Rank**: 1

---

## Positive Findings

These aspects of the codebase are working well:

- `memory/` directory completely removed from `tinycua_sdk`
- `tools/memory.py` deleted
- `tools/memory_tools.py` deleted
- `storage/snapshot.py` deleted
- `Agent` class has no `short_term_memory`, `long_term_memory`, or `planning_prompt` parameters
- `AgentConfig` has no memory fields
- `AgentExecutor` and `AgentDefinition` have no memory parameters
- No imports of memory modules in SDK source code
- Tests verify Agent rejects obsolete memory parameters (3 passed)
- Test verifies AgentConfig has no memory fields (1 passed)

---

## Action Items

| Item | Type | Priority | Owner |
|------|------|----------|-------|
| MEM-001 | Delete | P0 | — |
| MEM-002 | Fix | P1 | — |
| MEM-003 | Fix | P2 | — |
| MEM-004 | Fix | P3 | — |
| MEM-005 | Refactor | P3 | — |

---

## Validation Log

### Commands Executed

#### 1. Verify `memory/` directory deletion
```bash
$ find src/tinycua-sdk/tinycua_sdk -type d -name "memory"
(no output)
```
**Result:** ✅ CONFIRMED — `memory/` directory does not exist in `tinycua_sdk`.

---

#### 2. Verify `tools/memory.py` and `tools/memory_tools.py` deletion
```bash
$ find src/tinycua-sdk/tinycua_sdk -name "memory*.py"
(no output)
```
**Result:** ✅ CONFIRMED — No `memory*.py` files exist in `tinycua_sdk`.

---

#### 3. Verify `storage/snapshot.py` deletion
```bash
$ find src/tinycua-sdk/tinycua_sdk -name "snapshot.py"
(no output)
```
**Result:** ✅ CONFIRMED — `snapshot.py` does not exist.

---

#### 4. Verify Agent has no memory parameters
```bash
$ grep -r "short_term_memory\|long_term_memory\|planning_prompt" src/tinycua-sdk/tinycua_sdk/agent/ --include="*.py"
(no output)
```
**Result:** ✅ CONFIRMED — `Agent`, `AgentExecutor`, `AgentDefinition`, and `AgentConfig` have no memory parameters.

---

#### 5. Verify no memory imports in SDK source
```bash
$ grep -r "tinycua_sdk\.memory\|from .*memory import\|import .*memory\b" src/tinycua-sdk/tinycua_sdk/ --include="*.py"
(no output)
```
**Result:** ✅ CONFIRMED — No imports of memory modules in SDK source code.

---

#### 6. Run memory-specific tests
```bash
$ cd src/tinycua-sdk && python -m pytest tests/unit/test_agent.py -k "memory or planning" -v
============================= test session starts ==============================
...
tests/unit/test_agent.py::TestAgentConstruction::test_agent_rejects_short_term_memory PASSED
tests/unit/test_agent.py::TestAgentConstruction::test_agent_rejects_long_term_memory PASSED
tests/unit/test_agent.py::TestAgentConstruction::test_agent_rejects_planning_prompt PASSED
======================= 3 passed, 24 deselected in 0.06s =======================
```
**Result:** ✅ CONFIRMED — All 3 memory-rejection tests pass.

---

#### 7. Run AgentConfig memory field test
```bash
$ cd src/tinycua-sdk && python -m pytest tests/unit/test_config.py::TestAgentConfig::test_agent_config_no_memory_fields -v
PASSED
```
**Result:** ✅ CONFIRMED — AgentConfig has no memory fields.

---

#### 8. Run SDKConfig memory field test
```bash
$ cd src/tinycua-sdk && python -m pytest tests/unit/test_config.py::TestSDKConfig::test_sdk_config_no_memory_field -v
FAILED tests/unit/test_config.py::TestSDKConfig::test_sdk_config_no_memory_field
AssertionError: assert not True
 +  where True = hasattr(SDKConfig(...), 'memory')
```
**Result:** ❌ FAILED — `SDKConfig` still has `memory` field.

---

#### 9. Run full test suite
```bash
$ cd src/tinycua-sdk && python -m pytest tests/ -x -q
.....................................................................F
=================================== FAILURES ===================================
__________________ TestToolSchema.test_tool_generates_schema ___________________
...
E       AttributeError: 'Tool' object has no attribute 'schema'
...
1 failed, 69 passed, 1 warning in 18.26s
```
**Result:** ⚠️ PARTIAL — 69 passed, 1 failed (unrelated tool schema issue).

---

## Acceptance Criteria Revisited

| Criterion | Required | Actual | Pass? |
|-----------|----------|--------|-------|
| `memory/` directory does not exist | Yes | ✅ Deleted | **YES** |
| `Agent` does not reference memory | Yes | ✅ No memory params/imports | **YES** |
| `AgentConfig` does not reference memory | Yes | ✅ No memory fields | **YES** |
| `tools/memory.py` deleted | Yes | ✅ Deleted | **YES** |
| `tools/memory_tools.py` deleted | Yes | ✅ Deleted | **YES** |
| `storage/snapshot.py` deleted | Yes | ✅ Deleted | **YES** |
| `pytest` still passes for remaining tests | Yes | ⚠️ 69 passed, 1 failed (unrelated), plus `test_sdk_config_no_memory_field` fails | **NO** |

**Stage 05 memory removal is substantially complete.** The remaining `MemoryConfig` in `SDKConfig` and the broken example script are the only outstanding issues.

---

*Generated by opencode /review-project command*
