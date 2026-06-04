# [Roadmap]: TinyCUA Architecture Implementation

> **Draft status:** Review material for the design-simplification PR.
> Convert this draft into a GitHub roadmap issue before merge and delete this draft directory unless the user decides to keep it.

## Overview

Implement TinyCUA's target architecture as documented in `src/tinycua/docs/design/`:

```text
create_tinycua_agent(...)
  → SDK Agent(loop=TinyCUALoop(...))
  → agent.run(query="...", messages=[...], stream=True)
```

The implementation must build around the current `tinycua-sdk` contract. It must not
modify SDK APIs.

## In Scope

- `create_tinycua_agent(...)` factory
- `TinyCUALoop` extending SDK `BaseLoop`
- `NodeQueue`
- concrete TinyCUA nodes
- `NodeInput` / `NodePayload`
- per-node session/message context
- `PropagationRule`
- per-node tool scoping
- retry/validation
- stream handling across all nodes
- `TinyCUAResponseNode` suspension to request `TinyCUAInformationDigesterNode`

## Out of Scope

- SDK modifications
- TUI
- CLI
- HITL UX
- interrupt UX
- datastore persistence implementation
- resume UX

## Milestones

### 1. Agent Factory Contract

- **Design docs covered**:
  - `docs/design/README.md` — partial
  - `docs/design/loops/overview.md` — full
  - `docs/design/loops/base_loop.md` — partial
  - `docs/design/loops/tinycua_loop.md` — partial
  - `docs/design/config/session_config.md` — partial
  - `docs/design/constants/instructions.md` — partial
- **Contract implemented**:
  - `create_tinycua_agent(session=None, agent_config=None, session_config=None, ...) -> Agent`
  - returns SDK `Agent(loop=TinyCUALoop(...))`
  - creates a new session when `session is None`
  - applies `SessionConfig` to generated/provided session according to documented policy
  - does not modify SDK APIs
- **Contract deferred**: node execution, concrete nodes, propagation, streaming metadata.
- **Expected PR scope**: one PR.
- **Exit criteria**: factory returns a SDK Agent with TinyCUALoop attached.

### 2. SessionConfig and Base Node Config Models

- **Design docs covered**:
  - `docs/design/config/session_config.md` — full
  - `docs/design/config/node_config.md` — partial
  - `docs/design/models/session.md` — partial
- **Contract implemented**:
  - `SessionConfig`
  - base node config dataclass
  - append-only instruction/continuation fields
  - `SystemPrompt` / `SystemPromptBuilder` rendering model
  - `NodeToolPolicy`, `NodeStreamPolicy`, `NodeRetryPolicy` shapes
- **Contract deferred**: concrete per-node behavior.
- **Expected PR scope**: one PR.
- **Exit criteria**: config model tests pass and docs contract is represented in code.

### 2a. CompactionStrategy Contract

> Numbered as `2a` because compaction is selected by `SessionConfig` from milestone 2,
> but remains a separate PR-sized contract before transport and node execution work.

- **Design docs covered**:
  - `docs/design/utility/compaction.md` — full
  - `docs/design/config/session_config.md` — partial
  - `docs/design/models/session.md` — partial
- **Contract implemented**:
  - `CompactionStrategy.compact(messages: list[dict]) -> dict`
  - one assistant-role summary message output
  - strategy-owned configuration, including optional internal Agent usage
  - `SimpleCompaction` default/simple strategy
  - SimpleCompaction inherits parent Agent config when available and falls back to defaults otherwise
  - SimpleCompaction uses a tool-less compaction Agent and returns `{"role": "assistant", "content": response}`
  - system-role messages excluded by default from compaction targets
- **Contract deferred**: advanced/custom compaction strategies beyond `SimpleCompaction`.
- **Expected PR scope**: one PR.
- **Exit criteria**: sessions can compact selected context through a strategy without altering chat history or node continuation handling.

### 3. NodeInput and NodePayload Transport

- **Design docs covered**:
  - `docs/design/models/state_object.md` — partial
  - `docs/design/models/execution_log.md` — partial
  - `docs/design/models/agent_state.md` — partial
  - `docs/design/loops/node.md` — partial
- **Contract implemented**:
  - `NodeInputLike = str | NodeInput | NodePayload | list[dict]`
  - `NodePayload.to_message()` / `to_messages()`
  - `NodeInput(messages=[...], payloads=[...])`
  - no untrusted string parsing for internal input
- **Contract deferred**: concrete payload types for every node.
- **Expected PR scope**: one PR.
- **Exit criteria**: transport converts to assistant-role messages and safely handles strings/list messages.

### 4. Node Base, DecisionNode, and ProcessNode

- **Design docs covered**:
  - `docs/design/loops/node.md` — partial
  - `docs/design/config/node_config.md` — partial
- **Contract implemented**:
  - base `Node`
  - `DecisionNode`
  - `ProcessNode`
  - node session attachment skeleton
  - message/instruction builder interfaces
