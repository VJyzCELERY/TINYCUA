# Code Generation Rules for AI Agents

## Overview
This document defines the rules and expectations for AI agents generating code for the MAIN-PROJECT and its subprojects.

---

## General Principles
1. **Adopt Coding Standards**:
   - Enforce coding standards as described in `docs/project_rules/coding_standards.md`.
   - Incorporate logging practices as outlined in `docs/project_rules/logging_guidelines.md`.
   - Use Ruff auto-fix capabilities to ensure immediate compliance.
   - Include detailed docstrings with descriptions, arguments, and examples for all generated functions and classes.

2. **Purpose-Driven Code**:
   - AI-generated code must have a clear purpose and solve specific tasks or requirements.
   - All code must include comments documenting intent and functionality.

3. **Version Control**:
   - Log changes and generated contributions clearly for traceability.

---

## Commit Naming Rules
AI-generated commits must follow the repository's naming conventions as defined in `../project_rules/commit_naming.md` to ensure consistency in code history.

### Expected Commit Structure
```
(type): Commit message

[Optional Body]

[Optional Footer]
```

### Examples
- **Feature Addition**: `(feat): Implement OAuth2.0 tokens`
- **Bug Fix**: `(fix): Resolve crash in auth token refresh`
- **Documentation**: `(docs): Add API setup guide to README`
- **Bug Fix**: `fix(logging): handle missing log configurations gracefully`
- **Documentation**: `docs: update README with new installation guide`

Ensure commit messages are meaningful, concise, and adhere to the [commit naming rules](../project_rules/commit_naming.md).

---

## Docstring Requirements
Ensure all AI-generated functions and classes follow this format:

### Example Format
```python
"""
This function/class serves as a [brief purpose summary]. It works by [short explanation].

Args:
    arg1 (type): Description.
    arg2 (type): Description.
    **kwargs: Description of supported optional keyword arguments.

Examples:
    # Example usage:
    result = generated_function(arg1, arg2, kwarg_key=value)
"""
```

---

## Exception Handling
- All generated code must include appropriate error handling using `try-except` blocks.
- Clearly define custom exceptions if needed.

---

## Testing Expectations
1. **Test Coverage**:
    - AI-generated code must include corresponding unit and integration tests.
    - Tests must be generated under the appropriate subproject’s `tests/` folder.
2. **Documented Test Cases**:
    - Include examples of expected inputs and outputs in the docstrings.