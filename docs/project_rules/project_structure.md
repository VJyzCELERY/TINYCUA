# Project Structure

## Overview
TINYCUA is organized to facilitate modular subproject development and collaboration. Below is the general structure:

```
TINYCUA/
├── docs/                          # Main documentation
│   ├── agents/                    # AI agent rules and guidelines
│   └── project_rules/             # Coding standards, testing, logging rules
├── specs/                         # Project-level specifications
│   └── <feature-name>/
│       ├── spec.md                # "what and why" — requirements and acceptance criteria
│       └── design.md             # "how" — architecture and implementation plan
├── src/                           # Subprojects
│   ├── tinycua-backend/           # Backend services
│   ├── tinycua-finetune/          # LLM fine-tuning pipeline
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

## Specs Convention

Specs are **never** stored as flat files directly inside a `specs/` folder. Every spec belongs in a named feature subfolder. This applies at both the project level and inside each subproject.

| Level | Path pattern |
|-------|-------------|
| Project-wide | `specs/<feature-name>/spec.md` and `design.md` |
| Subproject-scoped | `src/<subproject>/specs/<feature-name>/spec.md` and `design.md` |

Subfolder names use `lower-kebab-case`.

---

## Standard Subproject Structure

Each subproject under `src/` follows this layout:

```
src/<subproject>/
├── docs/
│   ├── agents/agent_rules.md      # AI agent rules for this subproject
│   └── examples/example_main.py   # Usage examples
├── specs/
│   ├── README.md                  # Convention guide and features table
│   └── <feature-name>/
│       ├── spec.md
│       └── design.md
├── tests/
│   ├── unit/
│   └── integration/
├── <package>/                     # Python package (lower_snake_case)
├── AGENTS.md
├── Makefile
├── pyproject.toml
└── README.md
```

---

### Standard Makefile for Subprojects
All subprojects must include a `Makefile` to simplify common operations. Below are the predefined targets:

- **install**: Installs all dependencies.
- **lint**: Runs the linter (Ruff) for code style checks.
- **test**: Runs the test suite using pytest.
- **coverage**: Runs tests with code coverage and generates an HTML report.
- **complexity**: Checks cognitive complexity with radon.
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

# Check complexity
make complexity

# Clean the project
make clean
```