- **Contract deferred**: concrete TinyCUA nodes.
- **Expected PR scope**: one PR.
- **Exit criteria**: minimal node classes can be instantiated and accept `NodeInputLike`.

### 5. NodeQueue Basic Execution

- **Design docs covered**:
  - `docs/design/loops/node_queue.md` — partial
  - `docs/design/loops/tinycua_loop.md` — partial
- **Contract implemented**:
  - sequential queue
  - `queue[0]` active node
  - `advance()`
  - `spawn_after_current()`
  - terminal response handling skeleton
- **Contract deferred**: suspension/prepend.
- **Expected PR scope**: one PR.
- **Exit criteria**: queue can run a minimal process-node sequence.

### 6. NodeQueue Suspension and Prepend

- **Design docs covered**:
  - `docs/design/loops/node_queue.md` — full
  - `docs/design/loops/propagation.md` — partial
- **Contract implemented**:
  - `suspend_current_and_prepend(nodes)`
  - parent node relationship for prepended child
  - resume by queue position, no dedicated suspended state
- **Contract deferred**: ResponseNode-specific information digestion path.
- **Expected PR scope**: one PR.
- **Exit criteria**: prepended node runs before suspended parent and propagates selected output.

### 7. TinyCUALoop SDK Integration

- **Design docs covered**:
  - `docs/design/loops/base_loop.md` — full
  - `docs/design/loops/tinycua_loop.md` — partial
- **Contract implemented**:
  - extends SDK `BaseLoop`
  - consumes SDK `messages`, `tools`, `override_instructions`, `stream`
  - calls `agent._call_llm()` with node-scoped messages/tools
  - preserves `stream=False` final string behavior
- **Contract deferred**: all concrete node paths.
- **Expected PR scope**: one PR.
- **Exit criteria**: `Agent(loop=TinyCUALoop(...)).run(...)` runs a minimal queue without SDK changes.

### 8. RouteMap and Top-Level QueryAnalyst

- **Design docs covered**:
  - `docs/design/loops/route_map.md` — full
  - `docs/design/loops/node.md` — partial
  - `docs/design/models/classification.md` — partial
- **Contract implemented**:
  - DecisionNode-owned RouteMap
  - `TinyCUAQueryAnalystNode`
  - top-level labels: `passthrough`, `worker`
  - route to response path or worker path
- **Contract deferred**: Worker decision node.
- **Expected PR scope**: one PR.
- **Exit criteria**: top-level query classification routes queue deterministically.

### 9. TinyCUAWorkerNode Deterministic Routing

- **Design docs covered**:
  - `docs/design/loops/worker_concept.md` — partial
  - `docs/design/tools/task.md` — partial
  - `docs/design/models/worker_result.md` — partial
- **Contract implemented**:
  - no Worker QueryAnalyst
  - task-missing deterministic path to TaskAnalyzer with TaskInit/TaskCreate
  - worker-spawned-node detection
- **Contract deferred**: optional LLM worker decision.
- **Expected PR scope**: one PR.
- **Exit criteria**: Worker can initialize task analysis without LLM decision when task is missing.

### 10. TinyCUAWorkerNode Optional LLM Decision

- **Design docs covered**:
  - `docs/design/loops/worker_concept.md` — full
  - `docs/design/models/classification.md` — full
- **Contract implemented**:
  - worker labels: `task_recreation`, `task_reanalysis`, `proceed_execution`
  - dynamic `passthrough` label only when a worker-spawned node exists
  - route handlers for each worker route
- **Contract deferred**: full downstream process-node implementations.
- **Expected PR scope**: one PR.
- **Exit criteria**: Worker LLM decision mutates the queue correctly.

### 11. InformationDigesterNode

- **Design docs covered**:
  - `docs/design/loops/node.md` — partial
  - `docs/design/tools/digester.md` — full
  - `docs/design/models/information.md` — partial
  - `docs/design/models/digested_information.md` — full
- **Contract implemented**:
  - `TinyCUAInformationDigesterNode`
  - enhanced context retrieval tool integration
  - digest output model
  - selected digest propagation
- **Contract deferred**: ResponseNode suspension path.
- **Expected PR scope**: one PR.
- **Exit criteria**: digester produces structured digest from NodeInput/session context.

### 12. TaskAnalyzer and TaskAssessor Nodes

- **Design docs covered**:
  - `docs/design/loops/node.md` — partial
  - `docs/design/tools/task.md` — partial
  - `docs/design/tools/todo.md` — partial
  - `docs/design/models/task.md` — partial
  - `docs/design/models/todo.md` — partial
- **Contract implemented**:
  - `TinyCUATaskAnalyzerNode`
  - `TinyCUATaskAssessorNode`
  - task creation/reanalysis tool scope
- **Contract deferred**: executor/reviewer loop.
- **Expected PR scope**: one PR.
- **Exit criteria**: task tree can be created/analyzed/assessed by scoped nodes.

### 13. TaskExecutor and ResultReviewer Nodes

