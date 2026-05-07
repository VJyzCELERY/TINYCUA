# Stage 6: Serialization & Directory Loading — Description

## Purpose
Enable agents, skills, and tools to be exported/imported as JSON/YAML and bulk-loaded from directories. This stage adds serialization round-trips with optional secret redaction, `Skill.load_directory()` for SKILL.md parsing, and `Tool.load_directory()` for discovering `@tool` decorators in Python files.

## What You'll Find Here
- **`spec.md`** — Requirements for agent serialization (`to_config`, `to_json`, `to_yaml`, `from_dict`, file loaders), skill directory loading (SKILL.md frontmatter parsing), and tool directory loading (module scanning). Includes 6 success criteria covering round-trips, redaction, YAML, skill/tool directories, and integration tests.
- **`design.md`** — Full implementations: serialization methods with redaction logic, `from_dict()` reconstruction, SKILL.md frontmatter parser using YAML, `Tool.load_directory()` using `importlib.util`, and error handling for missing files or malformed content.

## What This Stage Does NOT Do
- It does not serialize custom loop instances or approval workflows — these are runtime objects that consumers must re-attach after loading.
- It does not implement tool callables from config — loaded tools without callables cannot be invoked (by design).
- It does not add new fields to `Skill` or `Tool`.

## How to Use These Files
1. Read `spec.md` to understand the exact serialization contract and directory formats.
2. Implement using `design.md`, but write integration tests first with temp files/directories.
3. Verify round-trip parity carefully — any field loss here breaks deployment workflows.

## Targets (Test Scenarios)
This stage includes 5 atomic test scenarios in `targets/`:
- **01_config_roundtrip.py** — Verify to_config/from_dict round-trip preserves all fields
- **02_json_redaction.py** — Verify to_json redacts api_key when requested
- **03_yaml_export_import.py** — Verify to_yaml/from_dict round-trip
- **04_skill_directory_loading.py** — Verify Skill.load_directory discovers and parses SKILL.md files
- **05_tool_directory_loading.py** — Verify Tool.load_directory discovers @tool-decorated functions

Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

> **Important:** These targets are **MUST-HAVE** requirements for this stage. However, you should write additional integration tests during development as needed. The targets represent the minimum coverage; you may add more tests to ensure robustness.

## Dependencies
- Depends on: Stages 0–5 (all value objects and execution must exist).
- Feeds into: Stage 9 (final polish includes verifying goal scripts can load from files).
