# Tasks: TinyCUA Runtime Invariants

Implementation tasks for the TinyCUA runtime-invariants quality gate. Each implementation task is one TDD cycle: write the smallest failing invariant test, make it pass, then verify protected paths stay untouched.

## TDD Phase (Tests First)

- [x] Add runtime invariant test helpers for scripted node/LLM behavior <!-- id: 0 -->
  - [x] Provide scripted valid outputs for passthrough and worker paths.
  - [x] Provide bad-once outputs for malformed route labels, missing required tool calls, and invalid node completion.
  - [x] Provide trace helpers: `trace_node_ids()`, `trace_has_transition()`, `retry_count_by_node()` or the smallest equivalent exposed only in tests if production trace already exists.
  - [x] References: Spec `./spec.md:224-229`, `./spec.md:279-299`; source `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/tinycua_loop.md:62-84`, `src/tinycua/docs/design/loops/node.md:216-220`.

- [x] Write route matrix integration tests <!-- id: 1 -->
  - [x] Test passthrough route: `User_Query -> QueryAnalyst -> ResponseNode`.
  - [x] Test worker route includes InformationDigester, Worker, TaskCreate/TaskAnalyzer, AnalysisEffort, TaskExecutor, ResultReviewer, ResultAggregation, ResponseNode.
  - [x] Test route trace ends at ResponseNode or explicit terminal node.
  - [x] References: Spec `./spec.md:184-186`, `./spec.md:224-226`, `./spec.md:271`; source `src/tinycua/docs/design/loops/query_analyst.md:57-65`, `src/tinycua/docs/design/loops/query_analyst.md:83-101`, `src/tinycua/docs/design/loops/worker.md:75-89`, `src/tinycua/docs/design/loops/response.md:60-90`.

- [x] Write impossible-route negative tests <!-- id: 2 -->
  - [x] Reject `TaskAnalyzer -> ResponseNode`.
  - [x] Reject `TaskAnalysis -> ResponseNode` if that legacy label/path exists.
  - [x] Reject `TaskCreate -> ResponseNode`.
  - [x] Reject `TaskExecutor -> ResponseNode` before ResultReviewer.
  - [x] References: Spec `./spec.md:195-196`, `./spec.md:210`, `./spec.md:226`, `./spec.md:272`; source `src/tinycua/docs/design/loops/task_analyzer.md:53-61`, `src/tinycua/docs/design/loops/task_executor.md:44-52`, `src/tinycua/docs/design/loops/result_reviewer.md:56-91`, `src/tinycua/docs/design/loops/node.md:173-214`.

- [x] Write bad-once self-recovery integration tests <!-- id: 3 -->
  - [x] For each internal node, emit one weak/malformed/missing-contract output first.
  - [x] Assert retry/correction happens at the same node.
  - [x] Assert the route does not skip to ResponseNode or another unrelated node.
  - [x] Assert final run reaches ResponseNode/terminal node legally.
  - [x] References: Spec `./spec.md:179`, `./spec.md:187`, `./spec.md:218-219`, `./spec.md:227`, `./spec.md:273`; source `src/tinycua/docs/design/loops/tinycua_loop.md:36-38`, `src/tinycua/docs/design/loops/tinycua_loop.md:67-84`, `src/tinycua/docs/design/loops/node.md:216-220`.

- [x] Write task-decomposition preservation unit tests <!-- id: 4 -->
  - [x] Assert `task_decompose` preserves at least 25 analyzer-provided subtasks in order.
  - [x] Do not encode spec policy guidance as pytest assertions; keep policy-pattern checks in the standalone script.
  - [x] References: Spec `./spec.md:180-181`, `./spec.md:208-210`, `./spec.md:246-249`, `./spec.md:261-262`; source `src/tinycua/docs/design/loops/task_analyzer.md:6-17`, `src/tinycua/docs/design/loops/task_analyzer.md:23-31`, `src/tinycua/docs/design/models/task.md:10-28`, `src/tinycua/docs/design/tools/task.md:19-28`.

