# Tasks: TinyCUA Design Simplification — Documentation Reorganization

Implementation tasks for the docs-only TinyCUA design simplification PR.

## Phase 0: Rewrite Planning Docs

- [ ] Rewrite `spec.md` from scratch with docs-only requirements and roadmap draft requirement <!-- id: 0 -->
- [ ] Rewrite `design.md` from scratch with full architecture and migration table <!-- id: 1 -->
- [ ] Rewrite `implementation-plan.md` from scratch with phased workflow <!-- id: 2 -->
- [ ] Rewrite `task.md` from scratch with detailed task IDs <!-- id: 3 -->
- [ ] Verify planning docs preserve SDK contract and prohibit SDK modifications <!-- id: 4 -->

## Phase 1: Create New Architecture Docs

- [ ] Create `docs/design/loops/base_loop.md` <!-- id: 5 -->
- [ ] Create `docs/design/loops/tinycua_loop.md` <!-- id: 6 -->
- [ ] Create `docs/design/loops/node_queue.md` <!-- id: 7 -->
- [ ] Create `docs/design/loops/node.md` <!-- id: 8 -->
- [ ] Create `docs/design/loops/route_map.md` <!-- id: 9 -->
- [ ] Create `docs/design/loops/propagation.md` <!-- id: 10 -->
- [ ] Create `docs/design/loops/worker_concept.md` <!-- id: 11 -->
- [ ] Create `docs/design/config/node_config.md` <!-- id: 12 -->
- [ ] Create `docs/design/config/session_config.md` <!-- id: 13 -->

## Phase 2: Update Retained Docs

- [ ] Update `docs/design/README.md` with new structure and reading order <!-- id: 14 -->
- [ ] Update `docs/design/loops/overview.md` for TinyCUALoop architecture <!-- id: 15 -->
- [ ] Merge old `docs/design/loops/react_agent.md` SDK relationship content into `loops/base_loop.md` <!-- id: 16 -->
- [ ] Update `docs/design/constants/instructions.md` for hardcoded instruction/continuation constants <!-- id: 17 -->
- [ ] Update `docs/design/constants/tools.md` for NodeToolPolicy <!-- id: 18 -->
- [ ] Update `docs/design/tools/digester.md` for InformationDigester node usage <!-- id: 19 -->
- [ ] Update `docs/design/tools/task.md` for task-node tool scopes <!-- id: 20 -->
- [ ] Update `docs/design/tools/todo.md` for TinyCUA node usage <!-- id: 21 -->
- [ ] Update `docs/design/utility/compaction.md` for SessionConfig compaction <!-- id: 22 -->
- [ ] Merge `docs/design/exceptions/loops.md` error framing into TinyCUALoop/node docs <!-- id: 23 -->
- [ ] Update system prompt guidance across node/config docs <!-- id: 23a -->
- [ ] Update compaction strategy contract across utility/session/config docs <!-- id: 23b -->

## Phase 3: Rename State to Models

- [ ] Rename `docs/design/state/` to `docs/design/models/` <!-- id: 24 -->
- [ ] Update `models/session.md` for root/per-node sessions, SDK messages, propagation, and dedupe <!-- id: 25 -->
- [ ] Update `models/state_object.md` for NodeInput/NodePayload serialization base <!-- id: 26 -->
- [ ] Update `models/agent_state.md` for lifecycle/result state only <!-- id: 27 -->
- [ ] Update `models/chat_record.md` for source-node metadata and message IDs <!-- id: 28 -->
- [ ] Update remaining model docs references and target terminology <!-- id: 29 -->

## Phase 4: Reconcile

- [ ] Verify design migration table covers every current `docs/design` file/group <!-- id: 30 -->
- [ ] Verify old graph concepts only appear in migration/history contexts <!-- id: 31 -->
- [ ] Verify no target Worker QueryAnalyst remains <!-- id: 32 -->
- [ ] Verify `TinyCUAResponseNode` naming is consistent <!-- id: 33 -->
- [ ] Verify NodeInput/NodePayload replaces internal YAML/front-matter transport <!-- id: 34 -->
- [ ] Verify SDK `Agent.run` / `BaseLoop.run` contract is described consistently <!-- id: 35 -->
- [ ] Verify all internal links and related sections are updated <!-- id: 36 -->

## Phase 5: Cleanup Obsolete Docs

- [ ] Delete `docs/design/agent_node/` <!-- id: 37 -->
- [ ] Delete `docs/design/agents/` <!-- id: 38 -->
- [ ] Delete `docs/design/orchestration/` <!-- id: 39 -->
- [ ] Delete old per-agent loop docs merged into `loops/node.md` <!-- id: 40 -->
- [ ] Delete `docs/design/config/types.md` and `docs/design/config/agents.md` <!-- id: 41 -->

## Phase 6: Roadmap Draft

- [ ] Create `docs/roadmap/tinycua_architecture_implementation/tinycua_architecture_implementation_main_issue_draft.md` <!-- id: 42 -->
- [ ] Ensure roadmap draft uses roadmap issue template structure conceptually <!-- id: 43 -->
- [ ] Ensure roadmap draft excludes TUI, CLI, HITL UX, interrupt UX, datastore persistence, resume UX, and SDK modifications <!-- id: 44 -->
- [ ] Ensure roadmap milestones are sequential and PR-sized by default <!-- id: 45 -->
- [ ] Ensure each milestone lists design docs covered, full/partial coverage, implemented/deferred contract, expected PR scope, and exit criteria <!-- id: 46 -->
- [ ] Avoid sub-issue drafts unless a milestone cannot reasonably fit one PR <!-- id: 47 -->
- [ ] Document roadmap draft directory as temporary review material to convert/delete before merge <!-- id: 48 -->

## Phase 7: Final Verification

- [ ] Count markdown files under `docs/design`; target 30 or fewer <!-- id: 49 -->
- [ ] Search stale terms and verify only migration/history usage remains <!-- id: 50 -->
- [ ] Verify no source code or test files changed <!-- id: 51 -->
- [ ] Inspect `git status`, `git diff`, and `git log --oneline -10` <!-- id: 52 -->
- [ ] Stage only intended docs/planning/roadmap draft files <!-- id: 53 -->

## Review and Merge

- [ ] Commit final docs changes <!-- id: 54 -->
- [ ] Push branch to origin <!-- id: 55 -->
- [ ] Update PR title and body <!-- id: 56 -->
- [ ] Address review feedback <!-- id: 57 -->
- [ ] Before merge, convert roadmap draft to real GitHub issue and delete draft directory unless user decides otherwise <!-- id: 58 -->

---

*Task IDs enable tracking and cross-referencing*
*Last updated: 2026-06-04*
