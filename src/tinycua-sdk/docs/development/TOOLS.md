# Development Tools Specification

This document defines the standard tools used across all subprojects in the TINYCUA monorepo.

---

## Linting & Code Quality

### Ruff
- **Purpose**: Fast Python linter written in Rust
- **Config**: `pyproject.toml` `[tool.ruff.lint]`
- **Rules**:
  - E, W, F: pycodestyle, pyflakes, pyflakes
  - D: pydocstyle (docstring conventions)
  - C901: mccabe (cognitive complexity, max 15)
- **Install**: `pip install ruff`
- **Usage**: `ruff check .` or `ruff check --fix .`

### Pre-commit
- **Purpose**: Git hooks for automated checks before commit
- **Config**: `.pre-commit-config.yaml`
- **Install**:
  1. `pip install -e ".[lint]"`
  2. `pre-commit install`
- **Hooks**:
  - `ruff`: Lint and format
  - `trailing-whitespace`: Remove trailing whitespace
  - `end-of-file-fixer`: Ensure files end with newline
  - `check-yaml`: Validate YAML files
  - `check-json`: Validate JSON files
  - `check-toml`: Validate TOML files
  - `check-merge-conflict`: Detect merge conflict markers
  - `cognitive-complexity`: Check complexity (max 15)

---

## Testing

### Pytest
- **Purpose**: Testing framework
- **Config**: `pyproject.toml` `[tool.pytest.ini_options]`
- **Install**: `pip install pytest pytest-asyncio pytest-cov`
- **Markers**:
  - `@pytest.mark.unit` - Fast, no external dependencies
  - `@pytest.mark.integration` - Requires external service
  - `@pytest.mark.lm_studio` - Requires LM Studio
  - `@pytest.mark.backend` - Requires backend server
  - `@pytest.mark.remote_runner` - Requires remote runner
- **Run**: `pytest` or `pytest -m integration`

### Coverage
- **Tool**: pytest-cov
- **Run**: `pytest --cov=src --cov-report=html`
- **Config**: `pyproject.toml` `[tool.coverage.run]`

---

## Complexity Analysis

### Radon
- **Purpose**: Cognitive complexity analysis
- **Install**: `pip install radon`
- **Run**: `radon cc src/ --min=A --max=15`
- **Thresholds**:
  - A (0-10): Simple
  - B (11-20): Moderate
  - C (21-30): Complex
  - D (31-40): Very complex
  - F (41+): Too complex

---

## Task Running

### Make
- **Purpose**: Task automation
- **Config**: `Makefile`
- **Usage**: `make <target>`
- **Targets** (standard):
  - `install`: Install dependencies
  - `lint`: Run linter
  - `test`: Run tests
  - `coverage`: Run with coverage
  - `complexity`: Run complexity analysis
  - `clean`: Clean artifacts

> **Note**: While Make is the standard, it requires GNU Make on Windows. For cross-platform alternatives, consider:
> - **Just**: Rust-based, faster than Make
> - **Taskell**: Python-based, similar to Make
> - **Invoke**: Python-based, uses Python syntax

---

## Dependencies

### pip-tools
- **Purpose**: Pin and resolve dependencies
- **Install**: `pip install pip-tools`
- **Usage**:
  - `pip-compile requirements.in` - Generate pinned requirements
  - `pip-sync requirements.txt` - Sync environment

---

## Standard Makefile Template

```makefile
.PHONY: install lint test coverage complexity clean

install:
	pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

test:
	pytest -m unit -v

coverage:
	pytest --cov=src --cov-report=html --cov-report=term

complexity:
	radon cc src/ --min=A --max=15

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
```

---

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: make lint
      - run: make test
      - run: make coverage
```

---

## Auto-Skip for Integration Tests

When services are unavailable, integration tests should auto-skip:

```python
import pytest

def pytest_collection_modifyitems(config, items):
    skip_lm_studio = pytest.mark.skip(reason="LM Studio not available")
    for item in items:
        if "lm_studio" in item.keywords:
            item.add_marker(skip_lm_studio)
```

Or use `pytest.mark.skipif` with environment checks:

```python
@pytest.mark.skipif(
    not is_lm_studio_available(),
    reason="LM Studio not available"
)
async def test_with_lm_studio():
    ...
```
