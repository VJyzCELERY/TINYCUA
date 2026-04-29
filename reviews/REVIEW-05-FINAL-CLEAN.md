# Stage 05 Review — Remove Memory

**Reviewer:** Fresh independent review  
**Date:** 2026-04-29  
**Status:** ISSUES FOUND — Stage 05 is NOT approved

---

## Checks Performed

| Check | Result | Notes |
|-------|--------|-------|
| `memory/` directory deleted | ✅ PASS | No `memory/` package found in codebase |
| `tools/memory.py` deleted | ✅ PASS | File does not exist |
| `tools/memory_tools.py` deleted | ✅ PASS | File does not exist |
| `storage/snapshot.py` deleted | ✅ PASS | File does not exist |
| `Agent` has no memory params | ✅ PASS | `agent.py`, `executor.py`, `definition.py` are clean — no `short_term_memory`, `long_term_memory`, or `planning_prompt` params |
| `AgentConfig` has no memory fields | ✅ PASS | `agent/config.py` has no memory fields |
| `Agent.run()` does not fetch/store memory | ✅ PASS | `executor.py` `run()` delegates to loop without memory interaction |
| No imports from deleted memory package | ✅ PASS | No `from .*memory` or `import .*memory` found |
| Package imports cleanly | ✅ PASS | `import tinycua_sdk` succeeds |

---

## Issues Found

### Issue 1: Lingering memory reference in `SDKConfig.from_env()`

**File:** `src/tinycua-sdk/tinycua_sdk/core/config.py`  
**Line:** 137

```python
database_url = os.getenv("TINYCUA_DATABASE_URL")
if database_url is not None:
    data["memory"] = {"database_url": database_url}
```

**Problem:** `SDKConfig` class definition has no `memory` field, but `from_env()` still constructs a `memory` dict and passes it into the Pydantic model. While Pydantic ignores extra fields by default, this is dead code that directly references the removed memory subsystem. It should be deleted entirely.

**Fix:** Remove lines 135–137 from `core/config.py`.

---

### Issue 2: Broken example file referencing deleted memory tools

**File:** `src/tinycua-sdk/examples/13_memory_example.py`

**Problem:** This example file imports and uses tools that were deleted in Stage 05:

```python
from tinycua_sdk.tools import (
    remember,
    recall,
    forget,
    list_memory,
    clear_memory,
    set_memory_backend,
    LocalMemoryBackend,
)
```

These symbols no longer exist in `tinycua_sdk.tools`. Running this example would raise `ImportError`.

**Fix:** Delete `examples/13_memory_example.py` entirely, or rewrite it to show consumer-managed memory (injecting facts via system prompt / messages).

---

## Summary

Stage 05 **partially completed** the memory removal:

- Core SDK (`Agent`, `AgentConfig`, `AgentExecutor`, `AgentDefinition`) is fully clean of memory references.
- The `memory/` package and related tool files (`tools/memory.py`, `tools/memory_tools.py`, `storage/snapshot.py`) are all properly deleted.
- **Two residual references remain:**
  1. `SDKConfig.from_env()` still builds a `memory` config dict.
  2. `examples/13_memory_example.py` is a broken example importing deleted symbols.

**Action required:** Fix the two issues above, then re-run this review.
