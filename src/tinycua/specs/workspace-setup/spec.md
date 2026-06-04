# Feature Specification: Workspace Setup

**Status**: Draft
**Created**: 2026-06-05
**Last Updated**: 2026-06-05
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Establish a verified, reproducible workspace for the TINYCUA prototype so that dependency management works, benchmark artifacts are excluded from version control, documentation scaffolding exists, and a no-op CLI entry point can be invoked via `uv run`.
- **Gaps**: The workspace currently lacks a verified `uv run` entry point, has no `.gitignore` rules for WildClawBench benchmark artifacts, and has no `docs/prototype/` directory for prototype documentation.
- **Non-Goals**: This spec does NOT cover implementing any actual CLI functionality beyond a no-op entry point. It does NOT cover WildClawBench benchmark integration itself. It does NOT cover subprojects other than `tinycua`.
- **Constraints**: Must honour the existing project structure (`src/tinycua/` subproject layout). Must use `uv` for all dependency management. Must not break existing Makefile targets or subproject relationships.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer clones the repository, runs `uv run tinycua` from `src/tinycua/`, and the CLI exits cleanly with a success message — confirming the workspace is functional and the entry point is wired correctly.

### Acceptance Scenarios

1. **Given** a fresh clone, **When** the developer runs `cd src/tinycua && uv sync`, **Then** dependencies install without error and a `.venv` is created.
2. **Given** a synced workspace, **When** the developer runs `uv run tinycua`, **Then** the CLI prints a confirmation message and exits with code 0.
3. **Given** the workspace, **When** WildClawBench artifacts (e.g., `benchmark_results/`, `*.benchmark.json`) are produced, **Then** they are excluded from `git status` via `.gitignore`.
4. **Given** the workspace, **When** the developer inspects `docs/prototype/`, **Then** a `README.md` exists explaining the prototype documentation structure.
5. **Given** the workspace, **When** the developer runs `make lint` from the project root, **Then** linting passes without errors on the new entry point code.

### Edge Cases

- What happens if `uv` is not installed? The `uv run` command fails with a clear "command not found" error — no special handling required.
- What happens if the developer runs `uv run tinycua` from outside `src/tinycua/`? The root `pyproject.toml` does not define a `tinycua` script, so `uv` falls back to the root project (no-op) or errors — acceptable for this milestone.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a `uv run tinycua` entry point that executes a no-op CLI (prints message, exits 0).
- **FR-002**: System MUST use `uv` for dependency management with `pyproject.toml` as the single source of truth.
- **FR-003**: System MUST exclude WildClawBench benchmark artifacts from version control via `.gitignore`.
- **FR-004**: System MUST provide a `docs/prototype/` directory with a `README.md` explaining the prototype documentation layout.
- **FR-005**: System MUST maintain the existing subproject structure (`src/tinycua/` with its own `pyproject.toml`, `Makefile`, `tests/`, etc.).
- **FR-006**: `uv run tinycua` MUST exit with code 0 and print a human-readable confirmation message.

### Key Entities

- **Workspace**: The root repository directory containing `src/` subprojects, root `pyproject.toml`, and agent/tooling configuration.
- **Entry Point**: A CLI script registered in `pyproject.toml` `[project.scripts]` that can be invoked via `uv run`.

---

## Success Criteria _(mandatory)_

- [ ] **uv sync works**: `cd src/tinycua && uv sync` completes without error
- [ ] **CLI entry point works**: `uv run tinycua` prints a message and exits with code 0
- [ ] **Gitignore excludes artifacts**: WildClawBench artifacts are not tracked by git
- [ ] **Prototype docs exist**: `docs/prototype/README.md` exists and describes the structure
- [ ] **Lint passes**: `make lint` from `src/tinycua/` passes without errors

---

## Testing Plan _(mandatory)_

### Unit Tests

- Not applicable for this milestone — workspace setup is validated via manual/acceptance tests.

### Integration Tests

- Not applicable for this milestone.

### Manual Tests _(if applicable)_

- Run `cd src/tinycua && uv sync` and verify no errors
- Run `uv run tinycua` and verify output and exit code
- Run `git status` after creating WildClawBench artifacts and verify they are ignored
- Inspect `docs/prototype/README.md` and verify content

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| pyproject.toml entry point | TODO | |
| .gitignore rules | TODO | |
| docs/prototype/ scaffolding | TODO | |
| uv run verification | TODO | |

---

## Open Questions _(optional)_

None.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
