# Claude Code CLI

## Verify

```bash
claude --version
claude --help
```

Use an installed, authenticated Claude Code CLI. Do not install it during `/goal`.

## Run from a shell

The non-interactive form is `claude -p "PROMPT"` (or `claude --print`):

```bash
claude -p "Implement the requested change." \
  --model "$MODEL" \
  --effort high \
  --permission-mode dontAsk \
  --output-format json
```

Claude Code has no top-level execution `--cwd`; the wrapper runs it in the validated worktree. `--add-dir` grants additional access but does not change that primary directory.

Useful documented options:

- `--model`: model alias or pinned model name.
- `--fallback-model`: ordered fallback aliases.
- `--effort low|medium|high|xhigh|max`: adaptive reasoning level when model-supported.
- `--continue`, `-c`: continue the last session; avoid in concurrent automation.
- `--resume`, `-r`: resume a specific session.
- `--session-id`: caller-provided UUID for a new session.
- `--fork-session`: fork a resumed or continued session.
- `--permission-mode`: permission profile.
- `--allowedTools` and `--disallowedTools`: explicit tool policy.
- `--output-format text|json|stream-json`: result format.
- `--max-turns` and `--max-budget-usd`: execution bounds.
- `--bare`: skip project configuration, hooks, skills, plugins, MCP, and auto-memory.

There is no documented `--reasoning` or `--thinking` CLI flag; use `--effort`. Positional text is the prompt; stdin supplies additional context.

## Unattended roles

Use `--permission-mode dontAsk` to deny unapproved actions instead of waiting for HITL. Add only the tools required by the authorized phase:

| Role | Recommended policy |
|---|---|
| Planner | `dontAsk` with read and authorized planning/delivery tools only. |
| Worker | `dontAsk` with explicit edit and test tools, or `acceptEdits` only when the phase permits edits. |
| Reviewer | `dontAsk` with read and test tools only. |

Do not default to `bypassPermissions` or `--dangerously-skip-permissions`; those are for an explicitly isolated environment only. Permission flags avoid stalls but do not grant authorization.

Resume a known session instead of `--continue`:

```bash
claude -p "Continue the approved task." --resume "$SESSION_ID" \
  --model "$MODEL" --permission-mode dontAsk --output-format json
```

## Wrap the exact command

The generic forms are `goal_roles.py verify <goal> <role> -- <provider-argv...>` and `run_agent.py <worktree> --goal <goal> --role <role> --phase <phase> [context...] -- <provider-argv...>`.

Verify configured-model binding:

```bash
uv run python .agents/scripts/goal_roles.py verify "$GOAL" "$ROLE" -- \
  claude -p "$PROMPT" --model "$MODEL" --permission-mode dontAsk
```

Then wrap the exact Claude argv:

```bash
uv run python .agents/scripts/run_agent.py "$WORKTREE" \
  --goal "$GOAL" --role "$ROLE" --phase "$PHASE" \
  --harness claude --model "$MODEL" --session "$SESSION_ID" -- \
  claude -p "$PROMPT" --model "$MODEL" --effort high \
    --permission-mode dontAsk --output-format json
```

Omit `--session` when starting a new session. `run_agent.py` launches exact argv without a shell and retains lifecycle metadata only; it does not parse Claude flags, output, or session events, and does not grant authorization.

## References

- https://code.claude.com/docs/en/cli-reference
- https://code.claude.com/docs/en/headless
- https://code.claude.com/docs/en/sessions
- https://code.claude.com/docs/en/model-config
- https://code.claude.com/docs/en/permission-modes
