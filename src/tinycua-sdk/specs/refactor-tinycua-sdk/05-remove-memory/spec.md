# Stage 05 — Remove Memory

## Objective

Delete the entire `memory/` package. Memory management is a consumer concern.

## Files to Delete

| File | Reason |
|------|--------|
| `memory/__init__.py` | Package init |
| `memory/short_term.py` | ShortTermMemory — stateful |
| `memory/long_term.py` | LongTermMemory — stateful |
| `memory/plugin.py` | Memory plugin — stateful |
| `memory/compression.py` | Context compression — consumer concern |
| `memory/cache.py` | Memory cache — stateful |

## Code Changes

### Remove Memory References from Agent

In `agent/agent.py`, `agent/executor.py`, `agent/definition.py`:
- Remove `short_term_memory` parameter from `__init__`
- Remove `long_term_memory` parameter from `__init__`
- Remove any memory-related imports
- Agent loop should not fetch or store memory

### Remove Memory References from Config

In `agent/config.py`:
- Remove `short_term_memory` and `long_term_memory` from `AgentConfig`

### Remove Memory References from Modeling

`modeling/user.py` references `LongTermMemory`. This file will be deleted in Stage 06, but ensure no lingering imports remain elsewhere.

## Acceptance Criteria

- [ ] `memory/` directory does not exist.
- [ ] `Agent` does not reference memory in any way.
- [ ] `AgentConfig` does not reference memory.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02, Stage 03, Stage 04
