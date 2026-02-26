# TINYCUA_RUNNER

Execution engine and workflow orchestration for the TINYCUA project.

## Folder Structure
```
TINYCUA_RUNNER/
├── docs/                      # Documentation directory
├── tinycua_runner/            # Source code
├── tests/                     # Testing files
├── specs/                     # Specifications and design docs
├── pyproject.toml             # Configuration for Python tooling
├── Makefile                   # Build and task automation
└── README.md                  # Subproject overview
```

## Setup Instructions
1. Create a virtual environment:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```
   make install
   ```
3. Run tests:
   ```
   make test
   ```
