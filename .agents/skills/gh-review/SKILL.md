# Skill: GitHub Review Workflow via `gh`

## Fetch PR Information

### Get PR Details

```bash
# Get PR number from branch name
PR_NUMBER=$(gh pr list --head "$(git branch --show-current)" --state open --json number --jq '.[0].number')

# View PR details
gh pr view "$PR_NUMBER" --json number,headRefName,baseRefName,title,body,author,state,mergeable,reviews,comments,files

# Get only changed files
gh pr view "$PR_NUMBER" --json files --jq '.files[].path'

# Get PR diff
gh pr diff "$PR_NUMBER"
```

### Fetch Review Comments

```bash
# Get all review comments on a PR (inline comments from reviews)
gh api "repos/:owner/:repo/pulls/$PR_NUMBER/comments" --jq '.[] | {path: .path, line: .line, body: .body, author: .user.login}'

# Get review summaries (top-level review comments)
gh api "repos/:owner/:repo/pulls/$PR_NUMBER/reviews" --jq '.[] | {id: .id, state: .state, body: .body, author: .user.login}'

# Get unresolved comments (reviews that requested changes)
gh api "repos/:owner/:repo/pulls/$PR_NUMBER/reviews" --jq '.[] | select(.state == "CHANGES_REQUESTED") | {id: .id, body: .body, author: .user.login}'

# Get pending/OPEN review threads
gh api "repos/:owner/:repo/pulls/$PR_NUMBER/comments" --jq '.[] | select(.position != null) | {id: .id, path: .path, line: .line, body: .body}'
```

### Check Review State

```bash
# Check if PR has been reviewed
gh pr view "$PR_NUMBER" --json reviews --jq '.reviews[-1].state'

# Possible states: APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING
```

## Post a Review

### Submit a Full PR Review

```bash
# Request changes with inline comments
gh pr review "$PR_NUMBER" \
  --request-changes \
  --body "$(cat <<'BODY'
## General Review Summary

[Overall assessment, key findings, scope notes]
BODY
)" \
  --comments "$(cat <<'COMMENTS'
[
  {
    "path": "src/file.py",
    "line": 42,
    "side": "RIGHT",
    "body": "**Issue**: [description]\n\n**Why**: [impact]\n\n**Suggestion**: [specific fix]\n\n**How to Validate**: [command]"
  }
]
COMMENTS
)"
```

### Inline Comment Format

Each inline comment should include:
- **Issue**: What's wrong and where
- **Why**: Why it matters (readability, performance, security)
- **Suggestion**: Specific fix or pattern
- **How to Validate**: Command to verify the fix

### Approval

```bash
# Approve the PR
gh pr review "$PR_NUMBER" --approve --body "LGTM. [brief positive note]"
```

### Comment Only

```bash
# Comment without explicit approval or changes request
gh pr review "$PR_NUMBER" --comment --body "Just some thoughts..."
```

## Reply to Review Threads

```bash
# Reply to a specific review comment thread
gh api -X POST "repos/:owner/:repo/pulls/$PR_NUMBER/comments" \
  -f body="Addressed in commit <sha>. The fix uses X instead of Y." \
  -f in_reply_to=<comment-id>
```

## Resolve Review Threads

```bash
# Mark a review thread as resolved
gh api -X PUT "repos/:owner/:repo/pulls/$PR_NUMBER/comments/<comment-id>" \
  -f body="Resolved in commit <sha>" \
  --field "event=RESOLVE"
```

Note: Not all comment types support direct resolution via API. Use `gh pr review` to re-review with updated status.

## Update Existing Review

```bash
# Dismiss a previous review and submit a new one
# First, dismiss the old review
gh api -X PUT "repos/:owner/:repo/pulls/$PR_NUMBER/reviews/<review-id>/dismissals" \
  -f message="Code has been updated since this review"

# Then submit a new review
gh pr review "$PR_NUMBER" --comment --body "Re-review after fixes: ..."
```

## Common Patterns

### Full Review Cycle

1. **Fetch**: `gh pr view` + `gh pr diff` to understand the PR
2. **Review**: `gh pr review --request-changes` with inline comments
3. **Update**: After fixes, `gh pr review --comment` with follow-up
4. **Approve**: `gh pr review --approve` when all issues resolved

### Check for Stale Reviews

```bash
# Get the latest commit SHA on the PR branch
LATEST_SHA=$(gh pr view "$PR_NUMBER" --json headRefOid --jq '.headRefOid')

# Get the commit SHA that the last review was on
REVIEW_SHA=$(gh api "repos/:owner/:repo/pulls/$PR_NUMBER/reviews" --jq '.[-1].commit_id')

if [ "$LATEST_SHA" != "$REVIEW_SHA" ]; then
  echo "Review is stale — new commits since last review"
fi
```

## Common Pitfalls

- **Inline comments require valid line numbers** in the current diff — use `gh pr diff` to verify
- **`side: "RIGHT"`** is for the new version; `side: "LEFT"` for the old version
- **Review JSON is fragile** — validate with `--jq` before posting
- **Rate limits**: gh api calls are rate-limited; batch where possible
- Use `:owner/:repo` pattern from `gh repo view --json owner,name --jq '{owner: .owner.login, name: .name}'`
