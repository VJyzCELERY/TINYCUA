# Implementation: WildClawBench TinyCUA BaseAgent Adapter

Provides a `TinyCUAAgent` adapter that implements WildClawBench's `BaseAgent` interface so TinyCUA can be selected as an agent backend for benchmark task execution. The adapter spawns the existing `tinycua run` CLI as a subprocess, handles timeout enforcement, collects usage data, and manages transcript paths.

## Context

- **Spec Reference**: [./spec.md](./spec.md)
- **Design Reference**: [./design.md](./design.md)
- **Priority**: P1
- **Estimated Effort**: S

## Environment Pre-requisites

### Configuration

- [x] **None** — no additional configuration beyond existing project setup. All tests use mocked subprocess calls.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| LLM endpoint | No | Mock via test fixtures | N/A |

- [x] **None** — unit tests mock subprocess execution; integration tests use a stub `tinycua` script.

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.10+, uv
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_wildclawbench_integration.py
"""Integration tests for WildClawBench TinyCUA BaseAgent Adapter."""


import json
import subprocess
from pathlib import Path

import pytest

from tinycua.wildclawbench.base_agent import AgentExecution, AgentTaskSpec
from tinycua.wildclawbench.agent import TinyCUAAgent


@pytest.fixture
def task_spec(tmp_path):
    """Create a minimal AgentTaskSpec for testing."""
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "output"
    return AgentTaskSpec(
        task_id="test-task-001",
        task={"type": "simple", "prompt": "test"},
        workspace_path=str(workspace),
        prompt="Say hello",
        timeout_seconds=30,
        output_dir=output_dir,
        model="test-model",
    )


def test_agent_expects_gateway_is_false():
    """Verify expects_gateway returns False (no long-running process needed)."""
    agent = TinyCUAAgent()
    assert agent.expects_gateway is False


def test_transcript_container_path_is_string():
    """Verify transcript_container_path returns a valid string path."""
    agent = TinyCUAAgent()
    path = agent.transcript_container_path
    assert isinstance(path, str)
    assert path.endswith("transcript.jsonl")


def test_prepare_grading_transcript_returns_container_path():
    """Verify prepare_grading_transcript returns transcript_container_path."""
    agent = TinyCUAAgent()
    result = agent.prepare_grading_transcript("any-task-id")
    assert result == agent.transcript_container_path


def test_run_task_spawns_correct_command(task_spec, monkeypatch):
    """Verify run_task builds the correct CLI command and spawns subprocess."""
    # Track the command that would be spawned
    spawned_commands = []

    original_popen = subprocess.Popen

    class MockPopen:
        def __init__(self, cmd, **kwargs):
            spawned_commands.append(cmd)
            self.returncode = 0
            self._stdout = b""
            self._stderr = b""

        def communicate(self, timeout=None):
            return (self._stdout, self._stderr)

        def kill(self):
            pass

        def wait(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", MockPopen)

    agent = TinyCUAAgent(tinycua_bin="/usr/bin/tinycua")
    execution = agent.run_task(task_spec)

    assert len(spawned_commands) == 1
    cmd = spawned_commands[0]
    assert cmd[0] == "/usr/bin/tinycua"
    assert cmd[1] == "run"
    assert cmd[2] == "Say hello"
    assert "--timeout" in cmd
    assert "--output-dir" in cmd
    assert "--workspace" in cmd
    assert "--model" in cmd
    assert execution.error is None


def test_run_task_returns_elapsed_time(task_spec, monkeypatch):
    """Verify run_task returns an AgentExecution with elapsed_time."""
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: type(
        "MockProc", (), {
            "communicate": lambda self, timeout=None: (b"", b""),
            "returncode": 0,
            "kill": lambda self: None,
            "wait": lambda self: None,
        }
    )())

    agent = TinyCUAAgent()
    execution = agent.run_task(task_spec)

    assert isinstance(execution, AgentExecution)
    assert execution.elapsed_time >= 0
    assert execution.error is None


def test_run_task_handles_timeout(task_spec, monkeypatch):
    """Verify run_task terminates subprocess on timeout and returns error."""
    class TimeoutPopen:
        def __init__(self, cmd, **kwargs):
            self.returncode = None

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

        def kill(self):
            self.returncode = -9

        def wait(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", TimeoutPopen)

    agent = TinyCUAAgent()
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "timed out" in execution.error.lower()


def test_run_task_handles_binary_not_found(task_spec, monkeypatch):
    """Verify run_task returns error when tinycua binary is not found."""
    def raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("tinycua not found")

    monkeypatch.setattr(subprocess, "Popen", raise_file_not_found)

    agent = TinyCUAAgent(tinycua_bin="nonexistent-tinycua")
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "not found" in execution.error.lower()


def test_run_task_creates_output_dir(task_spec, monkeypatch):
    """Verify run_task creates output directory if it doesn't exist."""
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: type(
        "MockProc", (), {
            "communicate": lambda self, timeout=None: (b"", b""),
            "returncode": 0,
            "kill": lambda self: None,
            "wait": lambda self: None,
        }
    )())

    agent = TinyCUAAgent()
    agent.run_task(task_spec)

    assert Path(task_spec.output_dir).exists()


