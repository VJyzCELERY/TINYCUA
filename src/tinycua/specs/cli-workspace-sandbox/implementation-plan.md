# Implementation: CLI Workspace Sandboxing

Fix the `tinycua run` CLI argparse crash and eliminate all process-wide CWD mutations.

## Context

- **Spec Reference**: specs/cli-workspace-sandbox/spec.md
- **Design Reference**: specs/cli-workspace-sandbox/design.md
- **Priority**: P0
- **Estimated Effort**: S

## Environment Pre-requisites

### Configuration

- [ ] **.env file** — required variables:
  ```
  TINYCUA_BASE_URL=http://localhost:1234/v1
  TINYCUA_API_KEY=not-needed
  TINYCUA_MODEL=qwen3.5-9b
  TINYCUA_PROVIDER_TYPE=openai-chat-completions
  ```
- [ ] **None** — no secrets beyond local LLM server

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| LM Studio / local LLM | Yes | Start LM Studio, load model | `curl http://localhost:1234/v1/models` |

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: tests/unit/test_cli_workspace_sandbox.py

def test_main_parser_accepts_run_args():
    """main.py argparse must accept all run subcommand args."""
    from tinycua.cli.main import main
    # Verify that `tinycua run "hello" --dir ./tmp` parses without error

def test_run_command_does_not_chdir(tmp_path, monkeypatch):
    """run_command must not call os.chdir."""
    original_cwd = Path.cwd()
    # ... run command ...
    assert Path.cwd() == original_cwd

def test_bind_workspace_does_not_mkdir(tmp_path):
    """bind_workspace must not create directories."""
    nonexistent = tmp_path / "should_not_exist"
    bind_workspace(str(nonexistent))
    assert not nonexistent.exists()

def test_context_var_workspace_resolved():
    """Workspace must be resolved to absolute path via ContextVar."""
    ...

def test_run_shell_uses_cwd_param(tmp_path, monkeypatch):
    """run_shell must pass cwd=workspace to subprocess, not os.chdir."""
    ...
```

### Key Test Scenarios

- [ ] `tinycua run "hello" --dir ./tmp` parses correctly (no argparse crash)
- [ ] `run_command` never calls `os.chdir`
- [ ] `bind_workspace` does NOT create directories
- [ ] `run_shell` uses `cwd=` parameter, not process CWD
- [ ] CWD is unchanged after a full `tinycua run` invocation

## Verification Plan

### Automated Tests

- [ ] `cd src/tinycua && uv run pytest tests/unit/test_cli_workspace_sandbox.py` — new tests pass
- [ ] `cd src/tinycua && uv run pytest` — full suite green, no regressions

### Manual Verification

- [ ] `cd src/tinycua && uv run tinycua run "hello" --dir ./tmp --provider-url http://localhost:1234/v1 --api-key test --model qwen3.5-9b`
- [ ] Verify CWD unchanged after run
- [ ] Verify `./tmp/.tinycua-artifacts/` contains run artifacts

## Proposed Changes

### cli/main.py

#### MODIFY — Register run args on subparser

- **Description**: Add all `run` subcommand arguments to the `run` subparser in `main.py` so that `parser.parse_args()` handles them correctly in a single pass. Remove the re-parse via `parse_args(sys.argv[2:])`.
- **Rationale**: The current empty subparser causes `argparse` to reject `tinycua run "hello" --dir ./tmp` with "unrecognized arguments".

### cli/run.py

#### MODIFY — Resolve `--dir` to absolute path immediately

- **Description**: Change `--dir` default to `None` instead of `Path.cwd()`. In `run_command`, resolve `None` to `Path.cwd().resolve()` and `Path` args to absolute. This avoids stale CWD references.
- **Rationale**: `Path.cwd()` evaluated at argparse default time can become stale. Resolving in `run_command` is safer.

### agent/tools/native/context.py

#### MODIFY — Remove mkdir from bind_workspace

- **Description**: Remove `workspace.mkdir(parents=True, exist_ok=True)` from `bind_workspace()`. Workspace creation is the CLI's job.
- **Rationale**: Silently recreating a deleted workspace masks bugs. If the workspace doesn't exist, that's a configuration error.

### cli/benchmark.py

#### MODIFY — Deprecate and remove os.chdir

- **Description**: Add `DeprecationWarning`. Replace `os.chdir(workspace)` with explicit `cwd=str(workspace)` in any subprocess calls.
- **Rationale**: Process-wide CWD mutation causes bugs in multi-threaded and multi-terminal scenarios.

### tests/unit/conftest.py

#### MODIFY — Remove FileNotFoundError workaround

- **Description**: Remove the `try: Path.cwd() except FileNotFoundError` pattern. If CWD disappears, that's a bug, not a normal condition.
- **Rationale**: Papering over CWD bugs hides real issues.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `cli/main.py` | Modify | Register run args on subparser, single-pass parse |
| `cli/run.py` | Modify | Resolve --dir to absolute in run_command, not argparse default |
| `agent/tools/native/context.py` | Modify | Remove mkdir from bind_workspace |
| `cli/benchmark.py` | Modify | Add deprecation warning, remove os.chdir |
| `tests/unit/conftest.py` | Modify | Remove FileNotFoundError workaround |

## Dependencies

- None — this is a self-contained fix

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Argparse arg duplication between main.py and run.py | Low | Extract shared arg definitions into a helper function |
| Tests that relied on bind_workspace creating dirs | Med | Fix tests to create their own dirs |
| benchmark.py callers broken by deprecation | Low | Warning only, not an error |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-18*