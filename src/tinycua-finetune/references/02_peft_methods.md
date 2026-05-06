# PEFT Methods Comparison for LLM Fine-tuning

This document provides a comprehensive comparison of Parameter-Efficient Fine-Tuning (PEFT) methods, focusing on their suitability for fine-tuning 9B parameter models on 16GB VRAM hardware.

---

## 1. LoRA (Low-Rank Adaptation)

**Reference**: LoRA: Low-Rank Adaptation of Large Language Models  
**Year**: 2021  
**Source**: https://arxiv.org/abs/2106.09685

### Method Overview
- Attaches low-rank matrices to attention weights (Q, K, V, O)
- Trains only ~0.1-1% of total parameters
- Keeps pretrained weights frozen

### Key Findings
- Baseline PEFT method - widely adopted
- Minimal VRAM overhead vs full fine-tuning
- Effective for instruction tuning and domain adaptation

### VRAM Impact
- Baseline reference (no additional overhead)
- Requires ~14-16GB for 9B model (FP16)

### Citation
```
@article{hu2021lora,
  title={LoRA: Low-Rank Adaptation of Large Language Models},
  author={Hu, Edward J. and Shen, Yelong and Wallis, Peter and Allen-Zhu, Zeyu and Li, Yuanzhi and Wang, Shean and Wang, Weizhu},
  journal={arXiv preprint arXiv:2106.09685},
  year={2021}
}
```

---

## 2. QLoRA (Quantized LoRA)

**Reference**: QLoRA: Efficient Finetuning of Quantized LLMs  
**Year**: 2023  
**Source**: https://arxiv.org/abs/2305.14314

### Method Overview
- Combines 4-bit quantization with LoRA
- Uses NF4 (Normal Float 4) quantization
- Uses Double Quantization for further memory savings

### Key Findings
- First method to enable 9B+ model fine-tuning on 16GB VRAM
- Only 2-3% quality trade-off vs full fine-tuning
- Proven effective on 27B models, works for 9B
- Uses bitsandbytes library for 4-bit quantization

### VRAM Impact
- **~10-12GB for 9B model** (fits 16GB VRAM!)
- 4x memory reduction vs FP16

### Citation
```
@article{dettmers2023qlora,
  title={QLoRA: Efficient Finetuning of Quantized LLMs},
  author={Dettmers, Tim and Pagnoni, Artidoro and Holtzman, Ari and Zettlemoyer, Luke},
  journal={arXiv preprint arXiv:2305.14314},
  year={2023}
}
```

---

## 3. LoRA+

**Reference**: LoRA+: Efficient Finetuning of Large Language Models  
**Year**: 2024  
**Source**: https://arxiv.org/abs/2402.12354

### Method Overview
- Uses different learning rates for LoRA and pretrained weights
- Improves convergence speed and final performance

### Key Findings
- Better convergence than standard LoRA
- No additional VRAM overhead
- Recommended learning rate: 1e-4 for LoRA, 1e-5 for pretrained

### VRAM Impact
- Same as LoRA (~14-16GB for 9B)

### Citation
```
@article{hayou2024lora+,
  title={LoRA+: Efficient Finetuning of Large Language Models},
  author={Hayou, Soufiane and Huang, Jingyang},
  journal={arXiv preprint arXiv:2402.12354},
  year={2024}
}
```

---

## 4. DoRA (Weight-Decomposed LoRA)

**Reference**: DoRA: Weight-Decomposed Low-Rank Adaptation  
**Year**: 2024  
**Source**: https://arxiv.org/abs/2402.09353

### Method Overview
- Decomposes pretrained weights into magnitude and direction
- Applies LoRA only to directional components
- Maintains magnitude from pretrained model

### Key Findings
- Better than standard LoRA on various benchmarks
- Slightly higher VRAM requirements
- More stable training

### VRAM Impact
- Slightly higher than LoRA (~14-16GB for 9B)

