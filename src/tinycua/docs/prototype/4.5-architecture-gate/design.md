# Design Document: End-to-End TinyCUA Architecture Verification Gate

**Spec**: `src/tinycua/specs/4.5-architecture-gate/spec.md`
**Status**: Ready
**Last Updated**: 2026-06-13

---

## Overview

This design defines the verification gate infrastructure for proving all 12 TinyCUA architecture paths work end-to-end with a local LLM. The gate is a standalone test harness that orchestrates path execution, validates outcomes, and produces pass/fail verdicts. No source code modifications are made — this is purely verification infrastructure.

---

## Architecture

### Component Overview

```
Verification Gate
  │
  ├── Path Registry
  │     └── 12 Architecture Paths (node sequences + expected outcomes)
  │
  ├── LLM Client
  │     └── Local LLM Endpoint (configurable)
  │
  ├── Path Executor
  │     ├── Node Sequence Runner
  │     ├── Session Config
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
| `tests/verification/executor.py` | New | Path execution engine — instantiates actual TinyCUA nodes and runs them through NodeQueue |
| `tests/verification/reporter.py` | New | Result collection and reporting |
| `tests/verification/config.py` | New | Configuration (LLM endpoint, timeouts) — reads from existing TinyCUA `LocalModelConfig` (from `tinycua.config.local_model`) |
| `tests/verification/test_gate.py` | New | Pytest entry point for the gate |
| `tests/verification/cross_cutting.py` | New | Cross-cutting concern verification (propagation, dedupe, tool scoping, retry, streaming) |
| `tinycua.loops.node` | Existing | `ProcessNode` and `DecisionNode` — generic node classes used by PathExecutor for logical nodes (TaskAssessor, TaskAnalyzer, etc.) configured with tool scopes from `tool_scopes.py` |
| `tinycua.SessionConfig` | Existing | Session configuration — used by PathExecutor for session isolation per path |
| `tinycua.config.tool_scopes` | Existing | Tool scope definitions — provides `NodeToolPolicy` for logical nodes (`task_assessor_tool_scope()`, `task_analyzer_tool_scope()`, etc.) |

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
    total_paths: int                   # 12
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

### GateConfig

```python
from dataclasses import dataclass, field
from tinycua.config.local_model import LocalModelConfig


@dataclass
class GateConfig:
    """Configuration for the verification gate.

    Wraps LocalModelConfig (LLM endpoint, model, API key) and adds
    verification-specific settings (timeouts, output paths).
    """
    local_model_config: LocalModelConfig
    default_timeout_seconds: int = 120
    output_dir: str = "test-results"

    @classmethod
    def from_env(cls) -> "GateConfig":
        """Construct GateConfig from environment variables.

        Reads OPENAI_CHAT_COMPLETIONS_BASE_URL, OPENAI_CHAT_COMPLETIONS_MODEL,
        and OPENAI_CHAT_COMPLETIONS_API_KEY, then builds a LocalModelConfig
        and wraps it with verification-specific defaults.
        """
        ...
```

### Gate Orchestrator

```python
class VerificationGate:
    """Main orchestrator for architecture verification."""

    def __init__(self, config: GateConfig):
        """Initialize with LLM endpoint and timeout configuration."""

    def run_all(self) -> VerificationReport:
        """Run all 12 paths and produce aggregate report."""

    def run_path(self, path_name: str) -> PathResult:
        """Run a single path by name."""

    def run_paths(self, path_names: list[str]) -> VerificationReport:
        """Run specific paths and produce report."""
```

### Path Executor

```python
class PathExecutor:
    """Executes a single architecture path using actual TinyCUA nodes and NodeQueue."""

    def __init__(self, gate_config: GateConfig):
        """Initialize with GateConfig for LLM and timeout settings.
        Session isolation is handled internally via SessionConfig."""

    def execute(self, path: ArchitecturePath) -> PathResult:
        """Instantiate nodes, run through NodeQueue, and return results."""
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

## PathExecutor and NodeQueue Integration

The verification gate must verify the **real** TinyCUA architecture, not a test harness imitation. PathExecutor achieves this by instantiating actual TinyCUA nodes and running them through the existing `NodeQueue` execution engine.

### Node Name Mapping

