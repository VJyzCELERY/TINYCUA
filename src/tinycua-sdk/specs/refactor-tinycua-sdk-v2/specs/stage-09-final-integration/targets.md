# Stage 9: Final Integration & Polish — Targets

## Purpose
Verify the entire SDK works end-to-end. All 16 goal scripts should be runnable.

---

### Target 9.1: Full Goal Script Execution

**File:** `targets/01_full_goal_execution.py`

```python
"""Target 9.1: Verify all 16 goal scripts can be executed without errors."""

import subprocess
import sys
from pathlib import Path

GOALS_DIR = Path(__file__).parent.parent / "goals"

# Collect all .py files from goals directories
goal_files = sorted(GOALS_DIR.rglob("*.py"))
# Exclude __init__.py and example sub-files that aren't standalone scripts
goal_files = [f for f in goal_files if f.name.startswith("0") or f.name.startswith("1")]

print(f"Found {len(goal_files)} goal files to test:")
for gf in goal_files:
    print(f"  - {gf.relative_to(GOALS_DIR.parent)}")

# Run each goal script (they may fail at LLM call time if no server is running)
# We only check that they don't raise ImportError, AttributeError, or NotImplementedError
errors = []
for gf in goal_files:
    result = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, '{Path(__file__).parent.parent.parent}'); exec(open('{gf}').read())"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        # Check for SDK-level errors (not LLM connection errors)
        stderr = result.stderr.lower()
        if "importerror" in stderr or "attributeerror" in stderr or "notimplementederror" in stderr:
            errors.append(f"{gf.name}: {result.stderr[:200]}")

if errors:
    print("\nSDK-level errors found:")
    for e in errors:
        print(f"  - {e}")
else:
    print("PASS — no SDK-level errors in any goal script")
```

**Expected Output:** `targets/01_full_goal_execution_expected-output.txt` → `PASS — no SDK-level errors in any goal script` (must not raise)

---

### Target 9.2: Public API is Clean

**File:** `targets/02_public_api_clean.py`

```python
"""Target 9.2: Verify from tinycua_sdk import * only exports v2 public API."""

from tinycua_sdk import *

expected = {
    "Agent",
    "LanguageModel",
    "Tool",
    "tool",
    "Skill",
    "SkillRegistry",
    "BaseLoop",
    "ApprovalWorkflow",
}

imported = {x for x in dir() if not x.startswith("_")}
assert imported == expected, f"Mismatch: extra={imported - expected}, missing={expected - imported}"
print("PASS")
```

**Expected Output:** `targets/02_public_api_clean_expected-output.txt` → `PASS`

---

### Target 9.3: No NotImplementedError in Production Code

**File:** `targets/03_no_notimplementederror.py`

```python
"""Target 9.3: Verify no production code raises NotImplementedError."""

import ast
from pathlib import Path

SDK_DIR = Path(__file__).parent.parent.parent / "tinycua_sdk"

not_implemented_files = []
for py_file in SDK_DIR.rglob("*.py"):
    if "__pycache__" in str(py_file):
        continue
    content = py_file.read_text()
    if "raise NotImplementedError" in content:
        not_implemented_files.append(str(py_file.relative_to(SDK_DIR.parent)))

if not_implemented_files:
    print("Found NotImplementedError in:")
    for f in not_implemented_files:
        print(f"  - {f}")
else:
    print("PASS — no NotImplementedError stubs found")
```

**Expected Output:** `targets/03_no_notimplementederror_expected-output.txt` → `PASS — no NotImplementedError stubs found` (must not raise)

---

### Target 9.4: Ruff Linting Passes

**File:** `targets/04_ruff_passes.py`

```python
"""Target 9.4: Verify ruff check passes on the SDK."""

import subprocess
from pathlib import Path

SDK_DIR = Path(__file__).parent.parent.parent

result = subprocess.run(
    ["ruff", "check", str(SDK_DIR / "tinycua_sdk")],
    capture_output=True, text=True, cwd=SDK_DIR,
)

if result.returncode != 0:
    print(f"FAIL:\n{result.stdout}\n{result.stderr}")
else:
    print("PASS — ruff check passed")
```

**Expected Output:** `targets/04_ruff_passes_expected-output.txt` → `PASS — ruff check passed` (must not raise)

---

### Target 9.5: Import Sanity Final Check

**File:** `targets/05_import_sanity_final.py`

```python
"""Target 9.5: Final import sanity check."""

import tinycua_sdk
from tinycua_sdk import Agent, LanguageModel, Tool, tool, Skill, SkillRegistry, BaseLoop, ApprovalWorkflow

print("PASS")
```

**Expected Output:** `targets/05_import_sanity_final_expected-output.txt` → `PASS`
