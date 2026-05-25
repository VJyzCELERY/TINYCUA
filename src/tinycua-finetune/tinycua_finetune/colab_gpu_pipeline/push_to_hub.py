from huggingface_hub import whoami, repo_exists

from . import config


def push_lora_adapter(model, tokenizer, hf_token):
    if not hf_token:
        print("HF_TOKEN not set. Skipping LoRA push.")
        return False

    user_info = whoami(token=hf_token)
    username = user_info["name"]
    lora_repo_id = f"{username}/{config.LORA_REPO_NAME}"
    print(f"Authenticated as: {username}")

    if repo_exists(lora_repo_id, token=hf_token):
        print(f"LoRA adapter already exists on HF Hub: {lora_repo_id}")
        print(f"  -> https://huggingface.co/{lora_repo_id}")
        return True

    print(f"Uploading LoRA adapter to {lora_repo_id}...")
    model.push_to_hub(lora_repo_id, token=hf_token)
    tokenizer.tokenizer.push_to_hub(lora_repo_id, token=hf_token)
    print(f"LoRA pushed: https://huggingface.co/{lora_repo_id}")
    print("LoRA adapter is the primary artifact - merge/GGUF steps can be re-run later.")
    return True
