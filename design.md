# Design Document: Full 60-Task Local-LLM Benchmark Run

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Created**: 2026-06-14
**Last Updated**: 2026-06-14

---

## Overview

This design describes the orchestration of a full 60-task WildClawBench benchmark run using the TinyCUA harness with a local LLM model. The focus is on execution, data collection, and result aggregation — not on code architecture changes. The output is a `summary_all.json` file with aggregate results and per-task artifacts for analysis in Milestone 5.7.

---

## Architecture

### Component Overview

```
Benchmark Orchestrator (Python script)
  │
  ├── reads WildClawBench task list (60 tasks)
  ├── for each task:
  │     ├── constructs AgentTaskSpec
  │     ├── TinyCUAAgent.run_task(spec)
  │     ├── TinyCUAAgent.collect_usage(task_id, output_dir, elapsed_time)
  │     ├── TinyCUAAgent.prepare_grading_transcript(task_id)
  │     └── stores result in TaskResult
  │
  ├── aggregates TaskResults into SummaryAggregate
  ├── collects RunMetadata (model, endpoint, hardware, runtime)
  └── writes summary_all.json
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `scripts/run_benchmark.py` | New | Orchestrator script for full benchmark run |
| `scripts/benchmark_config.py` | New | Configuration for benchmark run (model, endpoint, tasks) |
| `scripts/collect_metadata.py` | New | Hardware/runtime metadata collection |
| `benchmark_results/` | New | Output directory for benchmark artifacts |

---

## Data Model

### RunMetadata

```python
@dataclass
class RunMetadata:
    run_id: str                    # Unique run identifier (e.g., timestamp-based)
    start_time: str                # ISO 8601 start time
    end_time: str                  # ISO 8601 end time
    total_duration_seconds: float  # Total run duration
    
    # Model configuration
    local_model_name: str          # e.g., "llama3-70b"
    endpoint_url: str              # e.g., "http://localhost:8000/v1"
    api_key_configured: bool       # Whether API key was provided
    
    # Hardware info
    cpu_info: str                  # CPU model and count
    gpu_info: list[str]            # GPU model(s) and VRAM
    ram_total_gb: float            # Total system RAM
    
    # Runtime info
    runtime_version: str           # TinyCUA version
    docker_image_tag: str          # Docker image used (if any)
    python_version: str            # Python version
    
    # Judge configuration
    judge_model: str | None        # Judge LLM model (if configured)
    judge_endpoint: str | None     # Judge LLM endpoint (if configured)
```

### TaskResult

```python
@dataclass
class TaskResult:
    task_id: str                   # WildClawBench task identifier
    task_category: str             # e.g., "Productivity Flow", "Code Intelligence"
    score: float | None            # Grading score (None if failed/timeout)
    status: str                    # "success", "failed", "timeout", "error"
    elapsed_time: float            # Task execution time in seconds
    error: str | None              # Error message (if any)
    
    # Artifact paths (relative to output directory)
    transcript_path: str           # e.g., "results/<task_id>/transcript.jsonl"
    usage_path: str                # e.g., "results/<task_id>/usage.json"
    log_path: str                  # e.g., "results/<task_id>/agent.log"
    output_path: str | None        # e.g., "results/<task_id>/output/" (if applicable)
    
    # Usage data
    requests: int                  # Number of LLM requests
    total_tokens: int | None       # Total tokens (None if not available)
    cost: float                    # Cost (0.0 for local models)
```

### SummaryAggregate

```python
@dataclass
class SummaryAggregate:
    total_tasks: int               # Should be 60
    completed_tasks: int           # Tasks that finished (success or failed)
    successful_tasks: int          # Tasks with score > 0
    failed_tasks: int              # Tasks with error/timeout
    skipped_tasks: int             # Tasks not attempted (if any)
    
    average_score: float | None    # Average score across successful tasks
    min_score: float | None        # Minimum score
    max_score: float | None        # Maximum score
    median_score: float | None     # Median score
    
    total_elapsed_seconds: float   # Sum of all task elapsed times
    average_task_time: float       # Average time per task
    
    # Category breakdown
    category_scores: dict[str, dict]  # {category: {avg, min, max, count}}
