import json
import re
import math
from collections import Counter

import torch
from datasets import load_dataset
from tqdm import tqdm
from unsloth import FastModel

from tinycua_finetune.colab_gpu_pipeline import config


# ── Helpers ────────────────────────────────────────────────────────────

def extract_tool_calls_old(text):
    """ToolBench format: <tool_call>name(args)</tool_call>"""
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


def extract_tool_calls(text):
    """Hermes format: <tool_call>{"name": "...", "arguments": {...}}</tool_call>

    Returns list of dicts with keys: name, arguments, raw"""
    calls = []
    pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
    for m in re.finditer(pattern, text, re.DOTALL):
        raw = m.group(1)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            calls.append({"name": None, "arguments": {}, "raw": raw, "parse_error": True})
            continue
        calls.append({
            "name": parsed.get("name"),
            "arguments": parsed.get("arguments", {}),
            "raw": raw,
            "parse_error": False,
        })
    return calls


def extract_think_blocks(text):
    """Extract <think>...</think> content from text."""
    return re.findall(r"<think>(.*?)</think>", text, re.DOTALL)


def extract_text_outside_tags(text):
    """Return text with <think>, <tool_call>, <tool_response> tags stripped."""
    return re.sub(r"<think>.*?</think>|<tool_call>.*?</tool_call>|<tool_response>.*?</tool_response>",
                  "", text, flags=re.DOTALL).strip()


def hermes_to_openai_messages(conversations):
    """Convert Hermes ShareGPT conversations to OpenAI message dicts."""
    role_map = {"system": "system", "human": "user", "gpt": "assistant", "tool": "tool"}
    messages = []
    for turn in conversations:
        role = role_map.get(turn.get("from", ""))
        content = turn.get("value", "")
        if role == "tool":
            content = re.sub(r"<tool_response>(.*?)</tool_response>", r"\1", content, flags=re.DOTALL).strip()
            if not content:
                continue
        if role == "assistant":
            stripped = extract_text_outside_tags(content)
            if not stripped and extract_tool_calls(content):
                content = extract_text_outside_tags(content)
        if role:
            messages.append({"role": role, "content": content})
    return messages


def generate_response(model, tokenizer, messages, max_new_tokens=512, temperature=0.7, do_sample=True):
    """Generate a response from messages dict list (OpenAI format)."""
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        do_sample=do_sample,
    )
    return tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def get_tool_names_from_sample(sample):
    """Extract valid tool names from the sample's tools field."""
    tools_raw = sample.get("tools", "[]")
    if isinstance(tools_raw, str):
        try:
            tools_raw = json.loads(tools_raw)
        except json.JSONDecodeError:
            return set()
    return {t.get("function", t).get("name", "") for t in tools_raw}


def jaccard_similarity(set_a, set_b):
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)


def ngram_precision(reference_tokens, candidate_tokens, n):
    """Compute n-gram precision."""
    ref_ngrams = Counter(tuple(reference_tokens[i:i+n]) for i in range(len(reference_tokens)-n+1))
    cand_ngrams = Counter(tuple(candidate_tokens[i:i+n]) for i in range(len(candidate_tokens)-n+1))
    if not cand_ngrams:
        return 0.0
    matches = sum(min(cand_ngrams[ng], ref_ngrams[ng]) for ng in cand_ngrams)
    total = sum(cand_ngrams.values())
    return matches / total if total > 0 else 0.0


# ── Tier 1: Hermes Holdout Evaluation ────────────────────────────────

