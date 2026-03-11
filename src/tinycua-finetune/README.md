# tinycua-finetune

Fine-tuning pipeline for open-weight LLMs and vision-LMMs to perform tool-use and agentic
behavior. Produces LoRA adapter checkpoints (safetensors) and GGUF artifacts ready for
local inference via llama.cpp.

## Folder Structure

```
tinycua-finetune/
├── data/
│   └── examples/              # Example tool manifests and JSONL training datasets
├── docs/
│   ├── agents/                # AI agent rules for this subproject
│   └── examples/              # Example scripts
├── specs/                     # Specifications and design documents
├── tests/
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration / smoke tests
├── tinycua_finetune/          # Source code (Python package)
├── Makefile                   # Build and task automation
├── pyproject.toml             # Tooling configuration (Ruff, pytest)
└── README.md                  # This file
```

## Hardware Target

| Model Size | Mode              | Min GPU VRAM | System RAM |
|------------|-------------------|--------------|------------|
| 7B         | QLoRA (default)   | 12–16 GB     | 16 GB      |
| 13B        | QLoRA + offload   | 16 GB        | 32 GB      |

Tested hardware: Intel Core Ultra 275HX, 32 GB DDR5, NVIDIA RTX 5080 (16 GB VRAM).

## Setup Instructions

1. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   make install
   ```
3. Run tests:
   ```bash
   make test
   ```

## Quick Start

### Synthesize a training dataset from local tools

```bash
python -m tinycua_finetune.synthesize_dataset \
  --tools-dir data/examples/tools \
  --output data/examples/train.jsonl
```

### Fine-tune with QLoRA (7B, primary path)

```bash
make train-qlora MODEL=path/to/base DATA=data/examples/train.jsonl OUTPUT=models/adapter
```

### Fine-tune with CPU offload (experimental — 13B)

```bash
make train-offload MODEL=path/to/base DATA=data/examples/train.jsonl OUTPUT=models/adapter
```

### Merge adapter and convert to GGUF

```bash
make convert MODEL=path/to/base ADAPTER=models/adapter OUTPUT=models/
```

## Training Modes

| Mode      | Description                                           | Use Case          |
|-----------|-------------------------------------------------------|-------------------|
| `qlora`   | 4-bit quantized base + LoRA (default)                 | 7B on 16 GB VRAM  |
| `lora`    | float16 base + LoRA (higher memory)                   | Smaller models    |
| `offload` | QLoRA + Accelerate CPU offload (experimental)         | 13B on 16 GB VRAM |

## Specifications

See `specs/spec.md` and `specs/design.md` for requirements and architecture details.
Authoritative root-level specs live at `specs/tinycua-finetune/` in the repo root.

## Make Targets

| Target           | Description                                      |
|------------------|--------------------------------------------------|
| `make install`   | Install all dependencies from `requirements.txt` |
| `make lint`      | Run Ruff linter                                  |
| `make test`      | Run all tests with pytest                        |
| `make coverage`  | Run tests with HTML coverage report              |
| `make complexity`| Radon cognitive complexity audit                 |
| `make clean`     | Remove build artifacts and caches                |
| `make train-qlora`   | Run QLoRA fine-tuning (set MODEL/DATA/OUTPUT)  |
| `make train-offload` | Run offload fine-tuning (experimental 13B)     |
| `make convert`   | Merge adapter and convert to GGUF                |
