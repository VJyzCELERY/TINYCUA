# Design Document: WildClawBench Smoke Runs

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-14

---

## Overview

This design implements Milestone 5.5 — WildClawBench Smoke Runs. It adds a smoke-run orchestration script that selects representative tasks from each WildClawBench category, executes them via the existing TinyCUA adapter/CLI pipeline, collects all artifacts (logs, transcripts, usage, outputs), and produces a structured summary report documenting pass/fail/skip status with categorized failures. The design builds entirely on top of Milestones 5.1–5.4 infrastructure without modifying any existing components.

---

## Architecture

### Component Overview

```
SmokeRunOrchestrator
  → SmokeTaskSelector (selects tasks per category)
  → For each SmokeTask:
      → TinyCUAAgent.run_task(spec) OR tinycua run CLI
      → ArtifactCollector (gathers logs, transcripts, usage, outputs)
      → FailureCategorizer (classifies errors)
  → SmokeReportGenerator (aggregates results into summary report)
```

### Affected Components

> **Path convention**: All paths are relative to `src/tinycua/`.

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/cli/smoke_run.py` | New | Smoke-run orchestration script — task selection, execution, collection, reporting |
| `tinycua/wildclawbench/agent.py` | No change | Existing TinyCUAAgent adapter (Milestone 5.2) |
| `tinycua/cli/benchmark.py` | No change | Existing benchmark CLI (Milestone 5.1) |
| `tinycua/cli/transcript.py` | No change | Existing transcript/usage writing (Milestone 5.4) |
| `tests/unit/test_smoke_run.py` | New | Unit tests for task selection, failure categorization, report generation |
| `tests/integration/test_smoke_run_integration.py` | New | Integration tests for end-to-end smoke run |

---

## Data Model

### SmokeTask

```python
@dataclass(frozen=True)
class SmokeTask:
    task_id: str              # unique identifier (e.g., "prod-flow-001")
    category: str             # WildClawBench category name
    prompt: str               # task prompt text
    timeout_seconds: int      # per-task timeout (default: 300)
    workspace_path: Path      # working directory for the task
    output_dir: Path          # artifact output directory
    dependencies: list[str]   # required capabilities (e.g., ["browser", "email"])
```

### SmokeResult

```python
@dataclass
class SmokeResult:
    task_id: str
    category: str
    status: str               # "pass" | "fail" | "skip" | "timeout"
    elapsed_time: float       # seconds
    usage: dict | None        # usage summary from usage.json
    failure_reason: str | None
    failure_category: str | None  # "harness_crash" | "timeout" | "llm_error" | "missing_dependency" | "grading_error" | "other"
    artifact_paths: dict      # {"log": Path, "transcript": Path, "usage": Path}
```

### SmokeReport

```python
@dataclass
class SmokeReport:
    run_timestamp: str        # ISO 8601
    model: str                # model used
    base_url: str             # endpoint used
    total_tasks: int
    passed: int
    failed: int
    skipped: int
    timed_out: int
    results: list[SmokeResult]
    category_summary: dict[str, dict]  # per-category pass/fail/skip counts
    failure_taxonomy: dict[str, int]   # failure_category → count
```

### Failure Categories

| Category | Description |
|----------|-------------|
| `harness_crash` | TinyCUA agent or CLI crashed during execution |
| `timeout` | Task exceeded configured timeout |
| `llm_error` | LLM endpoint returned an error or was unreachable |
| `missing_dependency` | Task requires a capability not available (browser, email, etc.) |
| `grading_error` | Task completed but WildClawBench grading failed |
| `other` | Unclassified failure |

---

## API / Interface Contracts

### SmokeRunOrchestrator

```python
class SmokeRunOrchestrator:
    """Orchestrates WildClawBench smoke runs across categories.

    Args:
        model: Model name for TinyCUA agent.
        base_url: LLM API base URL.
        api_key: LLM API key.
        output_base: Base directory for all smoke-run artifacts.
        timeout: Default per-task timeout in seconds.
        mode: "local" (tinycua CLI) or "docker" (adapter via Docker).
    """

    def run(self) -> SmokeReport:
        """Execute smoke runs and return the summary report."""

    def select_tasks(self) -> list[SmokeTask]:
        """Select representative tasks from each category."""
