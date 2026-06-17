# Tasks: TinyCUA Actionable Runtime Traceability

Implementation tasks for node-prefixed traceability, real action execution, task
tree display, and in-memory session continuation.

## TDD Phase

- [x] Write transcript stream event tests <!-- id: 0 -->
- [x] Write task-tree text rendering tests <!-- id: 1 -->
- [x] Write default action tool exposure and SearXNG tests <!-- id: 2 -->
- [x] Write deterministic workspace action execution tests <!-- id: 3 -->
- [x] Write in-memory session continuation tests <!-- id: 4 -->

## Implementation Phase

- [x] Add node/tool transcript event helpers <!-- id: 5 -->
- [x] Add readable task-tree renderer and loop API <!-- id: 6 -->
- [x] Add SearXNG web search native tool <!-- id: 7 -->
- [x] Enable workspace native and web search tools by default <!-- id: 8 -->
- [x] Record action tool results/artifacts into task state <!-- id: 9 -->
- [x] Update notebook/CLI to display transcript, task tree text, tool results, and artifacts <!-- id: 10 -->

## Testing Phase

- [x] Run targeted unit/integration tests <!-- id: 11 -->
- [x] Run broad deterministic TinyCUA suite: `184 passed, 2 warnings in 6.94s` <!-- id: 12 -->
- [ ] Run live local LLM app-creation/manual acceptance <!-- id: 13 -->

## Verification Phase

- [x] Verify no files under `src/tinycua-sdk/` were modified <!-- id: 14 -->
- [x] Verify workspace confinement still rejects out-of-workspace paths via existing native tool suite <!-- id: 15 -->
- [ ] Verify notebook shows actual task tree/action evidence in live/manual app-creation flow <!-- id: 16 -->

---

*Task IDs enable tracking and cross-referencing*
*Last updated: 2026-06-15*
