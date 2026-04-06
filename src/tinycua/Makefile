# Makefile for tinycua

PYTHON ?= python3
UV ?= uv
SRC ?= tinycua

.PHONY: install lint test coverage complexity clean

install:
	$(UV) venv --clear
	$(UV) pip install -e ".[dev]"

lint:
	ruff check $(SRC)/
	ruff format --check $(SRC)/

lint-fix:
	ruff check $(SRC)/ --fix
	ruff format $(SRC)/

test:
	pytest tests/ -v

coverage:
	pytest tests/ --cov=$(SRC) --cov-report=html --cov-report=term-missing

complexity:
	radon cc $(SRC)/ --min=A --max=15

clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml dist build *.egg-info htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
