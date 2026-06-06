---
description: Improves review precision — rewrites vague findings, adds context, sharpens validation commands
subtask: true
---

Improve the precision of a review: rewrite vague descriptions, add missing context, sharpen validation commands, and make every finding actionable. If findings are linked to PR inline comments, post a follow-up comment noting the clarification.

> Load skill: review-core (for improving finding precision)

**Query**: $1 (optional natural language query, focus, or explicit review file path. If not an explicit review path, default to `./reviews/REVIEW_{normalized_branch}.md`.)
**Focus Area (Optional)**: $2 (clarify only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, clarify ALL OPEN findings.

---

## Pre-Flight Checks

> Load _common-preflight.md
> Load skill: gh (for gh.py — used for PR follow-ups)

```bash
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

If local is behind remote, sync first. Use fast-forward pull when possible. If the remote rebased/diverged, create a backup branch for local commits and stash dirty work before resetting to upstream. If the review commit range is stale, continue: this command updates the report text against the latest commit and refreshes the commit range.

---

## Instructions

1. **Read the Review**: Load the review report from `$REVIEW_FILE` (set to `./reviews/REVIEW_{normalized_branch}.md` by the common preflight). If it does not exist, stop and report that exact missing path; do not ask where the review file is.
2. **Run pre-flight checks**
3. **Capture current commit range**: Record the PR head at clarification time:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
    HEAD_SHA=$(uv run python .agents/scripts/gh.py cmd pr view "$PR_NUMBER" --json headRefOid --jq .headRefOid)
    BASE_SHA=$(uv run python .agents/scripts/gh.py cmd pr view "$PR_NUMBER" --json baseRefOid --jq .baseRefOid)
   COMMIT_RANGE="$BASE_SHA...$HEAD_SHA"
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

6. **Update the Review Report**: Save the clarified version. Run the commit range update script:
   ```bash
   uv run python .agents/scripts/update-commit-range.py "$REVIEW_FILE"
   ```
7. **Save Changes**: Use Write to update the original review file

## Required Context

- Preflight: preflight-review.py
- Skills: review-core, gh
- Rules: 004-review-standards.md
- Templates: none
- Mutates files: yes
- Mutates git history: no
- Mutates remote: no
- Requires user confirmation: no

## Important

- Do NOT change finding status — only improve clarity
- Keep the original intent — don't rewrite to say something different
- Add missing "How to Test/Validate" commands where absent
- Stale review commit range is not a blocker. Clarify against latest HEAD and update the report's commit range.
- Do not ask where the review file is. Default to `./reviews/REVIEW_{normalized_branch}.md`.
