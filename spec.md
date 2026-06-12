# Feature Specification: Tool Scoping

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 4.2 — Tool Scoping
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

---

## Problem Statement _(mandatory)_

- **Goals**: Implement per-node tool scoping so that every TinyCUA node sees only the tools it is authorized to use, with shared `enhanced_context_retrieval` cache behavior working correctly for its consumers (InformationDigesterNode, TaskExecutor, ResponseNode).
- **Gaps**: The `NodeToolPolicy` resolution mechanism exists (Milestone 1.2), but no concrete tool definitions, node-specific tool scope configurations, or `enhanced_context_retrieval` cache behavior have been implemented. Nodes currently have no defined tool scopes — the resolution infrastructure is in place but the actual tool contracts are not.
- **Non-Goals**:
  - Implementing the full tool SDK or replacing the placeholder `Tool` class with production tool implementations.
  - Implementing retry/validation behavior for tool calls (covered in Milestone 4.3).
  - Implementing streaming/tool-event lifecycle (covered in Milestone 4.4).
  - Implementing the `NodeMessagePolicy`, `NodeStreamPolicy`, or `NodeRetryPolicy` concrete node configurations (already covered in Milestone 1.2).
- **Constraints**:
  - Must not modify `tinycua-sdk` public APIs.
  - Must honor the existing `NodeToolPolicy.resolve_tools()` resolution order (node_tools → include_agent_tools → deny-wins-over-allow).
  - Must not introduce external dependencies beyond what the prototype already uses.
  - Tool scopes must match the design docs: `docs/design/constants/tools.md`, `docs/design/tools/task.md`, `docs/design/tools/todo.md`, `docs/design/tools/digester.md`.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A TinyCUA node is configured with a `NodeToolPolicy` that defines its allowed tools. When `TinyCUALoop._prepare_node()` calls `node.config.tool_policy.resolve_tools(outer_agent_tools)`, the node receives only the tools it is authorized to use. Different node types (QueryAnalyst, Worker, TaskCreate, TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, ResultAggregation, ResponseNode, InformationDigester) each have their own tool scope that matches the design specification.

### Acceptance Scenarios

1. **Given** a `TinyCUATaskExecutorNode` configured with `include_agent_tools="selected"` and `allowed_agent_tool_names=["web_search"]`, **When** `resolve_tools()` is called with outer tools `[web_search, calculator, file_read]`, **Then** the node receives `[node_task_tools, web_search]` — its node tools plus only the selected outer tool.

2. **Given** a `TinyCUATaskAnalyzerNode` in `task_creation` mode, **When** `resolve_tools()` is called, **Then** the node does NOT receive `TaskInit` or `TaskCreate` tools (TaskCreateNode handles root creation).

3. **Given** a `TinyCUATaskAnalyzerNode` in `task_recreation` mode, **When** `resolve_tools()` is called, **Then** the node DOES receive `TaskInit` and `TaskCreate` tools (LLM-assisted replacement).

4. **Given** a `TinyCUATaskAnalyzerNode` in `task_reanalysis` mode, **When** `resolve_tools()` is called, **Then** the node does NOT receive `TaskInit` or `TaskCreate` tools (refinement only).

5. **Given** a `TinyCUAQueryAnalystNode`, **When** `resolve_tools()` is called, **Then** the node receives classification tools and read-only task/context inspection tools, but no task mutation tools.

6. **Given** a `TinyCUAResponseNode` with `allow_information_digest_request=True`, **When** it needs additional context, **Then** it can suspend and prepend `InformationDigesterNode` to gather context before resuming.

7. **Given** `enhanced_context_retrieval` called by InformationDigesterNode, **When** called a second time for the same session, **Then** the tool reuses the cached scoped context file rather than recreating it.

8. **Given** `enhanced_context_retrieval` called by TaskExecutor directly (without spawning InformationDigesterNode), **When** called, **Then** the tool creates its own scoped cache and runs ReAct-style search within it.

### Edge Cases

- What happens when a node's `node_tools` list contains a tool whose name also appears in `denied_agent_tool_names`? (Node tools are always included — deny only applies to outer agent tools.)
- What happens when `include_agent_tools="selected"` but `allowed_agent_tool_names` is empty? (No outer tools are included.)
- What happens when `enhanced_context_retrieval` is called with an empty or minimal `session_context`? (It should create a cache with available context and return a "no useful context" fallback.)
- What happens when two nodes (e.g., TaskExecutor and ResponseNode) both call `enhanced_context_retrieval` on the same session? (Each gets its own scoped cache file — caches are per-call, not shared across nodes.)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Each concrete TinyCUA node MUST have a predefined `NodeToolPolicy` that matches its tool scope from `docs/design/constants/tools.md`.
- **FR-002**: `TinyCUATaskExecutorNode` tool scope MUST include task execution tools, selected outer Agent tools, `enhanced_context_retrieval`, and exploration/web/context search tools when enabled.
- **FR-003**: `TinyCUAResponseNode` tool scope MUST include the same base toolset as TaskExecutor, plus final response/synthesis tools, plus optional information-digestion request capability only when enabled.
- **FR-004**: `TinyCUAQueryAnalystNode` tool scope MUST include classification tools and read-only task/context inspection tools.
- **FR-005**: `TinyCUAInformationDigesterNode` tool scope MUST include `enhanced_context_retrieval` and `digest_information` tools.
- **FR-006**: `TinyCUATaskCreateNode` tool scope MUST include deterministic root task creation tools (`TaskInit`/`TaskCreate`) only.
- **FR-007**: `TinyCUATaskAnalyzerNode` tool scope MUST include structural task tools, with `TaskInit`/`TaskCreate` available only in `task_recreation` mode.
- **FR-008**: `TinyCUATaskAssessorNode` tool scope MUST include task assessment/read/update tools.
- **FR-009**: `TinyCUAWorkerNode` tool scope MUST include worker decision tools only.
- **FR-010**: `TinyCUAResultReviewerNode` tool scope MUST include review/decision tools and task result/context update tools.
- **FR-011**: Todo tools MUST be exposed through `NodeToolPolicy` to TaskExecutorNode and optionally ResponseNode, not through global agent-node configuration.
- **FR-012**: `enhanced_context_retrieval` MUST lazily create a scoped context cache file when called and run ReAct-style search within that cache.
- **FR-013**: `enhanced_context_retrieval` cache MUST be per-call — each invocation creates its own scoped cache file.
- **FR-014**: Task tool calls MUST directly mutate root `session.task` through TinyCUALoop task helpers; nodes MUST NOT return opaque mutation instructions.
- **FR-015**: Path-specific task tool semantics MUST be enforced: `task_creation` mode = TaskCreateNode only; `task_recreation` = TaskAnalyzerNode gets TaskInit/TaskCreate; `task_reanalysis` = no TaskInit/TaskCreate for TaskAnalyzerNode.

