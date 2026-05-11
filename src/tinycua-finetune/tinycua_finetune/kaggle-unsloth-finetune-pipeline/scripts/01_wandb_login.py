"""Step 1: Login to W&B and setup output directory.

This cell handles W&B authentication for experiment tracking.
If WANDB_API_KEY is not set in Kaggle Secrets, training will proceed without W&B logging.
"""

import os
from state import output_directory, wandb_key

try:
    from kaggle_secrets import UserSecretsClient
    user_secrets = UserSecretsClient()
    wandb_key = user_secrets.get_secret("WANDB_API_KEY")
except Exception:
    print("WANDB_API_KEY not found. W&B logging will be disabled.")
    wandb_key = None

if wandb_key:
    import wandb
    wandb.login(key=wandb_key)
    print("Logged in to W&B successfully!")
else:
    print("W&B login skipped - set WANDB_API_KEY in Kaggle Secrets to enable")

os.makedirs(output_directory, exist_ok=True)
print(f"Checkpoints will be saved to: {output_directory}")


def main():
    print("Step 1 complete: W&B login handled, output directory ready")


if __name__ == "__main__":
    main()