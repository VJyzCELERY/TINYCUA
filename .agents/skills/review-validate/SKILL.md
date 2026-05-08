---
name: review-validate
description: Run the complete validation pipeline — clarify then verify findings
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/review-validate.md
---

# Skill: review-validate — Full Validation Pipeline

## Purpose

Run the complete validation pipeline: clarify vague findings → verify each one's status (ADDRESSED, INVALID, or OPEN).

## Prerequisites

- Load skill: preflight (for preflight-review.py)

## Execution

1. Run preflight: `uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$1"`
2. Phase 1 — Clarify: delegate `/review-clarify` to improve finding precision
3. Phase 2 — Verify: delegate `/review-verify` to check each finding's status
4. Review the updated report to confirm all findings properly statused

## Common Pitfalls

- Always run clarify BEFORE verify — precise findings lead to accurate validation
- Run steps inline by default (only delegate to subagents if user explicitly says to)
- After verify, confirm all findings have proper statuses
