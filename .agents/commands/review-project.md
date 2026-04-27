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
4. **Create reviews directory**: Use Bash to create `$1/reviews/` directory if it doesn't exist
5. **Create Review Report**: Use the Write tool to generate REVIEW-{name}.md in `$1/reviews/` directory

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
[Command to check for this issue]
```

**Suggested Fix**:
[Description of how to fix]
```

## Important
- Each finding MUST include an executable validation command
- Use proper Issue Codes (ISSUE-001, ISSUE-002, etc.)
- Categorize findings by severity

Begin now - analyze the directory, identify findings, and write the review report.