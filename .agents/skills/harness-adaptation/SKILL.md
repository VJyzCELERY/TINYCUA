---
name: harness-adaptation
description: Form safe external /goal role invocations for installed AI harnesses
license: MIT
compatibility: opencode, codex, claude
metadata:
  type: infrastructure
---

# Harness Adaptation

Use this index only after `/goal` resolves an external Planner, Worker, or Reviewer role. `current` uses native sibling delegation and does not start a process.

Load exactly one selected provider guide:

- `opencode.md` for `opencode`
- `codex.md` for `codex`
- `claude-code.md` for `claude`

Each provider guide is a full installed-CLI reference: verify the version, form the provider's non-interactive command, select native unattended controls, and handle sessions and output according to that provider's documented interface. The guide then passes exact provider argv unchanged to the generic runner. `/goal` does not install or fall back, and it validates canonical repository evidence before treating a terminal run as complete.

`/goal --auto` authorizes the workflow batch; a provider's unattended flag, sandbox, or permission mode prevents HITL stalls only. It never grants more authority than the current `/goal` phase.