```

### summary_all.json Structure

```json
{
  "metadata": {
    "run_id": "2026-06-14T12:00:00Z",
    "start_time": "2026-06-14T12:00:00Z",
    "end_time": "2026-06-14T18:30:00Z",
    "total_duration_seconds": 23400,
    "local_model_name": "llama3-70b",
    "endpoint_url": "http://localhost:8000/v1",
    "api_key_configured": false,
    "cpu_info": "AMD Ryzen 9 7950X 16-Core",
    "gpu_info": ["NVIDIA RTX 4090 24GB"],
    "ram_total_gb": 64.0,
    "runtime_version": "0.1.0",
    "docker_image_tag": "tinycua-benchmark:latest",
    "python_version": "3.11.15",
    "judge_model": null,
    "judge_endpoint": null
  },
  "summary": {
    "total_tasks": 60,
    "completed_tasks": 58,
    "successful_tasks": 45,
    "failed_tasks": 10,
    "skipped_tasks": 2,
    "average_score": 0.72,
    "min_score": 0.0,
    "max_score": 1.0,
    "median_score": 0.8,
    "total_elapsed_seconds": 21600,
    "average_task_time": 360,
    "category_scores": {
      "Productivity Flow": {"avg": 0.75, "min": 0.0, "max": 1.0, "count": 10},
      "Code Intelligence": {"avg": 0.8, "min": 0.2, "max": 1.0, "count": 12}
    }
  },
  "tasks": [
    {
      "task_id": "task_001",
      "task_category": "Productivity Flow",
      "score": 0.85,
      "status": "success",
      "elapsed_time": 420.5,
      "error": null,
      "transcript_path": "results/task_001/transcript.jsonl",
      "usage_path": "results/task_001/usage.json",
      "log_path": "results/task_001/agent.log",
      "output_path": "results/task_001/output/",
      "requests": 15,
      "total_tokens": 25000,
      "cost": 0.0
    }
  ]
}
```

---

## API / Interface Contracts

### Benchmark Orchestrator Script

```python
# scripts/run_benchmark.py

def run_full_benchmark(
    config: BenchmarkConfig,
    output_dir: Path,
    tasks: list[str] | None = None,  # None = all 60 tasks
) -> dict:
    """
    Execute the full WildClawBench benchmark suite.
    
    Args:
        config: Benchmark configuration (model, endpoint, timeout, etc.)
        output_dir: Directory for results and artifacts
        tasks: Optional list of specific task IDs to run (default: all 60)
    
    Returns:
        Parsed summary_all.json content
    """
```

### Configuration

```python
# scripts/benchmark_config.py

@dataclass
class BenchmarkConfig:
    # Model configuration
    model_name: str = "llama3"
    base_url: str = "http://localhost:8000/v1"
    api_key: str | None = None
    
    # Execution configuration
    timeout_seconds: int = 600  # 10 minutes per task
    concurrent_tasks: int = 1   # Sequential for now
    
    # Docker configuration
    docker_image: str = "tinycua-benchmark:latest"
    use_docker: bool = True
    
    # Output configuration
    preserve_artifacts: bool = True
    verbose: bool = True
```

### Metadata Collection

```python
# scripts/collect_metadata.py

def collect_run_metadata(config: BenchmarkConfig) -> RunMetadata:
    """
    Collect hardware, software, and configuration metadata.
    
    Returns:
        RunMetadata with all fields populated
    """
