---
description: Fetches unresolved PR review comments and generates a review report
subtask: true
---

Fetch unresolved comments and review requests from a GitHub PR and generate a structured review report.

**PR Number (Optional)**: $1 (if not provided, detect from current branch)
**Output File (Optional)**: $2 (defaults to `./reviews/REVIEW-{name}-fetched.md`)

---

## Instructions

1. **Detect PR**: If `$1` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(gh pr list --head "$(git branch --show-current)" --state open --json number --jq '.[0].number')
   ```
2. **Detect owner/repo**:
   ```bash
   OWNER_REPO=$(gh repo view --json owner,name --jq '{owner: .owner.login, name: .name}' | jq -r '"\(.owner)/\(.name)"')
   ```
3. **Fetch PR details**:
   ```bash
   gh pr view "$PR_NUMBER" --json number,headRefName,baseRefName,title,author,state,reviews,comments,files
   ```
4. **Fetch inline review comments** (unresolved):
   ```bash
   gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/comments" --jq '.[] | select(.position != null)'
   ```
   Filter for unresolved threads (those without a resolution event).
5. **Fetch review summaries** (top-level review comments requesting changes):
   ```bash
   gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" --jq '.[] | select(.state == "CHANGES_REQUESTED")'
   ```
6. **Fetch pending/OPEN review threads**:
   ```bash
   gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/comments" --jq '.[] | select(.position != null) | {id: .id, path: .path, line: .line, body: .body, user: .user.login}'
   ```
7. **Compile findings**: For each unresolved comment, extract:
   - **Issue Code**: FETCH-001, FETCH-002, ...
   - **Severity**: Infer from review state (CHANGES_REQUESTED → HIGH, COMMENT → MEDIUM)
   - **Location**: The file path and line number from the comment
   - **Description**: The comment body
   - **Suggested Fix**: Extract from the comment body if present
   - **How to Validate**: Extract from the comment body if present
8. **Generate report**: Write the review report to `$2` (or default path) using the REVIEW-template.md structure

---

## Report Format

Use `.agents/templates/REVIEW-template.md` as the base structure. Each fetched comment becomes a finding:

```markdown
### [FETCH-001] - [HIGH] - [Issue summary]

**Status**: OPEN

**Severity**: HIGH

[Comment body — what the reviewer said]

**Location**: [file:line]

**Suggested Fix**:
[If the comment includes a suggestion, include it here]

**How to Validate**:
```bash
[If the comment includes validation steps, include them here]
```
```

---

## Important

- Read `.agents/skills/gh-review/SKILL.md` before fetching — it contains the full gh review workflow reference
- Only fetch unresolved comments (skip threads marked RESOLVED or OUTDATED)
- Distinguish between inline comments (file-specific) and top-level review summaries (general)
- Respect review state: CHANGES_REQUESTED reviews have actionable findings; COMMENTED reviews are informational
- If the PR has no unresolved comments, report that and exit cleanly
- Check `.agents/templates/REVIEW-template.md` for the expected output format
