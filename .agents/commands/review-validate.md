---
description: Validates findings from a previous review and MUST update the report
subtask: true
---

Validate findings from a previous review and MUST update the report with validation results.

**Review File**: $1 (path to the REVIEW-{name}.md file — look in `./reviews/` first if not found)
**Focus Area (Optional)**: $2 (validate only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, validate ALL OPEN findings.

## Instructions

1. **Read the Review**: Use the Read tool to load and analyze the review report
2. **MUST Update**: This command MUST update the review file with validation results
3. **Filter Findings**: If $2 is provided, only validate those findings
4. **Validate Each Finding**: For each OPEN finding:
   - Execute the "How to Test/Validate" command provided in the finding (use `uv run` for Python)
   - Determine if the issue has been ADDRESSED, INVALID, or remains OPEN
   - Document evidence from the validation command output
5. **Update the Review Report**:
   - Add or append to the "Validation Log" section
   - Update each finding's status, validation date, and notes
6. **Save Changes**: Use the Write tool to update the original review file

## Python Validation

This project uses `uv` for Python environment management. Always use `uv run`:

```bash
# ✅ Correct
cd <subproject-dir> && uv run python - <<'PY'
...
PY
cd <subproject-dir> && uv run pytest tests/

# ❌ Wrong
python ...
pytest ...
```

## Status Definitions
- **ADDRESSED**: Issue has been fixed (validation command passes)
- **INVALID**: Issue no longer exists or is no longer relevant
- **OPEN**: Issue still exists and is valid

## Important
- Run actual validation commands - don't just assume
- Document evidence from command output
- Be accurate in determining status
- This command MUST write/update the review file — do not skip the write step

Begin by reading the review file, then validate each finding and update the report.
