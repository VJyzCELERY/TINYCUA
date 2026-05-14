#!/usr/bin/env python3
"""Fine-tuning pipeline manager.

Runs the Kaggle + Unsloth QLoRA fine-tuning pipeline as in-process Python calls.
Each script corresponds to a notebook cell for improved reviewability.

Usage:
    python finetune.py run all        # Run all 17 steps
    python finetune.py run all --dry-run  # Print plan without executing
    python finetune.py run 7          # Run step 7 only
    python finetune.py run 5-12       # Run steps 5 through 12

<EOF_DESC>
"""

import argparse
import importlib.util
import os
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


def load_step_module(step_name, state):
    script = SCRIPTS_DIR / f"{step_name}.py"
    spec = importlib.util.spec_from_file_location(step_name, script)
    module = importlib.util.module_from_spec(spec)
    sys.modules['state'] = state
    spec.loader.exec_module(module)
    return module


def check_prerequisites(steps):
    missing = []
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        print(f"  [OK] HF_TOKEN is set")
    else:
        print(f"  [WARN] HF_TOKEN not set (HF push steps will fail)")
    wandb_key = os.environ.get("WANDB_API_KEY")
    if wandb_key:
        print(f"  [OK] WANDB_API_KEY is set")
    else:
        print(f"  [WARN] WANDB_API_KEY not set (W&B logging disabled)")
    output_dir = Path("/kaggle/working/")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] Output directory writable: {output_dir}")
    except Exception as e:
        print(f"  [WARN] Cannot create output directory: {e}")
    return missing


def run_step(step_name, state, dry_run=False):
    print(f"\n{'='*50}")
    print(f"{'DRY-RUN: ' if dry_run else ''}Running: {step_name}")
    print(f"{'='*50}\n")

    if dry_run:
        print(f"[dry-run] Would execute {step_name}.py")
        return True

    module = load_step_module(step_name, state)
    if hasattr(module, "run"):
        module.run(state)
    else:
        module.main()

    return True


def parse_range(range_str):
    parts = range_str.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid range format: {range_str}")

    start = int(parts[0])
    end = int(parts[1])

    if start < 1 or end > len(STEPS) or start > end:
        raise ValueError(f"Range must be between 1 and {len(STEPS)}")

    return STEPS[start - 1:end]


def run_steps(steps, state, dry_run=False):
    for step in steps:
        success = run_step(step, state, dry_run=dry_run)
        if not success:
            print(f"\n[ERROR] Step {step} failed. Stopping.")
            sys.exit(1)

    print(f"\n{'='*50}")
    print(f"{'DRY-RUN: ' if dry_run else ''}Completed {len(steps)} step(s)")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning pipeline manager")
    parser.add_argument("action", nargs="?", default=None)
    parser.add_argument("target", nargs="?", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = parser.parse_args()

    if args.action != "run" or not args.target:
        print("Usage:")
        print("  python finetune.py run all        # Run all 17 steps")
        print("  python finetune.py run all --dry-run  # Print plan without executing")
        print("  python finetune.py run 7          # Run step 7 only")
        print("  python finetune.py run 5-12       # Run steps 5 through 12")
        sys.exit(1)

    dry_run = args.dry_run

    if args.target == "all":
        steps = STEPS
    elif "-" in args.target:
        steps = parse_range(args.target)
    else:
        step_num = int(args.target)
        if step_num < 1 or step_num > len(STEPS):
            print(f"Step must be between 1 and {len(STEPS)}")
            sys.exit(1)
        steps = [STEPS[step_num - 1]]

    print(f"{'DRY-RUN: ' if dry_run else ''}Plan: {len(steps)} step(s): {steps}")

    sys.path.insert(0, str(SCRIPTS_DIR))

    if dry_run:
        print("\n--- Prerequisites Check ---")
        check_prerequisites(steps)

    import state as _state
    run_steps(steps, _state, dry_run=dry_run)


if __name__ == "__main__":
    main()
