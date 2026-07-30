# Neural Networks and Transformers Study Guide

[TOC](#table-of-contents)

## [Table of Contents](#table-of-contents)

- [Introduction](#introduction)
- [Fundamentals](#fundamentals)
  - [Backpropagation](#backpropagation)
  - [Gradient Descent](#gradient-descent)
- [Transformer Architecture](#transformer-architecture)
  - [Self-Attention Mechanism](#self-attention-mechanism)
  - [Positional Encoding](#positional-encoding)
  - [Encoders and Decoders](#encoders-and-decoders)
- [Code Example](#code-example)
- [Study Plan](#study-plan)

---

## Introduction

Neural networks and transformers are foundational architectures in modern artificial intelligence. Neural networks consist of interconnected nodes (neurons) organized in layers that learn to map inputs to outputs through training. Transformers, introduced in the paper "Attention Is All You Need" (2017), revolutionized sequence modeling by using self-attention mechanisms to process sequences in parallel without recurrence.

This guide covers the essential concepts you need to understand these powerful architectures.

---

## Fundamentals

### Backpropagation

Backpropagation is the algorithm used to train neural networks by computing gradients of the loss function with respect to each parameter. It uses the chain rule of calculus to efficiently compute how changes in weights affect the output.

**How it works:**
1. **Forward pass**: Input data flows through the network, producing an output
2. **Loss computation**: Compare the output with the true label using a loss function
3. **Backward pass**: Compute gradients by propagating errors backward from output to input layers
4. **Parameter update**: Adjust weights and biases in the direction that reduces loss

The chain rule allows efficient computation: if we have layers $L_1 \rightarrow L_2 \rightarrow \dots \rightarrow L_n$, then:

$$\frac{\partial L}{\partial w_{ij}} = \frac{\partial L}{\partial o} \cdot \frac{\partial o}{\partial z} \cdot \frac{\partial z}{\partial w}$$

where $L$ is loss, $o$ is output, $z$ is pre-activation, and $w$ is weight.

### Gradient Descent

Gradient descent is the optimization algorithm that updates model parameters to minimize the loss function. It iteratively adjusts parameters in the direction of steepest descent (negative gradient).

**Basic update rule:**
$$\theta_{t+1} = \theta_t - \eta \cdot \nabla_\theta L(\theta)$$

where:
- $\theta$ represents model parameters (weights and biases)
- $\eta$ is the learning rate
- $\nabla_\theta L$ is the gradient of the loss with respect to parameters

**Types of gradient descent:**

| Type | Description | Update Frequency |
|------|-------------|------------------|
| Batch GD | Uses entire training set | Once per epoch |
| Stochastic GD (SGD) | Uses one random sample per update | Every iteration |
| Mini-batch GD | Uses small batch of samples | Every mini-batch |

**Key hyperparameters:**
- **Learning rate ($\eta$)**: Controls step size; too large causes divergence, too small slows convergence
- **Momentum**: Adds velocity term to smooth updates and escape local minima
- **Weight decay (L2 regularization)**: Penalizes large weights to prevent overfitting

**Common loss functions:**
- Mean Squared Error (MSE): $L = \frac{1}{N}\sum_{i=1}^N (y_i - \hat{y}_i)^2$ for regression
- Cross-Entropy: $L = -\sum_{i=1}^C y_i \log(\hat{y}_i)$ for classification

---

## Transformer Architecture

### Self-Attention Mechanism

Self-attention allows each token in a sequence to attend to all tokens in the input, enabling the model to capture long-range dependencies efficiently. Unlike RNNs that process sequentially, attention computes relationships in parallel.

**Multi-Head Attention Formula:**

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

where:
- $Q$ (queries), $K$ (keys), and $V$ (values) are linear projections of the input
- $d_k$ is the dimension of key vectors; $\sqrt{d_k}$ scales dot products to prevent vanishing gradients
- The softmax ensures outputs sum to 1, creating a probability distribution

**Multi-head attention** concatenates $h$ attention heads and projects back:

$$\text{MultiHead}(Q,K,V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h)W^O$$

where $\text{head}_i = \text{Attention}(QW_i^Q, KW_i^K, VW_i^V)$

**Scaled Dot-Product Attention** (used in original Transformer):
1. Compute dot products: $QK^T$
2. Scale by $\sqrt{d_k}$ to stabilize gradients
3. Apply softmax to get attention weights
4. Weight sum of values

**Self-attention variants:**
- **Standard**: All positions attend to all positions (quadratic complexity)
- **Sparse attention**: Restricts attention to local windows for efficiency
- **Linear attention**: Uses kernel trick to achieve linear complexity

### Positional Encoding

Transformers lack recurrence and convolution, so they need explicit position information. Positional encodings are added to input embeddings to preserve sequence order.

**Sine/Cosine Positional Encoding:**

$$PE_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$
$$PE_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$

where:
- $pos$ is the position in the sequence (0-indexed)
- $i$ is the dimension index ($0 \le i < d_{model}/2$)
- $d_{model}$ is the model dimension (e.g., 512, 768, 1024)

**Key properties:**
- Even dimensions use sine, odd dimensions use cosine
- Different frequencies allow encoding relative positions
- High-frequency components encode short distances; low frequencies encode long distances
- Unique for each position, enabling models to learn absolute and relative positions

**Alternative positional encdings:**
- **Learned embeddings**: Trainable position vectors (used in BERT)
- **ALiBi**: Attention biases instead of adding to embeddings
- **RoPE (Rotary Positional Embeddings)**: Rotates query/key based on position

### Encoders and Decoders

The Transformer architecture consists of encoder and decoder stacks, each containing multiple identical layers.

**Encoder Stack:**
- Contains $N$ identical encoder layers (typically 6 in original paper)
- Each encoder layer has two sub-layers:
  1. **Multi-head self-attention**: Processes the input sequence
  2. **Position-wise feed-forward network**: Applies FFN independently to each position
- Each sub-layer is preceded by a residual connection and layer normalization

**Encoder architecture:**
```
Input Embeddings + Positional Encoding
    ↓
[ Encoder Layer 1 ]
    ↓
[ Encoder Layer 2 ]
    ↓
...
    ↓
[ Encoder Layer N ]
    ↓
Multi-Head Self-Attention → FFN → LayerNorm → Residual Connection
```

**Decoder Stack:**
- Contains $N$ identical decoder layers
- Each decoder layer has three sub-layers:
  1. **Masked multi-head self-attention**: Prevents attending to future positions (causal mask)
  2. **Multi-head attention over encoder output**: Allows decoder to attend to encoder states
  3. **Position-wise feed-forward network**
- Decoder layers also use residual connections and layer normalization

**Decoder architecture:**
```
Input Embeddings + Positional Encoding + Target Embedding
    ↓
[ Decoder Layer 1 ]
    ↓
Masked Self-Attention (causal mask)
    ↓
Encoder-Decoder Attention
    ↓
FFN → LayerNorm → Residual Connection
    ↓
[ Decoder Layer 2 ]
    ↓
...
    ↓
[ Decoder Layer N ]
    ↓
Output Projection + Softmax → Next Token Prediction
```

**Key differences:**
- Encoder processes entire input sequence (bidirectional)
- Decoder uses causal masking to prevent future position leakage
- Encoder-decoder attention allows decoder to focus on relevant encoder positions

---

## Code Example

Here's a PyTorch implementation of the core Transformer components:

```python
import torch
import torch.nn as nn
import math

class PositionalEncoding(nn.Module):
    """Sine/Cosine positional encoding."""
    
    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        self.d_model = d_model
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * 
                              (-math.log(10000.0) / (d_model // 2)))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        
    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class ScaledDotProductAttention(nn.Module):
    """Scaled dot-product attention."""
    
    def __init__(self):
        super().__init__()
        self.dropout = nn.Dropout(p=0.1)
        
    def forward(self, q, k, v, mask=None):
        d_k = q.size(1)  # Dimension of key vectors
        
        # Compute scaled dot-product attention
        scores = torch.matmul(q, k.transpose(-1, -2)) / math.sqrt(d_k)
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
            
        attn_weights = torch.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        return torch.matmul(attn_weights, v), attn_weights


class MultiHeadAttention(nn.Module):
    """Multi-head attention layer."""
    
    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        assert d_model % num_heads == 0
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)
        self.w_v = nn.Linear(d_model, d_model)
        self.o = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(p=dropout)
        
        # Split linear layers into heads
        self.w_q = nn.utils.split_orthogonal(self.w_q, [self.d_k] * self.num_heads)
        self.w_k = nn.utils.split_orthogonal(self.w_k, [self.d_k] * self.num_heads)
        self.w_v = nn.utils.split_orthogonal(self.w_v, [self.d_k] * self.num_heads)
        self.o = nn.utils.split_orthogonal(self.o, [self.d_k] * self.num_heads)
        
    def forward(self, q, k, v, mask=None):
        batch_size = q.size(0)
        
        # Split into heads
        q_heads = []
        k_heads = []
        v_heads = []
        o_heads = []
        
        for i in range(self.num_heads):
            q_heads.append(q.view(batch_size, -1, self.d_k))
            k_heads.append(k.view(batch_size, -1, self.d_k))
            v_heads.append(v.view(batch_size, -1, self.d_k))
            
        # Apply linear projections for each head
        q = torch.cat([self.w_q[i](q) for i in range(self.num_heads)], dim=-1)
        k = torch.cat([self.w_k[i](k) for i in range(self.num_heads)], dim=-1)
        v = torch.cat([self.w_v[i](v) for i in range(self.num_heads)], dim=-1)
        
        # Compute attention
        d_k = self.d_k
        scores = torch.matmul(q, k.transpose(-1, -2)) / math.sqrt(d_k)
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
            
        attn_weights = torch.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        output = torch.matmul(attn_weights, v)
        
        # Output projection
        output = self.o(output)
        
        return output


class EncoderLayer(nn.Module):
    """Transformer encoder layer."""
    
    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        
        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.feed_forward = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 4, d_model),
            nn.Dropout(dropout)
        )
        
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        
    def forward(self, x):
        # Self-attention with residual connection
        attn_output, _ = self.self_attn(x, x, x)
        x = x + attn_output
        x = self.norm1(x)
        
        # Feed-forward with residual connection
        ff_output = self.feed_forward(x)
        x = x + ff_output
        x = self.norm2(x)
        
        return x


class DecoderLayer(nn.Module):
    """Transformer decoder layer."""
    
    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        
        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.cross_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.feed_forward = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 4, d_model),
            nn.Dropout(dropout)
        )
        
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm3 = nn.LayerNorm(d_model)
        
    def forward(self, x, memory, mask=None):
        # Masked self-attention
        attn_output, _ = self.self_attn(x, x, x, mask=mask)
        x = x + attn_output
        x = self.norm1(x)
        
        # Cross-attention to encoder output
        attn_output, _ = self.cross_attn(x, memory, memory)
        x = x + attn_output
        x = self.norm2(x)
        
        # Feed-forward with residual connection
        ff_output = self.feed_forward(x)
        x = x + ff_output
        x = self.norm3(x)
        
        return x
```

---

## Study Plan

### Week 1-2: Foundations
**Goal**: Understand basic neural network concepts and optimization

| Day | Topic | Exercise |
|-----|-------|----------|
| 1-2 | Neural network basics (perceptron, layers) | Build a simple MNIST classifier from scratch |
| 3-4 | Backpropagation derivation | Implement backprop for a 2-layer network manually |
| 5-6 | Gradient descent variants | Compare batch GD vs SGD on a regression task |
| 7 | Review & quiz | Solve 10 practice problems on gradients |

**Resources**:
- "Neural Networks and Deep Learning" (Michael Nielsen) - Chapter 4
- PyTorch tutorials on backpropagation
- Khan Academy: Calculus review (chain rule, partial derivatives)

### Week 3-4: Transformers Part 1
**Goal**: Understand attention mechanisms and positional encoding

| Day | Topic | Exercise |
|-----|-------|----------|
| 8-9 | Self-attention derivation | Implement scaled dot-product attention from scratch |
| 10-11 | Multi-head attention | Implement multi-head attention with PyTorch |
| 12-13 | Positional encoding | Compute and visualize PE for different frequencies |
| 14 | Review & quiz | Implement transformer encoder layer from scratch |

**Resources**:
- "Attention Is All You Need" paper (Vaswani et al., 2017)
- Linus Unold's Transformer tutorial
- BERT source code on GitHub

### Week 5-6: Transformers Part 2
**Goal**: Understand encoder-decoder architecture and implementation

| Day | Topic | Exercise |
|-----|-------|----------|
| 15-16 | Encoder architecture | Build encoder stack with multiple layers |
| 17-18 | Decoder architecture | Implement decoder with masking and cross-attention |
| 19-20 | Full transformer model | Build complete encoder-decoder model |
| 21 | Review & quiz | Train a small transformer on translation task |

**Resources**:
- Hugging Face Transformers library documentation
- "Deep Learning" (Goodfellow) - Chapter 8
- Code implementations from papers

### Week 7-8: Advanced Topics & Projects
**Goal**: Deep dive and practical application

| Day | Topic | Exercise |
|-----|-------|----------|
| 22-23 | Variants (BERT, GPT, T5) | Compare encoder-only vs decoder-only architectures |
| 24-25 | Optimization tricks | Implement gradient accumulation, mixed precision training |
| 26-27 | Project planning | Choose a project and outline approach |
| 28-30 | Project execution | Complete your chosen project |

**Project ideas**:
- Build a sentiment classifier using BERT
- Implement a simple machine translation model
- Build a question-answering system with attention visualization
- Fine-tune a pre-trained model on custom data

### Final Review (Week 9)
**Goal**: Consolidate knowledge and prepare for application

| Day | Activity |
|-----|----------|
| 31-32 | Review all notes and code implementations |
| 33-34 | Solve additional problems from course materials |
| 35-36 | Build a portfolio piece combining concepts |
| 37-38 | Final review and knowledge consolidation |

### Practice Problems (Ongoing)
1. **Derive backpropagation** for a simple network with ReLU activations
2. **Implement attention visualization** to see what tokens attend to each other
3. **Compare different loss functions** on the same dataset
4. **Experiment with learning rate schedules** (cosine annealing, warmup)
5. **Implement position-wise feed-forward** with different activation functions

---

## Additional Resources

### Books
- "Deep Learning" by Goodfellow, Bengio, Courville
- "Deep Learning with Python" by François Chollet
- "Neural Networks and Deep Learning" (Michael Nielsen)

### Papers
- "Attention Is All You Need" (Vaswani et al., 2017)
- "BERT: Pre-training of Deep Bidirectional Transformers" (Devlin et al., 2019)
- "GPT-3: Language Models are Few-Shot Learners" (Brown et al., 2020)

### Code Repositories
- Hugging Face Transformers: https://github.com/huggingface/transformers
- PyTorch tutorials: https://pytorch.org/tutorials/
- TensorFlow tutorials: https://www.tensorflow.org/tutorials

### Online Courses
- Coursera: Deep Learning Specialization (Andrew Ng)
- Fast.ai Practical Deep Learning
- Stanford CS224n (Natural Language Processing with Deep Learning)

---

*Study Guide Version 1.0 | Last updated: 2026*

[Back to TOC](#table-of-contents)
