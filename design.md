# Design Document: Full 60-Task Local-LLM Benchmark Run

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Created**: 2026-06-14
**Last Updated**: 2026-06-14

---

## Overview

This design implements the full 60-task WildClawBench benchmark run for TinyCUA using local LLM models. The benchmark runner orchestrates execution of all WildClawBench tasks through the TinyCUA harness, collects per-task artifacts (transcripts, logs, usage), and produces an aggregate `summary_all.json` file with metadata and results. The design focuses on reliability (timeout handling, endpoint failure recovery, checkpoint/resume) and analyzability (structured output for comparison with other harnesses).

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Benchmark Runner (run_benchmark.py)          │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Task Loader  │───▶│ Task Runner  │───▶│ Result       │      │
│  │ (WildClawBench│    │ (TinyCUAAgent│    │ Collector    │      │
│  │  task list)  │    │  .run_task())│    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Checkpoint   │    │ Local LLM    │    │ Summary      │      │
│  │ Manager      │    │ Endpoint     │    │ Generator    │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │                                           │
         ▼                                           ▼
  ┌──────────────┐                          ┌──────────────┐
  │ WildClawBench│                          │ Output Dir   │
  │ Task Data    │                          │ (per-task    │
  │ (HuggingFace)│                          │  artifacts + │
  └──────────────┘                          │  summary)    │
                                            └──────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `scripts/run_benchmark.py` | New | Main benchmark runner script |
| `scripts/benchmark_config.py` | New | Configuration for benchmark runs |
| `scripts/summary_generator.py` | New | Generates `summary_all.json` |
| `scripts/checkpoint_manager.py` | New | Manages task completion checkpoints |
| `tests/unit/test_benchmark_runner.py` | New | Unit tests for runner logic |
| `tests/integration/test_benchmark_integration.py` | New | Integration test with subset of tasks |

---

## Data Model

### Summary File Schema (`summary_all.json`)

```python
BenchmarkSummary:
    metadata: BenchmarkMetadata
    tasks: list[TaskResult]
    aggregate: AggregateStats

BenchmarkMetadata:
    model_name: str                    # e.g., "llama3-8b"
    endpoint_url: str                  # e.g., "http://localhost:8000/v1"
    hardware: HardwareInfo
    total_runtime_seconds: float
    judge_config: JudgeConfig | None
    run_id: str                        # Unique run identifier
    started_at: str                    # ISO 8601 timestamp
    completed_at: str | None           # ISO 8601 timestamp

HardwareInfo:
    cpu: str                           # e.g., "AMD Ryzen 9 5900X"
    gpu: str | None                    # e.g., "NVIDIA RTX 4090"
    ram_gb: float
    platform: str                      # e.g., "linux"

JudgeConfig:
    judge_model: str | None            # Model used for judging (if any)
    judge_endpoint: str | None

TaskResult:
    task_id: str                       # WildClawBench task ID
    task_type: str                     # e.g., "simple", "compound"
    category: str                      # e.g., "coding", "productivity"
    status: str                        # "success", "failure", "timeout", "error"
    score: float | None                # Graded score (if gradable)
    elapsed_time_seconds: float
    token_usage: TokenUsage | None
    error_message: str | None
    transcript_path: str               # Relative path to transcript
    log_path: str                      # Relative path to agent log
    output_path: str                   # Relative path to task output

TokenUsage:
    requests: int
    total_tokens: int | None
    cost: float                        # Always 0.0 for local models

AggregateStats:
    total_tasks: int
    completed: int
    successful: int
    failed: int
    timed_out: int
    errored: int
    average_score: float | None
    average_elapsed_time: float
    total_tokens: int | None
```

### Checkpoint File Schema (`checkpoint.json`)

```python
Checkpoint:
    run_id: str
    completed_tasks: list[str]         # List of completed task IDs
    last_updated: str                  # ISO 8601 timestamp
```

---

## API / Interface Contracts

### Benchmark Runner

```python
# scripts/run_benchmark.py

def run_benchmark(
    config_path: str | None = None,    # Path to config YAML/JSON
    output_dir: str = "./benchmark_results",
    model: str | None = None,          # Override model name
    base_url: str | None = None,       # Override endpoint URL
    resume: bool = True,               # Resume from checkpoint
    task_ids: list[str] | None = None, # Subset of tasks to run
) -> BenchmarkSummary:
    """
    Run the full WildClawBench benchmark suite with TinyCUA.
    
    Returns a BenchmarkSummary with per-task results and metadata.
    """
```

### Checkpoint Manager

```python
# scripts/checkpoint_manager.py

class CheckpointManager:
    def __init__(self, output_dir: str, run_id: str):
        """Initialize checkpoint manager for a benchmark run."""
    
    def is_task_completed(self, task_id: str) -> bool:
        """Check if a task has already been completed."""
    
    def mark_task_completed(self, task_id: str) -> None:
        """Mark a task as completed in the checkpoint."""
    
    def get_completed_tasks(self) -> list[str]:
        """Return list of completed task IDs."""
    
    def save(self) -> None:
        """Persist checkpoint to disk."""
    
    def load(self) -> None:
        """Load checkpoint from disk (for resume)."""
```

### Summary Generator

