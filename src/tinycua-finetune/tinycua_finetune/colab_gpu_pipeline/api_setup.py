import os


def setup_wandb():
    try:
        from google.colab import userdata
        wandb_key = userdata.get("WANDB_API_KEY")
        if wandb_key:
            import wandb
            wandb.login(key=wandb_key)
            print("Logged in to W&B successfully!")
            return wandb_key
    except Exception:
        print("WANDB_API_KEY not found. W&B logging will be disabled.")
    return None


def setup_huggingface():
    try:
        from google.colab import userdata
        hf_token = userdata.get("HF_TOKEN")
        if hf_token:
            from huggingface_hub import login
            login(token=hf_token)
            print("Logged in to HuggingFace!")
            return hf_token
    except Exception:
        print("HF_TOKEN not found. HF push will be disabled.")
    return None


def mount_gdrive(output_dir):
    try:
        from google.colab import drive
        drive.mount("/content/drive")
    except Exception:
        print("Google Drive mount not available (not in Colab). Using local paths.")
    os.makedirs(output_dir, exist_ok=True)
    print(f"Checkpoints will be saved to: {output_dir}")


def setup_api_keys(output_dir):
    wandb_key = setup_wandb()
    hf_token = setup_huggingface()
    mount_gdrive(output_dir)
    return wandb_key, hf_token
