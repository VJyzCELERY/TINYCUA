# Makefile for tinycua-finetune
# Target: RTX 5080 16GB VRAM + 32GB RAM

# Variables
PYTHON ?= python3
SHELL := /bin/bash

.PHONY: install lint test coverage complexity clean \
        download-model generate-dataset generate-vlm-dataset \
        train-qlora train-lora train-offload train-vlm \
        convert

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

# Download base model from HuggingFace
# Default: Qwen/Qwen2.5-VL-7B-Instruct
MODEL_ID ?= Qwen/Qwen2.5-VL-7B-Instruct
MODEL_DIR ?= models/base
download-model:
	bash scripts/download_model.sh $(MODEL_ID) $(MODEL_DIR)

# Generate text training dataset from tool manifests
# Default: data/examples/tools -> data/examples/train.jsonl
TOOLS_DIR ?= data/examples/tools
OUTPUT_JSONL ?= data/examples/train.jsonl
generate-dataset:
	$(PYTHON) -m tinycua_finetune.synthesize_dataset \
		--tools-dir $(TOOLS_DIR) \
		--output $(OUTPUT_JSONL)

# Generate VLM training dataset with screenshot references
# Creates: data/examples/train_vlm.jsonl + placeholder screenshots
NUM_RECORDS ?= 10
OUTPUT_VLM ?= data/examples/train_vlm.jsonl
generate-vlm-dataset:
	$(PYTHON) scripts/generate_vlm_dataset.py \
		--tools-dir $(TOOLS_DIR) \
		--output $(OUTPUT_VLM) \
		--num-records $(NUM_RECORDS) \
		--create-screenshots

# Fine-tune with QLoRA (default — 7B on 16 GB VRAM)
# Usage: make train-qlora MODEL=<path> DATA=<path> OUTPUT=<path>
MODEL   ?= models/base
DATA    ?= data/examples/train.jsonl
OUTPUT  ?= models/adapter
train-qlora:
	$(PYTHON) -m tinycua_finetune.train \
		--model $(MODEL) \
		--data $(DATA) \
		--output-dir $(OUTPUT) \
		--mode qlora

# Fine-tune with LoRA (float16 — higher memory, better quality)
# Usage: make train-lora MODEL=<path> DATA=<path> OUTPUT=<path>
train-lora:
	$(PYTHON) -m tinycua_finetune.train \
		--model $(MODEL) \
		--data $(DATA) \
		--output-dir $(OUTPUT) \
		--mode lora

# Fine-tune with CPU offload (experimental — 13B on 16 GB VRAM + 32 GB RAM)
# Usage: make train-offload MODEL=<path> DATA=<path> OUTPUT=<path>
OFFLOAD_DIR ?= /tmp/tinycua-offload
train-offload:
	$(PYTHON) -m tinycua_finetune.train \
		--model $(MODEL) \
		--data $(DATA) \
		--output-dir $(OUTPUT) \
		--mode offload \
		--offload-dir $(OFFLOAD_DIR)

# Fine-tune with VLM mode (Vision-Language)
# Freeze vision encoder, LoRA on LLM only
# Usage: make train-vlm MODEL=<path> DATA=<path> OUTPUT=<path>
DATA_VLM ?= data/examples/train_vlm.jsonl
train-vlm:
	$(PYTHON) -m tinycua_finetune.train \
		--model $(MODEL) \
		--data $(DATA_VLM) \
		--output-dir $(OUTPUT) \
		--mode vlm

# Merge adapter and convert to GGUF
# Usage: make convert MODEL=<path> ADAPTER=<path> OUTPUT=<path>
ADAPTER ?= models/adapter
convert:
	$(PYTHON) -m tinycua_finetune.convert_to_gguf \
		--base-model $(MODEL) \
		--adapter-dir $(ADAPTER) \
		--output-dir $(OUTPUT)

# Full pipeline: download -> generate -> train -> convert
# This runs the complete fine-tuning pipeline
pipeline:
	@echo "=== Stage 1: Download Model ==="
	$(MAKE) download-model
	@echo ""
	@echo "=== Stage 2: Generate VLM Dataset ==="
	$(MAKE) generate-vlm-dataset
	@echo ""
	@echo "=== Stage 3: Train with QLoRA ==="
	$(MAKE) train-qlora
	@echo ""
	@echo "=== Stage 4: Convert to GGUF ==="
	$(MAKE) convert
	@echo ""
	@echo "=== Pipeline Complete! ==="
	@echo "GGUF model: $(OUTPUT)/model.gguf"

# Quick test: generate small dataset and run 1 step training
# For smoke testing the pipeline
smoke-test:
	$(MAKE) generate-vlm-dataset NUM_RECORDS=5
	$(MAKE) train-qlora DATA=data/examples/train_vlm.jsonl OUTPUT=models/test_adapter EPOCHS=1
