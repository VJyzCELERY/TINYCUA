import gc
import os

import torch
from huggingface_hub import whoami
from peft import PeftModel
from unsloth import FastModel

from . import config


def save_merged_and_gguf(model=None, tokenizer=None, hf_token=None, lora_on_hub=False):
    if not hf_token:
        print("HF_TOKEN not set. Cannot save to Hub.")
        return

    user_info = whoami(token=hf_token)
    username = user_info["name"]
    lora_repo_id = f"{username}/{config.LORA_REPO_NAME}"

    merged_output = os.path.join(config.MERGED_BASE_PATH, config.MERGED_OUTPUT_NAME)

    if model is None or tokenizer is None:
        print("Model not in memory. Reloading base model + adapter from HF Hub...")
        model, tokenizer = FastModel.from_pretrained(
            model_name=config.MODEL_NAME,
            max_seq_length=config.MAX_SEQ_LENGTH,
            load_in_4bit=True,
            device_map="cuda:0",
        )
        for _ in range(3):
            gc.collect()
            torch.cuda.empty_cache()
        with torch.inference_mode():
            model = PeftModel.from_pretrained(
                model, lora_repo_id,
                token=hf_token,
                is_trainable=False,
            )

    print(f"Saving merged 4-bit model to {merged_output}...")
    model.save_pretrained_merged(
        merged_output,
        tokenizer,
        save_method="merged_4bit",
    )
    print("Merged 4-bit model saved to GDrive!")

    vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
    if vram_gb < 20:
        print(f"\nGPU VRAM ({vram_gb:.1f}GB) < 20GB: GGUF export requires more VRAM.")
        print("Merged 4-bit model is saved to GDrive.")
        print("To convert to GGUF, run this cell on a V100/A100 GPU instead.")
        print("Or convert offline using llama.cpp convert script.")
    else:
        print(f"\nGPU VRAM ({vram_gb:.1f}GB) sufficient. Attempting GGUF export...")
        gguf_repo_id = f"{username}/{config.GGUF_REPO_NAME}"
        try:
            model.push_to_hub_gguf(
                gguf_repo_id,
                tokenizer,
                quantization_method="q4_k_m",
                token=hf_token,
                maximum_memory_usage=0.6,
            )
            print(f"GGUF Q4_K_M: https://huggingface.co/{gguf_repo_id}")
        except Exception as e:
            print(f"GGUF export failed: {e}")
            print("Merged 4-bit model is safe on GDrive. Use a higher-VRAM GPU for GGUF.")
