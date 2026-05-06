# Hardware & Quantization for LLM Fine-tuning

This document covers hardware requirements and quantization techniques essential for fine-tuning 9B parameter models on 16GB VRAM GPUs.

---

## 1. GPU Hardware for LLM Fine-tuning

### Your Target Hardware: RTX 5080 Laptop

| Specification | Value |
|---------------|-------|
| **VRAM** | 16 GB |
| **Memory Type** | GDDR7 |
| **CUDA Cores** | ~10,000+ |
| **TDP** | ~150W |

### Alternative GPUs (16GB VRAM)

| GPU | VRAM | Performance | Price |
|-----|------|-------------|-------|
| RTX 4090 (Laptop) | 16GB | Best | High |
| RTX 4080 (Laptop) | 12GB | Good | Medium |
| **RTX 5080** | 16GB | Best | High |
| RTX 3090 | 24GB | Good | Medium |
| RTX 4090 (Desktop) | 24GB | Best | Very High |

---

## 2. Quantization Methods

### 2.1 GPTQ (Accurate Post-Training Quantization)

**Reference**: GPTQ: Accurate Post-Training Quantization for LLMs  
**Year**: 2022  
**Source**: https://arxiv.org/abs/2210.17323

### Summary
- Loss-aware quantization method
- Optimizes for reconstruction error
- Achieves near FP16 quality at 4-bit

### Key Findings
- 4-bit quantization preserves 99% of quality
- Works well for inference
- Can be applied to fine-tuning with QLoRA

### Citation
```
@article{gptq_2022,
  title={GPTQ: Accurate Post-Training Quantization for LLMs},
  author={Frantar, Elias and Alistarh, Dan},
  journal={arXiv preprint arXiv:2210.17323},
  year={2022}
}
```

---

### 2.2 AWQ (Activation-Aware Weight Quantization)

**Reference**: AWQ: Activation-Aware Weight Quantization  
**Year**: 2024  
**Source**: https://arxiv.org/abs/2406.00588

### Summary
- Focuses on activation scales rather than weight precision
- Better for large models
- Used in many production deployments

### Key Findings
- Better than GPTQ for larger models
- 4-bit with minimal quality loss
- Faster inference

### Citation
```
@article{awq_2024,
  title={AWQ: Activation-Aware Weight Quantization},
  author={Lin, Ji and others},
  journal={arXiv preprint arXiv:2406.00588},
  year={2024}
}
```

---

### 2.3 NF4 (Normal Float 4)

**Reference**: QLoRA Paper  
**Year**: 2023  
**Source**: https://arxiv.org/abs/2305.14314

### Summary
- Used in QLoRA for 4-bit quantization
- Optimized for normal weight distributions
- Double quantization for additional savings

### Key Findings
- Best for LLM weights
- Used in bitsandbytes library
- Enables 4-bit fine-tuning

### Citation
```
@article{nf4_2023,
  title={QLoRA: Efficient Finetuning of Quantized LLMs},
  author={Dettmers, Tim and others},
  journal={arXiv preprint arXiv:2305.14314},
  year={2023}
}
```

---

## 3. Flash Attention

**Reference**: Flash Attention 2  
**Year**: 2023  
**Source**: https://arxiv.org/abs/2407.13382

### Summary
- Memory-efficient attention mechanism
- Reduces memory from O(N²) to O(N)
- Essential for long context training

### Key Findings
- 2-4x faster than standard attention
- 5-20x memory savings
- Required for 2048+ context lengths

### Citation
```
@article{flash_attention_2023,
  title={Flash Attention 2},
  author={Dao, Tri},
  journal={arXiv preprint arXiv:2407.13382},
  year={2023}
}
```

---

## 4. Gradient Checkpointing

**Reference**: Training Deep Nets with Sublinear Memory Cost  
**Year**: 2016  
**Source**: https://arxiv.org/abs/1604.06174

### Summary
- Trades compute for memory
- Recomputes activations during backward pass
- Essential for large model training

### Key Findings
- Can reduce memory by 50-70%
- Increases training time by 20-30%
- Critical for 9B model on 16GB VRAM

### Citation
```
@article{gradient_checkpointing_2016,
  title={Training Deep Nets with Sublinear Memory Cost},
  author={Chen, Tianqi and Xu, Bing and others},
  journal={arXiv preprint arXiv:1604.06174},
  year={2016}
}
```

---

## 5. VRAM Optimization Checklist

### For 9B Model on 16GB VRAM

| Technique | Memory Savings | Recommendation |
|-----------|-----------------|----------------|
| **4-bit Quantization (NF4)** | ~50% | Required |
| **Gradient Checkpointing** | ~30-50% | Required |
| **Flash Attention** | ~20% | Recommended |
| **Gradient Accumulation** | Variable | Use 12 steps |
| **Batch Size 1** | - | Required |
| **Mixed Precision (FP16)** | ~50% | Required |

---

## 6. Memory Breakdown: QLoRA 9B on 16GB VRAM

| Component | Memory (GB) |
|-----------|--------------|
| Model (4-bit) | ~5 |
| Optimizer (8-bit) | ~2 |
| Gradients (FP16) | ~2 |
| Activations | ~2-3 |
| **Total** | **~11-12GB** ✓ |

---

## 7. Training Configuration for 16GB VRAM

### Recommended Settings

```yaml
model:
  load_in_4bit: true
  bnb_4bit_compute_dtype: float16
  bnb_4bit_quant_type: nf4

training:
  per_device_train_batch_size: 1
  gradient_accumulation_steps: 12
  gradient_checkpointing: true
  max_seq_length: 2048

lora:
  r: 64
  lora_alpha: 64
  lora_dropout: 0
```

---

## 8. Key Takeaways

1. **QLoRA enables** 9B fine-tuning on 16GB VRAM
2. **4-bit quantization** is essential - saves ~50% memory
3. **Gradient checkpointing** required for large models
4. **Flash Attention** for context lengths >2048

---

*Last updated: 2026-05-06*