# Makefile for sub-project-template

# Variables
PYTHON ?= python3

.PHONY: install lint test coverage complexity clean

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
	pytest --cov=src --cov-report=html

# Run cognitive complexity analysis (radon)
complexity:
	radon cc . -a -nc
	radon mi . -n B

# Clean up artifacts
clean:
	rm -rf .pytest_cache .coverage coverage.xml dist build *.egg-info