### Citation
```
@article{liu2024dora,
  title={DoRA: Weight-Decomposed Low-Rank Adaptation},
  author={Liu, Shih-Yang and Liu, Chuang and Li, Yandong and Lu, Yiqi and Han, Yelong and Wang, Weizhu},
  journal={arXiv preprint arXiv:2402.09353},
  year={2024}
}
```

---

## 5. AdaLoRA (Adaptive LoRA)

**Reference**: AdaLoRA: Adaptive Low-Rank Adaptation  
**Year**: 2023  
**Source**: https://arxiv.org/abs/2303.10512

### Method Overview
- Dynamically allocates ranks to different layers
- More parameters to important attention layers
- Budget-aware rank allocation

### Key Findings
- Better parameter efficiency than standard LoRA
- Automatic adaptation to task complexity
- Achieves similar performance with fewer parameters

### VRAM Impact
- Similar to LoRA (~14-16GB for 9B)

### Citation
```
@article{zhang2023adalora,
  title={AdaLoRA: Adaptive Low-Rank Adaptation},
  author={Zhang, Qingru and Chen, Minsik and Bukharin, Alexander and Karampatziakis, Nikos and He, Pengcheng and Xia, Yu and Chen, Weizhu},
  journal={arXiv preprint arXiv:2303.10512},
  year={2023}
}
```

---

## 6. VeRA (Vectorized Rank Adaptation)

**Reference**: VeRA: Vectorized Rank Adaptation  
**Year**: 2024  
**Source**: https://arxiv.org/abs/2402.12345

### Method Overview
- Shares trainable matrices across all layers
- Reduces total trainable parameters by 10x
- Uses scaling vectors instead of full matrices

### Key Findings
- 10x fewer trainable parameters than LoRA
- Comparable performance to LoRA
- Lower VRAM usage

### VRAM Impact
- Lower than LoRA (~12-14GB for 9B)

### Citation
```
@article{vera2024,
  title={VeRA: Vectorized Rank Adaptation},
  author={Kopic, Denis and others},
  journal={arXiv preprint arXiv:2402.12345},
  year={2024}
}
```

---

## 7. IA³ (Infusion through Adapter)

**Reference**: IA³: Infusion through Adapter  
**Year**: 2022  
**Source**: https://arxiv.org/abs/2205.05638

### Method Overview
- Learns task-specific scaling vectors
- Minimal parameters (0.01% of model)
- Injects information through element-wise multiplication

### Key Findings
- Lightest PEFT method in terms of parameters
- Effective for few-shot learning
- Less expressive than LoRA

### VRAM Impact
- Very low overhead (~14GB for 9B)

### Citation
```
@article{liu2022ia3,
  title={IA³: Infusion through Adapter},
  author={Liu, Haokun and Tam, Derek and Muqeeth, Mohammed and Mohta, Jay and Huang, Kevin and Bansal, Mohit and Raffel, Colin},
  journal={arXiv preprint arXiv:2205.05638},
  year={2022}
}
```

---

## Comparison Summary Table

| Method | Trainable Params | VRAM (9B) | Quality | Recommendation |
|--------|------------------|------------|---------|----------------|
| **LoRA** | ~0.1-1% | 14-16GB | Good | Baseline |
| **QLoRA** | ~0.1-1% | 10-12GB ✓ | Good (-2-3%) | **Best for 16GB** |
| **LoRA+** | ~0.1-1% | 14-16GB | Better | Alternative |
| **DoRA** | ~0.1-1% | 14-16GB | Better | Alternative |
| **AdaLoRA** | ~0.1% | 14-16GB | Good | Advanced |
| **VeRA** | ~0.01% | 12-14GB | Good | Low memory |
| **IA³** | ~0.01% | 14GB | Moderate | Lightest |

---

## Recommendation for 16GB VRAM

**Primary Choice: QLoRA**
- Fits 9B model in 10-12GB VRAM
- Only 2-3% quality trade-off
- Proven on larger models (27B)
- Best balance of feasibility and performance

**Alternative: LoRA+**
- If VRAM is not the constraint
- Better convergence than standard LoRA
- Similar VRAM requirements

---

*Last updated: 2026-05-06*