import json
import re

import torch
from datasets import load_dataset
from tqdm import tqdm
from unsloth import FastModel

from . import config


def extract_tool_calls(text):
    tool_calls = []
    pattern = r"<tool_call>\s*(\w+)\s*\(([^)]*)\)\s*</tool_call>"
    matches = re.findall(pattern, text)
    for name, args_str in matches:
        try:
            args = json.loads(f"{{{args_str}}}") if args_str else {}
            tool_calls.append({"name": name, "args": args})
        except json.JSONDecodeError:
            tool_calls.append({"name": name, "args": {}, "parse_error": args_str})
    return tool_calls


def evaluate_on_toolbench(model, tokenizer, num_samples=100, max_new_tokens=512):
    try:
        eval_data = load_dataset(config.EVAL_DATASET_PATH, split="test")
        eval_data = eval_data.select(range(min(num_samples, len(eval_data))))
    except Exception as e:
        print(f"Could not load ToolBench eval set: {e}")
        print("Skipping ToolBench evaluation.")
        return {}

    results = {"correct": 0, "total": 0, "errors": 0}

    for example in tqdm(eval_data, desc="Evaluating"):
        try:
            messages = json.loads(example.get("messages", "[]"))
            if not messages:
                continue
            prompt_messages = []
            for msg in messages[:-1]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    prompt_messages.append({"role": role, "content": content})
            text = tokenizer.apply_chat_template(
                prompt_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = tokenizer(text, return_tensors="pt").to(model.device)
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                do_sample=True,
            )
            response = tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
            )

            expected_tools = messages[-1].get("tool_calls", [])
            actual_tools = extract_tool_calls(response)

            if expected_tools and actual_tools:
                expected_names = {t.get("function", {}).get("name", "") for t in expected_tools}
                actual_names = {t["name"] for t in actual_tools}
                if expected_names == actual_names:
                    results["correct"] += 1
                results["total"] += 1
        except Exception:
            results["errors"] += 1

    if results["total"] > 0:
        results["accuracy"] = results["correct"] / results["total"]

    print(f"ToolBench Results ({num_samples} samples):")
    print(f"  Accuracy: {results.get('accuracy', 0):.2%}")
    print(f"  Correct: {results['correct']} / {results['total']}")
    print(f"  Errors: {results['errors']}")

    return results


def run_evaluation(model, tokenizer, wandb_key=None, num_samples=100):
    print("Running ToolBench evaluation...")
    FastModel.for_inference(model)
    toolbench_results = evaluate_on_toolbench(model, tokenizer, num_samples=num_samples)

    if wandb_key and toolbench_results:
        import wandb
        wandb.log({"eval/toolbench_accuracy": toolbench_results.get("accuracy", 0)})
        wandb.log({"eval/toolbench_correct": toolbench_results["correct"]})
        wandb.log({"eval/toolbench_total": toolbench_results["total"]})

    return toolbench_results
