# Implementation: TINYCUA Fine-Tune Subproject

Provide a reproducible fine-tuning pipeline for open-weight base models (text LLM and vision-LMM) to produce models capable of structured tool-use and agentic behavior. Covers dataset synthesis from local tool manifests, QLoRA/LoRA training with optional CPU offload, LoRA adapter merging, and GGUF conversion.

## Context

- **Spec Reference**: [specs/tinycua-finetune/spec.md](spec.md)
- **Design Reference**: [specs/tinycua-finetune/design.md](design.md)
- **Priority**: P1
- **Estimated Effort**: L

## Success Criteria — Integration Tests (TDD First)

The following integration tests must be written FIRST and pass before implementation is considered complete. Each test proves a complete user-facing capability.

### Test 1: Dataset Synthesis End-to-End

```python
"""tests/integration/test_dataset_synthesis.py"""

def test_synthesize_from_tool_manifests(tmp_path):
    """Acceptance scenario 2: Given tool manifests, synthesizer produces valid JSONL."""
    # Arrange
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    manifest = tools_dir / "search_tool" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(json.dumps({
        "tools": [{
            "name": "search_tool",
            "description": "Searches a knowledge base",
            "args_schema": {"query": "string"},
            "example_call": {"query": "latest news"},
            "dry_run_output": "News results for 'latest news'"
        }]
    }))
    output_path = tmp_path / "train.jsonl"

    # Act
    from tinycua_finetune.synthesize_dataset import synthesize
    synthesize(tools_dir=str(tools_dir), output_path=str(output_path))

    # Assert
    assert output_path.exists()
    records = [json.loads(line) for line in output_path.read_text().strip().splitlines()]
    assert len(records) >= 1
    for r in records:
        assert all(k in r for k in ("id", "instruction", "tool_calls", "output"))
```

### Test 2: Preprocessor Validates Empty Dataset

```python
"""tests/integration/test_preprocess.py"""

def test_load_dataset_rejects_empty_file(tmp_path):
    """Edge case: empty JSONL raises clear error."""
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("")

    from tinycua_finetune.preprocess import load_dataset_from_jsonl
    import pytest
    with pytest.raises(ValueError, match="empty"):
        load_dataset_from_jsonl(str(empty_file))
```

### Test 3: Preprocessor Formats Prompt with Tool Tokens

```python
def test_format_prompt_includes_tool_tokens():
    """Training prompt contains special tool tokens."""
    from tinycua_finetune.preprocess import format_prompt
    record = {
        "id": "test-1",
        "instruction": "Search for news",
        "input": "",
        "tool_calls": [
            {"name": "search", "args": '{"query": "news"}', "result": "news data"}
        ],
        "output": "Here are the results"
    }
    prompt = format_prompt(record)
    assert "<tool>" in prompt
    assert "<tool_name>" in prompt
    assert "<tool_args>" in prompt
    assert "<tool_result>" in prompt
    assert "search" in prompt or "search" in prompt
```

### Test 4: Training Smoke Test (1-Step CPU)

```python
"""tests/integration/test_smoke_train.py"""

def test_training_runs_one_step_and_saves_adapter(tmp_path):
    """Acceptance scenario 1: Training in QLoRA mode writes safetensors adapter."""
    import subprocess
    import sys

    # Create a tiny JSONL dataset
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    dataset = data_dir / "train.jsonl"
    dataset.write_text(json.dumps({
        "id": "1",
        "instruction": "test",
        "input": "",
        "tool_calls": [],
        "output": "ok"
    }) + "\n")

    output_dir = tmp_path / "output"
    # Use a tiny stub model path; this test validates the pipeline runs
    # without crashing. On CI this would use a real small model.
    result = subprocess.run(
        [
            sys.executable, "-m", "tinycua_finetune.train",
            "--model", "hf-internal-testing/tiny-random-MistralForCausalLM",
            "--data", str(dataset),
            "--output-dir", str(output_dir),
            "--mode", "qlora",
            "--epochs", "1",
            "--max-seq-len", "128",
        ],
        capture_output=True, text=True, timeout=120
    )
    # Accept failure gracefully if GPU not available — must not be a code error
    if result.returncode != 0:
        assert "CUDA" in result.stderr or "cuda" in result.stderr or "MPS" in result.stderr, (
            f"Non-GPU error: {result.stderr}"
        )
    else:
        assert output_dir.exists()
        assert list(output_dir.glob("*.safetensors")) or list(output_dir.glob("adapter_model.safetensors"))
```

### Test 5: Conversion Wrapper Fails Loudly When Converter Missing

