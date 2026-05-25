import glob
import os

from trl import SFTTrainer, SFTConfig

from . import config


def setup_trainer(
    model,
    tokenizer,
    dataset_final,
    wandb_key=None,
    max_steps=20,
    output_dir=None,
    learning_rate=None,
    max_seq_length=None,
    random_seed=None,
    per_device_batch_size=1,
    gradient_accumulation_steps=8,
):
    if output_dir is None:
        output_dir = config.OUTPUT_DIR
    if learning_rate is None:
        learning_rate = config.LEARNING_RATE
    if max_seq_length is None:
        max_seq_length = config.MAX_SEQ_LENGTH
    if random_seed is None:
        random_seed = config.RANDOM_SEED

    if len(dataset_final) == 0:
        raise ValueError("Dataset is empty after filtering. Try increasing MAX_SEQ_LENGTH.")

    if wandb_key:
        os.environ["WANDB_PROJECT"] = config.WANDB_PROJECT

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset_final,
        eval_dataset=None,
        max_seq_length=max_seq_length,
        args=SFTConfig(
            dataset_text_field="text",
            per_device_train_batch_size=per_device_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            warmup_ratio=0.04,
            max_steps=max_steps,
            learning_rate=learning_rate,
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=random_seed,
            save_steps=10,
            save_total_limit=3,
            save_strategy="steps",
            report_to="wandb" if wandb_key else "none",
            output_dir=output_dir,
            dataset_num_proc=1,
        ),
    )

    print("=" * 50)
    print("Training Configuration:")
    print("=" * 50)
    print(f"  - Dataset size: {len(dataset_final)} samples")
    print(f"  - Batch size per device: {per_device_batch_size}")
    print(f"  - Gradient accumulation: {gradient_accumulation_steps}")
    effective_batch = per_device_batch_size * gradient_accumulation_steps
    print(f"  - Effective batch: {effective_batch}")
    print(f"  - Learning rate: {learning_rate}")
    print(f"  - Max steps: {max_steps}")
    print(f"  - Max sequence length: {max_seq_length}")
    print(f"  - W&B project: {config.WANDB_PROJECT}")

    return trainer


def run_training(trainer, output_dir=None):
    if output_dir is None:
        output_dir = config.OUTPUT_DIR

    print("=" * 50)
    print("Starting training...")
    print("=" * 50)

    checkpoint_dirs = sorted(glob.glob(os.path.join(output_dir, "checkpoint-*")))
    resume_from = checkpoint_dirs[-1] if checkpoint_dirs else None
    if resume_from:
        print(f"Resuming from checkpoint: {resume_from}")

    trainer.train(resume_from_checkpoint=resume_from)

    print("=" * 50)
    print("Training complete!")
    print("=" * 50)


def setup_full_trainer(
    model,
    tokenizer,
    dataset_final,
    wandb_key=None,
    output_dir=None,
    learning_rate=None,
    max_seq_length=None,
    random_seed=None,
):
    if output_dir is None:
        output_dir = config.OUTPUT_DIR
    if learning_rate is None:
        learning_rate = config.LEARNING_RATE
    if max_seq_length is None:
        max_seq_length = config.MAX_SEQ_LENGTH
    if random_seed is None:
        random_seed = config.RANDOM_SEED

    if wandb_key:
        os.environ["WANDB_PROJECT"] = config.WANDB_PROJECT

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset_final,
        eval_dataset=None,
        max_seq_length=max_seq_length,
        args=SFTConfig(
            dataset_text_field="text",
            per_device_train_batch_size=2,
            gradient_accumulation_steps=8,
            warmup_ratio=0.04,
            num_train_epochs=1,
            learning_rate=learning_rate,
            logging_steps=10,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=random_seed,
            save_steps=50,
            save_total_limit=5,
            save_strategy="steps",
            report_to="wandb" if wandb_key else "none",
            output_dir=output_dir,
        ),
    )

    print("=" * 50)
    print("Starting full training (1 epoch)...")
    print("=" * 50)

    checkpoint_dirs = sorted(glob.glob(os.path.join(output_dir, "checkpoint-*")))
    resume_from = checkpoint_dirs[-1] if checkpoint_dirs else None
    if resume_from:
        print(f"Resuming from checkpoint: {resume_from}")

    trainer.train(resume_from_checkpoint=resume_from)

    print("=" * 50)
    print("Full training complete!")
    print("=" * 50)
