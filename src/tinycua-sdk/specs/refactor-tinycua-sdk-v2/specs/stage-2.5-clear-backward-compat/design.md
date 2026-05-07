# Stage 2.5: Clear Backward Compatibility — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-2.5-clear-backward-compat/spec.md`

## Rationale

The Stage 2 design included an `_OBSOLETE_PARAMS` frozenset and keyword-argument validation logic. This was a carryover from the assumption that consumers would attempt to pass v1-era parameters to the new constructor. However:

1. This project is a **clean-slate reset** — there is no existing consumer base to migrate.
2. The parameter names in `_OBSOLETE_PARAMS` (`session_id`, `sub_agents`, `backend`, etc.) refer to concepts that were already deleted in Stage 0.
3. Having dead validation code for deleted concepts sends the wrong signal — it implies the SDK *could* accept them, which contradicts the clean-break philosophy.
4. The Python runtime already provides clear error messages for unexpected keyword arguments — no custom validation needed.

## Changes to Stage 2

### 1. Remove `_OBSOLETE_PARAMS` from `agent/agent.py`

Delete the frozenset and the `**kwargs` validation loop in `Agent.__init__()`:

```python
# BEFORE:
_OBSOLETE_PARAMS = frozenset({
    "system_prompt", "model", "provider", "base_url", "api_key",
    "mode", "backend_url", "backend_api_key", "backend_headers",
    "agent_id", "planning_prompt", "short_term_memory", "long_term_memory",
    "session_id", "sub_agents", "max_depth", "strip_thinking", "backend",
})

class Agent(AgentExecutor):
    def __init__(self, ..., **kwargs):
        for key in kwargs:
            if key in _OBSOLETE_PARAMS:
                raise TypeError(
                    f"Agent() got an unexpected keyword argument '{key}'. "
                    f"This parameter has been removed in v2."
                )
        ...

# AFTER:
class Agent(AgentExecutor):
    def __init__(self, ...):
        ...
```

### 2. Remove "Obsolete Parameter" Error Scenario

| Scenario (BEFORE) | Behavior |
|---|---|
| Obsolete parameter passed | `TypeError` with message naming the param |

| Scenario (AFTER) | Behavior |
|---|---|
| *(removed — Python handles unknown kwargs natively)* | |

### 3. Remove Target 2.5

Deleted `targets/05_obsolete_params_rejected.py` and its expected output file. Renumbered targets 2.6 → 2.5, 2.7 → 2.6.

## Changes to Subsequent Stages

No runtime changes needed in stages 3–9. The only changes are narrative/documentation:

- **Stage 3:** Remove any remaining "v2" language that frames the work as a migration.
- **Stage 4–8:** No backward-compat references exist; no changes needed.
- **Stage 9:** Remove "obsolete param rejection" from the test strategy table.

## Design Decisions

### Why not keep the validation as defense-in-depth?
The validation was defensive but misleading. It communicated "these are old parameters we used to accept" which is the opposite of the clean-slate message. If a consumer passes a typo'd parameter name, Python's standard `TypeError: unexpected keyword argument` is sufficient.

### Why a separate stage (2.5) instead of just editing Stage 2?
This is a philosophical change that affects the framing of the entire project, not just one stage. Making it a separate, visible stage ensures:
1. The decision is documented and auditable.
2. All downstream stages are explicitly updated.
3. The ROADMAP shows a clear break between "building the constructor" and "clearing backward-compat framing."
