# Makefile for hermes-benchmark

SRC ?= hermes_benchmark

.PHONY: install lint lint-fix test clean

install:
	uv pip install -e ".[dev]"

lint:
	uv run ruff check $(SRC)/
	uv run ruff format --check $(SRC)/

lint-fix:
	uv run ruff check $(SRC)/ --fix
	uv run ruff format $(SRC)/

test:
	uv run pytest tests/ -v

test-unit:
	uv run pytest tests/unit/ -v

test-integration:
	uv run pytest tests/integration/ -v

clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml dist build *.egg-info htmlcov/
