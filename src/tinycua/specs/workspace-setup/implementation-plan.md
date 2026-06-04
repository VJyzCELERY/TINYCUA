# Implementation: Workspace Setup (M0.1)

Establish a verified, reproducible workspace for the TINYCUA prototype: `uv`-managed dependencies, a no-op CLI entry point, WildClawBench artifact exclusions, and prototype documentation scaffolding.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0 (foundation for all future milestones)
- **Estimated Effort**: S

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python >=3.12
- [x] **Package manager**: uv
- [x] **None** — no additional CLI tools required

---

## Success Criteria — Verification (Manual, TDD Not Applicable)

This milestone is workspace scaffolding — the spec explicitly states integration tests are not applicable. Verification is manual acceptance testing.

```bash
# Scenario 1: uv sync completes without error
cd src/tinycua && uv sync
# Expected: .venv created, no errors

# Scenario 2: CLI entry point works
cd src/tinycua && uv run tinycua
# Expected: prints "tinycua: workspace is ready." and exits 0

# Scenario 3: WildClawBench artifacts are gitignored
mkdir -p src/tinycua/benchmark_results
touch src/tinycua/test.benchmark.json
git check-ignore -v src/tinycua/benchmark_results/ src/tinycua/test.benchmark.json
rm -rf src/tinycua/benchmark_results src/tinycua/test.benchmark.json

# Scenario 4: Prototype docs exist
cat src/tinycua/docs/prototype/README.md
# Expected: file exists with documentation content

# Scenario 5: Lint passes
cd src/tinycua && make lint
# Expected: no errors
```

### Key Test Scenarios

- [x] **Scenario 1**: `uv sync` installs dependencies and creates `.venv`
- [x] **Scenario 2**: `uv run tinycua` prints message and exits 0
- [x] **Scenario 3**: WildClawBench artifacts excluded from `git status`
- [x] **Scenario 4**: `docs/prototype/README.md` exists with content
- [x] **Scenario 5**: `make lint` passes on new code

## Verification Plan

### Automated Tests

- [x] Not applicable — workspace setup validated via manual acceptance (per spec)

### Manual Verification

- [x] Run all 5 scenarios above and confirm expected output
- [x] Verify `git diff` shows only intended changes (no accidental modifications)

### Performance Considerations

- [x] Not applicable for this milestone

## Proposed Changes

### Root Level

#### [MODIFY] `.gitignore`

- **Add WildClawBench artifact rules**: `benchmark_results/`, `*.benchmark.json`, `*.benchmark.yaml`
- **Rationale**: FR-003 requires benchmark artifacts to be excluded from version control

### src/tinycua/

#### [VERIFY] `src/tinycua/pyproject.toml`

- **Confirm entry point**: `[project.scripts] tinycua = "tinycua.cli.main:main"` already exists
- **Rationale**: FR-001 and FR-006 require the entry point to be wired correctly

#### [NEW] `src/tinycua/tinycua/cli/__init__.py`

- **Package init**: Empty `__init__.py` for the `cli` subpackage
- **Rationale**: Required for Python package discovery

#### [NEW] `src/tinycua/tinycua/cli/main.py`

- **No-op CLI entry point**: `main()` prints message, exits 0 via `SystemExit(0)`
- **Rationale**: FR-001 and FR-006 — the core deliverable of this milestone

#### [NEW] `src/tinycua/docs/prototype/README.md`

- **Prototype documentation scaffold**: Explains the `docs/prototype/` directory structure and purpose
- **Rationale**: FR-004 requires prototype documentation

#### [REFORMAT] `src/tinycua/tinycua/agent/tools/native/` (lint compliance)

- **Files**: `__init__.py`, `files.py`, `web.py` — reformatted only
- **Rationale**: `make lint` acceptance check required these files to pass linting; no behavior changes

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `src/tinycua/tinycua/cli/` | New | CLI subpackage with no-op entry point |
| `src/tinycua/tinycua/agent/tools/native/` | Reformatted | Lint compliance — no behavior changes |
| `.gitignore` | Modified | WildClawBench artifact exclusions added |
| `src/tinycua/docs/prototype/` | New | Prototype documentation directory |

## Data Model Changes

Not applicable.

## API Changes

Not applicable.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | No new dependencies; stdlib `print()` only |

### Internal Dependencies

- [x] No internal dependencies — standalone milestone

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Root `pyproject.toml` shadows `tinycua` script when run from repo root | Low | Document that `uv run tinycua` must be run from `src/tinycua/` |
| WildClawBench `.gitignore` rules too broad | Low | Use specific patterns (directory name + file extension) |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-05*
