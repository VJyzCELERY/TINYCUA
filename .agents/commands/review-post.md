---
description: Posts a review report as a PR review with inline comments
subtask: true
---

Post a completed review report as a GitHub PR review with inline comments.

**Query**: $1 (natural language query or review file path, e.g., "post the review from reviews/REVIEW-foo.md to PR #42" or simply "reviews/REVIEW-foo.md")
**PR Number (Optional)**: $2 (if not provided, detect from current branch or parse from query)


## Overview

This command reads a review report from `$1`, extracts each finding, and posts them as a structured PR review using the GitHub CLI. Each finding becomes an inline comment on the relevant file + line, and the review summary becomes the top-level review body.

---

## Instructions

1. **Read the review report**: Load the REVIEW-{name}.md file
2. **Detect PR**: If `$2` is not provided, detect the PR number:
   ```bash
   PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)
   ```
3. **Get PR diff**: Download the PR diff to map line numbers:
   ```bash
   gh pr diff "$PR_NUMBER"
   ```
4. **Build review payload**: For each finding in the report:
   - Extract the file path and line number from the **Location** field
   - Build an inline comment with:
     - **path**: The file path
     - **line**: The line number in the new diff
     - **side**: `RIGHT` (new diff side)
     - **body**: A structured comment containing:
       - `**Issue**: [finding title / description]`
       - `**Why**: [impact / rationale]`
       - `**Suggestion**: [proposed fix]`
       - `**How to Validate**: [validation command]`
   - Map the location to the current diff — if the line no longer exists, skip or adjust
5. **Build the review summary**: Extract the **Summary** section from the report as the top-level review body
6. **Post the review**:
   ```bash
   gh pr review "$PR_NUMBER" \
     --request-changes \
     --body "$(cat <<'BODY'
   [review summary from report]
   BODY
   )" \
     --comments "$(cat <<'COMMENTS'
   [JSON array of inline comments]
   COMMENTS
   )"
   ```

---

## Inline Comment Format

Each inline comment in the `--comments` JSON must follow this structure:

```json
{
  "path": "src/file.py",
  "line": 42,
  "side": "RIGHT",
  "body": "**Issue**: [brief description]\n\n**Why**: [why it matters]\n\n**Suggestion**: [specific fix]\n\n**How to Validate**: [command to verify]"
}
```

## Review Body Format

The top-level review body should include:

```markdown
## General Review Summary

[Overall assessment — key findings, scope notes, positive points]

### Key Findings

- **[ISSUE-CODE-001]**: [1-line summary]
- **[ISSUE-CODE-002]**: [1-line summary]
```

## Severity to Review Event Mapping

| Report Severity | Review Event |
|----------------|--------------|
| CRITICAL | `--request-changes` |
| HIGH | `--request-changes` |
| MEDIUM | `--comment` |
| LOW | `--comment` |

If any finding is CRITICAL or HIGH, use `--request-changes`. If all findings are MEDIUM or LOW, use `--comment`.

---

## Important

- Read `.agents/skills/gh-review/SKILL.md` before posting — it contains the full gh review workflow reference
- Always verify line numbers against the current PR diff before posting
- Inline comments with invalid line numbers will be rejected by GitHub
- Use heredocs (`<<'BODY'`, `<<'COMMENTS'`) for multiline content
- Do NOT post reviews with empty inline comments — skip findings that can't be mapped to the diff
- After posting, record the review ID for future updates
