---
description: Validates, clarifies, and updates review findings to ensure the review is precise and actionable
subtask: true
---

Validate findings from a previous review: confirm fixes, clarify vague issues, and update the report.

**Query**: $1 (natural language query or review file path, e.g., "validate the findings in reviews/REVIEW-foo.md" or simply "reviews/REVIEW-foo.md")
**Focus Area (Optional)**: $2 (validate only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, validate ALL OPEN findings.

---

## Role

`review-validate` has two equally important responsibilities:

1. **Validate**: Check if each finding has been properly addressed (ADDRESSED, INVALID, or still OPEN)
2. **Clarify**: Improve the precision of each finding — rewrite vague descriptions, add missing context, provide better validation commands — so the review is as actionable as possible

A finding that is too vague to act on should be clarified, not just left OPEN.

---

## Scope Alignment

Before validating, align with the current branch scope to ensure validation only runs on relevant code.

1. **Check current branch**: `git branch --show-current`
2. **Check for an existing PR**: `gh pr list --head "$(git branch --show-current)" --state open --json baseRefName,headRefName,number --jq '.[0]'`
3. **Get the current diff**: `git diff <base>...HEAD --name-only`
4. **Cross-reference findings with scope**:
   - If a finding's file is NOT in the current diff, mark it **INVALID** — "File unchanged in current diff — stale finding"
   - If a finding's file IS in the current diff, proceed with normal validation

---

## Instructions

1. **Align scope**: Follow the Scope Alignment section above
2. **Read the Review**: Load and analyze the review report
3. **MUST Update**: This command MUST update the review file with validation results
4. **Filter Findings**: If `$2` is provided, only validate those findings
5. **Process Each In-Scope Finding**:
   - **Clarify first**: Is the finding description clear and actionable? If not, rewrite it:
     - Add missing file:line references
     - Replace vague language ("bad code") with specific observations
     - Add or improve the "How to Test/Validate" command
     - Add or improve the "Suggested Fix"
   - **Then validate**: Execute the "How to Test/Validate" command (use `uv run` for Python)
   - **Determine status**: ADDRESSED (passes), INVALID (no longer relevant), or OPEN (still exists)
   - **Document evidence**: Include command output as evidence
6. **Update the Review Report**:
   - Add or append to the "Validation Log" section
   - Update each finding's status, validation date, and notes
   - Include the clarified finding text alongside the original
7. **Save Changes**: Use Write to update the original review file

## Python Validation

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
- **INVALID**: Issue no longer exists or is no longer relevant — including stale findings outside current diff scope
- **OPEN**: Issue still exists and is valid

## Important

- **Clarify before validating** — a vague finding helps nobody
- Run actual validation commands — don't just assume
- Document evidence from command output
- Be accurate in determining status
- This command MUST write/update the review file — do not skip the write step
- Stale findings (files outside current diff) should be marked INVALID automatically

Begin by reading the review file, aligning scope, then clarify and validate each finding and update the report.
