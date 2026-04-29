# Tasks: Remove CLI & Clients

Implementation tasks for deleting the `cli/` and `clients/` packages and cleaning up all dependent code. Check off items as completed.

## Deletion Phase

- [ ] Delete `cli/__init__.py` <!-- id: 0 -->
- [ ] Delete `cli/main.py` <!-- id: 1 -->
- [ ] Delete `cli/repl.py` <!-- id: 2 -->
- [ ] Delete `cli/agent_commands.py` <!-- id: 3 -->
- [ ] Delete `clients/__init__.py` <!-- id: 4 -->
- [ ] Delete `clients/backend.py` <!-- id: 5 -->
- [ ] Delete `clients/client.py` <!-- id: 6 -->
- [ ] Delete `clients/protocol.py` <!-- id: 7 -->
- [ ] Delete `clients/agent_client.py` <!-- id: 8 -->
- [ ] Remove `cli/` directory if empty <!-- id: 9 -->
- [ ] Remove `clients/` directory if empty <!-- id: 10 -->

## Cleanup Phase

- [ ] Remove `[project.scripts]` entry for `tinycua` from `pyproject.toml` <!-- id: 11 -->
- [ ] Remove `BackendClient`/`ResponsesClient` imports from `agent/executor.py` <!-- id: 12 -->
- [ ] Remove `_client`, `_get_client()`, `_run_deployed()`, `_run_guest()` from `agent/executor.py` <!-- id: 13 -->
- [ ] Simplify `Agent.run()` in `agent/executor.py` to local execution only <!-- id: 14 -->
- [ ] Remove `deploy()`, `delete()`, `set_guest_mode()`, `load_agent()` from `agent/agent.py` <!-- id: 15 -->

## Verification Phase

- [ ] Run `grep -r "from tinycua_sdk.cli"` and confirm zero matches <!-- id: 16 -->
- [ ] Run `grep -r "from tinycua_sdk.clients"` and confirm zero matches <!-- id: 17 -->
- [ ] Confirm `pyproject.toml` has no `[project.scripts]` section <!-- id: 18 -->
- [ ] Run `pytest` and confirm all remaining tests pass <!-- id: 19 -->

## Documentation Phase

- [ ] Update `CHANGELOG.md` or release notes if applicable <!-- id: 20 -->
- [ ] Update README to remove CLI/client references if present <!-- id: 21 -->

## Review and Merge

- [ ] Review all deletions and modifications for correctness <!-- id: 22 -->
- [ ] Merge to main branch <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-04-29*
