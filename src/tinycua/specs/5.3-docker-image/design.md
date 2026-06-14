# Design Document: TinyCUA Benchmark Docker Image

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-14

---

## Overview

This design specifies the Docker image for TinyCUA benchmark execution within WildClawBench. The image packages the TinyCUA prototype with all dependencies, configures access to local model endpoints, and provides a standardized runtime environment for benchmark task execution. The design focuses on container lifecycle, dependency management, configuration injection, and artifact preservation.

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    TinyCUA Benchmark Container               │
├─────────────────────────────────────────────────────────────┤
│  Base: python:3.11-slim                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  System Dependencies                                     │ │
│  │  - shell utilities (bash, coreutils)                     │ │
│  │  - file operations (find, grep, sed)                     │ │
│  │  - network tools (curl, wget)                            │ │
│  │  - browser/search (chromium, geckodriver) [optional]     │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Python Environment                                      │ │
│  │  - tinycua package (from local source)                   │ │
│  │  - tinycua-sdk dependency                                │ │
│  │  - OpenAI client library                                 │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Runtime Configuration                                   │ │
│  │  - TINYCUA_MODEL_ENDPOINT (env var)                      │ │
│  │  - TINYCUA_MODEL_API_KEY (env var)                       │ │
│  │  - BRAVE_API_KEY (env var)                               │ │
│  │  - /tmp_workspace (volume mount)                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Entry Point                                             │ │
│  │  - tinycua benchmark runner                              │ │
│  │  - Task prompt processing                                │ │
│  │  - Artifact collection                                   │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `Dockerfile` | New | Multi-stage build for TinyCUA benchmark image |
| `docker-compose.benchmark.yml` | New | Optional compose file for local development |
| `scripts/entrypoint.sh` | New | Container entry point script |
| `docs/benchmark/README.md` | New | Usage documentation for the benchmark image |
| `specs/5.3-docker-image/spec.md` | New | This specification |
| `specs/5.3-docker-image/design.md` | New | This design document |

---

## Data Model

### Container Configuration

```yaml
# Conceptual configuration shape (not final implementation)
ContainerConfig:
  base_image: str                    # "python:3.11-slim"
  python_version: str                # "3.11"
  tinycua_source: str                # Path to tinycua source for COPY
  dependencies: list[str]            # System packages to install
  env_vars: dict[str, str]           # Required/optional environment variables
  volumes: dict[str, str]            # Mount points (/tmp_workspace)
  entrypoint: str                    # Container entry point command
  healthcheck: dict                  # Optional health check configuration
```

### Environment Variables

```yaml
# Required environment variables
TINYCUA_MODEL_ENDPOINT: str          # OpenAI-compatible API endpoint URL
TINYCUA_MODEL_API_KEY: str           # API key for model endpoint (can be empty for local)
TINYCUA_MODEL_NAME: str              # Model name to use (default: "local-model")

# Optional environment variables
BRAVE_API_KEY: str                   # For web search tasks
TINYCUA_LOG_LEVEL: str               # Logging level (default: "INFO")
TINYCUA_TIMEOUT: int                 # Task timeout in seconds (default: 300)
```

---

## API / Interface Contracts

### Container Build Contract

```dockerfile
# Pseudo-Dockerfile (not final implementation)
FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bash \
    coreutils \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv (project uses uv for dependency management)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies
COPY requirements.txt .
RUN uv pip install --no-cache-dir -r requirements.txt

# Copy TinyCUA source
COPY src/tinycua /app/tinycua
COPY src/tinycua-sdk /app/tinycua-sdk

# Install TinyCUA (non-editable; editable installs don't work in Docker)
WORKDIR /app
RUN uv pip install ./tinycua-sdk && uv pip install ./tinycua

# Set up entry point
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Configure working directory
WORKDIR /tmp_workspace
ENTRYPOINT ["/app/entrypoint.sh"]
```

### Entry Point Contract

