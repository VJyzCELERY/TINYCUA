from . import config
from .api_setup import setup_api_keys
from .install_deps import install_dependencies
from .gpu_detection import detect_gpu
from .load_model import load_model_and_tokenizer
from .lora_config import apply_lora
from .dataset_loading import load_raw_dataset, preprocess_dataset
from .apply_template import apply_template_to_dataset
from .train import setup_trainer, run_training
from .evaluate import run_evaluation
from .push_to_hub import push_lora_adapter
from .save_model import save_merged_and_gguf


def run_test_pipeline(
    install_first=False,
    run_eval=True,
    push_adapter=True,
    save_model=True,
):
    if install_first:
        install_dependencies()

    detect_gpu()

    wandb_key, hf_token = setup_api_keys(config.OUTPUT_DIR)

    model, tokenizer = load_model_and_tokenizer()
    model = apply_lora(model)

    dataset = load_raw_dataset()
    processed = preprocess_dataset(dataset)
    tokenizer, dataset_final = apply_template_to_dataset(tokenizer, processed)

    trainer = setup_trainer(model, tokenizer, dataset_final, wandb_key=wandb_key)
    run_training(trainer)

    if run_eval:
        run_evaluation(model, tokenizer, wandb_key=wandb_key)

    if push_adapter:
        push_lora_adapter(model, tokenizer, hf_token)

    if save_model:
        save_merged_and_gguf(model, tokenizer, hf_token)

    print("\n--- Pipeline complete! ---")


def run_full_training(
    model,
    tokenizer,
    dataset_final,
    wandb_key=None,
    output_dir=None,
):
    from .train import setup_full_trainer
    setup_full_trainer(model, tokenizer, dataset_final, wandb_key=wandb_key, output_dir=output_dir)
