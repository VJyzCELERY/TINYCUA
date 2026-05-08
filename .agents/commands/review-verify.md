---
description: Checks review findings — valid, invalid, addressed, or still OPEN
subtask: true
---

Check each finding in a review: determine if it has been properly addressed, is no longer relevant, or remains OPEN. If findings are linked to PR inline comments, automatically reply with the verdict and resolve if appropriate.

> Load skill: review-verify (for checking finding statuses)

**Query**: $1 (natural language query or review file path, e.g., "verify the findings in reviews/REVIEW-foo.md" or simply "reviews/REVIEW-foo.md")
**Focus Area (Optional)**: $2 (verify only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, verify ALL OPEN findings.

---

## Pre-Flight: Commit Range Check

> Load skill: gh-pr-management (for gh.py — used for PR replies and resolution)

Before running validation, compare the review's commit range against current HEAD:

```bash
REVIEW_HEAD=$(grep 'Commit Range' "$REVIEW_FILE" | sed 's/.*\.\.\.//')
CURRENT_HEAD=$(git rev-parse HEAD)
if [ "$REVIEW_HEAD" == "$CURRENT_HEAD" ]; then
  echo "Review commit range matches HEAD — verifying against local codebase."
elif [ -n "$(git status --porcelain)" ]; then
  echo "Review HEAD differs from HEAD but unstaged changes exist — verifying local working tree (may differ from PR)."
else
  echo "Review is stale — HEAD has moved since review."
  echo "  Review was on: $REVIEW_HEAD"
  echo "  Current HEAD:  $CURRENT_HEAD"
  git log --oneline "$REVIEW_HEAD..$CURRENT_HEAD"
  echo "Ask user via question/ask tool (priority; inline if tool unavailable): continue with stale review or request fresh review?"
fi
```

---

## Instructions

1. **Read the Review**: Load the review report
2. **Run commit range check**: Compare review HEAD vs current HEAD
3. **Align Scope**: Check current branch and diff to identify stale findings (files outside current diff → INVALID)
4. **Filter Findings**: If `$2` is provided, only verify those findings
5. **Verify Each Finding**: For each OPEN finding:
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
7. **Update the Review Report**: Append to Validation Log, update statuses, add `**PR Reply**` URL if posted
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
