# Implementation: WildClawBench Smoke Runs

Adds a smoke-run orchestration script that selects representative tasks from each WildClawBench category, executes them via the existing TinyCUA adapter/CLI pipeline, collects all artifacts (logs, transcripts, usage, outputs), and produces a structured summary report documenting pass/fail/skip status with categorized failures. Builds entirely on top of Milestones 5.1–5.4 infrastructure without modifying any existing components.

## Context

- **Spec Reference**: `./spec.md` — WildClawBench Smoke Runs
- **Design Reference**: `./design.md` — WildClawBench Smoke Runs Design
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — smoke-run script reads model config from environment variables or CLI flags

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| Local OpenAI-compatible model endpoint | Yes | Per developer setup (e.g., `ollama serve`, vLLM, etc.) | `curl $BASE_URL/v1/models` |
| Docker (optional, for Docker mode) | No | `docker info` | `docker info` |

### Data / Fixtures

- [x] **None** — smoke-run script uses a static curated task list (no dataset loading)

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+, Docker (optional, for Docker mode)
- [x] **Package manager**: uv
- [x] **None** — no additional CLI tools required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_smoke_run_integration.py
"""Integration tests for WildClawBench smoke-run orchestration."""


def test_smoke_run_produces_report_with_all_categories(tmp_path):
    """Smoke run with mock agent produces a report covering all categories."""
    # Arrange
    orchestrator = SmokeRunOrchestrator(
        model="test-model",
        base_url="http://localhost:8000",
        api_key="test-key",
        output_base=tmp_path / "smoke-output",
        timeout=5,
        mode="local",
    )
    # Act
    report = orchestrator.run()
    # Assert
    assert report.total_tasks >= 6  # one per category minimum
    assert len(report.category_summary) >= 6
    for category in report.category_summary:
        assert report.category_summary[category]["total"] >= 1


def test_smoke_run_collects_artifacts_per_task(tmp_path):
    """Each attempted smoke task produces agent.log, transcript.jsonl, usage.json."""
    # Arrange
    orchestrator = SmokeRunOrchestrator(
        model="test-model",
        base_url="http://localhost:8000",
        api_key="test-key",
        output_base=tmp_path / "smoke-output",
        timeout=5,
        mode="local",
    )
    # Act
    report = orchestrator.run()
    # Assert
    for result in report.results:
        if result.status in ("pass", "fail", "timeout"):
            assert result.artifact_paths.get("log") is not None
            assert result.artifact_paths.get("transcript") is not None
            assert result.artifact_paths.get("usage") is not None


def test_smoke_run_skips_unavailable_dependencies(tmp_path):
    """Tasks with missing dependencies are skipped, not failed."""
    # Arrange
    orchestrator = SmokeRunOrchestrator(
        model="test-model",
        base_url="http://localhost:8000",
        api_key="test-key",
        output_base=tmp_path / "smoke-output",
        timeout=5,
        mode="local",
    )
    # Act
    report = orchestrator.run()
    # Assert — any skipped tasks should have documented reasons
    skipped = [r for r in report.results if r.status == "skip"]
    for result in skipped:
        assert result.failure_reason is not None
        assert len(result.failure_reason) > 0


def test_smoke_run_report_json_and_markdown(tmp_path):
    """Smoke run produces both JSON and Markdown summary reports."""
    # Arrange
    orchestrator = SmokeRunOrchestrator(
        model="test-model",
        base_url="http://localhost:8000",
        api_key="test-key",
        output_base=tmp_path / "smoke-output",
        timeout=5,
        mode="local",
    )
    # Act
    report = orchestrator.run()
    # Assert
    json_path = tmp_path / "smoke-output" / "smoke-report.json"
    md_path = tmp_path / "smoke-output" / "smoke-report.md"
    assert json_path.exists()
    assert md_path.exists()
