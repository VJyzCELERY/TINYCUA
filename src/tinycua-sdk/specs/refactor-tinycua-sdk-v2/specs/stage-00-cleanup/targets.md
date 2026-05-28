# Stage 0: Scorched-Earth Cleanup — Targets

## Purpose
Verify that cleanup is complete by confirming the SDK imports cleanly and deleted modules are truly gone.

---

### Target 0.1: Import Sanity

**File:** `targets/01_import_sanity.py`

```python
"""Target 0.1: Verify SDK imports cleanly after cleanup."""

from tinycua_sdk import Agent, LanguageModel, Tool, tool, Skill, SkillRegistry, BaseLoop, ApprovalWorkflow

print("PASS")
```

**Expected Output:** `targets/01_import_sanity_expected-output.txt` → `PASS`

---

### Target 0.2: Deleted Modules Raise ImportError

**File:** `targets/02_deleted_modules_raise.py`

```python
"""Target 0.2: Verify deleted modules cannot be imported."""

import subprocess
import sys

deleted_modules = [
    "tinycua_sdk.agent.backend_kind",
    "tinycua_sdk.tools.mcp",
    "tinycua_sdk.events.something",
    "tinycua_sdk.utils.helpers",
]

for mod in deleted_modules:
    result = subprocess.run(
        [sys.executable, "-c", f"import {mod}"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, f"{mod} should not be importable"
    assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr

print("PASS")
```

**Expected Output:** `targets/02_deleted_modules_raise_expected-output.txt` → `PASS`

---

### Target 0.3: No NotImplementedError at Import Time

**File:** `targets/03_no_stubs_at_import.py`

```python
"""Target 0.3: Verify no NotImplementedError is raised during import."""

import tinycua_sdk  # noqa: F401
print("PASS")
```

**Expected Output:** `targets/03_no_stubs_at_import_expected-output.txt` → `PASS`
