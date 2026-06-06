---
description: Verifies each finding against latest HEAD and unstaged changes — addressed, invalid, or still OPEN
subtask: true
---

Verify each finding against the current state: run the **How to Validate** command against the latest HEAD. This command does NOT reply to PR comments or update the remote — it only updates the local report. Use `review-update` to push changes to the PR.

> Load skill: review-core (for checking finding statuses)

**Query**: $1 (optional natural language query, focus, or explicit review file path. If not an explicit review path, default to `./reviews/REVIEW_{normalized_branch}.md`.)
**Focus Area (Optional)**: $2 (verify only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, verify ALL OPEN findings.

---

## Cross-Reference Review Log

Before verifying, check if a review log exists for this branch:

```bash
BRANCH=$(git branch --show-current)
LOG_PATH="./reviews/log/REVIEW_${BRANCH//\//_}.md"
if [ -f "$LOG_PATH" ]; then
    echo "Review log exists: $LOG_PATH"
fi
```

If the log exists, read it and note:
- **Previously deferred items**: If they reappear as OPEN in this review, flag them in the verification — they should be re-checked
- **Previously addressed items**: If they reappear, they may have regressed — flag for attention

## Pre-Flight: Capture current state

> Load _common-preflight.md
> Load skill: gh (for gh.py — used for PR context metadata)

Run the preflight to get scope info (PR number, files changed, commit range). Staleness warnings do not stop this command — they mean the review report must be updated against the latest commit:

```bash
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

This captures:
- **Scope info**: PR number, files changed, commit range
- **Unstaged changes**: If present, also run validation commands against unstaged content to check if local edits have resolved the finding

If local is behind remote, sync first. Use fast-forward pull when possible. If the remote rebased/diverged, create a backup branch for local commits and stash dirty work before resetting to upstream, then proceed with verification. Do NOT stop for review staleness warnings.

---

## Instructions

1. **Read the Review**: Load the review report from `$REVIEW_FILE` (set to `./reviews/REVIEW_{normalized_branch}.md` by the common preflight). If it does not exist, stop and report that exact missing path; do not ask where the review file is.
2. **Run pre-flight checks**: Run the review preflight. If the local checkout is outdated, sync to the latest remote commit first. If the review commit range is stale, continue and validate against the latest commit.
3. **Capture current commit range**: Record the PR head at verification time:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   echo "Verifying PR #${PR_NUMBER}"
   ```
   Do NOT fetch PR info with `| head -N` or other truncation — you need the full output.

4. **Align Scope**: Check current branch and diff to identify stale findings (files outside current diff → INVALID)
5. **Filter Findings**: If `$2` is provided, only verify those findings
6. **Verify Each Finding**: For each OPEN finding:
   - Execute the "How to Test/Validate" command (use `uv run` for Python)
   - Determine status:
     - Command succeeds → **ADDRESSED**
     - Stale/no longer relevant → **INVALID**
     - Still fails → **OPEN**
   - Document evidence
7. **MANDATORY — Update the Commit Range**: After verification, update the review report's Commit Range to the current HEAD so future staleness detection works correctly:
   ```bash
   uv run python .agents/scripts/update-commit-range.py "$REVIEW_FILE"
   ```
   This is REQUIRED. Without this, staleness detection will always report stale on subsequent runs because the old commit range is never refreshed.

## Status Definitions

- **ADDRESSED**: Issue fixed (validation passes)
- **INVALID**: No longer relevant — including stale findings outside current diff
- **OPEN**: Issue still exists

## Required Context

- Preflight: preflight-review.py
- Skills: review-core
- Rules: 004-review-standards.md
- Templates: none
- Mutates files: yes
- Mutates git history: no
- Mutates remote: no (local-only)
- Requires user confirmation: no

## Important

- Run actual validation commands — don't just assume
- Document evidence from command output
- Do NOT rewrite finding content — only update statuses and validation log
- This command is **local-only** — it does NOT reply to PR comments or resolve threads on GitHub. Use `review-update` to push status changes to the remote PR.
- **MUST update Commit Range** after verifying (step 7) — future staleness detection depends on it
- If review commit range is stale, this command updates the review report by validating every applicable finding against the latest commit and refreshing `**Commit Range**`.
- **Do NOT truncate `gh.py` output** when gathering PR info — never pipe through `head`, `tail`, or similar. You need the full output to get all metadata including commit range and body.
- Do not ask where the review file is. Default to `./reviews/REVIEW_{normalized_branch}.md`.