def test_collect_usage_returns_expected_keys(task_spec, tmp_path):
    """Verify collect_usage returns dict with requests, total_tokens, cost."""
    agent = TinyCUAAgent()
    usage = agent.collect_usage("test-task-001", tmp_path, 1.0)

    assert "requests" in usage
    assert "total_tokens" in usage
    assert "cost" in usage
    assert isinstance(usage["requests"], int)
    assert usage["cost"] == 0.0


def test_collect_usage_parses_transcript(task_spec, tmp_path):
    """Verify collect_usage parses transcript.jsonl for token counts."""
    transcript_path = tmp_path / "transcript.jsonl"
    transcript_data = [
        {"type": "llm.request", "usage": {"total_tokens": 100}},
        {"type": "response.completed", "usage": {"total_tokens": 50}},
        {"type": "tool.call", "usage": {}},
    ]
    with open(transcript_path, "w") as f:
        for event in transcript_data:
            f.write(json.dumps(event) + "\n")

    agent = TinyCUAAgent()
    usage = agent.collect_usage("test-task-001", tmp_path, 1.0)

    assert usage["requests"] == 2  # llm.request + response.completed
    assert usage["total_tokens"] == 150
    assert usage["cost"] == 0.0


def test_collect_usage_missing_transcript_returns_zeroed(tmp_path):
    """Verify collect_usage returns zeroed values when transcript is missing."""
    agent = TinyCUAAgent()
    usage = agent.collect_usage("test-task-001", tmp_path, 1.0)

    assert usage["requests"] == 0
    assert usage["total_tokens"] is None
    assert usage["cost"] == 0.0


def test_run_task_creates_transcript_and_log(task_spec, monkeypatch):
    """Verify run_task creates transcript.jsonl and agent.log in output_dir after execution."""
    output_dir = Path(task_spec.output_dir)

    def mock_popen(cmd, **kwargs):
        # Simulate CLI writing transcript and log files
        transcript = output_dir / "transcript.jsonl"
        log = output_dir / "agent.log"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text('{"type": "llm.request", "usage": {"total_tokens": 10}}\n')
        log.write_text("task completed\n")

        class MockProc:
            returncode = 0
            def communicate(self, timeout=None):
                return (b"", b"")
            def kill(self):
                pass
            def wait(self):
                pass
        return MockProc()

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    agent = TinyCUAAgent()
    execution = agent.run_task(task_spec)

    assert execution.error is None
    assert (output_dir / "transcript.jsonl").exists()
    assert (output_dir / "agent.log").exists()


def test_run_task_creates_workspace(task_spec, monkeypatch):
    """Verify run_task creates workspace directory if it doesn't exist."""
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: type(
        "MockProc", (), {
            "communicate": lambda self, timeout=None: (b"", b""),
            "returncode": 0,
            "kill": lambda self: None,
            "wait": lambda self: None,
        }
    )())

    agent = TinyCUAAgent()
    agent.run_task(task_spec)

    assert Path(task_spec.workspace_path).exists()
