# Makefile for tinycua-sdk

# Variables
PYTHON ?= python3
UV ?= uv
SRC ?= tinycua_sdk

.PHONY: install lint test coverage complexity clean precommit-install check run

# Install dependencies
install:
	$(UV) pip install -e ".[dev]"

# Run SDK example (local mode)
run:
	$(PYTHON) examples/01_agent_basic.py

# Install pre-commit hooks
precommit-install:
	$(UV) pip install -e ".[lint]"
	pre-commit install

# Run all checks (lint + complexity)
check:
	@echo "=== Running Ruff Lint ==="
	ruff check $(SRC)/
	@echo ""
	@echo "=== Running Ruff Format ==="
	ruff format --check $(SRC)/
	@echo ""
	@echo "=== Running Cognitive Complexity ==="
	@radon cc $(SRC)/ --min=A --max=15 -s; \
	if [ $$? -eq 0 ]; then \
		echo "No functions exceed complexity threshold (max=15)"; \
	fi
	@echo ""
	@echo "=== All checks passed ==="

# Run pre-commit hooks on all files
precommit:
	pre-commit run --all-files

# Run linter (Ruff)
lint:
	ruff check $(SRC)/
	ruff format --check $(SRC)/

# Run linter with auto-fix
lint-fix:
	ruff check $(SRC)/ --fix
	ruff format $(SRC)/

# Run tests
test:
	pytest tests/unit/ -v

# Run integration tests
test-integration:
	pytest tests/integration/ -v -m integration

# Run all tests
test-all:
	pytest tests/ -v

# Run tests with coverage
coverage:
	pytest tests/unit/ --cov=$(SRC) --cov-report=html --cov-report=term-missing

# Run cognitive complexity analysis (radon)
complexity:
	radon cc $(SRC)/ --min=A --max=15

# Clean up artifacts
clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml dist build *.egg-info htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Default target
help:
	@echo "Available targets:"
	@echo "  install           - Install dependencies"
	@echo "  precommit-install - Install and configure pre-commit hooks"
	@echo "  check             - Run all checks (lint + complexity)"
	@echo "  precommit         - Run pre-commit hooks on all files"
	@echo "  lint              - Run linter (ruff)"
	@echo "  lint-fix          - Run linter with auto-fix"
	@echo "  test              - Run unit tests"
	@echo "  test-integration  - Run integration tests"
	@echo "  test-all          - Run all tests"
	@echo "  coverage          - Run tests with coverage"
	@echo "  complexity        - Run complexity analysis"
	@echo "  clean             - Clean up artifacts"