The following table maps each spec node name to its actual Python class and import path. Nodes with dedicated classes are imported directly; logical-only nodes are instantiated as generic `ProcessNode` instances configured with the appropriate `NodeToolPolicy` from `tinycua.config.tool_scopes`.

| Spec Name | Python Class | Import Path | Notes |
|-----------|-------------|-------------|-------|
| QueryAnalyst | `TinyCUAQueryAnalystNode` | `tinycua.loops.query_analyst` | Dedicated class |
| InformationDigester | `TinyCUAInformationDigesterNode` | `tinycua.loops.information_digester` | Dedicated class |
| Worker | `TinyCUAWorkerNode` | `tinycua.loops.worker` | Dedicated class |
| TaskCreation | `TinyCUATaskCreateNode` | `tinycua.loops.task_create` | Dedicated class |
| PrimaryAgent | `ResponseNode` | `tinycua.loops.response_node` | Different name in codebase |
| TaskAssessor | `ProcessNode` (generic) | `tinycua.loops.node` | Configured with `task_assessor_tool_scope()` from `tool_scopes.py` |
| TaskAnalyzer | `ProcessNode` (generic) | `tinycua.loops.node` | Configured with `task_analyzer_tool_scope()` from `tool_scopes.py` |
| TaskExecutor | `ProcessNode` (generic) | `tinycua.loops.node` | Configured with `task_executor_tool_scope()` from `tool_scopes.py` |
| ResultReviewer | `ProcessNode` (generic) | `tinycua.loops.node` | Configured with `result_reviewer_tool_scope()` from `tool_scopes.py` |
| ResultAggregationNode | `ProcessNode` (generic) | `tinycua.loops.node` | Configured with `result_aggregation_tool_scope()` from `tool_scopes.py` |

### How It Works

1. **Node Instantiation**: For each path, PathExecutor resolves the node name to a class using the mapping above, then instantiates the node. Dedicated classes (`TinyCUAQueryAnalystNode`, etc.) are imported and created with their real config dataclasses. Logical-only nodes (`TaskAssessor`, etc.) are instantiated as generic `ProcessNode` instances with the appropriate `NodeToolPolicy` from `tool_scopes.py`.

2. **NodeQueue Execution**: PathExecutor feeds the instantiated nodes into a `NodeQueue` and runs the queue. The queue handles the real execution lifecycle: session creation, message building, LLM calls, output validation, propagation, and retry.

3. **No Parallel Execution Engine**: The verification gate does **not** create its own node runner or execution loop. It delegates entirely to `NodeQueue`, which is the same execution path used in production. This ensures we verify the actual architecture, not a simplified reimplementation.

4. **Session Isolation**: Each path gets a fresh `Session` via `SessionConfig`, ensuring no cross-path state leakage. The session is configured with the same LLM endpoint and model settings used in production.

### NodeQueue Lifecycle per Path

```text
PathExecutor.execute(path):
  1. Create fresh Session from SessionConfig
  2. Instantiate nodes from path.node_sequence
  3. Build NodeQueue with instantiated nodes
  4. Run NodeQueue → captures node outputs, session state, LLM interactions
  5. Validate final state against path.expected_outcome
  6. Return PathResult with full interaction log
```

### Why This Matters

If the gate reimplemented execution logic, it would verify the gate's own logic rather than the real architecture. By using `NodeQueue`, every node's real config, tool scope, retry policy, propagation rule, and streaming behavior is exercised. Failures in the gate point to real architecture issues, not test harness bugs.

---

## LLM Client Configuration

The verification gate does **not** create a new LLM client. It reuses the existing TinyCUA `LocalModelConfig` and `SessionConfig` to configure the LLM endpoint and session isolation respectively.

### Configuration Source

```text
tests/verification/config.py
  → reads from environment variables (OPENAI_CHAT_COMPLETIONS_BASE_URL, etc.)
  → constructs GateConfig which wraps LocalModelConfig for LLM endpoint settings
  → PathExecutor receives GateConfig (via VerificationGate), uses LocalModelConfig
    for LLM interactions and creates SessionConfig for session isolation per path
```

### Default Model

The default verification model is `qwen/qwen3.5-4b`, configured via `OPENAI_CHAT_COMPLETIONS_MODEL`. The endpoint defaults to the local LLM server (configurable per environment).

### Why Reuse Existing Config

