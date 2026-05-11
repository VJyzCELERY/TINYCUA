"""Step 14: Save Merged 16-bit Model.

Merges LoRA adapter with base model weights and saves to disk.
Note: This may fail on Kaggle due to limited disk space (~20GB).
"""

from state import model, tokenizer, output_directory

print("Saving merged 16-bit model...")
merged_save_path = f"{output_directory}qwen_tool_calling_merged"

model.save_pretrained_merged(
    merged_save_path,
    tokenizer,
    save_method="merged_16bit",
)

print(f"Merged 16bit model saved to: {merged_save_path}")


def main():
    print("Step 14 complete: Merged model saved")


if __name__ == "__main__":
    main()