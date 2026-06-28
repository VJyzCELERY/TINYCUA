# Design Document: TinyCUA Runtime Invariants

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-17

---

## Overview

This design records the non-negotiable TinyCUA runtime invariant: TinyCUA is an orchestration and transport layer around scoped ReAct-style node agents, not a behavior-forcing prompt router. The affected subproject is `src/tinycua`. The key decision is to make `src/tinycua/docs/design/**` the immutable source of truth for runtime architecture and to prohibit implementation shortcuts that force prompt-specific behavior, cap task counts, overexpose tools, or hide dirty/dead code.

This design also makes oversized TinyCUA code files an explicit refactor target: any TinyCUA source file over 1000 lines is presumed to be an overengineered dumping ground and must be split, simplified, or deleted unless the user explicitly approves an exception.

This branch is also the prototype trustworthiness quality gate. The implementation is not complete until a traceable one-shot script, end-to-end route proofs, self-recovery proofs, tool-scope proofs, and context-isolation proofs pass against the source-of-truth design routes.

---

## Architecture

### Component Overview

TinyCUA runtime responsibilities stay narrow:

```
User input
  -> Query/Worker route selection
  -> NodeQueue legal transition enforcement
  -> Node-owned prompt + scoped input + scoped tools
  -> SDK-backed ReAct/tool loop
  -> Node-owned output/handoff/result
  -> Loop validation of node contract only
  -> retry/correction on malformed node contract
```

The loop enforces transport, route, retry, and permission invariants. Nodes own behavior inside their scoped role. The runtime must never replace node judgment with prompt-category rules such as “app request means one vertical slice.”

### Exact Source-of-Truth Line References

