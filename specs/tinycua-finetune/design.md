# Design Document: TINYCUA Fine-Tune Subproject

**Spec**: [specs/tinycua-finetune/spec.md](spec.md)
**Status**: In Progress
**Last Updated**: 2026-05-25

---

## Overview

This document describes the technical design of `tinycua-finetune`, a new subproject that
provides a supervised fine-tuning pipeline for open-weight text LLMs and vision-LMMs to
produce models capable of structured tool-use and agentic behavior. The pipeline covers
dataset synthesis from local tool manifests, QLoRA/LoRA training with optional CPU offload,
LoRA adapter merging, and GGUF conversion. It targets single-GPU consumer hardware (16 GB
VRAM for 7B models; experimental CPU-offload path for 13B). The key architectural decision
is to use PEFT LoRA adapters on top of a quantized (bitsandbytes 4-bit) base model so the
pipeline remains runnable on a single consumer GPU while the final artifact is a standalone
GGUF file loadable by llama.cpp.

---

## Architecture

### Component Overview

```
[Tool Manifest Directory]
         |
         v
[Dataset Synthesizer]  ──────────────────────>  [JSONL Training Dataset]
(synthesize_dataset.py)                                    |
                                                           v
                                              [Data Preprocessor]
                                              (preprocess.py)
                                                           |
                                           tokenized HF Dataset
                                                           |
                    [Base Model (HF format, local dir)]    |
                                    |                      |
                                    v                      v
                          [Training Engine] <─────────────'
                          (train.py)
                          modes: qlora | lora | offload
                                    |
                                    v
                       [LoRA Adapter Checkpoint]
                       (safetensors, output_dir/)
                                    |
                                    v
                       [Adapter Merge Step]
                       (convert_to_gguf.py, phase 1 of 2)
                                    |
                                    v
                   [Merged HF Checkpoint (safetensors)]
                                    |
                                    v
                   [GGUF Conversion Wrapper]
                   (convert_to_gguf.py, phase 2 of 2)
                   (wraps community llama.cpp converter)
                                    |
                                    v
                        [.gguf artifact (output_dir/)]
```

### Affected Components

| Component                    | Change Type | Notes                                              |
|------------------------------|-------------|----------------------------------------------------|
| `tinycua_finetune/colab_gpu_pipeline_finetune_gemma_e4b-test.ipynb` | New | Colab GPU pipeline notebook for Gemma 4B E4B-IT |
| `tinycua_finetune/preprocess.py`           | New         | JSONL loading, prompt formatting, tokenization     |
| `tinycua_finetune/synthesize_dataset.py`   | New         | Tool manifest discovery, JSONL generation          |
| `tinycua_finetune/train.py`                | New         | Training entry-point, QLoRA/LoRA/offload modes     |
| `tinycua_finetune/convert_to_gguf.py`      | New         | Adapter merge + GGUF conversion wrapper            |
| `data/examples/`                           | New         | Example tool manifests and JSONL training datasets |
| `src/tinycua-finetune/Makefile`            | New         | Build targets for this subproject                  |
| Root `Makefile`                            | Modified    | Add tinycua-finetune to top-level targets          |

---

## Data Model

### Tool Manifest Schema

Each tool directory must contain a `manifest.json` with the following shape:

```python
# Conceptual data shape
ToolManifest:
    tools: list[ToolDescriptor]

ToolDescriptor:
    name: str                      # snake_case unique identifier
    description: str               # human-readable description of what the tool does
    args_schema: dict[str, str]    # mapping of arg name -> type string (e.g. "string", "int")
    example_call: dict[str, Any]   # example argument values
    dry_run_output: str            # example output string used by the synthesizer
```

### JSONL Dataset Record Schema

Each line in a training JSONL file must be a valid JSON object:

```python
# Conceptual data shape
DatasetRecord:
    id: str                        # unique identifier for this record
    instruction: str               # natural-language task description
    input: str                     # optional additional context (empty string if unused)
    tool_calls: list[ToolCall]     # ordered list of tool invocations (may be empty)
    output: str                    # expected final answer from the model

ToolCall:
    name: str                      # tool name matching a manifest descriptor
    args: str                      # serialized arguments (JSON string)
    result: str                    # tool execution result (from dry_run_output)
```

### Training Prompt Format

The preprocessor formats each record into a single string used as both the model input
and the training target (causal LM — all tokens are trained):