- **Design docs covered**:
  - `docs/design/loops/node.md` — partial
  - `docs/design/tools/task.md` — full
  - `docs/design/tools/todo.md` — partial
  - `docs/design/models/reviewer_decision.md` — full
  - `docs/design/models/todo.md` — partial
- **Contract implemented**:
  - `TinyCUATaskExecutorNode`
  - `TinyCUAResultReviewerNode`
  - accept/retry/replan/open-question flow
- **Contract deferred**: final response synthesis.
- **Expected PR scope**: one PR.
- **Exit criteria**: executor/reviewer path can complete or route retry/replan.

### 14. TinyCUAResponseNode

- **Design docs covered**:
  - `docs/design/loops/node.md` — full
  - `docs/design/loops/tinycua_loop.md` — partial
- **Contract implemented**:
  - final response synthesis
  - terminal output normalization to `str`
  - selected outer Agent tools according to NodeToolPolicy
- **Contract deferred**: suspension to InformationDigester.
- **Expected PR scope**: one PR.
- **Exit criteria**: passthrough path can produce final response.

### 15. ResponseNode Information-Digestion Suspension Path

- **Design docs covered**:
  - `docs/design/loops/node_queue.md` — full
  - `docs/design/loops/node.md` — full
  - `docs/design/tools/digester.md` — full
- **Contract implemented**:
  - ResponseNode request for information digest
  - pass ResponseNode session context through NodeInput
  - prepend InformationDigester with parent=ResponseNode
  - digest propagates back and ResponseNode resumes
- **Contract deferred**: advanced nested suspension.
- **Expected PR scope**: one PR.
- **Exit criteria**: ResponseNode can gather information mid-response and resume.

### 16. Propagation and Dedupe

- **Design docs covered**:
  - `docs/design/loops/propagation.md` — full
  - `docs/design/models/session.md` — full
  - `docs/design/models/chat_record.md` — full
  - `docs/design/models/state_store.md` — partial
- **Contract implemented**:
  - PropagationRule engine
  - chat_history vs session_context separation
  - source metadata
  - dedupe/origin ids
  - legacy propagation profiles
- **Contract deferred**: datastore persistence.
- **Expected PR scope**: one PR.
- **Exit criteria**: node outputs propagate without duplicate session_context entries.

### 17. Tool Scoping

- **Design docs covered**:
  - `docs/design/config/node_config.md` — full
  - `docs/design/constants/tools.md` — full
- **Contract implemented**:
  - NodeToolPolicy resolution
  - selected outer Agent tools
  - node-specific tool restrictions
- **Contract deferred**: none for architecture scope.
- **Expected PR scope**: one PR.
- **Exit criteria**: nodes only see allowed tools.

### 18. Retry, Validation, and Monitor Hook

- **Design docs covered**:
  - `docs/design/loops/node.md` — full
  - `docs/design/loops/tinycua_loop.md` — partial
  - `docs/design/models/agent_state.md` — partial
- **Contract implemented**:
  - NodeRetryPolicy
  - assistant-role retry continuations
  - validation per node
  - optional transient NodeMonitor/AgentMonitor hook
- **Contract deferred**: HITL UX.
- **Expected PR scope**: one PR.
- **Exit criteria**: invalid node output retries and exhaustion behavior are covered.
- **Exit criteria**:
  - invalid node output retries and retry exhaustion behavior are covered
  - validation pass/fail flow is covered for required tool calls and output schema
  - optional monitor hook lifecycle is covered without introducing HITL UX scope

### 19. Streaming Across Nodes

- **Design docs covered**:
  - `docs/design/loops/base_loop.md` — full
  - `docs/design/loops/tinycua_loop.md` — full
  - `docs/design/config/node_config.md` — full
- **Contract implemented**:
  - `stream=True` across every node
  - LLM/tool events visible to caller
  - node metadata where possible
  - lifecycle events configurable
- **Contract deferred**: none for architecture scope.
- **Expected PR scope**: one PR.
- **Exit criteria**: streamed runs surface node LLM/tool events and non-streamed runs return final string.

### 20. End-to-End Architecture Integration Verification Gate

> **Integration Verification Gate** — requires milestones 1-19 complete. This is a
> verification gate, not a standalone feature PR by default.

- **Design docs covered**:
  - all core `docs/design` architecture docs — full coverage audit
- **Contract implemented**:
  - passthrough path
  - worker path
  - response path
  - suspension path
  - propagation
  - tool scoping
  - streaming
- **Contract deferred**: out-of-scope UX/persistence/SDK work.
- **Expected PR scope**: verification gate after prior milestone PRs are complete.
- **Exit criteria**: `create_tinycua_agent(...).run(...)` works across documented architecture paths.

## Dependencies

- Current `tinycua-sdk` Agent/BaseLoop contract.
- Finalized `docs/design/` from the design-simplification PR.

## Additional Context

Each implementation PR should link back to this roadmap issue and cite the milestone it
implements. If a milestone proves too large, split it into smaller PR-sized milestones in
the main roadmap rather than creating nested roadmap layers.
