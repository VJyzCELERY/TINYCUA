# Design Document: End-to-End Integration Gate

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-12
**Milestone**: 3.5 — E2E Integration Gate

---

## Overview

This design implements a repeatable end-to-end verification gate that exercises the full TinyCUA architecture across all documented node paths — from `create_tinycua_agent(...)` through QueryAnalyst classification, WorkerNode task creation, execution/review loops, aggregation, and final response. The gate produces a structured verification report with per-path pass/fail status, timing, and artifact references. It is the final checkpoint before WildClawBench integration (Milestone 5.x).

---

## Architecture

### Component Overview

```text
verify_e2e_architecture(config)
  │
  ├─ Path 1: passthrough
  │   create_agent → QA → PASSTHROUGH route → ResponseNode
  │
  ├─ Path 2: worker_task_creation
  │   create_agent → QA → Worker → TaskCreate → TaskAnalyzer(initial)
  │
  ├─ Path 3: task_recreation_reanalysis
  │   create_agent → QA → Worker → TaskAnalyzer(recreation/reanalysis)
  │
  ├─ Path 4: proceed_execution
  │   create_agent → QA → Worker → TaskExecutor → ResultReviewer(accept)
  │
  ├─ Path 5: effort_loop
  │   create_agent → QA → Worker → AnalysisEffort → [TaskAssessor → TaskAnalyzer] × N
  │
  ├─ Path 6: executor_reviewer_retry_replan
  │   create_agent → QA → Worker → TaskExecutor → ResultReviewer(retry → replan)
  │
  ├─ Path 7: aggregation
  │   create_agent → ... → ResultAggregation → ResponseNode
  │
  ├─ Path 8: response
  │   create_agent → ... → ResponseNode(final synthesis)
  │
  └─ Path 9: response_suspension_digestion
      create_agent → ... → ResponseNode(suspend) → InformationDigester → ResponseNode(resume)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| tinycua.verification.gate | New | `verify_e2e_architecture()` entry point, path orchestration |
| tinycua.verification.paths | New | Path definitions mapping names to node execution sequences |
| tinycua.verification.report | New | `VerificationReport`, `PathResult` models |
| tinycua.verification.isolation | New | Fresh agent instantiation and state isolation per path |
| tinycua.verification.artifacts | New | Transcript, log, and task output collection |
| tinycua.factory | No change | Existing `create_tinycua_agent()` is the entry point for each path |
| tinycua.loops.* | No change | Existing nodes are exercised, not modified |
| tinycua.models.* | No change | Existing models are used for verification output |

---

## Data Model

### New Entities

```python
# VerificationReport — aggregated result of all path verifications
VerificationReport:
    overall_pass: bool              # True only if all paths pass
    paths: list[PathResult]         # Per-path results
    total_duration_ms: float        # Wall-clock time for entire gate
    artifact_dir: str               # Directory containing all artifacts
    timestamp: datetime             # When the gate was run

# PathResult — individual path verification outcome
PathResult:
    path_name: str                  # e.g., "passthrough", "worker_task_creation"
    pass: bool                      # True if path completed without error
    duration_ms: float              # Wall-clock time for this path
    node_trace: list[str]           # Ordered list of nodes executed
    error: str | None               # Error message if failed
    error_type: str | None          # "timeout", "llm_error", "queue_stall", "validation", etc.
    transcript_path: str | None     # Path to transcript artifact
    log_path: str | None            # Path to log artifact
    task_output_path: str | None    # Path to task output artifact
    retry_count: int                # Number of retries that occurred

# VerificationPath — definition of what to verify
VerificationPath:
    name: str                       # Unique path identifier
    description: str                # Human-readable description
    query: str                      # Input query to trigger this path
    expected_nodes: list[str]       # Expected node execution order (for validation)
    timeout_ms: int                 # Per-path timeout
    config_overrides: dict          # Optional agent/session config overrides
