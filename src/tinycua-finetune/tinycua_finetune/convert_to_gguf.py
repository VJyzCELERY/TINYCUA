#!/usr/bin/env python3
"""
GGUF Converter for TINYCUA Fine-Tuning

Merges LoRA adapters into the base model and converts to GGUF format.

Usage:
    python -m tinycua_finetune.convert_to_gguf \
        --base-model path/to/base \
        --adapter-dir path/to/adapter \
        --output-dir path/to/output
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


LLAMA_CPP_CONVERTER_VERSION = "latest"


def check_gguf_converter() -> Optional[Path]:
    """
    Check if llama.cpp converter is available.

    Returns:
        Path to converter script if found, None otherwise.
    """
    possible_paths = [
        Path("llama.cpp/convert.py"),
        Path("../llama.cpp/convert.py"),
        Path(os.path.expanduser("~/llama.cpp/convert.py")),
    ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


def merge_adapter(
    base_model_path: Path,
    adapter_path: Path,
    output_path: Path,
) -> None:
    """
    Merge LoRA adapter into base model.

    Args:
        base_model_path: Path to base model.
        adapter_path: Path to LoRA adapter.
        output_path: Output path for merged model.
    """
    logger.info(f"Loading base model from {base_model_path}")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.float16,
        device_map="cpu",
        trust_remote_code=True,
    )

    logger.info(f"Loading adapter from {adapter_path}")
    model = PeftModel.from_pretrained(base_model, adapter_path)

    logger.info("Merging adapter into base model...")
    merged_model = model.merge_and_unload()

    logger.info(f"Saving merged model to {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)
    merged_model.save_pretrained(output_path)

    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    tokenizer.save_pretrained(output_path)

    logger.info("Merge complete!")


def convert_to_gguf(
    merged_model_path: Path,
    output_path: Path,
    converter_path: Optional[Path] = None,
) -> None:
    """
    Convert merged HF model to GGUF format.

    Args:
        merged_model_path: Path to merged model.
        output_path: Output path for GGUF file.
        converter_path: Path to llama.cpp converter script.
    """
    if converter_path is None:
        converter_path = check_gguf_converter()

    if converter_path is None:
        logger.error(
            "llama.cpp converter not found! Please install llama.cpp:\n"
            "  git clone https://github.com/ggerganov/llama.cpp\n"
            "  cd llama.cpp\n"
            "  pip install -r requirements.txt\n"
            f"Expected converter at: llama.cpp/convert.py"
        )
        raise RuntimeError(
            "GGUF converter not found. Please install llama.cpp and ensure "
            "llama.cpp/convert.py exists, or provide --converter-path"
        )

    output_path.mkdir(parents=True, exist_ok=True)
    gguf_path = output_path / "model.gguf"

    logger.info(f"Converting model to GGUF format...")
    logger.info(f"Converter: {converter_path}")
    logger.info(f"Input: {merged_model_path}")
    logger.info(f"Output: {gguf_path}")

    cmd = [
        sys.executable,
        str(converter_path),
        str(merged_model_path),
        "--outfile",
        str(gguf_path),
        "--outtype",
        "q4_0",
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(result.stdout)
        logger.info("GGUF conversion complete!")
    except subprocess.CalledProcessError as e:
        logger.error(f"Conversion failed: {e.stderr}")
        raise RuntimeError(f"GGUF conversion failed: {e.stderr}")


def main():
    parser = argparse.ArgumentParser(description="Convert model to GGUF format")

    parser.add_argument(
        "--base-model",
        type=str,
        required=True,
        help="Path to base model",
    )
    parser.add_argument(
        "--adapter-dir",
        type=str,
        required=True,
        help="Path to LoRA adapter",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Output directory for GGUF",
    )
    parser.add_argument(
        "--skip-merge",
        action="store_true",
        help="Skip merge step (use if base + adapter already merged)",
    )
    parser.add_argument(
        "--converter-path",
        type=str,
        help="Path to llama.cpp convert.py script",
    )

    args = parser.parse_args()

    base_model_path = Path(args.base_model)
    adapter_path = Path(args.adapter_dir)
    output_dir = Path(args.output_dir)
    merged_path = output_dir / "merged"

    if not base_model_path.exists():
        raise FileNotFoundError(f"Base model not found: {base_model_path}")

    if not adapter_path.exists() and not args.skip_merge:
        raise FileNotFoundError(f"Adapter not found: {adapter_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_merge:
        logger.info("=" * 50)
        logger.info("STEP 1: Merging adapter into base model")
        logger.info("=" * 50)
        merge_adapter(base_model_path, adapter_path, merged_path)
    else:
        logger.info("Skipping merge step (--skip-merge)")
        merged_path = base_model_path

    converter_path = Path(args.converter_path) if args.converter_path else None

    logger.info("=" * 50)
    logger.info("STEP 2: Converting to GGUF format")
    logger.info("=" * 50)
    convert_to_gguf(merged_path, output_dir, converter_path)

    logger.info("=" * 50)
    logger.info("ALL DONE!")
    logger.info(f"GGUF model: {output_dir / 'model.gguf'}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
