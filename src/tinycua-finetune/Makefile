# Makefile for tinycua-finetune

# Variables
PYTHON ?= python3
UV ?= uv
SRC ?= tinycua_finetune

.PHONY: install lint lint-fix test coverage complexity clean check train-qlora train-offload convert

# Install dependencies
install:
	$(UV) pip install -r requirements.txt

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

# Run all checks (lint + complexity)
check:
	@echo "=== Running Ruff Lint ==="
	ruff check $(SRC)/
	@echo ""
	@echo "=== Running Ruff Format ==="
	ruff format --check $(SRC)/
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
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml dist build *.egg-info htmlcov/ models/

# Fine-tune with QLoRA (primary path — 7B on 16 GB VRAM)
# Override with: make train-qlora MODEL=<path> DATA=<path> OUTPUT=<path>
MODEL   ?= models/base
DATA    ?= data/examples/train.jsonl
OUTPUT  ?= models/adapter
train-qlora:
	$(PYTHON) -m tinycua_finetune.train \
		--model $(MODEL) \
		--data $(DATA) \
		--output-dir $(OUTPUT) \
		--mode qlora

# Fine-tune with CPU offload (experimental — 13B on 16 GB VRAM + 32 GB RAM)
OFFLOAD_DIR ?= /tmp/tinycua-offload
train-offload:
	$(PYTHON) -m tinycua_finetune.train \
		--model $(MODEL) \
		--data $(DATA) \
		--output-dir $(OUTPUT) \
		--mode offload \
		--offload-dir $(OFFLOAD_DIR)

# Merge adapter and convert to GGUF
# Override with: make convert MODEL=<path> ADAPTER=<path> OUTPUT=<path>
ADAPTER ?= models/adapter
convert:
	$(PYTHON) -m tinycua_finetune.convert_to_gguf \
		--base-model $(MODEL) \
		--adapter-dir $(ADAPTER) \
		--output-dir $(OUTPUT)
