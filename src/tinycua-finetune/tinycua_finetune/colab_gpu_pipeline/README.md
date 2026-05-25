# Colab GPU Pipeline — Gemma 4 E4B IT Fine-Tuning

Modular Python implementation of the fine-tuning pipeline from `colab_gpu_pipeline_finetune_gemma_e4b-test.ipynb`.

## Pipeline Steps

| File | Step |
|------|------|
| `config.py` | All hyperparameters (model name, LoRA rank, paths, seeds) |
| `api_setup.py` | Login to W&B, HuggingFace, mount Google Drive |
| `install_deps.py` | Install unsloth + dependencies (Colab or local) |
| `gpu_detection.py` | Detect GPU(s) and print VRAM info |
| `load_model.py` | Load Gemma 4 E4B IT with 4-bit NF4 quantization |
| `lora_config.py` | Apply QLoRA adapters (r=64, RSLoRA) |
| `dataset_loading.py` | Load hermes-agent-reasoning-traces + convert ShareGPT |
| `apply_template.py` | Apply gemma-4 chat template to dataset |
| `train.py` | SFTTrainer setup (test 20 steps) + execution + full 1-epoch |
| `evaluate.py` | ToolBench inference-based evaluation |
| `push_to_hub.py` | Push LoRA adapter to HuggingFace Hub |
| `save_model.py` | Save merged 4-bit model + GGUF Q4_K_M export |
| `pipeline.py` | Orchestrator that runs the full pipeline end-to-end |

## Usage

### Colab

```python
from colab_gpu_pipeline.pipeline import run_test_pipeline

run_test_pipeline(install_first=True)
```

For Colab, `install_first=True` handles dependency installation. Otherwise, skip it if you already ran the install cell.

### Local (Linux with NVIDIA GPU)

```bash
# 1. Install unsloth
pip install unsloth

# 2. Set environment variables
export WANDB_API_KEY=your_wandb_key
export HF_TOKEN=your_hf_token

# 3. Run pipeline
python -c "
from colab_gpu_pipeline.pipeline import run_test_pipeline
run_test_pipeline(install_first=False, run_eval=True, push_adapter=True)
"
```

### Run Individual Steps

```python
from colab_gpu_pipeline import (
    detect_gpu,
    load_model_and_tokenizer,
    apply_lora,
    load_raw_dataset,
    preprocess_dataset,
    apply_template_to_dataset,
    setup_trainer,
    run_training,
    run_evaluation,
    push_lora_adapter,
    save_merged_and_gguf,
)
from colab_gpu_pipeline import config

detect_gpu()
model, tokenizer = load_model_and_tokenizer()
model = apply_lora(model)

dataset = load_raw_dataset()
processed = preprocess_dataset(dataset)
tokenizer, dataset_final = apply_template_to_dataset(tokenizer, processed)

trainer = setup_trainer(model, tokenizer, dataset_final)
run_training(trainer)
```

### Full Training (1 Epoch)

```python
from colab_gpu_pipeline.pipeline import run_full_training

run_full_training(model, tokenizer, dataset_final)
```

## Local Environment Setup

### Requirements

| Component | Requirement |
|-----------|-------------|
| GPU | NVIDIA GPU with >=16GB VRAM (T4, V100, A100, RTX 4090) |
| RAM | >=32GB system RAM |
| Storage | >=50GB free (for model weights + dataset) |
| CUDA | CUDA 12.1+ |
| Python | 3.10 - 3.12 |

### Recommended Setup (Conda)

```bash
conda create -n tinycua-finetune python=3.12
conda activate tinycua-finetune
pip install --upgrade pip

# Core ML frameworks
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Unsloth + ecosystem
pip install unsloth unsloth_zoo bitsandbytes accelerate xformers triton

# Training
pip install transformers>=5.3.0 trl>=0.22.2 peft datasets

# Utilities
pip install sentencepiece protobuf huggingface_hub>=0.34.0 wandb tqdm
```

### Verify Setup

```bash
python -c "
import torch
from unsloth import FastModel
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB')
"
```

### Environment Variables

```bash
export WANDB_API_KEY=your_wandb_api_key
export HF_TOKEN=your_huggingface_token
export PYTORCH_ALLOC_CONF=expandable_segments:True
```

### Memory Notes

- Gemma 4 E4B IT (4-bit NF4) uses ~10GB VRAM for inference, ~14GB during training
- Test run (20 steps) takes ~15 minutes on a T4
- Full training (1 epoch, ~7644 samples) takes 4-6 hours on a T4
- Use `save_steps=50` and `save_total_limit=5` to manage disk space
- Checkpoint auto-resume: re-run the training cell and it picks up from the last checkpoint

## File Structure

```
colab_gpu_pipeline/
├── __init__.py           # Re-exports all public functions
├── config.py             # Hyperparameters and paths
├── api_setup.py          # API key login (W&B, HF, GDrive)
├── install_deps.py       # Dependency installation
├── gpu_detection.py      # GPU detection
├── load_model.py         # Model + tokenizer loading
├── lora_config.py        # LoRA adapter configuration
├── dataset_loading.py    # Dataset loading + ShareGPT conversion
├── apply_template.py     # Chat template application
├── train.py              # SFTTrainer setup + training execution
├── evaluate.py           # ToolBench evaluation harness
├── push_to_hub.py        # Push LoRA adapter to HF Hub
├── save_model.py         # Save merged 4-bit + GGUF export
├── pipeline.py           # Full pipeline orchestrator
└── README.md             # This file
```