```

### Schema Changes

- No changes to existing data structures. The verification models are new and self-contained.

---

## API / Interface Contracts

### New Functions

```python
def verify_e2e_architecture(
    *,
    local_endpoint: str | None = None,
    mock_llm: bool = True,
    artifact_dir: str = "./tmp/e2e-verification",
    path_timeout_ms: int = 30_000,
    overall_timeout_ms: int = 300_000,
) -> VerificationReport:
    """
    Run the full E2E verification gate across all documented architecture paths.

    Args:
        local_endpoint: URL for local LLM endpoint. Required when mock_llm=False.
        mock_llm: If True, use a mock LLM for deterministic, fast CI runs.
        artifact_dir: Directory for transcripts, logs, and task outputs.
        path_timeout_ms: Timeout per individual path (ms).
        overall_timeout_ms: Timeout for the entire gate (ms).

    Returns:
        VerificationReport with per-path results and overall status.

    Raises:
        ValueError: If mock_llm=False and local_endpoint is None.
    """
```

```python
def _verify_path(
    path: VerificationPath,
    *,
    local_endpoint: str | None,
    mock_llm: bool,
    artifact_dir: str,
    timeout_ms: int,
) -> PathResult:
    """
    Run a single verification path with a fresh agent instance.

    Creates a new agent, sends the path's query, collects artifacts,
    and returns the path result. Isolation is guaranteed by fresh agent
    instantiation per path.
    """
```

```python
def _build_verification_paths() -> list[VerificationPath]:
    """
    Return the ordered list of all architecture paths to verify.

    Each path defines the input query, expected node sequence, timeout,
    and any config overrides needed to trigger that specific path.
    """
