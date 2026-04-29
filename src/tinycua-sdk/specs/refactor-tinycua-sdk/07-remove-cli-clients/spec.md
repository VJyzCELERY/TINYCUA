# Stage 07 — Remove CLI & Clients

## Objective

Delete the `cli/` and `clients/` packages. Command-line interfaces and HTTP clients are consumer concerns.

## Files to Delete

### CLI

| File | Reason |
|------|--------|
| `cli/__init__.py` | Package init |
| `cli/main.py` | CLI entry point |
| `cli/repl.py` | REPL implementation |
| `cli/agent_commands.py` | Agent CLI commands |

### Clients

| File | Reason |
|------|--------|
| `clients/__init__.py` | Package init |
| `clients/backend.py` | BackendClient — HTTP client |
| `clients/client.py` | ResponsesClient — HTTP client |
| `clients/protocol.py` | Protocol definitions |
| `clients/agent_client.py` | AgentClient — HTTP client |

## Code Changes

### Remove CLI Entry Point

In `pyproject.toml`:
- Remove `console_scripts` entry point for `tinycua` CLI.

### Remove Client References from Agent

In `agent/executor.py`:
- Remove `_client`, `_get_client()`, `_run_deployed()`, `_run_guest()` methods.
- Remove `BackendClient` import.
- `Agent.run()` should only handle local execution. Remote execution is a consumer concern.

### Remove Deploy/Delete Methods from Agent

In `agent/agent.py`:
- Remove `deploy()`, `delete()`, `set_guest_mode()`, `load_agent()` class methods.
- These depend on `BackendClient` which is deleted.

## Acceptance Criteria

- [ ] `cli/` directory does not exist.
- [ ] `clients/` directory does not exist.
- [ ] `pyproject.toml` does not contain CLI entry point.
- [ ] `Agent` does not reference clients or remote execution.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02
