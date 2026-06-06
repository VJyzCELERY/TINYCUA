---
name: commit-cleanup
description: Commit cleanup command guidance — use when running /commit-cleanup to squash fixups, drop duplicates, and verify branch history
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/commit-cleanup.md
---

# Skill: commit-cleanup — Tidy Branch History

## What I do

Guide `/commit-cleanup` execution: inspect the current branch, run rebase preflight, squash fixup/squash commits, remove duplicate already-applied commits, and verify the final history.

## When to use me

Use this when the user invokes `/commit-cleanup` or asks to tidy commit history after a rebase.

Also load:

- `preflight` for `.agents/scripts/preflight-rebase.py`
- `git` for general safe rebase guidance

## How to use me

### 1. Run preflight

```bash
uv run python .agents/scripts/preflight-rebase.py --target main --list-commits
```

If it exits non-zero, read `.agents/scripts/preflight-rebase.py` and inspect its `<EOF_DESC>` usage block before continuing.

### 2. Inspect current history

```bash
git log --oneline --graph --all --decorate -15
```

Identify fixup/squash commits, duplicate commits already present in the target branch, and the intended final commit shape.

### 3. Clean only the current branch

- Squash only `fixup!`/`squash!` commits into their intended targets.
- Drop duplicate commits that are already applied to the target branch.
- Do not combine meaningful commits unless the user explicitly asks.

### 4. Verify

```bash
git log --oneline main..HEAD
git log --oneline --left-right main...HEAD --cherry-pick
```

Report what changed and the remaining unique commits.

## Common Pitfalls

- Do not rewrite protected branches such as `main` or `master`.
- Do not force-push without explicit user permission.
- Use `git push --force-with-lease`, never plain `--force`, if a rewritten branch must be pushed.
- Stop and ask the user before resolving conflicts or changing the intended commit structure.