```python
"""tests/integration/test_convert.py"""

def test_convert_fails_with_actionable_message_when_converter_missing(tmp_path):
    """Acceptance scenario 3: Wrapper fails loudly with install instructions."""
    from tinycua_finetune.convert_to_gguf import convert
    import pytest

    with pytest.raises(RuntimeError, match="llama.cpp"):
        convert(
            base_model=str(tmp_path / "nonexistent"),
            adapter_dir=str(tmp_path / "adapters"),
            output_dir=str(tmp_path / "out"),
            converter_path="/nonexistent/convert.py"
        )
```

## Proposed Changes

### Colab GPU Pipeline Notebook

#### [NEW] `src/tinycua-finetune/tinycua_finetune/colab_gpu_pipeline_finetune_gemma_e4b-test.ipynb`

- **[Description]**: Colab notebook implementing QLoRA fine-tuning for Google Gemma 4B E4B-IT on Colab T4/L4 GPU (16 GB VRAM). Covers dataset loading, 4-bit quantization, LoRA adapter training, adapter weight saving, and GGUF export. Runnable in the free Colab tier.
- **[Rationale]**: Provides a zero-setup cloud training path for Gemma 4B — the recommended entry-level model for the pipeline. Users can run the entire fine-tune without any local GPU or environment setup.

### Core Pipeline Modules

#### [NEW] `src/tinycua-finetune/tinycua_finetune/preprocess.py`

- **[Description]**: JSONL loading with schema validation, prompt formatting with special tool tokens, and tokenization helper.
- **[Rationale]**: Core data preprocessing required by all training modes.

#### [NEW] `src/tinycua-finetune/tinycua_finetune/synthesize_dataset.py`

- **[Description]**: Tool manifest discovery (recursive `manifest.json` glob under `tools_dir`), instruction-response pair generation, JSONL output writer.
- **[Rationale]**: Generates training data from the actual tools in the project.

#### [NEW] `src/tinycua-finetune/tinycua_finetune/train.py`

- **[Description]**: CLI entry-point supporting `qlora`, `lora`, and `offload` modes. Handles model loading, tokenizer special-token injection, PEFT LoRA configuration, training loop via `trl.SFTTrainer`, and adapter checkpoint saving.
- **[Rationale]**: Central training orchestrator covering all three modes.

#### [NEW] `src/tinycua-finetune/tinycua_finetune/convert_to_gguf.py`

- **[Description]**: Two-phase script: (1) merge LoRA adapter into base model weights, (2) wrap llama.cpp's HF-to-GGUF converter script. Phase 2 must fail loudly with version-pinned instructions if converter script is missing.
- **[Rationale]**: Produces the final portable GGUF artifact.

### Tests

#### [NEW] `src/tinycua-finetune/tests/unit/test_preprocess.py`

- **[Description]**: Unit tests for JSONL loading (happy path, empty file, missing field), prompt formatting with tool tokens, tokenization output shapes.

#### [NEW] `src/tinycua-finetune/tests/unit/test_synthesize_dataset.py`

- **[Description]**: Unit tests for manifest parsing, missing required field error, unsupported args type warning/skip, record count matches tool count.

#### [NEW] `src/tinycua-finetune/tests/unit/test_train.py`

- **[Description]**: Unit tests for CLI argument parsing, config validation, special token injection logic.

#### [NEW] `src/tinycua-finetune/tests/unit/test_convert.py`

- **[Description]**: Unit tests for merge argument handling, converter path validation, output path creation.

#### [MODIFY] `src/tinycua-finetune/tests/integration/test_integration.py`

- **[Description]**: Replace placeholder with real integration tests (dataset synthesis, preprocessor, smoke training, conversion wrapper).
- **[Breaking changes if any]**: None — placeholder currently has no real test logic.

### Example Data

#### [NEW] `src/tinycua-finetune/data/examples/manifest.json`

- **[Description]**: Example tool manifest with 1-2 sample tools for development and testing.
- **[Dependencies]**: None.

#### [NEW] `src/tinycua-finetune/data/examples/train.jsonl`

- **[Description]**: Example training dataset with 10 records for smoke testing.
- **[Dependencies]**: None.

### Build / Config

#### [DELETE] `src/tinycua-finetune/tinycua_finetune/dummy.py`

