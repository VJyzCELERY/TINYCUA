from unsloth.chat_templates import get_chat_template


def setup_chat_template(tokenizer):
    try:
        tokenizer = get_chat_template(
            tokenizer,
            chat_template="gemma-4",
        )
        print("Using Unsloth gemma4 chat template")
    except Exception:
        print("Unsloth gemma4 template not available, using default")
    return tokenizer


def apply_template_to_dataset(tokenizer, dataset):
    tokenizer = setup_chat_template(tokenizer)

    def apply_chat_template_fn(example):
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        return {"text": text}

    print("Applying chat template...")
    dataset_final = dataset.map(
        apply_chat_template_fn,
        remove_columns=dataset.column_names,
        num_proc=4,
    )
    print(f"Final dataset: {len(dataset_final)} samples")

    return tokenizer, dataset_final
