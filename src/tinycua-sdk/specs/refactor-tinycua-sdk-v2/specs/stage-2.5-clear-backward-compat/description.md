# Stage 2.5: Clear Backward Compatibility — Description

## Purpose
Strip out all backward-compatibility artifacts from the spec and implementation. The project is a **clean-slate reset** of tinycua-sdk — not a migration from v1. Any code, tests, or documentation that frames the work as "upgrading from v1" or "rejecting old parameters" is misleading and should be removed.

## What This Stage Does
1. Removes the `_OBSOLETE_PARAMS` frozenset and its validation logic from the Agent constructor design.
2. Removes the "obsolete params rejected" target and expected output from Stage 2.
3. Updates all subsequent stages (3–9) to remove any backward-compatibility or migration framing from descriptions, specs, and designs.
4. Updates the ROADMAP to reflect that this is a project reset, not a v2 migration.

## What This Stage Does NOT Do
- It does not change any runtime behavior — only spec/documentation/test targets change.
- It does not add new features.

## Dependencies
- Depends on: Stage 2 (Agent Configuration & Creation).
- Feeds into: Stages 3–9 (all subsequent stages build on a clean foundation).
