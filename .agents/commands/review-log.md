---
description: Logs a completed review cycle to the review log
subtask: true
---

Log the current review report into the permanent review log at `./reviews/log/REVIEW_{branch}.md`.

> Load skill: review-log (for logging review reports)

**Query**: $1 (natural language query or review file path, e.g., "log the review at reviews/REVIEW_feature.md" or simply "reviews/REVIEW_feature.md")

## Workflow

1. **Read the review report**: Load the review file at `$1` (defaults to `./reviews/REVIEW_{current_branch}.md`)

2. **Extract findings**: Parse all findings with status ADDRESSED, INVALID, or DEFERRED. Skip any OPEN findings.

3. **Determine log path**: The log file is at `./reviews/log/REVIEW_{current_branch}.md`. Check if it already exists.

4. **Determine entry ID**: Run `uv run python .agents/scripts/review-log.py --next-id` to get the next sequential REVIEW_ID.

5. **Generate entry**: Use `.agents/templates/REVIEW_LOG-template.md` as reference. Each entry must be wrapped in `[REVIEW_{ID}_START]` and `[REVIEW_{ID}_END]` delimiters.

6. **Create or append**: If the log file doesn't exist, create it with a `# Review Log: {branch}` header. Append the new entry.

7. **Validate**: Run `uv run python .agents/scripts/review-log.py --validate ./reviews/log/REVIEW_{branch}.md` to verify format.

8. **Return confirmation**: Report the log file path and entry ID.

## Entry Format

```
[REVIEW_{ID}_START]
---
**Review Date**: YYYY-MM-DD
**Scope**: PR #N or branch scope
**Cycle**: {ID}
**Total Findings**: N | **Resolved**: N | **Deferred**: N | **Invalid**: N
---
### F-001: Short Description
- **Severity**: high | **Category**: correctness
- **Status**: addressed
- **Problem**: Description of the issue
- **Validation**: How it was validated
- **Resolution**: What was done to fix
- **Reasoning**: Why this fix was chosen
---
[REVIEW_{ID}_END]
```

## Important
- Only log findings with status addressed, invalid, or deferred — never OPEN
- Each cycle gets a sequential ID (REVIEW_1, REVIEW_2, ...)
- The log is append-only — never modify existing entries
- Review log is at `./reviews/log/REVIEW_{branch}.md`, not in the main reviews directory
- The main review report at `./reviews/REVIEW_{branch}.md` is NOT deleted after logging
