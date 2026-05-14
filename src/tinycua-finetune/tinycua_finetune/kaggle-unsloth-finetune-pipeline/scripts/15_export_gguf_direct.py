"""Step 15: Direct GGUF Export via Unsloth.

Attempts to export the model directly to GGUF Q4_K_M format using Unsloth's built-in method.
Falls back to llama.cpp if this fails.
"""


def run(state):
    print("Attempting direct GGUF export via Unsloth...")
    state.gguf_path = f"{state.output_directory}qwen_tool_calling_q4km"

    try:
        state.model.save_pretrained_gguf(
            state.gguf_path,
            state.tokenizer,
            quantization_method="q4_k_m",
        )
        print(f"GGUF Q4_K_M saved to: {state.gguf_path}")
        state.GGUF_SUCCESS = True
    except Exception as e:
        print(f"Direct GGUF export failed: {e}")
        print("Falling back to llama.cpp conversion...")
        state.GGUF_SUCCESS = False


def main():
    print("Step 15 complete: GGUF export status unknown (run via pipeline for actual result)")


if __name__ == "__main__":
    main()
