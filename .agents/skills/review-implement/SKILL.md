---
name: review-implement
description: Apply code fixes from review findings without updating the review report
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/review-implement.md
---

# Skill: review-implement — Apply Fixes from Review Findings

## Purpose

Implement code fixes based on review findings. ONLY modifies source code — does NOT update the review report.

## Critical Rule

**DO NOT update the review report.** Read-only input. Status updates are handled by review-verify and review-validate.

If the review is stale, STOP. Do not implement stale findings. Tell the user directly to run `/review-verify` first so the review report is validated against the latest commit. Do not automatically run `/review-verify` from review-implement.

## Execution

1. Read `./reviews/REVIEW_{normalized_branch}.md` by default; normalize branch slashes (`/`) to underscores (`_`) and do not ask where the review file is
2. For each OPEN finding: go to Location, implement Suggested Fix, run validation command
3. Always use `uv run` for Python/pytest validation
4. Report which findings were fixed

## Common Pitfalls

- ONLY modify source code — never touch the review report
- Never implement stale review findings — recommend `/review-verify` and stop
- Run validation commands after fixing to confirm
- If validation fails, note what's still wrong
- Do not ask where the review file is. Default to `./reviews/REVIEW_{normalized_branch}.md`.
