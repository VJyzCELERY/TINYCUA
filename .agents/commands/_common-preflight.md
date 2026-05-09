Standard pre-flight invocation for review commands.

```bash
uv run python .agents/scripts/preflight-review.py --scope pr --review-file "$REVIEW_FILE"
```

- If preflight exits non-zero, read its warnings: staleness, unstaged changes, scope problems.
- For a new review (init): `uv run python .agents/scripts/preflight-review.py --scope pr --init-review`
- Always load this module before running any review command.
