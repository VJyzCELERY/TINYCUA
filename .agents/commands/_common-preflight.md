Standard pre-flight invocation for review commands. Sets `REVIEW_FILE` for use by subsequent steps.

Derive the canonical review path from the current branch. Normalize branch slashes (`/`) to underscores (`_`). Do not ask the user where the review file is; default to this path unless the user explicitly supplied a different review file path.

```bash
BRANCH=$(git branch --show-current)
NORMALIZED_BRANCH=${BRANCH//\//_}
REVIEW_FILE="./reviews/REVIEW_${NORMALIZED_BRANCH}.md"
echo "[INFO] Review file: ${REVIEW_FILE}"
```

Before validating or updating a review report, make sure local code is at the latest remote commit. A stale local checkout means the review report must be updated against newer code, not that the user should be asked where to write it.

```bash
git fetch origin
STATUS=$(git rev-list --left-right --count HEAD...@{u} 2>/dev/null || true)
LEFT=${STATUS%%[[:space:]]*}   # local-only commits
RIGHT=${STATUS##*[[:space:]]}  # remote-only commits

if [ -n "$STATUS" ] && [ "${RIGHT:-0}" -gt 0 ] && [ "${LEFT:-0}" -eq 0 ]; then
  git pull --ff-only
elif [ -n "$STATUS" ] && [ "${RIGHT:-0}" -gt 0 ] && [ "${LEFT:-0}" -gt 0 ]; then
  # Remote likely rebased/diverged. Preserve local progress before aligning.
  TS=$(date +%Y%m%d%H%M%S)
  BACKUP_BRANCH="backup/${NORMALIZED_BRANCH}-${TS}"
  git branch "$BACKUP_BRANCH" HEAD || {
    echo "[WARN] Could not create backup branch; ask directly before destructive sync."
    exit 1
  }
  if [ -n "$(git status --porcelain)" ]; then
    git stash push -u -m "pre-review-sync ${BRANCH} ${TS}" || {
      echo "[WARN] Could not stash local changes; ask directly before destructive sync."
      exit 1
    }
  fi
  echo "[INFO] Backed up local commits to ${BACKUP_BRANCH}; stashed dirty work if present."
  git reset --hard @{u}
fi
```

Never discard progress during a diverged/rebased sync. Create a backup branch for local commits and stash dirty work first. If either backup step fails, ask directly in your normal response and stop before any destructive sync.

Then invoke the preflight:

```bash
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

- If preflight exits non-zero, read its warnings: staleness, unstaged changes, scope problems.
- For review-validate/review-verify/review-clarify and other report-updating commands, review staleness is not a blocker: validate/update the report against the latest commit and then refresh the commit range.
- Default review path: `./reviews/REVIEW_{normalized_branch}.md` (branch slashes → `_`).
- Common variants under `./reviews/remote/`: `REVIEW_{normalized_branch}_remote_{ts}.md`.
- Always load this module before running any review command.
