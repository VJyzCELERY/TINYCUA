# Skill: GitHub Review Workflow via `gh`

## Golden Rule: Always Use Temp Files for Body Content

**Never pass review body content directly in bash.** Inline heredocs and string escaping in `gh pr review --body` cause frequent failures. Instead:

1. Write the content to a temporary `.md` file
2. Use `--body "$(cat <file>)"` and `--comments "$(cat <file>)"` to pass it to `gh`
3. Delete the temp files after the command succeeds

---

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
gh pr view "$PR_NUMBER" --json reviews --jq '.reviews[-1].state'
# Possible states: APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING
```

---

## Post a Review (Using Temp Files)

### Submit a Full PR Review with Inline Comments

```bash
# 1. Write the review body to a temp file
cat > ./tmp/gh-review-body.md << 'EOF'
## General Review Summary

[Overall assessment, key findings, scope notes, positive points]

### Key Findings
- Finding 1: [summary]
- Finding 2: [summary]
EOF

# 2. Write inline comments to a temp JSON file
cat > ./tmp/gh-review-comments.json << 'EOF'
[
  {
    "path": "src/file.py",
    "line": 42,
    "side": "RIGHT",
    "body": "**Issue**: [description]\n\n**Why**: [impact]\n\n**Suggestion**: [specific fix]\n\n**How to Validate**: [command]"
  }
]
EOF

# 3. Submit the review using temp files
gh pr review "$PR_NUMBER" \
  --request-changes \
  --body "$(cat ./tmp/gh-review-body.md)" \
  --comments "$(cat ./tmp/gh-review-comments.json)"

# 4. Clean up
rm ./tmp/gh-review-body.md ./tmp/gh-review-comments.json
```

### Inline Comment Format

Each inline comment in the JSON should include:
- **Issue**: What's wrong and where
- **Why**: Why it matters (readability, performance, security)
- **Suggestion**: Specific fix or pattern
- **How to Validate**: Command to verify the fix

### Approval

```bash
cat > ./tmp/gh-approve.md << 'EOF'
LGTM. [brief positive note about what looks good]
EOF

gh pr review "$PR_NUMBER" --approve --body "$(cat ./tmp/gh-approve.md)"
rm ./tmp/gh-approve.md
```

### Comment Only

```bash
cat > ./tmp/gh-comment.md << 'EOF'
[General feedback, questions, or observations]
EOF

gh pr review "$PR_NUMBER" --comment --body "$(cat ./tmp/gh-comment.md)"
rm ./tmp/gh-comment.md
```

---

## Reply to Review Threads

```bash
cat > ./tmp/gh-reply.md << 'EOF'
Addressed in commit <sha>. The fix uses X instead of Y.
EOF

gh api -X POST "repos/:owner/:repo/pulls/$PR_NUMBER/comments" \
  --input ./tmp/gh-reply.md \
  -f in_reply_to=<comment-id>
rm ./tmp/gh-reply.md
```

## Resolve Review Threads

```bash
cat > ./tmp/gh-resolve.md << 'EOF'
Resolved in commit <sha>.
EOF

gh api -X PUT "repos/:owner/:repo/pulls/$PR_NUMBER/comments/<comment-id>" \
  --input ./tmp/gh-resolve.md
rm ./tmp/gh-resolve.md
```

---

## Update Existing Review

```bash
# Dismiss a previous review
cat > ./tmp/gh-dismiss.md << 'EOF'
Code has been updated since this review.
EOF

gh api -X PUT "repos/:owner/:repo/pulls/$PR_NUMBER/reviews/<review-id>/dismissals" \
  --input ./tmp/gh-dismiss.md

# Submit new review
cat > ./tmp/gh-re-review.md << 'EOF'
Re-review after fixes: [summary of what changed and what's still pending]
EOF

gh pr review "$PR_NUMBER" --comment --body "$(cat ./tmp/gh-re-review.md)"
rm ./tmp/gh-dismiss.md ./tmp/gh-re-review.md
```

---

## Common Patterns

### Full Review Cycle

1. **Fetch**: `gh pr view` + `gh pr diff` to understand the PR
2. **Review**: Write review to temp files, submit with `gh pr review --request-changes`
3. **Update**: After fixes, write follow-up to temp file, submit with `gh pr review --comment`
4. **Approve**: Write approval to temp file, submit with `gh pr review --approve`

### Check for Stale Reviews

```bash
LATEST_SHA=$(gh pr view "$PR_NUMBER" --json headRefOid --jq '.headRefOid')
REVIEW_SHA=$(gh api "repos/:owner/:repo/pulls/$PR_NUMBER/reviews" --jq '.[-1].commit_id')

if [ "$LATEST_SHA" != "$REVIEW_SHA" ]; then
  echo "Review is stale — new commits since last review"
fi
```

---

## Common Pitfalls

- **Always use temp files** — never inline heredocs in `gh pr review` commands
- **`side: "RIGHT"`** is for the new version; `side: "LEFT"` for the old version
- **Validate JSON** before posting — use `echo '$comments_json' | jq .` to syntax-check
- **Rate limits**: `gh api` calls are rate-limited; batch where possible
- **Clean up**: Always `rm ./tmp/gh-*.md ./tmp/gh-*.json` after each operation
- Write temp files to `./tmp/` to avoid cluttering the repo