| Design Rule | Source-of-truth lines |
|-------------|-----------------------|
| TinyCUALoop is SDK-compatible execution loop and root session/NodeQueue owner | `src/tinycua/docs/design/loops/tinycua_loop.md:8-15` |
| Loop execution flow builds node messages, resolves scoped tools, calls LLM, validates/retries, records, and delegates completion to node | `src/tinycua/docs/design/loops/tinycua_loop.md:21-40` |
| `node.on_complete()` owns queue transitions; TinyCUALoop does not advance separately | `src/tinycua/docs/design/loops/tinycua_loop.md:51-54`, `src/tinycua/docs/design/loops/node_queue.md:44-47` |
| Monitor/correction hook is transient, assistant-role, and not durable queue behavior | `src/tinycua/docs/design/loops/tinycua_loop.md:67-84` |
| Loop handles invalid output, route labels, NodeInput, tool scope, terminal response, and SDK stream failures without SDK API changes | `src/tinycua/docs/design/loops/tinycua_loop.md:86-94` |
| Nodes own config, instruction, continuation, retry, message strategy, tool scope, stream policy, and propagation rule | `src/tinycua/docs/design/loops/node.md:25-27` |
| Nodes build one final system-role message from prompt fragments | `src/tinycua/docs/design/loops/node.md:29-64` |
| Internal handoffs are assistant-role; external user strings are the only user-role inputs | `src/tinycua/docs/design/loops/node.md:66-73`, `src/tinycua/docs/design/loops/node.md:83-86` |
| Node contract includes message building, validation, retry continuation, output recording, propagation, and completion | `src/tinycua/docs/design/loops/node.md:88-105` |
| Retry prompts are assistant-role continuations | `src/tinycua/docs/design/loops/node.md:216-220` |
| NodeQueue controls execution order but not automatic context sharing | `src/tinycua/docs/design/loops/node_queue.md:6-10` |
| NodeQueue input, advance, spawn, suspend, clear, and terminal behavior | `src/tinycua/docs/design/loops/node_queue.md:25-43`, `src/tinycua/docs/design/loops/node_queue.md:85-101` |
| RouteMap dispatch uses validated labels in owning route table | `src/tinycua/docs/design/loops/route_map.md:6-32` |
| Mandatory passthrough is deterministic active-node/session continuation routing | `src/tinycua/docs/design/loops/route_map.md:53-93` |
| Propagation controls node/session boundary crossing | `src/tinycua/docs/design/loops/propagation.md:6-19` |
| Segmented context propagation model | `src/tinycua/docs/design/loops/propagation.md:30-70` |
| Chat history vs reusable session context | `src/tinycua/docs/design/loops/propagation.md:79-92` |
| Transient routing node output becomes next node input segment | `src/tinycua/docs/design/loops/propagation.md:116-135` |
| AnalysisEffort controls upfront assessor/analyzer pass count | `src/tinycua/docs/design/loops/analysis_effort.md:6-11`, `src/tinycua/docs/design/loops/analysis_effort.md:12-29`, `src/tinycua/docs/design/loops/analysis_effort.md:30-53` |
| TaskAnalyzer role, non-responsibilities, outputs, tool modes, and queue behavior | `src/tinycua/docs/design/loops/task_analyzer.md:6-17`, `src/tinycua/docs/design/loops/task_analyzer.md:23-42`, `src/tinycua/docs/design/loops/task_analyzer.md:53-61` |
| TaskAssessor role, non-responsibilities, selected-task output, and queue behavior | `src/tinycua/docs/design/loops/task_assessor.md:6-18`, `src/tinycua/docs/design/loops/task_assessor.md:24-34`, `src/tinycua/docs/design/loops/task_assessor.md:50-58` |
| TaskExecutor role, non-responsibilities, inputs, tools, queue, and ownership | `src/tinycua/docs/design/loops/task_executor.md:6-24`, `src/tinycua/docs/design/loops/task_executor.md:31-43`, `src/tinycua/docs/design/loops/task_executor.md:44-52`, `src/tinycua/docs/design/loops/task_executor.md:63-74` |
| ResultReviewer role, non-responsibilities, decisions, and queue behavior | `src/tinycua/docs/design/loops/result_reviewer.md:6-18`, `src/tinycua/docs/design/loops/result_reviewer.md:39-91` |
| ResponseNode role, non-responsibilities, tools, context sufficiency, and terminal behavior | `src/tinycua/docs/design/loops/response.md:6-18`, `src/tinycua/docs/design/loops/response.md:31-58`, `src/tinycua/docs/design/loops/response.md:60-90` |
| Task model supports child task trees and active-task handoff/ownership | `src/tinycua/docs/design/models/task.md:10-28`, `src/tinycua/docs/design/models/task.md:54-91`, `src/tinycua/docs/design/models/task.md:92-108` |
| Task tools are exposed by node scope and path-specific analyzer semantics | `src/tinycua/docs/design/tools/task.md:5-18`, `src/tinycua/docs/design/tools/task.md:19-28` |
| 1000+ LOC source cleanup | User-mandated quality gate; supports responsibility separation across `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node_queue.md:25-47`, `src/tinycua/docs/design/loops/propagation.md:30-70` |
| QueryAnalyst entry and route labels | `src/tinycua/docs/design/loops/query_analyst.md:6-11`, `src/tinycua/docs/design/loops/query_analyst.md:57-65`, `src/tinycua/docs/design/loops/query_analyst.md:83-101`, `src/tinycua/docs/design/loops/query_analyst.md:132-135` |
| InformationDigester role, fresh session, selected input, read-only digest scope, and propagation | `src/tinycua/docs/design/loops/information_digester.md:13-18`, `src/tinycua/docs/design/loops/information_digester.md:27-43`, `src/tinycua/docs/design/loops/information_digester.md:52-58`, `src/tinycua/docs/design/loops/information_digester.md:84-100` |
| Worker decision hub, route shapes, terminal preservation, and transient propagation | `src/tinycua/docs/design/loops/worker.md:6-18`, `src/tinycua/docs/design/loops/worker.md:75-89`, `src/tinycua/docs/design/loops/worker.md:115-119`, `src/tinycua/docs/design/loops/worker.md:123-144` |
| TaskCreate root creation and transition to TaskAnalyzer | `src/tinycua/docs/design/loops/task_create.md:6-10`, `src/tinycua/docs/design/loops/task_create.md:36-44` |

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `src/tinycua/docs/design/**` | Protected | Ultimate runtime design source of truth. Must not be modified by this work. |
| `TinyCUALoop` | Constrained | May enforce route legality, contract validity, retries, context transport, and tool permissions only. Must not force task content or decomposition shape. |
| `Node` implementations | Constrained | Own prompts, handoffs, payload processing, and scoped behavior. Should act like normal scoped agents using specialized instructions/tools. |
| `TaskAnalyzer` | Constrained | Owns decomposition and roadmap. Runtime must not cap, collapse, template, or rewrite its task list. |
| `TaskExecutor` | Constrained | Executes current active task with arbitrary action tools and active-task result capability. Must not receive broad task mutation powers. |
| `ResponseNode` | Constrained | Generates final user-facing response and may use arbitrary tools if its scope requires. |
| Tool scopes | Constrained | Only TaskExecutor and ResponseNode get arbitrary action tools. Other nodes remain read-only plus scoped structural tools. |
| TinyCUA source files over 1000 LOC | Refactor Required | Split, simplify, or delete unless explicitly approved by the user. `TinyCUALoop` is a primary target. |
| One-shot script | Required | Simple prompt entry point with traceable node order, tool calls, final response, task tree, workspace files, and artifacts. |
| E2E route matrix | Required | Proves passthrough and worker paths terminate legally under LLM failure; impossible routes fail. |
| Self-recovery tests | Required | Prove nodes retry/correct and call required scoped tools rather than route skipping. |
| Context isolation tests | Required | Prove no wholesale duplicated context; only handoff/input plus documented propagated segments. |
| Tests | Modified | Tests assert architecture invariants, not prompt-specific forced behavior. |