### Key Entities

- **NodeToolPolicy**: Configuration dataclass controlling tool scope resolution per node. Already implemented in Milestone 1.2.
- **Tool**: Placeholder SDK tool type. Existing stub in `config/types.py`.
- **enhanced_context_retrieval**: Shared tool for scoped context search/cache. Used by InformationDigesterNode, TaskExecutor, and ResponseNode.
- **digest_information**: Tool for producing structured digested information. Used by InformationDigesterNode.
- **TaskInit / TaskCreate**: Task creation tools. Exposed to TaskCreateNode (always) and TaskAnalyzerNode (only in recreation mode).

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Every node has a defined tool scope**: All 11 concrete TinyCUA nodes have `NodeToolPolicy` configurations matching `docs/design/constants/tools.md`.
- [ ] **Tool resolution works end-to-end**: `TinyCUALoop._prepare_node()` resolves the correct tools for each node via `node.config.tool_policy.resolve_tools(tools)`.
- [ ] **Task tools mutate session directly**: Task tool calls directly mutate `session.task` through TinyCUALoop task helpers.
- [ ] **Path-specific task tool scoping works**: TaskAnalyzerNode receives/excludes TaskInit/TaskCreate based on mode (creation, recreation, reanalysis).
- [ ] **Todo tools are policy-controlled**: Todo tools are exposed only to nodes whose `NodeToolPolicy` allows them (TaskExecutor, optionally ResponseNode).
- [ ] **enhanced_context_retrieval cache works**: The tool lazily creates scoped caches, runs ReAct-style search, and caches are per-call.
- [ ] **TaskExecutor can call enhanced_context_retrieval directly**: Without spawning InformationDigesterNode.
- [ ] **Tests pass**: Unit tests for all node tool scope configurations and integration tests for tool resolution through the loop.

---

## Testing Plan _(mandatory)_

### Unit Tests

- [ ] Test `NodeToolPolicy` resolution for each concrete node type's expected tool scope.
- [ ] Test path-specific task tool scoping (creation, recreation, reanalysis modes).
- [ ] Test `enhanced_context_retrieval` cache creation and ReAct search behavior.
- [ ] Test `digest_information` tool output format.
- [ ] Test todo tool exposure via `NodeToolPolicy` for TaskExecutor and ResponseNode.
- [ ] Test edge cases: deny-wins-over-allow for node-specific tools, empty allowed list, empty session_context.

### Integration Tests

- [ ] Test `TinyCUALoop._prepare_node()` resolves correct tools for each node type.
- [ ] Test end-to-end tool resolution flow: agent tools → policy resolution → node receives correct subset.
- [ ] Test `enhanced_context_retrieval` called by different nodes on the same session produces independent caches.
- [ ] Test TaskExecutor calling `enhanced_context_retrieval` directly without spawning InformationDigesterNode.

### Manual Tests _(if applicable)_

- [ ] Verify that a TinyCUA agent with tool scoping configured can run through the QueryAnalyst → Worker → TaskCreate → TaskAnalyzer → TaskExecutor → ResultReviewer → Response path with correct tool visibility at each step.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| NodeToolPolicy resolution | Done | Implemented in Milestone 1.2 |
| Concrete node tool scope configs | TODO | Per-node NodeToolPolicy definitions |
| Task tools (TaskInit/TaskCreate) | TODO | Concrete tool implementations |
| Todo tools | TODO | Concrete tool implementations |
| enhanced_context_retrieval | TODO | Scoped cache + ReAct search |
| digest_information tool | TODO | Structured digest output |
| Path-specific task tool scoping | TODO | Mode-dependent TaskInit/TaskCreate |
| Unit tests for node scopes | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Should the placeholder `Tool` class be replaced with a richer type in this milestone?**
   - **Owner**: @VJyzCELERY
   - **Status**: Discussion
   - **Proposed Answer**: Keep the placeholder for this milestone; the milestone focuses on scope configuration, not tool implementation details.

2. **Should `enhanced_context_retrieval` be a real tool or a stub with the cache contract defined?**
   - **Owner**: @VJyzCELERY
   - **Status**: Discussion
   - **Proposed Answer**: Implement the cache contract and ReAct search interface as a stub that can be filled in with real search later.

---

## Review Checklist

- [ ] No implementation details beyond what the design docs specify
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
- [ ] Exit criteria match Milestone 4.2 from the roadmap issue
