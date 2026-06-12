# Scaling Laws for Neural Language Models

**Authors:** Jared Kaplan, Sam McCandlish, Tom Henighan, Tom B. Brown, Benjamin Chess, Rewon Child, Scott Gray, Alec Radford, Jeffrey Wu, Dario Amodei
**Year:** 2020
**Venue:** arXiv (later at ICML 2020 workshop)
**Link:** https://arxiv.org/abs/2001.08361

## Key Finding

**Test loss scales as a power-law with model size, dataset size, and compute budget.** Doubling parameters → predictable loss reduction. More importantly: there are diminishing returns — performance is bottlenecked by the smallest of (model size, data size, compute).

## Core Laws

$$L(N) \propto N^{-\alpha_N} \quad \text{(loss vs parameters)}$$
$$L(D) \propto D^{-\alpha_D} \quad \text{(loss vs data)}$$
$$L(C) \propto C^{-\alpha_C} \quad \text{(loss vs compute)}$$

Where $\alpha_N \approx 0.076$, $\alpha_D \approx 0.095$, $\alpha_C \approx 0.050$.

## Key Implications

1. **Larger models are inherently more capable** — smaller models have fundamentally higher baseline loss
2. **Optimal allocation** — for a given compute budget, there's an optimal ratio of parameters to training tokens (refined by Chinchilla)
3. **Diminishing returns** — beyond a point, adding more parameters doesn't help without more data
4. **Emergent abilities** — some capabilities only appear above certain scale thresholds

## Relevance to TINYCUA

This paper is **the mathematical foundation** for TINYCUA's core premise:

| Scaling Law Implication | TINYCUA Response |
|-------------------------|------------------|
| Smaller models have higher baseline loss | Compensate by reducing task complexity |
| Less capacity → worse at handling irrelevant context | Remove irrelevant context entirely |
| Emergent reasoning only at large scale | Don't rely on emergent reasoning — provide structured support |
| Data quality matters as much as quantity | Context quality matters as much as context quantity |

The scaling law formalizes why SLMs need **more help** with context: they have fewer parameters to allocate to attention, reasoning, and noise suppression. TINYCUA provides that help structurally rather than parametrically.

## How to Cite

```
@article{kaplan2020scaling,
  title={Scaling Laws for Neural Language Models},
  author={Kaplan, Jared and McCandlish, Sam and Henighan, Tom and Brown, Tom B and Chess, Benjamin and Child, Rewon and Gray, Scott and Radford, Alec and Wu, Jeffrey and Amodei, Dario},
  journal={arXiv preprint arXiv:2001.08361},
  year={2020}
}
```

## Connection in Lit Review

This is the **keystone paper** for the SLM argument. Use it to establish that:
1. Model capacity is bounded by parameters (Kaplan 2020)
2. Therefore SLMs have less "attention budget" to waste on irrelevant tokens
3. TINYCUA's context isolation conserves that limited budget

(Also see Hoffmann et al. 2022 "Chinchilla" for refined scaling laws.)