```

### Key Test Scenarios

- [x] **Scenario 1**: Full smoke run with mock agent produces a report with all 6 categories covered
- [x] **Scenario 2**: Each attempted task collects agent.log, transcript.jsonl, and usage.json artifacts
- [x] **Edge case**: Tasks with missing dependencies are skipped (not failed) with documented reasons

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for SmokeTaskSelector, categorize_failure, SmokeReportGenerator — test error handling, edge cases
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Run smoke script against a live local model endpoint and verify artifacts are produced
- [x] Verify smoke-run report accurately reflects pass/fail/skip status for each task

### Performance Considerations

- [x] Smoke runs are bounded by per-task timeout (default 300s) — no performance concern for 6–12 tasks

## Proposed Changes

### Smoke-Run Orchestration

#### [NEW] src/tinycua/tinycua/cli/smoke_run.py

- **Description**: Core smoke-run orchestration module containing `SmokeTask`, `SmokeResult`, `SmokeReport` dataclasses, `SmokeTaskSelector`, `SmokeRunOrchestrator`, `categorize_failure()`, and `SmokeReportGenerator`.
- **Dependencies**: `tinycua.wildclawbench.agent.TinyCUAAgent`, `tinycua.cli.transcript` (for artifact writing patterns), `tinycua.cli._common` (for shared CLI utilities)
- **Rationale**: All smoke-run logic lives in one module. The orchestrator wires task selection → execution → artifact collection → report generation.

#### [NEW] src/tinycua/tests/unit/test_smoke_run.py

- **Description**: Unit tests for SmokeTaskSelector (category coverage, skip logic), categorize_failure (each failure category), SmokeReportGenerator (correct aggregation), idempotency (re-run does not corrupt artifacts).
- **Dependencies**: `tinycua.cli.smoke_run`

#### [NEW] src/tinycua/tests/integration/test_smoke_run_integration.py

- **Description**: Integration tests for end-to-end smoke run with mock agent → artifact collection → report generation.
- **Dependencies**: `tinycua.cli.smoke_run`, `tinycua.wildclawbench.agent`

### CLI Integration

#### [MODIFY] src/tinycua/tinycua/cli/main.py

- **Description**: Register `tinycua smoke-run` subcommand with flags: `--model`, `--base-url`, `--api-key`, `--timeout`, `--mode`, `--output`.
- **Rationale**: Exposes the smoke-run orchestrator via the CLI entry point.
- **Breaking changes**: None — adds a new subcommand only.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/cli/smoke_run.py` | New | Smoke-run orchestration — task selection, execution, collection, reporting |
| `tinycua/cli/main.py` | Modify | Register `smoke-run` subcommand |
| `tests/unit/test_smoke_run.py` | New | Unit tests for smoke-run components |
| `tests/integration/test_smoke_run_integration.py` | New | Integration tests for end-to-end smoke run |

## Data Model Changes

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

## API Changes

### New CLI Subcommand

| Command | Description |
|---------|-------------|
| `tinycua smoke-run --model M --base-url URL --output DIR` | Run smoke tasks across all WildClawBench categories |

### Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--model` | str | env `TINYCUA_MODEL` | Model name |
| `--base-url` | str | env `TINYCUA_BASE_URL` | LLM API base URL |
| `--api-key` | str | env `TINYCUA_API_KEY` | LLM API key |
| `--timeout` | int | 300 | Per-task timeout in seconds |
| `--mode` | str | "local" | Execution mode: "local" or "docker" |
| `--output` | Path | `./smoke-runs` | Base output directory |
| `--verbose` | flag | False | Enable debug logging |

## Dependencies

### External Dependencies

- [x] No new external packages required — uses stdlib + existing tinycua dependencies

### Internal Dependencies

- [x] Depends on Milestone 5.2: `tinycua/wildclawbench/agent.py` (TinyCUAAgent adapter)
- [x] Depends on Milestone 5.4: `tinycua/cli/transcript.py` (transcript/usage writing patterns)
- [x] Blocks Milestone 5.6: Full 60-task benchmark run will reuse smoke-run infrastructure

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Local model endpoint too slow for smoke-run iteration | Medium | Allow per-task timeout override; support mock agent mode for testing |
| WildClawBench task prompts reference capabilities TinyCUA doesn't have | Low | Dependency-based skip logic with documented reasons |
| Docker image build fails due to missing system dependencies | Medium | Document required dependencies; fallback to local CLI mode |
| Static task list becomes stale as WildClawBench evolves | Low | Static list is intentional for prototype; document update process |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-14*
