#!/usr/bin/env python3
"""Fine-tuning pipeline manager.

Runs the Kaggle + Unsloth QLoRA fine-tuning pipeline as separate scripts.
Each script corresponds to a notebook cell for improved reviewability.

Usage:
    python finetune.py run all      # Run all 17 steps
    python finetune.py run 7       # Run step 7 only
    python finetune.py run 5-12     # Run steps 5 through 12

<EOF_DESC>
"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent / "scripts"

STEPS = [
    "01_wandb_login",
    "02_install_unsloth",
    "03_pip_install_alt",
    "04_gpu_detection",
    "05_load_model",
    "06_lora_config",
    "07_load_dataset",
    "08_preprocess_dataset",
    "09_apply_chat_template",
    "10_training_config",
    "11_train_on_responses",
    "12_run_training",
    "13_push_lora_to_hf",
    "14_save_merged_model",
    "15_export_gguf_direct",
    "16_export_gguf_llama_cpp",
    "17_push_gguf_to_hf",
]


def run_step(step_name):
    """Run a single step script."""
    script = SCRIPTS_DIR / f"{step_name}.py"
    print(f"\n{'='*50}")
    print(f"Running: {step_name}")
    print(f"{'='*50}\n")

    result = subprocess.run(
        [sys.executable, str(script)],
        check=True,
    )
    return result.returncode == 0


def parse_range(range_str):
    """Parse step range like '5-12' into list of step names."""
    parts = range_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid range format: {range_str}")

    start = int(parts[0])
    end = int(parts[1])

    if start < 1 or end > len(STEPS) or start > end:
        raise ValueError(f"Range must be between 1 and {len(STEPS)}")

    return STEPS[start - 1:end]


def run_steps(steps):
    """Run a list of steps, stopping on first error."""
    for step in steps:
        success = run_step(step)
        if not success:
            print(f"\n[ERROR] Step {step} failed. Stopping.")
            sys.exit(1)

    print(f"\n{'='*50}")
    print(f"Completed {len(steps)} step(s)")
    print(f"{'='*50}")


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "run":
        print("Usage:")
        print("  python finetune.py run all      # Run all 17 steps")
        print("  python finetune.py run 7        # Run step 7 only")
        print("  python finetune.py run 5-12     # Run steps 5 through 12")
        sys.exit(1)

    target = sys.argv[2]

    if target == "all":
        steps = STEPS
    elif "-" in target:
        steps = parse_range(target)
    else:
        step_num = int(target)
        if step_num < 1 or step_num > len(STEPS):
            print(f"Step must be between 1 and {len(STEPS)}")
            sys.exit(1)
        steps = [STEPS[step_num - 1]]

    print(f"Running {len(steps)} step(s): {steps}")
    run_steps(steps)


if __name__ == "__main__":
    main()