```
### Instruction:
{instruction}

### Input:
{input}

### Response:
<tool><tool_name>{name}</tool_name><tool_args>{args}</tool_args></tool>
<tool_result>{result}</tool_result>
{output}
```

If `tool_calls` is empty the `<tool>...</tool_result>` block is omitted.

### Special Tokens

The following tokens are added to the tokenizer vocabulary before training and the model
embedding matrix is resized to accommodate them:

```
<tool>        </tool>
<tool_name>   </tool_name>
<tool_args>   </tool_args>
<tool_result> </tool_result>
```

---

## API / Interface Contracts

### `preprocess.py`

```python
def load_dataset_from_jsonl(path: str) -> list[dict]:
    """
    Load and validate training records from a JSONL file.

    Args:
        path (str): Path to the JSONL file.

    Returns:
        list[dict]: List of validated record dicts.

    Raises:
        ValueError: If the file is empty or a record is missing required fields.
        FileNotFoundError: If the path does not exist.
    """

def format_prompt(record: dict) -> str:
    """
    Format a single training record into the prompt string.

    Args:
        record (dict): A validated DatasetRecord dict.

    Returns:
        str: Formatted prompt string ready for tokenization.
    """
```

### `synthesize_dataset.py`

```python
def discover_manifests(tools_dir: str) -> list[dict]:
    """
    Recursively discover manifest.json files under tools_dir.

    Args:
        tools_dir (str): Root directory containing tool subdirectories.

    Returns:
        list[dict]: List of parsed ToolManifest dicts.

    Raises:
        FileNotFoundError: If tools_dir does not exist.
    """

def synthesize(tools_dir: str, output_path: str) -> None:
    """
    Generate a JSONL training dataset from discovered tool manifests.

    Args:
        tools_dir (str): Root directory containing tool subdirectories.
        output_path (str): Destination JSONL file path.

    Raises:
        ValueError: If a manifest is missing required fields.
    """
```

### `train.py` (CLI)

```
python -m tinycua_finetune.train \
  --model <local_hf_model_dir> \
  --data  <train.jsonl> \
  --output-dir <output_dir> \
  --mode  {qlora,lora,offload}  [default: qlora] \
  --lora-r        <int>         [default: 16] \
  --lora-alpha    <int>         [default: 32] \
  --lora-dropout  <float>       [default: 0.05] \
  --batch-size    <int>         [default: 1] \
  --grad-accum    <int>         [default: 8] \
  --lr            <float>       [default: 1e-4] \
  --epochs        <int>         [default: 1] \
  --max-seq-len   <int>         [default: 512] \
  --offload-dir   <path>        [only for offload mode]
```

### `convert_to_gguf.py` (CLI)

```
python -m tinycua_finetune.convert_to_gguf \
  --base-model  <local_hf_model_dir> \
  --adapter-dir <lora_adapter_dir> \
  --output-dir  <output_dir> \
  [--skip-merge]        # if base + adapter are already merged
  [--converter-path <path_to_convert_hf_to_gguf_script>]
```

### Error Handling

| Error Case                        | Exception / Exit                          | Notes                                    |
|-----------------------------------|-------------------------------------------|------------------------------------------|
| Empty JSONL file                  | `ValueError("Dataset is empty: <path>")` |                                          |
| Missing required record field     | `ValueError("Missing field '<f>' in record <id>")` |                               |
| Model directory not found         | `FileNotFoundError`                       | From `from_pretrained`                   |
| GGUF converter not found          | `RuntimeError` with install instructions  | Must name expected script + version      |
| Invalid manifest field type       | `logging.warning` + skip                  | Non-fatal; logged and tool is skipped    |
| GPU OOM without offload           | Propagated as-is (`torch.cuda.OOMError`)  | No silent fallback                       |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [x] `tinycua_finetune/colab_gpu_pipeline_finetune_gemma_e4b-test.ipynb` — Colab GPU pipeline for Gemma 4B E4B-IT QLoRA fine-tuning (T4/L4 GPU)
- [ ] `tinycua_finetune/preprocess.py` — JSONL loader, prompt formatter, tokenizer helper
- [ ] `tinycua_finetune/synthesize_dataset.py` — manifest discovery + JSONL generator
- [ ] `tinycua_finetune/train.py` — training entry-point (qlora, lora, offload modes)
- [ ] `tinycua_finetune/convert_to_gguf.py` — adapter merge + GGUF conversion wrapper
- [ ] `data/examples/manifest.json` — example tool manifest
- [ ] `data/examples/train.jsonl` — example training dataset (10 records)
- [ ] `tests/unit/test_preprocess.py` — unit tests for preprocessor
- [ ] `tests/unit/test_synthesize_dataset.py` — unit tests for synthesizer
- [ ] `tests/integration/test_smoke_train.py` — smoke integration test (1-step CPU run)
- [ ] `Makefile` — `install`, `lint`, `test`, `coverage`, `complexity`, `clean`,
      `train-qlora`, `train-offload`, `convert`

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Vision-LMM support: freeze image encoder, LoRA on LLM side only (`--mode vlm`)
- [ ] Multimodal JSONL schema with `image` field
- [ ] GPTQ quantization step before GGUF conversion
- [ ] DeepSpeed ZeRO stage 3 config for extreme memory constraints (`--mode deepspeed`)
- [ ] CI GPU runner integration test

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **QLoRA as the default training mode**
   - **Reason**: 4-bit quantization + LoRA adapters enables 7B model fine-tuning within
     16 GB VRAM. This matches the primary target hardware (RTX 5080 laptop, 16 GB).
   - **Alternatives Considered**: Full fine-tune — rejected (exceeds VRAM for 7B+); LoRA
     only (float16) — available as `--mode lora` but not the default due to higher memory.

