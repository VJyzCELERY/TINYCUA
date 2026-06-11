## Summary

### Spec / Design References

Resolve paths via: `uv run python .agents/scripts/preflight-pr-body.py --spec <path/to/spec.md> [--design <path/to/design.md>]`
The script outputs repo-root-relative paths (handles worktrees) and can auto-detect `design.md`.

- **Spec**: `.worktrees/feat_3.5-response-node/spec.md` — path from repository root to `spec.md`
- **Design**: `.worktrees/feat_3.5-response-node/design.md` — path from repository root to `design.md`

### Problem

Milestone 3.5 of the TinyCUA Prototype roadmap ([#87](https://github.com/VJyzCELERY/TINYCUA/issues/87)) requires implementing the full `TinyCUAResponseNode` — the terminal node in the TinyCUALoop that produces the final user-facing response. The current `ResponseNode` is a minimal stub that only captures LLM output content. It lacks context sufficiency analysis, InformationDigesterNode suspension, direct tool access for context gathering, consolidated continuation behavior, and terminal output normalization.

### Solution

This PR establishes the specification and design for `TinyCUAResponseNode` as described in the roadmap's milestone 3.5 contract:

- **Spec** (`spec.md`): Defines functional requirements, acceptance criteria, edge cases, and testing plan for the full ResponseNode implementation.
- **Design** (`design.md`): Provides architectural overview, component interactions, API contracts, implementation phases, and technical decisions for building the hardened terminal node.

Key design decisions documented:
- Three-phase execution: context sufficiency check → optional context gathering (digester/tools) → final response synthesis
- Leverages existing `suspend_current_and_prepend` queue suspension (M1.7) for digester path
- Uses same base toolset as TaskExecutor per architecture requirements
- Configurable context sufficiency thresholds via NodeConfig

### Scope

In scope:
- Spec defining TinyCUAResponseNode requirements (FR-001 through FR-009)
- Design covering architecture, data model, API contracts, and implementation phases
- Branch feat/3.5-response-node with worktree at .worktrees/feat_3.5-response-node/

Out of scope:
- Actual implementation (deferred to subsequent PRs)
- InformationDigesterNode changes (milestone 2.5, already implemented)
- Suspension path to InformationDigester (deferred to milestone 3.6 per roadmap)

## How to Test

1. Review the spec and design documents:
   ```bash
   cat .worktrees/feat_3.5-response-node/spec.md
   cat .worktrees/feat_3.5-response-node/design.md
   ```

2. Verify alignment with the design doc:
   ```bash
   cat src/tinycua/docs/design/loops/response.md
   ```

3. No code to test — this PR is spec/design only.

## Review Notes

- `spec.md` — Verify all functional requirements from the roadmap milestone 3.5 contract are captured (FR-001 through FR-009)
- `design.md` — Verify architectural decisions match the design doc at `src/tinycua/docs/design/loops/response.md`
- Verify that deferred work (milestone 3.6) is properly scoped out

## Related Issues

- [#87 - Roadmap: TinyCUA Prototype for WildClawBench Harness Evaluation](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 3.5: TinyCUAResponseNode
