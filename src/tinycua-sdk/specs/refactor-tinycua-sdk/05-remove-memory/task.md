# Tasks: Remove Memory

Implementation tasks for deleting the `memory/` package, `tools/memory.py`, and all memory references from the SDK. Check off items as completed.

## Implementation Phase

- [ ] Delete `tinycua_sdk/memory/__init__.py` <!-- id: 0 -->
- [ ] Delete `tinycua_sdk/memory/short_term.py` <!-- id: 1 -->
- [ ] Delete `tinycua_sdk/memory/long_term.py` <!-- id: 2 -->
- [ ] Delete `tinycua_sdk/memory/plugin.py` <!-- id: 3 -->
- [ ] Delete `tinycua_sdk/memory/compression.py` <!-- id: 4 -->
- [ ] Delete `tinycua_sdk/memory/cache.py` <!-- id: 5 -->
- [ ] Delete `tinycua_sdk/tools/memory.py` <!-- id: 6 -->
- [ ] Remove `planning_prompt`, `short_term_memory`, `long_term_memory` from `agent/agent.py` <!-- id: 7 -->
- [ ] Remove `planning_prompt` from `agent/executor.py` <!-- id: 8 -->
- [ ] Remove `planning_prompt` from `agent/definition.py` <!-- id: 9 -->
- [ ] Remove `planning_prompt` from `agent/config.py` <!-- id: 10 -->
- [ ] Remove `planning_prompt` from `runner/runner.py` <!-- id: 11 -->
- [ ] Remove `long_term_memory` from `modeling/user.py` <!-- id: 12 -->
- [ ] Remove `long_term_memory` from `modeling/personality.py` <!-- id: 13 -->
- [ ] Remove memory exports from `tools/__init__.py` <!-- id: 14 -->

## Testing Phase

- [ ] Run `make lint` and fix any import errors <!-- id: 15 -->
- [ ] Run `pytest` and fix or remove broken tests <!-- id: 16 -->
- [ ] Run `make test` until full suite passes <!-- id: 17 -->

## Verification Phase

- [ ] Confirm `memory/` directory does not exist <!-- id: 18 -->
- [ ] Confirm `tools/memory.py` does not exist <!-- id: 19 -->
- [ ] Confirm zero `from tinycua_sdk.memory` imports remain in codebase <!-- id: 20 -->
- [ ] Confirm zero `ShortTermMemory` / `LongTermMemory` references remain in `agent/` <!-- id: 21 -->
- [ ] Confirm zero `planning_prompt` references remain in `agent/` and `runner/` <!-- id: 22 -->

## Documentation Phase

- [ ] Update `CHANGELOG` or migration notes if applicable <!-- id: 23 -->

## Review and Merge

- [ ] Create pull request <!-- id: 24 -->
- [ ] Address review feedback <!-- id: 25 -->
- [ ] Merge to main branch <!-- id: 26 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
