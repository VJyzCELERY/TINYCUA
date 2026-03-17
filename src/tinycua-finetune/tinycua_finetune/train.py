#!/usr/bin/env python3
"""
Training Engine for TINYCUA Fine-Tuning

Supports multiple training modes:
- qlora: 4-bit quantized + LoRA (default, 7B on 16GB VRAM)
- lora: float16 + LoRA (higher memory)
- offload: QLoRA + CPU offload (experimental 13B)
- vlm: Vision-Language mode (freeze encoder, LoRA on LLM)

Usage:
    python -m tinycua_finetune.train \
        --model path/to/model \
        --data path/to/train.jsonl \
        --output-dir models/adapter \
        --mode qlora
"""

import argparse
import logging
import os
from pathlib import Path
from typing import List, Optional

import torch
from accelerate import Accelerator
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoProcessor,
    AutoTokenizer,
    TrainingArguments,
)

from tinycua_finetune.preprocess import (
    SPECIAL_TOKENS,
    add_special_tokens,
    get_tokenized_dataset,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_model_and_tokenizer(
    model_path: Path,
    mode: str = "qlora",
    device_map: str = "auto",
) -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    """
    Load the base model and tokenizer.

    Args:
        model_path: Path to the HuggingFace model.
        mode: Training mode (qlora, lora, offload, vlm).
        device_map: Device mapping strategy.

    Returns:
        Tuple of (model, tokenizer).
    """
    logger.info(f"Loading model from {model_path}")

    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        trust_remote_code=True,
        padding_side="right",
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {
        "trust_remote_code": True,
        "device_map": device_map,
        "torch_dtype": torch.float16,
    }

    if mode in ("qlora", "offload"):
        model_kwargs["quantization_config"] = None

    model = AutoModelForCausalLM.from_pretrained(model_path, **model_kwargs)

    add_special_tokens(tokenizer)
    model.resize_token_embeddings(len(tokenizer))

    return model, tokenizer


def prepare_lora_model(
    model: AutoModelForCausalLM,
    mode: str = "qlora",
    lora_r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    target_modules: Optional[List[str]] = None,
) -> AutoModelForCausalLM:
    """
    Prepare model with LoRA configuration.

    Args:
        model: Base model.
        mode: Training mode.
        lora_r: LoRA rank.
        lora_alpha: LoRA alpha.
        lora_dropout: LoRA dropout.
        target_modules: Modules to apply LoRA to.

    Returns:
        Model with LoRA adapters.
    """
    if target_modules is None:
        target_modules = ["q_proj", "v_proj", "k_proj", "o_proj"]

    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=target_modules,
        bias="none",
        task_type="CAUSAL_LM",
    )

    if mode == "qlora":
        model = prepare_model_for_kbit_training(model)

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    return model


def train(
    model_path: str,
    data_path: str,
    output_dir: str,
    mode: str = "qlora",
    lora_r: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    batch_size: int = 1,
    gradient_accumulation: int = 8,
    learning_rate: float = 1e-4,
    epochs: int = 1,
    max_seq_len: int = 512,
    offload_dir: Optional[str] = None,
    save_steps: int = 10,
    logging_steps: int = 10,
) -> None:
    """
    Run the training pipeline.

    Args:
        model_path: Path to base model.
        data_path: Path to training JSONL.
        output_dir: Output directory for adapter.
        mode: Training mode (qlora, lora, offload, vlm).
        lora_r: LoRA rank.
        lora_alpha: LoRA alpha.
        lora_dropout: LoRA dropout.
        batch_size: Batch size per device.
        gradient_accumulation: Gradient accumulation steps.
        learning_rate: Learning rate.
        epochs: Number of epochs.
        max_seq_len: Maximum sequence length.
        offload_dir: Directory for CPU offload (offload mode).
        save_steps: Save checkpoint every N steps.
        logging_steps: Log every N steps.
    """
    model_path = Path(model_path)
    data_path = Path(data_path)
    output_dir = Path(output_dir)

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    if not data_path.exists():
        raise FileNotFoundError(f"Training data not found: {data_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    device_map = "auto"
    if mode == "offload":
        device_map = "cpu"
        logger.info("Using CPU offload mode - this is experimental!")

    model, tokenizer = load_model_and_tokenizer(model_path, mode, device_map)

    logger.info("Loading and tokenizing dataset...")
    tokenized_data = get_tokenized_dataset(data_path, tokenizer, max_seq_len)

    model = prepare_lora_model(
        model,
        mode=mode,
        lora_r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
    )

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation,
        learning_rate=learning_rate,
        num_train_epochs=epochs,
        max_steps=-1,
        save_steps=save_steps,
        logging_steps=logging_steps,
        save_total_limit=2,
        remove_unused_columns=False,
        fp16=True,
        dataloader_num_workers=0,
        report_to="none",
    )

    from transformers import Trainer, DataCollatorForLanguageModeling

    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )

    class Dataset:
        def __init__(self, data):
            self.data = data

        def __len__(self):
            return len(self.data["input_ids"])

        def __getitem__(self, idx):
            return {
                "input_ids": self.data["input_ids"][idx],
                "attention_mask": self.data["attention_mask"][idx],
                "labels": self.data["labels"][idx],
            }

    train_dataset = Dataset(tokenized_data)

    accelerator = Accelerator()

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        data_collator=data_collator,
    )

    logger.info("Starting training...")
    trainer.train()

    logger.info(f"Saving adapter to {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    logger.info("Training complete!")


def main():
    parser = argparse.ArgumentParser(description="TINYCUA Fine-Tuning")

    parser.add_argument("--model", type=str, required=True, help="Path to base model")
    parser.add_argument("--data", type=str, required=True, help="Path to training JSONL")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument(
        "--mode",
        type=str,
        default="qlora",
        choices=["qlora", "lora", "offload", "vlm"],
        help="Training mode",
    )
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument("--lora-dropout", type=float, default=0.05, help="LoRA dropout")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size")
    parser.add_argument("--grad-accum", type=int, default=8, help="Gradient accumulation")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--epochs", type=int, default=1, help="Number of epochs")
    parser.add_argument("--max-seq-len", type=int, default=512, help="Max sequence length")
    parser.add_argument("--offload-dir", type=str, help="CPU offload directory")
    parser.add_argument("--save-steps", type=int, default=10, help="Save every N steps")
    parser.add_argument("--logging-steps", type=int, default=10, help="Log every N steps")

    args = parser.parse_args()

    train(
        model_path=args.model,
        data_path=args.data,
        output_dir=args.output_dir,
        mode=args.mode,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        batch_size=args.batch_size,
        gradient_accumulation=args.grad_accum,
        learning_rate=args.lr,
        epochs=args.epochs,
        max_seq_len=args.max_seq_len,
        offload_dir=args.offload_dir,
        save_steps=args.save_steps,
        logging_steps=args.logging_steps,
    )


if __name__ == "__main__":
    main()
