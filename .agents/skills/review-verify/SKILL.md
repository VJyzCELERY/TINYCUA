---
name: review-verify
description: Execute validation commands to determine finding status — addressed, invalid, or open
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/review-verify.md
---

# Skill: review-verify — Check Each Finding's Status

## Purpose

Execute each finding's validation command to determine if it's ADDRESSED, INVALID, or still OPEN. Auto-reply to PR threads and resolve if appropriate.

## Prerequisites

- Load skill: gh-pr-management (for gh.py — replies and resolution)

## Execution

1. Check commit range staleness against current HEAD
2. For each OPEN finding: run the validation command (use `uv run` for Python)
3. Determine status: command succeeds → ADDRESSED, stale → INVALID, still fails → OPEN
4. If finding has PR Comment URL: post reply + resolve if ADDRESSED/INVALID, post reply if OPEN
5. Update the report's validation log and statuses

## Common Pitfalls

- Run actual validation commands — don't assume results
- Document evidence from command output
- Do NOT rewrite finding content — only update statuses and validation log
- Always post a reply when a finding has a PR Comment URL (closes the loop)