```

```python
def _collect_artifacts(
    path_name: str,
    agent: Agent,
    artifact_dir: str,
) -> tuple[str | None, str | None, str | None]:
    """
    Collect transcript, log, and task output artifacts for a completed path.

    Returns (transcript_path, log_path, task_output_path). Each may be None
    if the artifact was not produced.
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `mock_llm=False` and no `local_endpoint` | `ValueError("local_endpoint required when mock_llm=False")` | Startup validation |
| Path exceeds per-path timeout | `PathResult(pass=False, error_type="timeout")` | Path terminated, gate continues |
| Overall gate exceeds timeout | `VerificationReport` with partial results | Gate terminates, non-zero exit |
| Agent instantiation fails | `PathResult(pass=False, error_type="agent_error")` | Path skipped, gate continues |
| LLM returns invalid output | `PathResult(pass=False, error_type="validation")` | Retry may succeed; if exhaustion → fail |
| Queue stalls (no active node, no terminal) | `PathResult(pass=False, error_type="queue_stall")` | Detected by timeout or empty-queue check |
| Artifact collection fails | `PathResult(transcript_path=None, ...)` | Non-fatal; path may still pass |

---

## Implementation Phases

### Phase 1 — MVP (required for initial release)

- [ ] Create `tinycua/verification/` package with `__init__.py`
- [ ] Implement `VerificationReport` and `PathResult` dataclasses
- [ ] Implement `VerificationPath` dataclass
- [ ] Implement `_build_verification_paths()` with all 9 architecture paths
- [ ] Implement `_verify_path()` with fresh agent instantiation, query execution, and artifact collection
- [ ] Implement `verify_e2e_architecture()` entry point with path orchestration and timeout enforcement
- [ ] Implement `_collect_artifacts()` for transcript/log/output extraction
- [ ] Add CLI entry point or Makefile target for running the gate
- [ ] Add unit tests for verification models and gate logic
- [ ] Add integration test for gate run against mock LLM

### Phase 2 — Enhancements (post-MVP)

- [ ] Add parallel path execution option for faster CI (paths are independent)
- [ ] Add HTML/JSON report rendering for human-readable output
- [ ] Add path dependency graph visualization
- [ ] Add regression detection (compare against previous run's report)

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Fresh agent instance per path (not queue reset)
   - **Reason**: Guarantees complete isolation — no residual session, task tree, or queue state from a previous path. Simpler to reason about and debug.
   - **Alternatives Considered**: Queue reset between paths — rejected; risks residual state in session context, chat history, or task tree that could cause false positives/negatives.

2. **Decision**: Default to mock LLM for CI, support real endpoint via flag
   - **Reason**: Mock LLM is deterministic, fast, and free — ideal for CI. Real endpoint testing is valuable but slow and requires infrastructure; it should be opt-in.
   - **Alternatives Considered**: Always use real endpoint — rejected; too slow and fragile for CI. Always use mock — rejected; no way to validate against real LLM behavior.

3. **Decision**: Verification report as a dataclass (not a file format)
   - **Reason**: The report is an in-memory structure that can be serialized to JSON, printed to stdout, or rendered as HTML. Keeping it as a dataclass keeps the gate logic decoupled from output formatting.
   - **Alternatives Considered**: JSON file directly — rejected; couples output format to gate logic. Markdown report — rejected; harder to parse programmatically.

4. **Decision**: 9 paths covering the documented architecture (not 60 WildClawBench tasks)
   - **Reason**: The gate verifies *architecture completeness*, not task-level benchmark performance. Each path exercises a specific node/routing flow. WildClawBench tasks are the responsibility of Milestone 5.x.
   - **Alternatives Considered**: Include WildClawBench tasks in the gate — rejected; that's a separate milestone with different concerns (Docker, grading, workspace management).

5. **Decision**: Per-path timeout with overall timeout as a safety net
   - **Reason**: Individual paths may hang due to LLM non-response or queue stalls. A per-path timeout ensures the gate progresses. An overall timeout prevents the entire gate from hanging if multiple paths fail simultaneously.
   - **Alternatives Considered**: Only overall timeout — rejected; a single hung path blocks all remaining paths.

6. **Decision**: Artifact collection is non-fatal
   - **Reason**: Artifact collection is best-effort. A path may produce a valid result but fail to save a transcript (e.g., disk full). The path itself should still be marked as passed; the missing artifact is noted in the report.
   - **Alternatives Considered**: Artifact collection failure = path failure — rejected; conflates I/O errors with architecture failures.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Mock LLM does not exercise real LLM behavior paths | Medium | Medium | Support real endpoint via flag; mock is for CI correctness, not LLM quality |
| Fresh agent instantiation is slow (many paths) | Low | Low | Phase 2 parallel execution; paths are independent |
| Artifact collection may fail (disk, permissions) | Low | Low | Non-fatal; logged in report; path result unchanged |
| Some paths may require specific node states that are hard to trigger deterministically | Medium | Medium | Path queries are carefully designed to trigger the target path; config overrides available |
| Queue stall detection relies on timeout, not active monitoring | Low | Medium | Per-path timeout catches stalls; overall timeout as safety net |

---

## Open Questions (optional)

1. **Should the gate be a pytest fixture, a standalone script, or both?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-12
   - **Status**: Discussion
   - **Proposed Answer**: Standalone script (Makefile target / `uv run`) for CI; pytest-compatible function for integration test suites. Both call the same `verify_e2e_architecture()` entry point.

2. **How many retry attempts should the mock LLM simulate for retry paths?**
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-12
   - **Status**: Discussion
   - **Proposed Answer**: Mock LLM should simulate exactly one retry failure followed by a success (or acceptance) to exercise the retry path without infinite loops. Configurable per path.

---

## References

- Spec: `./spec.md`
- TinyCUALoop target architecture: `src/tinycua/docs/design/loops/tinycua_loop.md`
- ResponseNode target architecture: `src/tinycua/docs/design/loops/response.md`
- ResultAggregation target architecture: `src/tinycua/docs/design/loops/result_aggregation.md`
- InformationDigester target architecture: `src/tinycua/docs/design/loops/information_digester.md`
- NodeQueue target architecture: `src/tinycua/docs/design/loops/node_queue.md`
- RouteMap target architecture: `src/tinycua/docs/design/loops/route_map.md`
- Propagation target architecture: `src/tinycua/docs/design/loops/propagation.md`
- Agent factory: `src/tinycua/tinycua/factory.py`
- Issue: https://github.com/VJyzCELERY/TINYCUA/issues/87
