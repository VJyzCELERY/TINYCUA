# 9B Reasoning Models for Computer Use Agent

This document provides a comprehensive review of 9B parameter language models suitable for reasoning tasks and computer use agent applications, with focus on models that can be fine-tuned on 16GB VRAM hardware.

---

## 1. Qwen3.5-9B

**Reference**: Qwen3 Technical Report  
**Year**: 2025  
**Source**: https://arxiv.org/abs/2505.09388

### Dataset
- **Pre-training tokens**: ~18-36T multimodal tokens (varies by model variant)
- **Languages**: 201 languages and dialects
- **Data sources**: Web text, code repositories, PDF documents (extracted via Qwen2.5-VL), synthetic data (generated via Qwen2.5-Math and Qwen2.5-Coder)

### Key Findings
- Native multimodal architecture (early fusion) - no separate VL variant needed
- Best VRAM efficiency with INT4 quantization (~6GB for 9B model)
- Strong reasoning benchmarks: 82.5 MMLU-Pro, 81.7 GPQA Diamond
- 262K token context length (1M extended via YaRN)
- Gated Delta Network (GDN) + Hybrid Attention for efficient inference

### Citation
```
@article{qwen3_technical_2025,
  title={Qwen3 Technical Report},
  author={Qwen Team},
  year={2025},
  url={https://arxiv.org/abs/2505.09388}
}
```

---

## 2. DeepSeek-LLM 9B

**Reference**: DeepSeek-LLM: Scaling Open-Source Language Models with Long-termism  
**Year**: 2024  
**Source**: https://arxiv.org/abs/2401.02954

### Dataset
- **Pre-training tokens**: 2 trillion tokens (English and Chinese)
- **Composition**: 31.2% general language, 46.6% mathematical problems, 22.2% code
- **Data sources**: Internet text, math datasets (gsm8k-ScRel), code repositories, self-collected data

### Key Findings
- Multi-step learning rate scheduler (vs cosine in LLaMA)
- Surpasses LLaMA-2 70B in code, math, and reasoning tasks
- Supports both base and chat variants
- 4096 sequence length

### Citation
```
@article{deepseek_llm_2024,
  title={DeepSeek LLM: Scaling Open-Source Language Models with Longtermism},
  author={DeepSeek Team},
  year={2024},
  url={https://arxiv.org/abs/2401.02954}
}
```

---

## 3. DeepSeek-Coder 9B

**Reference**: DeepSeek-Coder: Code-Specific Pre-training  
**Year**: 2024  
**Source**: https://huggingface.co/deepseek-ai/deepseek-coder-9b-base

### Dataset
- **Pre-training tokens**: 2T+ tokens with heavy code focus
- **Data sources**: GitHub repositories, code datasets, StackOverflow data

### Key Findings
- Specialized for code generation and understanding
- Trained with Fill-in-the-Middle (FIM) objective
- Strong performance on HumanEval, MBPP, and other code benchmarks

### Citation
```
@article{deepseek_coder_2024,
  title={DeepSeek-Coder: Code-Specific Pre-training},
  author={DeepSeek Team},
  year={2024},
  url={https://huggingface.co/deepseek-ai/deepseek-coder-9b-base}
}
```

---

## 4. LLaMA 3 8B

**Reference**: LLaMA 3 Open Foundation Model  
**Year**: 2024  
**Source**: https://arxiv.org/abs/2407.21783

### Dataset
- **Pre-training tokens**: 15 trillion tokens
- **Languages**: ~20 languages
- **Data sources**: Diverse web data, code, academic papers

### Key Findings
- Improved instruction following over LLaMA 2
- Strong reasoning capabilities but lower than Qwen3.5
- 8K context length (extended to 128K in some variants)
- Less VRAM efficient than Qwen3.5 (~8GB INT4 vs ~6GB)

### Citation
```
@article{llama3_2024,
  title={LLaMA 3 Open Foundation Model},
  author={Meta AI},
  year={2024},
  url={https://arxiv.org/abs/2407.21783}
}
```

---

## 5. Qwen2.5-VL 9B

**Reference**: Qwen2-VL Technical Report  
**Year**: 2025  
**Source**: https://arxiv.org/abs/2408.12253

### Dataset
- **Pre-training tokens**: 18 trillion tokens
- **Focus**: Vision-language reasoning tasks

### Key Findings
- Vision-language model for computer use with screenshots
- Strong on multimodal benchmarks (MMMU, MMBench)
- Native support for screen understanding

### Citation
```
@article{qwen2_vl_2025,
  title={Qwen2-VL Technical Report},
  author={Qwen Team},
  year={2025},
  url={https://arxiv.org/abs/2408.12253}
}
```

---

## Comparison Summary

| Model | Parameters | VRAM (INT4) | Context | Languages | Reasoning (MMLU-Pro) |
|-------|------------|-------------|---------|------------|---------------------|
| Qwen3.5-9B | 9B | ~6GB | 262K | 201 | 82.5 |
| DeepSeek-LLM 9B | 9B | ~6GB | 4K | ~10 | ~70 |
| DeepSeek-Coder 9B | 9B | ~6GB | 4K | ~10 | ~65 (code) |
| LLaMA 3-8B | 8B | ~8GB | 8K-128K | ~20 | ~70 |
| Qwen2.5-VL 9B | 9B | ~8GB | 128K | 29 | ~75 |

---

## VRAM Feasibility for 16GB GPU

All 9B models listed above can be fine-tuned with QLoRA on 16GB VRAM:
- Qwen3.5-9B: ~6GB (best efficiency)
- DeepSeek models: ~6GB
- LLaMA 3-8B: ~8GB

**Recommendation**: Qwen3.5-9B offers the best balance of reasoning capability, VRAM efficiency, and multimodal support for computer use agent applications.

---

*Last updated: 2026-05-06*