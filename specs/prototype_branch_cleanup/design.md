# Design Document: Prototype Branch Cleanup

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Created**: 2026-06-15
**Last Updated**: 2026-06-15

---

## Overview

This design describes the reorganization of misplaced files in the TINYCUA repository to follow project conventions. The cleanup moves specs to `src/tinycua/specs/`, Docker artifacts to `src/tinycua-benchmark/`, deletes review artifacts, and removes root-level clutter. The focus is on file organization without modifying content.

---

## Architecture

### Component Overview

```
Repository Root
├── src/tinycua/specs/ (destination for all specs)
│   ├── [existing specs]
│   └── [moved root specs]
├── src/tinycua-benchmark/ (destination for Docker files)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── scripts/entrypoint.sh
├── [cleaned root - only project-level files]
└── .reviews/ [deleted]
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| Root `spec.md` | Moved | To `src/tinycua/specs/5.6-full-benchmark-run/spec.md` |
| Root `design.md` | Moved | To `src/tinycua/specs/5.6-full-benchmark-run/design.md` |
| Root `implementation-plan.md` | Moved | To `src/tinycua/specs/5.6-full-benchmark-run/implementation-plan.md` |
| Root `task.md` | Moved | To `src/tinycua/specs/5.6-full-benchmark-run/task.md` |
| Root `specs/` | Moved | All subdirectories to `src/tinycua/specs/` |
| Root `Dockerfile` | Moved | To `src/tinycua-benchmark/Dockerfile` |
| Root `docker-compose.benchmark.yml` | Moved | To `src/tinycua-benchmark/docker-compose.yml` |
| Root `scripts/entrypoint.sh` | Moved | To `src/tinycua-benchmark/scripts/entrypoint.sh` |
| `.reviews/` | Deleted | Review artifacts removed |

---

## Data Model

### File Movement Map

```yaml
# Source → Destination mapping
root_files:
  spec.md: src/tinycua/specs/5.6-full-benchmark-run/spec.md
  design.md: src/tinycua/specs/5.6-full-benchmark-run/design.md
  implementation-plan.md: src/tinycua/specs/5.6-full-benchmark-run/implementation-plan.md
  task.md: src/tinycua/specs/5.6-full-benchmark-run/task.md

root_specs:
  tinycua-worker-digestion/: src/tinycua/specs/tinycua-worker-digestion/
  tinycua-nodequeue-suspend/: src/tinycua/specs/tinycua-nodequeue-suspend/
  tinycua-nodequeue-basic/: src/tinycua/specs/tinycua-nodequeue-basic/
  tinycua-node/: src/tinycua/specs/tinycua-node/
  wildclawbench-adapter/: src/tinycua/specs/wildclawbench-adapter/
  tinycua-finetune/: src/tinycua/specs/tinycua-finetune/

docker_files:
  Dockerfile: src/tinycua-benchmark/Dockerfile
  docker-compose.benchmark.yml: src/tinycua-benchmark/docker-compose.yml
  scripts/entrypoint.sh: src/tinycua-benchmark/scripts/entrypoint.sh

deleted:
  .reviews/: [deleted]
```

### Schema Changes

No data model changes - this is purely a file reorganization.

---

## API / Interface Contracts

### File Operations

```bash
# Move root spec files
mv spec.md src/tinycua/specs/5.6-full-benchmark-run/
mv design.md src/tinycua/specs/5.6-full-benchmark-run/
mv implementation-plan.md src/tinycua/specs/5.6-full-benchmark-run/
mv task.md src/tinycua/specs/5.6-full-benchmark-run/

# Move root specs
mv specs/tinycua-worker-digestion/ src/tinycua/specs/
mv specs/tinycua-nodequeue-suspend/ src/tinycua/specs/
mv specs/tinycua-nodequeue-basic/ src/tinycua/specs/
mv specs/tinycua-node/ src/tinycua/specs/
mv specs/wildclawbench-adapter/ src/tinycua/specs/
mv specs/tinycua-finetune/ src/tinycua/specs/