def evaluate_on_hermes(model, tokenizer, num_samples=200, max_new_tokens=512):
    """Evaluate tool-calling metrics on held-out hermes-agent-reasoning-traces samples.

    Metrics:
      - toolcall_accuracy: fraction of tool names matching ground truth
      - arg_json_validity: fraction of tool-call arguments that parse as valid JSON
      - format_compliance: fraction of assistant turns with well-formed <tool_call>
      - exact_toolcall_match: name + arguments match expected exactly
      - think_block_rate: fraction of responses containing <think>
      - tool_hallucination_rate: fraction of tool calls using names absent from tools field
    """
    try:
        dataset = load_dataset(config.DATASET_PATH, config.DATASET_CONFIG, split="train")
        dataset = dataset.select(range(min(num_samples, len(dataset))))
    except Exception as e:
        print(f"Could not load hermes eval set: {e}")
        return {}

    results = {
        "total_samples": min(num_samples, len(dataset)),
        "total_tool_calls": 0,
        "toolcall_accuracy": 0.0,
        "toolcall_correct": 0,
        "arg_json_validity": 0.0,
        "valid_args": 0,
        "format_compliance": 0.0,
        "compliant_responses": 0,
        "exact_match_correct": 0,
        "exact_match_total": 0,
        "think_blocks": 0,
        "tool_hallucinations": 0,
        "total_generated_calls": 0,
        "errors": 0,
    }

    for sample in tqdm(dataset, desc="Hermes Eval"):
        try:
            convs = sample.get("conversations", [])
            valid_tools = get_tool_names_from_sample(sample)

            gpt_indices = [i for i, t in enumerate(convs) if t.get("from") == "gpt"]
            if len(gpt_indices) < 1:
                continue

            last_gpt_idx = gpt_indices[-1]
            prompt_convs = convs[:last_gpt_idx]
            reference_convs = convs[last_gpt_idx]

            messages = hermes_to_openai_messages(prompt_convs)
            if not messages:
                continue

            response = generate_response(model, tokenizer, messages, max_new_tokens=max_new_tokens, do_sample=True)

            ref_content = reference_convs.get("value", "")
            ref_calls = extract_tool_calls(ref_content)
            gen_calls = extract_tool_calls(response)

            ref_has_tools = len(ref_calls) > 0
            gen_has_tools = len(gen_calls) > 0

            if gen_has_tools:
                for gc in gen_calls:
                    if gc["name"] is not None and gc["name"] not in valid_tools:
                        results["tool_hallucinations"] += 1
                    if not gc["parse_error"]:
                        results["valid_args"] += 1
                results["compliant_responses"] += 1
                results["total_generated_calls"] += len(gen_calls)

            gen_think_blocks = extract_think_blocks(response)
            if gen_think_blocks:
                results["think_blocks"] += 1

            if ref_has_tools and gen_has_tools:
                ref_names = {c["name"] for c in ref_calls if c["name"]}
                gen_names = {c["name"] for c in gen_calls if c["name"]}

                for ref_name in ref_names:
                    results["total_tool_calls"] += 1
                    if ref_name in gen_names:
                        results["toolcall_correct"] += 1

                for ref_call in ref_calls:
                    results["exact_match_total"] += 1
                    for gen_call in gen_calls:
                        if (ref_call["name"] == gen_call["name"]
                                and ref_call["arguments"] == gen_call["arguments"]):
                            results["exact_match_correct"] += 1
                            break

        except Exception:
            results["errors"] += 1

    n = results["total_samples"]
    if n > 0:
        results["format_compliance"] = results["compliant_responses"] / n
        results["think_block_rate"] = results["think_blocks"] / n
    if results["total_tool_calls"] > 0:
        results["toolcall_accuracy"] = results["toolcall_correct"] / results["total_tool_calls"]
    if results["total_generated_calls"] > 0:
        results["arg_json_validity"] = results["valid_args"] / results["total_generated_calls"]
    if results["exact_match_total"] > 0:
        results["exact_toolcall_match"] = results["exact_match_correct"] / results["exact_match_total"]

    print(f"\nHermes Eval Results ({num_samples} samples):")
    print(f"  ToolCall Accuracy:    {results.get('toolcall_accuracy', 0):.2%}")
    print(f"  Arg JSON Validity:    {results.get('arg_json_validity', 0):.2%}")
    print(f"  Format Compliance:    {results.get('format_compliance', 0):.2%}")
    print(f"  Exact Match:          {results.get('exact_toolcall_match', 0):.2%}")
    print(f"  Think Block Rate:     {results.get('think_block_rate', 0):.2%}")
    print(f"  Hallucinations:       {results['tool_hallucinations']}")
    print(f"  Errors:               {results['errors']}")

    return results