- [x] Write tool-scope unit tests <!-- id: 5 -->
  - [x] Assert InformationDigester has only retrieval/digest tools and no task/action tools.
  - [x] Assert TaskAnalyzer has structural task tools only by mode, not arbitrary write/execute tools.
  - [x] Assert only TaskExecutor and ResponseNode receive arbitrary workspace/action tools.
  - [x] References: Spec `./spec.md:183`, `./spec.md:188`, `./spec.md:213-214`, `./spec.md:228`, `./spec.md:274`; source `src/tinycua/docs/design/tools/task.md:5-18`, `src/tinycua/docs/design/loops/information_digester.md:13-18`, `src/tinycua/docs/design/loops/information_digester.md:52-58`, `src/tinycua/docs/design/loops/task_executor.md:31-43`, `src/tinycua/docs/design/loops/response.md:31-58`.

- [x] Write context propagation and dedupe unit tests <!-- id: 6 -->
  - [x] Assert internal handoffs are assistant/internal records, not recreated external user messages.
  - [x] Assert retry continuations are assistant-role.
  - [x] Assert forwarded context is selected handoff/output, not wholesale prior context.
  - [x] Assert duplicate origin records are deduped.
  - [x] References: Spec `./spec.md:182`, `./spec.md:215-216`, `./spec.md:228-229`, `./spec.md:266`, `./spec.md:275`; source `src/tinycua/docs/design/loops/node.md:66-73`, `src/tinycua/docs/design/loops/node.md:83-86`, `src/tinycua/docs/design/loops/node.md:216-220`, `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/loops/propagation.md:79-109`, `src/tinycua/docs/design/loops/propagation.md:116-135`.

- [x] Write one-shot script traceability integration test <!-- id: 7 -->
  - [x] Run `scripts/run_agent.py` with a simple prompt.
  - [x] Assert stdout contains trace, final response, task tree, workspace files, and artifacts sections.
  - [x] Assert stream mode exposes node/tool lifecycle enough to audit route order.
  - [x] References: Spec `./spec.md:224`, `./spec.md:270`; source `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/tinycua_loop.md:62-65`, `src/tinycua/docs/design/loops/node_queue.md:85-101`.

- [x] Write source-size guard unit test <!-- id: 8 -->
  - [x] Fail if any TinyCUA Python source file exceeds 1000 lines without explicit user-approved exception.
  - [x] Do not encode spec policy guidance as pytest assertions.
  - [x] References: Spec `./spec.md:63-68`, `./spec.md:220-221`, `./spec.md:269`; source `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node_queue.md:25-47`, `src/tinycua/docs/design/loops/propagation.md:30-70`.

- [x] Write standalone policy-guidance audit script, not pytest <!-- id: 9 -->
  - [x] Add `src/tinycua/scripts/check_runtime_policy_guidance.py`.
  - [x] Audit known forced-behavior strings, prompt-category special casing, task caps, and hardcoded task titles from the spec guidance.
  - [x] Exit non-zero and print matches when violations are found.
  - [x] References: Spec `./spec.md:29-42`, `./spec.md:242-255`, `./spec.md:261-262`.

- [x] Run invariant tests — expect RED before fixes <!-- id: 10 -->
  - [x] `cd src/tinycua && uv run pytest tests/integration/test_runtime_invariant_route_matrix.py -q`
  - [x] `cd src/tinycua && uv run pytest tests/integration/test_runtime_invariant_failure_recovery.py -q`
  - [x] `cd src/tinycua && uv run pytest tests/integration/test_runtime_invariant_traceability.py -q`
  - [x] `cd src/tinycua && uv run pytest tests/unit/test_runtime_invariant_task_decomposition.py tests/unit/test_runtime_invariant_tool_scopes.py tests/unit/test_runtime_invariant_context_propagation.py tests/unit/test_runtime_invariant_source_guards.py -q`
  - [x] `cd src/tinycua && uv run python scripts/check_runtime_policy_guidance.py`
  - [x] RED confirmed: 10 test failures (decomposition cap + source-size) + policy script exit 1 (8 violations). Route/retry/tool-scope/context/traceability already GREEN — those invariants hold today.

