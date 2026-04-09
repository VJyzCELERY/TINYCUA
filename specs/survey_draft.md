# Fine-Tuning Survey Draft

**Status**: Draft
**Created**: 2026-04-09
**Branch**: requirements-survey

---

## Purpose

This document surveys fine-tuning approaches, best practices, and considerations for building a computer use agent capable of tool calling and vision-language tasks.

---

## 1. Fine-Tuning Approaches

### 1.1 Full Fine-Tuning
- **Pros**: Maximum adaptation to target domain
- **Cons**: High VRAM requirement, risk of catastrophic forgetting
- **VRAM**: ~28GB for 7B model (float16)

### 1.2 LoRA (Low-Rank Adaptation)
- **Pros**: Low VRAM, efficient, maintains base model knowledge
- **Cons**: May not fully capture complex behaviors
- **VRAM**: ~14GB for 7B model (float16)

### 1.3 QLoRA (Quantized LoRA)
- **Pros**: Very low VRAM, 4-bit quantization
- **Cons**: Slight quality trade-off
- **VRAM**: ~10-12GB for 7B model
- **Target Hardware**: RTX 5080 16GB VRAM

---

## 2. Target Hardware

| Component | Specification |
|-----------|---------------|
| CPU | Intel Ultra 9 275HX |
| GPU | RTX 5080 Laptop GPU |
| VRAM | 16 GB |
| RAM | 32 GB DDR5 6400 MT/s |

### VRAM Optimization Strategies
1. Gradient checkpointing
2. 4-bit quantization (NF4)
3. Mixed precision training (fp16)
4. Optimal batch size: 1 with gradient accumulation 8
5. Max sequence length: 512 (can increase if VRAM allows)

---

## 3. Model Options

### 3.1 Text-Only Models
| Model | Parameters | VRAM (QLoRA) | Quality |
|-------|------------|---------------|---------|
| Qwen2.5-7B | 7B | ~10GB | High |
| Mistral-7B | 7B | ~10GB | High |
| Llama-2-7B | 7B | ~10GB | Medium |

### 3.2 Vision-Language Models
| Model | Parameters | VRAM (QLoRA) | Notes |
|-------|------------|---------------|-------|
| Qwen2.5-VL-7B | 7B | ~12GB | Recommended |
| LLaVA-1.6-7B | 7B | ~12GB | Good for screenshots |
| CogVLM-7B | 7B | ~14GB | Higher quality |

---

## 4. Dataset Considerations

### 4.1 Training Data Format
```json
{
  "id": "record_001",
  "instruction": "Task description",
  "image": "path/to/image.png",  // For VLM
  "tool_calls": [
    {
      "name": "tool_name",
      "args": "{\"arg1\": \"value1\"}",
      "result": "execution result"
    }
  ],
  "output": "Final response"
}
```

### 4.2 Dataset Size Recommendations
| Use Case | Min Records | Recommended |
|----------|------------|-------------|
| Testing/Dev | 10 | 50 |
| Fine-tuning | 100 | 1000+ |
| Production | 5000+ | 10000+ |

### 4.3 Data Quality Guidelines
- Diverse tool usage examples
- Varied instruction phrasing
- Realistic tool call sequences
- Accurate tool results (or realistic dry-run outputs)

---

## 5. Tool Manifest Schema

### Required Fields
```json
{
  "name": "tool_name",
  "description": "What the tool does",
  "args_schema": {"arg1": "type"},
  "example_call": {"arg1": "value"},
  "dry_run_output": "Expected output"
}
```

### Tool Types for Computer Use
1. **UI Interaction**: click, type, scroll, drag
2. **Screen Capture**: screenshot, screen_region
3. **Text Extraction**: read, ocr, extract_text
4. **File Operations**: read_file, write_file, list_dir
5. **Search**: web_search, find_element
6. **System**: execute_command, get_clipboard

---

## 6. Training Pipeline

### 6.1 Stages
```
Tool Manifests → Dataset Synthesizer → JSONL Dataset
                                          ↓
Base Model ← Download Script ← HuggingFace
                ↓
        Tokenization (with special tokens)
                ↓
        Training (QLoRA/LoRA/Offload/VLM)
                ↓
        LoRA Adapter Checkpoint
                ↓
        Merge Adapter → HF Checkpoint
                ↓
        Convert to GGUF → Local Inference Ready
```

### 6.2 Special Tokens for Tool Calling
```
<tool> </tool>
<tool_name> </tool_name>
<tool_args> </tool_args>
<tool_result> </tool_result>
```

---

## 7. Open Questions

- [ ] Dataset size for effective fine-tuning?
- [ ] Optimal LoRA rank (r=16 vs r=32)?
- [ ] Training epochs for convergence?
- [ ] Evaluation metrics for tool-calling accuracy?
- [ ] Retention testing for base model knowledge?

---

## 8. Next Steps

1. [ ] Finalize dataset schema
2. [ ] Collect/gather training data
3. [ ] Test fine-tuning pipeline with small dataset
4. [ ] Evaluate model quality
5. [ ] Scale up training data
6. [ ] Optimize for production deployment

---

## References

- QLoRA: Efficient Fine-Tuning of Quantized LLMs (Dettmers et al.)
- LLaVA: Large Language and Vision Assistant
- Qwen2.5-VL Technical Report
- PEFT: Parameter-Efficient Fine-Tuning
