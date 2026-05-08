---
name: review-update
description: Update PR reviews after fixes — resolve addressed, reply on remaining
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/review-update.md
---

# Skill: review-update — Update PR Review After Fixes

## Purpose

Update an existing PR review after fixes: resolve addressed findings, reply to open threads, post summary.

## Prerequisites

- Load skill: preflight (for preflight-pr.py)
- Load skill: gh-pr-management (for gh.py — comment/reply/resolve)

## Execution

1. Read updated review report
2. Detect PR: `PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)`
3. Fetch existing comments: `uv run python .agents/scripts/gh.py fetch comments "$PR_NUMBER"`
4. For each finding: match to PR comment, post reply (resolved or still open), resolve if addressed
5. Post summary comment: `uv run python .agents/scripts/gh.py post comment "$PR_NUMBER" ./tmp/summary.md`

## Common Pitfalls

- ADDRESSED → reply + resolve, INVALID → reply + resolve, OPEN → reply (no resolve)
- Find original comment ID before replying
- New findings should use review-post instead
- After all resolved, post approval
