# Feature Specification: TinyCUA Runtime Invariants

**Status**: Draft
**Created**: 2026-06-17
**Last Updated**: 2026-06-17
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Preserve TinyCUA as a deterministic orchestration layer around flexible ReAct-style node agents, so runtime code guarantees correct node progression, scoped context transport, traceable prototype execution, and tool permission boundaries without forcing task shape, solution strategy, roadmap size, or prompt-specific behavior. This branch is the quality gate for deciding whether the prototype runtime is trustworthy.
- **Gaps**: Recent runtime iterations introduced prompt-class heuristics and rigid behavior, including app/web-ui special casing, forced minimal vertical-slice decomposition, task-count caps, downgraded analysis effort defaults, and guard rails that changed what the LLM should decide. These violate the intended architecture and repeatedly regress TinyCUA away from an agent system into a brittle prompt router.
- **Non-Goals**: This spec does not replace, rewrite, reinterpret, or edit the existing source-of-truth design documents under `src/tinycua/docs/design/**`. This spec does not authorize new prompt-specific heuristics, hidden behavior templates, task-count caps, dead code, or broad SDK rewrites.
- **Constraints**:
  - `src/tinycua/docs/design/**` is the ultimate source of truth for TinyCUA runtime behavior. If implementation behavior conflicts with those documents, the implementation is incorrect.
  - Source-of-truth design documents under `src/tinycua/docs/design/**` MUST NOT be modified as part of runtime fixes unless the user explicitly requests a design-document revision. No incidental wording, formatting, or cleanup changes are allowed.
  - `src/tinycua-sdk/**` MUST NOT be modified by TinyCUA runtime invariant work. TinyCUA must wrap or adapt SDK behavior at the TinyCUA layer when needed.
  - TinyCUA runtime MUST use TinyCUA-SDK capabilities as much as possible. Missing SDK capabilities should be wrapped minimally at the TinyCUA layer instead of reinvented.
  - Final product code MUST NOT include dead code, deliberately ignored dirty code, broad `ruff noqa` suppression to hide complexity, or cognitively complex huge functions kept only to satisfy tooling.
  - TinyCUA code files over 1000 lines are presumed overengineered and MUST be split, simplified, or deleted unless the user explicitly approves the exception. `TinyCUALoop` is a primary refactor target under this rule.

---

## Zero-Tolerance Ultimatum

These rules are mandatory acceptance gates. Any spec, design, implementation, test, PR body, review resolution, or runtime behavior that violates any item below MUST be rejected and MUST NOT be accepted as complete. Passing tests, passing Ruff, live-run success, benchmark convenience, provider instability, or prototype pressure does not override these rules.

1. **ZERO TOLERANCE TOWARD FORCING LLM BEHAVIOUR**
   - TinyCUA may enforce node contracts, legal routes, scoped context, tool permissions, and retries/corrections.
   - TinyCUA MUST NOT force what plan, decomposition, implementation strategy, answer style, or task shape the LLM chooses inside a valid node contract.
   - Source: `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node.md:88-105`.

2. **ZERO TOLERANCE WITH SITUATION-SPECIFIC PROMPT BEHAVIOUR**
   - No runtime or prompt layer may special-case behavior for prompt categories such as app, web UI, backend, frontend, API, notebook, benchmark, research, docs, or similar situation classes.
   - Node instructions may define role and tool scope only; they must not encode “if this kind of user prompt, force this plan shape.”
   - Source: `src/tinycua/docs/design/loops/task_analyzer.md:6-10`, `src/tinycua/docs/design/loops/task_analyzer.md:23-31`, `src/tinycua/docs/design/loops/node.md:25-27`.

3. **ZERO TOLERANCE WITH ANY ALTERATION USING HEURISTIC**
   - TinyCUA MUST NOT rewrite, collapse, truncate, replace, or reinterpret node output using prompt heuristics, string matching, hidden templates, fixed task titles, task-count caps, or content-class rules.
   - Any correction path must be generic and limited to helping the same node satisfy its required contract.
   - Source: `src/tinycua/docs/design/loops/task_analyzer.md:23-31`, `src/tinycua/docs/design/models/task.md:10-28`, `src/tinycua/docs/design/loops/tinycua_loop.md:67-84`.

4. **ZERO TOLERANCE WITH TINYCUA-SDK MODIFICATION**
   - Runtime-invariant work MUST NOT modify `src/tinycua-sdk/**`.
   - TinyCUA must use SDK-compatible execution and minimal TinyCUA-layer wrappers for missing SDK capabilities.
   - Source: `src/tinycua/docs/design/loops/tinycua_loop.md:8-15`, `src/tinycua/docs/design/loops/tinycua_loop.md:86-94`.

