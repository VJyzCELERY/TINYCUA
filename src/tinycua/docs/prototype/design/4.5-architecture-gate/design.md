# Design Document: End-to-End TinyCUA Architecture Verification Gate

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-13

---

## Overview

This design defines the verification gate infrastructure for proving all 11 TinyCUA architecture paths work end-to-end with a local LLM. The gate is a standalone test harness that orchestrates path execution, validates outcomes, and produces pass/fail verdicts. No source code modifications are made — this is purely verification infrastructure.

---

## Architecture

### Component Overview

```
Verification Gate
  │
  ├── Path Registry
  │     └── 11 Architecture Paths (node sequences + expected outcomes)
  │
  ├── LLM Client
  │     └── Local LLM Endpoint (configurable)
  │
  ├── Path Executor
  │     ├── Node Sequence Runner
  │     ├── Session Manager
  │     └── Timeout Controller
  │
  ├── Result Collector
  │     ├── Per-Path Results (pass/fail, duration, logs)
  │     └── Aggregated Report
  │
  └── Output
        ├── JSON Results File
        └── Human-Readable Summary
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tests/verification/` | New | Verification gate test infrastructure |
| `tests/verification/gate.py` | New | Main gate orchestrator |
| `tests/verification/paths.py` | New | Path definitions and registry |
| `tests/verification/executor.py` | New | Path execution engine |
| `tests/verification/reporter.py` | New | Result collection and reporting |
| `tests/verification/config.py` | New | Configuration (LLM endpoint, timeouts) |
| `tests/verification/test_gate.py` | New | Pytest entry point for the gate |

---

## Data Model

### Architecture Path

```python
# Conceptual data shape (not necessarily the final class)
ArchitecturePath:
    name: str                          # e.g., "passthrough_simple"
    description: str                   # Human-readable description
    node_sequence: list[str]           # Ordered node IDs to execute
    expected_nodes: list[str]          # Nodes that must execute
    expected_outcome: str              # "success", "hitl", "failure"
    timeout_seconds: int               # Per-path timeout
    setup_fn: Callable | None          # Optional setup (e.g., inject mandatory_passthrough)
    validation_fn: Callable | None     # Optional custom validation
```

### Path Result

```python
PathResult:
    path_name: str                     # Name of the path
    status: str                        # "pass", "fail", "timeout", "error"
    duration_seconds: float            # Execution time
    llm_interactions: list[dict]       # Full LLM interaction log
    node_outputs: dict[str, Any]       # Output from each node
    session_state: dict                # Final session state
    error: str | None                  # Error message if failed
    error_traceback: str | None        # Full traceback if exception
```

### Verification Report

```python
VerificationReport:
    overall_status: str                # "pass" or "fail"
    total_paths: int                   # 11
    passed: int                        # Count of passing paths
    failed: int                        # Count of failing paths
    timed_out: int                     # Count of timed-out paths
    path_results: list[PathResult]     # Per-path results
    summary: str                       # Human-readable summary
    timestamp: str                     # ISO 8601 timestamp
    llm_model: str                     # Model used for verification
```

---

## API / Interface Contracts

### Gate Orchestrator

```python
class VerificationGate:
    """Main orchestrator for architecture verification."""

    def __init__(self, config: GateConfig):
        """Initialize with LLM endpoint and timeout configuration."""

    def run_all(self) -> VerificationReport:
        """Run all 11 paths and produce aggregate report."""

    def run_path(self, path_name: str) -> PathResult:
        """Run a single path by name."""

    def run_paths(self, path_names: list[str]) -> VerificationReport:
        """Run specific paths and produce report."""
```

### Path Executor

```python
class PathExecutor:
    """Executes a single architecture path."""

    def __init__(self, llm_client: LLMClient, session_manager: SessionManager):
        """Initialize with LLM client and session manager."""

    def execute(self, path: ArchitecturePath) -> PathResult:
        """Execute the path and return results."""
```

### Report Generator

