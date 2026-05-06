# Stage 2.5: Clear Backward Compatibility — Targets

## Purpose
Verify the Agent constructor is clean — no backward-compatibility validation, no obsolete parameter recognition.

---

### Target 2.5.1: Constructor Accepts Only Current Params

**File:** `targets/01_no_obsolete_params.py`

```python
"""Target 2.5.1: Verify Agent constructor has no backward-compat validation."""

from tinycua_sdk import Agent

# These should cause a normal TypeError (not a custom message about being obsolete)
obsolete_names = [
    "system_prompt", "model", "provider", "base_url", "api_key",
    "mode", "backend_url", "backend_api_key", "backend_headers",
    "agent_id", "planning_prompt", "short_term_memory", "long_term_memory",
    "session_id", "sub_agents", "max_depth", "strip_thinking", "backend",
]

for param in obsolete_names:
    try:
        Agent(**{param: "test"})
        assert False, f"{param} should raise TypeError"
    except TypeError:
        pass  # Standard Python behavior — no custom message

print("PASS")
```

**Expected Output:** `targets/01_no_obsolete_params_expected-output.txt` → `PASS`
