# Makefile for tinycua-backend

SRC ?= tinycua_backend

.PHONY: install lint lint-fix test clean

install:
	uv pip install -e .

lint:
	uv run ruff check $(SRC)/
	uv run ruff format --check $(SRC)/

lint-fix:
	uv run ruff check $(SRC)/ --fix
	uv run ruff format $(SRC)/

test:
	@echo "tinycua-backend is a skeleton; no tests are defined yet."

clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml dist build *.egg-info htmlcov/
