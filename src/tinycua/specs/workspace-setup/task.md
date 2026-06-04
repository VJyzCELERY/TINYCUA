# Tasks: Workspace Setup (M0.1)

Implementation tasks for Workspace Setup. Check off items as completed.

## TDD Phase (Tests First)

- [x] Not applicable — workspace setup uses manual acceptance tests, not TDD <!-- id: 0 -->

## Implementation Phase

- [x] Add WildClawBench artifact rules to root `.gitignore` <!-- id: 1 -->
  - [x] Add `benchmark_results/` directory pattern
  - [x] Add `*.benchmark.json` file pattern
  - [x] Add `*.benchmark.yaml` file pattern
- [x] Create `src/tinycua/tinycua/cli/__init__.py` <!-- id: 2 -->
  - [x] Empty package init file
- [x] Create `src/tinycua/tinycua/cli/main.py` <!-- id: 3 -->
  - [x] Define `main()` function with `print("tinycua: workspace is ready.")`
  - [x] Exit via `raise SystemExit(0)`
- [x] Verify `src/tinycua/pyproject.toml` entry point <!-- id: 4 -->
  - [x] Confirm `[project.scripts] tinycua = "tinycua.cli.main:main"` exists (already present)
- [x] Create `src/tinycua/docs/prototype/README.md` <!-- id: 5 -->
  - [x] Document the prototype directory structure and purpose

## Testing Phase

- [x] Run `cd src/tinycua && uv sync` — expect no errors <!-- id: 6 -->
- [x] Run `cd src/tinycua && uv run tinycua` — expect "tinycua: workspace is ready." and exit 0 <!-- id: 7 -->
- [ ] Run `cd src/tinycua && make lint` — expect no errors <!-- id: 8 -->

## Verification Phase

- [x] Verify WildClawBench artifacts are gitignored <!-- id: 9 -->
  - [x] Create `benchmark_results/` and `*.benchmark.json` in `src/tinycua/`
  - [x] Run `git status` and confirm they are not shown
  - [x] Clean up test artifacts
- [x] Verify `docs/prototype/README.md` exists with content <!-- id: 10 -->
- [x] Verify `git diff` shows only intended changes <!-- id: 11 -->

## Documentation Phase

- [x] spec.md created <!-- id: 12 -->
- [x] design.md created <!-- id: 13 -->
- [x] implementation-plan.md created <!-- id: 14 -->
- [x] task.md created <!-- id: 15 -->

## Review and Merge

- [ ] Create pull request <!-- id: 16 -->
- [ ] Address review feedback <!-- id: 17 -->
- [ ] Merge to main branch <!-- id: 18 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-05*