### Required End-to-End Route Proofs

The implementation must include proof that every `User_Query -> TinyCUA Agent.run` terminates at ResponseNode or an explicit terminal node. The only accepted top-level shapes are:

```text
Simple / passthrough:
  User_Query
  -> Agent.run
  -> QueryAnalyst
  -> ResponseNode
```

Source: `src/tinycua/docs/design/loops/query_analyst.md:57-65`, `src/tinycua/docs/design/loops/query_analyst.md:83-93`, `src/tinycua/docs/design/loops/response.md:60-90`.

```text
Worker path:
  User_Query
  -> Agent.run
  -> QueryAnalyst
  -> InformationDigester
  -> Worker
  -> TaskCreate or TaskAnalyzer
  -> AnalysisEffort
  -> repeated [TaskAssessor, TaskAnalyzer] according to WorkerEffort
  -> TaskExecutor
  -> ResultReviewer
  -> repeat legal ResultReviewer branches until all tasks complete
  -> ResultAggregation
  -> ResponseNode
```

Source: `src/tinycua/docs/design/loops/query_analyst.md:83-101`, `src/tinycua/docs/design/loops/information_digester.md:84-100`, `src/tinycua/docs/design/loops/worker.md:75-89`, `src/tinycua/docs/design/loops/task_create.md:36-44`, `src/tinycua/docs/design/loops/analysis_effort.md:30-53`, `src/tinycua/docs/design/loops/task_executor.md:44-52`, `src/tinycua/docs/design/loops/result_reviewer.md:56-91`, `src/tinycua/docs/design/loops/node.md:173-214`.

Strictly impossible and unacceptable examples:

- `TaskAnalyzer -> ResponseNode`
- `TaskAnalysis -> ResponseNode`
- `TaskCreate -> ResponseNode`
- `TaskExecutor -> ResponseNode` before ResultReviewer
- Any task path that reaches ResponseNode before all required task/review/aggregation design steps complete

Source: `src/tinycua/docs/design/loops/task_analyzer.md:53-61`, `src/tinycua/docs/design/loops/task_executor.md:44-52`, `src/tinycua/docs/design/loops/result_reviewer.md:56-91`, `src/tinycua/docs/design/loops/node.md:173-214`.

---

