---
description: Updates an existing PR review with follow-up comments and resolves addressed findings
subtask: true
---

Update an existing PR review with follow-up comments and resolve findings that have been addressed.

**Query**: $1 (natural language query or review file path, e.g., "update the PR review from reviews/REVIEW-foo.md" or simply "reviews/REVIEW-foo.md")
**PR Number (Optional)**: $2 (if not provided, detect from current branch or parse from query)


## Overview

After fixes have been implemented and validated, this command updates the PR review to reflect the new state: resolved findings get a follow-up comment and are marked resolved; findings that remain open get a follow-up comment requesting further changes.

---

## Instructions

1. **Read the updated review report**: Load the REVIEW-{name}.md file
2. **Detect PR**: If `$2` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/get-pr-number.py)
   ```
3. **Fetch existing review comments**: Get all current inline comments on the PR:
   ```bash
   gh api "repos/:owner/:repo/pulls/$PR_NUMBER/comments"
   ```
4. **Map findings to comments**: For each finding in the review report:
   - Find the matching review comment by path/line or issue code
   - Check the finding's **Status** (ADDRESSED, INVALID, or OPEN)
   - **If ADDRESSED or INVALID**: Post a reply resolving the thread:
     ```bash
     gh api -X POST "repos/:owner/:repo/pulls/$PR_NUMBER/comments" \
       -f body="✅ **Resolved**: [brief note on how it was fixed]" \
       -f in_reply_to=<comment-id>
     ```
   - **If still OPEN**: Post a reply noting it remains open:
     ```bash
     gh api -X POST "repos/:owner/:repo/pulls/$PR_NUMBER/comments" \
       -f body="❌ **Still open**: [note on what's still needed]" \
       -f in_reply_to=<comment-id>
     ```
5. **Post a summary comment**: Add a top-level review comment summarizing the update:
   ```bash
   gh pr review "$PR_NUMBER" --comment --body "$(cat <<'BODY'
   ## Review Update

   **N findings resolved**, **N still open**.

   See inline replies for details on each finding.
   BODY
   )"
   ```

---

## Finding Status Mapping

| Report Status | Action |
|--------------|--------|
| ADDRESSED | Reply with ✅ Resolved note |
| INVALID | Reply with explanation of why invalid |
| OPEN | Reply with ❌ Still open note + what's needed |

---

## Important

- Read `.agents/skills/gh-review/SKILL.md` before updating — it contains the full gh review workflow reference
- Find the original comment ID before replying — use `gh api` to list PR comments
- Only reply to threads that had inline comments in the original review
- New findings (not present in the original review) should use `review-post` instead
- After all findings are resolved, suggest using `gh pr review --approve` to approve
