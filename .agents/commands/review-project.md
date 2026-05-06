---
description: Conducts a code review of the specified directory and generates a report
subtask: true
---

Conduct a thorough review of the specified directory and generate a comprehensive report.

**Target Directory**: $1
**Review Focus (Optional)**: $2 (what to focus on - e.g., "security", "performance", "docs", "full")

If no review focus is provided, conduct a comprehensive full review.

## Instructions

1. **Analyze the Directory**: Use Glob and Read tools to examine all files in `$1` thoroughly
2. **Focus Review**: If `$2` is provided, prioritize reviewing for that specific aspect:
   - "security" - focus on security vulnerabilities
   - "performance" - focus on performance issues
   - "docs" - focus on documentation quality
   - "code" - focus on code quality
   - "full" - comprehensive review (default if no focus)
3. **Identify Findings**: Document issues with clear Issue Codes (e.g., ISSUE-001, ISSUE-002)
4. **Create review output directory**: Use Bash to create `./reviews/` directory if it doesn't exist
5. **Create Review Report**: Use the Write tool to write the review report to `./reviews/REVIEW-{directory-name}.md`

## Report Path Convention

Review reports ALWAYS go to `./reviews/REVIEW-{name}.md` (relative to the repo root / workdir).  
Do NOT write reviews inside the target directory. This keeps reviews findable at a consistent location.

The `$1` argument is the target being reviewed, NOT the output location.

## Python Validation Commands

This project uses `uv` for Python environment management. All validation commands in findings MUST use `uv run`:

```bash
# Always use uv run for Python commands
cd src/tinycua-sdk && uv run python -c "..."
cd src/tinycua-sdk && uv run pytest tests/...

# ❌ Wrong - bare python/pytest may import from wrong worktree
python ...
pytest ...
```

## Report Filename
Use format: `REVIEW-{directory-name}.md`

## Review Report Format

```markdown
# Review Report: [Project Name]

**Directory Reviewed**: [absolute/path]
**Review Date**: [YYYY-MM-DD]
**Review Focus**: [focus or "full"]
**Reviewer**: Code Reviewer

---

## Summary

[Brief summary of what was reviewed]

---

## Findings

### [ISSUE-001] - [CRITICAL] - [Issue Name]

**Status**: OPEN

**Severity**: CRITICAL

[Detailed description of the issue]

**Location**: [file:line number]

**How to Test/Validate**:
```bash
[Command to check for this issue - MUST use uv run]
```

**Suggested Fix**:
[Description of how to fix]
```

## Important
- MUST create the review file at `./reviews/REVIEW-{name}.md`
- Each finding MUST include an executable validation command (prefixed with `uv run`)
- Use proper Issue Codes (ISSUE-001, ISSUE-002, etc.)
- Categorize findings by severity

Begin now - analyze the directory, identify findings, and write the review report.