2. **Accelerate CPU offload for the 13B experimental path**
   - **Reason**: Simpler configuration than DeepSpeed for a single-node setup. Leverages
     the available 32 GB system RAM without requiring a multi-process launcher.
   - **Alternatives Considered**: DeepSpeed ZeRO stage 3 — retained as a Phase 2 option
     for users who need maximum memory reduction; rejected for Phase 1 due to setup
     complexity.

3. **safetensors for all checkpoint output**
   - **Reason**: Safer serialization (no arbitrary code execution), broadly compatible
     with the HF ecosystem and GGUF converters.
   - **Alternatives Considered**: pickle-based `.bin` — rejected for security reasons.

4. **JSONL for the training dataset format**
   - **Reason**: Simple, line-by-line streamable, easy to generate and inspect. No
     dependency on a database or binary format.
   - **Alternatives Considered**: Parquet / Arrow — rejected as overkill for the dataset
     sizes expected at this stage.

5. **Special tokens for tool-call structure**
   - **Reason**: Deterministic parsing of tool invocations from model output. Avoids
     fragile regex over free-form text.
   - **Alternatives Considered**: JSON-in-output — possible but adds parsing complexity
     and is harder to teach reliably with small datasets.

6. **Phase 1 text-only, Phase 2 vision**
   - **Reason**: Text LLM tool-use is the core MVP. Vision-LMM adds significant
     preprocessing and model-family complexity that should not block Phase 1 delivery.

7. **GGUF conversion via external community tools (wrapper approach)**
   - **Reason**: GGUF converter scripts are maintained by the llama.cpp community and
     change frequently. Wrapping them (rather than embedding) keeps our code minimal and
     easy to update. The wrapper must fail loudly with actionable instructions if the
     expected converter script is missing.

---

## Risks & Mitigations

| Risk                                      | Likelihood | Impact | Mitigation                                                     |
|-------------------------------------------|------------|--------|----------------------------------------------------------------|
| GGUF converter script API changes         | High       | Medium | Wrapper fails loudly; document pinned converter version        |
| 13B OOM on 16 GB + 32 GB RAM in offload   | Medium     | Low    | Document as "experimental"; tested config included in docs     |
| Base model license incompatibility        | Medium     | High   | Spec and README document known-compatible model families       |
| bitsandbytes version incompatibility      | Medium     | Medium | Pin tested version in requirements.txt; document CUDA version  |
| Slow training throughput with CPU offload | High       | Low    | Document expected throughput; offload mode is "experimental"   |

---

## Open Questions

1. Should the tool manifest schema be defined centrally in `tinycua-sdk` and referenced
   here, or defined locally in `tinycua-finetune`? Local for Phase 1; migrate to SDK in
   Phase 2 if the manifest format stabilises.

2. Which specific llama.cpp conversion script version should be pinned for Phase 1?
   Resolve before implementation starts.

---

## References

- Spec: `specs/tinycua-finetune/spec.md`
- Project Guidelines: `PROJECT-GUIDELINES.md`
- Coding Standards: `docs/project_rules/coding_standards.md`
- Testing Guidelines: `docs/project_rules/testing_guidelines.md`
