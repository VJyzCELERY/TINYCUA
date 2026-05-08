---
description: Posts a review report as a PR review with inline comments and tracks URLs
subtask: true
---

Post a completed review report as a GitHub PR review with inline comments. After posting, update the local review report with the URLs of each posted comment.

**Query**: $1 (natural language query or review file path, e.g., "post the review from reviews/REVIEW-foo.md to PR #42" or simply "reviews/REVIEW-foo.md")
**PR Number (Optional)**: $2 (if not provided, detect from current branch or parse from query)

---

## Overview

This command reads a review report from `$1`, extracts each finding, and posts them as a structured PR review. After posting, it updates the local review report to track the URL of each comment so future commands (verify, clarify) can reply and resolve them automatically.

---

## Instructions

> Load skill: preflight (for preflight-pr.py)
> Load skill: gh-pr-management (for gh.py — all posting operations)

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
   - Build an inline comment with `path`, `line`, `side`, and `body`
   - Map the location to the current diff — if the line no longer exists, skip or adjust
5. **Post the review**:
   ```bash
   cat > ./tmp/review-body.md << 'BODY'
   [review summary from report]
   BODY
   cat > ./tmp/review-comments.json << 'COMMENTS'
   [JSON array of inline comments]
   COMMENTS
   uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/review-body.md ./tmp/review-comments.json --event REQUEST_CHANGES
   ```
6. **Fetch posted comments to get URLs**: After posting, fetch the PR comments:
   ```bash
   uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER"
   ```
   Match each comment to its finding by file path and line number.
7. **Update the local review report**: For each finding that was posted, append a `**PR Comment**` field:
   ```
   **PR Comment**: https://github.com/owner/repo/pull/<number>#discussion_r<comment-id>
   ```
   Also add a `**PR Review**` field for the overall review:
   ```
   **PR Review URL**: https://github.com/owner/repo/pull/<number>#pullrequestreview-<review-id>
   ```
   Save the updated review report. This links every finding to its PR comment so future commands can reply and resolve automatically.

---

## Inline Comment Format

```json
{
  "path": "src/file.py",
  "line": 42,
  "side": "RIGHT",
  "body": "**Issue**: [description]\n\n**Why**: [impact]\n\n**Suggestion**: [fix]\n\n**How to Validate**: [command]"
}
```

## Severity to Review Event Mapping

| Report Severity | Review Event |
|----------------|--------------|
| CRITICAL | `--request-changes` |
| HIGH | `--request-changes` |
| MEDIUM | `--comment` |
| LOW | `--comment` |

## Important

- Read `.agents/scripts/gh.py` usage before posting — all PR writes go through it
- Always verify line numbers against the current PR diff before posting
- **After posting, MUST update the local review report** with PR comment URLs — this enables automatic reply/resolve in review-verify and review-clarify
- Do NOT post reviews with empty inline comments — skip findings that can't be mapped to the diff
