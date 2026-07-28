---
description: Creates or updates remote indexed Specs documents or explicit local planning artifacts
subtask: true
---

# Plan

**Query**: `$1` optional `OWNER/REPO#NUMBER`. **Context**: `$2` optional priorities.

Read root `AGENTS.md`, rules `001`, `005`, and `007`, and all four planning templates. A `local:<lower-kebab-id>` target uses its ignored local bundle and the four matching templates; run `uv run python .agents/scripts/local_issue.py validate <lower-kebab-id>`, work only from its returned recorded worktree/branch, validate all five bundle documents and resolve clarification markers, then run `uv run python .agents/scripts/local_issue.py transition <lower-kebab-id> planned`. Do not write remotely. For a remote target, if `$1` is omitted resolve it with `uv run python .agents/scripts/workflow_state.py resolve-active --format json`; otherwise run `uv run python .agents/scripts/workflow_state.py show OWNER/REPO#NUMBER --format json`. Re-fetch the open non-roadmap issue and use its canonical URL as `$TARGET`. From the primary checkout, acquire the target worktree:

```bash
PRIMARY=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
TARGET_RESULT=$(cd "$PRIMARY" && uv run python .agents/scripts/resolve-target-worktree.py "$TARGET")
```

Require one returned worktree path for the resolved target, then perform every state, artifact, and template operation from that returned worktree. The default profile is remote. Create the four complete documents from the templates under `./tmp/` and resolve every clarification marker. Preview the exact remote Specs mutations: ensure may create the `spec` label, create or reuse the Specs issue titled exactly `Spec(#<primary-number>): <primary-title>`, and link the primary issue; publication will create only missing canonical document comments, write the completed Specs index once, and edit only changed indexed comments. Require fresh remote-write confirmation unless inherited `--auto` authorizes the previewed batch. Use the indexed Specs recipe in the `gh` skill: exhaustive `gh api --paginate ... --jq '.[]'` NDJSON reads, transport-free `specs_validation.py` checks including the deterministic title, `--body-file` for comment creation, and `gh api --input` for generated update payloads. Verify each write and stable URL, record complete remote references with `workflow_state.py set-specs`, and remove all temporary documents and payloads after state is written. A changed record must use the next revision and retain its canonical index and document URLs; preserve any `Delivery PR: <url>` marker when rewriting the Specs issue body. `set-specs` is valid at every workflow phase and does not change phase, status, pending action, PRs, or review facts. Do not create local canonical planning paths in the remote profile.

An explicit ignored `.agents/local/planning-profile.json` containing `{"profile":"local"}` is reserved for development of this template repository. Only this local profile uses the prior issue-keyed `.agents/local/state/artifacts/` flow and `uv run python .agents/scripts/workflow_state.py set-artifacts OWNER/REPO#NUMBER --directory <directory> --spec <spec> --design <design> --plan <plan> --task <task> --format json`. A `local:<lower-kebab-id>` bundle has no remote identity and does not use `workflow_state.py`; it remains local until `/create-pr` records its verified promotion. For a remote target, after all records validate, transition to `planned` only from `branched` with `uv run python .agents/scripts/workflow_state.py transition OWNER/REPO#NUMBER planned --status active --clear-pending-action --format json`. At every later phase, record a changed Specs revision without transitioning backward or changing the current status. Do not change source code.

## Required Context

- Root `AGENTS.md`; rules `001-agent-behavior.md`, `005-project-structure.md`, `007-spec-design-standards.md`; issue/state; planning templates.

## Mutations

- Remote profile: may create the `spec` label and Specs issue, link the primary issue, create missing canonical comments, initialize one stable Specs index, edit changed indexed comments, and write Specs references and planning phase to ignored local state.
- Local profile: creates or updates only state artifacts `spec.md`, `design.md`, `implementation-plan.md`, and `task.md` in the issue's ignored artifact directory, plus artifact paths and planning phase in state.

## Confirmation

- Preview remote Specs mutations and require fresh remote-write confirmation immediately before them, except for inherited `--auto`. Ask separately when issue, project/subproject, or requirements are ambiguous. No Git action is permitted.

## Failure

- Stop on missing templates, issue/state conflict, closed/roadmap issue, unresolved clarification, or unsafe artifact path; do not invent requirements.
