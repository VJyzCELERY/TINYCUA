# Implementation: TinyCUA Design Simplification — Documentation Reorganization

Rewrite TinyCUA design documentation around the SDK-compatible TinyCUALoop / NodeQueue architecture and produce a reviewable implementation roadmap draft. This is a **docs-only** PR.

## Context

- **Spec Reference**: `src/tinycua/specs/design-simplification/spec.md`
- **Design Reference**: `src/tinycua/specs/design-simplification/design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

- **None** — documentation only.

---

## Success Criteria — Integration Tests (TDD First)

No automated tests are required for this docs-only PR.

### Key Verification Scenarios

- [ ] `docs/design/` describes SDK-compatible TinyCUALoop architecture without requiring SDK changes.
- [ ] All current `docs/design` files/groups are accounted for in the migration table and final file layout.
- [ ] Old architecture terms appear only in migration/history context.
- [ ] Roadmap draft exists and contains PR-sized sequential milestones tied to design docs.

---

## Verification Plan

### Automated / Search Checks

- [ ] Search for stale target-architecture terms: `AgentGraph`, `RouterNode`, `AgentNode`, `PrimaryNode`, `Worker QueryAnalyst`, YAML front-matter transport.
- [ ] Count markdown files under `src/tinycua/docs/design/`; target is 30 or fewer after cleanup.
- [ ] Verify no source code or test files changed.
- [ ] Verify compaction docs define strategy-owned behavior and one assistant-message output.
- [ ] Verify system prompt docs distinguish static, configurable, and dynamic system prompt segments.

### Manual Verification

- [ ] Read `docs/design/README.md` reading order.
- [ ] Read each new architecture doc for SDK-boundary consistency.
- [ ] Confirm roadmap draft follows `.github/ISSUE_TEMPLATE/roadmap.yml` conceptually.
- [ ] Confirm roadmap draft milestones are PR-sized and list design-doc coverage.

---

## Proposed Changes

### Phase 0 — Rewrite Planning Docs

#### MODIFY `src/tinycua/specs/design-simplification/spec.md`

- Rewrite from scratch with final requirements for docs/design migration, SDK-boundary constraints, node architecture, streaming, and roadmap draft.

#### MODIFY `src/tinycua/specs/design-simplification/design.md`

- Rewrite from scratch with full architecture design and complete docs/design migration table.

#### MODIFY `src/tinycua/specs/design-simplification/implementation-plan.md`

- Rewrite from scratch with phased docs workflow.

#### MODIFY `src/tinycua/specs/design-simplification/task.md`

- Rewrite from scratch with detailed task IDs.

### Phase 0a — Synchronize Planning Docs

#### MODIFY `src/tinycua/specs/design-simplification/spec.md`

- Update spec.md with FR-048+ continuation/task-tree/aggregation/retrieval-cache requirements.
- Add new edge cases for duplicate WorkerNode, open_question, and resumed WorkerNode reuse.
- Add `MandatoryPassthrough` and `AggregatedResult` to Key Entities.
- Add provider prompt caching to non-goals.

#### MODIFY `src/tinycua/specs/design-simplification/design.md`

- Update design.md with corresponding blueprint sections: Queue Bootstrap, QueryAnalyst Prechecks, Mandatory Passthrough, TaskTree Active Task Lifecycle, ResultAggregationNode, Tool Scope, ResponseNode Consolidated Continuation, Provider Prompt Caching Non-Goal.
- Add AggregatedResult model and enhanced_context_retrieval cache behavior.

#### MODIFY `src/tinycua/specs/design-simplification/implementation-plan.md`

- Add Phase 0a and Phase 6a/7a tasks for this clarification pass.

#### MODIFY `src/tinycua/specs/design-simplification/task.md`

- Add task items for Phase 0a synchronization and Phase 6a/7a roadmap/PR body synchronization.

### Phase 1 — Create New Design Docs

Create these docs before deleting old docs:

- `src/tinycua/docs/design/loops/base_loop.md`
- `src/tinycua/docs/design/loops/tinycua_loop.md`
- `src/tinycua/docs/design/loops/node_queue.md`
- `src/tinycua/docs/design/loops/node.md`
- `src/tinycua/docs/design/loops/route_map.md`
- `src/tinycua/docs/design/loops/propagation.md`
- `src/tinycua/docs/design/loops/worker_concept.md`
- `src/tinycua/docs/design/config/node_config.md`
- `src/tinycua/docs/design/config/session_config.md`

### Phase 2 — Update Retained Docs

Update retained docs to reference the new architecture:

- `src/tinycua/docs/design/README.md`
- `src/tinycua/docs/design/loops/overview.md`
- `src/tinycua/docs/design/constants/instructions.md`
- `src/tinycua/docs/design/constants/tools.md`
- `src/tinycua/docs/design/tools/digester.md`
- `src/tinycua/docs/design/tools/task.md`
- `src/tinycua/docs/design/tools/todo.md`
- `src/tinycua/docs/design/utility/compaction.md`

### Phase 3 — Rename State Docs to Models

Rename `docs/design/state/` to `docs/design/models/` and update model docs for:

- Session/root and per-node sessions
- StateObject and NodeInput/NodePayload transport
- AgentState as lifecycle/result output
- ChatRecord source-node metadata and dedupe
- Task, information, classification, execution, reviewer, worker result models

### Phase 4 — Reconcile

- Verify each old doc's useful content landed in the correct new/retained doc.
- Verify links and references are updated.
- Verify old concepts appear only in migration/history context.
- Verify new docs acknowledge SDK Agent.run/BaseLoop.run inputs and do not propose SDK changes.

### Phase 5 — Cleanup Obsolete Docs

Only after Phase 4:

- Delete `docs/design/agent_node/`.
- Delete `docs/design/agents/`.
- Delete `docs/design/orchestration/`.
- Delete old per-agent loop docs merged into `loops/node.md`.
- Delete `docs/design/config/types.md` and `docs/design/config/agents.md`.

### Phase 6 — Roadmap Draft

Create:

```text
src/tinycua/docs/roadmap/tinycua_architecture_implementation/
└── tinycua_architecture_implementation_main_issue_draft.md
```

Roadmap draft requirements:

- Follow `.github/ISSUE_TEMPLATE/roadmap.yml` conceptually.
- Scope only TinyCUA architecture implementation.
- Exclude TUI, CLI, HITL UX, interrupt UX, datastore persistence, resume UX, and SDK modifications.
- Keep milestones sequential and PR-sized by default.
- Each milestone lists design docs covered, full/partial coverage, implemented contract, deferred contract, expected PR scope, and exit criteria.
- Avoid sub-issue drafts unless a milestone cannot reasonably fit one PR.
- Mark draft directory as temporary review material to convert/delete before merge.

### Phase 6a — Roadmap Synchronization

#### MODIFY `src/tinycua/docs/roadmap/tinycua_architecture_implementation/tinycua_architecture_implementation_main_issue_draft.md`

- Add/update roadmap milestones for mandatory_passthrough, active task lifecycle, ResultAggregationNode, retrieval cache, and ResponseNode continuation.
- Update E2E verification gate with new architecture contract checks.

### Phase 7 — Final Verification, Commit, Push, PR Update

- Verify docs-only diff.
- Inspect `git status`, `git diff`, and `git log --oneline -10`.
- Stage only intended docs/planning/roadmap draft files.
- Commit and push (user granted permission).
- Squash/cleanup PR commit history if needed (user granted permission).
- Update PR title/body to match new docs scope (user granted permission).

### Phase 7a — PR Body Synchronization

#### UPDATE PR #86 body

- Update PR body so the public PR description matches the new architecture scope.
- Add summary/solution additions for mandatory_passthrough, queue bootstrap, active task lifecycle, ResultAggregationNode, enhanced_context_retrieval cache, and ResponseNode consolidated continuation.
- Add scope additions for FR-048 through FR-058.
- Add out-of-scope clarification for architecture-level continuation routing vs HITL UX.
- Add review notes for TaskTree/ResultAggregationNode, QueryAnalyst/mandatory_passthrough, and roadmap synchronization.

---

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `docs/design/loops/*` | New/Modified | Main TinyCUALoop, NodeQueue, node, route, propagation docs. |
| `docs/design/config/*` | New/Modified | SessionConfig and node config policies. |
| `docs/design/models/*` | Rename/Modified | Former state docs with NodeInput/NodePayload/session updates. |
| `docs/design/agent_node/*` | Remove | Merged into node/loop/model docs. |
| `docs/design/agents/*` | Remove | Merged into concrete TinyCUA node docs. |
| `docs/design/orchestration/*` | Remove | Merged into TinyCUALoop/NodeQueue/Worker docs. |
| `docs/design/exceptions/*` | Remove | Merged into TinyCUALoop/node docs. |
| `docs/roadmap/*` | New temporary draft | Reviewable issue draft for implementation roadmap. |

---

## Dependencies

### External Dependencies

None.

### Internal Dependencies

- Current SDK Agent/BaseLoop contract is treated as fixed input.
- Current design docs are source material for migration.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing old content during cleanup | High | Create new docs first, reconcile before delete. |
| Roadmap milestones too broad | Medium | Require PR-sized milestones in roadmap draft. |
| SDK contract misrepresented | High | Explicit SDK boundary section in design docs. |
| Roadmap draft accidentally committed permanently | Low | Document as temporary review material to convert/delete before merge. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-04*
