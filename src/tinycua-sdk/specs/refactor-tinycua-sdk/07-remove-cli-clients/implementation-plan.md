# Implementation: Remove CLI & Clients

Delete the `cli/` and `clients/` packages from the SDK, along with all dependent code in `pyproject.toml`, `agent/executor.py`, and `agent/agent.py`. CLI and HTTP client functionality are consumer concerns, not part of the core SDK library.

## Context

- **Spec Reference**: [spec.md](spec.md)
- **Design Reference**: [design.md](design.md)
- **Priority**: P1
- **Estimated Effort**: S

## Proposed Changes

### CLI Package Removal

#### [DELETE] `cli/__init__.py`

- **[Description of change]**: Delete the `cli/` package initializer.
- **[Rationale]**: The CLI is a standalone consumer application, not part of the SDK.

#### [DELETE] `cli/main.py`

- **[Description of change]**: Delete the CLI entry point module.
- **[Rationale]**: The CLI will be moved to a separate deliverable (`tinycua-cli`).

#### [DELETE] `cli/repl.py`

- **[Description of change]**: Delete the REPL implementation module.
- **[Rationale]**: Interactive REPL is a consumer concern.

#### [DELETE] `cli/agent_commands.py`

- **[Description of change]**: Delete the agent management CLI commands module.
- **[Rationale]**: Agent management commands are CLI-specific and not part of the SDK.

### Clients Package Removal

#### [DELETE] `clients/__init__.py`

- **[Description of change]**: Delete the `clients/` package initializer.
- **[Rationale]**: HTTP clients are consumer infrastructure, not SDK components.

#### [DELETE] `clients/backend.py`

- **[Description of change]**: Delete the `BackendClient` module.
- **[Rationale]**: Backend HTTP communication is a consumer concern.

#### [DELETE] `clients/client.py`

- **[Description of change]**: Delete the `ResponsesClient` module.
- **[Rationale]**: HTTP client implementation belongs in consumer code.

#### [DELETE] `clients/protocol.py`

- **[Description of change]**: Delete the protocol definitions module.
- **[Rationale]**: Protocol definitions are consumer-specific.

#### [DELETE] `clients/agent_client.py`

- **[Description of change]**: Delete the `AgentClient` module.
- **[Rationale]**: Agent HTTP client is a consumer concern.

### Build & Agent Code Cleanup

#### [MODIFY] `pyproject.toml`

- **[Description of change]**: Remove the `[project.scripts]` entry point for `tinycua` CLI.
- **[Rationale]**: No CLI is shipped with the SDK.

#### [MODIFY] `agent/executor.py`

- **[Description of change]**:
  - Remove `BackendClient` and `ResponsesClient` imports.
  - Remove `_client`, `_get_client()`, `_run_deployed()`, and `_run_guest()` methods.
  - Simplify `Agent.run()` to handle only local execution.
- **[Rationale]**: Remote execution is a consumer concern. The SDK only supports local agent execution.

#### [MODIFY] `agent/agent.py`

- **[Description of change]**:
  - Remove `deploy()`, `delete()`, `set_guest_mode()`, and `load_agent()` class methods.
- **[Rationale]**: These methods depend on `BackendClient`, which is being removed.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `cli/` | Remove | Entire CLI package deleted |
| `clients/` | Remove | Entire clients package deleted |
| `pyproject.toml` | Modify | Remove `[project.scripts]` entry |
| `agent/executor.py` | Modify | Remove remote execution paths |
| `agent/agent.py` | Modify | Remove deploy/delete/guest methods |

## Data Model Changes

None. No new types or interfaces are introduced; only deletion occurs.

## API Changes

### Removed Public API

| Item | Location | Reason |
|------|----------|--------|
| `Agent.deploy()` | `agent/agent.py` | Depends on deleted `BackendClient` |
| `Agent.delete()` | `agent/agent.py` | Depends on deleted `BackendClient` |
| `Agent.set_guest_mode()` | `agent/agent.py` | Depends on deleted `BackendClient` |
| `Agent.load_agent()` | `agent/agent.py` | Depends on deleted `BackendClient` |
| `Agent._run_deployed()` | `agent/executor.py` | Remote execution removed |
| `Agent._run_guest()` | `agent/executor.py` | Remote execution removed |
| `tinycua` CLI entry point | `pyproject.toml` | CLI is a separate deliverable |

## Verification Plan

### Automated Tests

- [ ] Run `pytest` for the remaining SDK code and confirm all tests pass.

### Manual Verification

- [ ] Verify `cli/` directory does not exist.
- [ ] Verify `clients/` directory does not exist.
- [ ] Verify `pyproject.toml` has no `[project.scripts]` entry.
- [ ] Verify no imports from `tinycua_sdk.cli` or `tinycua_sdk.clients` remain in the codebase.

### Performance Considerations

- [ ] Confirm test suite runs in the same time (or faster) after deletions.

## Rollout Strategy

1. **Phase 1** (Deletion): Delete `cli/` and `clients/` directories.
2. **Phase 2** (Cleanup): Remove CLI entry point from `pyproject.toml`, remote execution from `agent/executor.py`, and deploy/delete methods from `agent/agent.py`.
3. **Phase 3** (Verification): Run full test suite and grep for any remaining references.

## Dependencies

### External Dependencies

None.

### Internal Dependencies

- [ ] Depends on Stage 01 (tests already cleaned up)
- [ ] Depends on Stage 02 (core structure in place)
- [ ] Blocks: None (can proceed in parallel with Stages 03–06, 08)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hidden imports from `cli` or `clients` in remaining code | Medium | Grep for all references before and after deletion |
| Broken tests referencing removed modules | Medium | Run `pytest` after all changes |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
