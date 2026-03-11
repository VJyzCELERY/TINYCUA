# Makefile for tinycua-finetune

# Variables
PYTHON ?= python3

.PHONY: install lint test coverage complexity clean train-qlora train-offload convert

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
	pytest --cov=tinycua_finetune --cov-report=html

# Run cognitive complexity analysis (radon)
complexity:
	radon cc . -a -nc
	radon mi . -n B

# Clean up artifacts
clean:
	rm -rf .pytest_cache .coverage coverage.xml dist build *.egg-info htmlcov/ models/

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
