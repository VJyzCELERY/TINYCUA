# Feature Specification: Milestone 4.2 — Tool Scoping

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua (prototype)
**Roadmap Issue**: [#87 — Milestone 4.2](https://github.com/VJyzCELERY/TINYCUA/issues/87)

---

## Problem Statement

- **Goals**: Wire per-node tool policies so each TinyCUA node sees only its allowed tools, implement the task/todo/digester tool functions, and verify the shared `enhanced_context_retrieval` contract across its consumers (InformationDigester, TaskExecutor, ResponseNode).
- **Gaps**: The `NodeToolPolicy` resolution mechanism and its integration in `TinyCUALoop._prepare_node()` are fully implemented and tested, but every concrete node currently uses the default `NodeToolPolicy(include_agent_tools="none")`. No TinyCUA-specific tools (task tools, todo tools, `enhanced_context_retrieval`, `digest_information`) exist yet. Per-node config subclasses or factory functions that assemble the correct tool policy for each node type do not exist.
- **Non-Goals**: Implementing the missing concrete nodes (TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, ResultAggregation) — those belong to earlier or later milestones. Production-quality CLI/TUI UX. WildClawBench integration.
- **Constraints**: Must not modify `tinycua-sdk` public APIs. Must preserve the existing `NodeToolPolicy` dataclass interface and `resolve_tools()` contract. All tools must work with local model endpoints.

---

## User Scenarios & Testing

### Primary Scenario

A developer instantiates `create_tinycua_agent(...)` and the resulting agent's nodes each receive only the tools they are designed to use. For example, `QueryAnalystNode` sees classification and read-only task tools but never sees shell or file-write tools. `TaskExecutorNode` sees execution tools plus selected outer Agent tools and `enhanced_context_retrieval`. The shared `enhanced_context_retrieval` tool produces consistent results whether called by InformationDigester, TaskExecutor, or ResponseNode.

### Acceptance Scenarios

1. **Given** a `QueryAnalystNode` with its designed tool policy, **When** `resolve_tools()` is called with outer Agent tools, **Then** only classification and read-only task/context tools are included — no shell, file-write, or execution tools.
2. **Given** a `TaskExecutorNode` with `include_agent_tools="selected"` and `allowed_agent_tool_names=["run_shell", "read_file"]`, **When** `resolve_tools()` is called, **Then** the resolved tools contain the node's task tools plus exactly `run_shell` and `read_file` from outer tools.
3. **Given** a `ResponseNode` with the same base toolset as `TaskExecutorNode`, **When** its tool policy is resolved, **Then** it includes all TaskExecutor tools plus optional information-digestion request capability.
4. **Given** `enhanced_context_retrieval` called by InformationDigester with a session context, **When** the tool is invoked a second time with the same session, **Then** it reuses the lazily-created scoped cache rather than creating a new one.
5. **Given** a node with `include_agent_tools="all"` and `denied_agent_tool_names=["run_shell"]`, **When** `resolve_tools()` is called, **Then** `run_shell` is excluded even though it would be included by `"all"`.

### Edge Cases

- What happens when a node's `node_tools` list contains a tool with the same name as an outer Agent tool? **Deny wins over allow** per the resolution order.
- What happens when `enhanced_context_retrieval` receives an empty session context? It should create a minimal cache and return a "no useful context" result.
- What happens when a node is configured with `include_agent_tools="selected"` but `allowed_agent_tool_names` is empty? Only `node_tools` are included.

---

## Requirements

### Functional Requirements

- **FR-001**: `NodeToolPolicy.resolve_tools(outer_agent_tools)` MUST implement the resolution order: start with `node_tools`, then conditionally merge outer tools based on `include_agent_tools` mode, with deny winning over allow.
- **FR-002**: Each concrete TinyCUA node MUST be configurable with a node-specific `NodeToolPolicy` that reflects its designed tool scope from `docs/design/constants/tools.md`.
- **FR-003**: `QueryAnalystNode` MUST have tool scope limited to classification + read-only task/context tools.
- **FR-004**: `InformationDigesterNode` MUST have tool scope limited to `enhanced_context_retrieval` + `digest_information`.
- **FR-005**: `WorkerNode` MUST have tool scope limited to worker decision tools only.
- **FR-006**: `TaskCreateNode` MUST have tool scope limited to deterministic root task creation tools (`TaskInit`/`TaskCreate`).
- **FR-007**: `TaskExecutorNode` (when implemented) MUST have tool scope including task execution tools + selected outer Agent tools + `enhanced_context_retrieval`.
- **FR-008**: `ResponseNode` (when implemented with full toolset) MUST have the same base toolset as TaskExecutorNode plus optional information-digestion request capability.
- **FR-009**: `enhanced_context_retrieval` MUST lazily create a scoped session-context cache and run a limited ReAct-style search over that cache using grep/search and paginated read tools.
- **FR-010**: `enhanced_context_retrieval` MUST be callable by InformationDigesterNode, TaskExecutorNode, and ResponseNode with consistent behavior across all consumers.
- **FR-011**: Task tools (TaskInit, TaskCreate, task assessment/read/update, task execution, review decision) MUST be implemented as callable tool functions.
- **FR-012**: Todo tools MUST be implemented and available to nodes whose `NodeToolPolicy` includes them.

### Key Entities

- **NodeToolPolicy**: Controls which tools a node can see. Contains `node_tools`, `include_agent_tools` mode, `allowed_agent_tool_names`, and `denied_agent_tool_names`.
- **Tool**: A callable function with a name, description, and parameter schema that can be presented to an LLM.
- **enhanced_context_retrieval**: A shared tool that lazily creates a scoped context cache and provides ReAct-style search over it.
- **Task Tools**: Structural tools that directly mutate `session.task` through TinyCUALoop task helpers (TaskInit, TaskCreate, task assessment, task execution, review decision).
- **Todo Tools**: Plan/task tracking tools exposed through `NodeToolPolicy`.

---

## Success Criteria

- [ ] **Each node sees only allowed tools**: QueryAnalyst, InformationDigester, Worker, TaskCreate, TaskExecutor, ResultReviewer, and ResponseNode each resolve to their designed tool scope.
- [ ] **Deny wins over allow**: A tool in both `allowed_agent_tool_names` and `denied_agent_tool_names` is excluded.
- [ ] **Node tools always included**: `node_tools` are always in the resolved set regardless of `include_agent_tools` mode.
- [ ] **enhanced_context_retrieval works across consumers**: InformationDigester, TaskExecutor, and ResponseNode all invoke the same tool and get consistent cache behavior.
- [ ] **Task tools mutate session.task directly**: TaskInit/TaskCreate and related tools call TinyCUALoop task helpers rather than returning opaque instructions.
- [ ] **Todo tools propagate correctly**: Todo state propagates according to `PropagationRule`.
- [ ] **All existing tests pass**: The existing `NodeToolPolicy` resolution tests and `TinyCUALoop` integration tests remain green.

---

## Testing Plan

### Unit Tests

- `TestNodeToolPolicy` (existing — 8 tests): Verify defaults, none/selected/all modes, deny-wins-over-allow, deny-wins-over-all, node_tools-always-included.
- **New per-node tool policy tests**: For each concrete node, verify `resolve_tools()` returns the designed tool scope.
- **enhanced_context_retrieval tests**: Lazy cache creation, cache reuse, empty context handling, ReAct-style search within cache boundaries.
- **Task tool tests**: Each task tool (TaskInit, TaskCreate, assessment, execution, review) correctly calls TinyCUALoop task helpers.
- **Todo tool tests**: Todo tools read/write todo state and propagate correctly.

### Integration Tests

- **Node tool scope integration**: Instantiate each node with its designed config, call `resolve_tools()` with a mock outer tool set, verify the resolved tools match the design.
- **enhanced_context_retrieval cross-consumer**: Call the tool from InformationDigester, TaskExecutor, and ResponseNode contexts, verify consistent cache behavior.
- **TinyCUALoop tool resolution end-to-end**: Run a minimal queue with nodes configured with their designed tool policies, verify each node receives only its allowed tools during `_prepare_node()`.

### Manual Tests

- Verify that `create_tinycua_agent(...)` returns an agent whose nodes have non-default tool policies configured.
- Run a minimal agent flow and inspect that each node's LLM call receives only the expected tools.

---

## Open Questions

1. **Per-node config subclasses vs. factory functions**: Should we create `TinyCUAQueryAnalystNodeConfig`, `TinyCUAWorkerNodeConfig`, etc. as subclasses of `NodeConfigBase`, or use factory functions that return `NodeConfigBase` with the correct `NodeToolPolicy`? The design doc lists per-node config classes but the current code uses only `NodeConfigBase`.
   - **Proposed Answer**: Use per-node config subclasses as documented in `docs/design/config/node_config.md` — they are already specced and match the design intent.
2. **Tool registration pattern**: Should tools be registered as module-level singletons or instantiated per-node? The current `Tool` placeholder stub suggests per-instance, but real tools may need shared state (e.g., `enhanced_context_retrieval` cache).
   - **Proposed Answer**: Tools with shared state (cache) should be module-level or passed via dependency injection; stateless tools can be per-instance.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices) — spec-level only
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
