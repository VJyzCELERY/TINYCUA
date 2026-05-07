# Skill: GitHub Review Workflow via `gh`

## Golden Rule: Use Temp Files + REST API

**Never pass review body content directly in bash.** `gh pr review --body` and `gh pr edit --body` use a deprecated GraphQL API that may fail silently.

Instead, use `gh api` REST endpoints with temp files:

1. Write the content to a temporary file under `./tmp/`
2. Pass it via `gh api ... -f body="$(cat <file>)"`
3. Delete the temp files after the command succeeds

### Detect Owner/Repo

```bash
OWNER_REPO=$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')
```

---

## Fetch PR Information

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
# All inline comments
gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/comments" --jq '.[] | {path, line, body, user: .user.login}'

# Review summaries (top-level)
gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" --jq '.[] | {id, state, body, user: .user.login}'

# Unresolved/CHANGES_REQUESTED reviews
gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" --jq '.[] | select(.state == "CHANGES_REQUESTED") | {id, body, user: .user.login}'

# Pending/OPEN review threads
gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/comments" --jq '.[] | select(.position != null) | {id, path, line, body}'
```

---

## Post a Review (Using REST API)

### Submit a Full PR Review with Inline Comments

```bash
# 1. Write the review body to a temp file
cat > ./tmp/gh-review-body.md << 'EOF'
## General Review Summary

[Overall assessment, key findings, scope notes]

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

# 3. Submit via REST API (stable, no GraphQL deprecation)
gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" \
  --method POST \
  -f body="$(cat ./tmp/gh-review-body.md)" \
  -f event="REQUEST_CHANGES" \
  --input ./tmp/gh-review-comments.json

# 4. Clean up
rm ./tmp/gh-review-body.md ./tmp/gh-review-comments.json
```

### Inline Comment Format

Each inline comment should include:
- **Issue**: What's wrong and where
- **Why**: Why it matters (readability, performance, security)
- **Suggestion**: Specific fix or pattern
- **How to Validate**: Command to verify the fix

### Approval

```bash
cat > ./tmp/gh-approve.md << 'EOF'
LGTM. [brief positive note]
EOF

gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" \
  --method POST \
  -f body="$(cat ./tmp/gh-approve.md)" \
  -f event="APPROVE"

rm ./tmp/gh-approve.md
```

### Comment Only

```bash
cat > ./tmp/gh-comment.md << 'EOF'
[General feedback]
EOF

gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" \
  --method POST \
  -f body="$(cat ./tmp/gh-comment.md)" \
  -f event="COMMENT"

rm ./tmp/gh-comment.md
```

---

## Reply to Review Threads

```bash
cat > ./tmp/gh-reply.md << 'EOF'
Addressed in commit <sha>.
EOF

gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/comments" \
  --method POST \
  --input ./tmp/gh-reply.md \
  -f in_reply_to=<comment-id>

rm ./tmp/gh-reply.md
```

## Resolve Review Threads

```bash
cat > ./tmp/gh-resolve.md << 'EOF'
Resolved in commit <sha>.
EOF

gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/comments/<comment-id>" \
  --method PATCH \
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

gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews/<review-id>/dismissals" \
  --method PUT \
  --input ./tmp/gh-dismiss.md

# Submit new review
cat > ./tmp/gh-re-review.md << 'EOF'
Re-review after fixes: [summary]
EOF

gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" \
  --method POST \
  -f body="$(cat ./tmp/gh-re-review.md)" \
  -f event="COMMENT"

rm ./tmp/gh-dismiss.md ./tmp/gh-re-review.md
```

---

## Check for Stale Reviews

```bash
LATEST_SHA=$(gh pr view "$PR_NUMBER" --json headRefOid --jq '.headRefOid')
REVIEW_SHA=$(gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" --jq '.[-1].commit_id')

if [ "$LATEST_SHA" != "$REVIEW_SHA" ]; then
  echo "Review is stale — new commits since last review"
fi
```

---

## Common Pitfalls

- **Always use `gh api` REST** for write operations — avoids GraphQL deprecation issues
- **`side: "RIGHT"`** is for the new version; `side: "LEFT"` for the old version
- **Validate JSON** before posting — use `cat ./tmp/file.json | python -m json.tool`
- **Detect `$OWNER_REPO`** dynamically — never hardcode it
- **Clean up**: Always `rm ./tmp/gh-*.md ./tmp/gh-*.json` after each operation
- Write temp files under `./tmp/` — it's gitignored