## Implementation Phase

- [x] Remove hard task-count caps and decomposition rewrites <!-- id: 11 -->
  - [x] Remove `_MAX_DECOMPOSE_SUBTASKS` or equivalent cap from `src/tinycua/tinycua/tools/task_tools.py`.
  - [x] Remove `maxItems` from task-decompose schema.
  - [x] Remove slicing/truncation of analyzer-created subtasks.
  - [x] Preserve order and content of analyzer-provided child tasks.
  - [x] References: Spec `./spec.md:208-210`, `./spec.md:246-249`; source `src/tinycua/docs/design/loops/task_analyzer.md:23-31`, `src/tinycua/docs/design/models/task.md:10-28`, `src/tinycua/docs/design/tools/task.md:19-28`.

- [x] Remove prompt-specific task behavior from node prompts/recovery <!-- id: 12 -->
  - [x] Remove app/web-ui/backend/frontend/notebook/research prompt-category special cases from runtime code.
  - [x] Remove hardcoded task titles such as “Build a minimal runnable vertical-slice app...”.
  - [x] Keep node prompts limited to role, contract, tool scope, and generic retry continuation.
  - [x] References: Spec `./spec.md:29-42`, `./spec.md:206-210`, `./spec.md:246-249`, `./spec.md:261`; source `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node.md:29-64`, `src/tinycua/docs/design/loops/task_analyzer.md:6-17`, `src/tinycua/docs/design/loops/task_analyzer.md:23-31`.

- [x] Restore generic worker effort behavior <!-- id: 13 -->
  - [x] Ensure `none` means no extra assessor/analyzer passes and still advances to TaskExecutor.
  - [x] Remove defaults that force low-effort shortcut behavior outside the design config.
  - [x] Ensure medium/high can schedule repeated `[TaskAssessor, TaskAnalyzer]` before execution.
  - [x] References: Spec `./spec.md:186`, `./spec.md:297`; source `src/tinycua/docs/design/loops/analysis_effort.md:12-29`, `src/tinycua/docs/design/loops/analysis_effort.md:30-53`, `src/tinycua/docs/design/loops/analysis_effort.md:55-60`.
  - [x] FINDING: `.env.example` default `TINYCUA_WORKER_EFFORT=none` matches the design-doc default (`analysis_effort.md:59`, `node_config.md:136-137`). No change needed — changing it would violate the source-of-truth docs.

- [x] Enforce legal route transitions in queue/route handling <!-- id: 14 -->
  - [x] Validate route labels against each owning node's RouteMap.
  - [x] Reject TaskAnalyzer/TaskCreate/TaskExecutor direct-to-Response skip paths.
  - [x] Preserve `node.on_complete()` as the only queue transition owner; loop must not advance separately after completion.
  - [x] Ensure terminal ResponseNode exists without accepting impossible task-path shortcuts.
  - [x] References: Spec `./spec.md:205`, `./spec.md:210`, `./spec.md:218`, `./spec.md:226`; source `src/tinycua/docs/design/loops/route_map.md:6-32`, `src/tinycua/docs/design/loops/tinycua_loop.md:51-54`, `src/tinycua/docs/design/loops/node_queue.md:44-47`, `src/tinycua/docs/design/loops/node_queue.md:85-101`.
  - [x] VERIFIED: 6 route-matrix + 3 impossible-route tests pass; loop already retries/fails-closed on illegal transitions.

