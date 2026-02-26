# Makefile for TINYCUA_SDK

# Variables
PYTHON ?= python3

.PHONY: install lint test coverage clean

# Install dependencies
install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# Run linter (Ruff)
lint:
	ruff .

# Run tests
test:
	pytest

# Run tests with coverage
coverage:
	pytest --cov=tinycua_sdk --cov-report=html

# Clean up artifacts
clean:
	rm -rf .pytest_cache .coverage coverage.xml dist build *.egg-info htmlcov/
