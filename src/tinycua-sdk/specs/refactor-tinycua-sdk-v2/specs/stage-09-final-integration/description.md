# Stage 9: Final Integration & Polish — Description

## Purpose
Ensure all 16 goal-derived integration tests pass, the SDK is fully typed and linted, public API exports are clean, old tests are removed, and no `NotImplementedError` stubs remain in production code. This is the final quality gate before release.

## What You'll Find Here
- **`spec.md`** — Requirements for full test suite pass (16/16), type cleanup, public API exports (`__all__`), documentation updates, old test removal, linting, and stub elimination. Includes 6 success criteria covering all requirements plus goal script executability.
- **`design.md`** — Final architecture overview: complete module structure with deleted modules listed for reference, `__init__.py` final state, type cleanup checklist per file, test strategy (integration + unit + mock transport), and a release readiness checklist with verification commands.

## What This Stage Does NOT Do
- It does not implement new features — only verifies and polishes what already exists.
- It does not change the public API shape — only cleans up exports.
- It does not add new integration tests — all 16 are derived from goal scripts in earlier stages.

## How to Use These Files
1. Read `spec.md` to understand all acceptance criteria that must be met before this stage is complete.
2. Follow `design.md`'s verification commands systematically — run them in order.
3. Do not mark this stage complete until every success criterion passes and the release checklist is green.

## Targets (Test Scenarios)
This stage includes 5 atomic test scenarios in `targets/`:
- **01_full_goal_execution.py** — Verify all 16 goal scripts can be executed without errors
- **02_public_api_clean.py** — Verify from tinycua_sdk import * only exports the public API
- **03_no_notimplementederror.py** — Verify no production code raises NotImplementedError
- **04_ruff_passes.py** — Verify ruff check passes on the SDK
- **05_import_sanity_final.py** — Final import sanity check

Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

> **Important:** These targets are **MUST-HAVE** requirements for this stage. However, you should write additional integration tests during development as needed. The targets represent the minimum coverage; you may add more tests to ensure robustness.

## Dependencies
- Depends on: All previous stages (0–8) must be complete with all integration tests passing individually.
- Feeds into: Release — once this stage completes, the SDK is ready for distribution.
