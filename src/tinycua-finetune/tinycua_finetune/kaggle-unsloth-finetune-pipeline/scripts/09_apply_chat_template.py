"""Step 9: Apply Chat Template.

Applies Qwen3 chat template to conversations.
Filters examples exceeding max context length.
"""

from unsloth.chat_templates import get_chat_template

from state import tokenizer, processed, MAX_CONTEXT_LENGTH

print("Applying chat template...")
tokenizer = get_chat_template(
    tokenizer,
    chat_template="qwen3",
)


def apply_chat_template(example):
    text = tokenizer.apply_chat_template(
        example['conversations'],
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}


dataset_final = processed.map(
    apply_chat_template,
    remove_columns=processed.column_names,
    num_proc=4,
)
print(f"Final dataset: {len(dataset_final)} samples")


def filter_by_length(example):
    tokens = tokenizer(example['text'], add_special_tokens=False)
    return len(tokens['input_ids']) <= MAX_CONTEXT_LENGTH


before_count = len(dataset_final)
dataset_final = dataset_final.filter(filter_by_length, num_proc=4)
after_count = len(dataset_final)
print(f"Filtered: {before_count - after_count}/{before_count} samples removed ({100*(before_count-after_count)/before_count:.1f}%)")


def main():
    print("Step 9 complete: Chat template applied")


if __name__ == "__main__":
    main()