5. **ZERO TOLERANCE WITH `src/tinycua/docs/design` MODIFICATION**
   - Files under `src/tinycua/docs/design/**` MUST remain byte-for-byte untouched unless the user explicitly requests a design-document revision.
   - No “cleanup,” formatting, wording, typo, or reference update is allowed in that tree during implementation work.
   - Source: this user-mandated acceptance gate plus authoritative design ownership cited throughout this spec.

6. **ZERO TOLERANCE WITH `src/tinycua/docs/design` DRIFT**
   - Any implementation behavior that conflicts with `src/tinycua/docs/design/**` is incorrect, even if tests pass.
   - The fix is to change implementation/tests/specs outside the source-of-truth tree to conform to the design docs, not to reinterpret or bypass them.
   - Source: `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node_queue.md:25-47`, `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/tools/task.md:5-18`.

7. **ZERO TOLERANCE WITH POLICY MODIFICATION WITHOUT USER APPROVAL**
   - This Zero-Tolerance Ultimatum and the runtime invariants in this spec MUST NOT be weakened, deleted, reworded to reduce strictness, moved to a less visible location, or bypassed without explicit user approval.
   - Any PR or commit that modifies these policies without explicit user approval MUST be rejected.

8. **ZERO TOLERANCE WITH OVERENGINEERED 1000+ LINE CODE FILES IN FINAL PRODUCT**
   - Any TinyCUA source file over 1000 lines MUST be treated as architectural debt and refactored into smaller, cohesive modules before acceptance unless the user explicitly approves the exception.
   - `TinyCUALoop` and any other orchestration file exceeding 1000 lines MUST be decomposed so loop code remains transport/orchestration, not a dumping ground for node-specific behavior, prompt-specific guards, or hidden policy logic.
   - The refactor must delete dead code and simplify control flow; it must not move complexity into ignored helper files, broad lint suppressions, or unused compatibility branches.
   - Source: user-mandated quality invariant; supports source-of-truth separation of loop, node, queue, propagation, route, and task responsibilities in `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node_queue.md:25-47`, and `src/tinycua/docs/design/loops/propagation.md:30-70`.

---

## Source-of-Truth Design Documents

The following design-document tree is authoritative and must not be replaced by ad-hoc implementation behavior:

- `src/tinycua/docs/design/README.md`
- `src/tinycua/docs/design/loops/overview.md`
- `src/tinycua/docs/design/loops/tinycua_loop.md`
- `src/tinycua/docs/design/loops/base_loop.md`
- `src/tinycua/docs/design/loops/node.md`
- `src/tinycua/docs/design/loops/node_queue.md`
- `src/tinycua/docs/design/loops/route_map.md`
- `src/tinycua/docs/design/loops/propagation.md`
- `src/tinycua/docs/design/loops/analysis_effort.md`
- `src/tinycua/docs/design/loops/task_create.md`
- `src/tinycua/docs/design/loops/task_analyzer.md`
- `src/tinycua/docs/design/loops/task_assessor.md`
- `src/tinycua/docs/design/loops/task_executor.md`
- `src/tinycua/docs/design/loops/result_reviewer.md`
- `src/tinycua/docs/design/loops/result_aggregation.md`
- `src/tinycua/docs/design/loops/response.md`
- `src/tinycua/docs/design/loops/query_analyst.md`
- `src/tinycua/docs/design/loops/information_digester.md`
- `src/tinycua/docs/design/loops/worker.md`
- `src/tinycua/docs/design/loops/worker_concept.md`
- `src/tinycua/docs/design/loops/expected_scenarios.md`
- `src/tinycua/docs/design/models/*.md`
- `src/tinycua/docs/design/tools/*.md`
- `src/tinycua/docs/design/config/*.md`
- `src/tinycua/docs/design/constants/*.md`
- `src/tinycua/docs/design/utility/*.md`

Any future work that conflicts with these documents is a bug. The fix is to change the implementation to match the design docs, not to silently redefine the design in code.

### Exact Source-of-Truth Line References

Every invariant in this spec traces to exact source-of-truth design lines below. If a later implementation conflicts with these cited lines, the implementation is wrong.

