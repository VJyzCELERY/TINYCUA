# Skill: GitHub PR Management via `gh`

## Create a PR

```bash
gh pr create --title "type(scope): title" --body "$(cat <<'EOF'
## Summary
...
EOF
)"
```

- Use `--base` to target a specific branch (defaults to the repo's default branch)
- Use `--draft` to create as draft
- Always use a heredoc (`<<'EOF'`) for the body to handle multiline content

## Update PR Body

```bash
gh pr edit <number> --body "$(cat <<'EOF'
## Summary
...
EOF
)"
```

- Or update from a file: `gh pr edit <number> --body "$(cat updated-body.md)"`

## Add PR Comment

```bash
gh pr comment <number> --body "Your comment here"
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
# Submit a review with inline comments
gh pr review <number> --body "Summary comment" --comments "$(cat <<'EOF'
[{"path": "file.py", "line": 10, "body": "Issue description", "side": "RIGHT"},
 {"path": "file.py", "line": 25, "body": "Another issue", "side": "RIGHT"}]
EOF
)" --request-changes

# Approve
gh pr review <number> --approve --body "LGTM"

# Comment only
gh pr review <number> --comment --body "General feedback"

# Request changes
gh pr review <number> --request-changes --body "Changes needed"
```

**Note**: Inline comments via `--comments` use JSON array format. Each item needs `path`, `line`/`startLine`, `body`, and `side` (`LEFT` for old diff, `RIGHT` for new diff).

## PR Review Templates

When creating a PR body, always check `.agents/templates/PR-body.md` first. The template includes sections for:
- Spec/Design references
- Problem & Solution
- Scope (in/out)
- Testing steps
- Review notes
- Related issues

## Resolve Review Threads

```bash
# Resolve a specific review thread
gh api -X POST "repos/:owner/:repo/pulls/<number>/reviews/<review-id>/threads" -f body="Resolved in <commit>" -f event="RESOLVE"
```

## Common Pitfalls

- **Don't** use `--body` with inline JSON for `--comments` — they must be separate
- **Don't** forget `side: "RIGHT"` for the new diff side
- **Do** use `<<'EOF'` heredocs for multiline bodies (single quotes prevent variable expansion)
- **Do** use `gh pr view <number> --json files --jq '.files[].path'` to get changed files for inline comment placement
- PR numbers can be obtained from `gh pr list --head <branch> --json number --jq '.[0].number'`
