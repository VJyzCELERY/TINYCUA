# Implementation: TinyCUA Benchmark Docker Image

Provide a Docker image that packages the TinyCUA prototype for WildClawBench benchmark evaluation, enabling TinyCUA to run as a comparable agent harness alongside OpenClaw, Claude Code, Codex CLI, and Hermes Agent.

## Context

- **Spec Reference**: `./spec.md` — TinyCUA Benchmark Docker Image specification
- **Design Reference**: `./design.md` — Docker image architecture and container lifecycle design
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [ ] **.env file** — required variables for container runtime:
  ```
  TINYCUA_BASE_URL=http://host.docker.internal:1234/v1
  TINYCUA_API_KEY=
  TINYCUA_MODEL=local-model
  BRAVE_API_KEY=xxx
  ```
- [ ] **None** — build-time has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Docker | Yes | Docker Desktop / dockerd | `docker info` |
| Local model endpoint | Yes (for runtime) | vLLM / Ollama / LM Studio | `curl $TINYCUA_BASE_URL/health` |

### Data / Fixtures

- [ ] **None** — no data or fixtures needed at build time

### Access / Permissions

- [ ] **Docker access** — user must be in the `docker` group or run as root
- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.11+, Docker 24+
- [ ] **Package manager**: uv
- [ ] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/test_docker_image.py
"""Integration tests for Docker image build and container lifecycle."""

import subprocess
import pytest


IMAGE_TAG = "tinycua-benchmark:test"