# ── Tier 1b: SelfCheck Consistency (reference-free) ──────────────────

def evaluate_selfcheck(model, tokenizer, dataset=None, num_samples=50,
                       num_generations=5, max_new_tokens=512):
    """SelfCheckGPT-style consistency evaluation — no reference needed.

    Generates N completions per prompt and measures pairwise consistency:
      - tool_name_consistency: mean Jaccard of tool name sets across generations
      - arg_key_consistency: mean Jaccard of arg key sets across generations
      - format_compliance_stability: stdev of format compliance across generations
      - think_block_stability: stdev of think-block presence across generations
      - text_self_bleu: mean pairwise self-BLEU (lower = more diverse / less certain)
    """
    if dataset is None:
        try:
            dataset = load_dataset(config.DATASET_PATH, config.DATASET_CONFIG, split="train")
        except Exception as e:
            print(f"Could not load dataset for SelfCheck: {e}")
            return {}

    dataset = dataset.select(range(min(num_samples, len(dataset))))

    results = {
        "total_prompts": min(num_samples, len(dataset)),
        "tool_name_consistency": 0.0,
        "arg_key_consistency": 0.0,
        "format_compliance_stability": 0.0,
        "think_block_stability": 0.0,
        "text_self_bleu": 0.0,
        "errors": 0,
    }

    all_name_consistencies = []
    all_arg_consistencies = []
    all_format_flags = []
    all_think_flags = []
    all_self_bleus = []

    for sample in tqdm(dataset, desc="SelfCheck Eval"):
        try:
            convs = sample.get("conversations", [])
            gpt_indices = [i for i, t in enumerate(convs) if t.get("from") == "gpt"]
            if len(gpt_indices) < 1:
                continue
            prompt_convs = convs[:gpt_indices[-1]]
            messages = hermes_to_openai_messages(prompt_convs)
            if not messages:
                continue

            generations = []
            for _ in range(num_generations):
                resp = generate_response(model, tokenizer, messages,
                                         max_new_tokens=max_new_tokens,
                                         temperature=0.7, do_sample=True)
                generations.append(resp)

            gen_tool_sets = []
            gen_arg_key_sets = []
            gen_has_format = []
            gen_has_think = []
            gen_tokens = []

            for g in generations:
                calls = extract_tool_calls(g)
                name_set = {c["name"] for c in calls if c["name"]}
                arg_key_set = set()
                for c in calls:
                    arg_key_set.update(c["arguments"].keys())
                gen_tool_sets.append(name_set)
                gen_arg_key_sets.append(arg_key_set)
                gen_has_format.append(1.0 if len(calls) > 0 else 0.0)
                gen_has_think.append(1.0 if extract_think_blocks(g) else 0.0)
                gen_tokens.append(g.split())

            pair_name_iou = []
            pair_arg_iou = []
            pair_self_bleu = []
            for i in range(num_generations):
                for j in range(i + 1, num_generations):
                    pair_name_iou.append(jaccard_similarity(gen_tool_sets[i], gen_tool_sets[j]))
                    pair_arg_iou.append(jaccard_similarity(gen_arg_key_sets[i], gen_arg_key_sets[j]))
                    bp = 1.0
                    if gen_tokens[i] and gen_tokens[j]:
                        prec = ngram_precision(gen_tokens[j], gen_tokens[i], 1)
                        if prec > 0:
                            bp = min(1.0, math.exp(1 - len(gen_tokens[j]) / len(gen_tokens[i])) if gen_tokens[i] else 1.0)
                        pair_self_bleu.append(prec * bp)
            if pair_name_iou:
                all_name_consistencies.append(sum(pair_name_iou) / len(pair_name_iou))
                all_arg_consistencies.append(sum(pair_arg_iou) / len(pair_arg_iou))
                all_self_bleus.append(sum(pair_self_bleu) / len(pair_self_bleu))
            all_format_flags.append(gen_has_format)
            all_think_flags.append(gen_has_think)

        except Exception:
            results["errors"] += 1

    if all_name_consistencies:
        results["tool_name_consistency"] = sum(all_name_consistencies) / len(all_name_consistencies)
    if all_arg_consistencies:
        results["arg_key_consistency"] = sum(all_arg_consistencies) / len(all_arg_consistencies)
    if all_self_bleus:
        results["text_self_bleu"] = sum(all_self_bleus) / len(all_self_bleus)
    if all_format_flags:
        per_prompt_stds = [sum(f) / len(f) for f in all_format_flags]
        results["format_compliance_stability"] = (
            sum((s - sum(per_prompt_stds)/len(per_prompt_stds))**2 for s in per_prompt_stds)
            / len(per_prompt_stds)
        ) ** 0.5 if len(per_prompt_stds) > 1 else 0.0
    if all_think_flags:
        per_think_stds = [sum(t) / len(t) for t in all_think_flags]
        results["think_block_stability"] = (
            sum((s - sum(per_think_stds)/len(per_think_stds))**2 for s in per_think_stds)
            / len(per_think_stds)
        ) ** 0.5 if len(per_think_stds) > 1 else 0.0

    print(f"\nSelfCheck Consistency Results ({num_samples} samples x {num_generations} gens):")
    print(f"  Tool Name Jaccard:    {results.get('tool_name_consistency', 0):.3f}")
    print(f"  Arg Key Jaccard:      {results.get('arg_key_consistency', 0):.3f}")
    print(f"  Self-BLEU:            {results.get('text_self_bleu', 0):.3f}")
    print(f"  Format Stability:     {results.get('format_compliance_stability', 0):.3f}")
    print(f"  Think Stability:      {results.get('think_block_stability', 0):.3f}")
    print(f"  Errors:               {results['errors']}")

    return results


