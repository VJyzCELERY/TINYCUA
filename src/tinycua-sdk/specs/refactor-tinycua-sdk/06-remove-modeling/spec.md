# Stage 06 — Remove Modeling

## Objective

Delete the entire `modeling/` package. User profiling and personality analysis are consumer concerns.

## Files to Delete

| File | Reason |
|------|--------|
| `modeling/__init__.py` | Package init |
| `modeling/user.py` | UserModel, UserPreference, UserGoal |
| `modeling/profiler.py` | CommunicationProfiler |
| `modeling/personality.py` | Personality |

## Code Changes

### Remove Modeling References

Search for imports from `tinycua_sdk.modeling` across the codebase:
```bash
rg "from tinycua_sdk.modeling" src/
rg "import tinycua_sdk.modeling" src/
```

## Acceptance Criteria

- [ ] `modeling/` directory does not exist.
- [ ] No imports from `tinycua_sdk.modeling` remain in the codebase.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02
