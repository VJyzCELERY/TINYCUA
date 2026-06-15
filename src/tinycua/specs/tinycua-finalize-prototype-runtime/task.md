# Tasks: TinyCUA Final Prototype Runtime

Implementation tasks for TinyCUA Final Prototype Runtime. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write final runtime integration tests from `implementation-plan.md` <!-- id: 0 -->
- [x] Write contract guardrail unit tests for stubs, message payloads, and routing <!-- id: 1 -->
- [x] Write task/session state, tool feedback, workspace isolation, node, worker runtime, streaming, CLI, notebook, and live LLM tests <!-- id: 2 -->
- [x] Run new tests and confirm RED before implementation <!-- id: 3 -->

## Implementation Phase

- [x] Phase 0 — Contract guardrails <!-- id: 4 -->
  - [x] Add no-runtime-stubs guardrail.
  - [x] Add message contract guardrail.
  - [x] Add route contract guardrail.
- [x] Phase 1 — Task state foundation <!-- id: 5 -->
  - [x] Implement typed task tree state, active traversal, transitions, reviewer decisions, artifacts, serialization, and query helpers.
  - [x] Bind task/todo/workspace/artifact/transition state to sessions.
- [x] Phase 2 — Tool execution and feedback <!-- id: 6 -->
  - [x] Feed provider-compatible tool results back into LLM continuation calls.
  - [x] Make task tools session-bound, typed, error-safe, and active-task-aware.
  - [x] Make todo tools session-bound instead of module-global.
  - [x] Bind native tools to workspace context and reject out-of-workspace paths.
- [x] Phase 3 — Concrete task nodes <!-- id: 7 -->
  - [x] Implement task creation behavior.
  - [x] Implement analyzer, effort, assessor, executor, reviewer, and aggregation nodes.
- [x] Phase 4 — Dynamic worker runtime <!-- id: 8 -->
  - [x] Add state-driven worker runtime controller.
  - [x] Keep worker node route-focused and delegate lifecycle transitions.
- [x] Phase 5 — Streaming runtime <!-- id: 9 -->
  - [x] Unify sync/stream node execution and expose final-response-only stream mode.
  - [x] Emit route/tool-result/debug events separately from final response tokens.
  - [x] Capture CLI final stream, debug trace, task tree, artifacts, and usage separately.
- [x] Phase 6 — Notebook acceptance demo <!-- id: 10 -->
  - [x] Update notebook contract/demo coverage without synthetic success.
- [x] Phase 7 — Live LLM acceptance gate <!-- id: 11 -->
  - [x] Add live tests for passthrough, worker lifecycle, tool feedback, streaming, and artifacts.

## Testing Phase

- [x] Run phase-specific deterministic unit and integration tests from `implementation-plan.md` <!-- id: 12 -->
- [ ] Run existing suite: `cd src/tinycua && uv run pytest -q` <!-- id: 13 -->
- [x] Run live LLM tests: `cd src/tinycua && TINYCUA_LIVE_LLM=1 uv run pytest tests/integration/test_default_agent_flow_live.py tests/integration/test_final_prototype_live.py -q` <!-- id: 14 -->
- [x] Run live notebook contract: `cd src/tinycua && TINYCUA_LIVE_LLM=1 uv run pytest tests/integration/test_notebook_contract_live.py -q` <!-- id: 15 -->

## Verification Phase

- [x] Verify no files under `src/tinycua-sdk/` were modified <!-- id: 16 -->
- [x] Verify local LLM endpoint health at `http://localhost:1234/v1/models` <!-- id: 17 -->
- [x] Verify notebook/CLI artifacts, task tree export, route/tool decisions, and no fallback-as-success <!-- id: 18 -->
- [ ] Verify worker event volume and task tree snapshots are bounded <!-- id: 19 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-15*
