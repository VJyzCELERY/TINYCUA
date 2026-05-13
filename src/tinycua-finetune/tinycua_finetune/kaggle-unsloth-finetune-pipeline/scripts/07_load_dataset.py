"""Step 7: Load and Explore Dataset.

Loads the younissk/tool-calling-mix dataset and explores its structure.
Displays dataset splits, columns, and sample data.
"""


def run(state):
    from datasets import load_dataset

    print("Loading tool-calling-mix dataset (all splits)...")

    state.dataset = load_dataset("younissk/tool-calling-mix")

    print(f"\nDataset splits: {list(state.dataset.keys())}")
    for split_name, split_data in state.dataset.items():
        print(f"  {split_name}: {len(split_data)} samples")

    print(f"\nColumns: {state.dataset['train'].column_names}")
    print(f"\nSample (first example):")
    sample = state.dataset['train'][0]
    print(f"  n_calls: {sample['n_calls']}")
    print(f"  difficulty: {sample['difficulty']}")
    print(f"  meta_source: {sample['meta_source']}")
    print(f"  valid: {sample['valid']}")

    print("\nExploring data structure...")
    print("Train keys:", state.dataset['train'].features.keys())
    print("\nFirst example:")
    example = state.dataset['train'][0]
    for key in example.keys():
        print(f"  {key}: {type(example[key])}")

    if 'messages' in example:
        print("\nMessages (first 2):")
        for msg in example['messages'][:2]:
            print(f"  Role: {msg.get('role')}")
            print(f"  Keys: {msg.keys()}")
            if 'tool_calls' in msg:
                print(f"  Tool calls: {msg['tool_calls']}")


def main():
    print("Step 7 complete: Dataset loaded and explored")


if __name__ == "__main__":
    main()
