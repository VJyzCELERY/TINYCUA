# Transformer Architecture Deep Dive

## Overview

The Transformer is a family of artificial neural network architectures based on multi-head attention mechanisms, designed to efficiently process and generate sequences. Unlike recurrent networks that process tokens sequentially, Transformers can handle entire sequences in parallel through self-attention mechanisms.

---

## Table of Contents

1. [Encoder-Decoder Structure](#encoder-decoder-structure)
2. [Positional Encoding](#positional-encoding)
3. [Feed-Forward Networks (FFN)](#feed-forward-networks-ffn)
4. [Key Components in Detail](#key-components-in-detail)

---

## Encoder-Decoder Structure

### High-Level Architecture

The Transformer model consists of two main components: an **encoder** and a **decoder**, each composed of stacked identical layers.

```
┌─────────────────────────────────────────────────────────────┐
│                    TRANSFORMER ARCHITECTURE                  │
├──────────────────┬──────────────────────────────────────────┤
│      ENCODER     │              DECODER                      │
│  Stack of N layers│  Stack of M layers                       │
│                   │                                          │
│  ┌─────┐         │  ┌─────┐                                  │
│  │Enc1 │         │  │Dec1 │                                  │
│  └──┬──┘         │  └──┬──┘                                  │
│     │            │     │                                      │
│  ┌─────┐         │  ┌─────┐                                  │
│  │Enc2 │         │  │Dec2 │                                  │
│  └──┬──┘         │  └──┬──┘                                  │
│     │            │     │                                      │
│  ┌─────┐         │  ┌─────┐                                  │
│  │EncN │         │  │DecM │                                  │
│  └─────┘         │  └─────┘                                  │
└──────────────────┴──────────────────────────────────────────┘
```

### Encoder Structure

Each encoder layer contains:

1. **Multi-Head Self-Attention Mechanism** - Allows the model to attend to all positions in the input sequence simultaneously
2. **Feed-Forward Neural Network (FFN)** - Processes information independently at each position
3. **Add & Norm Layers** - Residual connections with layer normalization for stable training

```
Encoder Layer:
┌─────────────────────────────────────────────────────────────┐
│  Input Embeddings + Positional Encoding                      │
│          ↓                                                   │
│  Multi-Head Self-Attention                                    │
│    ├─ Query, Key, Value projections                          │
│    ├─ Scaled dot-product attention                            │
│    └─ Concatenate heads + Linear projection                   │
│          ↓ (Residual Connection + Layer Norm)                 │
│  Point-wise Feed-Forward Network                              │
│    ├─ First linear layer: d_model → 4×d_model                │
│    ├─ ReLU activation                                         │
│    └─ Second linear layer: 4×d_model → d_model                │
└─────────────────────────────────────────────────────────────┘
```

### Decoder Structure

Each decoder layer contains:

1. **Masked Multi-Head Self-Attention** - Attends only to previous positions (causal attention)
2. **Cross-Attention Mechanism** - Attends to encoder outputs
3. **Point-wise Feed-Forward Network**
4. Add & Norm layers throughout

```
Decoder Layer:
┌─────────────────────────────────────────────────────────────┐
│  Input Embeddings + Positional Encoding                      │
│          ↓                                                   │
│  Masked Multi-Head Self-Attention (Causal Attention)           │
│    └─ Only attends to positions i ≤ current position          │
│          ↓ (Residual + Norm)                                 │
│  Cross-Attention                                              │
│    ├─ Queries from decoder                                   │
│    ├─ Keys/Values from encoder output                        │
│    └─ Allows decoder to attend to encoder features             │
│          ↓ (Residual + Norm)                                 │
│  Point-wise Feed-Forward Network                              │
└─────────────────────────────────────────────────────────────┘
```

### Input Processing Pipeline

```
Raw Text → Tokenization → Embedding Layer → Positional Encoding
                                                         ↓
                                                    Transformer Encoder/Decoder
                                                         ↓
                                                  Linear Output Layer
                                                         ↓
                                                   Softmax + Vocab
```

---

## Positional Encoding

### Why Positional Encoding is Needed

Transformers use self-attention mechanisms that are **permutation-invariant** - they don't inherently understand the order of tokens. To preserve sequence information, positional encoding must be added to input embeddings:

```python
# Input embedding (learnable) + Positional encoding = Final token representation
final_representation = X_embedding(X) + P(positional_encoding(position))
```

### Sinusoidal Positional Encoding

The original Transformer paper introduced **sinusoidal positional encodings**, a non-learned, deterministic approach:

$$PE(pos, 2i) = \sin(\frac{pos}{10000^{2i/d_{model}}})$$

$$PE(pos, 2i+1) = \cos(\frac{pos}{10000^{2i/d_{model}}})$$

Where:
- `pos` is the position in the sequence (0, 1, 2, ...)
- `i` is the dimension index (0 to d_model/2 - 1)
- `d_model` is the model dimension (typically 512, 768, or 1024)

### Key Properties of Sinusoidal Encoding

1. **Generalization**: The sinusoidal pattern allows encoding positions beyond the training sequence length
2. **Relative Position Information**: Any two relative positions can be represented as a linear transformation of their absolute positional encodings:
   $$PE(pos+k, 2i) = -PE(pos, 2i+1)$$
3. **Different Frequencies**: Different dimensions encode different frequencies, allowing the model to learn various distance relationships

### Alternative Positional Encoding Methods

| Method | Description | Pros | Cons |
|--------|-------------|------|------|
| **Sinusoidal** | Fixed trigonometric functions | Generalizes beyond training length; deterministic | Not learned from data |
| **Learnable Embeddings** | Trainable position embeddings | Learns optimal representations | Limited to sequence length of training |
| **RoPE (Rotary)** | Rotary positional encoding | Relative position encoded naturally | More complex implementation |

### Positional Encoding Visualization

```
Position 0:    [sin(0/10000^0), cos(0/10000^0), sin(0/10000^2), ...]
Position 1:    [sin(1/10000^0), cos(1/10000^0), sin(1/10000^2), ...]
Position 2:    [sin(2/10000^0), cos(2/10000^0), sin(2/10000^2), ...]
...

Note: Even dimensions use sine, odd dimensions use cosine
```

---

## Feed-Forward Networks (FFN)

### Architecture and Function

The feed-forward network in Transformers is a **two-layer fully connected network** that applies non-linear transformations independently at each position. It's also known as the "point-wise" or "fully-connected" layer.

```
┌─────────────────────────────────────────────────────────────┐
│                    FEED-FORWARD NETWORK (FFN)                │
├─────────────────────────────────────────────────────────────┤
│  Input:          X ∈ ℝ^(batch_size, seq_len, d_model)       │
│                                                            │
│  Layer 1:        Linear(d_model → 4×d_model)               │
│                  → ReLU activation                          │
│                                                            │
│  Layer 2:        Linear(4×d_model → d_model)                │
│                                                            │
│  Output:         X' ∈ ℝ^(batch_size, seq_len, d_model)      │
└─────────────────────────────────────────────────────────────┘
```

### Mathematical Formulation

$$FFN(X) = \max(0, XW_1 + b_1)W_2 + b_2$$

Where:
- $X$ is the input at a given position
- $W_1$ projects to an expanded dimension (typically 4×d_model)
- $b_1, b_2$ are biases
- $\max(0, \cdot)$ applies ReLU activation

### Why FFN Matters in Transformers

1. **Most Parameters**: The FFN contains the majority of parameters in a Transformer model
2. **Non-linearity**: Provides necessary non-linear transformations for complex pattern learning
3. **Position-wise Processing**: Unlike attention which operates across positions, FFN processes each position independently
4. **Feature Expansion**: The expanded dimension allows the model to learn richer feature representations

### Alternative Architectures

Recent research has explored alternatives:

- **One Wide FFN**: Uses wider layers with fewer hidden units
- **Gated FFNs**: Incorporates gating mechanisms for better control
- **SwiGLU FFNs**: Uses Swish activation with gated linear units (used in modern models like GPT-J)

---

## Key Components in Detail

### Multi-Head Self-Attention

The attention mechanism that enables Transformers to focus on different parts of the input:

$$	ext{Attention}(Q, K, V) = 	ext{softmax}\left(\frac{QK^T}{\sqrt{d_k}}ight)V$$

Where:
- $Q$ (Queries): What we're looking for
- $K$ (Keys): What's available to attend to
- $V$ (Values): Information retrieved from attention
- $\sqrt{d_k}$ is scaling factor for stable gradients

### Cross-Attention (Decoder Only)

Allows the decoder to attend to encoder outputs:

$$	ext{CrossAttn}(Q_{dec}, K_{enc}, V_{enc}) = 	ext{softmax}\left(\frac{Q_{dec}K_{enc}^T}{\sqrt{d_k}}ight)V_{enc}$$

### Layer Normalization

Applied after each sub-layer to stabilize training:

$$LN(x) = \frac{x - \mu(x)}{\sigma(x)} \cdot \gamma + \beta$$

Where $\mu$ and $\sigma$ are mean and standard deviation, $\gamma$ and $\beta$ are learnable parameters.

### Residual Connections

Additive shortcuts around each sub-layer:

$$	ext{Output} = 	ext{SubLayer}(x) + x$$

---

## Summary Comparison Table

| Component | Purpose | Key Mechanism |
|-----------|---------|---------------|
| **Encoder** | Process input sequence | Self-attention across all positions |
| **Decoder** | Generate output sequence | Causal self-attention + cross-attention to encoder |
| **Positional Encoding** | Preserve order information | Sinusoidal functions (or learned embeddings) |
| **Multi-Head Attention** | Capture different relationships | Parallel attention heads with different subspaces |
| **FFN** | Non-linear feature transformation | Two-layer fully connected network |

---

## References

1. Vaswani, A., et al. "Attention Is All You Need." NeurIPS 2017.
2. D2L (Dive into Deep Learning) - Chapter on Transformers.
3. Codecademy: Transformer Architecture Explained with Self-Attention Mechanism.
4. Medium articles on Feedforward Networks and Positional Encodings.

---

*Document created for comprehensive study of Transformer architecture fundamentals.*