- [x] Implement generic node retry/correction without forced content <!-- id: 15 -->
  - [x] Validate required node output/tool-call contracts.
  - [x] Retry same node with assistant-role continuation.
  - [x] If monitor/correction exists, keep it transient and assistant-role only.
  - [x] Do not insert prompt-specific plans, task names, route skips, or final answers.
  - [x] References: Spec `./spec.md:179`, `./spec.md:187`, `./spec.md:218-219`, `./spec.md:227`; source `src/tinycua/docs/design/loops/tinycua_loop.md:36-38`, `src/tinycua/docs/design/loops/tinycua_loop.md:67-84`, `src/tinycua/docs/design/loops/node.md:216-220`.
  - [x] VERIFIED: 6 failure-recovery tests pass; removed the forbidden `_recover_task_analyzer_validation_failure` vertical-slice fabrication.

- [x] Align tool scopes with source-of-truth docs <!-- id: 16 -->
  - [x] InformationDigester: retrieval/digest only.
  - [x] QueryAnalyst: read-only task inspection only.
  - [x] Worker: decision/routing tools only.
  - [x] TaskCreate: TaskInit/TaskCreate only.
  - [x] TaskAnalyzer: structural tools by mode; TaskInit/TaskCreate only for recreation.
  - [x] TaskExecutor: active task execution/result update plus allowed action tools.
  - [x] ResultReviewer: review decision and active task result/context update.
  - [x] ResponseNode: terminal response tools and allowed direct tools when context insufficient.
  - [x] References: Spec `./spec.md:213-214`, `./spec.md:228`, `./spec.md:274`; source `src/tinycua/docs/design/tools/task.md:5-18`, `src/tinycua/docs/design/loops/information_digester.md:52-58`, `src/tinycua/docs/design/loops/task_executor.md:31-43`, `src/tinycua/docs/design/loops/response.md:31-58`.
  - [x] VERIFIED: 21 tool-scope tests pass; scopes already match design docs.

- [x] Fix context propagation and internal roles <!-- id: 17 -->
  - [x] Keep external user strings as user-role only at trust boundary.
  - [x] Convert internal strings/handoffs/retries to assistant/internal records.
  - [x] Propagate prior+input upward and output forward according to segmented context model.
  - [x] Dedupe by origin record id before storage and LLM-bound messages.
  - [x] References: Spec `./spec.md:215-216`, `./spec.md:228-229`, `./spec.md:266`, `./spec.md:275`; source `src/tinycua/docs/design/loops/node.md:66-73`, `src/tinycua/docs/design/loops/node.md:83-86`, `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/loops/propagation.md:79-109`, `src/tinycua/docs/design/loops/propagation.md:116-135`.
  - [x] VERIFIED: 6 context-propagation tests pass; propagation layer already correct.

- [x] Refactor TinyCUA source files over 1000 LOC <!-- id: 18 -->
  - [x] Identify TinyCUA Python files over 1000 lines.
  - [x] Split only oversized files; do not add abstractions for files already below the gate.
  - [x] For `tinycua_loop.py`, split by real responsibilities: orchestration, route validation, retry/correction, trace collection, SDK/tool adapter.
  - [x] Delete dead code and broad lint suppressions instead of moving them.
  - [x] References: Spec `./spec.md:63-68`, `./spec.md:220-221`, `./spec.md:269`; source `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node_queue.md:25-47`, `src/tinycua/docs/design/loops/propagation.md:30-70`.
  - [x] STATUS: `tinycua_loop.py` 3730 -> 903 + 4 cohesive mixins (orchestration 997, validation_retry 825, prompt_protocol 591, trace_state 508) + `_loop_constants.py` (15). User-approved 1500-LOC hard gate (spec Zero-Tolerance item 8 exception) keeps `node.py` (1020) and `smoke_run.py` (1027) as cohesive single files with no dead/unused code (ruff F rules clean). Source-size guard enforces 1500.