# Move Docker files to src/tinycua-benchmark/
mkdir -p src/tinycua-benchmark/scripts
mv Dockerfile src/tinycua-benchmark/
mv docker-compose.benchmark.yml src/tinycua-benchmark/docker-compose.yml
mv scripts/entrypoint.sh src/tinycua-benchmark/scripts/

# Delete review artifacts
rm -rf .reviews/

# Update Dockerfile to reference new entrypoint location
# (Update COPY path if needed)
```

### Error Handling

| Error Case | Solution |
|------------|----------|
| File already exists at destination | Rename with suffix or merge carefully |
| Broken references after move | Update references in documentation |
| .reviews/ contains important data | Preserve content but gitignore |

---

## Implementation Phases

### Phase 1 — Root File Cleanup

- [x] Create `src/tinycua/specs/5.6-full-benchmark-run/` directory
- [x] Move root `spec.md`, `design.md`, `implementation-plan.md`, `task.md` to new directory
- [x] Verify files are readable at new location

### Phase 2 — Specs Relocation

- [x] Move all subdirectories from root `specs/` to `src/tinycua/specs/`
- [x] Verify no duplicate directory names
- [x] Update any references to old locations

### Phase 3 — Docker Files Relocation

- [ ] Create `src/tinycua-benchmark/scripts/` directory
- [ ] Move `Dockerfile` to `src/tinycua-benchmark/`
- [ ] Move `docker-compose.benchmark.yml` to `src/tinycua-benchmark/docker-compose.yml`
- [ ] Move `scripts/entrypoint.sh` to `src/tinycua-benchmark/scripts/`
- [ ] Update Dockerfile COPY path for entrypoint.sh
- [ ] Test Docker build still works

### Phase 4 — Cleanup

- [ ] Delete `.reviews/` directory
- [ ] Clean up empty directories
- [ ] Update .gitignore if needed

### Phase 5 — Verification

- [ ] Verify all files are at correct locations
- [ ] Verify no broken references
- [ ] Test Docker build: `docker build -t tinycua-benchmark src/tinycua-benchmark/`
- [ ] Run `git status` to confirm clean working tree

---

## Technical Decisions

1. **Decision**: Move root spec files to `src/tinycua/specs/5.6-full-benchmark-run/`
   - **Reason**: Creates dedicated directory for Milestone 5.6 artifacts
   - **Alternatives Considered**: Merge into existing specs - rejected because 5.6 is a distinct milestone

2. **Decision**: Move Docker files to `src/tinycua-benchmark/`
   - **Reason**: Creates dedicated subproject for benchmark Docker infrastructure
   - **Alternatives Considered**: Keep in root - rejected because it clutters the root directory

3. **Decision**: Delete `.reviews/` directory
   - **Reason**: Review artifacts are temporary workspace-specific files that should not be preserved
   - **Alternatives Considered**: Gitignore - rejected because user wants them deleted

4. **Decision**: Keep `scripts/entrypoint.sh` but move to `src/tinycua-benchmark/scripts/`
   - **Reason**: Script is still needed for Docker benchmark execution
   - **Alternatives Considered**: Remove - rejected because it's referenced in Dockerfile

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Broken references after file moves | Medium | Medium | Search for references before moving, update as needed |
| Duplicate directory names | Low | Low | Check destination before moving, rename if needed |
| Accidental data loss | Low | High | Use `git mv` for tracking, verify content after moves |
| Empty directories left behind | High | Low | Clean up empty directories after moves |

---

## Open Questions _(optional)_

1. **What should the Docker subproject be named?**
   - **Status**: Decided
   - **Proposed Answer**: `src/tinycua-benchmark/` - contains all Docker-related files for benchmarking.

2. **Should the .reviews/ directory be deleted or just gitignored?**
   - **Status**: Decided
   - **Proposed Answer**: Deleted - review artifacts are temporary and should not be preserved.

---

## References

- Spec: [./spec.md](./spec.md)
- Project conventions: `AGENTS.md`
- Directory structure: `src/tinycua/specs/`
- Gitignore patterns: `.gitignore`
