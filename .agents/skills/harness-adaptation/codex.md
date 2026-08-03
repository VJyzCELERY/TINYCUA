# Codex CLI

## Verify

```bash
codex --version
codex exec --help
```

Use an installed, authenticated Codex CLI. Do not install it during `/goal`.

## Run from a shell

The non-interactive form is `codex exec [OPTIONS] [PROMPT]`:

```bash
codex exec \
  --cd "$WORKTREE" \
  --model "$MODEL" \
  --config 'model_reasoning_effort="high"' \
  --sandbox workspace-write \
  --json \
  "Implement the requested change."
```

Useful documented options:

- `--model`, `-m`: model identifier.
- `--config`, `-c`: repeatable TOML configuration; use `model_reasoning_effort` for reasoning effort.
- `--profile`, `-p`: named Codex profile.
- `--cd`, `-C`: workspace root.
- `--sandbox read-only|workspace-write|danger-full-access`: execution sandbox.
- `--add-dir`: additional writable directory.
- `--json`: JSONL events.
- `--output-last-message`: final response file.
- `--output-schema`: structured final response schema.
- `--ephemeral`: disable session persistence; do not use when resume is required.
- `resume <session>` or `resume --last`: continue a session.

There is no stable `--auto` or `--effort` flag for `codex exec`. Headless execution does not prompt, so make the sandbox explicit instead.

## Unattended roles

| Role | Recommended sandbox |
|---|---|
| Planner | `--sandbox read-only` unless the phase is authorized to write Specs or deliver a PR. |
| Worker | `--sandbox workspace-write`. |
| Reviewer | `--sandbox read-only`. |

Network access is separate from workspace writes and must be enabled only for an authorized phase that requires it. Never use `--dangerously-bypass-approvals-and-sandbox` or `--yolo` by default; they are for an explicitly isolated environment only. These CLI controls do not grant authorization.

Resume a known session with shared options before `resume`:

```bash
codex exec -C "$WORKTREE" -m "$MODEL" --sandbox workspace-write --json \
  resume "$SESSION_ID" "Continue the approved task."
```

## Wrap the exact command

The generic forms are `goal_roles.py verify <goal> <role> -- <provider-argv...>` and `run_agent.py <worktree> --goal <goal> --role <role> --phase <phase> [context...] -- <provider-argv...>`.

Verify the configured long-form model selector:

```bash
uv run python .agents/scripts/goal_roles.py verify "$GOAL" "$ROLE" -- \
  codex exec --cd "$WORKTREE" --model "$MODEL" --sandbox workspace-write --json "$PROMPT"
```

Then wrap the exact Codex argv:

```bash
uv run python .agents/scripts/run_agent.py "$WORKTREE" \
  --goal "$GOAL" --role "$ROLE" --phase "$PHASE" \
  --harness codex --model "$MODEL" --session "$SESSION_ID" -- \
  codex exec --cd "$WORKTREE" --model "$MODEL" \
    --config 'model_reasoning_effort="high"' --sandbox workspace-write --json "$PROMPT"
```

Omit `--session` when starting a new session. `--json` lets `run_agent.py` retain only a validated Codex `thread.started.thread_id` while discarding every raw event. On a failed run with a captured session, use `run_agent.py resume <failed-run-id> --` with the exact `resume "$SESSION_ID"` argv above. The runner does not parse Codex flags. This does not grant authorization.

## References

- https://developers.openai.com/codex/non-interactive-mode
- https://developers.openai.com/codex/developer-commands?surface=cli#cli-codex-exec
- https://developers.openai.com/codex/agent-approvals-security
- https://developers.openai.com/codex/config-file/config-reference
