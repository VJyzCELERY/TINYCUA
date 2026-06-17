# Implementation: agents-benchmark

Unified WildClawBench benchmark harness that replaces `hermes-benchmark` with a single CLI entry point orchestrating all four supported agent types (Hermes, Claude Code, Codex CLI, OpenClaw) through a registry-based adapter pattern.

## Context

- **Spec Reference**: `src/agents-benchmark/spec.md`
- **Design Reference**: `src/agents-benchmark/design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **Docker** — required for agent execution (Hermes agent runs in Docker containers)
- [ ] **API keys** — environment variables for each agent (e.g., `HERMES_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). Agents with missing keys are skipped with a warning.
- [ ] **Local LLM endpoint** (optional) — for local model benchmarks (e.g., vLLM, LM Studio)

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Docker | Yes (for integration tests) | `docker info` | `docker info` exits 0 |

### Data / Fixtures

- [ ] **None** — no seed data or migrations needed

### Access / Permissions

- [ ] **None** — no special access required beyond Docker and API keys

### Developer Tooling

- [ ] **Runtime**: Python >=3.11, Docker
- [ ] **Package manager**: uv
- [ ] **None** — no additional CLI tools required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/test_pipeline_integration.py
"""Integration tests for the benchmark pipeline."""


def test_pipeline_runs_all_agents_in_order(mock_adapters):
    """Pipeline must execute agents in fixed order: hermes, claudecode, codex, openclaw."""
    runner = BenchmarkRunner(config=load_config(...))
    result = runner.run_pipeline(agents=["all"], model="test-model")

    assert len(result.agent_results) == 4
    assert list(result.agent_results.keys()) == ["hermes", "claudecode", "codex", "openclaw"]


def test_pipeline_filters_agents(mock_adapters):
    """Pipeline must only run agents specified in --agents filter."""
    runner = BenchmarkRunner(config=load_config(...))
    result = runner.run_pipeline(agents=["hermes", "openclaw"], model="test-model")

    assert "hermes" in result.agent_results
    assert "openclaw" in result.agent_results
    assert "claudecode" not in result.agent_results
    assert "codex" not in result.agent_results


def test_pipeline_skips_failed_agent_and_continues(mock_adapters_with_failure):
    """Pipeline must skip a failed agent and continue with the next one."""
    runner = BenchmarkRunner(config=load_config(...))
    result = runner.run_pipeline(agents=["all"], model="test-model")

    assert "hermes" in result.agent_results
    assert "claudecode" in result.agent_results
    assert result.summary["hermes"]["status"] == "error"
    assert result.summary["claudecode"]["status"] == "success"
```

```python
# Test file: tests/test_compare_agents.py
"""Integration tests for N-way comparison."""


def test_compare_agents_produces_per_task_deltas():
    """compare_agents must produce per-task deltas for N agents."""
    agent_results = {
        "hermes": [{"task_id": "t1", "score": 1.0, "status": "success"}],
        "claudecode": [{"task_id": "t1", "score": 0.5, "status": "success"}],
    }
    report = compare_agents(agent_results)

    assert len(report["per_task_comparison"]) == 1
    assert report["per_task_comparison"][0]["hermes_score"] == 1.0
    assert report["per_task_comparison"][0]["claudecode_score"] == 0.5


def test_compare_agents_empty_results():
    """compare_agents must handle empty results gracefully."""
    report = compare_agents({})
    assert report["per_task_comparison"] == []
    assert report["agents"] == []