| Invariant | Source-of-truth lines |
|-----------|-----------------------|
| TinyCUALoop is SDK-compatible execution/orchestration loop | `src/tinycua/docs/design/loops/tinycua_loop.md:8-15` |
| Loop execution flow: build node messages, resolve scoped tools, call LLM, validate/retry, then `node.on_complete` | `src/tinycua/docs/design/loops/tinycua_loop.md:21-40` |
| `node.on_complete()` owns queue transitions; loop does not advance separately | `src/tinycua/docs/design/loops/tinycua_loop.md:51-54`, `src/tinycua/docs/design/loops/node_queue.md:44-47` |
| Monitor/correction is transient and assistant-role, not a durable behavior-forcing node | `src/tinycua/docs/design/loops/tinycua_loop.md:67-84` |
| Error handling covers invalid output, routes, node input, tool scope, terminal response, and SDK stream issues without SDK API changes | `src/tinycua/docs/design/loops/tinycua_loop.md:86-94` |
| Nodes own config, instruction, continuation, retry policy, message strategy, tool scope, stream policy, and propagation rule | `src/tinycua/docs/design/loops/node.md:25-27` |
| Nodes build one final system-role message from their own prompt fragments | `src/tinycua/docs/design/loops/node.md:29-64` |
| Internal handoffs are assistant-role, not recreated user messages | `src/tinycua/docs/design/loops/node.md:66-73`, `src/tinycua/docs/design/loops/node.md:83-86` |
| Node contract includes `build_messages`, `validate_output`, `build_retry_continuation`, `record_output`, `propagate`, and `on_complete` | `src/tinycua/docs/design/loops/node.md:88-105` |
| Retry prompts are assistant-role continuations | `src/tinycua/docs/design/loops/node.md:216-220` |
| Queue order controls execution order but does not imply automatic context sharing | `src/tinycua/docs/design/loops/node_queue.md:6-10` |
| Queue input/advance/propagation behavior follows assigned node input and segmented output forwarding | `src/tinycua/docs/design/loops/node_queue.md:25-43` |
| Queue bootstrap enforces QueryAnalyst entry and terminal ResponseNode safety | `src/tinycua/docs/design/loops/node_queue.md:85-101` |
| Route dispatch uses validated labels in the owning route map only | `src/tinycua/docs/design/loops/route_map.md:6-32` |
| Mandatory passthrough provides deterministic continuation routing to intended active node/session | `src/tinycua/docs/design/loops/route_map.md:53-93` |
| Propagation controls what crosses node/session boundaries | `src/tinycua/docs/design/loops/propagation.md:6-19` |
| Segmented context model controls prior/input/output propagation | `src/tinycua/docs/design/loops/propagation.md:30-70` |
| Chat history is durable audit; session context is reusable LLM context | `src/tinycua/docs/design/loops/propagation.md:79-92` |
| Transient routing node output enters next node input segment | `src/tinycua/docs/design/loops/propagation.md:116-135` |
| AnalysisEffort controls upfront assessment/analysis pass count before execution | `src/tinycua/docs/design/loops/analysis_effort.md:6-11` |
| WorkerEffort pass mapping: none/low/medium/high | `src/tinycua/docs/design/loops/analysis_effort.md:12-29` |
| AnalysisEffort prepends TaskAssessor/TaskAnalyzer until threshold and then advances to TaskExecutor | `src/tinycua/docs/design/loops/analysis_effort.md:30-53` |
| TaskAnalyzer performs mode-specific task analysis, decomposition, and refinement | `src/tinycua/docs/design/loops/task_analyzer.md:6-10` |
| TaskAnalyzer does not create root tasks, execute tasks, or assess task quality/completeness | `src/tinycua/docs/design/loops/task_analyzer.md:12-17` |
| TaskAnalyzer mutates task tree through structural task tools, not opaque loop-applied instructions | `src/tinycua/docs/design/loops/task_analyzer.md:23-31` |
| TaskAnalyzer mode tool scope forbids TaskInit/TaskCreate except explicitly allowed recreation | `src/tinycua/docs/design/loops/task_analyzer.md:33-42` |
| TaskAnalyzer queue behavior routes to AnalysisEffort or TaskExecutor depending on context | `src/tinycua/docs/design/loops/task_analyzer.md:53-61` |
| TaskAssessor evaluates task tree and selects unfinished tasks for decomposition/reanalysis | `src/tinycua/docs/design/loops/task_assessor.md:6-10` |
| TaskAssessor does not decompose, execute, or create tasks | `src/tinycua/docs/design/loops/task_assessor.md:12-18` |
| TaskAssessor outputs selected unfinished tasks or no-analyzer-needed signal | `src/tinycua/docs/design/loops/task_assessor.md:24-28` |
| TaskExecutor performs ReAct-style execution of current active task and is the only node that may execute task actions/results | `src/tinycua/docs/design/loops/task_executor.md:6-10` |
| TaskExecutor must not select active task, edit active task, mutate task tree, review results, or synthesize final responses | `src/tinycua/docs/design/loops/task_executor.md:12-19` |
| TaskExecutor receives current active task and high-level read-only task tree list | `src/tinycua/docs/design/loops/task_executor.md:20-24` |
| TaskExecutor tool scope is active-task execution/result update, retrieval, and HITL passthrough | `src/tinycua/docs/design/loops/task_executor.md:31-43` |
| TaskExecutor completes to ResultReviewer | `src/tinycua/docs/design/loops/task_executor.md:44-52` |
| ResultReviewer evaluates TaskExecutor output and is the quality gate | `src/tinycua/docs/design/loops/result_reviewer.md:6-10` |
| ResultReviewer does not execute, decompose/analyze, or synthesize final responses | `src/tinycua/docs/design/loops/result_reviewer.md:12-18` |
| ResultReviewer decisions and queue behavior | `src/tinycua/docs/design/loops/result_reviewer.md:39-91` |
| ResponseNode is terminal/suspendable final synthesis node, not generic PrimaryNode | `src/tinycua/docs/design/loops/response.md:6-10` |
| ResponseNode does not own task traversal, execute tasks, or review results | `src/tinycua/docs/design/loops/response.md:12-18` |
| ResponseNode may use allowed tools directly when context is insufficient | `src/tinycua/docs/design/loops/response.md:31-58` |
| Task model supports children list without a task-count limit | `src/tinycua/docs/design/models/task.md:10-28` |
| Active task handoff protocol and ownership rules | `src/tinycua/docs/design/models/task.md:54-91` |
| Task tree completion/update rules after reviewer accept | `src/tinycua/docs/design/models/task.md:92-108` |
| Task tools are exposed according to node tool scope | `src/tinycua/docs/design/tools/task.md:5-18` |
| TaskAnalyzer path-specific task-tool semantics | `src/tinycua/docs/design/tools/task.md:19-28` |
| QueryAnalyst is the top-level entry point and first node for every run | `src/tinycua/docs/design/loops/query_analyst.md:6-11` |
| QueryAnalyst routes only worker/uncertain/passthrough and retries invalid/missing labels | `src/tinycua/docs/design/loops/query_analyst.md:57-82`, `src/tinycua/docs/design/loops/query_analyst.md:132-135` |
| QueryAnalyst queue behavior spawns or forwards to Worker | `src/tinycua/docs/design/loops/query_analyst.md:83-101` |
| InformationDigester does not execute/create/mutate tasks or synthesize final responses | `src/tinycua/docs/design/loops/information_digester.md:13-18` |
| InformationDigester has retrieval/digest scope only | `src/tinycua/docs/design/loops/information_digester.md:52-58` |
| InformationDigester uses fresh session, selected input only, and own-output propagation | `src/tinycua/docs/design/loops/information_digester.md:27-43`, `src/tinycua/docs/design/loops/information_digester.md:93-100` |
| Worker owns task planning/execution orchestration decisions, not task mutation/execution/review/response | `src/tinycua/docs/design/loops/worker.md:6-18` |
| Worker route queue shapes include task creation/recreation/reanalysis/proceed execution paths ending in ResultReviewer/ResponseNode | `src/tinycua/docs/design/loops/worker.md:75-89` |
| Worker must ensure terminal path after clearing queue | `src/tinycua/docs/design/loops/worker.md:115-119` |
| TaskCreate creates root then advances to TaskAnalyzer | `src/tinycua/docs/design/loops/task_create.md:6-10`, `src/tinycua/docs/design/loops/task_create.md:36-44` |

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user gives TinyCUA an arbitrary task request. TinyCUA routes the request through the correct node sequence, gives each node only its scoped context and tools, retries malformed node output until the node satisfies its contract, and lets the node decide task decomposition, implementation strategy, and final wording within its role and tool scope. The runtime never hardcodes behavior for prompt categories such as app building, web UI work, research, notebooks, or any other content class.

