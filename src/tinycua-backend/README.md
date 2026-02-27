# tinycua-backend

Backend services and core API functionality for the TINYCUA project.

## Folder Structure
```
tinycua-backend/
├── docs/                      # Documentation directory
├── tinycua_backend/           # Source code
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
