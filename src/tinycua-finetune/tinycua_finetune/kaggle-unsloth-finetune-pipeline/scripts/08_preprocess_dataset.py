"""Step 8: Dataset Preprocessing.

Converts raw dataset to training format:
- Parses messages_json field
- Handles tool_calls in OpenAI format
- Filters invalid examples (missing assistant response)
- Combines train and validation splits
"""


def run(state):
    import json
    from datasets import concatenate_datasets

    print("Combining train and validation splits...")
    combined_dataset = concatenate_datasets([
        state.dataset['train'],
        state.dataset['validation']
    ])
    print(f"Combined dataset: {len(combined_dataset)} samples")


    def convert_to_training_format(example):
        try:
            messages = json.loads(example.get('messages_json', '[]'))
            conversations = []

            for msg in messages:
                role = msg.get('role', '')
                content = msg.get('content', '') or ''

                tool_calls = msg.get('tool_calls', [])
                if tool_calls:
                    for tc in tool_calls:
                        func = tc.get('function', {})
                        func_name = func.get('name', '')
                        func_args = func.get('arguments', '{}')
                        if isinstance(func_args, str):
                            func_args = func_args
                        else:
                            func_args = json.dumps(func_args)

                        content += f"\n<tool>\n<tool_name>\n{func_name}\n</tool_name>\n<tool_args>\n{func_args}\n</tool_args>\n</tool>"

                if role in ['user', 'assistant', 'system']:
                    if role == 'system':
                        continue
                    conversations.append({"role": role, "content": content})

            if len(conversations) < 2:
                return {"conversations": None}
            if conversations[-1]["role"] != "assistant":
                return {"conversations": None}

            return {"conversations": conversations}
        except Exception as e:
            print(f"Error: {e}, keys: {example.keys()}")
            return {"conversations": None}


    print("Converting to training format...")
    processed = combined_dataset.map(
        convert_to_training_format,
        remove_columns=combined_dataset.column_names,
        num_proc=4,
    )
    processed = processed.filter(lambda x: x['conversations'] is not None)
    print(f"After filtering: {len(processed)} samples")

    state.processed = processed


def main():
    print("Step 8 complete: Dataset preprocessed")


if __name__ == "__main__":
    main()