This branch serves as the prototype trustworthiness quality gate. A prototype is not trustworthy unless it can be exercised through a simple one-shot script, produces traceable runs, proves legal end-to-end routes under LLM failure, preserves scoped context, and enforces node tool boundaries.

### Acceptance Scenarios

1. **Given** a task-analysis node emits malformed output or omits the required task-state tool call, **When** TinyCUALoop validates the node result, **Then** TinyCUALoop retries or invokes a generic monitor/correction path so the same node can self-correct instead of routing directly to an invalid downstream node such as ResponseNode.
2. **Given** a request that may require many tasks, **When** TaskAnalyzer decomposes the work, **Then** TinyCUA preserves the analyzer-owned task list without runtime-imposed prompt-class collapsing or hard task-count limits.
3. **Given** an app/web-ui request, **When** TaskAnalyzer decides the roadmap, **Then** TinyCUA does not force a minimal vertical slice, backend/frontend/API split, single-task plan, or any other prompt-specific plan shape.
4. **Given** any internal node communicates to another node, **When** context is propagated, **Then** internal communication is assistant-role in persisted session context; ephemeral user-role retry prompts may be used only inside an LLM attempt and must be transformed back to assistant/internal records for propagation.
5. **Given** a node is not TaskExecutor or ResponseNode, **When** tools are resolved for that node, **Then** it receives only read-only tools plus its scoped structural node tools, never arbitrary workspace/action tools.
6. **Given** any user query enters `TinyCUA Agent.run`, **When** the run completes, **Then** it always ends at ResponseNode or an explicit terminal node and never skips from task/planning nodes directly to ResponseNode. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:19-40`, `src/tinycua/docs/design/loops/node_queue.md:85-101`, `src/tinycua/docs/design/loops/response.md:60-90`.
7. **Given** a simple passthrough request, **When** QueryAnalyst classifies it as passthrough, **Then** the legal end-to-end route is `User_Query -> Agent.run -> QueryAnalyst -> ResponseNode`. Source: `src/tinycua/docs/design/loops/query_analyst.md:57-65`, `src/tinycua/docs/design/loops/query_analyst.md:83-93`, `src/tinycua/docs/design/loops/response.md:60-90`.
8. **Given** a worker request, **When** QueryAnalyst routes to worker, **Then** the legal upfront worker path is `User_Query -> Agent.run -> QueryAnalyst -> InformationDigester -> Worker -> TaskCreate/TaskAnalyzer -> AnalysisEffort -> repeated TaskAssessor/TaskAnalyzer per effort -> TaskExecutor -> ResultReviewer -> executor/reviewer/replan/open-question branches until tasks complete -> ResultAggregation -> ResponseNode`. Source: `src/tinycua/docs/design/loops/query_analyst.md:83-101`, `src/tinycua/docs/design/loops/information_digester.md:84-100`, `src/tinycua/docs/design/loops/worker.md:75-89`, `src/tinycua/docs/design/loops/analysis_effort.md:30-53`, `src/tinycua/docs/design/loops/result_reviewer.md:56-91`, `src/tinycua/docs/design/loops/node.md:173-214`.
9. **Given** LLM output is weak, malformed, or missing required tool calls, **When** a node attempts to complete, **Then** the internal node retry/correction loop lets the node self-recover by calling appropriate scoped tools or emitting the required contract rather than allowing an illegal route. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:36-38`, `src/tinycua/docs/design/loops/tinycua_loop.md:67-84`, `src/tinycua/docs/design/loops/node.md:216-220`.
10. **Given** tools are resolved for internal nodes, **When** the node is not TaskExecutor or ResponseNode, **Then** arbitrary write/execute tools such as shell, Python, file write, or file edit are not exposed; read-only or scoped structural tools are the maximum. Source: `src/tinycua/docs/design/loops/task_executor.md:6-10`, `src/tinycua/docs/design/loops/response.md:31-58`, `src/tinycua/docs/design/loops/information_digester.md:13-18`, `src/tinycua/docs/design/loops/information_digester.md:52-58`, `src/tinycua/docs/design/tools/task.md:5-18`.
11. **Given** context is propagated between nodes, **When** the next node builds its input, **Then** context is isolated and deduped: at most the selected handoff/input payload and permitted propagated segments appear, not wholesale duplicated prior node messages. Source: `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/loops/propagation.md:94-109`, `src/tinycua/docs/design/loops/query_analyst.md:24-43`, `src/tinycua/docs/design/loops/worker.md:123-144`.

