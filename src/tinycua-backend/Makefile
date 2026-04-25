# Makefile for tinycua-backend

# Variables
PYTHON ?= python3
UV ?= uv
SRC ?= tinycua_backend

.PHONY: install lint lint-fix test coverage complexity clean check run
.PHONY: docker-up docker-down docker-logs docker-restart docker-rebuild docker-restart-fresh

# Install dependencies
install:
	$(UV) pip install -e .

# ============================================
# Docker Operations
# ============================================

# Start PostgreSQL
docker-up:
	docker compose up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@docker compose ps

# Stop PostgreSQL
docker-down:
	docker compose down

# View logs
docker-logs:
	docker compose logs -f

# Restart
docker-restart:
	docker compose restart

# Rebuild (stop, remove, rebuild, start)
docker-rebuild:
	docker compose down
	docker compose up -d --build
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@docker compose ps

# Rebuild fresh (with volume deletion - removes all data)
docker-restart-fresh:
	docker compose down -v
	docker compose up -d --build
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@docker compose ps

# ============================================
# Server
# ============================================

# Run the backend server
run: docker-up
	@echo "Starting tinycua-backend..."
	$(PYTHON) -m tinycua_backend.main

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

# Run all checks (lint + complexity + mypy)
check:
	@echo "=== Running Ruff Lint ==="
	ruff check $(SRC)/
	@echo ""
	@echo "=== Running Ruff Format ==="
	ruff format --check $(SRC)/
	@echo ""
	@echo "=== Running Mypy Type Check ==="
	mypy $(SRC)/
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