## Data Model

### New Entities _(if applicable)_

No new runtime data entities are required by this design document.

### Schema Changes _(if applicable)_

No schema changes are required. If later implementation needs metadata to track retries or monitor corrections, it must be generic and must not encode prompt categories or forced task shapes.

---

## API / Interface Contracts

### Runtime Contract

TinyCUA runtime implementation must obey these interface-level contracts:

- `TinyCUALoop` may validate that a node emitted the required route/tool contract.
- `TinyCUALoop` may reject illegal transitions, such as TaskAnalyzer advancing directly to ResponseNode.
- `TinyCUALoop` may retry the same node, or use a generic monitor/correction path, when node output is malformed.
- `TinyCUALoop` must not decide the content of task decomposition, implementation style, roadmap size, or final answer strategy.
- Task decomposition APIs must preserve all analyzer-provided subtasks. They must not silently truncate, collapse, or replace subtasks.
- Tool resolution must follow node scope from the design docs.
- TinyCUA source files over 1000 lines must fail acceptance unless split, simplified, deleted, or explicitly user-approved.
- A simple one-shot script or equivalent entry point must run a TinyCUA agent from a prompt and emit traceable node order, tool calls, final response, task tree, workspace files, and artifact paths.
- E2E tests must inject weak/malformed/missing LLM outputs and prove legal recovery to the same node or legal downstream route.
- Tool-scope tests must prove InformationDigester has no task tools and only TaskExecutor/ResponseNode receive arbitrary write/execute tools.
- Context tests must prove node inputs are isolated and deduped according to propagation rules.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Node emits invalid route | Retry/correct same node | Do not skip to unrelated node. |
| Node omits required contract tool | Retry/correct same node | Correction is generic, not prompt-specific. |
| Analyzer emits many subtasks | Preserve all tasks | Scheduler may batch later, but must not drop tasks. |
| Implementation conflicts with `src/tinycua/docs/design/**` | Implementation is invalid | Fix code/tests, not the source-of-truth docs. |
| Non-executor node receives action tools | Tool-scope failure | Only TaskExecutor and ResponseNode may get arbitrary action tools. |
| TinyCUA source file exceeds 1000 lines | Acceptance failure | Refactor into smaller cohesive modules; do not hide complexity behind lint ignores. |
| One-shot script lacks traceability | Acceptance failure | Add node-order, tool-call, final response, task tree, workspace, and artifact reporting. |
| LLM failure causes route skip | Acceptance failure | Retry/correct same node or fail; never advance through impossible route. |
| Task path skips reviewer | Acceptance failure | Enforce `TaskExecutor -> ResultReviewer` before any aggregation/response path. |
| Internal node has out-of-scope tools | Acceptance failure | Fix tool policy; do not rely on prompt obedience. |
| Node receives duplicated wholesale context | Acceptance failure | Fix propagation/dedupe; pass selected handoff/input only. |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Remove prompt-specific behavior from runtime prompts, tools, recovery paths, and tests.
- [ ] Remove hard task-count caps and task-list truncation from task decomposition.
- [ ] Restore generic analysis effort behavior and defaults according to design docs.
- [ ] Add route-invariant tests proving illegal node transitions cannot advance.
- [ ] Add tool-scope tests proving only TaskExecutor and ResponseNode get arbitrary action tools.
- [ ] Add context-propagation tests proving internal communication persists as assistant/internal, not external user turns.
- [ ] Add source-of-truth protection checks ensuring `src/tinycua/docs/design/**` is unchanged by runtime implementation work.
- [ ] Add source-size audit and refactor `TinyCUALoop` plus any other TinyCUA source file over 1000 lines.
- [ ] Implement or preserve a traceable one-shot script equivalent to `src/tinycua/scripts/run_agent.py`.
- [ ] Add E2E route-matrix tests for simple passthrough and worker paths under LLM failure injection.
- [ ] Add impossible-route tests for TaskAnalyzer/TaskAnalysis to ResponseNode and TaskExecutor to ResponseNode before ResultReviewer.
- [ ] Add self-recovery tests proving nodes can call scoped tools after retry/correction.
- [ ] Add context isolation and dedupe tests for node input propagation.

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Add a generic monitor/correction node or helper only if deterministic retries cannot robustly enforce node contracts.
- [ ] Add scheduler batching for very large task trees only if needed; batching must preserve every analyzer-created task.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Treat `src/tinycua/docs/design/**` as immutable source-of-truth for runtime behavior.
   - **Reason**: The design docs already define loop, node, propagation, route, task, and tool responsibilities. Implementation must not silently replace them.
   - **Alternatives Considered**: Update design docs to match shortcuts — rejected because it hides regressions and violates user instruction.