### Edge Cases

- If strict validation cannot reliably identify a correct tool call, the runtime may use a generic monitor/correction agent or retry path to help the same node satisfy its required contract. The monitor must not impose task content, plan shape, or prompt-specific behavior.
- If the LLM proposes a very large roadmap, TinyCUA must not truncate the task list. Scheduling, batching, or execution ordering may be managed separately without deleting or rewriting analyzer-owned tasks.
- If a node attempts an impossible route, such as TaskAnalyzer directly to ResponseNode, the loop must reject that route and retry or correct the node contract.
- If any path skips `TaskExecutor -> ResultReviewer` and advances directly to ResponseNode before task completion and aggregation, the run is invalid and must fail validation.
- If source code appears to need `ruff noqa`, long complex functions, or unused dead branches, the code must be simplified instead of suppressed.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: TinyCUALoop MUST act as orchestration and transport only: route nodes, enforce legal node transitions, provide scoped inputs, execute tools through TinyCUA-SDK mechanisms, validate node contracts, and retry/correct malformed node emissions. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:8-15`, `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/tinycua_loop.md:86-94`.
- **FR-002**: TinyCUALoop MUST NOT force behavior for specific prompt categories, including but not limited to app-building, web UI, notebook, benchmark, research, frontend, backend, API, or documentation prompts. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/task_analyzer.md:6-10`.
- **FR-003**: TinyCUALoop MUST NOT force behavior in general beyond node contract validity, route correctness, scoped context propagation, and tool permission boundaries. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/route_map.md:6-32`, `src/tinycua/docs/design/loops/propagation.md:6-19`, `src/tinycua/docs/design/tools/task.md:5-18`.
- **FR-004**: TinyCUA MUST NOT impose a hard limit on the number of tasks TaskAnalyzer may create. Any execution batching must preserve all analyzer-created tasks. Source: `src/tinycua/docs/design/models/task.md:10-28`, `src/tinycua/docs/design/loops/task_analyzer.md:23-31`.
- **FR-005**: TaskAnalyzer MUST own task decomposition and roadmap structure according to its scoped prompt, tools, and context. Runtime code must not rewrite analyzer output into hardcoded task names or prompt-specific plan templates. Source: `src/tinycua/docs/design/loops/task_analyzer.md:6-10`, `src/tinycua/docs/design/loops/task_analyzer.md:23-31`, `src/tinycua/docs/design/tools/task.md:19-28`.
- **FR-006**: TaskAnalyzer MUST NOT be allowed to advance directly to ResponseNode. Any illegal route transition must be rejected by the orchestration layer. Source: `src/tinycua/docs/design/loops/task_analyzer.md:53-61`, `src/tinycua/docs/design/loops/tinycua_loop.md:86-94`, `src/tinycua/docs/design/loops/node_queue.md:44-47`.
- **FR-007**: Each node MUST build its own system prompt, messages, handoff payloads, and output processing from scoped input. TinyCUALoop must not assemble node-specific meaning outside the node. Source: `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node.md:29-64`, `src/tinycua/docs/design/loops/node.md:88-105`.
- **FR-008**: Each node SHOULD act like a normal scoped ReAct agent similar to SDK BaseLoop behavior, with specialized instruction and tool scope rather than rigid runtime behavior injection. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:8-15`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/task_executor.md:6-10`.
- **FR-009**: TaskExecutor MUST receive only the active task context, read-only task-tree overview, execution tools, and the specialized active-task result/update capability required by design docs. It must not receive broad tree mutation powers. Source: `src/tinycua/docs/design/loops/task_executor.md:20-24`, `src/tinycua/docs/design/loops/task_executor.md:31-43`, `src/tinycua/docs/design/models/task.md:82-91`.
- **FR-010**: ResponseNode and TaskExecutor are the only nodes allowed to receive arbitrary workspace/action tools such as file writing, shell execution, Python execution, or external action tools. Other nodes must be read-only except for their scoped structural node tools. Source: `src/tinycua/docs/design/loops/task_executor.md:6-10`, `src/tinycua/docs/design/loops/task_executor.md:31-43`, `src/tinycua/docs/design/loops/response.md:31-58`, `src/tinycua/docs/design/tools/task.md:5-18`.
- **FR-011**: Internal node communication MUST follow the context propagation rules in `src/tinycua/docs/design/loops/propagation.md` and related design docs. Persisted internal communication must be assistant/internal, not user chat history. Source: `src/tinycua/docs/design/loops/node.md:66-73`, `src/tinycua/docs/design/loops/node.md:83-86`, `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/loops/propagation.md:79-92`.
- **FR-012**: Ephemeral user-role retry prompts are allowed only as provider-facing attempt messages when needed for LLM consistency. They MUST NOT be persisted as external user messages and MUST be transformed to assistant/internal records for propagation. Source: `src/tinycua/docs/design/loops/node.md:66-73`, `src/tinycua/docs/design/loops/node.md:216-220`, `src/tinycua/docs/design/loops/tinycua_loop.md:67-84`.
- **FR-013**: TinyCUA MUST use TinyCUA-SDK capabilities for LLM loops, tool execution, and BaseLoop-like behavior wherever possible. Workarounds for missing SDK features must be minimal wrappers at the TinyCUA layer. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:8-15`, `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/tinycua_loop.md:86-94`.
- **FR-014**: Runtime validation MUST supervise node contract completion, not task content. It may require required tool calls or legal route outputs, but must not dictate what task plan or implementation strategy the LLM chooses. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:36-38`, `src/tinycua/docs/design/loops/tinycua_loop.md:86-94`, `src/tinycua/docs/design/loops/node.md:88-105`.
- **FR-015**: If validation is hard with deterministic code alone, TinyCUA MAY use a generic monitor/correction agent to identify mistakes and instruct the same node to emit the proper required tool call. The monitor/correction path must not introduce prompt-specific forced behavior. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:67-84`, `src/tinycua/docs/design/loops/node.md:216-220`.
- **FR-016**: Final product code MUST NOT contain dead code, deliberately ignored branches, unused compatibility shims, broad `ruff noqa` suppressions, or cognitively complex huge functions hidden from linting. Source: user-mandated quality invariant for this spec; no source-of-truth design doc permits dead/dirty code or lint suppression as architecture.
- **FR-017**: TinyCUA source files over 1000 lines MUST be refactored, split, simplified, or deleted before acceptance unless the user explicitly approves an exception. Source: user-mandated quality invariant plus separation of loop/node/queue/propagation responsibilities in `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node_queue.md:25-47`, `src/tinycua/docs/design/loops/propagation.md:30-70`.
- **FR-018**: Any implementation that violates `src/tinycua/docs/design/**` is incorrect even if tests pass. Source: entire source-of-truth tree, with runtime responsibilities anchored in `src/tinycua/docs/design/loops/tinycua_loop.md:8-15`, node ownership in `src/tinycua/docs/design/loops/node.md:25-27`, propagation in `src/tinycua/docs/design/loops/propagation.md:6-19`, and tool scopes in `src/tinycua/docs/design/tools/task.md:5-18`.
- **FR-019**: Tests MUST NOT encode prompt-specific forced behavior as expected behavior. Tests should assert invariants, permissions, routes, and context propagation. Source: `src/tinycua/docs/design/loops/route_map.md:6-32`, `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/tools/task.md:5-18`, `src/tinycua/docs/design/loops/task_analyzer.md:6-10`.
- **FR-020**: TinyCUA MUST provide a simple traceable one-shot script or equivalent entry point, like `src/tinycua/scripts/run_agent.py`, that runs a TinyCUA agent from a prompt and emits enough trace data to inspect node order, tool calls, final response, task tree, workspace files, and artifacts. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:62-65`, `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node_queue.md:85-101`.
- **FR-021**: End-to-end tests MUST prove every `Agent.run` path terminates at ResponseNode or an explicit terminal node regardless of LLM weakness, malformed output, missing route labels, or missing tool calls. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:19-40`, `src/tinycua/docs/design/loops/node_queue.md:85-101`, `src/tinycua/docs/design/loops/response.md:60-90`, `src/tinycua/docs/design/loops/query_analyst.md:132-135`.
- **FR-022**: End-to-end tests MUST prove legal passthrough and worker routes exactly follow source-of-truth queue shapes and MUST reject impossible routes, including TaskAnalysis/TaskAnalyzer directly to ResponseNode and TaskExecutor directly to ResponseNode before ResultReviewer. Source: `src/tinycua/docs/design/loops/query_analyst.md:83-101`, `src/tinycua/docs/design/loops/worker.md:75-89`, `src/tinycua/docs/design/loops/task_analyzer.md:53-61`, `src/tinycua/docs/design/loops/task_executor.md:44-52`, `src/tinycua/docs/design/loops/result_reviewer.md:56-91`.
- **FR-023**: Internal nodes MUST self-recover through node retry/correction using scoped tools and required contract emissions, not by route skipping or runtime-forced content. Source: `src/tinycua/docs/design/loops/tinycua_loop.md:36-38`, `src/tinycua/docs/design/loops/tinycua_loop.md:67-84`, `src/tinycua/docs/design/loops/node.md:216-220`.
- **FR-024**: Tool scope tests MUST prove internal node tools never exceed their design scope. InformationDigester must not receive task tools, TaskAnalyzer must not receive execution tools, and arbitrary write/execute tools are restricted to TaskExecutor and ResponseNode. Source: `src/tinycua/docs/design/loops/information_digester.md:13-18`, `src/tinycua/docs/design/loops/information_digester.md:52-58`, `src/tinycua/docs/design/loops/task_executor.md:6-10`, `src/tinycua/docs/design/loops/response.md:31-58`, `src/tinycua/docs/design/tools/task.md:5-18`.
- **FR-025**: Context propagation tests MUST prove node messages are isolated, deduped, and limited to selected handoff/input payloads plus documented propagation segments. Source: `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/loops/propagation.md:94-109`, `src/tinycua/docs/design/loops/query_analyst.md:24-43`, `src/tinycua/docs/design/loops/worker.md:123-144`, `src/tinycua/docs/design/loops/information_digester.md:27-43`.

