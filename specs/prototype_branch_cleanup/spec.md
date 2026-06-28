# Feature Specification: Prototype Branch Cleanup

**Status**: Draft
**Created**: 2026-06-15
**Last Updated**: 2026-06-15
**Subproject(s) Affected**: tinycua (root repository)

---

## Problem Statement _(mandatory)_

- **Goals**: Reorganize misplaced files to follow project conventions, ensuring specs/designs live in `src/tinycua/specs/`, Docker artifacts move to `src/tinycua-benchmark/`, review artifacts are deleted, and root-level clutter is removed.
- **Gaps**: Multiple files are in incorrect locations:
  - Root-level spec/design/implementation-plan/task files for Milestone 5.6
  - Specs at root `specs/` that belong in `src/tinycua/specs/`
  - Docker files (Dockerfile, docker-compose.benchmark.yml, scripts/entrypoint.sh) at root belong in `src/tinycua-benchmark/`
  - Review artifact in `.reviews/` should be deleted
- **Non-Goals**: This spec does NOT cover:
  - Modifying file contents (only moving/deleting files)
  - Creating new features or functionality
  - Changing project architecture
  - Updating documentation content
- **Constraints**: Must preserve all file content during moves. Must not break existing references or imports. Must follow project directory conventions defined in AGENTS.md.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer clones the repository and expects a clean directory structure where:
- Specs and designs are in `src/tinycua/specs/`
- Root contains only project-level files (README, Makefile, pyproject.toml, etc.)
- Review artifacts are gitignored and not tracked
- Docker-related scripts are in appropriate locations

### Acceptance Scenarios

1. **Given** the repository root, **When** a developer lists files, **Then** only project-level files remain (no spec/design/implementation-plan/task files, no Docker files).
2. **Given** the `specs/` directory at root, **When** specs are inspected, **Then** all specs have been moved to `src/tinycua/specs/`.
3. **Given** Docker files at root, **When** they are inspected, **Then** they have been moved to `src/tinycua-benchmark/`.
4. **Given** `.reviews/` directory, **When** the directory is checked, **Then** it has been deleted.

### Edge Cases

- What happens if a file being moved is referenced by other files? References must be updated or the move must be documented.
- What happens if files have the same name at the destination? Files must be renamed or merged carefully.
- What happens if `.reviews/` contains important review history? Reviews should be preserved but gitignored.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST move root-level `spec.md`, `design.md`, `implementation-plan.md`, and `task.md` to appropriate locations under `src/tinycua/specs/`.
- **FR-002**: System MUST move all specs from root `specs/` directory to `src/tinycua/specs/`.
- **FR-003**: System MUST move `Dockerfile`, `docker-compose.benchmark.yml`, and `scripts/entrypoint.sh` to `src/tinycua-benchmark/`.
- **FR-004**: System MUST delete `.reviews/` directory.
- **FR-005**: System MUST preserve all file content during moves (no data loss).
- **FR-006**: System MUST update any broken references after file moves.
- **FR-007**: System MUST follow project conventions for directory structure.

### Key Entities

- **Spec Files**: Feature specifications that define requirements and acceptance criteria.
- **Design Files**: Technical design documents that describe implementation approaches.
- **Review Artifacts**: Review reports and findings that should be gitignored.
- **Root Directory**: Project root containing only top-level configuration and documentation.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Root directory clean**: No spec/design/implementation-plan/task files in root.
- [ ] **Specs relocated**: All specs from `specs/` moved to `src/tinycua/specs/`.
- [ ] **Docker files relocated**: Dockerfile, docker-compose.benchmark.yml, scripts/entrypoint.sh moved to `src/tinycua-benchmark/`.
- [ ] **Reviews deleted**: `.reviews/` directory is deleted.
- [ ] **No broken references**: All file moves preserve content and update references.
- [ ] **Project structure follows conventions**: Directory layout matches AGENTS.md guidelines.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Verify `.gitignore` contains `.reviews/` pattern
- Verify no spec/design files remain in root directory
- Verify all files from `specs/` are now in `src/tinycua/specs/`
- Verify all files from `src/tinycua/docs/design/` are now in `src/tinycua/specs/`

### Integration Tests

- Verify `git status` shows clean working tree after cleanup
- Verify all moved files are still readable and have correct content
- Verify no broken imports or references in codebase

### Manual Tests

- Visual inspection of directory structure
- Verify `git diff` shows only file moves, no content changes
- Verify all specs/designs are accessible at new locations

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Root file cleanup | DONE | Moved spec.md, design.md, implementation-plan.md, task.md |
| Specs relocation | DONE | Moved from root specs/ to src/tinycua/specs/ |
| Docker file relocation | TODO | Move Dockerfile, docker-compose.benchmark.yml, scripts/entrypoint.sh to src/tinycua-benchmark/ |
| Reviews deletion | TODO | Delete .reviews/ directory |
| Reference updates | TODO | Fix any broken references after moves |

---

## Open Questions _(optional)_

1. **What should the Docker subproject be named?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-15
   - **Status**: Decided
   - **Proposed Answer**: `src/tinycua-benchmark/` - contains all Docker-related files for benchmarking.

2. **Should the .reviews/ directory be deleted or just gitignored?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-15
   - **Status**: Decided
   - **Proposed Answer**: Deleted - review artifacts are temporary and should not be preserved.

---

## Review Checklist

- [x] No implementation details beyond file operations
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
