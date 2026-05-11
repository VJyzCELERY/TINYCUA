"""Step 5: Load Model and Tokenizer.

Loads the Qwen3-4B base model with QLoRA configuration (4-bit NF4 quantization).
Uses Unsloth's FastLanguageModel for memory-efficient loading.
"""

import torch
from transformers import BitsAndBytesConfig
from unsloth import FastLanguageModel

from state import model, tokenizer

print("Loading model...")

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
)

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Qwen3-4B-Base",
    max_seq_length=2048,
    load_in_4bit=True,
    load_in_8bit=False,
    full_finetuning=False,
    quantization_config=bnb_config,
    device_map="auto",
    dtype=torch.float16,
)

print("Model loaded successfully!")
print(f"Model device: {next(model.parameters()).device}")
print("Tokenizer loaded")
print(f"Tokenizer vocab size: {len(tokenizer)}")
print("Using device_map: auto")
print("Setup complete! Ready for LoRA configuration.")


def main():
    print("Step 5 complete: Model and tokenizer loaded")


if __name__ == "__main__":
    main()