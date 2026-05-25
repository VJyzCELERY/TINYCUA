from unsloth import FastModel

from . import config


def apply_lora(model, lora_rank=None, random_seed=None):
    if lora_rank is None:
        lora_rank = config.LORA_RANK
    if random_seed is None:
        random_seed = config.RANDOM_SEED

    model = FastModel.get_peft_model(
        model,
        finetune_vision_layers=False,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=lora_rank,
        lora_alpha=lora_rank,
        lora_dropout=0,
        bias="none",
        random_state=random_seed,
        use_rslora=True,
    )

    print("LoRA adapter configured with QLoRA optimization (RSLoRA enabled)")
    return model
