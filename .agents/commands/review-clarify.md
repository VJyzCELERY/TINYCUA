---
description: Improves review precision — rewrites vague findings, adds context, sharpens validation commands
subtask: true
---

Improve the precision of a review: rewrite vague descriptions, add missing context, sharpen validation commands, and make every finding actionable. If findings are linked to PR inline comments, post a follow-up comment noting the clarification.

> Load skill: review-core (for improving finding precision)

**Query**: $1 (natural language query or review file path, e.g., "clarify the findings in reviews/REVIEW_foo.md" or simply "reviews/REVIEW_foo.md")
**Focus Area (Optional)**: $2 (clarify only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, clarify ALL OPEN findings.

---

## Pre-Flight Checks

> Load _common-preflight.md
> Load skill: gh (for gh.py — used for PR follow-ups)

```bash
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

---

## Instructions

1. **Read the Review**: Load the review report
2. **Run pre-flight checks**
3. **Capture current commit range**: Record the PR head at clarification time:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   HEAD_SHA=$(gh pr view "$PR_NUMBER" --json headRefOid --jq .headRefOid)
   BASE_SHA=$(gh pr view "$PR_NUMBER" --json baseRefOid --jq .baseRefOid)
   COMMIT_RANGE="$(git rev-parse --short "$BASE_SHA")...$(git rev-parse --short "$HEAD_SHA")"
   echo "Clarifying at: $COMMIT_RANGE"
   ```
4. **Filter Findings**: If `$2` is provided, only clarify those findings
5. **Clarify Each Finding**: For each finding, check and improve:

   | Aspect | Check | Fix |
   |--------|-------|-----|
   | **Location** | Is the file:line precise? | Add missing file/line references |
   | **Description** | Vague language? | Replace with specific observations |
   | **Why It Matters** | Missing impact? | Add: "This causes X because Y" |
   | **Suggested Fix** | Too generic? | Add concrete code example or pattern |
   | **How to Validate** | Missing or broken? | Add or fix (prefixed with `uv run`) |
   | **Severity** | Appropriate? | Adjust: CRITICAL/HIGH/MEDIUM/LOW |

6. **Update the Review Report**: Save the clarified version. Replace the `**Commit Range**` line in the report header with `**Commit Range**: ${COMMIT_RANGE}`.
7. **Post follow-up to PR if linked**: If a finding has a `**PR Comment**` URL, post a follow-up:
   ```bash
   cat > ./tmp/followup.md << 'EOF'
   **Clarified**: The finding has been updated for clarity.
   [summary of changes — added file:line, sharpened description, etc.]
   EOF
   uv run python .agents/scripts/gh.py post reply <pr> <comment-id> ./tmp/followup.md
   ```
   Extract `<pr>` and `<comment-id>` from: `https://github.com/owner/repo/pull/<pr>#discussion_r<comment-id>`
8. **Track the follow-up**: Add a `**PR Follow-up**` field with the reply URL
9. **Save Changes**: Use Write to update the original review file

## Important

- Do NOT change finding status — only improve clarity
- Keep the original intent — don't rewrite to say something different
- Add missing "How to Test/Validate" commands where absent
