# Makefile for tinycua-sdk

SRC ?= tinycua_sdk

.PHONY: install lint lint-fix test test-unit test-integration coverage complexity clean check precommit-install precommit

install:
	uv pip install -e ".[dev]"

precommit-install:
	uv pip install -e ".[lint]"
	uv run pre-commit install

lint:
	uv run ruff check $(SRC)/
	uv run ruff format --check $(SRC)/

lint-fix:
	uv run ruff check $(SRC)/ --fix
	uv run ruff format $(SRC)/

test-unit:
	uv run pytest tests/unit/ -v --tb=short

test-integration:
	uv run pytest tests/integration/ -v --tb=short --log-cli-level=INFO

test:
	uv run pytest

coverage:
	uv run pytest tests/unit/ --cov=$(SRC) --cov-report=html --cov-report=term-missing

complexity:
	uv run radon cc $(SRC)/ --min=A --max=15

check: lint complexity

precommit:
	uv run pre-commit run --all-files

clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml dist build *.egg-info htmlcov/
