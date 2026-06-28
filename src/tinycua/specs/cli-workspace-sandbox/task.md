# Tasks: CLI Workspace Sandboxing

Implementation tasks for CLI Workspace Sandboxing. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for CLI argparse fix <!-- id: 0 -->
- [ ] Write unit tests for bind_workspace (no mkdir) <!-- id: 1 -->
- [ ] Write unit tests for run_command CWD stability <!-- id: 2 -->
- [ ] Run tests — expect RED <!-- id: 3 -->

## Implementation Phase

- [ ] Fix main.py: register run args on subparser, single-pass dispatch <!-- id: 4 -->
- [ ] Fix run.py: resolve --dir to absolute in run_command <!-- id: 5 -->
- [ ] Fix context.py: remove mkdir from bind_workspace <!-- id: 6 -->
- [ ] Fix benchmark.py: deprecation warning + remove os.chdir <!-- id: 7 -->
- [ ] Fix conftest.py: remove FileNotFoundError workaround <!-- id: 8 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN <!-- id: 9 -->
- [ ] Run full suite: `cd src/tinycua && uv run pytest` <!-- id: 10 -->

## Verification Phase

- [ ] Manual: `tinycua run "hello" --dir ./tmp` works without argparse crash <!-- id: 11 -->
- [ ] Manual: CWD unchanged after run <!-- id: 12 -->

## Review and Merge

- [ ] Commit and push <!-- id: 13 -->

---

*Task IDs enable tracking and cross-referencing*
*Last updated: 2026-06-18*