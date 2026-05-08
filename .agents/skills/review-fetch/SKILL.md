---
name: review-fetch
description: Fetch unresolved PR review comments into a local structured report
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/review-fetch.md
---

# Skill: review-fetch — Pull PR Comments into Local Review

## Purpose

Fetch unresolved PR review comments and generate a structured local review report for tracking.

## Prerequisites

- Load skill: preflight (for preflight scripts)
- Load skill: gh-pr-management (for gh.py — fetching comments)

## Execution

1. Detect PR: `PR_NUMBER=$(uv run python .agents/scripts/preflight-pr.py "$1")`
2. Fetch PR details: `gh pr view "$PR_NUMBER" --json title,body`
3. Fetch unresolved comments: `uv run python .agents/scripts/gh.py fetch unresolved "$PR_NUMBER"`
4. Check PR body/title compliance against spec references
5. Compile findings using `.agents/templates/REVIEW-template.md`
6. Write report to `./reviews/REVIEW-{name}-fetched.md`

## Common Pitfalls

- Only fetch unresolved comments — skip RESOLVED or OUTDATED threads
- Distinguish inline comments vs top-level review summaries
- Check PR body/title for compliance and flag issues as findings
