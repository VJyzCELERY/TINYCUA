# Makefile for tinycua

SRC ?= tinycua

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
	@echo "tinycua is a skeleton; no tests are defined yet."

clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml dist build *.egg-info htmlcov/
