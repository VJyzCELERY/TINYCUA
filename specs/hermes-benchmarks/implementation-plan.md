# Implementation: Hermes-Agent Benchmark Integration

Enable Hermes agent (from InternLM/WildClawBench) to run as a first-class benchmark target alongside TinyCUAAgent, using the same WildClawBench harness and grading pipeline, with side-by-side result comparison.

## Context

- **Spec Reference**: `specs/hermes-benchmarks/spec.md`
- **Design Reference**: `specs/hermes-benchmarks/design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [ ] **.env file** — required variables:
  ```
  HERMES_API_KEY=sk-...
  ```
- [ ] **None** — this feature has no additional configuration dependencies beyond what already exists for TinyCUA benchmarks

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Docker daemon | Yes | `open --background -a Docker` | `docker info` |
| Hermes agent Docker image | Yes | `docker build -f Dockerfile.hermes -t hermes-agent .` | `docker run --rm hermes-agent --help` |

### Data / Fixtures

- [ ] **Small task subset for smoke tests** — e.g., 3 tasks from each category (12 total)
- [ ] **Mock API server** for testing Hermes agent without external model dependency (optional for CI)

### Access / Permissions

- [ ] API key for external LLM provider (e.g., OpenAI, Anthropic) set as `HERMES_API_KEY`
- [ ] **None** — no firewall/VPN/special access required

### Developer Tooling

- [ ] **Runtime**: Python >=3.12
- [ ] **Package manager**: uv
- [ ] **Additional CLI tools**: Docker, `yaml` Python library (already a transitive dependency)
- [ ] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_hermes_agent_integration.py
"""Integration tests for Hermes agent WildClawBench adapter."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from tinycua.wildclawbench.base_agent import AgentExecution, AgentTaskSpec
from tinycua.wildclawbench.hermes_agent import HermesAgent
from tinycua.scripts.benchmark_config import BenchmarkConfig
from tinycua.scripts.run_benchmark import run_full_benchmark


@pytest.fixture
def hermes_config(tmp_path):
    """Create a temporary Hermes config YAML file."""
    config = {
        "model": "gpt-4",
        "api_base": "https://api.openai.com/v1",
        "api_key_env": "HERMES_API_KEY",
        "temperature": 0.0,
        "max_tokens": 4096,
        "timeout": 120,
    }
    config_path = tmp_path / "hermes-config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return str(config_path)


@pytest.fixture
def task_spec(tmp_path):
    """Create a minimal AgentTaskSpec for testing."""
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "output"
    return AgentTaskSpec(
        task_id="hermes-test-001",
        task={"type": "simple", "prompt": "test"},
        workspace_path=str(workspace),
        prompt="Write a single sentence about penguins.",
        timeout_seconds=60,
        output_dir=output_dir,
        model="gpt-4",
    )


def test_hermes_agent_properties():
    """Verify HermesAgent static properties match BaseAgent contract."""
    agent = HermesAgent(config_path="dummy.yaml")
    assert agent.expects_gateway is False
    assert isinstance(agent.transcript_container_path, str)
    assert agent.transcript_container_path.endswith("transcript.jsonl")


def test_hermes_agent_config_validation_invalid_path():
    """Verify HermesAgent raises FileNotFoundError for missing config."""
    with pytest.raises(FileNotFoundError):
        HermesAgent(config_path="/nonexistent/path.yaml")


def test_hermes_agent_config_validation_missing_field(tmp_path):
    """Verify HermesAgent raises ValueError for missing required config fields."""
    config_path = tmp_path / "bad-config.yaml"
    with open(config_path, "w") as f:
        yaml.dump({"model": "gpt-4"}, f)  # missing api_base, api_key_env
    with pytest.raises(ValueError, match="api_base"):
        HermesAgent(config_path=str(config_path))


def test_hermes_agent_docker_command_structure(task_spec, hermes_config, monkeypatch):
    """Verify HermesAgent builds correct docker run command."""
    spawned_commands = []

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

    # Ensure API key env var is set for validation
    monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

    agent = HermesAgent(config_path=hermes_config)
    execution = agent.run_task(task_spec)

    assert len(spawned_commands) == 1
    cmd = spawned_commands[0]
    assert cmd[0] == "docker"
    assert cmd[1] == "run"
    assert "--rm" in cmd
    assert "hermes-agent" in cmd
    assert execution.error is None


def test_hermes_agent_missing_api_key(hermes_config, task_spec, monkeypatch):
    """Verify HermesAgent returns error when required API key env var is missing."""
    # Remove the API key from environment
    monkeypatch.delenv("HERMES_API_KEY", raising=False)

    agent = HermesAgent(config_path=hermes_config)
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "HERMES_API_KEY" in execution.error


def test_hermes_agent_docker_build_failure(hermes_config, task_spec, monkeypatch):
    """Verify HermesAgent handles Docker build failure gracefully."""
    def raise_build_error(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["docker", "build"])

    monkeypatch.setattr(subprocess, "run", raise_build_error)
    monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

    agent = HermesAgent(config_path=hermes_config)
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "build" in execution.error.lower() or "docker" in execution.error.lower()


def test_hermes_agent_container_timeout(hermes_config, task_spec, monkeypatch):
    """Verify HermesAgent handles container timeout gracefully."""
    class TimeoutPopen:
        def __init__(self, cmd, **kwargs):
            self._cmd = cmd

        def communicate(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=self._cmd, timeout=timeout)

        def kill(self):
            pass

        def wait(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", TimeoutPopen)
    monkeypatch.setitem(os.environ, "HERMES_API_KEY", "sk-test-key")

    agent = HermesAgent(config_path=hermes_config)
    execution = agent.run_task(task_spec)

    assert execution.error is not None
    assert "timed out" in execution.error.lower()


def test_hermes_collect_usage_empty(task_spec, tmp_path, hermes_config):
    """Verify collect_usage returns zeroed values when no artifacts exist."""
    agent = HermesAgent(config_path=hermes_config)
    usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)

    assert usage["requests"] == 0
    assert usage["total_tokens"] is None
    assert usage["cost"] == 0.0


def test_hermes_collect_usage_with_transcript(task_spec, tmp_path, hermes_config):
    """Verify collect_usage parses Hermes transcript for usage data."""
    transcript_path = tmp_path / "transcript.jsonl"
    transcript_data = [
        {"type": "llm.request", "usage": {"total_tokens": 100}},
        {"type": "response.completed", "usage": {"total_tokens": 50}},
    ]
    with open(transcript_path, "w") as f:
        for event in transcript_data:
            f.write(json.dumps(event) + "\n")

    agent = HermesAgent(config_path=hermes_config)
    usage = agent.collect_usage("hermes-test-001", tmp_path, 1.0)

    assert usage["requests"] == 2
    assert usage["total_tokens"] == 150


def test_benchmark_cli_selects_hermes_agent(hermes_config, tmp_path, monkeypatch):
    """Verify --agent-backend hermesagent selects HermesAgent in the benchmark pipeline."""
    called_with_agent = []

    def mock_run_benchmark(config, output_dir, tasks=None):
        called_with_agent.append(config)
        return {"summary": {}, "tasks": []}

    monkeypatch.setattr(
        "tinycua.scripts.run_benchmark.run_full_benchmark",
        mock_run_benchmark,
    )

    from tinycua.scripts.run_benchmark import main
    import sys

    test_args = [
        "run_benchmark.py",
        "--agent-backend", "hermesagent",
        "--hermes-config", hermes_config,
        "--output-dir", str(tmp_path),
        "--tasks", "task_001,task_002",
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    # parse_args will inject --agent-backend and --hermes-config
    # This test verifies the CLI arg propagation works
    from tinycua.scripts.benchmark_config import parse_args
    args = parse_args(test_args[1:])
    assert args.agent_backend == "hermesagent"
    assert args.hermes_config == hermes_config


def test_side_by_side_report_comparison(tmp_path, hermes_config):
    """Verify side-by-side report compares TinyCUA and Hermes results correctly."""
    from tinycua.scripts.compare_results import compare_results

    tinycua_results = {
        "summary": {"average_score": 0.75, "successful_tasks": 45},
        "tasks": [
            {"task_id": "task_001", "score": 1.0, "status": "success", "elapsed_time": 10.0},
            {"task_id": "task_002", "score": 0.0, "status": "failed", "elapsed_time": 5.0},
        ],
    }
    hermes_results = {
        "summary": {"average_score": 0.50, "successful_tasks": 30},
        "tasks": [
            {"task_id": "task_001", "score": 1.0, "status": "success", "elapsed_time": 15.0},
            {"task_id": "task_002", "score": 0.0, "status": "timeout", "elapsed_time": 60.0},
        ],
    }

    comparison = compare_results(tinycua_results, hermes_results)

    assert "agent_a" in comparison
    assert "agent_b" in comparison
    assert comparison["agent_a"]["name"] == "tinycua"
    assert comparison["agent_b"]["name"] == "hermes"
    assert "per_task_comparison" in comparison
    assert len(comparison["per_task_comparison"]) == 2
```

