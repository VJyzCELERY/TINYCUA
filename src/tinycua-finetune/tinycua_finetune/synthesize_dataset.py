#!/usr/bin/env python3
"""
Dataset Synthesizer for TINYCUA Fine-Tuning

Generates training data from tool manifests (text-only mode).

Usage:
    python -m tinycua_finetune.synthesize_dataset \
        --tools-dir data/examples/tools \
        --output data/examples/train.jsonl
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def discover_manifests(tools_dir: Path) -> list[dict[str, Any]]:
    """
    Recursively discover manifest.json files under tools_dir.

    Args:
        tools_dir: Root directory containing tool subdirectories.

    Returns:
        List of parsed ToolManifest dicts.

    Raises:
        FileNotFoundError: If tools_dir does not exist.
    """
    if not tools_dir.exists():
        raise FileNotFoundError(f"Tools directory not found: {tools_dir}")

    manifests = []
    for tool_path in tools_dir.iterdir():
        if tool_path.is_dir():
            manifest_file = tool_path / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file) as f:
                    manifest = json.load(f)
                    manifests.append(manifest)
                    logger.info(f"Found manifest: {manifest.get('name', 'unknown')}")

    if not manifests:
        raise ValueError(f"No tool manifests found in {tools_dir}")

    return manifests


def synthesize(tools_dir: Path, output_path: Path) -> None:
    """
    Generate a JSONL training dataset from discovered tool manifests.

    Args:
        tools_dir: Root directory containing tool subdirectories.
        output_path: Destination JSONL file path.

    Raises:
        ValueError: If a manifest is missing required fields.
    """
    manifests = discover_manifests(tools_dir)

    required_fields = ["name", "description", "args_schema", "example_call", "dry_run_output"]
    records = []

    for idx, manifest in enumerate(manifests):
        missing = [f for f in required_fields if f not in manifest]
        if missing:
            logger.warning(f"Skipping {manifest.get('name', idx)}: missing fields {missing}")
            continue

        example_call = manifest["example_call"]

        instruction = f"Use the {manifest['name']} tool to {manifest['description'].lower()}"

        tool_call = {
            "name": manifest["name"],
            "args": json.dumps(example_call),
            "result": manifest["dry_run_output"],
        }

        record = {
            "id": f"train_{idx:03d}",
            "instruction": instruction,
            "input": "",
            "tool_calls": [tool_call],
            "output": manifest["dry_run_output"],
        }

        records.append(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    logger.info(f"Generated {len(records)} training records")
    logger.info(f"Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Synthesize training dataset from tool manifests")
    parser.add_argument(
        "--tools-dir",
        type=Path,
        default=Path("data/examples/tools"),
        help="Directory containing tool manifests",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/examples/train.jsonl"),
        help="Output JSONL file path",
    )

    args = parser.parse_args()

    synthesize(args.tools_dir, args.output)


if __name__ == "__main__":
    main()
