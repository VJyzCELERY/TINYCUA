# Skill: review-clarify — Improve Finding Precision

## Purpose

Rewrite vague findings to be precise, actionable, and well-located. Add missing context, sharp validation commands, and clear impact statements.

## Prerequisites

- Load skill: preflight (for preflight-review.py)
- Load skill: gh-pr-management (for gh.py — used for PR follow-ups)

## Execution

1. Run preflight: `uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"`
2. For each OPEN finding, check and improve:
   - Location: file:line must be precise
   - Description: replace vague language with specifics
   - Why It Matters: add impact analysis
   - Suggested Fix: add concrete code examples
   - How to Validate: add or fix validation commands (prefixed with `uv run`)
   - Severity: ensure appropriate
3. If finding has a PR Comment URL, post a follow-up via `gh.py post reply`
4. Update the review report — do NOT change finding status

## Common Pitfalls

- Do NOT change finding status — only improve clarity
- Keep original intent — don't change what the finding says
- Add missing validation commands where absent
