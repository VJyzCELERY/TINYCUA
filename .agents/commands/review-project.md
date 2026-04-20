---
description: Conducts a code review of the specified directory and generates a report
subtask: true
---

Conduct a thorough review of the specified directory and generate a comprehensive report.

**Target Directory**: $1

## Instructions

1. **Analyze the Directory**: Use Glob and Read tools to examine all files in `$1` thoroughly
2. **Identify Findings**: Document issues with clear Issue Codes (e.g., ISSUE-001, ISSUE-002)
3. **Create reviews directory**: Use Bash to create `$1/reviews/` directory if it doesn't exist
4. **Create Review Report**: Use the Write tool to generate REVIEW-{name}.md in `$1/reviews/` directory

## Report Filename
Use format: `REVIEW-{directory-name}.md` (e.g., for `/path/to/myproject` use `REVIEW-myproject.md`)

## Review Report Format

```markdown
# Review Report: [Project Name]

**Directory Reviewed**: [absolute/path]
**Review Date**: [YYYY-MM-DD]
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

## Review Categories to Check
- Code quality and style
- Security vulnerabilities
- Performance issues
- Documentation completeness
- Test coverage
- API consistency
- Error handling
- Dependencies

## Important
- Each finding MUST include an executable validation command
- Use proper Issue Codes (ISSUE-001, ISSUE-002, etc.)
- Categorize findings by severity
- Use the Write tool to create the review file

## Template Reference
- Template file: `~/.config/opencode/templates/REVIEW-template.md`

Begin now - analyze the directory, identify findings, and write the review report to `$1/reviews/REVIEW-{name}.md`