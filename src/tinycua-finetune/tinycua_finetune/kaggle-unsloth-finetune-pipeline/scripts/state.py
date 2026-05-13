"""Shared state for pipeline scripts.

This module holds global state that is shared across pipeline scripts.
Each script should import and use these variables.
"""

model = None
tokenizer = None
dataset = None
dataset_final = None
processed = None
trainer = None

wandb_key = None
hf_token = None
output_directory = "/kaggle/working/"

RANDOM_SEED = 3407
LEARNING_RATE = 2e-4
LORA_RANK = 64
MAX_CONTEXT_LENGTH = 2048

GGUF_SUCCESS = False
gguf_path = None