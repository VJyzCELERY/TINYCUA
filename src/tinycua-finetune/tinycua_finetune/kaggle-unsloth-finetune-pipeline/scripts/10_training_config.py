"""Step 10: Configure Training Parameters.

Sets up SFTTrainer with SFTConfig for QLoRA fine-tuning.
Configures batch size, learning rate, logging, and W&B integration.
Note: This config is for quick testing (20 steps). For full training, adjust parameters.
"""


def run(state):
    import os
    from trl import SFTTrainer, SFTConfig

    if len(state.dataset_final) == 0:
        raise ValueError("Dataset is empty after filtering.")

    print(f"Dataset size: {len(state.dataset_final)} samples")

    wandb_project_name = "qwen-tool-calling-qlora"

    if state.wandb_key:
        os.environ["WANDB_PROJECT"] = wandb_project_name

    state.trainer = SFTTrainer(
        model=state.model,
        tokenizer=state.tokenizer,
        train_dataset=state.dataset_final,
        eval_dataset=None,
        args=SFTConfig(
            dataset_text_field="text",
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            warmup_ratio=0.04,
            max_steps=20,
            learning_rate=state.LEARNING_RATE,
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=state.RANDOM_SEED,
            save_steps=100,
            save_total_limit=2,
            save_strategy="steps",
            report_to="wandb" if state.wandb_key else "none",
            output_dir=state.output_directory,
            max_seq_length=state.MAX_CONTEXT_LENGTH,
            logging_dir=f"{state.output_directory}/logs",
        ),
    )

    print(f"Trainer configured:")
    print(f"  - Batch size: 2 (per device)")
    print(f"  - Gradient accumulation: 8")
    print(f"  - Effective batch: 16")
    print(f"  - Learning rate: {state.LEARNING_RATE}")
    print(f"  - Max steps: 20 (test run)")
    print(f"  - Max sequence length: {state.MAX_CONTEXT_LENGTH}")
    print(f"  - W&B project: {wandb_project_name}")


def main():
    print("Step 10 complete: Training configured")


if __name__ == "__main__":
    main()
