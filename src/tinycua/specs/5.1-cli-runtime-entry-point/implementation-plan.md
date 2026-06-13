# Implementation: TinyCUA CLI / Runtime Entry Point

Replace the no-op CLI placeholder with a fully functional `tinycua run` subcommand that accepts a task prompt and timeout, configures a local model endpoint, executes the TinyCUA agent, and produces WildClawBench-compatible transcript/log artifacts.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [x] **None** — the CLI itself reads from env vars at runtime; no pre-existing config needed

### Running Services

- [ ] **Local LLM endpoint** (vLLM, Ollama, or LM Studio) for integration testing — `TINYCUA_BASE_URL=http://localhost:8080/v1`

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **None** — no additional CLI tools required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_cli_run.py
"""Integration tests for tinycua run CLI."""


import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


class TestCLIRunArgumentParsing:
    """Verify all CLI flags and positional arguments are correctly parsed."""

    def test_run_requires_prompt(self):
        """Given no prompt, the CLI exits with usage error (code 2)."""
        result = subprocess.run(
            [sys.executable, "-m", "tinycua.cli.main", "run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_run_accepts_prompt_positional(self):
        """Given a prompt as positional arg, the CLI accepts it."""
        # This test will call the parse_args helper directly
        from tinycua.cli.run import parse_args

        args = parse_args(["hello world"])
        assert args.prompt == "hello world"

    def test_run_accepts_prompt_flag(self):
        """Given --prompt flag, the CLI accepts it."""
        from tinycua.cli.run import parse_args

        args = parse_args(["--prompt", "do something"])
        assert args.prompt == "do something"

    def test_run_defaults(self):
        """Given minimal args, defaults are applied correctly."""
        from tinycua.cli.run import parse_args

        args = parse_args(["test"])
        assert args.timeout == 600
        assert args.output_dir == Path("/tmp_workspace/results")
        assert args.workspace == Path("/tmp_workspace")
        assert args.verbose is False

    def test_run_accepts_all_flags(self):
        """Given all flags, they are parsed correctly."""
        from tinycua.cli.run import parse_args

        args = parse_args([
            "--timeout", "30",
            "--output-dir", "./out",
            "--workspace", "/ws",
            "--base-url", "http://localhost:8080/v1",
            "--api-key", "sk-test",
            "--model", "llama-3-8b",
            "--verbose",
            "my task",
        ])
        assert args.prompt == "my task"
        assert args.timeout == 30
        assert args.output_dir == Path("./out")
        assert args.workspace == Path("/ws")
        assert args.base_url == "http://localhost:8080/v1"
        assert args.api_key == "sk-test"
        assert args.model == "llama-3-8b"
        assert args.verbose is True


class TestCLIRunConfigLoading:
    """Verify environment variable and CLI config loading."""

    def test_config_from_env_vars(self):
        """Given env vars, config is loaded correctly."""
        from tinycua.cli.config import load_config

        with patch.dict("os.environ", {
            "TINYCUA_BASE_URL": "http://env-host:8080/v1",
            "TINYCUA_API_KEY": "env-key",
            "TINYCUA_MODEL": "env-model",
        }):
            config = load_config(base_url=None, api_key=None, model=None)
            assert config["base_url"] == "http://env-host:8080/v1"
            assert config["api_key"] == "env-key"
            assert config["model"] == "env-model"

    def test_cli_overrides_env_vars(self):
        """Given both env vars and CLI flags, CLI flags win."""
        from tinycua.cli.config import load_config

        with patch.dict("os.environ", {
            "TINYCUA_BASE_URL": "http://env-host:8080/v1",
            "TINYCUA_API_KEY": "env-key",
        }):
            config = load_config(
                base_url="http://cli-host:9090/v1",
                api_key="cli-key",
                model=None,
            )
            assert config["base_url"] == "http://cli-host:9090/v1"
            assert config["api_key"] == "cli-key"

    def test_missing_base_url_raises(self):
        """Given no base_url in env or CLI, raises ValueError."""
        from tinycua.cli.config import load_config

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="base_url"):
                load_config(base_url=None, api_key=None, model=None)

    def test_missing_api_key_raises(self):
        """Given no api_key in env or CLI, raises ValueError."""
        from tinycua.cli.config import load_config

        with patch.dict("os.environ", {
            "TINYCUA_BASE_URL": "http://localhost:8080/v1",
        }, clear=False):
            with pytest.raises(ValueError, match="api_key"):
                load_config(base_url=None, api_key=None, model=None)


class TestCLIRunExitCodes:
    """Verify exit codes for success, error, and timeout scenarios."""

    def test_exit_code_0_on_success(self):
        """Given a successful run, exit code is 0."""
        from tinycua.cli.run import run_command

        with patch("tinycua.cli.run.create_tinycua_agent") as mock_factory:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value="done")
            mock_factory.return_value = mock_agent

            with patch("tinycua.cli.run.load_config", return_value={
                "base_url": "http://localhost:8080/v1",
                "api_key": "test",
                "model": "test-model",
            }):
                exit_code = run_command(
                    prompt="test task",
                    timeout=10,
                    output_dir=Path("./tmp_test_out"),
                    workspace=Path("./tmp_test_ws"),
                    base_url=None, api_key=None, model=None,
                    verbose=False,
                )
                assert exit_code == 0

    def test_exit_code_1_on_error(self):
        """Given an agent crash, exit code is 1."""
        from tinycua.cli.run import run_command

        with patch("tinycua.cli.run.create_tinycua_agent") as mock_factory:
            mock_factory.side_effect = RuntimeError("endpoint unreachable")

            with patch("tinycua.cli.run.load_config", return_value={
                "base_url": "http://localhost:8080/v1",
                "api_key": "test",
                "model": "test-model",
            }):
                exit_code = run_command(
                    prompt="test task",
                    timeout=10,
                    output_dir=Path("./tmp_test_out"),
                    workspace=Path("./tmp_test_ws"),
                    base_url=None, api_key=None, model=None,
                    verbose=False,
                )
                assert exit_code == 1

    def test_exit_code_124_on_timeout(self):
        """Given timeout exceeded, exit code is 124."""
        import asyncio
        from tinycua.cli.run import run_command

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(100)
            return "never"

        with patch("tinycua.cli.run.create_tinycua_agent") as mock_factory:
            mock_agent = AsyncMock()
            mock_agent.run = slow_run
            mock_factory.return_value = mock_agent

            with patch("tinycua.cli.run.load_config", return_value={
                "base_url": "http://localhost:8080/v1",
                "api_key": "test",
                "model": "test-model",
            }):
                exit_code = run_command(
                    prompt="test task",
                    timeout=1,  # 1 second timeout
                    output_dir=Path("./tmp_test_out"),
                    workspace=Path("./tmp_test_ws"),
                    base_url=None, api_key=None, model=None,
                    verbose=False,
                )
                assert exit_code == 124


