"""Step 15: Direct GGUF Export via Unsloth.

Attempts to export the model directly to GGUF Q4_K_M format using Unsloth's built-in method.
Falls back to llama.cpp if this fails.
"""

from state import model, tokenizer, output_directory, GGUF_SUCCESS, gguf_path

print("Attempting direct GGUF export via Unsloth...")
gguf_path = f"{output_directory}qwen_tool_calling_q4km"

try:
    model.save_pretrained_gguf(
        gguf_path,
        tokenizer,
        quantization_method="q4_k_m",
    )
    print(f"GGUF Q4_K_M saved to: {gguf_path}")
    GGUF_SUCCESS = True
except Exception as e:
    print(f"Direct GGUF export failed: {e}")
    print("Falling back to llama.cpp conversion...")
    GGUF_SUCCESS = False


def main():
    print(f"Step 15 complete: GGUF export {'succeeded' if GGUF_SUCCESS else 'failed - will use llama.cpp fallback'}")


if __name__ == "__main__":
    main()