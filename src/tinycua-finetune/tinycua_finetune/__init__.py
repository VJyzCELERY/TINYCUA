"""
TINYCUA Fine-Tuning Pipeline

Fine-tuning pipeline for open-weight LLMs and vision-LMMs to perform tool-use
and agentic behavior. Produces LoRA adapter checkpoints (safetensors) and
GGUF artifacts ready for local inference via llama.cpp.

Target Hardware: RTX 5080 16GB VRAM + 32GB RAM

Usage:
    # Synthesize dataset
    python -m tinycua_finetune.synthesize_dataset --tools-dir data/examples/tools --output data/examples/train.jsonl

    # Train with QLoRA
    python -m tinycua_finetune.train --model models/base --data data/examples/train.jsonl --output-dir models/adapter --mode qlora

    # Convert to GGUF
    python -m tinycua_finetune.convert_to_gguf --base-model models/base --adapter-dir models/adapter --output-dir models/
"""

__version__ = "0.1.0"

from tinycua_finetune.preprocess import (
    SPECIAL_TOKENS,
    add_special_tokens,
    format_prompt,
    format_tool_call,
    get_tokenized_dataset,
    load_dataset_from_jsonl,
    preprocess_dataset,
)

from tinycua_finetune.synthesize_dataset import discover_manifests, synthesize

__all__ = [
    "SPECIAL_TOKENS",
    "add_special_tokens",
    "format_prompt",
    "format_tool_call",
    "get_tokenized_dataset",
    "load_dataset_from_jsonl",
    "preprocess_dataset",
    "discover_manifests",
    "synthesize",
]
