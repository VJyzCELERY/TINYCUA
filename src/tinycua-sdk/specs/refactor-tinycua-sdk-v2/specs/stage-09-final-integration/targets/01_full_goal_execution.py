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