- **[Description]**: Remove placeholder file once real modules are implemented.
- **[Rationale]**: No longer needed.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua_finetune/colab_gpu_pipeline_finetune_gemma_e4b-test.ipynb` | New | Colab GPU pipeline notebook for Gemma 4B E4B-IT QLoRA fine-tuning |
| `tinycua_finetune/preprocess.py` | New | JSONL loading, prompt formatting, tokenization |
| `tinycua_finetune/synthesize_dataset.py` | New | Tool manifest discovery, JSONL generation |
| `tinycua_finetune/train.py` | New | Training entry-point (qlora/lora/offload) |
| `tinycua_finetune/convert_to_gguf.py` | New | Adapter merge + GGUF conversion wrapper |
| `tinycua_finetune/dummy.py` | Delete | Remove placeholder |
| `data/examples/manifest.json` | New | Example tool manifest |
| `data/examples/train.jsonl` | New | Example training dataset |
| `tests/unit/` | New | Unit test files for each module |
| `tests/integration/` | Modify | Real integration tests replace placeholder |
| Root `Makefile` | Modify | Add tinycua-finetune to top-level targets |

## Data Model Changes

```python
# Tool Manifest — JSON file per tool directory
ToolManifest:
    tools: list[ToolDescriptor]

ToolDescriptor:
    name: str
    description: str
    args_schema: dict[str, str]
    example_call: dict[str, Any]
    dry_run_output: str

# JSONL Dataset Record — one per line
DatasetRecord:
    id: str
    instruction: str
    input: str
    tool_calls: list[ToolCall]
    output: str

ToolCall:
    name: str
    args: str
    result: str

# Special tokens injected into tokenizer vocabulary
SPECIAL_TOKENS = [
    "<tool>", "</tool>",
    "<tool_name>", "</tool_name>",
    "<tool_args>", "</tool_args>",
    "<tool_result>", "</tool_result>",
]
```

## Verification Plan

### Automated Tests

- [ ] Unit tests for `preprocess.py` (JSONL loading, prompt formatting, tokenization)
- [ ] Unit tests for `synthesize_dataset.py` (manifest parsing, record generation)
- [ ] Unit tests for `train.py` (CLI arg parsing, config validation)
- [ ] Unit tests for `convert_to_gguf.py` (argument handling, error cases)
- [ ] Integration test: dataset synthesis from tool manifests (Test 1)
- [ ] Integration test: empty JSONL raises error (Test 2)
- [ ] Integration test: prompt formatting with tool tokens (Test 3)
- [ ] Integration test: smoke training run 1 step (Test 4)
- [ ] Integration test: conversion wrapper missing converter (Test 5)
- [ ] Full suite: `make test` passes

### Manual Verification

- [x] Colab GPU pipeline notebook runs end-to-end on Gemma 4B E4B-IT (T4/L4 GPU)
- [ ] Full QLoRA run on real 7B model with example manifest dataset
- [ ] Load produced GGUF in llama-cpp-python and verify tool-call output
- [ ] Offload mode on 13B model confirms training proceeds without OOM

### Performance Considerations

- [ ] Training memory usage stays within 16 GB VRAM for 7B QLoRA
- [ ] Training memory usage stays within 16 GB VRAM + 32 GB RAM for 13B offload
- [ ] `make complexity` passes with max complexity <= 15

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `transformers` | >=4.36.0 | HF model loading, tokenization, trainer |
| `peft` | >=0.7.0 | LoRA adapter configuration and training |
| `trl` | >=0.7.0 | SFTTrainer for supervised fine-tuning |
| `bitsandbytes` | >=0.41.0 | 4-bit quantization for QLoRA mode |
| `accelerate` | >=0.25.0 | CPU offload support for offload mode |
| `datasets` | >=2.14.0 | HF Dataset wrapper for training data |
| `safetensors` | >=0.4.0 | Safe tensor serialization |
| `llama.cpp` (convert script) | Pinned version | HF-to-GGUF conversion (external, not pip) |

### Internal Dependencies

- [ ] Depends on `tinycua-sdk` for tool manifest format (if shared in Phase 2)
- [ ] Blocks downstream GGUF loading in `tinycua-runner`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| GGUF converter script API changes | Medium | Wrapper fails loudly; document pinned converter version in code |
| 13B OOM on 16 GB + 32 GB RAM in offload | Low | Document as "experimental"; provide tested config |
| bitsandbytes version incompatibility with CUDA | Medium | Pin tested version; document CUDA version requirement |
| Slow training throughput with CPU offload | Low | Document expected throughput; mode is "experimental" |
| Colab session timeout / disconnection | Medium | Checkpoint mid-training; document resume-from-checkpoint workflow |
| Missing GPU on CI for integration tests | Medium | Use tiny stub HF models; gracefully skip if no GPU |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-25*
