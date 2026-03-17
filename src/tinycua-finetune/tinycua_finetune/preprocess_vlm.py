#!/usr/bin/env python3
"""
VLM Data Preprocessor for TINYCUA Fine-Tuning

Handles:
- Loading images from paths
- Multimodal tokenization (text + images)
- Prompt formatting with special tokens for tool calls

Used with VLM models like Qwen2.5-VL-7B-Instruct
"""

import json
from pathlib import Path
from typing import Any

from transformers import AutoProcessor


def load_vlm_dataset(jsonl_path: Path) -> list[dict[str, Any]]:
    """
    Load VLM training records from JSONL.

    Args:
        jsonl_path: Path to the JSONL file.

    Returns:
        List of VLM records with image paths.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If records are missing required fields.
    """
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Dataset not found: {jsonl_path}")

    records = []
    required_fields = ["id", "instruction", "image", "tool_calls", "output"]

    with open(jsonl_path) as f:
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
        raise ValueError(f"Dataset is empty: {jsonl_path}")

    return records


def format_tool_call(tool_call: dict[str, Any]) -> str:
    """
    Format a tool call with special tokens.

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


def format_vlm_prompt(record: dict[str, Any]) -> str:
    """
    Format a VLM record into a prompt string.

    Args:
        record: VLM record with instruction and tool_calls.

    Returns:
        Formatted prompt string.
    """
    instruction = record.get("instruction", "")
    tool_calls = record.get("tool_calls", [])
    output = record.get("output", "")

    tool_calls_text = ""
    if tool_calls:
        tool_calls_text = "\n".join(format_tool_call(tc) for tc in tool_calls)
        tool_calls_text += "\n"

    prompt = f"""### Instruction:
{instruction}

### Response:
{tool_calls_text}{output}"""

    return prompt


def load_image(image_path: str | Path) -> Any:
    """
    Load an image from path.

    Args:
        image_path: Path to the image file.

    Returns:
        PIL Image or image tensor.
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow is required for image loading: pip install Pillow")

    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    return Image.open(img_path).convert("RGB")


def preprocess_vlm_batch(
    records: list[dict[str, Any]],
    processor: AutoProcessor,
    max_length: int = 512,
    vision_max_resolution: int = 448,
) -> dict[str, Any]:
    """
    Preprocess a batch of VLM records.

    Args:
        records: List of VLM records.
        processor: Qwen2VLP processor.
        max_length: Maximum text sequence length.
        vision_max_resolution: Maximum image resolution.

    Returns:
        Dict with input_ids, pixel_values, attention_mask, and labels.
    """
    prompts = [format_vlm_prompt(record) for record in records]
    images = [load_image(record["image"]) for record in records]

    text_inputs = processor(
        text=prompts,
        images=images,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=max_length,
    )

    input_ids = text_inputs["input_ids"]
    attention_mask = text_inputs["attention_mask"]
    pixel_values = text_inputs["pixel_values"]
    image_grid = text_inputs.get("image_grid")

    labels = input_ids.clone()

    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "pixel_values": pixel_values,
        "image_grid": image_grid,
        "labels": labels,
    }


def get_vlm_dataset(
    jsonl_path: Path,
    processor: AutoProcessor,
    max_length: int = 512,
    vision_max_resolution: int = 448,
) -> list[dict[str, Any]]:
    """
    Load and preprocess a VLM dataset.

    Args:
        jsonl_path: Path to JSONL file.
        processor: Qwen2VLP processor.
        max_length: Maximum sequence length.
        vision_max_resolution: Maximum image resolution.

    Returns:
        List of preprocessed records.
    """
    records = load_vlm_dataset(jsonl_path)
    return records
