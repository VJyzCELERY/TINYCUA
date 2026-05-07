# Stage 03 — Remove Session & Utils

## Objective

Delete the `session/` package and `utils/session.py`. Session management is a consumer concern.

## Files to Delete

| File | Reason |
|------|--------|
| `session/session.py` | File-based session manager — stateful |
| `session/__init__.py` | Package init |
| `utils/session.py` | Session utility wrappers — stateful |

## Code Changes

### Remove Session References from Agent

In `agent/agent.py`, `agent/executor.py`, `agent/definition.py`:
- Remove `session_id` parameter from `__init__`
- Remove `messages` list from internal state (AgentExecutor stores message history)
- `Agent.run()` should accept `messages` as an optional parameter

### Remove Session References from Config

In `agent/config.py`:
- Remove `session_id` from `AgentConfig`

## Acceptance Criteria

- [ ] `session/` directory does not exist.
- [ ] `utils/session.py` does not exist.
- [ ] `Agent` does not reference `session_id` or session imports.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02
