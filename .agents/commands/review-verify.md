---
description: Verifies each finding against latest HEAD and unstaged changes — addressed, invalid, or still OPEN
subtask: true
---

Verify each finding against the current state: run the **How to Validate** command against the latest HEAD (and also check if any unstaged local changes have resolved it). This command does NOT check staleness — it always verifies against whatever HEAD currently is. Findings outside the current diff are marked INVALID.

> Load skill: review-core (for checking finding statuses)

**Query**: $1 (natural language query or review file path, e.g., "verify the findings in reviews/REVIEW_foo.md" or simply "reviews/REVIEW_foo.md")
**Focus Area (Optional)**: $2 (verify only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, verify ALL OPEN findings.

---

## Cross-Reference Review Log

Before verifying, check if a review log exists for this branch:

```bash
LOG_PATH="./reviews/log/REVIEW_$(git branch --show-current | tr '/' '-').md"
if [ -f "$LOG_PATH" ]; then
    echo "Review log exists: $LOG_PATH"
fi
```

If the log exists, read it and note:
- **Previously deferred items**: If they reappear as OPEN in this review, flag them in the verification — they should be re-checked
- **Previously addressed items**: If they reappear, they may have regressed — flag for attention

## Pre-Flight: Capture current state

> Load _common-preflight.md
> Load skill: gh (for gh.py — used for PR replies and resolution)

Run the preflight to get scope info (PR number, files changed, commit range). Staleness warnings can be ignored — this command always verifies against whatever HEAD currently is:

```bash
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

This captures:
- **Scope info**: PR number, files changed, commit range
- **Unstaged changes**: If present, also run validation commands against unstaged content to check if local edits have resolved the finding

Then proceed with verification — do NOT stop for staleness warnings.

---

## Instructions

1. **Read the Review**: Load the review report
2. **Run pre-flight checks**: Run the review preflight — if warnings appear, handle staleness or unstaged changes before proceeding
3. **Capture current commit range**: Record the PR head at verification time:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   HEAD_SHA=$(gh pr view "$PR_NUMBER" --json headRefOid --jq .headRefOid)
   BASE_SHA=$(gh pr view "$PR_NUMBER" --json baseRefOid --jq .baseRefOid)
   COMMIT_RANGE="$(git rev-parse --short "$BASE_SHA")...$(git rev-parse --short "$HEAD_SHA")"
   echo "Verifying at: $COMMIT_RANGE"
   ```
4. **Align Scope**: Check current branch and diff to identify stale findings (files outside current diff → INVALID)
5. **Filter Findings**: If `$2` is provided, only verify those findings
6. **Verify Each Finding**: For each OPEN finding:
   - Execute the "How to Test/Validate" command (use `uv run` for Python)
   - Determine status:
     - Command succeeds → **ADDRESSED**
     - Stale/no longer relevant → **INVALID**
     - Still fails → **OPEN**
   - Document evidence
6. **Auto-reply to PR comments**: If a finding has a `**PR Comment**` URL:
    - **If ADDRESSED or INVALID**: Post reply + resolve:
      ```bash
      cat > ./tmp/reply.md << 'EOF'
      ✅ **Resolved**: [evidence note]
      EOF
      uv run python .agents/scripts/gh.py interact reply "$PR_COMMENT_URL" ./tmp/reply.md
      uv run python .agents/scripts/gh.py interact resolve "$PR_COMMENT_URL"
      ```
    - **If OPEN**: Post reply (no resolve):
      ```bash
      cat > ./tmp/reply.md << 'EOF'
      ❌ **Still open**: [what's needed]
      EOF
      uv run python .agents/scripts/gh.py interact reply "$PR_COMMENT_URL" ./tmp/reply.md
      ```
    Use the `**PR Comment**` URL directly as `$PR_COMMENT_URL` — no manual ID extraction needed.
7. **Update the Review Report**: Append to Validation Log, update statuses, add `**PR Reply**` URL if posted. Also update the report header with the commit range at verification time:
   - Replace the `**Commit Range**` line in the report header with `**Commit Range**: ${COMMIT_RANGE}`
8. **Save Changes**: Use Write to update the original review file

## Status Definitions

- **ADDRESSED**: Issue fixed (validation passes)
- **INVALID**: No longer relevant — including stale findings outside current diff
- **OPEN**: Issue still exists

## Important

- Run actual validation commands — don't just assume
- Document evidence from command output
- Do NOT rewrite finding content — only update statuses and validation log
- If a finding has a PR Comment URL, always post a reply — this closes the feedback loop
- Only resolve if ADDRESSED or INVALID — leave OPEN threads open
