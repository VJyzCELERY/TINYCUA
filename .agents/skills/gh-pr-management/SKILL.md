# Skill: GitHub PR Management via `gh.py`

## Golden Rule: Use `.agents/scripts/gh.py`

All PR operations should use `.agents/scripts/gh.py` — a Python script that uses the stable REST API instead of the deprecated GraphQL API that `gh pr edit --body` relies on.

Temp files go in `./tmp/` (gitignored) and are auto-deleted on success.

---

## Create a PR

```bash
cat > ./tmp/pr-body.md << 'EOF'
[content using .agents/templates/PR-body.md]
EOF

uv run python .agents/scripts/gh.py create "type(scope): title" ./tmp/pr-body.md --head <branch> --base main

# ./tmp/pr-body.md is auto-deleted on success
```

- Add `--draft` for draft PRs
- Change `--base` to target a different branch
- Always check `.agents/templates/PR-body.md` first

## Update PR Body

```bash
cat > ./tmp/pr-body.md << 'EOF'
[updated content]
EOF

uv run python .agents/scripts/gh.py update body <pr> ./tmp/pr-body.md
```

## Add PR Comment

```bash
cat > ./tmp/pr-comment.md << 'EOF'
[comment content]
EOF

uv run python .agents/scripts/gh.py post comment <pr> ./tmp/pr-comment.md
```

## List / Get PR Details

```bash
gh pr list --head <branch> --state open --json number,headRefName,baseRefName,title
uv run python .agents/scripts/gh.py fetch pr <pr>
```

## PR Review with Inline Comments

```bash
# Write review body
cat > ./tmp/review-body.md << 'EOF'
## Summary
[review summary]
EOF

# Write inline comments JSON
cat > ./tmp/review-comments.json << 'EOF'
[
  {"path": "file.py", "line": 10, "body": "**Issue**: ...", "side": "RIGHT"}
]
EOF

# Post review with inline comments
uv run python .agents/scripts/gh.py post review <pr> ./tmp/review-body.md ./tmp/review-comments.json --event REQUEST_CHANGES

# Both temp files are auto-deleted on success
```

- `--event APPROVE` — approve
- `--event COMMENT` — comment only  
- `--event REQUEST_CHANGES` — request changes

## Reply to a Review Thread

```bash
cat > ./tmp/reply.md << 'EOF'
Addressed in commit <sha>.
EOF

uv run python .agents/scripts/gh.py post reply <pr> <comment-id> ./tmp/reply.md
```

## Resolve a Review Thread

```bash
uv run python .agents/scripts/gh.py resolve <pr> <comment-id>
```

## Post Single Inline Comment

```bash
cat > ./tmp/inline.md << 'EOF'
**Issue**: ...
**Suggestion**: ...
EOF

uv run python .agents/scripts/gh.py post inline <pr> ./tmp/inline.md --path src/file.py --line 42
```

## Common Pitfalls

- Always use `gh.py` for write operations — `gh pr edit` uses deprecated GraphQL
- Temp files in `./tmp/` are auto-cleaned on success; no need to `rm` manually
- Use `gh.py fetch unresolved <pr>` to see outstanding review threads
- PR numbers from: `gh pr list --head <branch> --json number --jq '.[0].number'`