```python
# scripts/summary_generator.py

class SummaryGenerator:
    def __init__(self, output_dir: str, metadata: BenchmarkMetadata):
        """Initialize summary generator."""
    
    def add_task_result(self, result: TaskResult) -> None:
        """Add a task result to the summary."""
    
    def generate(self) -> BenchmarkSummary:
        """Generate the final summary with aggregate stats."""
    
    def save(self, path: str = "summary_all.json") -> None:
        """Save summary to disk."""
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Local model endpoint unreachable | Task marked as "error", run continues | Retry after configurable delay |
| Task timeout | Task marked as "timeout", process killed | Preserve partial artifacts |
| WildClawBench task data missing | Task skipped, marked as "error" | Log warning, continue |
| Output disk full | Run pauses, logs error | Preserve completed artifacts |
| Checkpoint corruption | Run starts fresh, logs warning | Do not lose completed task data |

---

## Implementation Phases

### Phase 1 — Core Runner (MVP)

- [ ] Implement `BenchmarkRunner` class with task iteration
- [ ] Implement `CheckpointManager` for resume support
- [ ] Implement `SummaryGenerator` for `summary_all.json`
- [ ] Implement timeout and endpoint failure handling
- [ ] Implement progress logging (stdout + log file)
- [ ] Unit tests for all components

### Phase 2 — Integration and Validation

- [ ] Integration test with 3 tasks from different categories
- [ ] Verify summary file correctness
- [ ] Verify per-task artifact collection
- [ ] Test interruption and resume
- [ ] Manual run with a known local model

### Phase 3 — Full Benchmark Run

- [ ] Execute full 60-task benchmark
- [ ] Validate all task artifacts exist
- [ ] Analyze results against baselines
- [ ] Document findings and recommendations

> **Note**: Phase 3 must NOT be attempted until Phase 2 is complete and validated.

---

## Technical Decisions

1. **Decision**: Use Python script (`run_benchmark.py`) rather than shell script for the runner.
   - **Reason**: Python provides better error handling, checkpoint management, and summary generation. It also integrates naturally with the TinyCUA Python codebase.
   - **Alternatives Considered**: Shell script — rejected because checkpoint/resume and structured summary generation are complex in bash.

2. **Decision**: Use `TinyCUAAgent.run_task(spec)` via Python API rather than CLI subprocess.
   - **Reason**: Avoids subprocess overhead for 60 tasks and allows direct access to return values (elapsed_time, error) without parsing stdout.
   - **Alternatives Considered**: CLI subprocess — rejected because it adds overhead and makes summary generation harder.

3. **Decision**: Store checkpoints as JSON files rather than a database.
   - **Reason**: Simple, portable, and sufficient for sequential task execution. No external dependencies needed.
   - **Alternatives Considered**: SQLite — rejected as overkill for this prototype scope.

4. **Decision**: Sequential task execution (no concurrency) for the initial implementation.
   - **Reason**: Ensures reproducibility and simplifies timeout/error handling. Local LLM endpoints may not handle concurrent requests well.
   - **Alternatives Considered**: Concurrent execution — deferred to post-MVP; requires careful handling of model endpoint capacity.

5. **Decision**: Produce `summary_all.json` as the primary output format.
   - **Reason**: JSON is widely supported, easy to parse, and matches WildClawBench conventions. Can be converted to other formats (CSV, markdown) as needed.
   - **Alternatives Considered**: CSV — rejected because nested data (per-task results) is awkward in CSV. Markdown — rejected as not machine-readable.

6. **Decision**: Include hardware metadata in the summary.
   - **Reason**: Local model performance is heavily dependent on hardware. Recording CPU/GPU/RAM allows meaningful comparison across different setups.
   - **Alternatives Considered**: Omit hardware — rejected because it makes cross-run comparisons meaningless.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Local model endpoint becomes unstable during long run | Medium | High | Implement retry with backoff; record partial results |
| Some WildClawBench tasks require tools not available in TinyCUA | High | Medium | Record tool-availability failures; document gaps in summary |
| Disk space exhaustion during 60-task run | Low | High | Monitor disk usage; pause and warn if low |
| WildClawBench task data format changes | Low | Medium | Pin to specific WildClawBench version; validate task schema |
| Summary file becomes very large | Low | Low | JSON is compact; 60 tasks is manageable |
| Checkpoint file corruption | Low | Medium | Atomic writes; validate on load |

---

## Open Questions _(optional)_

1. **Should the runner support configurable concurrency (number of parallel tasks)?**
   - Current thinking: Start with sequential. Add concurrency as a CLI flag (`--concurrency N`) post-MVP if model endpoint supports it.

2. **How should the runner handle WildClawBench tasks that require external API keys (e.g., BRAVE_API_KEY)?**
   - Current thinking: Tasks requiring unavailable API keys should be skipped with a clear "skipped — missing API key" status in the summary.

3. **Should the summary include a comparison section with published baselines?**
   - Current thinking: No — keep the summary focused on TinyCUA results. Comparison is a separate analysis step (Milestone 5.7).

---

## References

- Spec: [./spec.md](./spec.md)
- WildClawBench repository: `https://github.com/InternLM/WildClawBench`
- WildClawBench dataset: `https://huggingface.co/datasets/internlm/WildClawBench`
- WildClawBench leaderboard: `https://internlm.github.io/WildClawBench/`
- Existing TinyCUA adapter: `src/tinycua/tinycua/wildclawbench/agent.py`
- Existing TinyCUA CLI: `src/tinycua/tinycua/cli/run.py`
- Issue: https://github.com/VJyzCELERY/TINYCUA/issues/87 (Milestone 5.6)
