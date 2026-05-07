## Summary

### Problem
[Describe the problem being solved. What was missing, broken, or unclear before this change? Be specific about the user-facing or developer-facing impact.]

### Solution
[Describe the solution implemented. List key changes, new modules, modified files, and architectural decisions. Be specific about what was added/changed/removed.]

### Scope

In scope:
- [Item 1: concise description of what's included]

Out of scope:
- [Item 1: concise description of what's explicitly excluded]

## How to Test

1. Run the test suite:
   ```bash
   cd <subproject-dir> && uv run pytest
   ```
   - Expected: [describe expected test results]

2. Run lint:
   ```bash
   cd <subproject-dir> && uv run ruff check .
   ```
   - Expected: `All checks passed!`

3. Run type checking:
   ```bash
   cd <subproject-dir> && uv run mypy <python_package>/
   ```
   - Expected: Success, no issues.

[Additional verification steps as needed.]

## Review Notes

- [File/module 1] — [what to review closely and why]
- [File/module 2] — [what to review closely and why]

## Related Issues

- [#issue-number](link-to-issue) — [description]
