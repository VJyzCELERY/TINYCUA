# Design Document: CLI Workspace Sandboxing

**Spec**: ./spec.md
**Status**: In Progress
**Last Updated**: 2026-06-18

---

## Overview

Fix the `tinycua run` CLI argparse crash and eliminate all process-wide CWD mutations. The key architectural change: workspace-scoped operations use explicit `cwd=` in subprocess calls and `ContextVar`-based path resolution, never `os.chdir()`. The `run` subparser in `main.py` gets its full argument set so argparse validates correctly in one pass.

---

## Architecture

### Component Overview

```
tinycua run "prompt" --dir ./tmp
  │
  ├─ main.py          [MODIFY] Register run args on subparser
  ├─ run.py           [MODIFY] Remove any CWD assumptions, resolve --dir early
  ├─ context.py       [MODIFY] Remove mkdir from bind_workspace, fix ContextVar propagation
  ├─ shell.py         [MODIFY] Already uses cwd=, verify no chdir
  ├─ python_exec.py   [MODIFY] Already uses cwd=, verify no chdir
  ├─ files.py         [MODIFY] Verify resolve_workspace_path works correctly
  └─ benchmark.py     [MODIFY] Mark deprecated, remove os.chdir
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `cli/main.py` | Modify | Register run args on subparser so argparse works |
| `cli/run.py` | Modify | Resolve `--dir` to absolute path immediately |
| `cli/config.py` | No change | Already correct |
| `agent/tools/native/context.py` | Modify | Remove `mkdir` from `bind_workspace`, ensure ContextVar propagation |
| `agent/tools/native/shell.py` | Verify | Already uses `cwd=str(workspace)`, no `os.chdir` |
| `agent/tools/native/python_exec.py` | Verify | Already uses `cwd=str(workspace)`, no `os.chdir` |
| `agent/tools/native/files.py` | Verify | Uses `resolve_workspace_path`, no `os.chdir` |
| `cli/benchmark.py` | Modify | Add deprecation warning, remove `os.chdir` |

---

## API / Interface Contracts

### `main.py` — Register run subparser arguments

```python
# Before: empty subparser (causes argparse crash)
subparsers.add_parser("run", help="...")

# After: full argument set
run_parser = subparsers.add_parser("run", help="...")
run_parser.add_argument("prompt", nargs="?")
run_parser.add_argument("--prompt", dest="prompt_option", default=None)
run_parser.add_argument("--dir", type=Path, default=Path.cwd())
run_parser.add_argument("--model", type=str, default=None)
# ... all other run args
```

Then `main.py` dispatches using `args` directly from the first parse, no re-parsing.

### `context.py` — Remove mkdir from bind_workspace

```python
# Before
def bind_workspace(workspace_dir):
    workspace = Path(workspace_dir).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)  # ← REMOVED
    _WORKSPACE_DIR.set(workspace)

# After
def bind_workspace(workspace_dir):
    workspace = Path(workspace_dir).expanduser().resolve()
    _WORKSPACE_DIR.set(workspace)
```

Workspace creation is the CLI's responsibility, not the tool binding's.

### `benchmark.py` — Deprecation

```python
# Add deprecation warning at top of benchmark_run_command
import warnings
warnings.warn(
    "tinycua benchmark is deprecated. Use tinycua run instead.",
    DeprecationWarning,
    stacklevel=2,
)
# Remove os.chdir(workspace) — use cwd= in subprocess calls instead
```

---

## Implementation Phases

### Phase 1 — Fix CLI argparse and CWD sandboxing

- [ ] Fix `main.py` to register run args on subparser
- [ ] Fix `main.py` dispatch to use single-parsed args (no re-parse)
- [ ] Remove `mkdir` from `bind_workspace` in `context.py`
- [ ] Add deprecation + remove `os.chdir` from `benchmark.py`
- [ ] Fix `conftest.py` to not paper over CWD bugs

### Phase 2 — ContextVar propagation (if needed)

- [ ] Verify ContextVar works correctly in `asyncio.run()` context
- [ ] Add explicit workspace re-binding in `_run_async_safely` if needed

---

## Technical Decisions

1. **Decision**: Single-pass argparse (register args on subparser) instead of `parse_known_args`
   - **Reason**: Cleaner, standard argparse pattern. `parse_known_args` would require manual validation. Registering args on the subparser lets argparse handle validation naturally.
   - **Alternatives Considered**: `parse_known_args` + manual re-parse — rejected because it's fragile and bypasses argparse validation.

2. **Decision**: Remove `mkdir` from `bind_workspace`
   - **Reason**: Creating directories is the CLI's responsibility, not the tool binding's. Re-creating a deleted workspace silently masks bugs.
   - **Alternatives Considered**: Keep mkdir but add logging — rejected because it masks real issues.

3. **Decision**: Deprecate `benchmark.py` instead of removing
   - **Reason**: There may be external callers. A deprecation warning is non-breaking.
   - **Alternatives Considered**: Delete it — rejected for backward compatibility.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Subparser arg duplication with `run.py`'s `parse_args` | Med | Med | Refactor to share arg definitions or use single parse |
| ContextVar not propagating in ThreadPoolExecutor | Low | Med | Test explicitly; add manual propagation if needed |
| Removing mkdir from bind_workspace breaks tests | Med | Low | Tests should create their own workspace dirs |

---

## References

- Spec: `./spec.md`