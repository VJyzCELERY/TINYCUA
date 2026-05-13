"""Step 13: Push LoRA Adapter to HuggingFace Hub.

Uploads the trained LoRA adapter and tokenizer to HuggingFace Hub.
Requires HF_TOKEN in Kaggle Secrets.
"""


def run(state):
    from huggingface_hub import whoami

    try:
        from kaggle_secrets import UserSecretsClient
        user_secrets = UserSecretsClient()
        hf_token = user_secrets.get_secret("HF_TOKEN")
    except Exception:
        print("HF_TOKEN not found. Cannot push to HuggingFace Hub.")
        hf_token = None

    if not hf_token:
        print("Skipping HuggingFace upload - set HF_TOKEN in Kaggle Secrets")
    else:
        user_info = whoami(token=hf_token)
        username = user_info['name']
        lora_repo_id = f"{username}/qwen3-4b-tool-calling-lora"

        print(f"Authenticated as: {username}")
        print(f"Uploading LoRA adapter to {lora_repo_id}...")

        state.model.push_to_hub(lora_repo_id, token=hf_token)
        state.tokenizer.push_to_hub(lora_repo_id, token=hf_token)

        print(f"LoRA pushed: https://huggingface.co/{lora_repo_id}")


def main():
    print("Step 13 complete: LoRA pushed to Hub (or skipped)")


if __name__ == "__main__":
    main()
