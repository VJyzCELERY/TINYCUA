"""Step 17: Push GGUF to HuggingFace Hub.

Uploads the GGUF Q4_K_M file to HuggingFace Hub.
Requires HF_TOKEN in Kaggle Secrets.
Upload size is approximately 2.4GB.
"""

from huggingface_hub import HfApi, whoami

from state import GGUF_SUCCESS, gguf_path, output_directory

try:
    from kaggle_secrets import UserSecretsClient
    user_secrets = UserSecretsClient()
    hf_token = user_secrets.get_secret("HF_TOKEN")
except Exception:
    print("HF_TOKEN not found. Cannot push to HuggingFace Hub.")
    hf_token = None

if not hf_token:
    print("Skipping GGUF upload - set HF_TOKEN in Kaggle Secrets")
else:
    user_info = whoami(token=hf_token)
    username = user_info['name']
    gguf_repo_id = f"{username}/qwen3-4b-tool-calling-q4km"

    print(f"Authenticated as: {username}")

    if GGUF_SUCCESS:
        gguf_file = f"{gguf_path}/qwen_tool_calling_q4km.gguf"
    else:
        gguf_file = f"{output_directory}qwen_tool_calling_q4km.gguf"

    print(f"Uploading GGUF Q4_K_M to {gguf_repo_id}...")

    api = HfApi()
    api.upload_file(
        path_or_fileobj=gguf_file,
        path_in_repo="qwen_tool_calling_q4km.gguf",
        repo_id=gguf_repo_id,
        repo_type="model",
        token=hf_token,
    )

    print(f"GGUF pushed: https://huggingface.co/{gguf_repo_id}")


def main():
    print("Step 17 complete: GGUF pushed to Hub (or skipped)")


if __name__ == "__main__":
    main()