Using `LocalModelConfig` (for LLM endpoint, model, API key) and `SessionConfig` (for session isolation) ensures the verification gate tests the real LLM integration path — including provider selection, model resolution, API key handling, and base URL configuration. A custom LLM client would bypass these mechanisms and reduce verification fidelity.

---

## Cross-Cutting Concern Verification

Cross-cutting concerns (propagation/dedupe, tool scoping, retry/validation, streaming) are verified **as part of path execution**, not as separate paths. Each path logs these behaviors during execution, and the gate validates them against expected patterns.

### What Is Verified Per Path

| Concern | Verification Approach | Logged In |
|---------|----------------------|-----------|
| **Context propagation** | Verify that accepted task results propagate to future task contexts | `node_outputs` — track which tasks received context updates |
| **Dedupe** | Verify that no duplicate context is propagated to the same task | `node_outputs` — check for redundant context entries |
| **Tool scoping** | Verify each node only accesses tools allowed by its `NodeToolPolicy` | `node_outputs` — record tool invocations per node |
| **Retry behavior** | Verify retry creates new sub-session with failure context | `llm_interactions` — track retry count and session boundaries |
| **Output validation** | Verify `validate_output()` is called on every node response | `node_outputs` — record validation outcomes |
| **Streaming** | Verify streaming behavior matches node's `StreamPolicy` | `llm_interactions` — record streaming vs batch per node |

### How It Works

Each `PathExecutor` includes a `CrossCuttingCollector` (defined in `tests/verification/cross_cutting.py` and instantiated by `PathExecutor`) that hooks into the node execution lifecycle:

1. **Before node execution**: Record expected tool scope from `NodeToolPolicy`.
2. **After node execution**: Record actual tool invocations, output validation result, retry count.
3. **After path completion**: Validate cross-cutting expectations against collected data.

Failures in cross-cutting concerns are reported as path-level warnings or failures, depending on severity. This approach ensures every path exercise real cross-cutting behavior without duplicating verification across 12 separate paths.

---

## Implementation Phases

### Phase 1 — Path Definitions (required)

- [ ] Define all 12 architecture paths with node sequences and expected outcomes
- [ ] Create path registry with lookup by name
- [ ] Define path validation criteria (what constitutes success/failure)

### Phase 2 — Executor Infrastructure (required)

- [ ] Implement PathExecutor that runs node sequences against LLM
- [ ] Implement session isolation via SessionConfig
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
   - **Owner**: @VJyzCELERY
   - **Target**: Use `qwen/qwen3.5-4b` via `OPENAI_CHAT_COMPLETIONS_MODEL`. Configurable endpoint via existing TinyCUA `SessionConfig` mechanisms.
   - **Status**: Resolved
   - **Answer**: Use `qwen/qwen3.5-4b` via `OPENAI_CHAT_COMPLETIONS_MODEL`. Configurable endpoint via existing TinyCUA `SessionConfig` mechanisms.

2. **Should the gate support running against cloud LLM endpoints for comparison?**
   - **Owner**: @VJyzCELERY
   - **Target**: Not in this milestone. Local-only for reproducibility. Cloud support as follow-up.
   - **Status**: Resolved
   - **Answer**: Not in this milestone. Local-only for reproducibility. Cloud support as follow-up.

3. **How many times should each path run to account for LLM non-determinism?**
   - **Owner**: @VJyzCELERY
   - **Target**: Single run for initial verification. Multiple runs as a follow-up for robustness.
   - **Status**: Resolved
   - **Answer**: Single run for initial verification. Multiple runs as a follow-up for robustness.

---

## References

- Spec: `src/tinycua/specs/4.5-architecture-gate/spec.md`
- Architecture docs: `src/tinycua/docs/architecture/README.md`
- Route map: `src/tinycua/docs/design/loops/route_map.md`
- Worker orchestration: `src/tinycua/docs/architecture/worker-orchestration.md`
- Query analyst: `src/tinycua/docs/architecture/query-analyst.md`
- Result reviewer: `src/tinycua/docs/architecture/result-reviewer.md`
- Result aggregation: `src/tinycua/docs/design/loops/result_aggregation.md`
- Node hierarchy: `src/tinycua/docs/design/loops/node.md`
- State objects: `src/tinycua/docs/architecture/state-objects.md`