2. **Decision**: Runtime validation supervises node contracts, not node content decisions.
   - **Reason**: TinyCUA’s value is deterministic progression through flexible agents. Forcing plan shape destroys the agent-system advantage.
   - **Alternatives Considered**: Hardcode behavior for common prompts — rejected as strictly forbidden.

3. **Decision**: No task-count cap in decomposition.
   - **Reason**: TaskAnalyzer owns roadmap size. Dropping tasks is data loss and changes model intent.
   - **Alternatives Considered**: Keep a small cap for prototype stability — rejected. If throughput matters, schedule/batch without deletion.

4. **Decision**: Tool scopes remain strict and node-specific.
   - **Reason**: Nodes should act like normal scoped agents without overexposure. Only TaskExecutor and ResponseNode need arbitrary action tools.
   - **Alternatives Considered**: Give all nodes action tools and rely on prompts — rejected as unsafe and contrary to design docs.

5. **Decision**: Dead/dirty/ignored code is not acceptable final product code.
   - **Reason**: Large ignored complexity and dead branches make regressions easier and hide architectural violations.
   - **Alternatives Considered**: Use `ruff noqa` or compatibility branches to pass tests quickly — rejected.

6. **Decision**: TinyCUA source files over 1000 lines are acceptance failures unless explicitly user-approved.
   - **Reason**: Oversized orchestration files become overengineered dumping grounds for prompt-specific guards, hidden policy, node-specific behavior, and dead code.
   - **Alternatives Considered**: Keep a large loop class and add more guards — rejected because it violates responsibility separation in the source-of-truth docs.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Removing forced heuristics exposes LLM instability | Medium | Medium | Use generic retries or monitor correction focused only on node contract validity. |
| Unlimited task counts create large queues | Medium | Medium | Preserve all tasks; add scheduler batching only if needed. |
| Tests accidentally encode forced behavior again | High | High | Add negative tests for prompt-specific forcing and task truncation. |
| Source-of-truth docs are edited during cleanup | Medium | High | Check `git diff -- src/tinycua/docs/design` before review/commit. |
| Tool scopes drift | Medium | High | Keep explicit tool-scope tests per node. |
| Code complexity grows during fixes | Medium | Medium | Prefer deletion; split functions instead of adding broad guards or lint ignores. |
| Oversized files hide policy drift | High | High | Enforce 1000 LOC source audit and split oversized files by documented responsibilities. |
| Route tests pass only happy path | High | High | Use failure-injection E2E tests for every internal node. |
| Trace script exists but hides route bugs | Medium | High | Assert trace contains node order, tool calls, final response, task tree, workspace files, and artifacts. |
| Tool scope expands accidentally | Medium | High | Test each node policy, with explicit negative assertions for InformationDigester/task tools and non-executor write tools. |
| Context isolation regresses through convenience forwarding | High | High | Assert exact selected handoff/input segments and dedupe behavior. |

---

## Open Questions _(optional)_

None. These are user-mandated runtime invariants.

---

## References

