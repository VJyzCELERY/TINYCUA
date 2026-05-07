---
description: Validates findings from a previous review and MUST update the report
subtask: true
---

Validate findings from a previous review and MUST update the report with validation results.

**Review File**: $1 (path to the REVIEW-{name}.md file — look in `./reviews/` first if not found)
**Focus Area (Optional)**: $2 (validate only specific finding codes or severity, e.g., "CRITICAL" or "ISSUE-001,ISSUE-002")

If no focus area is provided, validate ALL OPEN findings.

---

## Scope Alignment (IMPORTANT)

Before validating, align with the current branch scope to ensure validation only runs on relevant code.

### Scope Check Steps

1. **Check current branch**:
   ```bash
   git branch --show-current
   ```
   - If branch is `main`, no diff scoping needed
   - If on a feature branch, proceed to check for PR

2. **Check for an existing PR**:
   ```bash
   gh pr list --head "$(git branch --show-current)" --state open --json baseRefName,headRefName,number --jq '.[0]'
   ```
   - If PR exists, use the PR target branch as the diff base
   - If no PR, use `git merge-base main HEAD` as the diff base

3. **Get the current diff**:
   ```bash
   git diff <base>...HEAD --name-only
   ```

4. **Cross-reference findings with scope**:
   - For each OPEN finding, check if its location exists in the current diff
   - If a finding's file is NOT in the current diff, mark it as **INVALID** with note: "File unchanged in current diff — stale finding"
   - If a finding's file IS in the current diff, proceed with normal validation
   - Findings for files outside `$1` (the reviewed directory) are exempt from scope alignment

---

## Instructions

1. **Align scope**: Follow the Scope Alignment section above
2. **Read the Review**: Load and analyze the review report
3. **MUST Update**: This command MUST update the review file with validation results
4. **Filter Findings**: If `$2` is provided, only validate those findings
5. **Validate Each In-Scope Finding**: For each OPEN finding:
   - Execute the "How to Test/Validate" command provided in the finding (use `uv run` for Python)
   - Determine if the issue has been ADDRESSED, INVALID, or remains OPEN
   - Document evidence from the validation command output
6. **Update the Review Report**:
   - Add or append to the "Validation Log" section
   - Update each finding's status, validation date, and notes
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

- Run actual validation commands — don't just assume
- Document evidence from command output
- Be accurate in determining status
- This command MUST write/update the review file — do not skip the write step
- Stale findings (files outside current diff) should be marked INVALID automatically

Begin by reading the review file, aligning scope, then validate each finding and update the report.
