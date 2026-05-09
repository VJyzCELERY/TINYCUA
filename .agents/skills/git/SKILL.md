---
name: git
description: Rebase branches, clean up commit history safely
license: MIT
compatibility: opencode
metadata:
  type: command-skill
---

# Skill: git — Rebase and Commit Cleanup

## Purpose

Safely rebase branches onto targets without duplicating commits, and clean up commit history by squashing fixups and removing duplicates.

## Prerequisites

- Load skill: preflight (for preflight-rebase.py)

## Execution

### Rebase
1. Run preflight: `uv run python .agents/scripts/preflight-rebase.py --target <target>`
2. Check for already-applied commits: `git log --oneline <target>..HEAD`
3. If no unique commits, exit early
4. Run: `git rebase <target>`
5. If conflicts: analyze, present to user, apply their decision
6. Force push: `git push --force origin <branch>`

### Commit cleanup
1. List recent commits: `git log --oneline -20`
2. Identify fixup/revert/duplicate commits
3. Squash using `git rebase -i` is NOT supported — use soft reset instead:
   - `git reset --soft <base>` + `git commit -m "message"`
4. Verify the cleaned history

## Common Pitfalls
- Never use `--reapply-cherry-picks` unless intentionally needed
- Always involve the user for conflict resolution — never auto-resolve
- Check commits are not already in target before rebasing