- Spec: `./spec.md`
- Source of truth: `../../docs/design/**`
- Loop design: `../../docs/design/loops/tinycua_loop.md` (`src/tinycua/docs/design/loops/tinycua_loop.md:8-15`, `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/tinycua_loop.md:51-54`, `src/tinycua/docs/design/loops/tinycua_loop.md:67-94`)
- QueryAnalyst design: `../../docs/design/loops/query_analyst.md` (`src/tinycua/docs/design/loops/query_analyst.md:6-11`, `src/tinycua/docs/design/loops/query_analyst.md:57-65`, `src/tinycua/docs/design/loops/query_analyst.md:83-101`, `src/tinycua/docs/design/loops/query_analyst.md:132-135`)
- InformationDigester design: `../../docs/design/loops/information_digester.md` (`src/tinycua/docs/design/loops/information_digester.md:13-18`, `src/tinycua/docs/design/loops/information_digester.md:27-43`, `src/tinycua/docs/design/loops/information_digester.md:52-58`, `src/tinycua/docs/design/loops/information_digester.md:84-100`)
- Worker design: `../../docs/design/loops/worker.md` (`src/tinycua/docs/design/loops/worker.md:6-18`, `src/tinycua/docs/design/loops/worker.md:75-89`, `src/tinycua/docs/design/loops/worker.md:115-119`, `src/tinycua/docs/design/loops/worker.md:123-144`)
- TaskCreate design: `../../docs/design/loops/task_create.md` (`src/tinycua/docs/design/loops/task_create.md:6-10`, `src/tinycua/docs/design/loops/task_create.md:36-44`)
- Node design: `../../docs/design/loops/node.md` (`src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node.md:29-73`, `src/tinycua/docs/design/loops/node.md:83-105`, `src/tinycua/docs/design/loops/node.md:216-220`)
- Queue design: `../../docs/design/loops/node_queue.md` (`src/tinycua/docs/design/loops/node_queue.md:6-10`, `src/tinycua/docs/design/loops/node_queue.md:25-47`, `src/tinycua/docs/design/loops/node_queue.md:85-101`)
- Route map: `../../docs/design/loops/route_map.md` (`src/tinycua/docs/design/loops/route_map.md:6-32`, `src/tinycua/docs/design/loops/route_map.md:53-93`)
- Propagation design: `../../docs/design/loops/propagation.md` (`src/tinycua/docs/design/loops/propagation.md:6-19`, `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/loops/propagation.md:79-92`, `src/tinycua/docs/design/loops/propagation.md:116-135`)
- Analysis effort design: `../../docs/design/loops/analysis_effort.md` (`src/tinycua/docs/design/loops/analysis_effort.md:6-53`)
- Task analyzer design: `../../docs/design/loops/task_analyzer.md` (`src/tinycua/docs/design/loops/task_analyzer.md:6-17`, `src/tinycua/docs/design/loops/task_analyzer.md:23-42`, `src/tinycua/docs/design/loops/task_analyzer.md:53-61`)
- Task assessor design: `../../docs/design/loops/task_assessor.md` (`src/tinycua/docs/design/loops/task_assessor.md:6-18`, `src/tinycua/docs/design/loops/task_assessor.md:24-34`, `src/tinycua/docs/design/loops/task_assessor.md:50-58`)
- Task executor design: `../../docs/design/loops/task_executor.md` (`src/tinycua/docs/design/loops/task_executor.md:6-24`, `src/tinycua/docs/design/loops/task_executor.md:31-52`, `src/tinycua/docs/design/loops/task_executor.md:63-74`)
- Result reviewer design: `../../docs/design/loops/result_reviewer.md` (`src/tinycua/docs/design/loops/result_reviewer.md:6-18`, `src/tinycua/docs/design/loops/result_reviewer.md:39-91`)
- Response design: `../../docs/design/loops/response.md` (`src/tinycua/docs/design/loops/response.md:6-18`, `src/tinycua/docs/design/loops/response.md:31-58`, `src/tinycua/docs/design/loops/response.md:60-90`)
- Task model design: `../../docs/design/models/task.md` (`src/tinycua/docs/design/models/task.md:10-28`, `src/tinycua/docs/design/models/task.md:54-108`)
- Tool design: `../../docs/design/tools/task.md` (`src/tinycua/docs/design/tools/task.md:5-28`)
