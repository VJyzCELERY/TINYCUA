# Skill: review-post — Post Review as PR Inline Comments

## Purpose

Post a completed review report as a GitHub PR review with inline comments. Track URLs in the local report for future auto-reply/resolve.

## Prerequisites

- Load skill: preflight (for preflight-pr.py)
- Load skill: gh-pr-management (for gh.py — posting operations)

## Execution

1. Detect PR: `PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)`
2. Get PR diff: `gh pr diff "$PR_NUMBER"` (map finding locations to diff lines)
3. Build review body + inline comments JSON in `./tmp/`
4. Post: `uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/review-body.md ./tmp/review-comments.json --event REQUEST_CHANGES`
5. Fetch posted comments to get URLs: `uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER"`
6. Update local review report with PR Comment URLs and PR Review URL

## Common Pitfalls

- Verify line numbers against current PR diff before posting
- CRITICAL/HIGH → REQUEST_CHANGES, MEDIUM/LOW → COMMENT
- Always update local report with PR URLs after posting
- Skip findings that can't be mapped to the diff