```bash
# Pseudo-entrypoint (not final implementation)
#!/bin/bash
set -e

# Validate required environment variables
if [ -z "$TINYCUA_MODEL_ENDPOINT" ]; then
    echo "ERROR: TINYCUA_MODEL_ENDPOINT not set"
    exit 1
fi

# Configure TinyCUA with model endpoint
export TINYCUA_MODEL_ENDPOINT="$TINYCUA_MODEL_ENDPOINT"
export TINYCUA_MODEL_API_KEY="${TINYCUA_MODEL_API_KEY:-}"

# Run TinyCUA agent with task prompt
# NOTE: The CLI entry point `tinycua` is established in Milestone 5.1
# (see specs/5.1-cli-runtime-entry-point/). The benchmark subcommand
# is provided by that CLI, not a standalone python -m module.
exec tinycua benchmark run \
    --prompt "$TASK_PROMPT" \
    --workspace /tmp_workspace \
    --output /tmp_workspace/results \
    --transcript /tmp_workspace/transcript.jsonl
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Missing `TINYCUA_MODEL_ENDPOINT` | Exit code 1 with error message | Container fails to start |
| Model endpoint unreachable | Agent error with connectivity message | Task fails, transcript preserved |
| Missing `BRAVE_API_KEY` | Warning log, continue execution | Web search tasks may fail |
| `/tmp_workspace` not mounted | Exit code 1 with error message | Container fails to start |
| Write permission denied | Agent error with permission message | Task fails, partial results preserved |
| Task timeout | Graceful shutdown, preserve artifacts | Exit code 0, timeout noted in transcript |

---

## Implementation Phases

### Phase 1 — MVP (Required for initial release)

- [ ] Create Dockerfile with base image and system dependencies
- [ ] Install Python dependencies and TinyCUA packages
- [ ] Implement entry point script with environment validation
- [ ] Configure volume mounting for `/tmp_workspace`
- [ ] Add basic health check
- [ ] Create smoke test task for validation
- [ ] Document all configuration options
- [ ] Test container build and basic execution

### Phase 2 — Enhancements (Post-MVP)

- [ ] Add optional browser/search dependencies (chromium, geckodriver)
- [ ] Implement multi-stage build for smaller image size
- [ ] Add Docker Compose file for local development
- [ ] Add container logging and monitoring hooks
- [ ] Optimize image layers for faster builds
- [ ] Add CI/CD pipeline integration

---

## Technical Decisions

1. **Decision**: Use `python:3.11-slim` as base image.
   - **Reason**: Minimal footprint (~150MB) with Python 3.11 support. Slim variant includes only essential packages.
   - **Alternatives Considered**: `python:3.11` (full) — too large (~900MB). `alpine` — musl compatibility issues with some Python packages.

2. **Decision**: Install TinyCUA from local source via `COPY` and `pip install -e`.
   - **Reason**: Allows development iteration without publishing packages. Matches project structure where TinyCUA is a local subproject.
   - **Alternatives Considered**: Install from PyPI — not applicable since TinyCUA is not published. Use `COPY --from=builder` — adds complexity without benefit for prototype.

3. **Decision**: Use environment variables for model endpoint configuration.
   - **Reason**: Follows Twelve-Factor App principles. Allows runtime configuration without rebuilding image. Compatible with WildClawBench's environment injection.
   - **Alternatives Considered**: Config files — more complex to manage in containers. Command-line arguments — less flexible for container orchestration.

4. **Decision**: Mount `/tmp_workspace` as volume.
   - **Reason**: Matches WildClawBench's contract for task workspace. Allows task files to be injected and results to be extracted without container modification.
   - **Alternatives Considered**: Bake workspace into image — not feasible since tasks are dynamic. Use named volumes — harder to inspect results.

5. **Decision**: Separate entry point script from Python module.
   - **Reason**: Allows environment validation, signal handling, and graceful shutdown before Python execution. Provides clearer error messages for configuration issues.
   - **Alternatives Considered**: Direct Python entry point — less flexibility for pre-execution checks.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Image size exceeds 2GB target | Medium | Medium | Use multi-stage build, minimize layers, remove build dependencies |
| Local model endpoint unreachable from container | High | High | Document networking options (host.docker.internal, bridge networks) |
| Missing system dependencies for WildClawBench tasks | Medium | High | Research task requirements, add dependencies incrementally |
| Browser/search tools add significant size | Medium | Low | Make optional, document for specific task categories |
| Container startup time too slow | Low | Medium | Optimize layer caching, use smaller base image |

---

## Open Questions

1. **Browser/search dependency scope**
   - Should chromium and geckodriver be included in the base image or as optional add-ons?
   - Impact: Image size vs. out-of-the-box functionality for web-dependent tasks.

2. **Local model endpoint networking**
   - What Docker networking configuration is needed for host-local model endpoints?
   - Options: `--network host`, `host.docker.internal`, bridge network with host routing.
   - **`--network host`**: Shares the host network namespace directly. Simple but reduces container isolation; port conflicts possible.
   - **`host.docker.internal`**: Docker Desktop provides this automatically; on Linux, add `--add-host=host.docker.internal:host-gateway` to the `docker run` command.
   - **Bridge network with host routing**: Use a custom bridge and configure routing. Most isolated but requires manual IP/route setup.
   - Recommendation: Use `--add-host=host.docker.internal:host-gateway` for Linux, native `host.docker.internal` for Docker Desktop, as the simplest cross-platform approach.

3. **Logging and monitoring**
   - Should the container include logging drivers for centralized log collection?
   - For prototype: simple stdout/stderr logging is sufficient.

4. **Multi-architecture support**
   - Should the image support both amd64 and arm64 architectures?
   - For prototype: amd64 only is sufficient.

---

## References

- **Spec**: `./spec.md` — feature specification and acceptance criteria
- **WildClawBench Adapter Contract**: `specs/wildclawbench-spike/spec.md` — adapter contract research
- **TinyCUA Design Docs**: `src/tinycua/docs/design/` — target architecture documentation
- **Docker Best Practices**: [Dockerfile reference](https://docs.docker.com/engine/reference/builder/)
- **WildClawBench Container Requirements**: [WildClawBench documentation](https://github.com/InternLM/WildClawBench)
- **Existing Docker Configuration**: `src/tinycua-backend/docker-compose.yml` — reference for Docker conventions