---
description: Creates or updates issue-linked single or stacked pull requests
subtask: true
---

# Create PR

**Query**: `$1` optional `OWNER/REPO#NUMBER` or `local:<lower-kebab-id>`. **Mode**: `$2` `single` (default) or `full stack`.

Read root `AGENTS.md`, rule `006-commits-and-prs.md`, `_common-github-ownership.md`, the `gh` skill, `.agents/templates/PR-body.md`, and issue state. For `local:<lower-kebab-id>`, run `uv run python .agents/scripts/local_issue.py validate <lower-kebab-id>` from its recorded worktree; it must be `reviewed` before promotion, and a verified promotion record supplies its remote identity on a later resume. If `$1` is omitted, resolve a remote target with `uv run python .agents/scripts/workflow_state.py resolve-active --format json`; otherwise run `uv run python .agents/scripts/workflow_state.py show OWNER/REPO#NUMBER --format json` for a remote target. Re-fetch the open, non-roadmap, non-`spec`-labelled issue and existing PRs before planning. Use the canonical issue URL as `$TARGET`, then acquire it from the primary checkout:

```bash
PRIMARY=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
TARGET_RESULT=$(cd "$PRIMARY" && uv run python .agents/scripts/resolve-target-worktree.py "$TARGET")
```

Require one returned worktree path for the resolved target, then perform every branch, state, temporary-body, push, and PR operation from that returned worktree.

For a local target, validate its complete reviewed bundle before promotion. Promotion is the only remote mutation allowed for an unpromoted bundle: create or reuse one remote primary issue from `draft.md`, publish the same validated planning documents through the indexed Specs protocol, and verify the exact `Spec(#<primary-number>): <primary-title>` title and canonical comment URLs. Write the verified mapping to `./tmp/local-promotion.json`, then record it with `uv run python .agents/scripts/local_issue.py promote <lower-kebab-id> --mapping ./tmp/local-promotion.json`; it initializes normal remote workflow state only from that mapping. Before any `git push`, PR create/update, ownership claim, or `Delivery PR` marker write, only a promoted bundle may proceed. An unpromoted, incomplete, malformed, unreviewed, or conflicting local bundle stops before those delivery mutations. A previously promoted bundle reuses its validated mapping; remote-first targets retain the existing path.

For `single`, create or update the PR for the recorded/current branch against its actual base. For `full stack`, read validated lifecycle/branch state and create or update every cumulative branch PR in order, with each PR based on its immediate predecessor. Refuse an incomplete or ambiguous stack.

Prepare one filled PR body per branch under `./tmp/`. After promotion, render `Specs: #<number>` plus **Spec**, **Design**, **Implementation Plan**, and **Tasks** links copied only from the validated `workflow_state.specs.documents` URLs; never use caller-supplied, guessed, or fetched alternate URLs. Stacked PRs reuse the same references. An unpromoted local profile cannot retain repository-relative artifact references for delivery. The final PR alone contains `Closes OWNER/REPO#NUMBER` and `Closes #<Specs number>` while retaining the canonical Specs links; every earlier stacked PR contains `Refs OWNER/REPO#NUMBER` and `Refs #<Specs number>` and never `Closes`. Include stack order and neighboring PR links where applicable. Titles follow the commit format.

Preview all branch/base pairs, pushes, titles, bodies, authenticated login, ownership claims, and create/update operations before mutation. Ask one fresh permission for the exact push batch and execute only after approval. Then ask separate fresh permission for the exact GitHub write batch; create with `gh pr create --repo OWNER/REPO --title <title> --body-file <body-file> --head <branch> --base <branch> --draft`. For an existing PR, compare the fetched title and body with the rendered values and skip the write when both are unchanged. Otherwise write only the changed `title` and/or `body` keys to `./tmp/pr-metadata.json`, require a JSON object with a nonempty string title when present and a string body when present, preview it, then run `gh api --method PATCH repos/OWNER/REPO/pulls/<pr> --input ./tmp/pr-metadata.json`. Inherited `/goal` authorization covers only this previewed batch; standalone invocations retain both permissions. Verify new PRs are drafts and existing readiness is unchanged. Claim every returned PR through `_common-github-ownership.md`, preserving existing assignees, then remove generated body and payload files after success or failure.

For a standalone metadata-only correction, use the same fetched comparison and file-backed REST update, then verify metadata and unchanged readiness.

After each successful create or update, fetch the PR and verify head, base, issue linkage, and body. Record every verified PR, in stack order, with `uv run python .agents/scripts/workflow_state.py set-pr OWNER/REPO#NUMBER <number> --url <url> --head <head> --base <base> --format json`; this preserves partial progress for either single or full-stack resume. After the verified final PR, the remote profile re-fetches the Specs issue, replaces or appends its single `Delivery PR: <url>` marker with the verified final PR URL while preserving `Primary Issue` and the indexed Documents block, writes the changed body to `./tmp/specs-delivery.json`, and runs `gh api --method PATCH repos/OWNER/REPO/issues/<Specs number> --input ./tmp/specs-delivery.json`; skip an unchanged marker and verify it after the write. Only when the requested set is complete, read the current workflow phase. For initial delivery, run `uv run python .agents/scripts/workflow_state.py transition OWNER/REPO#NUMBER pr_open --status active --clear-pending-action --format json`. When the current phase is `reviewing`, preserve `reviewing` and clear delivery state with `uv run python .agents/scripts/workflow_state.py transition OWNER/REPO#NUMBER reviewing --status active --clear-pending-action --format json`; never transition backward from `reviewing` to `pr_open`.

## Required Context

- Root `AGENTS.md`; commit/PR rule; `gh` skill; PR template; workflow and optional stack state.

## Mutations

- Confirmed pushes, confirmed PR create or update writes, temporary PR bodies, and ignored workflow state. No commits or history rewrites.

## Confirmation

- Preview first. Outside inherited `/goal` authorization, push permission and remote write permission are separate and fresh; partial approval authorizes only the named batch.

## Failure

- Stop on dirty/uncommitted content, missing remote base, stale/diverged state, malformed stack, duplicate PRs, invalid template body, bad issue linkage, denied permission, or partial remote failure. Record only verified PRs and report the safe resume point.