```

---

## Implementation Phases

### Phase 1 — Benchmark Script Structure

- [ ] Create `scripts/run_benchmark.py` with argument parsing
- [ ] Create `scripts/benchmark_config.py` with configuration dataclass
- [ ] Implement task list loading (from WildClawBench or hardcoded list)
- [ ] Implement basic loop: for each task, run TinyCUAAgent

### Phase 2 — Data Collection and Aggregation

- [ ] Implement per-task result collection (TaskResult)
- [ ] Implement usage data collection via TinyCUAAgent.collect_usage()
- [ ] Implement aggregate statistics calculation (SummaryAggregate)
- [ ] Implement metadata collection (RunMetadata)

### Phase 3 — Output Generation

- [ ] Implement summary_all.json schema and writing
- [ ] Implement task artifact directory structure
- [ ] Implement error handling and graceful failure

### Phase 4 — Testing and Validation

- [ ] Unit tests for schema validation and aggregate logic
- [ ] Integration test with subset of tasks
- [ ] Manual test with full 60-task run

---

## Technical Decisions

1. **Decision**: Use Python script (not CLI command) for benchmark orchestration.
   - **Reason**: Benchmark runs are long-running (hours), require detailed logging, and benefit from script-level control over the execution loop. A CLI command would add unnecessary complexity.
   - **Alternatives Considered**: Adding a `tinycua benchmark` CLI command — rejected because it conflates agent execution with benchmark orchestration.

2. **Decision**: Store results in a flat directory structure (`results/<task_id>/`) rather than nested by category.
   - **Reason**: Simpler artifact management, easier to inspect individual task results, and matches WildClawBench conventions.
   - **Alternatives Considered**: Nested `results/<category>/<task_id>/` — rejected because it complicates artifact path management.

3. **Decision**: Run tasks sequentially (concurrent_tasks=1) by default.
   - **Reason**: Local LLM endpoints may not support high concurrency; sequential execution ensures stable resource usage and clearer error attribution.
   - **Alternatives Considered**: Parallel execution — deferred to post-prototype if local endpoint supports it.

4. **Decision**: Include raw hardware info in metadata (CPU model, GPU VRAM, RAM).
   - **Reason**: Essential for interpreting benchmark results; local model performance is heavily dependent on hardware.
   - **Alternatives Considered**: Just GPU info — rejected because CPU/RAM also affect performance for non-GPU tasks.

5. **Decision**: Use TinyCUAAgent adapter rather than direct CLI invocation.
   - **Reason**: Adapter provides consistent interface for task execution, usage collection, and transcript management. Avoids duplicating subprocess handling logic.
   - **Alternatives Considered**: Direct CLI invocation — rejected because it would require reimplementing timeout handling, usage parsing, and artifact management.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Local LLM endpoint crashes mid-run | Medium | High | Record partial results; support resuming from last completed task |
| Task timeouts exceed reasonable limits | Medium | Medium | Configurable timeout per task; default 10 minutes |
| Hardware info collection fails on some platforms | Low | Low | Graceful fallback to "unknown" for missing hardware fields |
| summary_all.json becomes very large (60 tasks) | Low | Low | Use compact JSON; 60 tasks is manageable |
| WildClawBench task list changes between versions | Low | Medium | Document task list source; allow manual task specification |
| Docker resource exhaustion during long runs | Medium | High | Monitor container resource usage; add resource limits |

---

## Open Questions _(optional)_

1. **Should the benchmark support resuming from a partial run?**
   - Current thinking: Yes, for robustness. If the run is interrupted, it should detect completed tasks and skip them on re-run. This requires tracking completed task IDs.

2. **How should judge LLM configuration be handled in the metadata?**
   - Current thinking: Include judge_model and judge_endpoint in metadata, but allow them to be null if not configured. Document that judge configuration is separate from harness execution.

3. **Should the benchmark script support custom task lists?**
   - Current thinking: Yes, via a `--tasks` argument that accepts a comma-separated list of task IDs. Default is all 60 tasks.

---

## References

- Spec: [./spec.md](./spec.md)
- WildClawBench task list: `https://github.com/InternLM/WildClawBench`
- Issue: https://github.com/VJyzCELERY/TINYCUA/issues/87 (Milestone 5.6)
- TinyCUA adapter: `src/tinycua/tinycua/wildclawbench/agent.py` (Milestone 5.2)
- TinyCUA CLI: `src/tinycua/tinycua/cli/run.py` (Milestone 5.1)
- Docker image: `Dockerfile` (Milestone 5.3)
