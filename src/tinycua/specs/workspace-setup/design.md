# Design Document: Workspace Setup

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-05

---

## Overview

This design establishes the TINYCUA prototype workspace: a `uv`-managed Python project with a no-op CLI entry point, WildClawBench artifact exclusions, and prototype documentation scaffolding. The changes are scoped to the `src/tinycua/` subproject and the root `.gitignore`.

---

## Architecture

### Component Overview

```
TINYCUA (root)
├── pyproject.toml              # root project (preflight scripts)
├── .gitignore                  # extended with WildClawBench rules
├── src/
│   └── tinycua/                # main CLI subproject
│       ├── pyproject.toml      # tinycua package definition + entry point
│       ├── tinycua/
│       │   ├── __init__.py
│       │   ├── cli/
│       │   │   ├── __init__.py
│       │   │   └── main.py     # no-op CLI entry point
│       │   └── agent/          # existing (unchanged)
│       ├── tests/
│       ├── docs/
│       │   └── prototype/
│       │       └── README.md   # prototype docs structure
│       └── Makefile
└── docs/
    └── prototype/              # (if root-level prototype docs are needed)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `src/tinycua/pyproject.toml` | Modified | Verify `[project.scripts]` entry point is correct |
| `src/tinycua/tinycua/cli/__init__.py` | New | Package init for CLI module |
| `src/tinycua/tinycua/cli/main.py` | New | No-op CLI entry point |
| `src/tinycua/docs/prototype/README.md` | New | Prototype documentation scaffold |
| `.gitignore` (root) | Modified | Add WildClawBench artifact exclusions |

---

## Data Model

Not applicable — this milestone involves no persistent data structures.

---

## API / Interface Contracts

### CLI Entry Point

```python
# src/tinycua/tinycua/cli/main.py

def main() -> None:
    """No-op CLI entry point for workspace verification."""
    print("tinycua: workspace is ready.")
    raise SystemExit(0)
```

**Contract**:
- `main()` takes no arguments.
- `main()` prints a single line to stdout.
- `main()` exits with code 0 via `SystemExit(0)`.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `uv` not installed | Shell error: `command not found: uv` | No special handling needed |
| Run from wrong directory | `uv` uses root `pyproject.toml` — no `tinycua` script defined | Acceptable for M0.1 |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add `tinycua/cli/` package with `__init__.py` and `main.py`
- [ ] Verify `[project.scripts]` in `src/tinycua/pyproject.toml` points to `tinycua.cli.main:main`
- [ ] Add WildClawBench artifact rules to root `.gitignore`
- [ ] Create `src/tinycua/docs/prototype/README.md` with structure documentation
- [ ] Verify `uv run tinycua` works from `src/tinycua/`

### Phase 2 — Enhancements _(post-MVP)_

Not applicable for this milestone.

---

## Technical Decisions

1. **Decision**: Use `SystemExit(0)` instead of `return` in `main()`
   - **Reason**: Explicit exit code makes the no-op behavior unambiguous; `uv run` captures the exit code.
   - **Alternatives Considered**: Bare `return` — rejected because it relies on the caller's exit code handling.

2. **Decision**: Place WildClawBench rules in root `.gitignore` rather than `src/tinycua/.gitignore`
   - **Reason**: Benchmark artifacts may be generated anywhere in the repo; root-level exclusion is simpler and catches all locations.
   - **Alternatives Considered**: Subproject `.gitignore` — rejected because it only covers `src/tinycua/`.

3. **Decision**: Use `print()` instead of `logging` or `rich` for the no-op message
   - **Reason**: Minimal dependency footprint; the no-op entry point should not import anything beyond stdlib.
   - **Alternatives Considered**: `rich.console.Console().print()` — rejected because it adds an import dependency for a one-line message.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Root `pyproject.toml` shadows `tinycua` script when run from repo root | Low | Low | Document that `uv run tinycua` must be run from `src/tinycua/` |
| WildClawBench `.gitignore` rules too broad | Low | Low | Use specific patterns (directory + file extension) |

---

## Open Questions _(optional)_

None.

---

## References

- Spec: `./spec.md`
- Existing `src/tinycua/pyproject.toml`: already has `[project.scripts] tinycua = "tinycua.cli.main:main"`
- Existing root `.gitignore`: needs WildClawBench additions
