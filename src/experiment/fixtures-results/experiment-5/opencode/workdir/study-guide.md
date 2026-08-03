# Neural Networks & Transformers Study Guide

A comprehensive learning resource covering fundamentals of neural networks and transformer architecture.

---

## Table of Contents

- [1. Introduction](#1-introduction)
- [2. Fundamental Concepts](#2-fundamental-concepts)
  - [2.1 Perceptrons and Activation Functions](#21-perceptrons-and-activation-functions)
  - [2.2 Neural Network Architecture](#22-neural-network-architecture)
- [3. Training Neural Networks](#3-training-neural-networks)
  - [3.1 Loss Functions](#31-loss-functions)
  - [3.2 Gradient Descent](#32-gradient-descent)
  - [3.3 Backpropagation](#33-backpropagation)
- [4. Transformers Architecture](#4-transformers-architecture)
  - [4.1 Self-Attention Mechanism](#41-self-attention-mechanism)
  - [4.2 Positional Encoding](#42-positional-encoding)
  - [4.3 Encoder Architecture](#43-encoder-architecture)
  - [4.4 Decoder Architecture](#44-decoder-architecture)
- [5. Practical Study Plan](#6-practical-study-plan)

---

## 1. Introduction

Neural networks and transformers represent two pillars of modern artificial intelligence. Neural networks provide the foundation for deep learning, while transformers revolutionized how we process sequential data like text and speech.

This guide covers:
- **Neural Networks**: From basic perceptrons to deep architectures
- **Training Mechanisms**: How neural networks learn through gradient descent and backpropagation
- **Transformers**: The architecture behind modern LLMs, covering self-attention, positional encoding, encoder-decoder design

---

## 2. Fundamental Concepts

### 2.1 Perceptrons and Activation Functions

A perceptron is the simplest neural network unit:

```
output = activation(sum(weight₁ × input₁ + weight₂ × input₂ + ... + bias))
```

**Common Activation Functions:**

| Function | Formula | Use Case |
|----------|---------|----------|
| Sigmoid | σ(x) = 1/(1+e⁻ˣ) | Binary classification, output layer |
| ReLU | f(x) = max(0, x) | Hidden layers (most common) |
| Tanh | tanh(x) = (eˣ - e⁻ˣ)/(eˣ + e⁻ˣ) | Normalized outputs [-1, 1] |
| Softmax | exp(xᵢ)/Σexp(xⱼ) | Multi-class classification output |

**Why activation functions matter:** Without non-linear activations like ReLU or sigmoid, a neural network would just be a linear model—no matter the number of layers. Activation functions introduce non-linearity, enabling networks to learn complex patterns.

### 2.2 Neural Network Architecture

A typical feedforward neural network consists of:

```
Input Layer → Hidden Layer(s) → Output Layer
```

**Key Components:**

- **Weights (W)**: Parameters that determine the strength of connections between neurons
- **Biases (b)**: Allow each neuron to have an activation threshold independent of input
- **Layers**: Groups of neurons that transform data at different abstraction levels

**Forward Propagation Example:**

For a single hidden layer with one neuron:

```python
# Forward pass for one training example
z = W · x + b                    # Linear transformation (W: weights, x: input, b: bias)
a = activation(z)                # Apply non-linear activation function
y_pred = final_activation(y)     # e.g., softmax for multi-class output
```

**Multi-Layer Networks:** Each layer transforms the output of the previous layer. Deep networks have many such layers stacked together.

---

## 3. Training Neural Networks

### 3.1 Loss Functions

Loss functions measure how far predictions are from actual values:

| Task | Loss Function | Formula |
|------|--------------|---------|
| Regression | Mean Squared Error (MSE) | L = (1/n) Σ(yᵢ - ŷᵢ)² |
| Binary Classification | Binary Cross-Entropy | L = -[y·log(ŷ) + (1-y)·log(1-ŷ)] |
| Multi-class | Categorical Cross-Entropy | L = -Σ yᵢ·log(ŷᵢ) |

**Why minimize loss?** Training is the process of adjusting weights to minimize loss. Lower loss means better predictions.

### 3.2 Gradient Descent

Gradient descent is an optimization algorithm that finds optimal weights by iteratively moving in the direction that reduces loss most rapidly.

**The Update Rule:**

```
W_new = W_old - learning_rate × gradient_of_loss(W)
b_new = b_old - learning_rate × gradient_of_loss(b)
```

**Key Concepts:**

- **Learning Rate (η)**: Step size for weight updates. Too large → overshoot minimum; too small → slow convergence
- **Gradient**: Derivative of loss with respect to weights, indicating direction and magnitude of steepest ascent
- **Local Minimum vs Global Minimum**: Gradient descent finds a local minimum; techniques like momentum help escape poor local minima

**Variants:**

| Type | Description | Pros/Cons |
|------|-------------|-----------|
| Batch GD | Uses entire training set per update | Stable but slow, memory intensive |
| Stochastic GD (SGD) | Updates after each sample | Fast but noisy convergence |
| Mini-batch SGD | Updates on small batches (32-512 samples) | Best trade-off between speed and stability |

**Gradient Descent in Action:**

```python
# Pseudocode for training with mini-batch gradient descent
for epoch in range(num_epochs):
    # Shuffle data each epoch
    for batch_X, batch_y in batches(training_data):
        # Forward pass: compute predictions
        predictions = model.forward(batch_X)
        
        # Compute loss
        loss = compute_loss(predictions, batch_y)
        
        # Backward pass: compute gradients
        gradients = compute_gradients(predictions, batch_y)
        
        # Update weights using gradient descent
        for param, grad in zip(model.parameters(), gradients):
            param -= learning_rate * grad
        
        # Optionally: apply optimizer with momentum/Adam
```

### 3.3 Backpropagation

Backpropagation is the algorithm that efficiently computes gradients needed for gradient descent. It applies the chain rule of calculus to compute how changes in weights affect loss.

**The Chain Rule:**

For a simple network with layers L₁ → L₂ → ... → Lₙ:

```
∂Loss/∂Wᵢ = ∂Loss/∂aₙ × ∂aₙ/∂zₙ × ∂zₙ/∂aₙ₋₁ × ∂aₙ₋₁/∂zₙ₋₁ × ... × ∂z₂/∂Wᵢ
```

**The Backpropagation Algorithm:**

1. **Forward Pass**: Compute predictions and loss
2. **Backward Pass (starting from output layer)**:
   - Compute error at output: δ_out = ∂Loss/∂z_out
   - Propagate errors backward through layers
   - For each hidden layer l: δ_l = ((W_{l+1} · δ_{l+1}) ⊙ σ'(z_l))

**Example Derivation for a Simple Network:**

```python
# Consider network: Input → Hidden (ReLU) → Output (Sigmoid)

# Forward pass
z_h = W₁·x + b₁           # Hidden layer pre-activation
a_h = ReLU(z_h)           # Hidden activation
z_o = W₂·a_h + b₂         # Output pre-activation  
a_o = sigmoid(z_o)        # Final prediction

# Backward pass (computing gradients)
# Step 1: Output layer error
error_o = a_o - y                   # Simple loss derivative for MSE
dz_o = error_o * sigmoid'(z_o)      # Chain rule applied
dW2 = dz_o · a_hᵀ / n                # Gradient w.r.t. weights
db2 = dz_o.sum() / n                 # Gradient w.r.t. biases

# Step 2: Hidden layer (propagating error backward)
dz_h = W₂ᵀ · dz_o                   # Error propagated to hidden layer
h_masked = (z_h > 0).astype(float)  # ReLU derivative (1 if z>0, else 0)
dz_h = h_masked * dz_h             # Apply ReLU derivative

# Hidden layer gradients
dW1 = dz_h · xᵀ / n
db1 = dz_h.sum() / n
```

**Key Insight:** Backpropagation efficiently reuses intermediate computations from the forward pass, making it computationally efficient (O(n) instead of O(n²)).

---

## 4. Transformers Architecture

Transformers revolutionized NLP by replacing recurrent architectures with self-attention mechanisms that process sequences in parallel.

### 4.1 Self-Attention Mechanism

Self-attention allows each token to attend to all other tokens, creating rich contextual representations.

**Scaled Dot-Product Attention:**

```
Attention(Q, K, V) = softmax( (QKᵀ)/√dₖ ) · V
```

Where:
- **Q (Queries)**: What we're looking for
- **K (Keys)**: What's available in the sequence  
- **V (Values)**: Information to retrieve
- **dₖ**: Dimension of key vectors (scaling factor prevents softmax saturation)

**Multi-Head Attention:**

Instead of computing one attention matrix, multi-head attention computes multiple attention heads with different learned linear projections:

```python
class MultiHeadAttention(nn.Module):
    def __init__(self, embed_dim, num_heads):
        self.num_heads = num_heads
        self.embed_dim = embed_dim
        
        # Linear projections for each head
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        
        # Output projection
        self.out_proj = nn.Linear(embed_dim, embed_dim)
    
    def forward(self, x):
        B, T, C = x.size()  # Batch size, sequence length, embedding dim
        
        # Project inputs into Q, K, V spaces
        q = self.q_proj(x).view(B, T, self.num_heads, -1).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_heads, -1).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_heads, -1).transpose(1, 2)
        
        # Compute attention scores and apply softmax
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.embed_dim / self.num_heads)
        attn_weights = F.softmax(attn_weights, dim=-1)
        
        # Apply attention to values
        out = torch.matmul(attn_weights, v)
        
        # Concatenate heads and project back
        out = out.transpose(1, 2).contiguous().view(B, T, self.embed_dim)
        return self.out_proj(out)
```

**Key Properties:**
- **Parallel Processing**: All positions attend simultaneously (unlike RNNs which process sequentially)
- **Content-Based Routing**: Tokens "attend" to relevant parts of the input based on learned attention patterns
- **Position Independent**: Base attention mechanism doesn't know token order (addressed by positional encoding)

### 4.2 Positional Encoding

Since transformers lack recurrence or convolution, they need explicit position information—provided by positional encodings.

**Sinusoidal Positional Encodings (Original Transformer):**

```python
def get_sinusoidal_encoding(max_len=5000):
    """Generate sinusoidal positional embeddings"""
    pe = torch.zeros(max_len, d_model)
    
    # Even positions: sin function
    # Odd positions: cos function
    position = torch.arange(0, max_len).unsqueeze(1)
    div_term = torch.exp(torch.arange(0, d_model, 2).float() * 
                        (-math.log(10000.0) / d_model))
    
    pe[:, 0::2] = torch.sin(position.float() * div_term)
    pe[:, 1::2] = torch.cos(position.float() * div_term)
    
    return pe.unsqueeze(0)  # Shape: (1, max_len, d_model)
```

**Positional Encoding Properties:**
- **Learnable vs Fixed**: Original used fixed sinusoidal; BERT uses learned embeddings
- **Relative Positionality**: sin(x) and cos(x) differ by constant offsets, enabling relative position understanding
- **Extrapolation**: Sinusoidal encodings generalize to sequence lengths beyond training

**Modern Alternatives:**
| Type | Description | Use Case |
|------|-------------|----------|
| Sinusoidal (original) | Fixed sin/cos functions | GPT-style models |
| Learned embeddings | Trainable positional matrix | BERT-style models |
| RoPE (Rotary) | Rotation-based relative positions | Modern LLMs (Llama, Mistral) |

### 4.3 Encoder Architecture

Encoders process the entire input sequence to create contextual representations for all tokens.

**Encoder Stack:**

```
Input Embeddings + Positional Encoding
        ↓
    [Self-Attention]
          ↓
       [Layer Norm]
          ↓
      [Feed Forward Network]
          ↓
       [Layer Norm]
          ↓
         ... (repeat N times)
```

**Encoder Block Components:**

1. **Multi-Head Self-Attention**: All tokens attend to all other tokens equally
2. **Add & Normalize**: Residual connection + Layer Normalization
3. **Feed Forward Network**: Two linear layers with ReLU in between

**Complete Encoder Implementation:**

```python
class TransformerEncoder(nn.Module):
    def __init__(self, embed_dim, num_heads, num_layers, 
                 feedforward_dim, dropout=0.1):
        super().__init__()
        
        self.layers = nn.ModuleList([
            # Each layer: Multi-Head Attention + FFN
            EncoderLayer(embed_dim, num_heads, feedforward_dim, dropout)
            for _ in range(num_layers)
        ])
    
    def forward(self, x):
        """Process input sequence through all encoder layers"""
        for layer in self.layers:
            x = layer(x)
        return x  # Shape: (B, T, embed_dim)


class EncoderLayer(nn.Module):
    def __init__(self, embed_dim, num_heads, feedforward_dim, dropout=0.1):
        super().__init__()
        
        self.self_attn = MultiHeadAttention(embed_dim, num_heads)
        self.feed_forward = FeedForwardNetwork(embed_dim, feedforward_dim)
        
        # Layer normalization and residual connections
        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        """Encoder layer with residual connections"""
        # Self-attention branch
        attn_out = self.self_attn(x, x, x)  # Q=K=V=x for encoder
        x = x + self.dropout(attn_out)      # Residual connection
        
        # Feed-forward branch  
        ffn_out = self.feed_forward(self.norm1(x))
        x = x + self.dropout(ffn_out)       # Second residual connection
        
        return self.norm2(x)                 # Final layer normalization
```

**Key Features:**
- **Residual Connections**: Skip connections prevent vanishing gradients in deep networks
- **Layer Normalization**: Stabilizes training by normalizing activations across features
- **Symmetric Design**: All tokens processed identically (no special output token)

### 4.4 Decoder Architecture

Decoders generate autoregressive outputs, attending to both encoder states and previous decoder positions (with masking).

**Decoder Stack:**

```
Input Embeddings + Positional Encoding
        ↓
    [Masked Self-Attention] ← Masks future positions
          ↓
       [Layer Norm]
          ↓
      [Encoder-Decoder Attention] ← Attends to encoder outputs
          ↓
       [Layer Norm]
          ↓
      [Feed Forward Network]
          ↓
       [Layer Norm]
          ↓
         ... (repeat N times)
```

**Complete Decoder Implementation:**

```python
class TransformerDecoder(nn.Module):
    def __init__(self, embed_dim, num_heads, num_layers, 
                 feedforward_dim, dropout=0.1, vocab_size=None):
        super().__init__()
        
        self.embedding = nn.Embedding(vocab_size, embed_dim)  # Input embeddings
        
        self.layers = nn.ModuleList([
            DecoderLayer(embed_dim, num_heads, feedforward_dim, 
                        dropout=dropout)
            for _ in range(num_layers)
        ])
    
    def forward(self, x):
        """Autoregressive generation with causal masking"""
        # Add positional encoding to input embeddings
        x = self.embedding(x) + POSITIONAL_ENCODINGS
        
        # Process through decoder layers
        for layer in self.layers:
            x = layer(x)
        
        return x  # Final logits (or pass through final linear layer)


class DecoderLayer(nn.Module):
    def __init__(self, embed_dim, num_heads, feedforward_dim, dropout=0.1):
        super().__init__()
        
        self.masked_self_attn = MaskedMultiHeadAttention(embed_dim, num_heads)
        self.cross_attn = CrossAttention(embed_dim, num_heads)  # Encoder-decoder attn
        self.feed_forward = FeedForwardNetwork(embed_dim, feedforward_dim)
        
        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)
        self.norm3 = nn.LayerNorm(embed_dim)
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x):
        """Decoder layer with masking and cross-attention"""
        # 1. Masked self-attention (causal mask prevents seeing future positions)
        attn_out = self.masked_self_attn(x, x, x)
        x = x + self.dropout(attn_out)
        
        # 2. Cross-attention to encoder outputs
        cross_out = self.cross_attn(self.norm1(x), encoder_output)
        x = x + self.dropout(cross_out)
        
        # 3. Feed-forward network
        ffn_out = self.feed_forward(self.norm2(x))
        x = x + self.dropout(ffn_out)
        
        return self.norm3(x)  # Final layer normalization


class MaskedMultiHeadAttention(MultiHeadAttention):
    """Self-attention with causal (triangular) masking"""
    
    def forward(self, q, k, v, mask=None):
        B, T_q, C = q.size()
        
        # Project inputs
        q = self.q_proj(q).view(B, T_q, self.num_heads, -1).transpose(1, 2)
        k = self.k_proj(k).view(B, T_k, self.num_heads, -1).transpose(1, 2)
        v = self.v_proj(v).view(B, T_v, self.num_heads, -1).transpose(1, 2)
        
        # Compute attention scores
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(C / self.num_heads)
        
        # Apply causal mask if not provided
        if mask is None:
            # Create triangular mask: future positions masked with -inf
            mask = torch.triu(torch.ones(T_q, T_q, device=q.device), diagonal=1).to(q.device) * float('-inf')
        
        attn_weights = F.softmax(attn_scores + mask, dim=-1)
        
        out = torch.matmul(attn_weights, v)
        return out.transpose(1, 2).contiguous().view(B, T_q, C)


class CrossAttention(nn.Module):
    """Cross-attention: decoder queries encoder outputs"""
    
    def __init__(self, embed_dim, num_heads):
        super().__init__()
        
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)  # From encoder output
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        
        self.out_proj = nn.Linear(embed_dim, embed_dim)
    
    def forward(self, decoder_states, encoder_output):
        """Cross-attention: decoder attends to all encoder positions"""
        B, T_dec, C = decoder_states.size()
        
        # Decoder queries
        q = self.q_proj(decoder_states).view(B, T_dec, 1, -1)
        
        # Encoder provides keys and values (all positions available)
        k = self.k_proj(encoder_output).unsqueeze(1)
        v = self.v_proj(encoder_output).unsqueeze(1)
        
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(C)
        attn_weights = F.softmax(attn_scores, dim=-1)
        
        out = torch.matmul(attn_weights, v)
        return self.out_proj(out.squeeze(1))  # Remove batch dimension


# Simplified Feed Forward Network (same for encoder and decoder)
class FeedForwardNetwork(nn.Module):
    def __init__(self, embed_dim, feedforward_dim):
        super().__init__()
        
        self.fc1 = nn.Linear(embed_dim, feedforward_dim)
        self.fc2 = nn.Linear(feedforward_dim, embed_dim)
    
    def forward(self, x):
        return self.fc2(F.relu(self.fc1(x)))
```

**Key Differences: Encoder vs Decoder:**

| Feature | Encoder | Decoder |
|---------|---------|---------|
| Self-Attention | Full attention matrix | Causal (masked) attention |
| Cross-Attention | None | Attends to encoder output |
| Input Processing | Entire sequence at once | Autoregressive (one token at a time) |
| Output | Contextual representations for all tokens | Next-token prediction logits |

---

## 5. Practical Study Plan

### Week-by-Week Learning Schedule

**Weeks 1-2: Foundations of Neural Networks**
- [ ] Read "Neural Networks and Deep Learning" (http://neuralnetworksanddeeplearning.com)
- [ ] Implement a multi-layer perceptron from scratch in Python/NumPy
- [ ] Understand forward/backward propagation mathematically
- [ ] Experiment with different activation functions

**Weeks 3-4: Training Optimization**
- [ ] Study gradient descent variants (SGD, Adam, RMSProp)
- [ ] Implement backpropagation from scratch for a small network
- [ ] Learn about regularization techniques (dropout, weight decay)
- [ ] Practice hyperparameter tuning

**Weeks 5-6: Introduction to Transformers**
- [ ] Read "The Illustrated Transformer" (https://jalammar.github.io/illustrated-transformer/)
- [ ] Implement self-attention from scratch
- [ ] Understand positional encoding implementations
- [ ] Build a simple encoder-only transformer

**Weeks 7-8: Deep Dive into Architecture**
- [ ] Implement full encoder-decoder transformer
- [ ] Study BERT vs GPT architectures (encoder-only vs decoder-only)
- [ ] Learn about RoPE and modern positional encodings
- [ ] Experiment with different layer normalization strategies

**Weeks 9-10: Applications and Advanced Topics**
- [ ] Study attention visualization techniques
- [ ] Learn about prompt engineering and fine-tuning
- [ ] Explore transformer variants (Vision Transformers, etc.)
- [ ] Read recent research papers in the field

### Recommended Exercises

**Beginner:**
```python
# Exercise 1: Implement a simple neural network from scratch
import numpy as np

class SimpleNN:
    def __init__(self, input_size, hidden_size, output_size):
        self.W1 = np.random.randn(input_size, hidden_size) * 0.1
        self.b1 = np.zeros((1, hidden_size))
        self.W2 = np.random.randn(hidden_size, output_size) * 0.1
        self.b2 = np.zeros((1, output_size))
    
    def forward(self, x):
        z1 = x.dot(self.W1) + self.b1
        a1 = np.maximum(0, a1)  # ReLU activation
        z2 = a1.dot(self.W2) + self.b2
        return z2
    
    def backward(self, x, y_true, y_pred):
        m = len(y_true)
        dz2 = (y_pred - y_true) / m  # MSE derivative
        dW2 = a1.T.dot(dz2) / m
        db2 = np.mean(dz2, axis=0, keepdims=True)
        
        da1 = dz2.dot(self.W2.T)
        dz1 = da1 * (np.maximum(0, z1 > 0))  # ReLU derivative
        dW1 = x.T.dot(dz1) / m
        db1 = np.mean(dz1, axis=0, keepdims=True)
        
        return {'dW1': dW1, 'db1': db1, 'dW2': dW2, 'db2': db2}

# Exercise 2: Implement self-attention from scratch
import torch
import math

class SelfAttention(torch.nn.Module):
    def __init__(self, embed_dim, num_heads):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        
        self.q_proj = torch.nn.Linear(embed_dim, embed_dim)
        self.k_proj = torch.nn.Linear(embed_dim, embed_dim)
        self.v_proj = torch.nn.Linear(embed_dim, embed_dim)
    
    def forward(self, x):
        B, T, C = x.size()
        
        # Project to Q, K, V
        q = self.q_proj(x).view(B, T, self.num_heads, -1).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_heads, -1).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_heads, -1).transpose(1, 2)
        
        # Scale dot-product attention
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(C // self.num_heads)
        attn_weights = F.softmax(attn_weights, dim=-1)
        
        out = torch.matmul(attn_weights, v).transpose(1, 2).contiguous().view(B, T, C)
        return out

# Exercise 3: Generate positional encodings
import numpy as np

def get_positional_encoding(max_len=5000, d_model=512):
    """Generate sinusoidal positional embeddings"""
    pe = np.zeros((max_len, d_model))
    
    position = np.arange(0, max_len).reshape(-1, 1)
    div_term = np.exp(np.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))
    
    pe[:, 0::2] = np.sin(position.astype(float) * div_term)
    pe[:, 1::2] = np.cos(position.astype(float) * div_term)
    
    return pe
```

### Additional Resources

**Essential Reading:**
- "Deep Learning" by Goodfellow, Bengio, Courville (free online book)
- "The Illustrated Transformer" - Jay Alammar's blog series
- Dive into Deep Learning (d2l.ai) - comprehensive free textbook

**Key Papers to Read:**
1. Vaswani et al., "Attention Is All You Need" (2017) - Original transformer paper
2. Devlin et al., "BERT: Pre-training of Deep Bidirectional Transformers" (2019)
3. Radford et al., "Language Models are Unsupervised Multitask Learners" (GPT-2, 2019)

**Tools for Practice:**
- PyTorch tutorials and examples
- Hugging Face transformers library documentation
- Fast.ai practical deep learning courses

---

*Study Guide Version 1.0 | Last Updated: July 2026*