### Key Test Scenarios

- [ ] **Scenario 1**: HermesAgent implements BaseAgent ABC correctly — properties, run_task, collect_usage
- [ ] **Scenario 2**: Config validation rejects missing/invalid config with clear errors
- [ ] **Scenario 3**: Docker build failure is handled gracefully (logged, not crash)
- [ ] **Scenario 4**: Missing API key env var is detected and reported
- [ ] **Scenario 5**: Container timeout is handled the same way as TinyCUA
- [ ] **Scenario 6**: Benchmark CLI correctly selects HermesAgent via `--agent-backend hermesagent`
- [ ] **Scenario 7**: Side-by-side comparison report merges two `summary_all.json` files

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for `HermesAgent` — config validation, Docker command construction, error handling
- [ ] Unit tests for `compare_results` — side-by-side comparison logic
- [ ] Existing test suite — confirm no regressions: `uv run pytest`

### Manual Verification

- [ ] Run Hermes agent against 3 WildClawBench tasks and verify transcript output
- [ ] Run full 60-task Hermes benchmark and compare scores
- [ ] Verify setup docs by following them step-by-step

### Performance Considerations

- [ ] Hermes Docker image build time (multi-stage build, layer caching)
- [ ] Transcript file size for large runs (verify no OOM on 60 tasks)

