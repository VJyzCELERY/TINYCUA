# Design Document: TinyCUA Actionable Runtime Traceability

**Spec**: `./spec.md`
**Status**: In Progress
**Last Updated**: 2026-06-15

---

## Overview

This design turns the finalization branch from a traceable planner into an
actionable local agent runtime. It adds node-prefixed transcript events, readable
task-tree rendering, default workspace/web action tools, and in-memory session
continuation contracts while preserving the no-SDK-change boundary.

---

## Architecture

### Component Overview

```text
Agent.run / stream
  |
  v
TinyCUALoop
  |-- transcript events: [USER], [Node], [Node][tool]
  |-- trace entries: resolved tools + llm-visible tools + forced tool_choice
  |-- task tree renderer: JSON snapshot -> readable hierarchy
  |
  v
Worker/TaskExecutor
  |-- workspace native tools (file/shell/python) enabled by default
  |-- SearXNG search tool enabled by default
  |-- tool results -> task result/artifact metadata
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.factory` | Modified | Default agent tool list includes workspace action tools and SearXNG search. |
| `tinycua.agent.tools.native.web_search` | New | SearXNG JSON search tool. |
| `tinycua.loops.tinycua_loop` | Modified | Emit/read transcript events, trace actual LLM-visible tool scope, preserve session continuation. |
| `tinycua.loops.task_tree_rendering` | New | Bounded text renderer for task hierarchy. |
| `tinycua.loops.task_nodes` | Modified | TaskExecutor records action tool results/artifacts. |
| Notebook/CLI | Modified | Display readable task tree and node/tool transcript. |

---

## Data Model

### New Entities _(if applicable)_

```python
TranscriptEvent:
    type: str              # user, node_delta, tool_call, tool_result
    node_id: str | None
    node_label: str
    tool_name: str | None
    content: str
    visibility: str        # user_visible or debug

TaskTreeRenderOptions:
    max_depth: int
    max_nodes: int
    include_status: bool
```

### Schema Changes _(if applicable)_

- Trace entries gain optional `llm_tool_names`, `forced_tool_choice`, and
  `tool_choice_strategy` fields.
- State snapshots gain optional `task_tree_text` for display-only rendering.
- Task result metadata can include `tool_results` and artifact paths.

---

## API / Interface Contracts

### New / Modified Functions

```python
TinyCUALoop.get_transcript_events() -> list[dict[str, Any]]
TinyCUALoop.render_task_tree() -> str
```

Factory behavior changes:

```python
create_tinycua_agent(...)
# default: includes safe workspace-native tools and web_search
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| SearXNG unavailable | Tool result `success=False` | No synthetic search success. |
| Shell timeout | Tool result `timed_out=True` | Recorded in trace/task metadata. |
| Path outside workspace | Tool error | Existing workspace confinement remains authoritative. |

---

## Implementation Phases

### Phase 1 — Traceability MVP _(required)_

- [ ] Add transcript event model/helpers and node/tool labels.
- [ ] Add task-tree text renderer and expose via loop state snapshot.
- [ ] Add deterministic tests for readable stream transcript and task tree.

### Phase 2 — Action Tool Availability _(required)_

- [ ] Add SearXNG web search tool.
- [ ] Enable workspace file/shell/python/web tools by default with workspace confinement.
- [ ] Add deterministic tests proving real file write + shell verification.

### Phase 3 — Session Continuation _(required)_

- [ ] Add tests for in-memory session reuse across runs.
- [ ] Ensure compaction inputs remain available without persistent storage.

### Phase 4 — Notebook/CLI Demo _(required)_

- [ ] Show transcript, task tree text, tool results, and artifacts.
- [ ] Update live/manual validation notes.

---

## Technical Decisions

1. **Decision**: Keep implementation in TinyCUA only.
   - **Reason**: PR constraint forbids SDK changes.
   - **Alternatives Considered**: SDK per-call event APIs — deferred.
2. **Decision**: Enable action tools by default but keep workspace confinement.
   - **Reason**: The prototype goal is a functional local agent, not a planner.
   - **Alternatives Considered**: Opt-in native tools — rejected for this prototype goal.
3. **Decision**: Display task trees as bounded text plus JSON.
   - **Reason**: Users need readable progress while developers need full state.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Shell tools perform unwanted actions | Medium | High | Workspace cwd binding; path confinement; explicit docs. |
| Local model ignores tools | Medium | High | Existing forced route tools; action tests with deterministic tool calls. |
| Stream output becomes noisy | Medium | Medium | User-visible transcript events are separate from debug events. |
| Web search flakes | Medium | Medium | Structured failure results; deterministic tests mock HTTP. |

---

## Open Questions _(optional)_

None.

---

## References

- Spec: `./spec.md`
- Parent finalization spec: `../tinycua-finalize-prototype-runtime/spec.md`
- Reliability plan: `../tinycua-finalize-prototype-runtime/runtime-reliability-implementation-plan.md`
