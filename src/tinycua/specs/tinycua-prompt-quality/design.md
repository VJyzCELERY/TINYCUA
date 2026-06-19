# Design Document: TinyCUA Prompt Quality

**Spec**: ./spec.md
**Status**: In Progress
**Last Updated**: 2026-06-19

---

## Overview

Improve TinyCUA internal node prompts and retry framing across seven concerns: canonical mission propagation, tool-use clarity, internal-vs-user message distinction, architecture fidelity, role/scope clarity, tool-call correctness, and task-result quality. All changes are prompt-text and runtime-side metadata; no architecture, routing, node, or permission changes.

Research basis: hermes-agent (`/home/chris/.hermes/hermes-agent`) patterns — three-tier prompt separation, `[System: ...]` retry prefix convention, `GoalManager` goal re-injection, conditional tool guidance keyed on present tool names, and judge-style evidence requirements — adapted to TINYCUA's single-agent-internal-nodes model.

---

## Architecture

### Component Overview

```
DigestedInformation / raw user query
        |
        v  (TaskCreate populates root.metadata)
root task: metadata["mission"], metadata["inherited_constraints"]
        |
        v  (task_decompose propagates)
child task: metadata["inherited_constraints"]
        |
        v  (every worker-internal node renders)
## Mission block in continuation
        |
        v
TaskAnalyzer / TaskAssessor / TaskExecutor / ResultReviewer / ResultAggregation
```

### Affected Components

| Component | File | Change Type | Notes |
|-----------|------|-------------|-------|
| TaskCreate node | `loops/task_create.py` | Modified | Populate root `mission` after task_init via `parse_loop_result` hook |
| TaskDecompose tool | `tools/task_tools.py` | Modified | Propagate `inherited_constraints` to children |
| Worker-internal nodes | `loops/task_nodes.py` | Modified | Render `## Mission` block; tool guidance; scope boundary; reviewer instruction |
| QueryAnalyst node | `loops/query_analyst.py` | Modified | Tool guidance; proactive required-tool line; scope boundary |
| InformationDigester | `loops/information_digester.py` | Modified | Scope boundary (instruction text only) |
| Response node | `loops/response_node.py` | Modified | Scope boundary (instruction text only) |
| Node base | `loops/node.py` | Modified | `build_tool_system_prompt` becomes the per-node guidance hook point |
| Retry mixin | `loops/validation_retry_mixin.py` | Modified | `[System: ...]` framing; soft reviewer verification nudge |
| Orchestration mixin | `loops/orchestration_mixin.py` | Modified | Call soft reviewer nudge after validation passes |
| Tests | `tests/unit/` | Added/Modified | New tests + fix existing prompt-text assertions |

---

## Data Model

No `Task` dataclass schema change. New fields live in the existing free-form `Task.metadata` dict:

- `metadata["mission"]` (str): the canonical original request / goal. Set once at Task Creation. Immutable except `replan`.
- `metadata["inherited_constraints"]` (list[str]): hard constraints inherited from the parent (or from the digest at the root). Propagated to children on `task_decompose`.

These are additive and consistent with existing `metadata` usage (`analysis_effort_pass_limit`, `assessor_recovery`, `executor_partial_tool_results`, etc.).

---

## API / Interface Contracts

No public API changes. No new tools. No new nodes.

### Message Role Convention

| Message origin | Role | Prefix/Convention |
|---|---|---|
| External user input | `user` | plain content (no prefix) |
| Internal node handoff (NodeInput) | `assistant` | `continuation_role="assistant"` (existing) |
| Retry / validation correction | `user` | `[System: ...]` prefix (new) — provider alternation requires `user`, prefix marks internal origin |
| Tool result | `tool` | existing |

The `[System: ...]` prefix is a text convention (hermes pattern), not a new role. It distinguishes internal runtime directives from genuine user turns without breaking provider role-alternation rules.

### Error Handling

| Error Case | Handling | Notes |
|------------|----------|-------|
| Reviewer omits terminate after required work | Existing validation retry (unchanged behavior, new `[System: ...]` wording) | No crash |
| Reviewer approves file-artifact task without read-only verification | Soft transcript note (FR-009) | **No validation crash** — informational only |
| TaskCreate with no digest and no user query | `mission` set to empty string | Downstream renders empty `## Mission` (no-op) |

---

## Implementation Phases

### Phase A — Canonical mission & constraint propagation (Goals 1, 4, 5, 7b)

