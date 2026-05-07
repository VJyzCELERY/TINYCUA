# Skill: GitHub PR Management via `gh`

## Golden Rule: Always Use Temp Files for Body Content

**Never pass PR body content directly in bash.** Inline heredocs and string escaping cause frequent failures. Instead:

1. Write the content to a temporary `.md` file
2. Use `--body-file` or `--body "$(cat <file>)"` to pass it to `gh`
3. Delete the temp file after the command succeeds

```bash
# ✅ CORRECT - write body to temp file first
cat > ./tmp/pr-body.md << 'EOF'
## Summary

[content here]
EOF

gh pr create --title "type(scope): title" --body "$(cat ./tmp/pr-body.md)"
rm ./tmp/pr-body.md

# ❌ WRONG - inline heredocs in gh command break with complex content
gh pr create --title "..." --body "$(cat <<'EOF' ... EOF)"
```

---

## Create a PR

```bash
cat > ./tmp/pr-body.md << 'EOF'
## Summary
[content using .agents/templates/PR-body.md]
EOF

gh pr create \
  --title "type(scope): title" \
  --body "$(cat ./tmp/pr-body.md)"

rm ./tmp/pr-body.md
```

- Use `--base <branch>` to target a specific branch
- Use `--draft` to create as draft
- Always check `.agents/templates/PR-body.md` first for the body structure

## Update PR Body

```bash
cat > ./tmp/pr-body.md << 'EOF'
## Summary
[updated content]
EOF

gh pr edit <number> --body "$(cat ./tmp/pr-body.md)"
rm ./tmp/pr-body.md
```

## Add PR Comment

```bash
cat > ./tmp/pr-comment.md << 'EOF'
Your comment here — can include markdown, code blocks, etc.
EOF

gh pr comment <number> --body "$(cat ./tmp/pr-comment.md)"
rm ./tmp/pr-comment.md
```

## List PRs

```bash
gh pr list --head <branch> --state open --json number,headRefName,baseRefName,title
```

## Get PR Details

```bash
gh pr view <number> --json number,headRefName,baseRefName,title,body,comments,reviews
gh pr view <number> --json files --jq '.files[].path'   # list changed files
```

## PR Review with Inline Comments

```bash
# Write the review body to a temp file
cat > ./tmp/review-body.md << 'EOF'
## Summary
[review summary]
EOF

# Write inline comments to a temp JSON file
cat > ./tmp/review-comments.json << 'EOF'
[
  {"path": "file.py", "line": 10, "body": "**Issue**: ...\n\n**Suggestion**: ...", "side": "RIGHT"},
  {"path": "file.py", "line": 25, "body": "**Issue**: ...\n\n**Suggestion**: ...", "side": "RIGHT"}
]
EOF

# Submit review using temp files
gh pr review <number> \
  --request-changes \
  --body "$(cat ./tmp/review-body.md)" \
  --comments "$(cat ./tmp/review-comments.json)"

rm ./tmp/review-body.md ./tmp/review-comments.json
```

- Approve: `gh pr review <number> --approve --body "$(cat ./tmp/body.md)"`
- Comment only: `gh pr review <number> --comment --body "$(cat ./tmp/body.md)"`
- Request changes: `gh pr review <number> --request-changes --body "$(cat ./tmp/body.md)"`

**Inline comments via `--comments` use JSON array format.** Each item needs `path`, `line`/`startLine`, `body`, and `side` (`LEFT` for old diff, `RIGHT` for new diff).

## Resolve Review Threads

```bash
cat > ./tmp/resolve-comment.md << 'EOF'
Resolved in <commit>.
EOF

gh api -X POST "repos/:owner/:repo/pulls/<number>/comments/<comment-id>/replies" \
  --input ./tmp/resolve-comment.md
rm ./tmp/resolve-comment.md
```

## Common Pitfalls

- **Always use temp files** — never inline heredocs directly in `gh` commands
- **Don't** use `--body` with inline JSON for `--comments` — they must be separate
- **Don't** forget `side: "RIGHT"` for the new diff side
- **Do** write body to `./tmp/` to avoid cluttering the repo
- **Do** use `gh pr view <number> --json files --jq '.files[].path'` to get changed files
- **Do** clean up temp files after each command (`rm ./tmp/gh-*.md`)
- PR numbers can be obtained from `gh pr list --head <branch> --json number --jq '.[0].number'`