```python
class ReportGenerator:
    """Generates human-readable and machine-readable reports."""

    def generate_json(self, report: VerificationReport) -> str:
        """Generate JSON output."""

    def generate_summary(self, report: VerificationReport) -> str:
        """Generate human-readable summary."""
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| LLM endpoint unreachable | PathResult(status="error", error="LLM endpoint unreachable") | Gate continues with other paths |
| Path timeout | PathResult(status="timeout", error="Path exceeded timeout") | Gate continues with other paths |
| Node execution error | PathResult(status="fail", error=str(e)) | Full traceback captured |
| Session state invalid | PathResult(status="fail", error="Session state mismatch") | Expected vs actual state logged |

---

## Implementation Phases

### Phase 1 — Path Definitions (required)

- [ ] Define all 11 architecture paths with node sequences and expected outcomes
- [ ] Create path registry with lookup by name
- [ ] Define path validation criteria (what constitutes success/failure)

### Phase 2 — Executor Infrastructure (required)

- [ ] Implement PathExecutor that runs node sequences against LLM
- [ ] Implement SessionManager for path isolation
- [ ] Implement TimeoutController for per-path limits
- [ ] Implement LLM interaction logging

### Phase 3 — Gate Orchestrator (required)

- [ ] Implement VerificationGate that orchestrates path execution
- [ ] Implement parallel or sequential execution (configurable)
- [ ] Implement result aggregation and pass/fail logic

### Phase 4 — Reporting (required)

- [ ] Implement JSON output format
- [ ] Implement human-readable summary report
- [ ] Implement LLM interaction log capture for failed paths

### Phase 5 — pytest Integration (required)

- [ ] Create pytest entry point for the gate
- [ ] Support command-line path selection
- [ ] Support CI-friendly output formats

---

## Technical Decisions

1. **Decision**: Use pytest as the test runner for the verification gate.
   - **Reason**: pytest is already the project's test framework; CI integration is straightforward.
   - **Alternatives Considered**: Custom CLI — rejected because pytest provides fixtures, parameterization, and reporting out of the box.

2. **Decision**: Paths execute sequentially by default, with parallel option.
   - **Reason**: Sequential execution is simpler to debug and produces deterministic results. Parallel execution is optional for faster runs.
   - **Alternatives Considered**: Always parallel — rejected because LLM resource contention can cause flaky results.

3. **Decision**: Each path gets its own session for isolation.
   - **Reason**: Paths should not share state; session isolation prevents cross-path contamination.
   - **Alternatives Considered**: Shared session — rejected because it creates dependencies between paths.

4. **Decision**: LLM interaction logs are captured for all paths, not just failures.
   - **Reason**: Full logs enable post-hoc analysis even for passing paths (e.g., investigating unexpected LLM behavior).
   - **Alternatives Considered**: Log only failures — rejected because it loses information for debugging edge cases.

5. **Decision**: Gate produces both JSON and human-readable output.
   - **Reason**: JSON for CI integration and machine consumption; human-readable for developer debugging.
   - **Alternatives Considered**: JSON only — rejected because developers need readable output during investigation.

6. **Decision**: Path definitions are declarative (data), not imperative (code).
   - **Reason**: Declarative definitions are easier to review, modify, and extend. They separate path specification from execution logic.
   - **Alternatives Considered**: Code-based definitions — rejected because they blur the line between test infrastructure and test logic.

7. **Decision**: No source code modifications — verification only.
   - **Reason**: This milestone proves the existing implementation works; it does not add features or fix bugs.
   - **Alternatives Considered**: Fix issues found during verification — rejected because it conflates verification with implementation.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Local LLM produces inconsistent results | Medium | Medium | Run each path multiple times; report variance; use deterministic temperature settings |
| LLM resource exhaustion during long test runs | Low | Medium | Sequential execution default; configurable delays between paths |
| Path timeout too aggressive for complex paths | Medium | Low | Generous default timeouts; configurable per-path overrides |
| LLM endpoint configuration varies by environment | High | Low | Config file with environment-specific settings; clear error messages |
| Verification gate itself has bugs | Medium | High | Gate is small, focused code; manual verification of gate logic |

---

## Open Questions _(optional)_

1. **Which local LLM model and endpoint should be the default for verification?**
   - Current thinking: Use whatever model was validated in previous milestones, with a configurable endpoint.

2. **Should the gate support running against cloud LLM endpoints for comparison?**
   - Current thinking: Not in this milestone. Local-only for reproducibility. Cloud support as follow-up.

3. **How many times should each path run to account for LLM non-determinism?**
   - Current thinking: Single run for initial verification. Multiple runs as a follow-up for robustness.

---

## References

- Spec: `./spec.md`
- Architecture docs: `src/tinycua/docs/architecture/README.md`
- Route map: `src/tinycua/docs/design/loops/route_map.md`
- Worker orchestration: `src/tinycua/docs/architecture/worker-orchestration.md`
- Query analyst: `src/tinycua/docs/architecture/query-analyst.md`
- Result reviewer: `src/tinycua/docs/architecture/result-reviewer.md`
