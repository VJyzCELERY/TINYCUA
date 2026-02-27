# Project Structure

## Overview
TINYCUA is organized to facilitate modular subproject development and collaboration. Below is the general structure:

```
TINYCUA/
├── docs/                          # Main documentation
│   ├── agents/                    # AI agent rules and guidelines
│   └── project_rules/             # Coding standards, testing, logging rules
├── specs/                         # Project-level specifications
├── src/                           # Subprojects
│   ├── tinycua-backend/           # Backend services
│   ├── tinycua-runner/            # Execution engine
│   └── tinycua-sdk/               # Developer SDK
├── .gitignore
├── AGENTS.md
├── Makefile
├── PROJECT-GUIDELINES.md
└── README.md
```

Subprojects inherit coding standards and documentation rules from TINYCUA but may define specific rules in their `docs/project_rules/` folder.

---

### Standard Makefile for Subprojects
All subprojects must include a `Makefile` to simplify common operations. Below are the predefined targets:

- **install**: Installs all dependencies from `requirements.txt`.
- **lint**: Runs the linter (Ruff) for code style checks.
- **test**: Runs the test suite using Pytest.
- **coverage**: Runs tests with code coverage and generates an HTML report.
- **clean**: Removes temporary files, artifacts, and caches.

#### Example Usage:
```bash
# Install dependencies
make install

# Run linting
make lint

# Run tests
make test

# Check coverage
make coverage

# Clean the project
make clean
```
