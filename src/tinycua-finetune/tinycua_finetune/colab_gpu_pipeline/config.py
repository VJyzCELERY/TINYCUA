import os

RANDOM_SEED = 3407
LEARNING_RATE = 2e-4
LORA_RANK = 64
MAX_SEQ_LENGTH = 2048
MODEL_NAME = "unsloth/gemma-4-E4B-it"
DATASET_CONFIG = "kimi"
DATASET_PATH = "lambda/hermes-agent-reasoning-traces"
EVAL_DATASET_PATH = "younissk/tool-calling-mix"
WANDB_PROJECT = "gemma4-e4b-hermes-agent-reasoning"
OUTPUT_DIR = os.environ.get("TINYCUA_OUTPUT_DIR", "./checkpoints")

LORA_REPO_NAME = "gemma-4-e4b-hermes-agent-reasoning-lora"
GGUF_REPO_NAME = "gemma-4-e4b-hermes-agent-reasoning-gguf"
MERGED_OUTPUT_NAME = "gemma-4-e4b-hermes-merged-4bit"
MERGED_BASE_PATH = os.environ.get("TINYCUA_MERGED_BASE", "./output")

ROLE_MAPPING = {
    "system": "system",
    "human": "user",
    "gpt": "assistant",
    "tool": "tool",
}
