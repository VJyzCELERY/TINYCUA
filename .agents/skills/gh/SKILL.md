---
name: gh
description: GitHub PR management and review operations via gh.py
license: MIT
compatibility: opencode
metadata:
  type: command-skill
---

# Skill: gh — GitHub PR and Review Operations

## Purpose

Manage GitHub PRs and reviews. All write operations go through `.agents/scripts/gh.py`. Only use raw `gh api` as fallback.

## Golden Rule: Use gh.py for ALL PR Operations

**Always prefer `.agents/scripts/gh.py` — even for read operations.** Only use raw `gh` CLI when gh.py doesn't support the operation you need.

```bash
# See all available subcommands
uv run python .agents/scripts/gh.py --help
```

Temp files go in `./tmp/` (gitignored). gh.py auto-cleans on success.

## Common Operations

### Fetch
```bash
uv run python .agents/scripts/gh.py fetch pr "$PR_NUMBER"      # PR details
uv run python .agents/scripts/gh.py fetch prs                   # List PRs (--head, --state, --base, --limit)
uv run python .agents/scripts/gh.py fetch repo                  # Repo info (owner, language, visibility)
uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER" # Inline comments + reviews
uv run python .agents/scripts/gh.py fetch unresolved "$PR_NUMBER" # Unresolved threads
```

### Post review
```bash
uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/body.md ./tmp/comments.json --event REQUEST_CHANGES
uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/body.md --event APPROVE
uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/body.md --event COMMENT
```

### Reply and resolve
```bash
uv run python .agents/scripts/gh.py post reply "$PR_NUMBER" <comment-id> ./tmp/reply.md
uv run python .agents/scripts/gh.py resolve "$PR_NUMBER" <comment-id>
uv run python .agents/scripts/gh.py post inline "$PR_NUMBER" ./tmp/inline.md --path src/file.py --line 42
```

### Update
```bash
uv run python .agents/scripts/gh.py update title "$PR_NUMBER" "New Title"
uv run python .agents/scripts/gh.py update body "$PR_NUMBER" ./tmp/new-body.md
```

### Create PR
1. Read `.agents/templates/PR-body.md` and fill in all sections based on the spec/design/changes
2. Write the filled body to `./tmp/pr-body.md`
3. Create:
```bash
uv run python .agents/scripts/gh.py create "Title" ./tmp/pr-body.md [--head <branch>] [--base <branch>]
```
4. Verify body was set: `uv run python .agents/scripts/gh.py fetch pr <pr-number>`

### Run any gh command (wildcard)
```bash
# Auto-formats JSON output to markdown, raw output passthrough for non-JSON
uv run python .agents/scripts/gh.py cmd pr view 10 --json number,title,state
uv run python .agents/scripts/gh.py cmd pr diff 10
uv run python .agents/scripts/gh.py cmd pr list --head my-branch
uv run python .agents/scripts/gh.py cmd repo view --json name,description
```

## Common Pitfalls
- **Always use gh.py first** — even for read operations. Only fall back to raw `gh` CLI if gh.py doesn't have the subcommand
- **Retry on transient/syntax errors** — if gh.py fails with a syntax/transient error, retry once after a 2-second pause before falling back to raw `gh`
- **Check gh.py --help** before using raw `gh` — the operation you need may already be covered
- **`gh pr diff` is OK** — gh.py doesn't have a diff subcommand yet
- **Unknown commands** — if gh.py doesn't support an operation, it tells you to use raw `gh` CLI. Just run the command it shows.
- **`side: "RIGHT"`** for new version, **`side: "LEFT"`** for old version
- **Validate JSON** before posting: `cat ./tmp/file.json | python -m json.tool`
- Write temp files under `./tmp/` — it's gitignored
