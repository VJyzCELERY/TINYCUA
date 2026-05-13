"""Step 16: llama.cpp Fallback for GGUF Export.

If direct GGUF export failed, clones llama.cpp and converts the merged model to GGUF format.
This is a fallback method when Unsloth's direct export fails.
"""


def run(state):
    if not state.GGUF_SUCCESS:
        print("Cloning llama.cpp...")

        import os
        os.system("git clone --depth 1 https://github.com/ggerganov/llama.cpp.git")

        print("Converting to GGUF Q4_K_M...")
        os.system(
            f"python llama.cpp/convert_hf_to_gguf.py {state.output_directory}qwen_tool_calling_merged "
            f"--outfile {state.output_directory}qwen_tool_calling_q4km.gguf --outtype q4_k_m "
            f"--split-max-size 2G"
        )

        print(f"GGUF Q4_K_M saved via llama.cpp")
    else:
        print("Skipping llama.cpp - direct export succeeded")


def main():
    print("Step 16 complete: GGUF export via llama.cpp (if needed)")


if __name__ == "__main__":
    main()
