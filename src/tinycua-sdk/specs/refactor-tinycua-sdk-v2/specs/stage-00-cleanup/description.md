# Stage 0: Scorched-Earth Cleanup — Description

## Purpose
This stage removes every dead module, stub, and obsolete concept from the v1 SDK so that subsequent stages build on a clean foundation. It is not a refactor — it is deletion. Nothing is deprecated; everything is removed.

## What You'll Find Here
- **`spec.md`** — The authoritative list of what to delete, organized by file and issue code from the review report. Includes 5 concrete success criteria with copy-paste verification commands.
- **`design.md`** — Step-by-step implementation plan: deletion order (leaf modules first, then keeping files), exact code snippets for each file's in-place cleanup, test deletions, and risk mitigation.

## What This Stage Does NOT Do
- It does not implement any new features.
- It does not rename or restructure kept modules — that happens in later stages.
- It does not write integration tests — those are derived from goal scripts in later stages.

## How to Use These Files
1. Read `spec.md` first to understand the full scope of deletion.
2. Follow `design.md`'s phased approach: delete leaf modules, then gut keeping files, then clean old tests.
3. Run each success criterion command after completing the relevant phase — do not wait until the end.

## Targets (Test Scenarios)
This stage includes 3 atomic test scenarios in `targets/`:
- **01_import_sanity.py** — Verify SDK imports cleanly after cleanup
- **02_deleted_modules_raise.py** — Verify deleted modules cannot be imported
- **03_no_stubs_at_import.py** — Verify no NotImplementedError is raised during import

Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

## Dependencies
This stage has no dependencies on other stages. It is the first stage and must complete before any implementation work begins.
