# Makefile for agent-benchmark

SRC ?= agent_benchmark

.PHONY: install lint lint-fix test test-unit test-integration clean setup run status help

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

setup:
	@bash benchmark.sh setup

run:
	@bash benchmark.sh run $(ARGS)

run-model:
	@bash benchmark.sh run --model $(MODEL) $(ARGS)

run-agent:
	@bash benchmark.sh run --agent $(AGENT) $(ARGS)

run-category:
	@bash benchmark.sh run --category $(CATEGORY) $(ARGS)

status:
	@bash benchmark.sh status

help:
	@bash benchmark.sh help
	@echo ""
	@echo "Make targets:"
	@echo "  make install        - Install Python dependencies"
	@echo "  make lint           - Run linting checks"
	@echo "  make lint-fix       - Fix linting issues"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make setup          - Full setup (deps, images, data, env)"
	@echo "  make run            - Run all agents sequentially"
	@echo "  make run-model      - Run with specific model (MODEL=name)"
	@echo "  make run-agent      - Run specific agent (AGENT=name)"
	@echo "  make run-category   - Run specific category (CATEGORY=name)"
	@echo "  make status         - Show latest results"
	@echo ""
	@echo "Examples:"
	@echo "  make setup"
	@echo "  make run"
	@echo "  make run-model MODEL=openrouter/openai/gpt-5.5"
	@echo "  make run-agent AGENT=hermesagent"
	@echo "  make run-category CATEGORY=01_Productivity_Flow"