## Proposed Changes

### Hermes Agent Module — New

#### [NEW] `src/tinycua/tinycua/wildclawbench/hermes_agent.py`

- **[Description]**: New `HermesAgent` class implementing `BaseAgent` ABC. Runs Hermes via Docker container, builds command, handles errors.
- **[Dependencies]**: `tinycua.wildclawbench.base_agent`, `yaml`, `os`, `subprocess`, `pathlib`, `logging`
- **[Key methods]**:
  - `__init__(self, config_path: str)` — loads and validates YAML config
  - `_load_config(path)` — parse YAML, validate required fields (`model`, `api_base`, `api_key_env`)
  - `run_task(spec)` — build docker command, spawn subprocess, return AgentExecution
  - `collect_usage(task_id, output_dir, elapsed_time)` — parse transcript JSONL
  - `_build_docker_command(spec)` — construct `docker run` args with volume mounts, env vars, config
  - `_ensure_image()` — check if image exists locally, build if needed

#### [NEW] `src/tinycua/tinycua/scripts/compare_results.py`

- **[Description]**: Module for side-by-side comparison of two `summary_all.json` results (TinyCUA vs Hermes).
- **[Key function]**: `compare_results(tinycua_data, hermes_data) -> dict` — merges per-task scores, computes deltas, writes comparison JSON.
- **[Output]**: `comparison.json` with per-task and aggregate delta.

### Config Validation — New

#### [NEW] `src/tinycua/tinycua/wildclawbench/hermes_config.py`

- **[Description]**: HermesConfig dataclass and YAML loader. Validates required fields, types, and env var existence.
- **[Key types]**:
  ```python
  @dataclass
  class HermesConfig:
      model: str
      api_base: str
      api_key_env: str
      temperature: float = 0.0
      max_tokens: int = 4096
      timeout: int = 120
  ```

### Docker Infrastructure — New

#### [NEW] `src/tinycua/docker/Dockerfile.hermes`

- **[Description]**: Multi-stage Dockerfile for Hermes agent. Base on upstream WildClawBench Hermes image, pin to commit `86d7144`.
- **[Rationale]**: Docker isolation per WildClawBench harness contract.

#### [NEW] `src/tinycua/scripts/build_hermes_image.sh`

- **[Description]**: Shell script to build the Hermes Docker image with layer caching.
- **[Usage]**: `bash scripts/build_hermes_image.sh`

### Benchmark Runner — Modified

#### [MODIFY] `src/tinycua/tinycua/scripts/benchmark_config.py`

- **[Description]**: Add `--agent-backend` and `--hermes-config` CLI arguments.
- **[Changes]**:
  - Add `agent_backend: str = "tinycua"` field to `BenchmarkConfig`
  - Add `hermes_config_path: str | None = None` field to `BenchmarkConfig`
  - Add `--agent-backend` argparse argument with choices `["tinycua", "hermesagent"]`
  - Add `--hermes-config` argparse argument for path to Hermes config YAML

