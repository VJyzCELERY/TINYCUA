---
name: gh-review
description: Post, reply, resolve, and update PR reviews via gh.py and gh api
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/gh-review.md
---

# Skill: GitHub Review Workflow via `gh.py` (Primary) and `gh api` (Fallback)

## Golden Rule: Use `gh.py` First

**Always prefer `.agents/scripts/gh.py` for PR write operations.** It uses the stable REST API and handles temp file cleanup automatically. Only use raw `gh api` if `gh.py` doesn't support the operation you need.

Load the companion skill for more detail on gh.py operations:
> Load skill: gh-pr-management

```bash
# See all available subcommands
uv run python .agents/scripts/gh.py --help
```

Temp files go in `./tmp/` (gitignored) and are auto-deleted on success by gh.py.

---

## Fetch PR Information

### Basic PR Details (via gh CLI — read-only is fine)

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

### Fetch via gh.py

```bash
# Fetch PR info
uv run python .agents/scripts/gh.py fetch pr "$PR_NUMBER"

# Fetch unresolved review comments
uv run python .agents/scripts/gh.py fetch unresolved "$PR_NUMBER"

# Fetch all comments
uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER"

# Fetch a URL resource (raw content)
uv run python .agents/scripts/gh.py fetch url <url>
```

---

## Post a Review (Primary: gh.py)

### Submit a Full PR Review with Inline Comments

```bash
# 1. Write the review body to a temp file
cat > ./tmp/review-body.md << 'EOF'
## General Review Summary

[Overall assessment, key findings, scope notes]

### Key Findings
- Finding 1: [summary]
- Finding 2: [summary]
EOF

# 2. Write inline comments to a temp JSON file
cat > ./tmp/review-comments.json << 'EOF'
[
  {
    "path": "src/file.py",
    "line": 42,
    "side": "RIGHT",
    "body": "**Issue**: [description]\n\n**Why**: [impact]\n\n**Suggestion**: [specific fix]\n\n**How to Validate**: [command]"
  }
]
EOF

# 3. Submit via gh.py (auto-cleans temp files on success)
uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/review-body.md ./tmp/review-comments.json --event REQUEST_CHANGES
```

### Inline Comment Format

Each inline comment should include:
- **Issue**: What's wrong and where
- **Why**: Why it matters (readability, performance, security)
- **Suggestion**: Specific fix or pattern
- **How to Validate**: Command to verify the fix

### Approval

```bash
cat > ./tmp/review-approve.md << 'EOF'
LGTM. [brief positive note]
EOF

uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/review-approve.md --event APPROVE
```

### Comment Only

```bash
cat > ./tmp/review-comment.md << 'EOF'
[General feedback]
EOF

uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/review-comment.md --event COMMENT
```

---

## Reply to Review Threads

```bash
cat > ./tmp/reply.md << 'EOF'
Addressed in commit <sha>.
EOF

uv run python .agents/scripts/gh.py post reply "$PR_NUMBER" <comment-id> ./tmp/reply.md
```

## Resolve Review Threads

```bash
uv run python .agents/scripts/gh.py resolve "$PR_NUMBER" <comment-id>
```

---

## Post Single Inline Comment

```bash
cat > ./tmp/inline.md << 'EOF'
**Issue**: ...
**Suggestion**: ...
EOF

uv run python .agents/scripts/gh.py post inline "$PR_NUMBER" ./tmp/inline.md --path src/file.py --line 42
```

---

## Fallback: Raw `gh api` (when gh.py doesn't support the operation)

If gh.py doesn't support a specific operation, use `gh api` directly:

### Detect Owner/Repo

```bash
OWNER_REPO=$(gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"')
```

### Fetch Review Comments (raw)

```bash
# All inline comments
gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/comments" --jq '.[] | {path, line, body, user: .user.login}'

# Review summaries (top-level)
gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" --jq '.[] | {id, state, body, user: .user.login}'
```

### Submit via raw REST API

```bash
cat > ./tmp/gh-review-body.md << 'EOF'
[review content]
EOF

cat > ./tmp/gh-review-comments.json << 'EOF'
[{"path": "file.py", "line": 10, "body": "**Issue**: ...", "side": "RIGHT"}]
EOF

gh api "repos/$OWNER_REPO/pulls/$PR_NUMBER/reviews" \
  --method POST \
  -f body="$(cat ./tmp/gh-review-body.md)" \
  -f event="REQUEST_CHANGES" \
  --input ./tmp/gh-review-comments.json

rm ./tmp/gh-review-body.md ./tmp/gh-review-comments.json
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

rm ./tmp/gh-dismiss.md
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

- **Always use gh.py first** — only fall back to raw `gh api` if gh.py doesn't have the subcommand
- **`side: "RIGHT"`** is for the new version; `side: "LEFT"` for the old version
- **Validate JSON** before posting — use `cat ./tmp/file.json | python -m json.tool`
- **Detect `$OWNER_REPO`** dynamically — never hardcode it
- **Clean up**: If using raw gh api, always `rm ./tmp/gh-*.md ./tmp/gh-*.json` after
- gh.py auto-cleans temp files on success — no need to rm manually
- Write temp files under `./tmp/` — it's gitignored
