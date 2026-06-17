# Tasks: agents-benchmark

Implementation tasks for agents-benchmark. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for pipeline (test_pipeline_integration.py) <!-- id: 0 -->
  - [x] test_pipeline_runs_all_agents_in_order
  - [x] test_pipeline_filters_agents
  - [x] test_pipeline_skips_failed_agent_and_continues
- [x] Write integration tests for N-way comparison (test_compare_agents.py) <!-- id: 1 -->
  - [x] test_compare_agents_produces_per_task_deltas
  - [x] test_compare_agents_empty_results
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2 -->
  - [x] `cd src/agents-benchmark && uv run pytest tests/integration/ -v` fails as expected

## Implementation Phase

- [x] Create package skeleton <!-- id: 3 -->
  - [x] Create `src/agents-benchmark/pyproject.toml` with metadata, deps, ruff/pytest config
  - [x] Create `src/agents-benchmark/Makefile` with lint, test, clean, format targets
  - [x] Create `src/agents-benchmark/agents_benchmark/__init__.py` (empty initially)
  - [x] Create `src/agents-benchmark/agents_benchmark/__main__.py` stub
  - [x] Verify: `cd src/agents-benchmark && uv run python -m agents_benchmark --help` works
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest` — no tests yet, should pass (0 collected)
- [x] Migrate base_agent.py from hermes-benchmark <!-- id: 4 -->
  - [x] Copy `src/hermes-benchmark/hermes_benchmark/base_agent.py` → `src/agents-benchmark/agents_benchmark/base_agent.py`
  - [x] Verify imports work: `cd src/agents-benchmark && uv run python -c "from agents_benchmark.base_agent import BaseAgent, AgentTaskSpec, AgentExecution"`
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest` passes
- [x] Implement AgentConfig and config loader <!-- id: 5 -->
  - [x] Create `src/agents-benchmark/agents_benchmark/config.py` with `AgentConfig` dataclass
  - [x] Implement `load_config()` function (YAML + env var resolution)
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_agent_config.py -v`
- [x] Write unit tests for AgentConfig <!-- id: 6 -->
  - [x] Create `src/agents-benchmark/tests/unit/test_agent_config.py`
  - [x] Test: valid config loads correctly
  - [x] Test: missing required fields raises ValueError
  - [x] Test: env var interpolation in config values
  - [x] Test: default values applied when optional fields missing
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_agent_config.py -v` — all GREEN
- [x] Implement AgentRegistry <!-- id: 7 -->
  - [x] Create `src/agents-benchmark/agents_benchmark/agent_registry.py`
  - [x] Implement `register(name, adapter_class)`, `get(name)`, `list_all()`
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_agent_registry.py -v`
- [x] Write unit tests for AgentRegistry <!-- id: 8 -->
  - [x] Create `src/agents-benchmark/tests/unit/test_agent_registry.py`
  - [x] Test: register and get adapter by name
  - [x] Test: get unknown adapter raises KeyError
  - [x] Test: list_all returns registered names
  - [x] Test: register overwrites existing adapter
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_agent_registry.py -v` — all GREEN
- [x] Migrate HermesAgent adapter <!-- id: 9 -->
  - [x] Create `src/agents-benchmark/agents_benchmark/agents/__init__.py`
  - [x] Copy `src/hermes-benchmark/hermes_benchmark/hermes_agent.py` → `src/agents-benchmark/agents_benchmark/agents/hermes.py`
  - [x] Update imports: `hermes_benchmark` → `agents_benchmark`
  - [x] Rename class to `HermesAgentAdapter` for clarity
  - [x] Copy `src/hermes-benchmark/hermes_benchmark/hermes_config.py` → `src/agents-benchmark/agents_benchmark/agents/hermes_config.py` (if needed)
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_base_agent.py -v`
- [x] Implement stub adapters for ClaudeCode, Codex, OpenClaw <!-- id: 10 -->
  - [x] Create `src/agents-benchmark/agents_benchmark/agents/claudecode.py` — stub implementing BaseAgent
  - [x] Create `src/agents-benchmark/agents_benchmark/agents/codex.py` — stub implementing BaseAgent
  - [x] Create `src/agents-benchmark/agents_benchmark/agents/openclaw.py` — stub implementing BaseAgent
  - [x] Each stub must implement all abstract methods from BaseAgent
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_base_agent.py -v`
- [x] Migrate and extend compare module <!-- id: 11 -->
  - [x] Copy `src/hermes-benchmark/hermes_benchmark/compare_results.py` → `src/agents-benchmark/agents_benchmark/compare.py`
  - [x] Generalize `compare_results()` to `compare_agents()` for N agents
  - [x] Update output format: dynamic agent names instead of hardcoded tinycua/hermes
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_compare_results.py -v`
- [x] Write unit tests for N-way comparison <!-- id: 12 -->
  - [x] Create `src/agents-benchmark/tests/unit/test_compare_results.py`
  - [x] Test: 2-agent comparison produces correct deltas (migrated tests)
  - [x] Test: N-agent comparison (3+ agents) produces correct deltas
  - [x] Test: empty results handled gracefully
  - [x] Test: missing tasks in some agents appear with nulls
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_compare_results.py -v` — all GREEN
- [x] Implement BenchmarkRunner <!-- id: 13 -->
  - [x] Create `src/agents-benchmark/agents_benchmark/runner.py`
  - [x] Implement `run_pipeline(agents, model, ...)` — sequential agent execution
  - [x] Implement `run_single_agent(agent_name, tasks, model)` — single agent, all tasks
  - [x] Implement `run_single_task(agent, task_spec)` — single task, single agent
  - [x] Implement agent filtering logic
  - [x] Implement error handling: skip failed agents, continue pipeline
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_benchmark_runner.py -v`
- [x] Write unit tests for BenchmarkRunner <!-- id: 14 -->
  - [x] Create `src/agents-benchmark/tests/unit/test_benchmark_runner.py`
  - [x] Test: pipeline runs agents in correct order
  - [x] Test: agent filtering works (--agents hermes,openclaw)
  - [x] Test: failed agent is skipped, others continue
  - [x] Test: empty agent list produces empty results
  - [x] Test: pipeline result contains summary per agent
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run pytest tests/unit/test_benchmark_runner.py -v` — all GREEN
- [x] Implement CLI entry point <!-- id: 15 -->
  - [x] Implement `src/agents-benchmark/agents_benchmark/__main__.py` with argparse
  - [x] Default subcommand: run pipeline (--model, --agents, --category, --parallel, --results-dir)
  - [x] `compare` subcommand: compare results (--results-dir, --output)
  - [x] Update `__init__.py` with public API exports
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run python -m agents_benchmark --help` shows options
  - [x] **Test requirement**: `cd src/agents-benchmark && uv run python -m agents_benchmark compare --help` shows options

## Testing Phase

- [x] Run integration tests — expect GREEN <!-- id: 16 -->
  - [x] `cd src/agents-benchmark && uv run pytest tests/integration/ -v` — all pass
- [x] Run full unit test suite <!-- id: 17 -->
  - [x] `cd src/agents-benchmark && uv run pytest tests/unit/ -v` — all pass
- [x] Run complete test suite <!-- id: 18 -->
  - [x] `cd src/agents-benchmark && uv run pytest` — all tests pass
- [x] Run lint checks <!-- id: 19 -->
  - [x] `cd src/agents-benchmark && uv run ruff check` — no errors
  - [x] `cd src/agents-benchmark && uv run ruff format --check` — no formatting issues

## Verification Phase

- [x] Verify CLI works end-to-end <!-- id: 20 -->
  - [x] `cd src/agents-benchmark && uv run python -m agents_benchmark --help` shows correct usage
  - [x] `cd src/agents-benchmark && uv run python -m agents_benchmark compare --help` shows correct usage
- [x] Verify package installs cleanly <!-- id: 21 -->
  - [x] `cd src/agents-benchmark && uv run pip install -e .` succeeds
  - [x] Verify no import errors in any module
- [ ] Delete old hermes-benchmark subproject <!-- id: 22 -->
  - [ ] Verify agents-benchmark passes all tests first
  - [ ] Remove `src/hermes-benchmark/` directory
  - [ ] Update any root-level references to hermes-benchmark
  - [ ] Verify no broken imports elsewhere in the project

## Documentation Phase

- [ ] Update spec.md success criteria with checkmarks <!-- id: 23 -->
- [ ] Verify all spec acceptance scenarios are covered by tests <!-- id: 24 -->

## Review and Merge

- [ ] Create pull request for feature/agent-benchmark <!-- id: 25 -->
  - [ ] Use PR body template from `.agents/templates/PR-body.md`
  - [ ] Include spec and design references
- [ ] Address review feedback <!-- id: 26 -->
- [ ] Merge to main branch <!-- id: 27 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-17*