```

### Key Test Scenarios

- [ ] **Scenario 1**: Pipeline runs all 4 agents in sequence, each gets tasks, results are collected per-agent
- [ ] **Scenario 2**: Agent filtering via `--agents hermes,openclaw` excludes non-specified agents
- [ ] **Scenario 3**: Failed agent (missing API key) is skipped, remaining agents continue
- [ ] **Scenario 4**: N-way comparison produces per-task deltas across all agents
- [ ] **Edge case**: Empty task list produces valid empty results

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for each module: registry, runner, compare, config, adapters
- [ ] Existing test suite — confirm no regressions: `cd src/agents-benchmark && uv run pytest`
- [ ] Lint: `cd src/agents-benchmark && uv run ruff check && uv run ruff format --check`

### Manual Verification

- [ ] Verify `uv run python -m agents_benchmark --help` shows correct CLI options
- [ ] Verify `uv run python -m agents_benchmark compare --help` works

### Performance Considerations

- [ ] No performance requirements for MVP — sequential agent execution is acceptable

## Proposed Changes

### Package Structure

#### NEW `src/agents-benchmark/pyproject.toml`

- **Description**: Package metadata, dependencies, CLI scripts, ruff/pytest config
- **Dependencies**: `pyyaml>=6.0` (carried over from hermes-benchmark)
- **Dev dependencies**: `pytest>=8.0.0`, `pytest-cov>=4.1.0`, `ruff>=0.3.0`, `mypy>=1.8.0`
- **CLI scripts**: `agents-benchmark = "agents_benchmark.__main__:main"`

#### NEW `src/agents-benchmark/Makefile`

- **Description**: Dev commands (lint, test, clean)
- **Targets**: `lint`, `test`, `clean`, `format`

### Core Module

#### NEW `src/agents-benchmark/agents_benchmark/__init__.py`

- **Description**: Package init with public API exports
- **Exports**: `AgentRegistry`, `BenchmarkRunner`, `compare_agents`, `AgentConfig`, `load_config`

#### NEW `src/agents-benchmark/agents_benchmark/__main__.py`

- **Description**: CLI entry point using argparse (no external deps)
- **Subcommands**: default (run pipeline), `compare` (N-way comparison)
- **Options**: `--model`, `--agents`, `--category`, `--parallel`, `--results-dir`, `--config`

#### MIGRATED `src/agents-benchmark/agents_benchmark/base_agent.py`

- **Description**: WildClawBench BaseAgent ABC and dataclasses, migrated from `hermes-benchmark/base_agent.py`
- **Changes**: None structurally — this is a direct copy. All 4 adapters will implement this interface.
- **Source**: `src/hermes-benchmark/hermes_benchmark/base_agent.py`

### Agent Adapters

#### NEW `src/agents-benchmark/agents_benchmark/agents/__init__.py`

- **Description**: Adapters package init

#### MIGRATED `src/agents-benchmark/agents_benchmark/agents/hermes.py`

- **Description**: HermesAgent adapter, migrated from `hermes-benchmark/hermes_agent.py`
- **Changes**: Update import path from `hermes_benchmark` → `agents_benchmark`; rename class to `HermesAgentAdapter` for clarity
- **Source**: `src/hermes-benchmark/hermes_benchmark/hermes_agent.py`

#### NEW `src/agents-benchmark/agents_benchmark/agents/claudecode.py`

- **Description**: Claude Code adapter — implements BaseAgent for Claude Code agent harness
- **Dependencies**: BaseAgent ABC, AgentConfig
- **Note**: Stub implementation for MVP; actual Docker integration follows WildClawBench patterns

#### NEW `src/agents-benchmark/agents_benchmark/agents/codex.py`

- **Description**: Codex CLI adapter — implements BaseAgent for Codex CLI agent harness
- **Dependencies**: BaseAgent ABC, AgentConfig
- **Note**: Stub implementation for MVP

#### NEW `src/agents-benchmark/agents_benchmark/agents/openclaw.py`

- **Description**: OpenClaw adapter — implements BaseAgent for OpenClaw agent harness
- **Dependencies**: BaseAgent ABC, AgentConfig
- **Note**: Stub implementation for MVP

### Registry

#### NEW `src/agents-benchmark/agents_benchmark/agent_registry.py`

- **Description**: Central registry for agent adapter lookup by name
- **Interface**: `AgentRegistry.register(name, adapter_class)`, `AgentRegistry.get(name)`, `AgentRegistry.list_all()`
- **Pattern**: Registry pattern (per design.md decision)

### Config

#### NEW `src/agents-benchmark/agents_benchmark/config.py`

- **Description**: Per-agent configuration loader (YAML + env var resolution)
- **Dataclass**: `AgentConfig` with fields: name, model, api_base, api_key_env, docker_image, dockerfile_path, timeout_seconds, extra_env
- **Source**: Extended from `hermes-benchmark/hermes_config.py` (generalized for 4 agents)

### Runner

#### NEW `src/agents-benchmark/agents_benchmark/runner.py`

- **Description**: Pipeline orchestrator — runs agents sequentially, collects results
- **Interface**: `BenchmarkRunner.run_pipeline()`, `run_single_agent()`, `run_single_task()`
- **Error handling**: Skip failed agents, continue pipeline, report status per-agent

### Compare

#### MIGRATED `src/agents-benchmark/agents_benchmark/compare.py`

- **Description**: N-way comparison module, extended from `hermes-benchmark/compare_results.py`
- **Changes**: Generalize from 2-agent (tinycua/hermes) to N-agent comparison; support dynamic agent names in output
- **Source**: `src/hermes-benchmark/hermes_benchmark/compare_results.py`

### Tests

#### NEW `src/agents-benchmark/tests/unit/test_agent_registry.py`

- **Description**: Test agent adapter registration and lookup by name

#### NEW `src/agents-benchmark/tests/unit/test_agent_config.py`

- **Description**: Test AgentConfig loading from YAML/env vars

#### NEW `src/agents-benchmark/tests/unit/test_benchmark_runner.py`

- **Description**: Test sequential agent pipeline, filtering, and error handling

#### NEW `src/agents-benchmark/tests/unit/test_compare_results.py`

- **Description**: Test N-way comparison logic (migrated from hermes-benchmark, extended)

#### NEW `src/agents-benchmark/tests/unit/test_base_agent.py`

- **Description**: Test BaseAgent ABC contract compliance for all adapters

#### NEW `src/agents-benchmark/tests/integration/test_pipeline_integration.py`

- **Description**: Test full pipeline with mock agents

#### NEW `src/agents-benchmark/tests/integration/test_hermes_agent_integration.py`

- **Description**: Test HermesAgent Docker execution end-to-end (requires Docker)

### Cleanup

#### DELETE `src/hermes-benchmark/`

- **Description**: Remove old hermes-benchmark subproject — fully replaced by agents-benchmark
- **Condition**: Only after agents-benchmark passes all tests and lint

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `agents_benchmark/__init__.py` | New | Package init, public API exports |
| `agents_benchmark/__main__.py` | New | CLI entry point (argparse) |
| `agents_benchmark/base_agent.py` | Migrated | Copied from hermes-benchmark, unchanged |
| `agents_benchmark/agent_registry.py` | New | Registry pattern for agent adapter lookup |
| `agents_benchmark/agents/` | New | Per-agent adapter directory |
| `agents_benchmark/agents/hermes.py` | Migrated | From hermes-benchmark, import path updated |
| `agents_benchmark/agents/claudecode.py` | New | Claude Code adapter (stub) |
| `agents_benchmark/agents/codex.py` | New | Codex CLI adapter (stub) |
| `agents_benchmark/agents/openclaw.py` | New | OpenClaw adapter (stub) |
| `agents_benchmark/runner.py` | New | Pipeline orchestrator |
| `agents_benchmark/compare.py` | Migrated | Extended from hermes-benchmark for N agents |
| `agents_benchmark/config.py` | New | Per-agent configuration loader |
| `src/hermes-benchmark/` | Deleted | Replaced by agents-benchmark |

## Data Model Changes

```python
# New/extended dataclasses

