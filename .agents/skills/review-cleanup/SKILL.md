---
name: review-cleanup
description: Archive resolved review reports after all findings are addressed
license: MIT
compatibility: opencode
metadata:
  type: command-skill
  source: .agents/commands/review-cleanup.md
---

# Skill: review-cleanup — Archive Resolved Reviews

## Purpose

Move resolved review reports (all findings ADDRESSED or INVALID) to archive. Keep a summary of what was cleaned.

## Execution

1. Find all REVIEW-*.md files in the reviews directory
2. For each: check if all findings are ADDRESSED or INVALID
3. If fully resolved: move to `reviews/archived/REVIEW-{name}-RESOLVED.md`
4. Generate a cleanup summary

## Common Pitfalls

- Only archive if ALL findings are resolved — any OPEN finding means skip
- Don't delete — move to archive
- Keep a summary of what was archived and what remains
