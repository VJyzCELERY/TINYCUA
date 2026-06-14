# Implementation: Full 60-Task Local-LLM Benchmark Run

Execute all 60 WildClawBench tasks using the TinyCUA harness with a local LLM model, producing `summary_all.json` aggregate results and per-task artifacts for comparison with other harnesses.

## Context

- **Spec Reference**: [spec.md](./spec.md) — Milestone 5.6: Full 60-Task Local-LLM Benchmark Run
- **Design Reference**: [design.md](./design.md) — Benchmark Orchestrator architecture
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [x] **.env file** — required variables:
  ```
  # Local LLM endpoint (e.g., vLLM, Ollama, LM Studio)
  TINYCUA_BASE_URL=http://localhost:8000/v1
  TINYCUA_API_KEY=              # optional for local models
  TINYCUA_MODEL=llama3
  ```
- [ ] **Environment variables** documented in `src/tinycua/.env.example`
- [ ] **None** — no hosted service secrets required

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Local LLM endpoint | Yes | User's local provider (vLLM/Ollama/LM Studio) | `curl $TINYCUA_BASE_URL/models` |
| Docker daemon | Yes | `dockerd` or Docker Desktop | `docker info` |

### Data / Fixtures

- [x] WildClawBench task list — 60 tasks (discovered from WildClawBench package or hardcoded)
- [x] TinyCUA Docker image from Milestone 5.3 (`tinycua-benchmark:latest`)

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.12+
- [x] **Package manager**: uv
- [x] **Additional CLI tools**: docker

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: src/tinycua/tests/test_benchmark_orchestrator.py
"""Integration tests for the full benchmark orchestrator."""


def test_run_metadata_schema_valid():
    """RunMetadata serialises to a valid JSON structure with all required fields."""
    from scripts.benchmark_config import BenchmarkConfig
    from scripts.collect_metadata import collect_run_metadata

    config = BenchmarkConfig(model_name="test-model", base_url="http://localhost:9999/v1")
    metadata = collect_run_metadata(config)

    assert metadata.run_id  # non-empty string
    assert metadata.local_model_name == "test-model"
    assert metadata.endpoint_url == "http://localhost:9999/v1"
    assert metadata.total_duration_seconds >= 0
    assert isinstance(metadata.cpu_info, str) and len(metadata.cpu_info) > 0
    assert isinstance(metadata.gpu_info, list)
    assert metadata.ram_total_gb > 0
    assert metadata.runtime_version  # non-empty
    assert metadata.python_version  # non-empty


def test_task_result_schema_valid():
    """TaskResult serialises to the expected JSON shape."""
    from scripts.run_benchmark import TaskResult

    result = TaskResult(
        task_id="task_001",
        task_category="Productivity Flow",
        score=0.85,
        status="success",
        elapsed_time=42.5,
        error=None,
        transcript_path="results/task_001/transcript.jsonl",
        usage_path="results/task_001/usage.json",
        log_path="results/task_001/agent.log",
        output_path="results/task_001/output/",
        requests=10,
        total_tokens=5000,
        cost=0.0,
    )

    assert result.task_id == "task_001"
    assert result.status == "success"
    assert result.score == 0.85


def test_summary_aggregate_calculation():
    """SummaryAggregate computes correct statistics from a list of TaskResults."""
    from scripts.run_benchmark import SummaryAggregate, TaskResult

    results = [
        TaskResult("t1", "Cat", 0.9, "success", 10.0, None, "", "", "", None, 5, 1000, 0.0),
        TaskResult("t2", "Cat", 0.7, "success", 20.0, None, "", "", "", None, 8, 2000, 0.0),
        TaskResult("t3", "Cat", None, "failed", 30.0, "error", "", "", "", None, 0, None, 0.0),
    ]

    agg = SummaryAggregate.from_task_results(results)

    assert agg.total_tasks == 3
    assert agg.successful_tasks == 2
    assert agg.failed_tasks == 1
    assert agg.skipped_tasks == 0
    assert agg.average_score is not None
    assert abs(agg.average_score - 0.8) < 0.01


def test_summary_all_json_written(tmp_path):
    """run_full_benchmark writes a valid summary_all.json to output_dir."""
    # This test uses a mock agent to avoid requiring a real LLM endpoint.
    import json
    from pathlib import Path

    # Arrange: mock TinyCUAAgent, BenchmarkConfig with 2 tasks
    # Act: run_full_benchmark(config, tmp_path, tasks=["t1", "t2"])
    # Assert: (tmp_path / "summary_all.json") exists and is valid JSON with
    #         "metadata", "summary", "tasks" keys.
    # (Full implementation in test phase)


def test_preflight_check_fails_on_readonly_dir(tmp_path):
    """preflight_check raises PermissionError for a read-only output directory."""
    from scripts.collect_metadata import preflight_check

    readonly = tmp_path / "readonly"
    readonly.mkdir()
    readonly.chmod(0o444)

    try:
        with pytest.raises(PermissionError):
            preflight_check(readonly)
    finally:
        readonly.chmod(0o755)  # restore for cleanup


def test_task_artifacts_preserved(tmp_path):
    """After a task run, transcript.jsonl and usage.json exist in task output dir."""
    # Arrange: mock agent that writes dummy files
    # Act: execute single task
    # Assert: transcript_path.exists(), usage_path.exists(), log_path.exists()
    # (Full implementation in test phase)