- [x] Preserve/restore one-shot script trace output <!-- id: 19 -->
  - [x] Keep `src/tinycua/scripts/run_agent.py` runnable with one prompt.
  - [x] Print trace, final response, task tree, workspace files, and artifacts.
  - [x] Ensure `--stream` exposes node/tool lifecycle events enough to audit order.
  - [x] References: Spec `./spec.md:224`, `./spec.md:270`; source `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/tinycua_loop.md:62-65`, `src/tinycua/docs/design/loops/node_queue.md:85-101`.
  - [x] VERIFIED: 3 traceability tests pass; script already emits all required sections.

## Testing Phase

- [ ] Run invariant tests — expect GREEN <!-- id: 20 -->
  - [ ] `cd src/tinycua && uv run pytest tests/integration/test_runtime_invariant_route_matrix.py -q`
  - [ ] `cd src/tinycua && uv run pytest tests/integration/test_runtime_invariant_failure_recovery.py -q`
  - [ ] `cd src/tinycua && uv run pytest tests/integration/test_run_agent_traceability.py -q`
  - [ ] `cd src/tinycua && uv run pytest tests/unit/test_runtime_invariant_task_decomposition.py tests/unit/test_runtime_invariant_tool_scopes.py tests/unit/test_runtime_invariant_context_propagation.py tests/unit/test_runtime_invariant_source_guards.py -q`

- [ ] Run existing TinyCUA tests <!-- id: 21 -->
  - [ ] `cd src/tinycua && uv run pytest tests/unit -q`
  - [ ] `cd src/tinycua && uv run pytest tests/integration -q`

- [ ] Run lint/format checks <!-- id: 22 -->
  - [ ] `cd src/tinycua && uv run ruff check tinycua tests scripts/run_agent.py`
  - [ ] Do not add broad `ruff noqa`; simplify instead.
  - [ ] References: Spec `./spec.md:20-21`, `./spec.md:220-221`, `./spec.md:268-269`.

## Verification Phase

- [ ] Verify protected source-of-truth docs are untouched <!-- id: 23 -->
  - [ ] `git diff -- src/tinycua/docs/design` returns empty.
  - [ ] References: Spec `./spec.md:16-18`, `./spec.md:49-57`, `./spec.md:264`.

- [ ] Verify protected SDK is untouched <!-- id: 24 -->
  - [ ] `git diff -- src/tinycua-sdk` returns empty.
  - [ ] References: Spec `./spec.md:18-19`, `./spec.md:44-47`, `./spec.md:217`.

- [ ] Verify no forced behavior remains with standalone script <!-- id: 25 -->
  - [ ] Run `cd src/tinycua && uv run python scripts/check_runtime_policy_guidance.py`.
  - [ ] Confirm any policy-guidance violation is reported by the script, not encoded as a pytest assertion.
  - [ ] References: Spec `./spec.md:29-42`, `./spec.md:242-255`, `./spec.md:261-262`.

- [ ] Manually run one-shot simple and worker prompts <!-- id: 26 -->
  - [ ] `cd src/tinycua && uv run python scripts/run_agent.py --prompt "hello" --stream`
  - [ ] `cd src/tinycua && uv run python scripts/run_agent.py --prompt "Create a multi-step implementation plan" --worker-effort medium --stream`
  - [ ] Confirm simple route is QueryAnalyst -> ResponseNode.
  - [ ] Confirm worker route reaches TaskExecutor -> ResultReviewer before aggregation/response.

## Documentation Phase

- [ ] Update runtime docs outside `src/tinycua/docs/design/**` only if implementation introduces new test helpers or script flags <!-- id: 27 -->
  - [ ] Do not update source-of-truth design docs.
  - [ ] References: Spec `./spec.md:16-18`, `./spec.md:49-57`.

## Review and Merge

- [ ] Final diff review before PR/update <!-- id: 28 -->
  - [ ] Confirm only intended TinyCUA runtime/tests/spec files changed.
  - [ ] Confirm `reviews/` files, if any, are not staged.
  - [ ] Confirm protected paths remain clean.

- [ ] Commit only after explicit user approval <!-- id: 29 -->
  - [ ] Ask before committing.
  - [ ] Use concise commit message matching repo style.

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-17*
