#!/usr/bin/env python3
"""
Data Preprocessor for TINYCUA Fine-Tuning

Handles:
- JSONL dataset loading
- Prompt formatting with special tokens
- Tokenization for training

Special tokens for tool-call structure:
- <tool> </tool>
- <tool_name> </tool_name>
- <tool_args> </tool_args>
- <tool_result> </tool_result>
"""

import json
from pathlib import Path
from typing import Any

from transformers import PreTrainedTokenizer


SPECIAL_TOKENS = [
    "<tool>",
    "</tool>",
    "<tool_name>",
    "</tool_name>",
    "<tool_args>",
    "</tool_args>",
    "<tool_result>",
    "</tool_result>",
]


def load_dataset_from_jsonl(path: Path) -> list[dict[str, Any]]:
    """
    Load and validate training records from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of validated record dicts.

    Raises:
        ValueError: If the file is empty or a record is missing required fields.
        FileNotFoundError: If the path does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    records = []
    required_fields = ["id", "instruction", "tool_calls", "output"]

    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON at line {line_num}: {e}")

            missing_fields = [f for f in required_fields if f not in record]
            if missing_fields:
                raise ValueError(
                    f"Missing required fields {missing_fields} in record {record.get('id', line_num)}"
                )

            records.append(record)

    if not records:
        raise ValueError(f"Dataset is empty: {path}")

    return records


def format_tool_call(tool_call: dict[str, Any]) -> str:
    """
    Format a single tool call into the special token structure.

    Args:
        tool_call: Dict with name, args, and result.

    Returns:
        Formatted string with special tokens.
    """
    name = tool_call.get("name", "")
    args = tool_call.get("args", "")
    result = tool_call.get("result", "")

    formatted = (
        f"<tool>"
        f"<tool_name>{name}</tool_name>"
        f"<tool_args>{args}</tool_args>"
        f"<tool_result>{result}</tool_result>"
        f"</tool>"
    )

    return formatted


def format_prompt(record: dict[str, Any]) -> str:
    """
    Format a single training record into the prompt string.

    Args:
        record: A validated DatasetRecord dict.

    Returns:
        Formatted prompt string ready for tokenization.

    The format follows:
    ### Instruction:
    {instruction}

    ### Input:
    {input}

    ### Response:
    {tool_calls}
    {output}
    """
    instruction = record.get("instruction", "")
    input_text = record.get("input", "")
    tool_calls = record.get("tool_calls", [])
    output = record.get("output", "")

    tool_calls_text = ""
    if tool_calls:
        tool_calls_text = "\n".join(format_tool_call(tc) for tc in tool_calls)
        tool_calls_text += "\n"

    prompt = f"""### Instruction:
{instruction}

### Input:
{input_text}

### Response:
{tool_calls_text}{output}"""

    return prompt


def add_special_tokens(tokenizer: PreTrainedTokenizer) -> int:
    """
    Add special tokens to the tokenizer and resize model embeddings.

    Args:
        tokenizer: The tokenizer to add tokens to.

    Returns:
        Number of tokens added.
    """
    num_added = tokenizer.add_special_tokens(
        {
            "additional_special_tokens": SPECIAL_TOKENS,
        }
    )

    return num_added


def preprocess_dataset(
    records: list[dict[str, Any]],
    tokenizer: PreTrainedTokenizer,
    max_length: int = 512,
) -> dict[str, list]:
    """
    Preprocess a list of records for training.

    Args:
        records: List of dataset records.
        tokenizer: The tokenizer to use.
        max_length: Maximum sequence length.

    Returns:
        Dict with input_ids, attention_mask, and labels.
    """
    prompts = [format_prompt(record) for record in records]

    encodings = tokenizer(
        prompts,
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors="pt",
    )

    input_ids = encodings["input_ids"]
    attention_mask = encodings["attention_mask"]
    labels = input_ids.clone()

    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "labels": labels,
    }


def get_tokenized_dataset(
    jsonl_path: Path,
    tokenizer: PreTrainedTokenizer,
    max_length: int = 512,
) -> dict[str, list]:
    """
    Load and tokenize a JSONL dataset.

    Args:
        jsonl_path: Path to the JSONL file.
        tokenizer: The tokenizer to use.
        max_length: Maximum sequence length.

    Returns:
        Dict with input_ids, attention_mask, and labels.
    """
    records = load_dataset_from_jsonl(jsonl_path)
    return preprocess_dataset(records, tokenizer, max_length)
