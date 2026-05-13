"""Step 9: Apply Chat Template.

Applies Qwen3 chat template to conversations.
Filters examples exceeding max context length.
"""


def run(state):
    from unsloth.chat_templates import get_chat_template

    print("Applying chat template...")
    state.tokenizer = get_chat_template(
        state.tokenizer,
        chat_template="qwen3",
    )


    def apply_chat_template(example):
        text = state.tokenizer.apply_chat_template(
            example['conversations'],
            tokenize=False,
            add_generation_prompt=False,
        )
        return {"text": text}


    state.dataset_final = state.processed.map(
        apply_chat_template,
        remove_columns=state.processed.column_names,
        num_proc=4,
    )
    print(f"Final dataset: {len(state.dataset_final)} samples")


    def filter_by_length(example):
        tokens = state.tokenizer(example['text'], add_special_tokens=False)
        return len(tokens['input_ids']) <= state.MAX_CONTEXT_LENGTH


    before_count = len(state.dataset_final)
    state.dataset_final = state.dataset_final.filter(filter_by_length, num_proc=4)
    after_count = len(state.dataset_final)
    print(f"Filtered: {before_count - after_count}/{before_count} samples removed ({100*(before_count-after_count)/before_count:.1f}%)")


def main():
    print("Step 9 complete: Chat template applied")


if __name__ == "__main__":
    main()
