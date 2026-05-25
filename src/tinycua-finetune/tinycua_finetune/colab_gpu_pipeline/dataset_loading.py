from datasets import load_dataset

from . import config


def load_raw_dataset(dataset_path=None, dataset_config=None):
    if dataset_path is None:
        dataset_path = config.DATASET_PATH
    if dataset_config is None:
        dataset_config = config.DATASET_CONFIG

    print(f"Loading hermes-agent-reasoning-traces ({dataset_config} config)...")
    dataset = load_dataset(dataset_path, dataset_config, split="train")

    print(f"Dataset loaded: {len(dataset)} samples")
    print(f"Columns: {dataset.column_names}")

    sample = dataset[0]
    print("First example:")
    print(f"  Category: {sample['category']}")
    print(f"  Subcategory: {sample['subcategory']}")
    print(f"  Conversations: {len(sample['conversations'])} turns")

    return dataset


def convert_to_messages(example):
    role_mapping = config.ROLE_MAPPING
    conversations = example["conversations"]
    messages = []

    for turn in conversations:
        role = role_mapping.get(turn.get("from", ""))
        content = turn.get("value", "")
        if not role or not content:
            continue
        if role == "tool":
            if messages and messages[-1]["role"] == "assistant":
                messages[-1]["content"] += f"\n\n[Tool Result]\n{content}\n[/Tool Result]"
            continue
        if role == "assistant" and messages and messages[-1]["role"] == "assistant":
            messages[-1]["content"] += f"\n\n{content}"
            continue
        messages.append({"role": role, "content": content})

    if len(messages) < 2:
        return {"messages": None}
    if messages[-1]["role"] != "assistant":
        return {"messages": None}
    if messages[0]["role"] == "assistant":
        return {"messages": None}

    return {"messages": messages}


def preprocess_dataset(dataset):
    print("Converting ShareGPT format to standard messages...")
    processed = dataset.map(
        convert_to_messages,
        remove_columns=dataset.column_names,
        num_proc=4,
    )
    processed = processed.filter(lambda x: x["messages"] is not None)
    print(f"After conversion: {len(processed)} valid samples")
    return processed
