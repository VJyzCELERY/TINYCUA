# Naming Conventions

This document defines the naming conventions for the MAIN-PROJECT and its subprojects.

## Convention Reference

Throughout the project documentation, these placeholders are used. Each maps to a specific naming rule:

| Placeholder | Represents | Convention | Example |
|-------------|-----------|------------|---------|
| `<subproject>` | Subproject directory under `src/` | `lower-kebab-case` | `my-subproject` |
| `<subproject-dir>` | Same as `<subproject>` (used in path examples) | `lower-kebab-case` | `my-subproject` |
| `<python_package>` | Python package directory inside subproject | `lower_snake_case` | `my_subproject` |
| `<module>` | Domain/feature subpackage inside the Python package | `lower_snake_case` | `clients`, `models`, `tools` |
| `<feature-name>` | Feature spec/design folder | `lower-kebab-case` | `user-authentication` |

## Subproject Naming

1. Each subproject folder uses `lower-kebab-case`:
   - Directory: `src/<subproject>/`
   - Example: `src/my-subproject/`
2. The corresponding Python package folder inside a subproject uses `lower_snake_case`:
   - Directory: `src/<subproject>/<python_package>/`
   - Example: `src/my-subproject/my_subproject/`

## Module / Subpackage Naming

1. Domain/feature subpackages inside the Python package use `lower_snake_case`:
   - Directory: `<python_package>/<module>/`
   - Example: `my_subproject/clients/`

## File Naming Conventions

1. Python files use `snake_case`:
   - Example: `my_module.py`
2. Test files are prepended with `test_`:
   - Example: `test_main.py`

## Feature Spec Naming

1. Feature spec/design folders use `lower-kebab-case`:
   - Directory: `specs/<feature-name>/`
   - Example: `specs/user-authentication/`
