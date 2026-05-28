# Stage 2.5: Clear Backward Compatibility — Targets

## Purpose
Verify the Agent constructor is clean — no backward-compatibility validation, no obsolete parameter recognition.

---

### Target 2.5.1: Constructor Accepts Only Current Params

**File:** `targets/01_no_obsolete_params.py`

```python
"""Target 2.5.1: Verify Agent constructor has no backward-compat validation."""

from tinycua_sdk import Agent

# Any unknown keyword should produce Python's standard TypeError
# (no custom message about obsolete parameters)
try:
    Agent(unknown_param="test")
    assert False, "unknown param should raise TypeError"
except TypeError:
    pass  # Standard Python behavior — clean constructor

print("PASS")
```

**Expected Output:** `targets/01_no_obsolete_params_expected-output.txt` → `PASS`
