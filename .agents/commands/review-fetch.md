---
description: Fetches unresolved PR review comments and generates a review report
subtask: true
---

Fetch unresolved comments and review requests from a GitHub PR and generate a structured review report.

**Query**: $1 (natural language query — specify the PR, e.g., "fetch reviews from PR #42" or simply "42")
**Output File (Optional)**: $2 (defaults to `./reviews/REVIEW-{name}-fetched.md`)


## Instructions

1. **Detect PR**: If `$1` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   ```
2. **Fetch PR details**:
   ```bash
   uv run python .agents/scripts/gh.py fetch pr "$PR_NUMBER"
   ```
3. **Fetch unresolved comments and reviews**:
   ```bash
   uv run python .agents/scripts/gh.py fetch unresolved "$PR_NUMBER"
   ```
4. **Compile findings**: For each unresolved comment, extract:
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
