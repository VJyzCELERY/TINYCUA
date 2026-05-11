---
description: Checks review findings — valid, invalid, addressed, or still OPEN
subtask: true
---

Check each finding in a review: determine if it has been properly addressed, is no longer relevant, or remains OPEN. If findings are linked to PR inline comments, automatically reply with the verdict and resolve if appropriate.

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

## Pre-Flight: Run Review Preflight

> Load _common-preflight.md
> Load skill: gh (for gh.py — used for PR replies and resolution)

Before running validation, run the review preflight to check if the review is stale:

```bash
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

This checks:
- **Staleness**: Whether HEAD has moved since the review was created
- **Unstaged changes**: Whether there are local modifications
- **Scope info**: PR number, files changed, commit range

If the preflight exits non-zero, read its warnings:
- If review is stale (HEAD moved): the findings should be re-verified against the current code. Ask user: continue with stale review or request a fresh review?
- If unstaged changes exist: verification may differ from the PR state — note this in the output
- If all clear: proceed with verification

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
     uv run python .agents/scripts/gh.py post reply <pr> <comment-id> ./tmp/reply.md
     uv run python .agents/scripts/gh.py resolve <pr> <comment-id>
     ```
   - **If OPEN**: Post reply (no resolve):
     ```bash
     cat > ./tmp/reply.md << 'EOF'
     ❌ **Still open**: [what's needed]
     EOF
     uv run python .agents/scripts/gh.py post reply <pr> <comment-id> ./tmp/reply.md
     ```
   Extract `<pr>` and `<comment-id>` from: `https://github.com/owner/repo/pull/<pr>#discussion_r<comment-id>`
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