- [ ] A1: Populate `root.metadata["mission"]` + `inherited_constraints` in `TinyCUATaskCreateNode.parse_loop_result` from `DigestedInformation` or raw user query.
- [ ] A2: Propagate `inherited_constraints` in `TaskDecomposeTool.__call__` after `decompose_task`.
- [ ] A3: Add `_render_mission_block(session)` helper; render `## Mission` in TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, ResultAggregation continuations.
- [ ] A-tests: `test_task_create_mission.py`, `test_task_decompose_constraints.py`, `test_mission_rendering.py`.

### Phase B — Retry framing (Goal 3)

- [ ] B1: `_retry_prompt_for_llm` → `[System: {directive}]`; `_natural_retry_message` / `_retry_message_for_validation` build imperative directives directly.
- [ ] B-tests: `test_retry_prompt_framing.py`.

### Phase C — Tool clarity & scope boundaries (Goals 2, 5, 6)

- [ ] C1: Override `build_tool_system_prompt` per node with behavioral guidance keyed on present tool names.
- [ ] C2: Add proactive "Your final action MUST call `<tool>`" line to single-required-tool node instructions.
- [ ] C3: Add one-line scope boundary to each node instruction.
- [ ] C-tests: `test_tool_guidance_prompt.py`.

### Phase D — Reviewer quality (Goal 7a, no-crash)

- [ ] D1: Strengthen `_RESULT_REVIEWER_INSTRUCTION` with read-only verification evidence requirement.
- [ ] D2: Add `_maybe_warn_reviewer_no_verification` soft nudge called after validation passes in `_execute_node` / `_finalize_streamed_node`.
- [ ] D-tests: `test_reviewer_verification_nudge.py`.

### Phase E — Cleanup & verification

- [ ] E1: Fix existing tests broken by prompt-text changes.
- [ ] E2: Run full unit suite (`uv run pytest tests/unit/`).
- [ ] E3: Smoke test experiment 3 against local LLM server.

---

## Technical Decisions

1. **Decision**: Store `mission`/`inherited_constraints` in `Task.metadata`, not a new dataclass field.
   - **Reason**: Zero schema risk; `metadata` is already the extension point.
   - **Alternatives**: New `Task` field — rejected (schema change, serialization impact).

2. **Decision**: Retry uses `role:"user"` with `[System: ...]` prefix, not a true `system` role.
   - **Reason**: Mid-turn `system` messages break role alternation on OpenAI-compatible providers (LM Studio, Ollama, vLLM). Hermes uses the same prefix convention.
   - **Alternatives**: Custom `internal` role — rejected (breaks provider compat).

3. **Decision**: Reviewer verification is a soft transcript note, never a hard validation failure.
   - **Reason**: User requirement: no crashing failures. Hard fails risk reviewer loops.
   - **Alternatives**: Soft warning then hard fail — rejected by user.

4. **Decision**: `mission` is immutable except `replan`.
   - **Reason**: It is the original end goal; replan legitimately restructures the tree.
   - **Alternatives**: Fully immutable — rejected (replan needs revision authority).

5. **Decision**: Per-node tool guidance via `build_tool_system_prompt`, not a prose tool list.
   - **Reason**: SDK exposes native function-calling schemas via `tools=`; prose tool lists duplicate and invite hallucinated JSON. Guidance is behavioral ("prefer X over Y", "final action MUST call Z"), keyed on tool names present (hermes pattern).
   - **Alternatives**: List tools as prose — rejected (duplicates native schemas).

6. **Decision**: Defer progressive tool disclosure / `tool_search` bridge.
   - **Reason**: TINYCUA tool count is small; YAGNI until it exceeds a context threshold.
   - **Alternatives**: Implement now — rejected (over-engineering).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Prompts get too long | Low | Medium | Keep additions short; tested for presence not exact text |
| Reviewer still loops | Low | Medium | Soft nudge (no crash) + clearer terminate guidance; rerun experiment 3 |
| Existing tests break on prompt-text change | High | Low | Phase E explicitly fixes assertions; run full suite |
| `mission` empty when no digest | Low | Low | Falls back to raw user query; empty `## Mission` is a no-op |

---

## References

- Spec: `./spec.md`
- Hermes-agent research: prompt assembly (`agent/system_prompt.py`), retry framing (`agent/conversation_loop.py`), goal re-injection (`hermes_cli/goals.py`), conditional tool guidance (`agent/prompt_builder.py`), delegate constraint-carrying (`tools/delegate_tool.py`).
- TINYCUA architecture: `docs/architecture/overview.md`, `docs/design/README.md` (untouched).