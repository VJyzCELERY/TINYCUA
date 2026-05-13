"""Step 6: Configure LoRA Adapter.

Configures LoRA parameters for QLoRA fine-tuning:
- r=64: LoRA rank (dimension of adaptation matrices)
- target_modules: attention and MLP layers
- RSLoRA enabled for better convergence
"""


def run(state):
    from unsloth import FastLanguageModel

    print("Configuring LoRA adapter...")
    print(f"  - Random seed: {state.RANDOM_SEED}")
    print(f"  - LoRA rank: {state.LORA_RANK}")
    print(f"  - Target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj")

    state.model = FastLanguageModel.get_peft_model(
        state.model,
        r=state.LORA_RANK,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=state.LORA_RANK,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=state.RANDOM_SEED,
        use_rslora=True,
    )

    print("LoRA adapter configured with QLoRA optimization (RSLoRA enabled)")


def main():
    print("Step 6 complete: LoRA adapter configured")


if __name__ == "__main__":
    main()
