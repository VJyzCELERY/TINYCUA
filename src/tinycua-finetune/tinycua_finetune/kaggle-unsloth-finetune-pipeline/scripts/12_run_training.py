"""Step 12: Run Training.

Executes the QLoRA fine-tuning training loop.
Trains for 20 steps (test run) as configured in step 10.
"""


def run(state):
    print("=" * 50)
    print("Starting training...")
    print("=" * 50)

    state.trainer.train()

    print("=" * 50)
    print("Training complete!")
    print("=" * 50)


def main():
    print("Step 12 complete: Training finished")


if __name__ == "__main__":
    main()