class TestCLIRunTranscriptWriting:
    """Verify transcript JSONL file is produced."""

    def test_transcript_file_created(self, tmp_path):
        """Given a successful run, transcript.jsonl exists in output dir."""
        from tinycua.cli.transcript import write_transcript

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Create hello.txt"},
            {"role": "assistant", "content": "I'll create that file."},
        ]
        write_transcript(messages, tmp_path / "transcript.jsonl")

        assert (tmp_path / "transcript.jsonl").exists()
        lines = (tmp_path / "transcript.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            record = json.loads(line)
            assert "role" in record


class TestCLIRunLogWriting:
    """Verify structured agent log is produced."""

    def test_log_file_created(self, tmp_path):
        """Given a run, agent.log exists in output dir."""
        from tinycua.cli.logging import write_log_entry

        write_log_entry(tmp_path / "agent.log", "start", "info", {"prompt": "test"})
        write_log_entry(tmp_path / "agent.log", "complete", "info", {"duration": 1.2})

        assert (tmp_path / "agent.log").exists()
        lines = (tmp_path / "agent.log").read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert "timestamp" in entry
            assert "event" in entry
            assert "level" in entry
```

### Key Test Scenarios

- [ ] **Scenario 1**: CLI argument parsing — all flags and positional args work correctly
- [ ] **Scenario 2**: Config loading — env vars + CLI overrides + validation
- [ ] **Scenario 3**: Exit codes — 0 success, 1 error, 124 timeout
- [ ] **Scenario 4**: Transcript writing — JSONL output produced
- [ ] **Scenario 5**: Log writing — structured JSON log entries produced
- [ ] **Edge case**: Missing required config raises clear error before agent execution
- [ ] **Edge case**: Output directory created if it doesn't exist

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for argument parsing, config loading, exit codes
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Run `tinycua run "echo hello"` against a local LLM endpoint and verify transcript output
- [ ] Run with `--timeout 5` against a slow prompt and verify timeout behavior
- [ ] Run with invalid endpoint and verify error handling

### Performance Considerations

- [ ] N/A — CLI execution time is bounded by LLM latency, not CLI overhead

## Proposed Changes

### CLI Module

#### [NEW] `tinycua/cli/run.py`

- **Description**: `run` subcommand implementation — argument parsing, agent execution, timeout enforcement, transcript/log writing
- **Dependencies**: `tinycua.factory`, `tinycua.cli.config`, `tinycua.cli.transcript`, `tinycua.cli.logging`

#### [NEW] `tinycua/cli/config.py`

- **Description**: Environment variable and CLI config loading — `load_config()` reads `TINYCUA_BASE_URL`, `TINYCUA_API_KEY`, `TINYCUA_MODEL` from env vars, applies CLI overrides, validates required fields
- **Dependencies**: `os.environ`

#### [NEW] `tinycua/cli/transcript.py`

- **Description**: Transcript capture and JSONL writing — `write_transcript()` converts working messages to OpenClaw-compatible JSONL format
- **Dependencies**: `json`, `pathlib.Path`

#### [NEW] `tinycua/cli/logging.py`

- **Description**: Structured agent log writing — `write_log_entry()` produces JSON lines with timestamps, event types, and payloads
- **Dependencies**: `json`, `pathlib.Path`, `datetime`

#### [MODIFY] `tinycua/cli/main.py`

- **Description**: Replace no-op placeholder with `tinycua run` subcommand dispatcher using argparse with subcommands
- **Breaking changes**: The `tinycua` command without `run` subcommand will now show help instead of "workspace is ready"

#### [MODIFY] `tinycua/cli/__init__.py`

- **Description**: May need to export subcommand functions if using package-level registration

### SDK Integration

#### [MODIFY] `tinycua/loops/tinycua_loop.py`

- **Description**: Add `self._working_messages: list[dict] = []` attribute to `__init__()` and set it in `run()` before returning, so transcript writer can access working messages after execution
- **Breaking changes**: None — additive change to existing class

### Configuration

#### [MODIFY] `pyproject.toml`

- **Description**: Verify `[project.scripts]` entry point — currently `tinycua = "tinycua.cli.main:main"`, should work as-is since `main()` will dispatch to subcommands

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/cli/main.py` | Modify | Replace no-op with argparse subcommand dispatcher |
| `tinycua/cli/run.py` | New | `run` subcommand implementation |
| `tinycua/cli/config.py` | New | Env var + CLI config loading |
| `tinycua/cli/transcript.py` | New | Transcript capture and JSONL writing |
| `tinycua/cli/logging.py` | New | Structured agent log writing |
| `tinycua/loops/tinycua_loop.py` | Modify | Expose working messages for transcript capture |
| `pyproject.toml` | Unchanged | Entry point already correct |

## Data Model Changes

```python
# tinycua/cli/config.py
@dataclass
class RunConfig:
    """Configuration for a single tinycua run invocation."""
    prompt: str                          # Required task prompt
    timeout: int = 600                   # Max execution seconds
    output_dir: Path = Path("/tmp_workspace/results")
    workspace: Path = Path("/tmp_workspace")
    base_url: str                        # OpenAI-compatible endpoint (required)
    api_key: str                         # API key (required)
    model: str = "local-model"           # Model identifier
    verbose: bool = False                # Debug logging

# tinycua/cli/logging.py
@dataclass
class LogEntry:
    timestamp: str       # ISO 8601
    event: str           # "start" | "config" | "agent_run" | "complete" | "error" | "timeout"
    level: str           # "info" | "warning" | "error"
    data: dict           # Event-specific payload
```

## API Changes

### CLI Interface

```bash
# Basic usage
tinycua run "Create a file called hello.txt with content 'Hello, World!'"

# With options
tinycua run \
  --timeout 120 \
  --output-dir ./results \
  --workspace /tmp_workspace \
  --base-url http://localhost:8080/v1 \
  --api-key sk-local \
  --model llama-3-8b \
  --verbose \
  "Summarize the files in the current directory"
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Successful completion |
| 1 | General error (invalid args, agent crash, endpoint unreachable) |
| 124 | Timeout (agent killed after exceeding timeout) |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | All dependencies are stdlib or already in project |

### Internal Dependencies

- [x] Depends on `tinycua.factory.create_tinycua_agent()` (already exists)
- [x] Depends on `tinycua.loops.tinycua_loop.TinyCUALoop` (needs minor modification to expose working messages)
- [x] Depends on `tinycua_sdk.agent.agent.Agent` (already exists)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| BaseLoop working messages not accessible after run | High | Add `self._working_messages` attribute to TinyCUALoop — already resolved in design |
| Timeout watchdog kills process before cleanup completes | Medium | Use `threading.Timer` with SIGTERM + 2s grace period + SIGKILL; write partial transcript on signal |
| Transcript format mismatch with WildClawBench | High | Follow exact schema from adapter-contract.md; test with WildClawBench transcript loader |
| Local model endpoint latency causes premature timeout | Medium | Default timeout of 600s is generous; document that users should adjust based on model speed |
| Output directory permissions in container | Medium | Pre-flight check before agent execution; create directory if it doesn't exist |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-13*