### Key Entities

- **TinyCUALoop**: Orchestration wrapper responsible for deterministic route progression, scoped context delivery, node contract validation, retry/correction, and SDK-backed tool execution.
- **Node**: Scoped ReAct-style agent with its own instruction, prompt/message building, tool scope, output processing, and handoff payload ownership.
- **TaskAnalyzer**: Node that owns task decomposition and roadmap creation without runtime-imposed task count or prompt-class templates.
- **TaskExecutor**: Node that executes the current active task with arbitrary action tools and active-task result reporting, while seeing a read-only task-tree overview.
- **ResponseNode**: Node that generates final user-facing responses and may use arbitrary tools if needed by design scope.
- **Source-of-Truth Design Docs**: `src/tinycua/docs/design/**`; authoritative runtime architecture that implementation must follow and must not silently modify.

---

## Prohibited Patterns

The following patterns are explicitly forbidden:

- Hardcoded prompt-category behavior, e.g. `if "app" in prompt`, `if web_ui`, `if notebook`, or equivalent hidden heuristics.
- Forced task titles such as “Build a minimal runnable vertical-slice app...” injected by runtime code.
- Automatic collapsing of analyzer-created tasks into one task or a fixed template.
- Hard limits on task count such as `maxItems: 3`, slicing subtasks, or dropping tasks for convenience.
- Runtime validation that judges the desired implementation style instead of node contract validity.
- Giving non-executor/non-response nodes arbitrary write/shell/action tools.
- Persisting internal retry/correction messages as external user chat turns.
- Modifying `src/tinycua/docs/design/**` to make implementation shortcuts appear valid.
- Adding dead code, broad lint ignores, or complex ignored functions just to pass tests or Ruff.
- Leaving TinyCUA source files over 1000 lines in the final product without explicit user-approved exception.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **No prompt-specific forcing**: Searching runtime code finds no app/web-ui/notebook/research/etc. prompt-category heuristics that alter task shape, route, or implementation strategy.
- [ ] **No task-count cap**: Task decomposition preserves arbitrary analyzer-created task counts without hard truncation.
- [ ] **Legal routing enforced**: Illegal transitions such as TaskAnalyzer to ResponseNode are rejected and retried/corrected.
- [ ] **Docs remain immutable**: No files under `src/tinycua/docs/design/**` are modified by this work unless the user explicitly requested design-doc changes.
- [ ] **Tool scopes match design**: Only TaskExecutor and ResponseNode have arbitrary action tools; other nodes are read-only plus scoped structural tools.
- [ ] **Context propagation matches design**: Internal handoffs and retries persist as assistant/internal context, with no accidental external user history pollution.
- [ ] **SDK used where possible**: TinyCUA uses SDK loop/tool-execution capabilities, with only minimal wrappers for missing SDK behavior.
- [ ] **Clean final code**: No dead code, no broad `ruff noqa`, no intentionally ignored dirty branches, and no large cognitively complex functions introduced.
- [ ] **No 1000+ LOC source dumping grounds**: Every TinyCUA source file over 1000 lines is split, simplified, deleted, or explicitly approved by the user as an exception.
- [ ] **Traceable one-shot script**: A simple script or equivalent entry point runs TinyCUA from one prompt and emits traceable node order, tool calls, final response, task tree, workspace files, and artifact locations.
- [ ] **E2E route proof under LLM failure**: Tests prove every `Agent.run` path ends at ResponseNode/terminal node and follows legal source-of-truth routes regardless of weak/malformed/missing LLM output.
- [ ] **No impossible route acceptance**: Tests reject TaskAnalyzer/TaskAnalysis to ResponseNode, TaskExecutor to ResponseNode before ResultReviewer, and any other source-of-truth-impossible skip.
- [ ] **Node self-recovery proof**: Tests prove internal nodes can recover by retrying/correcting and calling appropriate scoped tools or required contract tools.
- [ ] **Tool scope proof**: Tests prove InformationDigester has no task tools, non-executor/non-response nodes have no arbitrary write/execute tools, and TaskExecutor/ResponseNode are the only arbitrary action-tool nodes.
- [ ] **Context isolation proof**: Tests prove node inputs are not duplicated wholesale and are limited to handoff payloads plus documented propagation segments.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Add tests that fail if `task_decompose` truncates, collapses, or rewrites arbitrary subtasks.
- Add tests that fail if runtime code contains prompt-specific forced task titles or app/web-ui decomposition heuristics.
- Add route-invariant tests for illegal node transitions, including TaskAnalyzer to ResponseNode.
- Add tool-scope tests proving only TaskExecutor and ResponseNode receive arbitrary action tools.
- Add context-propagation tests proving internal retry/correction records are persisted as assistant/internal, not external user turns.
- Add a source-size audit test/check that fails for TinyCUA source files over 1000 lines unless explicitly user-approved.
- Add E2E route-matrix tests for passthrough and worker paths, including malformed/missing LLM outputs at each node.
- Add self-recovery tests proving nodes retry and then call required scoped tools rather than skipping routes.
- Add negative tests proving impossible routes never pass validation or queue advancement.