@dataclass
class AgentConfig:
    name: str
    model: str
    api_base: str
    api_key_env: str
    docker_image: str
    dockerfile_path: str
    timeout_seconds: int = 300
    extra_env: dict[str, str] = field(default_factory=dict)

@dataclass
class BenchmarkResult:
    agent_name: str
    task_id: str
    score: float | None
    status: str
    elapsed_time: float
    token_usage: dict[str, Any]
    output_dir: Path

@dataclass
class PipelineResult:
    agent_results: dict[str, list[BenchmarkResult]]
    summary: dict[str, Any]
    comparison: dict[str, Any] | None
```

## API Changes

### CLI Interface

| Command | Description |
|---------|-------------|
| `uv run python -m agents_benchmark --model X --agents all` | Run all agents sequentially |
| `uv run python -m agents_benchmark --model X --agents hermes,openclaw` | Run specific agents |
| `uv run python -m agents_benchmark --model X --agents all --parallel 4` | Run with parallel tasks |
| `uv run python -m agents_benchmark compare --results-dir ./output` | Compare results |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pyyaml | >=6.0 | YAML config loading (migrated from hermes-benchmark) |

### Internal Dependencies

- [ ] Depends on nothing (standalone subproject)
- [ ] Replaces `hermes-benchmark` subproject

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Docker image build failures across platforms | Medium | Test on macOS and Linux; clear error messages |
| API rate limiting during long runs | Medium | Retry logic with exponential backoff |
| Stub adapters (claudecode, codex, openclaw) may not match actual WildClawBench interface | Medium | Pin to WildClawBench commit in Dockerfiles; test against real agents in integration tests |
| WildClawBench upstream changes break adapters | Low | Pin WildClawBench commit; monitor upstream |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-17*