```

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Integration test: `test_run_task_creates_transcript_and_log` — covers acceptance scenario #4
- [ ] Unit tests for `TinyCUAAgent` properties (`expects_gateway`, `transcript_container_path`)
- [ ] Unit tests for `run_task()` subprocess command construction
- [ ] Unit tests for `run_task()` timeout handling
- [ ] Unit tests for `run_task()` error handling (binary not found, non-zero exit)
- [ ] Unit tests for `collect_usage()` transcript parsing
- [ ] Unit tests for `collect_usage()` missing transcript file
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify adapter can be imported: `uv run python -c "from tinycua.wildclawbench.agent import TinyCUAAgent"`
- [ ] Verify `BaseAgent` ABC is satisfied (no abstract method errors on instantiation)

### Performance Considerations

- [x] Subprocess overhead is acceptable for benchmark task execution (tasks run for seconds/minutes)

## Proposed Changes

### Core Adapter

#### [NEW] `src/tinycua/tinycua/wildclawbench/__init__.py`

- **Description**: Package init for the WildClawBench adapter subpackage
- **Dependencies**: None

#### [NEW] `src/tinycua/tinycua/wildclawbench/base_agent.py`

- **Description**: Local copy of WildClawBench `BaseAgent` ABC, `AgentTaskSpec`, and `AgentExecution` dataclasses. Avoids hard dependency on WildClawBench.
- **Dependencies**: `abc`, `dataclasses`, `pathlib`, `subprocess`, `typing`

#### [NEW] `src/tinycua/tinycua/wildclawbench/agent.py`

- **Description**: `TinyCUAAgent` class implementing `BaseAgent`. Wraps `tinycua run` CLI as subprocess with timeout handling, usage collection, and transcript path management.
- **Dependencies**: `base_agent.py`, `subprocess`, `time`, `json`, `logging`

### Tests

#### [NEW] `src/tinycua/tests/unit/test_wildclawbench_agent.py`

- **Description**: Unit tests for adapter class properties, subprocess command construction, timeout handling, error handling, and usage collection
- **Dependencies**: `tinycua.wildclawbench.agent`, `tinycua.wildclawbench.base_agent`

#### [NEW] `src/tinycua/tests/integration/test_wildclawbench_integration.py`

- **Description**: Integration tests with mock task spec verifying end-to-end adapter behavior
- **Dependencies**: `tinycua.wildclawbench.agent`, `tinycua.wildclawbench.base_agent`, `pytest`

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/wildclawbench/` | New | WildClawBench adapter subpackage |
| `tinycua/wildclawbench/__init__.py` | New | Package init |
| `tinycua/wildclawbench/base_agent.py` | New | Local `BaseAgent` ABC, `AgentTaskSpec`, `AgentExecution` |
| `tinycua/wildclawbench/agent.py` | New | `TinyCUAAgent` adapter class |
| `tests/unit/test_wildclawbench_agent.py` | New | Unit tests |
| `tests/integration/test_wildclawbench_integration.py` | New | Integration tests |

## Data Model Changes

```python
# tinycua/wildclawbench/base_agent.py — Local copies from WildClawBench

@dataclass(frozen=True)
class AgentTaskSpec:
    task_id: str
    task: dict[str, Any]
    workspace_path: str
    prompt: str
    timeout_seconds: int
    output_dir: Path
    model: str
    thinking: str | None = None
    models_config: dict[str, Any] | None = None
    lobster: dict[str, Any] | None = None


@dataclass
class AgentExecution:
    elapsed_time: float
    error: str | None = None
    gateway_proc: subprocess.Popen[str] | None = None
    agent_proc: subprocess.Popen[str] | None = None


class BaseAgent(ABC):
    @property
    @abstractmethod
    def expects_gateway(self) -> bool: ...

    @property
    @abstractmethod
    def transcript_container_path(self) -> str: ...

    def prepare_grading_transcript(self, task_id: str) -> str:
        return self.transcript_container_path

    @abstractmethod
    def run_task(self, spec: AgentTaskSpec) -> AgentExecution: ...

    @abstractmethod
    def collect_usage(self, task_id: str, output_dir: Path, elapsed_time: float) -> dict[str, Any]: ...
```

## API Changes

### New Classes

| Class | Description |
|-------|-------------|
| `TinyCUAAgent` | WildClawBench adapter wrapping `tinycua run` CLI |
| `BaseAgent` | Local copy of WildClawBench ABC |
| `AgentTaskSpec` | Local copy of WildClawBench task spec dataclass |
| `AgentExecution` | Local copy of WildClawBench execution result dataclass |

### Constructor

```python
TinyCUAAgent(
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    tinycua_bin: str = "tinycua",
)
```

## Dependencies

### External Dependencies

- [x] No new external dependencies — uses only stdlib (`subprocess`, `json`, `logging`, `time`, `pathlib`)

### Internal Dependencies

- [x] Depends on existing `tinycua run` CLI entry point (`src/tinycua/tinycua/cli/run.py`)
- [x] Does NOT depend on WildClawBench package (local copies avoid hard dependency)
- [x] Does NOT modify `tinycua-sdk` public APIs

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| WildClawBench `BaseAgent` interface changes | Low | Local copy is easy to update; pin to known version |
| `tinycua run` CLI output format changes break usage parsing | Low | Usage parsing is best-effort; returns zeroed values on failure |
| Subprocess timeout doesn't kill child processes cleanly | Medium | Use `proc.kill()` + `proc.wait()`; monitor for zombie processes |
| Local model endpoint unreachable from subprocess | Medium | Subprocess inherits env vars; error captured in `AgentExecution` |
| WildClawBench transcript loader expects specific JSONL schema | Medium | Design events to match common JSONL format; test with actual loader |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-14*