### Integration Tests

- Run a complex app-like prompt and assert TinyCUA preserves a multi-task analyzer roadmap when the analyzer emits one.
- Run a non-app complex prompt and assert the same orchestration rules apply without prompt-category special cases.
- Run worker effort with default settings and assert AnalysisEffort can schedule assessor/analyzer passes according to configuration.
- Run the one-shot script against simple passthrough and worker prompts and assert trace output contains legal node order, terminal response, task tree, tool calls, and artifact paths.
- Run failure-injection integration tests where every internal node fails once and then recovers through retries without illegal route skips.

### Manual Tests _(if applicable)_

- Inspect live `run_agent.py --stream` output for a complex prompt and verify the loop only enforces node contracts/routes while the LLM owns roadmap shape.
- Confirm `git diff -- src/tinycua/docs/design` is empty unless the user explicitly requested design-doc changes.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Runtime invariant spec | Done | This document records the non-negotiable design constraints. |
| Source-of-truth design docs | Protected | Must not be modified by runtime fixes without explicit user request. |
| Forced-behavior cleanup | TODO | Remove prompt-specific heuristics and task-count caps in implementation work. |
| 1000+ LOC source cleanup | TODO | Refactor `TinyCUALoop` and any other oversized TinyCUA source files. |
| Regression tests | TODO | Add invariant tests before implementation changes. |

---

## Open Questions _(optional)_

None. These invariants are user-mandated and are not optional design preferences.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
