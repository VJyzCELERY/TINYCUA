---
description: Safely rebases current branch onto target — avoids duplicating already-applied commits
subtask: true
---

Safely rebase the current branch onto a target branch (default: `main`) without duplicating commits that are already in the target history.

**Query**: $1 (natural language query — specify the target branch, e.g., "rebase onto main" or simply "main")
**Target Branch**: (parsed from query, defaults to `main`)

---

## Instructions

Read `.agents/skills/git-rebase/SKILL.md` before proceeding — it contains the full rebase workflow reference.

### 1. Check Current State

```bash
git log --oneline --graph --all --decorate -10
```

Understand where the current branch is relative to the target.

### 2. Check for Already-Applied Commits

Before rebasing, check if any commits on the current branch are already in the target:

```bash
# List commits on current branch NOT in target
UNIQUE_COMMITS=$(git log --oneline <target>..HEAD)

if [ -z "$UNIQUE_COMMITS" ]; then
  echo "No unique commits — branch is already up to date with target."
  exit 0
fi

# Check if any commits are already applied (cherry-picked or merged)
git log --oneline HEAD --not <target> --cherry-pick
```

Use `--cherry-pick` or `--fork-point` to detect commits that have already been applied elsewhere:

```bash
git merge-base --fork-point <target> HEAD
```

### 3. Perform the Rebase

```bash
git rebase <target>
```

- If `git rebase` warns about skipped commits (already applied), use `--reapply-cherry-picks` only if intentionally needed
- Normally, skipped commits should NOT be reapplied — they're already in the target

### 4. Handle Conflicts

```bash
git status                    # see which files conflict
# Fix conflicts manually
git add <resolved-file>       # stage resolved file
git rebase --continue         # continue rebase

# To abort:
git rebase --abort
```

### 5. Verify After Rebase

```bash
git log --oneline --graph --all --decorate -10
git diff <target>...HEAD --stat   # what changed vs target
```

### 6. Skip If No Change Needed

If after checking, the branch has no unique, meaningful commits (only merge commits or already-applied commits), exit cleanly:

```bash
if [ "$(git log --oneline <target>..HEAD | wc -l)" -eq 0 ]; then
  echo "Branch is already up to date — nothing to rebase."
  exit 0
fi
```

---

## Important

- Read the git-rebase skill before executing
- Always check for already-applied commits before rebasing
- Never use `--reapply-cherry-picks` unless you explicitly want duplicates
- After rebasing, force push is required (`git push --force origin <branch>`)
- If unsure, use `git rebase --abort` to return to original state
- Conflicts during rebase are normal — resolve them carefully, don't abort unless the conflicts are unresolvable

Begin by reading the git-rebase skill, then check the current branch state and rebase onto the target.
