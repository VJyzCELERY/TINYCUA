---
name: review-pr
description: Post, update, and fetch PR reviews with inline comments
license: MIT
compatibility: opencode
metadata:
  type: command-skill
---

# Skill: review-pr — PR Review Operations

## Purpose

Post completed reviews as GitHub PR inline comments, update existing reviews after fixes, and fetch unresolved PR comments into local review files.

## Prerequisites

- Load skill: preflight (for preflight-pr.py)
- Load skill: gh (for gh.py — all posting/fetching operations)

## Execution

### Post review
1. Detect PR: `PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py)`
2. Get PR diff: `gh pr diff "$PR_NUMBER"` (map finding locations to diff lines)
3. Read Overall Assessment from report header → determines review event
4. Build inline comments JSON in `./tmp/`
5. Post: `uv run python .agents/scripts/gh.py post review "$PR_NUMBER" ./tmp/body.md ./tmp/comments.json --event "$EVENT"`
6. Fetch posted comments, update local report with PR Comment URLs

### Update review
1. Read updated report, detect PR, fetch existing comments
2. For each finding: match to PR comment, post reply, resolve if addressed
3. Post summary comment after all updates

### Fetch comments
1. Detect PR, fetch unresolved comments via gh.py
2. Compile findings using `.agents/templates/REVIEW-template.md`
3. Write report to `./reviews/REVIEW_{name}_fetched.md`

## Event mapping
| Assessment | Event |
|-----------|-------|
| Approved / Approved With Recommendation | APPROVE |
| Change Requested / Blocked | REQUEST_CHANGES |

## Common Pitfalls
- Always verify line numbers against current PR diff before posting
- Always update local report with PR URLs after posting
- Only fetch unresolved comments — skip RESOLVED or OUTDATED
- New findings should use review-post instead of review-update
