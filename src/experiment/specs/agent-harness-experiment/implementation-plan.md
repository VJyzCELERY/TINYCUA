# Implementation: Agent Harness Experiment

Build the minimum useful experiment harness for comparing Opencode, Hermes, OpenClaw, and TINYCUA on the same prompt. The implementation favors readable files, visible commands, and fail-loud placeholders over a comprehensive benchmark platform.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [ ] **.env file** — required variables documented in `src/experiment/.env.example`:
  ```text
  EXPERIMENT_LLM_PROVIDER=openai-compatible
  EXPERIMENT_LLM_MODEL=qwen3.5-9b
  EXPERIMENT_LLM_BASE_URL=http://localhost:1234/v1
  EXPERIMENT_LLM_API_KEY=<put_api_key_here>
  EXPERIMENT_TIMEOUT_SECONDS=900
  EXPERIMENT_TINYCUA_PROVIDER_TYPE=openai-chat-completions
  ```
- [ ] **Host endpoint note** — when running from containers, local model servers may need `http://host.docker.internal:1234/v1` instead of `http://localhost:1234/v1`.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Local OpenAI-compatible LLM server | Yes for real runs / No for stub tests | User-provided, example LM Studio on port `1234` | `curl http://localhost:1234/v1/models` |
| Docker daemon | Yes for real runs / No for pure unit tests | Docker Desktop / system service | `docker compose version` |

### Data / Fixtures

- [ ] **Stub docker executable** for integration tests, so tests prove runner behavior without real LLM credentials or images.
- [ ] **No seeded data** — experiments create their own result directories.

### Access / Permissions

- [ ] **LLM API key** — placeholder is allowed for local no-auth servers, but key must still flow through config for harnesses that require it.
- [ ] **Docker permissions** — user can run `docker compose` for manual verification.

### Developer Tooling

- [ ] **Runtime**: Python 3.12 for `src/experiment`; Docker for manual image builds.
- [ ] **Package manager**: uv.
- [ ] **Additional CLI tools**: npm inside Node-based containers only.

---

## Success Criteria — Integration Tests (TDD First)

Define these tests first under `src/experiment/tests/integration/test_run_experiment.py`. Keep them stdlib-heavy and stub Docker; real container builds stay manual.

```python
# Test file: src/experiment/tests/integration/test_run_experiment.py
"""Integration tests for the agent harness experiment runner."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def make_fake_docker(tmp_path: Path) -> Path:
    """Create a docker stub that records compose service invocations."""
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys\n"
        "service = sys.argv[sys.argv.index('run') + 2]\n"
        "pathlib.Path(os.environ['DOCKER_CALLS']).open('a').write(service + '\\n')\n"
        "print(f'{service} stdout')\n"
        "print(f'{service} stderr', file=sys.stderr)\n"
        "sys.exit(7 if service == 'hermes' else 0)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    return docker


def test_runner_invokes_all_agents_in_order_and_writes_metadata(tmp_path: Path):
    """One prompt runs all four services, even when Hermes fails."""
    calls = tmp_path / "calls.txt"
    make_fake_docker(tmp_path)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(calls),
    }

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "run_experiment.py"),
            "--num",
            "1",
            "--prompt",
            "compare harnesses",
            "--output-root",
            str(tmp_path / "results"),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert calls.read_text().splitlines() == ["opencode", "hermes", "openclaw", "tinycua"]
    for agent in ["opencode", "hermes", "openclaw", "tinycua"]:
        root = tmp_path / "results" / agent / "experiment-1"
        assert (root / "prompt.txt").read_text() == "compare harnesses"
        meta = json.loads((root / "metadata.json").read_text())
        assert meta["agent"] == agent
        assert meta["experiment_num"] == 1
        assert "duration_seconds" in meta
    assert json.loads((tmp_path / "results" / "hermes" / "experiment-1" / "metadata.json").read_text())["exit_code"] == 7


def test_runner_rejects_empty_prompt_before_docker(tmp_path: Path):
    """Whitespace prompts fail before invoking Docker."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "run_experiment.py"), "--num", "1", "--prompt", "   "],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "prompt" in result.stderr.lower()
```

### Key Test Scenarios

- [ ] **Sequential stub run**: all four Docker Compose services are invoked in order and write prompt/log/metadata artifacts.
- [ ] **Failure continuation**: a non-zero service exit code is recorded and later services still run.
- [ ] **Input guard**: empty prompts fail before Docker is invoked.
- [ ] **Overwrite guard**: an existing `experiment-{num}` path fails unless `--overwrite` is set.

## Verification Plan

### Automated Tests

- [ ] Integration tests above — must pass for implementation to be complete.
- [ ] Unit tests for runner helpers — prompt loading, metadata generation, output path selection, overwrite behavior.
- [ ] Static Dockerfile/Compose tests — assert four services, four named volumes, TINYCUA local copy/install commands, and shared `env_file`.
- [ ] Existing experiment tests: `cd src/experiment && uv run pytest`.

### Manual Verification

- [ ] Copy `.env.example` to `.env` and adjust `EXPERIMENT_LLM_BASE_URL` if container-to-host networking needs `host.docker.internal`.
- [ ] Build images: `cd src/experiment && docker compose build`.
- [ ] Run one prompt: `cd src/experiment && uv run python run_experiment.py --num 1 --prompt "write hello.txt"`.
- [ ] Inspect each agent result directory for `prompt.txt`, `stdout.log`, `stderr.log`, and `metadata.json`.

