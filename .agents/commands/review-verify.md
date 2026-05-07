---
description: Checks review findings — valid, invalid, addressed, or still OPEN
subtask: true
---

Check each finding in a review: determine if it has been properly addressed, is no longer relevant, or remains OPEN.

**Query**: $1 (natural language query or review file path, e.g., "verify the findings in reviews/REVIEW-foo.md" or simply "reviews/REVIEW-foo.md")
**Focus Area (Optional)**: $2 (verify only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, verify ALL OPEN findings.

---

## Role

`review-verify` checks each finding's status by running its validation command. It does NOT modify the finding's content or description — only its status.

---

## Instructions

1. **Read the Review**: Load the review report
2. **Check if review is stale**: Extract the **Commit Range** from the review header and compare to current HEAD:
   ```bash
   REVIEW_HEAD=$(grep 'Commit Range' "$REVIEW_FILE" | sed 's/.*\.\.\.//')
   CURRENT_HEAD=$(git rev-parse HEAD)
   if [ "$REVIEW_HEAD" != "$CURRENT_HEAD" ]; then
     echo "⚠ Review is stale — HEAD has moved since review was created."
     echo "  Review was on: $REVIEW_HEAD"
     echo "  Current HEAD:  $CURRENT_HEAD"
     echo "  New commits:"
     git log --oneline "$REVIEW_HEAD..$CURRENT_HEAD"
   fi
   ```
   If stale, warn the user via the question/ask tool before proceeding. Let them decide whether to continue or request a fresh review.
3. **Align Scope**: Check current branch and diff to identify stale findings (files outside current diff → INVALID)
3. **Filter Findings**: If `$2` is provided, only verify those findings
4. **Verify Each Finding**: For each OPEN finding:
   - Execute the "How to Test/Validate" command (use `uv run` for Python)
   - Determine status based on command output:
     - Command succeeds → **ADDRESSED**
     - Command fails but issue is stale/no longer relevant → **INVALID**
     - Command fails and issue persists → **OPEN**
   - Document evidence from the command output
5. **Update the Review Report**:
   - Append to the "Validation Log" section
   - Update each finding's status, validation date, and notes
6. **Save Changes**: Use Write to update the original review file

## Status Definitions

- **ADDRESSED**: Issue has been fixed (validation command passes)
- **INVALID**: Issue no longer exists or is no longer relevant — including stale findings outside current diff scope
- **OPEN**: Issue still exists and is valid

## Important

- Run actual validation commands — don't just assume
- Document evidence from command output
- Do NOT rewrite finding content — only update statuses and validation log
- Stale findings (files outside current diff) should be marked INVALID automatically
