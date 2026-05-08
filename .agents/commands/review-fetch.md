---
description: Fetches unresolved PR review comments and generates a review report
subtask: true
---

Fetch unresolved comments and review requests from a GitHub PR and generate a structured review report.

**Query**: $1 (natural language query — specify the PR, e.g., "fetch reviews from PR #42" or simply "42")
**Output File (Optional)**: $2 (defaults to `./reviews/REVIEW-{name}-fetched.md`)


## Instructions

## Pre-Flight

Before fetching, load the relevant skills and run the PR pre-flight:

> Load skill: preflight (for preflight scripts)
> Load skill: gh-pr-management (for gh.py — fetching PR comments)

```bash
PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py "$1")
```

Also run the review pre-flight for scope context:

```bash
uv run python .agents/scripts/preflight-review.py --scope pr
```

---

1. **Detect PR**: If `$1` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   ```
2. **Fetch PR details** (including title, body, and spec references):
   ```bash
   gh pr view "$PR_NUMBER" --json title,body --jq '"TITLE: \(.title)\n\nBODY:\n\(.body)"'
   ```
3. **Fetch unresolved comments and reviews**:
   ```bash
   uv run python .agents/scripts/gh.py fetch unresolved "$PR_NUMBER"
   ```
4. **Check PR body/title compliance**: Before compiling findings, check if the PR body and title accurately describe the changes and reference any relevant specs. If the PR body or title need updating (e.g., stale description, missing spec references, misleading title), add a finding:
   ```markdown
   ### [FETCH-001] - [MEDIUM] - [PR body/title needs update]
   
   **Status**: OPEN
   
   **Severity**: MEDIUM
   
   [Explain what's wrong — e.g., PR title doesn't match changes, PR body lacks spec reference]
   
   **Location**: [PR #number]
   
   **Suggested Fix**:
   [What the title or body should say]
   ```
5. **Compile findings**: For each unresolved comment, extract:
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