### Performance Considerations

- [ ] Record wall-clock `duration_seconds` for each service run.
- [ ] Do not add caching, databases, or metrics services in MVP.

## Proposed Changes

### Experiment Python Subproject

#### [NEW] `src/experiment/pyproject.toml`

- **Description**: Minimal Python project so `cd src/experiment && uv run pytest` and `uv run python run_experiment.py` work.
- **Rationale**: Keeps experiment tooling scoped to the subproject.

#### [NEW] `src/experiment/run_experiment.py`

- **Description**: CLI runner that validates prompt input, computes result paths, invokes Docker Compose services in fixed order, captures stdout/stderr, and writes `metadata.json`.
- **Rationale**: Centralizes sequencing and timing in one boring stdlib script.

#### [NEW] `src/experiment/tests/integration/test_run_experiment.py`

- **Description**: Stub-Docker tests for sequential execution, failure continuation, and artifact layout.
- **Rationale**: Proves behavior without real images or LLM credentials.

#### [NEW] `src/experiment/tests/unit/test_run_experiment.py`

- **Description**: Unit tests for prompt loading, metadata shape, and overwrite guard.
- **Rationale**: Catches runner edge cases without spawning subprocesses.

### Compose and Containers

#### [NEW] `src/experiment/docker-compose.yml`

- **Description**: Four services (`opencode`, `hermes`, `openclaw`, `tinycua`), shared `env_file: .env`, named volumes, and `host.docker.internal:host-gateway`.
- **Rationale**: Enforces separate containers and per-agent persistent storage.

#### [NEW] `src/experiment/.env.example`

- **Description**: Example shared provider/model config using `http://localhost:1234/v1`, `qwen3.5-9b`, and `<put_api_key_here>`.
- **Rationale**: One knob set for comparable runs.

#### [NEW] `src/experiment/docker/tinycua.Dockerfile`

- **Description**: Python 3.12 image that copies and installs local `src/tinycua-sdk` then `src/tinycua`; entrypoint runs `tinycua run` with `--dir`.
- **Rationale**: Required by FR-009; experiments test local branch code.

#### [NEW] `src/experiment/docker/opencode.Dockerfile`

- **Description**: Node image installing `opencode-ai`, with visible config setup for shared model/provider values.
- **Rationale**: Separate Opencode container with readable failure if config is wrong.

#### [NEW] `src/experiment/docker/openclaw.Dockerfile`

- **Description**: Node or official OpenClaw image installing `openclaw@latest`, with startup config writing `~/.openclaw/openclaw.json`.
- **Rationale**: Separate OpenClaw container with visible provider mapping.

#### [NEW] `src/experiment/docker/hermes.Dockerfile`

- **Description**: Hermes image using the simplest verified install path, with explicit provider/model setup.
- **Rationale**: Separate Hermes container; fail loudly if local OpenAI-compatible URL is unsupported.

#### [NEW] `src/experiment/docker/run-agent.sh`

- **Description**: Small shared shell wrapper, if it stays shorter than four duplicated wrappers, for writing prompt/log files and running agent commands.
- **Rationale**: Optional. Skip it if duplication is clearer.

### Documentation

#### [NEW] `src/experiment/README.md`

- **Description**: Short usage notes for `.env`, build, run, and result inspection.
- **Rationale**: Only enough docs to run the experiment.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `src/experiment` | New | Lightweight experiment subproject. |
| `run_experiment.py` | New | Sequential runner and metadata collector. |
| Docker Compose | New | Four isolated services and volumes. |
| TINYCUA image | New | Installs local packages and runs `tinycua run`. |
| Agent images | New | Harness-specific install/run boundaries. |

## Data Model Changes

```python
ExperimentResult:
    experiment_num: int
    agent: str
    prompt: str
    started_at: str
    ended_at: str
    duration_seconds: float
    exit_code: int
    status: str
```

## API Changes

### New CLI

| Command | Description |
|---------|-------------|
| `uv run python run_experiment.py --num N --prompt "..."` | Run prompt across all harnesses. |
| `uv run python run_experiment.py --num N --prompt-file prompt.txt` | Run prompt loaded from a file. |
| `uv run python run_experiment.py --num N --prompt "..." --overwrite` | Replace existing result directories. |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | latest compatible | Tests only. |
| Docker Compose | installed on host | Manual runs and real container execution. |
| npm packages inside images | latest/pinned later | Agent harness CLIs. |

### Internal Dependencies

- [ ] TINYCUA image depends on local `src/tinycua-sdk` and `src/tinycua` packages.
- [ ] No dependency on a database, web app, or benchmark service.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent CLI or package name changes | Medium | Keep commands visible and fail-loud; update one Dockerfile. |
| Local model URL is wrong inside containers | Medium | Document `host.docker.internal` and add Compose `extra_hosts`. |
| Opencode/OpenClaw/Hermes config needs more than env vars | Medium | Generate minimal config files at startup; preserve setup stderr. |
| TINYCUA CLI flags drift | Medium | Test Dockerfile/entrypoint for `tinycua run --dir`; avoid stale `--workspace` flags. |
| Real LLM runs are flaky | Low | Stub Docker for automated tests; keep real runs manual. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-18*