#### [MODIFY] `src/tinycua/tinycua/scripts/run_benchmark.py`

- **[Description]**: Refactor `run_full_benchmark` to accept a `BaseAgent` instance instead of hardcoding `TinyCUAAgent`. Add agent factory logic.
- **[Changes]**:
  - Change `run_full_benchmark` signature to accept `agent: BaseAgent | None = None`
  - Add `_create_agent(config)` factory function that returns `TinyCUAAgent` or `HermesAgent` based on `config.agent_backend`
  - Update `main()` to use the factory and pass agent to `run_full_benchmark`
  - Import `HermesAgent` and `compare_results`

### WildClawBench Package — Modified

#### [MODIFY] `src/tinycua/tinycua/wildclawbench/__init__.py`

- **[Description]**: Export `HermesAgent` from the package.
- **[Changes]**: Add `from tinycua.wildclawbench.hermes_agent import HermesAgent` and add to `__all__`.

### Testing — New

#### [NEW] `src/tinycua/tests/unit/test_hermes_agent.py`

- **[Description]**: Unit tests for HermesAgent config validation, Docker command construction, error handling, usage collection.

#### [NEW] `src/tinycua/tests/unit/test_compare_results.py`

- **[Description]**: Unit tests for side-by-side comparison logic.

#### [NEW] `src/tinycua/tests/integration/test_hermes_agent_integration.py`

- **[Description]**: Integration tests from the TDD section above.

### Documentation — New

#### [NEW] `src/tinycua/docs/hermes-benchmark-setup.md`

- **[Description]**: Step-by-step setup guide for running Hermes agent benchmark.
- **[Sections]**: Prerequisites, Docker Setup, Config File, Running, Comparing Results.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.wildclawbench.hermes_agent` | New | Hermes agent adapter implementing BaseAgent |
| `tinycua.wildclawbench.hermes_config` | New | HermesConfig dataclass & YAML loader |
| `tinycua.scripts.compare_results` | New | Side-by-side comparison module |
| `tinycua.scripts.run_benchmark` | Modify | Accept BaseAgent, add agent factory |
| `tinycua.scripts.benchmark_config` | Modify | Add --agent-backend, --hermes-config args |
| `tinycua.wildclawbench.__init__` | Modify | Export HermesAgent |
| `docker/Dockerfile.hermes` | New | Hermes agent Docker image |
| `scripts/build_hermes_image.sh` | New | Build helper script |

## Data Model Changes

```python
# New types
@dataclass
class HermesConfig:
    model: str
    api_base: str
    api_key_env: str
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: int = 120

# Modified types
@dataclass
class BenchmarkConfig:
    model_name: str = "llama3"
    base_url: str = "http://localhost:8000/v1"
    api_key: str | None = None
    timeout_seconds: int = 600
    preserve_artifacts: bool = True
    verbose: bool = False
    concurrent_tasks: int = 1
    agent_backend: str = "tinycua"          # NEW
    hermes_config_path: str | None = None   # NEW
```

## API Changes

### New CLI Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--agent-backend` | choice | `tinycua` | Agent to use: `tinycua` or `hermesagent` |
| `--hermes-config` | str | None | Path to Hermes agent config YAML file |

### New Scripts

| Script | Description |
|--------|-------------|
| `python -m tinycua.scripts.compare_results <a.json> <b.json>` | Generate side-by-side comparison report |
| `bash scripts/build_hermes_image.sh` | Build Hermes Docker image |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyYAML | (included, transitive via tinycua-sdk) | Parse Hermes config YAML |

### Internal Dependencies

- [ ] Depends on `BaseAgent` ABC (`tinycua.wildclawbench.base_agent`) — already exists
- [ ] Depends on `Docker` installed on the host machine
- [ ] Blocks side-by-side comparison of TinyCUA vs Hermes benchmark results

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hermes Docker image is large (>5GB) | Medium | Multi-stage build, document expected size; allow image reuse across runs |
| Hermes API dependency (external model) | High | Document required env vars; fail fast with clear error message |
| Transcript format mismatch | Low | Validate transcript schema after Hermes run; compare against OpenClaw format |
| Grading incompatibility | Medium | Reuse existing grading pipeline as-is; run smoke test with known scores to verify |
| Upstream Hermes agent changes | Low | Pin to specific commit (`86d7144`); update pin intentionally |

---

*Generated from specs/hermes-benchmarks/spec.md and specs/hermes-benchmarks/design.md*
*Last updated: 2026-06-15*
