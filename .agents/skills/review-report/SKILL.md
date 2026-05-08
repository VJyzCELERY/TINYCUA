---
name: review-report
description: Conduct scoped code reviews of branch changes and generate structured reports
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/review-report.md
---

# Skill: review-report — Scoped Code Review with Report

## Purpose

Conduct a scoped code review of the current branch's changes and generate a structured report with actionable findings.

## Prerequisites

- Load skill: preflight (for preflight-review.py and preflight-pr.py)
- Load skill: gh-pr-management (for PR context — body, title)

## Execution

1. Run preflight: `uv run python .agents/scripts/preflight-review.py --scope pr --init-review`
2. If reviewing against a PR: read PR body/title via `gh pr view`, adjust scope, check compliance
3. Determine scope: PR mode (diff against PR base), Branch mode (diff against merge-base), or Unscoped
4. Analyze all in-scope files
5. Write findings to `./reviews/REVIEW-{name}.md` using `.agents/templates/REVIEW-template.md`
6. Each finding must have: precise file:line, severity, description, why it matters, suggested fix, validation command

## Common Pitfalls

- Documentation is equal priority to code — flag doc issues at same severity
- Record commit range in header for staleness detection
- Always check PR body/title compliance against specs
- Use `uv run` prefix on all Python validation commands
- Review files in `./reviews/` are gitignored — do NOT `git add` or commit them