# ── Tier 2: Text Similarity (BLEU, ROUGE-L, chrF++) ──────────────────

def _lcs_length(X, Y):
    m, n = len(X), len(Y)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if X[i - 1] == Y[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def compute_bleu(candidate_tokens, reference_tokens, max_n=4):
    """Simple BLEU score computation (no smoothing)."""
    ref_len = len(reference_tokens)
    cand_len = len(candidate_tokens)
    if cand_len == 0 or ref_len == 0:
        return 0.0
    precisions = []
    for n in range(1, max_n + 1):
        p = ngram_precision(reference_tokens, candidate_tokens, n)
        precisions.append(p if p > 0 else 1e-9)
    bp = 1.0 if cand_len > ref_len else math.exp(1 - ref_len / cand_len)
    avg_log_prec = sum(math.log(p) for p in precisions) / max_n
    return bp * math.exp(avg_log_prec)


def compute_rouge_l(candidate_tokens, reference_tokens):
    """ROUGE-L: F1 based on LCS."""
    lcs = _lcs_length(candidate_tokens, reference_tokens)
    ref_len = len(reference_tokens)
    cand_len = len(candidate_tokens)
    if ref_len == 0 or cand_len == 0:
        return 0.0
    prec = lcs / cand_len
    rec = lcs / ref_len
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


def compute_chrf(candidate, reference, n=6):
    """chrF++: character n-gram F-score (simplified, no word n-grams)."""
    cand_chars = list(candidate)
    ref_chars = list(reference)
    if not cand_chars or not ref_chars:
        return 0.0
    prec_avg = 0.0
    rec_avg = 0.0
    for k in range(1, n + 1):
        cand_ngrams = Counter(tuple(cand_chars[i:i+k]) for i in range(len(cand_chars) - k + 1))
        ref_ngrams = Counter(tuple(ref_chars[i:i+k]) for i in range(len(ref_chars) - k + 1))
        if not cand_ngrams or not ref_ngrams:
            continue
        matches = sum(min(cand_ngrams[ng], ref_ngrams[ng]) for ng in cand_ngrams)
        prec_avg += matches / sum(cand_ngrams.values())
        rec_avg += matches / sum(ref_ngrams.values())
    prec_avg /= n
    rec_avg /= n
    if prec_avg + rec_avg == 0:
        return 0.0
    return 2 * prec_avg * rec_avg / (prec_avg + rec_avg)


def evaluate_text_similarity(model, tokenizer, dataset=None, num_samples=200, max_new_tokens=512):
    """Compute BLEU, ROUGE-L, chrF++ on final assistant responses.

    Compares generated text (outside tool/think tags) against ground truth.
    """
    if dataset is None:
        try:
            dataset = load_dataset(config.DATASET_PATH, config.DATASET_CONFIG, split="train")
        except Exception as e:
            print(f"Could not load dataset for text similarity: {e}")
            return {}

    dataset = dataset.select(range(min(num_samples, len(dataset))))

    results = {
        "total_samples": min(num_samples, len(dataset)),
        "bleu": 0.0,
        "rouge_l": 0.0,
        "chrf": 0.0,
        "errors": 0,
    }

    bleus, rouges, chrf_scores = [], [], []

    for sample in tqdm(dataset, desc="TextSim Eval"):
        try:
            convs = sample.get("conversations", [])
            gpt_indices = [i for i, t in enumerate(convs) if t.get("from") == "gpt"]
            if len(gpt_indices) < 1:
                continue

            last_gpt_idx = gpt_indices[-1]
            prompt_convs = convs[:last_gpt_idx]
            reference_convs = convs[last_gpt_idx]

            messages = hermes_to_openai_messages(prompt_convs)
            if not messages:
                continue

            response = generate_response(model, tokenizer, messages, max_new_tokens=max_new_tokens, do_sample=True)

            ref_text = extract_text_outside_tags(reference_convs.get("value", ""))
            gen_text = extract_text_outside_tags(response)

            if not ref_text or not gen_text:
                continue

            ref_tokens = ref_text.split()
            gen_tokens = gen_text.split()

            bleus.append(compute_bleu(gen_tokens, ref_tokens))
            rouges.append(compute_rouge_l(gen_tokens, ref_tokens))
            chrf_scores.append(compute_chrf(gen_text, ref_text))

        except Exception:
            results["errors"] += 1

    if bleus:
        results["bleu"] = sum(bleus) / len(bleus)
        results["rouge_l"] = sum(rouges) / len(rouges)
        results["chrf"] = sum(chrf_scores) / len(chrf_scores)

    print(f"\nText Similarity Results ({num_samples} samples):")
    print(f"  BLEU:        {results['bleu']:.4f}")
    print(f"  ROUGE-L:     {results['rouge_l']:.4f}")
    print(f"  chrF++:      {results['chrf']:.4f}")
    print(f"  Errors:      {results['errors']}")

    return results


# ── Tier 3a: MMLU Mini ───────────────────────────────────────────────

MMLU_SUBJECTS = [
    "abstract_algebra", "anatomy", "astronomy", "business_ethics", "clinical_knowledge",
    "college_biology", "college_chemistry", "college_computer_science", "college_mathematics",
    "college_medicine", "college_physics", "computer_security", "conceptual_physics",
    "econometrics", "electrical_engineering", "elementary_mathematics", "formal_logic",
    "global_facts", "high_school_biology", "high_school_chemistry", "high_school_computer_science",
    "high_school_european_history", "high_school_geography", "high_school_government_and_politics",
    "high_school_macroeconomics", "high_school_mathematics", "high_school_microeconomics",
    "high_school_physics", "high_school_psychology", "high_school_statistics",
    "high_school_us_history", "high_school_world_history", "human_aging", "human_sexuality",
    "international_law", "jurisprudence", "logical_fallacies", "machine_learning",
    "management", "marketing", "medical_genetics", "miscellaneous", "moral_disputes",
    "moral_scenarios", "nutrition", "philosophy", "prehistory", "professional_accounting",
    "professional_law", "professional_medicine", "professional_psychology", "public_relations",
    "security_studies", "sociology", "us_foreign_policy", "virology", "world_religions",
]


def evaluate_mmlu_mini(model, tokenizer, num_per_subject=5, max_new_tokens=32):
    """MMLU multi-domain knowledge accuracy on a random subset."""
    try:
        mmlu = load_dataset("cais/mmlu", "all", split="test")
    except Exception as e:
        print(f"Could not load MMLU: {e}")
        return {}

    results = {"total": 0, "correct": 0, "per_subject": {}, "errors": 0}

    for subject in tqdm(MMLU_SUBJECTS, desc="MMLU Mini"):
        sub = mmlu.filter(lambda x: x["subject"] == subject)
        sub = sub.select(range(min(num_per_subject, len(sub))))
        correct = 0
        total = 0
        for sample in sub:
            try:
                question = sample["question"]
                choices = sample["choices"]
                answer_idx = sample["answer"]

                choice_letters = "ABCD"
                choice_text = "\n".join(f"{choice_letters[i]}. {c}" for i, c in enumerate(choices))

                prompt_text = (
                    f"Answer the following multiple-choice question. "
                    f"Respond with only the letter (A, B, C, or D).\n\n"
                    f"Question: {question}\n\nChoices:\n{choice_text}\n\nAnswer:"
                )

                messages = [{"role": "user", "content": prompt_text}]
                response = generate_response(model, tokenizer, messages,
                                             max_new_tokens=max_new_tokens,
                                             temperature=0.1, do_sample=False)

                pred_letter = response.strip()[0].upper() if response.strip() else ""
                if pred_letter == choice_letters[answer_idx]:
                    correct += 1
                total += 1

            except Exception:
                results["errors"] += 1

        if total > 0:
            results["per_subject"][subject] = correct / total
            results["correct"] += correct
            results["total"] += total

    if results["total"] > 0:
        results["accuracy"] = results["correct"] / results["total"]

    total_q = results["total"]
    print(f"\nMMLU Mini Results ({total_q} questions, {num_per_subject}/subject):")
    print(f"  Accuracy:   {results.get('accuracy', 0):.2%}")
    print(f"  Correct:    {results['correct']} / {results['total']}")
    print(f"  Errors:     {results['errors']}")
    print(f"  Subjects:   {len([s for s, v in results['per_subject'].items() if v > 0])}")

    return results


# ── Tier 3b: MGSM Mini ───────────────────────────────────────────────

def evaluate_mgsm_mini(model, tokenizer, num_samples=50, lang="en", max_new_tokens=128):
    """MGSM math reasoning accuracy."""
    try:
        mgsm = load_dataset("juletxara/mgsm", lang, split="test")
    except Exception as e:
        print(f"Could not load MGSM: {e}")
        return {}

    mgsm = mgsm.select(range(min(num_samples, len(mgsm))))

    results = {"total": 0, "correct": 0, "errors": 0, "answers": []}

    for sample in tqdm(mgsm, desc="MGSM Mini"):
        try:
            question = sample["question"]
            answer = sample["answer_number"]

            prompt_text = (
                f"Solve the following math problem step by step. "
                f"End your answer with '#### <number>'.\n\n{question}"
            )

            messages = [{"role": "user", "content": prompt_text}]
            response = generate_response(model, tokenizer, messages,
                                         max_new_tokens=max_new_tokens,
                                         temperature=0.1, do_sample=False)

            pred_match = re.search(r"####\s*(-?\d+\.?\d*)", response)
            pred_num = float(pred_match.group(1)) if pred_match else None
            expected_num = float(answer)

            is_correct = pred_num is not None and abs(pred_num - expected_num) / max(1.0, abs(expected_num)) < 0.01
            if is_correct:
                results["correct"] += 1
            results["total"] += 1

        except Exception:
            results["errors"] += 1

    if results["total"] > 0:
        results["accuracy"] = results["correct"] / results["total"]

    print(f"\nMGSM Mini Results ({num_samples} samples):")
    print(f"  Accuracy:   {results.get('accuracy', 0):.2%}")
    print(f"  Correct:    {results['correct']} / {results['total']}")
    print(f"  Errors:     {results['errors']}")

    return results


# ── Existing: ToolBench Evaluation ────────────────────────────────────

def evaluate_on_toolbench(model, tokenizer, num_samples=100, max_new_tokens=512):
    try:
        eval_data = load_dataset(config.EVAL_DATASET_PATH, split="test")
        eval_data = eval_data.select(range(min(num_samples, len(eval_data))))
    except Exception as e:
        print(f"Could not load ToolBench eval set: {e}")
        print("Skipping ToolBench evaluation.")
        return {}

    results = {"correct": 0, "total": 0, "errors": 0}

    for example in tqdm(eval_data, desc="ToolBench"):
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
            actual_tools = extract_tool_calls_old(response)

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


# ── Orchestrator ──────────────────────────────────────────────────────

def run_evaluation(model, tokenizer, wandb_key=None,
                   eval_toolbench=True,
                   eval_hermes=True,
                   eval_text_sim=True,
                   eval_selfcheck=True,
                   eval_mmlu=False,
                   eval_mgsm=False,
                   num_samples_toolbench=100,
                   num_samples_hermes=200,
                   num_samples_textsim=200,
                   num_samples_selfcheck=50,
                   num_selfcheck_generations=5,
                   num_mmlu_per_subject=5,
                   num_mgsm=50,
                   max_new_tokens=512,
                   ):
    print("\n" + "=" * 60)
    print("EVALUATION SUITE")
    print("=" * 60)

    FastModel.for_inference(model)

    all_results = {}

    if eval_toolbench:
        print("\n--- ToolBench Evaluation ---")
        all_results["toolbench"] = evaluate_on_toolbench(
            model, tokenizer, num_samples=num_samples_toolbench, max_new_tokens=max_new_tokens
        )

    if eval_hermes:
        print("\n--- Hermes Holdout Evaluation ---")
        all_results["hermes"] = evaluate_on_hermes(
            model, tokenizer, num_samples=num_samples_hermes, max_new_tokens=max_new_tokens
        )

    if eval_selfcheck:
        print("\n--- SelfCheck Consistency ---")
        all_results["selfcheck"] = evaluate_selfcheck(
            model, tokenizer, num_samples=num_samples_selfcheck,
            num_generations=num_selfcheck_generations, max_new_tokens=max_new_tokens
        )

    if eval_text_sim:
        print("\n--- Text Similarity ---")
        all_results["text_similarity"] = evaluate_text_similarity(
            model, tokenizer, num_samples=num_samples_textsim, max_new_tokens=max_new_tokens
        )

    if eval_mmlu:
        print("\n--- MMLU Mini ---")
        all_results["mmlu"] = evaluate_mmlu_mini(
            model, tokenizer, num_per_subject=num_mmlu_per_subject, max_new_tokens=max_new_tokens
        )

    if eval_mgsm:
        print("\n--- MGSM Mini ---")
        all_results["mgsm"] = evaluate_mgsm_mini(
            model, tokenizer, num_samples=num_mgsm, max_new_tokens=max_new_tokens
        )

    if wandb_key:
        import wandb
        flat = {}
        for suite, metrics in all_results.items():
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    flat[f"eval/{suite}_{k}"] = v
        if flat:
            wandb.log(flat)

    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)

    return all_results