```

**Execution Model**: Tasks execute sequentially via `subprocess.run()` with a per-task timeout. The orchestrator iterates through selected tasks one at a time. Each task runs in an isolated subprocess — partial failures (e.g., task 3 crashes) do not abort remaining tasks. The orchestrator catches exceptions per-task, categorizes the failure, and continues to the next task. The `SmokeReport` reflects the outcome of all attempted tasks regardless of individual failures.

### SmokeTaskSelector

```python
class SmokeTaskSelector:
    """Selects tasks for smoke runs based on category and dependency availability.

    Args:
        available_capabilities: Set of capabilities available in the current
            environment (e.g., {"browser", "email", "filesystem"}).
    """

    def select(self) -> list[SmokeTask]:
        """Return one task per category where dependencies are met."""
```

### FailureCategorizer

```python
def categorize_failure(
    error: Exception | str,
    exit_code: int | None,
    elapsed: float,
    timeout: int,
) -> str:
    """Classify a failure into a category.

    Returns one of: "harness_crash", "timeout", "llm_error",
    "missing_dependency", "grading_error", "other".
    """
```

### Error Handling

| Error Case | Response | Notes |
|------------|----------|-------|
| Docker build failure | Skip all Docker tasks, report build error | Don't fail entire run |
| LLM endpoint unreachable | Mark task as `llm_error`, continue next task | Don't abort remaining tasks |
| Task timeout | Mark as `timeout`, kill process, continue | Use configured timeout |
| Output directory not writable | Fail fast before any execution | Validate upfront |
| Grading failure | Mark as `grading_error`, preserve partial artifacts | Log grading error message |

---

## Implementation Phases

### Phase 1 — Task Selection (required)

- [ ] Define `SmokeTask` dataclass with task metadata
- [ ] Implement `SmokeTaskSelector` with static curated task list per category
- [ ] Implement dependency checking logic (capability → task mapping)
- [ ] Add skip logic for tasks with unavailable dependencies

### Phase 2 — Smoke-Run Orchestration (required)

- [ ] Implement `SmokeRunOrchestrator` class
- [ ] Wire task selection → execution → artifact collection pipeline
- [ ] Support both local CLI mode (`tinycua run`) and Docker adapter mode
- [ ] Implement cooperative timeout per task (threading.Timer or subprocess timeout)

### Phase 3 — Failure Categorization and Reporting (required)

- [ ] Implement `categorize_failure()` with exception/exit-code heuristics
- [ ] Implement `SmokeResult` and `SmokeReport` dataclasses
- [ ] Implement `SmokeReportGenerator` for structured report output (JSON + Markdown)
- [ ] Implement per-category summary and failure taxonomy aggregation

### Phase 4 — CLI Integration (required)

- [ ] Add `tinycua smoke-run` CLI subcommand
- [ ] Accept flags: `--model`, `--base-url`, `--api-key`, `--timeout`, `--mode`, `--output`
- [ ] Wire CLI to `SmokeRunOrchestrator.run()`
- [ ] Print summary table to stdout after completion

### Phase 5 — Tests (required)

- [ ] Unit tests for `SmokeTaskSelector` — category coverage, skip logic
- [ ] Unit tests for `categorize_failure()` — each failure category
- [ ] Unit tests for `SmokeReportGenerator` — correct aggregation
- [ ] Unit tests for idempotency — re-run does not corrupt artifacts
- [ ] Integration test: mock agent → full smoke run → report generation

---

## Technical Decisions

1. **Decision**: Use a static curated task list per category rather than dynamic dataset loading.
   - **Reason**: Simplicity for the research prototype. WildClawBench tasks are stable (60-task suite). Dynamic loading adds complexity without benefit for smoke runs.
   - **Alternatives Considered**: Load tasks dynamically from WildClawBench dataset — rejected as over-engineering for smoke runs; can be added in Milestone 5.6.

2. **Decision**: Support both local CLI and Docker modes via a `--mode` flag.
   - **Reason**: Local mode enables fast iteration during development. Docker mode validates the containerized path that WildClawBench expects. Both use the same artifact collection pipeline.
   - **Alternatives Considered**: Docker-only — rejected because it slows development iteration. Local-only — rejected because it doesn't validate the Docker path.

3. **Decision**: Produce both JSON and Markdown summary reports.
   - **Reason**: JSON is machine-readable for downstream analysis. Markdown is human-readable for quick inspection in PRs and issue comments.
   - **Alternatives Considered**: JSON-only — rejected because developers need quick human-readable summaries. Markdown-only — rejected because programmatic access is needed for Milestone 5.7 analysis.

4. **Decision**: Categorize failures into six fixed categories rather than free-form error messages.
   - **Reason**: Enables per-category aggregation in the failure taxonomy, which is the primary deliverable for documenting failures by category (per the milestone contract).
   - **Alternatives Considered**: Free-form error messages — rejected because they don't support structured aggregation.

5. **Decision**: Skip tasks with unavailable dependencies rather than failing them.
   - **Reason**: Smoke runs should validate what's possible, not fail on known limitations. Skip reasons are documented for transparency.
   - **Alternatives Considered**: Fail skipped tasks — rejected because it inflates the failure count with expected failures.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Local model endpoint too slow for smoke-run iteration | High | Medium | Allow per-task timeout override; support mock agent mode for testing |
| WildClawBench task prompts reference capabilities TinyCUA doesn't have | High | Low | Dependency-based skip logic with documented reasons |
| Docker image build fails due to missing system dependencies | Medium | Medium | Document required dependencies; fallback to local CLI mode |
| Smoke-run report is too large for PR comments | Low | Low | Output as separate artifact file; summarize key metrics in PR body |
| Task selection list becomes stale as WildClawBench evolves | Low | Low | Static list is intentional for prototype; document update process |

---

## Open Questions _(optional)_

1. **Should the smoke-run script be a standalone script or a CLI subcommand?**
   - **Resolved**: Both. A standalone script for development iteration (`python -m tinycua.cli.smoke_run`), and a `tinycua smoke-run` CLI subcommand for formal runs.
   - **Rationale**: Local standalone mode enables fast iteration without CLI registration overhead. The CLI subcommand provides the polished entry point for formal validation runs and integrates with the existing `tinycua` CLI structure (matching `tinycua benchmark`, `tinycua transcript`, etc.).

2. **How many tasks per category should smoke runs cover?**
   - **Resolved**: Minimum one per category for smoke runs. The milestone contract says "at least one task from each category where dependencies are available." More tasks can be added if time permits.
   - **Rationale**: One task per category satisfies the milestone contract while keeping smoke-run duration manageable (6–12 tasks at 300s timeout each). Additional tasks can be added incrementally as the static list evolves.

---

## References

- Spec: [./spec.md](./spec.md)
- Milestone 5.5 contract: `issue #87` — "run at least one task from each category where dependencies are available; collect scores, usage, logs, transcripts, and task outputs; document failures by category"
- Existing components:
  - `tinycua/wildclawbench/agent.py` — TinyCUAAgent adapter (Milestone 5.2)
  - `tinycua/wildclawbench/base_agent.py` — BaseAgent ABC and dataclasses
  - `tinycua/cli/benchmark.py` — benchmark CLI (Milestone 5.1)
  - `tinycua/cli/transcript.py` — transcript/usage writing (Milestone 5.4)
  - `tinycua/cli/_common.py` — shared CLI utilities
- WildClawBench sources:
  - GitHub: `https://github.com/InternLM/WildClawBench`
  - Paper: `https://arxiv.org/abs/2605.10912`
  - Dataset: `https://huggingface.co/datasets/internlm/WildClawBench`
