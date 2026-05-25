from unsloth import FastModel
import torch

from . import config


def load_model_and_tokenizer(
    model_name=None,
    max_seq_length=None,
    load_in_4bit=True,
):
    if model_name is None:
        model_name = config.MODEL_NAME
    if max_seq_length is None:
        max_seq_length = config.MAX_SEQ_LENGTH

    print("Loading model...")
    model, tokenizer = FastModel.from_pretrained(
        model_name=model_name,
        max_seq_length=max_seq_length,
        load_in_4bit=load_in_4bit,
        load_in_8bit=False,
        full_finetuning=False,
        device_map="auto",
        dtype=None,
    )

    print("Model loaded successfully!")
    if torch.cuda.is_available():
        print(f"Model device: {next(model.parameters()).device}")

    print(f"Tokenizer vocab size: {len(tokenizer.tokenizer)}")
    print("Setup complete! Ready for LoRA configuration.")

    return model, tokenizer
