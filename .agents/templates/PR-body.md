## Summary

### Spec / Design References
- **Spec**: `<repo-root-relative-path>` — full path from the repository root (not worktree root, not CWD) to the spec file. Resolve against `git rev-parse --show-toplevel`, not `pwd`. There may be intermediate subdirectories before the final `spec.md`. Example: `src/tinycua-sdk/specs/refactor-tinycua-sdk-v2/specs/stage-06-serialization/spec.md`
- **Design**: `<repo-root-relative-path>` — same rules as Spec above, pointing to the corresponding `design.md`. Example: `src/tinycua-sdk/specs/refactor-tinycua-sdk-v2/specs/stage-06-serialization/design.md`

### Problem
[Describe the problem being solved. Reference the spec's problem statement. What was missing, broken, or unclear before this change?]

### Solution
[Describe the solution implemented. Map key changes to spec functional requirements (FR-001, FR-002, etc.). List new modules, modified files, and architectural decisions.]

### Scope

In scope:
- [Map to spec FRs: e.g., FR-001 — user authentication via OAuth]
- [Item 2]

Out of scope:
- [Item 1: explicitly excluded — if from spec, note which FR is deferred]
- [Item 2]

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
