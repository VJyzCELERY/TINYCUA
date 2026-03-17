# Makefile for tinycua-runner

# Variables
PYTHON ?= python3
UV ?= uv
SRC ?= tinycua_runner

.PHONY: install lint lint-fix test coverage complexity clean check run

# Install dependencies
install:
	pip3 install -e .

# Run the runner server
run:
	@echo "Starting tinycua-runner..."
	$(PYTHON) -m tinycua_runner.main

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
	pytest

# Run tests with coverage
coverage:
	pytest --cov=$(SRC) --cov-report=html

# Run cognitive complexity analysis (radon)
complexity:
	radon cc $(SRC)/ --min=A --max=15

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

# Clean up artifacts
clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml dist build *.egg-info htmlcov/
