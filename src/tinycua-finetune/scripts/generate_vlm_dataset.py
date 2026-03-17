#!/usr/bin/env python3
"""
VLM Dataset Generator for TINYCUA Fine-Tuning

Generates training data from tool manifests with screenshot references.
Each record includes:
- instruction: Natural language task description
- image: Path to screenshot
- tool_calls: Structured tool invocations
- output: Expected model response
"""

import argparse
import json
import os
import random
from pathlib import Path
from typing import Any, Optional


TOOL_INSTRUCTIONS = {
    "click": [
        "Click on the button shown in the screenshot at coordinates ({x}, {y})",
        "The highlighted element should be clicked at position ({x}, {y})",
        "Click at coordinates ({x}, {y}) to interact with the UI element",
    ],
    "type": [
        "Type '{text}' into the input field shown in the screenshot",
        "Enter the text '{text}' at the current cursor position",
        "Input the following text: {text}",
    ],
    "screenshot": [
        "Capture a screenshot of the current screen",
        "Take a screenshot of the visible area",
        "Record the current screen state as an image",
    ],
    "read": [
        "Extract all visible text from the screenshot",
        "What text is displayed on the screen?",
        "Read the content from the current screen",
    ],
    "scroll": [
        "Scroll {direction} by {amount} pixels",
        "Scroll down/up to reveal more content",
        "Move the view {direction} by {amount} pixels",
    ],
}

SCREENSHOT_DESCRIPTIONS = [
    "A login form with username and password fields",
    "A web browser showing a search results page",
    "A desktop with file explorer window open",
    "A text editor with code content",
    "A shopping cart with several items",
    "A settings panel with toggle switches",
    "A chat application with message history",
    "A spreadsheet with data cells",
    "A terminal window with command output",
    "A calendar application with events",
]

VLM_OUTPUTS = {
    "click": "Clicked at ({x}, {y}) with {button} button",
    "type": "Typed '{text}' with {delay}ms character delay",
    "screenshot": "Screenshot captured: {width}x{height} {format}",
    "read": "Extracted text from screen: {char_count} characters found",
    "scroll": "Scrolled {direction} by {amount} pixels",
}


def load_manifests(tools_dir: Path) -> list[dict[str, Any]]:
    """Load all tool manifests from the tools directory."""
    manifests = []
    
    if not tools_dir.exists():
        raise FileNotFoundError(f"Tools directory not found: {tools_dir}")
    
    for tool_path in tools_dir.iterdir():
        if tool_path.is_dir():
            manifest_file = tool_path / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file) as f:
                    manifest = json.load(f)
                    manifests.append(manifest)
    
    if not manifests:
        raise ValueError(f"No tool manifests found in {tools_dir}")
    
    return manifests


def generate_tool_call(manifest: dict[str, Any]) -> dict[str, Any]:
    """Generate a tool call from a manifest's example call."""
    tool_name = manifest["name"]
    example_call = manifest["example_call"]
    dry_run_output = manifest["dry_run_output"]
    
    tool_call = {
        "name": tool_name,
        "args": json.dumps(example_call),
        "result": dry_run_output,
    }
    
    return tool_call


def generate_instruction(manifest: dict[str, Any], example_call: dict[str, Any]) -> str:
    """Generate a natural language instruction for the tool."""
    tool_name = manifest["name"]
    template = random.choice(TOOL_INSTRUCTIONS.get(tool_name, ["Use the {tool} tool"]))
    
    instruction = template
    for key, value in example_call.items():
        instruction = instruction.replace(f"{{{key}}}", str(value))
    
    return instruction


def generate_output(manifest: dict[str, Any], example_call: dict[str, Any]) -> str:
    """Generate the expected model output."""
    tool_name = manifest["name"]
    template = VLM_OUTPUTS.get(tool_name, "Tool executed successfully")
    
    output = template
    for key, value in example_call.items():
        output = output.replace(f"{{{key}}}", str(value))
    
    if tool_name == "screenshot":
        output = output.format(width=1920, height=1080, format="png")
    elif tool_name == "read":
        output = output.format(char_count=random.randint(20, 200))
    
    return output


def generate_vlm_record(
    manifest: dict[str, Any],
    screenshot_path: str,
    record_id: str,
) -> dict[str, Any]:
    """Generate a single VLM training record."""
    example_call = manifest["example_call"]
    
    instruction = generate_instruction(manifest, example_call)
    tool_call = generate_tool_call(manifest)
    output = generate_output(manifest, example_call)
    
    record = {
        "id": record_id,
        "instruction": instruction,
        "image": screenshot_path,
        "tool_calls": [tool_call],
        "output": output,
    }
    
    return record


def generate_dataset(
    tools_dir: Path,
    output_path: Path,
    num_screenshots: int = 10,
    screenshots_dir: Optional[Path] = None,
) -> None:
    """Generate the VLM training dataset."""
    manifests = load_manifests(tools_dir)
    
    if screenshots_dir is None:
        screenshots_dir = tools_dir.parent / "screenshots"
    
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    records = []
    record_id = 0
    
    for screenshot_idx in range(num_screenshots):
        screenshot_name = f"screen_{screenshot_idx:03d}.png"
        screenshot_path = str(screenshots_dir / screenshot_name)
        
        screen_desc = SCREENSHOT_DESCRIPTIONS[screenshot_idx % len(SCREENSHOT_DESCRIPTIONS)]
        
        manifest = manifests[screenshot_idx % len(manifests)]
        
        record = {
            "id": f"vlm_{record_id:04d}",
            "instruction": f"[Screen shows: {screen_desc}] {generate_instruction(manifest, manifest['example_call'])}",
            "image": screenshot_path,
            "tool_calls": [generate_tool_call(manifest)],
            "output": generate_output(manifest, manifest["example_call"]),
        }
        
        records.append(record)
        record_id += 1
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    
    print(f"Generated {len(records)} VLM training records")
    print(f"Output: {output_path}")
    print(f"Screenshots: {screenshots_dir}")


def create_placeholder_screenshots(screenshots_dir: Path, num_screenshots: int = 10) -> None:
    """Create placeholder screenshots for testing."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(num_screenshots):
            img = Image.new("RGB", (800, 600), color="#2d2d2d")
            draw = ImageDraw.Draw(img)
            
            text = f"Screenshot {i+1}"
            draw.text((400, 300), text, fill="white", anchor="mm")
            
            img.save(screenshots_dir / f"screen_{i:03d}.png")
        
        print(f"Created {num_screenshots} placeholder screenshots in {screenshots_dir}")
    except ImportError:
        print("Pillow not installed, skipping placeholder screenshots")


def main():
    parser = argparse.ArgumentParser(description="Generate VLM training dataset")
    parser.add_argument(
        "--tools-dir",
        type=Path,
        default=Path("data/examples/tools"),
        help="Directory containing tool manifests",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/examples/train_vlm.jsonl"),
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--num-records",
        type=int,
        default=10,
        help="Number of training records to generate",
    )
    parser.add_argument(
        "--create-screenshots",
        action="store_true",
        help="Create placeholder screenshots",
    )
    
    args = parser.parse_args()
    
    if args.create_screenshots:
        screenshots_dir = args.tools_dir.parent / "screenshots"
        create_placeholder_screenshots(screenshots_dir, args.num_records)
    
    generate_dataset(
        tools_dir=args.tools_dir,
        output_path=args.output,
        num_screenshots=args.num_records,
    )


if __name__ == "__main__":
    main()
