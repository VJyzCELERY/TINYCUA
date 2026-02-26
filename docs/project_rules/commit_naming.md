# Commit Naming Rules

## Overview
Commit messages should be clear, meaningful, and follow a consistent structure to improve collaboration and version tracking.

## Commit Message Format
Each commit message must include the following parts:
```
(type): Commit message

[Optional Body]

[Optional Footer]
```

- **Type**: Describes the purpose of the commit (e.g., feat, fix).
- **Description**: A concise summary of the changes (imperative form, max 70 characters).
- **Body**: A detailed explanation of changes, if necessary.
- **Footer**: References to issues, breaking changes, or metadata.

## Commit Types
The following commit types must be used:
- **(feat)**: Adding a new feature.
- **(fix)**: Fixing a bug.
- **(chore)**: Non-functional updates (e.g., dependency upgrades).
- **(docs)**: Documentation changes only.
- **(test)**: Adding or modifying tests.
- **(refactor)**: Refactoring code without adding new functionality.
- **(style)**: Code formatting or style changes.

## Examples
- **Example 1 (Feature)**:
  ```
  (feat): Add OAuth2.0 support to login API
  ```
- **Example 2 (Bug Fix)**:
  ```
  (fix): Resolve crash on invalid log level

  Added a default fallback log level to handle unexpected inputs gracefully.
  ```
- **Example 3 (Breaking Change)**:
  ```
  (feat): Update the response schema for /users endpoint

  BREAKING CHANGE: The /users endpoint now returns an array instead of an object.
  ```
- **Example 4 (Chore)**:
  ```
  (chore): Upgrade Django to version 4.1
  ```

## Additional Rules
- Keep the subject line (type + description) under **70 characters**.
- Use the **imperative mood** for the description (e.g., "Add support" not "Added support").
- Include references to issues using `Fixes #<issue-number>` in the footer, if applicable.

## Tools to Enforce Rules
- **Optional**: Use tools like `commitlint` to validate commit messages.
- Example pre-commit hook:
  ```bash
  npx commitlint --edit $1
  ```
