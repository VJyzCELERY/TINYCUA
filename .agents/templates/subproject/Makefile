# Makefile for sub-project-template

.PHONY: install lint test coverage complexity clean

# Install dependencies
install:
	uv sync

# Run linter (Ruff)
lint:
	uv run ruff check .

# Run tests
test:
	uv run pytest

# Run tests with coverage
coverage:
	uv run pytest --cov=src --cov-report=html

# Run cognitive complexity analysis (radon)
complexity:
	uv run radon cc . -a -nc
	uv run radon mi . -n B

# Clean up artifacts
clean:
	rm -rf .pytest_cache .coverage coverage.xml dist build *.egg-info