class TestDockerfileBuild:
    """Verify the Dockerfile builds successfully."""

    def test_dockerfile_exists(self):
        """Dockerfile exists at the project root."""
        from pathlib import Path

        dockerfile = Path(__file__).parent.parent.parent.parent / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile must exist at project root"

    def test_docker_image_builds(self):
        """Docker image builds without errors."""
        result = subprocess.run(
            ["docker", "build", "-t", IMAGE_TAG, "."],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, f"Build failed:\n{result.stderr}"

    def test_image_size_under_2gb(self):
        """Built image is under 2GB."""
        result = subprocess.run(
            ["docker", "image", "inspect", IMAGE_TAG, "--format", "{{.Size}}"],
            capture_output=True,
            text=True,
        )
        size_bytes = int(result.stdout.strip())
        size_gb = size_bytes / (1024**3)
        assert size_gb < 2.0, f"Image size {size_gb:.2f}GB exceeds 2GB target"


class TestContainerStartup:
    """Verify the container starts and reaches a ready state."""

    def test_container_starts(self):
        """Container starts without errors."""
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-e", "TINYCUA_BASE_URL=http://example.com/v1",
                IMAGE_TAG,
                "echo", "ready",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Container failed to start:\n{result.stderr}"
        assert "ready" in result.stdout

    def test_container_fails_without_model_endpoint(self):
        """Container fails with clear error when TINYCUA_BASE_URL is missing."""
        result = subprocess.run(
            ["docker", "run", "--rm", IMAGE_TAG, "exit", "0"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Entry point should reject missing endpoint
        assert result.returncode != 0 or "TINYCUA_BASE_URL" in result.stderr


class TestWorkspaceMounting:
    """Verify /tmp_workspace mounting and read/write operations."""

    def test_workspace_is_writable(self):
        """Container can write to /tmp_workspace."""
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", "/tmp/test-workspace:/tmp_workspace",
                "-e", "TINYCUA_BASE_URL=http://example.com/v1",
                IMAGE_TAG,
                "sh", "-c", "touch /tmp_workspace/test-file && echo ok",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Workspace write failed:\n{result.stderr}"
        assert "ok" in result.stdout


class TestEnvironmentVariables:
    """Verify environment variable injection and accessibility."""

    def test_env_vars_accessible(self):
        """Injected environment variables are accessible inside the container."""
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-e", "TINYCUA_BASE_URL=http://example.com/v1",
                "-e", "BRAVE_API_KEY=test-key-123",
                IMAGE_TAG,
                "sh", "-c", "echo $BRAVE_API_KEY",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "test-key-123" in result.stdout


class TestTinyCUAInstalled:
    """Verify TinyCUA is installed and the CLI is available."""

    def test_tinycua_cli_available(self):
        """tinycua CLI is available in the container."""
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-e", "TINYCUA_BASE_URL=http://example.com/v1",
                IMAGE_TAG,
                "tinycua", "--help",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"tinycua CLI not found:\n{result.stderr}"
        assert "tinycua" in result.stdout.lower()

    def test_tinycua_benchmark_subcommand(self):
        """tinycua benchmark subcommand is available."""
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-e", "TINYCUA_BASE_URL=http://example.com/v1",
                IMAGE_TAG,
                "tinycua", "benchmark", "--help",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"benchmark subcommand not found:\n{result.stderr}"
```

### Key Test Scenarios

- [ ] **Scenario 1**: Dockerfile builds successfully — the image contains all dependencies
- [ ] **Scenario 2**: Container starts and reaches ready state — entry point validates config
- [ ] **Scenario 3**: Workspace mounting — `/tmp_workspace` is accessible and writable
- [ ] **Scenario 4**: Environment variable injection — `BRAVE_API_KEY` and model config are accessible
- [ ] **Scenario 5**: TinyCUA CLI is installed — `tinycua` command and `benchmark` subcommand work
- [ ] **Edge case**: Missing `TINYCUA_BASE_URL` — container exits with clear error

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Build the image on a development machine: `docker build -t tinycua-benchmark .`
- [ ] Run the container with a real local model endpoint (e.g., Ollama, LM Studio)
- [ ] Verify the image size is under 2GB: `docker image inspect tinycua-benchmark --format '{{.Size}}'`
- [ ] Check container logs for any missing dependencies or configuration issues

### Performance Considerations

- [ ] Image build time should be under 5 minutes with layer caching
- [ ] Container startup should be under 10 seconds

## Proposed Changes

### Docker Configuration

#### [NEW] `Dockerfile`

- **Description**: Multi-stage Dockerfile that builds the TinyCUA benchmark image
- **Base**: `python:3.11-slim` (minimal footprint, ~150MB)
- **Dependencies**: System packages (bash, coreutils, curl, git), uv, Python dependencies, TinyCUA + tinycua-sdk
- **Rationale**: Provides a self-contained, reproducible runtime for benchmark execution

#### [NEW] `scripts/entrypoint.sh`

- **Description**: Container entry point script that validates environment, configures TinyCUA, and executes the benchmark task
- **Rationale**: Separates pre-execution validation from Python code; provides clearer error messages for configuration issues

#### [NEW] `docker-compose.benchmark.yml`

- **Description**: Optional Docker Compose file for local development and testing
- **Rationale**: Simplifies running the benchmark with proper networking and volume mounts

### CLI Changes

#### [MODIFY] `src/tinycua/tinycua/cli/main.py`

- **Description**: Add `benchmark` subcommand to the CLI with `run` sub-subcommand
- **Rationale**: The design specifies `tinycua benchmark run` as the entry point for benchmark execution (per Milestone 5.1 CLI contract)

#### [NEW] `src/tinycua/tinycua/cli/benchmark.py`

- **Description**: Benchmark subcommand implementation — parses args, runs TinyCUA agent with benchmark-specific defaults (workspace, output, transcript paths)
- **Rationale**: Separates benchmark execution logic from the generic `run` command

### Documentation

#### [NEW] `src/tinycua/docs/benchmark/README.md`

- **Description**: Usage documentation for the benchmark Docker image — build instructions, configuration, networking, troubleshooting
- **Rationale**: FR-009 requires documentation of all configuration options

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `Dockerfile` | New | Multi-stage build for TinyCUA benchmark image |
| `scripts/entrypoint.sh` | New | Container entry point with environment validation |
| `docker-compose.benchmark.yml` | New | Optional compose file for local development |
| `src/tinycua/tinycua/cli/main.py` | Modify | Add `benchmark` subcommand dispatch |
| `src/tinycua/tinycua/cli/benchmark.py` | New | Benchmark run command implementation |
| `src/tinycua/docs/benchmark/README.md` | New | Usage documentation |

## Data Model Changes

```yaml
# Container configuration (conceptual)
ContainerConfig:
  base_image: "python:3.11-slim"
  python_version: "3.11"
  tinycua_source: "./"  # COPY context
  env_vars:
    TINYCUA_BASE_URL: str      # Required
    TINYCUA_API_KEY: str       # Optional (default: "")
    TINYCUA_MODEL: str         # Optional (default: sensible local model identifier)
    BRAVE_API_KEY: str         # Optional
  volumes:
    /tmp_workspace: str           # Task workspace mount point
```

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| python | 3.11-slim | Base image |
| uv | latest | Package manager inside container |

### Internal Dependencies

- [ ] Depends on Milestone 5.1 CLI runtime entry point (`tinycua` command)
- [ ] Depends on `tinycua-sdk` package

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Image size exceeds 2GB target | Medium | Use slim base, minimize layers, remove build deps after install |
| Local model endpoint unreachable from container | High | Document `--add-host=host.docker.internal:host-gateway` for Linux |
| Missing system dependencies for WildClawBench tasks | Medium | Research task requirements, add dependencies incrementally |
| Browser/search tools add significant size | Low | Make optional, document for specific task categories |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-14*