```

### Key Test Scenarios

- [x] **Scenario 1**: RunMetadata collection — verifies hardware/software metadata is captured correctly
- [x] **Scenario 2**: TaskResult schema — ensures per-task results serialize to the expected JSON shape
- [x] **Scenario 3**: SummaryAggregate calculation — validates pass/fail/skip counts and average score
- [x] **Scenario 4**: summary_all.json output — confirms the orchestrator writes valid JSON with all required sections
- [x] **Edge case**: Read-only output directory — preflight_check rejects before any tasks execute

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for metadata collection (CPU/GPU/RAM extraction on various platforms)
- [ ] Unit tests for summary statistics (edge cases: all pass, all fail, zero tasks)
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Run full 60-task benchmark with a local LLM endpoint and inspect `summary_all.json`
- [ ] Verify task-level artifacts for a sample of tasks (transcript, usage, log)
- [ ] Verify metadata section includes model name, endpoint, hardware, runtime version
- [ ] Compare results format with WildClawBench conventions

### Performance Considerations

- [ ] Benchmark run completes within expected time for 60 tasks (configurable timeout per task)
- [ ] summary_all.json file size is reasonable (<1MB for 60 tasks)

## Proposed Changes

### Benchmark Scripts (`src/tinycua/scripts/`)

#### NEW `src/tinycua/scripts/__init__.py`

- **Description**: Package init for benchmark scripts
- **Dependencies**: None

#### NEW `src/tinycua/scripts/benchmark_config.py`

- **Description**: `BenchmarkConfig` dataclass with model, endpoint, Docker, and output configuration
- **Dependencies**: dataclasses, pathlib

#### NEW `src/tinycua/scripts/collect_metadata.py`

- **Description**: `collect_run_metadata()` function — gathers CPU, GPU, RAM, Python version, runtime version. `preflight_check()` function — verifies output directory is writable.
- **Dependencies**: platform, subprocess, benchmark_config

#### NEW `src/tinycua/scripts/run_benchmark.py`

- **Description**: Main orchestrator — `run_full_benchmark(config, output_dir, tasks)`. Loops through tasks, runs TinyCUAAgent, collects usage, aggregates results, writes `summary_all.json`. Supports resumption via `.completed` file.
- **Dependencies**: TinyCUAAgent, BenchmarkConfig, RunMetadata, collect_metadata

### Tests (`src/tinycua/tests/`)

#### NEW `src/tinycua/tests/test_benchmark_orchestrator.py`

- **Description**: Integration tests for RunMetadata, TaskResult, SummaryAggregate, summary_all.json output, preflight_check
- **Dependencies**: pytest, scripts module

### Output Directory

#### NEW `src/tinycua/benchmark_results/`

- **Description**: Output directory for benchmark artifacts (created at runtime)
- **Dependencies**: None (gitignored)

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `scripts/` (new package) | New | Benchmark orchestration scripts |
| `scripts/benchmark_config.py` | New | Configuration dataclass |
| `scripts/collect_metadata.py` | New | Hardware/runtime metadata collection |
| `scripts/run_benchmark.py` | New | Full benchmark orchestrator loop |
| `tests/test_benchmark_orchestrator.py` | New | Integration tests |
| `benchmark_results/` | New | Runtime output directory (gitignored) |

## Data Model Changes

```python
@dataclass
class RunMetadata:
    run_id: str
    start_time: str
    end_time: str
    total_duration_seconds: float
    local_model_name: str
    endpoint_url: str
    api_key_configured: bool
    cpu_info: str
    gpu_info: list[str]
    ram_total_gb: float
    runtime_version: str
    docker_image_tag: str
    python_version: str
    judge_model: str | None
    judge_endpoint: str | None

@dataclass
class TaskResult:
    task_id: str
    task_category: str
    score: float | None
    status: str  # "success" | "failed" | "timeout" | "error"
    elapsed_time: float
    error: str | None
    transcript_path: str
    usage_path: str
    log_path: str
    output_path: str | None
    requests: int
    total_tokens: int | None
    cost: float

@dataclass
class SummaryAggregate:
    total_tasks: int
    completed_tasks: int
    successful_tasks: int
    failed_tasks: int
    skipped_tasks: int
    average_score: float | None
    min_score: float | None
    max_score: float | None
    median_score: float | None
    total_elapsed_seconds: float
    average_task_time: float
    category_scores: dict[str, dict]
```

## API Changes

No API endpoint changes — this is a script-based orchestrator invoked via `uv run python scripts/run_benchmark.py`.

### CLI Interface

| Command | Description |
|---------|-------------|
| `uv run python scripts/run_benchmark.py` | Run full 60-task benchmark |
| `uv run python scripts/run_benchmark.py --tasks t1,t2,t3` | Run subset of tasks |
| `uv run python scripts/run_benchmark.py --output-dir ./my_results` | Custom output directory |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none new) | — | All dependencies already in pyproject.toml |

### Internal Dependencies

- [x] Depends on Milestone 5.1 (CLI runtime entry point)
- [x] Depends on Milestone 5.2 (BaseAgent adapter)
- [x] Depends on Milestone 5.3 (Docker image)
- [x] Depends on Milestone 5.4 (Transcript artifacts)
- [x] Depends on Milestone 5.5 (Smoke runs)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Local LLM endpoint crashes mid-run | High | Track completed tasks in `.completed` file; support resume by skipping completed tasks on re-run |
| Task timeouts exceed reasonable limits | Medium | Configurable per-task timeout; default 600s (10 min) |
| Hardware info collection fails on some platforms | Low | Graceful fallback to "unknown" for missing fields |
| WildClawBench task list changes between versions | Medium | Document task list source; allow `--tasks` manual specification |
| Docker resource exhaustion during long runs | High | Monitor container resource usage; add resource limits |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-14*
