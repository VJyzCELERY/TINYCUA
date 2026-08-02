# OpenCode CLI

## Verify

```bash
opencode --version
opencode models
opencode run --help
```

Use an installed, authenticated OpenCode CLI. Do not install it during `/goal`.

## Run from a shell

The non-interactive form is `opencode run [message...]`:

```bash
opencode run \
  --dir "$WORKTREE" \
  --model "provider/model" \
  --variant high \
  --auto \
  "Implement the requested change."
```

Useful documented options:

- `--model`, `-m`: provider/model identifier.
- `--agent`: primary OpenCode agent.
- `--variant`: provider/model-specific configuration, commonly reasoning effort.
- `--thinking`: display reasoning blocks; it does not select reasoning effort.
- `--dir`: project directory.
- `--continue`, `-c`: continue the last session in the directory.
- `--session`, `-s`: continue a specific session; prefer this over `--continue` in automation.
- `--fork`: fork a continued or explicit session.
- `--format default|json`: output format.
- `--file`, `-f`: attach supporting files.

There is no documented `--reasoning` flag. Variant names vary by provider, model, and installed OpenCode version. Use quoted positional prompt text; stdin behavior and JSON event fields are version-sensitive.

## Unattended roles

`--auto` lets OpenCode auto-approve permissions not otherwise denied. Use it only after `/goal` has authorized that phase and preserve explicit denials for destructive or out-of-worktree operations. It does not grant authorization.

| Role | Recommended command shape |
|---|---|
| Planner | `opencode run --auto --model <model> --dir "$WORKTREE" "Plan or synchronize Specs."` |
| Worker | `opencode run --auto --model <model> --dir "$WORKTREE" "Implement the approved plan."` |
| Reviewer | `opencode run --auto --model <model> --dir "$WORKTREE" "Review changes; do not modify files."` |

For an explicit resume:

```bash
opencode run --session "$SESSION_ID" --model "provider/model" --dir "$WORKTREE" \
  "Continue the approved task."
```

Do not rely on `--continue` when concurrent work could make “last session” ambiguous.

## Wrap the exact command

The generic forms are `goal_roles.py verify <goal> <role> -- <provider-argv...>` and `run_agent.py <worktree> --goal <goal> --role <role> --phase <phase> [context...] -- <provider-argv...>`.

First require exact configured-model binding:

```bash
uv run python .agents/scripts/goal_roles.py verify "$GOAL" "$ROLE" -- \
  opencode run --auto --dir "$WORKTREE" --model "$MODEL" "$PROMPT"
```

Then pass that unchanged OpenCode argv to the generic wrapper:

```bash
uv run python .agents/scripts/run_agent.py "$WORKTREE" \
  --goal "$GOAL" --role "$ROLE" --phase "$PHASE" \
  --harness opencode --model "$MODEL" --session "$SESSION_ID" -- \
  opencode run --auto --dir "$WORKTREE" --model "$MODEL" "$PROMPT"
```

Omit `--session` when starting a new session. `run_agent.py` sets the process working directory, starts the exact argv without a shell, and retains lifecycle metadata only. It does not parse OpenCode flags, output, or session events, and does not grant authorization.

## References

- https://opencode.ai/docs/cli/#run-1
- https://opencode.ai/docs/models/#variants
- https://opencode.ai/docs/agents/
