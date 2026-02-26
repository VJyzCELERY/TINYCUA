# Subprojects Directory

## Overview
The `src/` folder contains subprojects that are modular components of TINYCUA. Each subproject inherits rules and conventions from the main project, but may also define its own specific rules in `docs/project_rules`. Each subproject has its own documentation, rules, and tests.

### Subprojects
1. **TINYCUA_BACKEND** - Backend services and core API functionality.
2. **TINYCUA_RUNNER** - Execution engine and workflow orchestration.
3. **TINYCUA_SDK** - Developer SDK and integration libraries.

### Adding a New Subproject
1. Create a folder inside `src/`.
2. Add the necessary files and documentation, including `README.md`, `docs/`, `tests/`, and configuration files.
