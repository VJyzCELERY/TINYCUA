from tinycua_finetune.colab_gpu_pipeline import config
from tinycua_finetune.colab_gpu_pipeline.api_setup import setup_api_keys
from tinycua_finetune.colab_gpu_pipeline.install_deps import install_dependencies
from tinycua_finetune.colab_gpu_pipeline.gpu_detection import detect_gpu
from tinycua_finetune.colab_gpu_pipeline.load_model import load_model_and_tokenizer
from tinycua_finetune.colab_gpu_pipeline.lora_config import apply_lora
from tinycua_finetune.colab_gpu_pipeline.dataset_loading import load_raw_dataset, preprocess_dataset
from tinycua_finetune.colab_gpu_pipeline.apply_template import apply_template_to_dataset
from tinycua_finetune.colab_gpu_pipeline.train import setup_trainer, run_training
from tinycua_finetune.colab_gpu_pipeline.evaluate import run_evaluation
from tinycua_finetune.colab_gpu_pipeline.push_to_hub import push_lora_adapter
from tinycua_finetune.colab_gpu_pipeline.save_model import save_merged_and_gguf


def run_test_pipeline(
    install_first=False,
    run_eval=True,
    push_adapter=True,
    save_model=True,
    eval_toolbench=True,
    eval_hermes=True,
    eval_text_sim=True,
    eval_selfcheck=True,
    eval_mmlu=False,
    eval_mgsm=False,
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
        run_evaluation(model, tokenizer, wandb_key=wandb_key,
                       eval_toolbench=eval_toolbench,
                       eval_hermes=eval_hermes,
                       eval_text_sim=eval_text_sim,
                       eval_selfcheck=eval_selfcheck,
                       eval_mmlu=eval_mmlu,
                       eval_mgsm=eval_mgsm,
                       num_samples_toolbench=config.EVAL_NUM_SAMPLES_TOOLBENCH,
                       num_samples_hermes=config.EVAL_NUM_SAMPLES_HERMES,
                       num_samples_textsim=config.EVAL_NUM_SAMPLES_TEXTSIM,
                       num_samples_selfcheck=config.EVAL_NUM_SAMPLES_SELFCHECK,
                       num_selfcheck_generations=config.EVAL_NUM_SELFCHECK_GENERATIONS,
                       num_mmlu_per_subject=config.EVAL_NUM_MMLU_PER_SUBJECT,
                       num_mgsm=config.EVAL_NUM_MGSM,
                       max_new_tokens=config.EVAL_MAX_NEW_TOKENS,
                       )

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
    from tinycua_finetune.colab_gpu_pipeline.train import setup_full_trainer
    setup_full_trainer(model, tokenizer, dataset_final, wandb_key=wandb_key, output_dir=output_dir)
