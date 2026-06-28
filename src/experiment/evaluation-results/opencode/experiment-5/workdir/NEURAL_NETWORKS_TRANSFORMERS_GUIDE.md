# Comprehensive Guide to Neural Networks & Transformers

---

## Table of Contents

1. [Introduction](#introduction)
2. [Neural Networks Fundamentals](#neural-networks-fundamentals)
3. [Deep Learning Architectures](#deep-learning-architectures)
4. [Transformers Architecture](#transformers-architecture)
5. [Implementation Examples](#implementation-examples)
6. [Applications & Use Cases](#applications--use-cases)

---

## Introduction

### What are Neural Networks?

**Neural networks (NN)** are computational models inspired by the structure and function of biological neural networks in brains. They consist of interconnected nodes (neurons) organized in layers that process information through weighted connections.

### What are Transformers?

The **Transformer architecture**, introduced in 2017, revolutionized deep learning for sequence processing tasks like language modeling, translation, and text generation by replacing recurrent structures with self-attention mechanisms.

---

## Neural Networks Fundamentals

### Core Components

#### 1. Neurons (Perceptrons)

A basic neuron computes a weighted sum of inputs plus a bias:

```
z = Σ(w_i * x_i) + b
a = σ(z)  # where σ is activation function
```

**Activation Functions:**

| Function | Formula | Use Case |
|----------|---------|----------|
| Sigmoid | `σ(x) = 1/(1+e^-x)` | Binary classification output |
| Tanh | `tanh(x)` | Hidden layers (zero-centered) |
| ReLU | `max(0, x)` | Most common for hidden layers |
| Leaky ReLU | `max(αx, x)` if x<0 else x | Prevents "dying ReLU" problem |

#### 2. Layers

- **Input Layer**: Receives raw data (no activation)
- **Hidden Layers**: Process information with weights and activations
- **Output Layer**: Produces final predictions

#### 3. Forward Propagation

Data flows from input → hidden layers → output:

```python
# Pseudocode
def forward(x):
    z1 = W1 @ x + b1        # Linear transformation
    a1 = relu(z1)           # Activation (hidden layer)
    
    z2 = W2 @ a1 + b2
    a2 = softmax(z2)        # Output for classification
    
    return a2
```

#### 4. Loss Function

Measures difference between prediction and actual:

| Task | Common Loss Functions |
|------|-----------------------|
| Classification | Cross-Entropy, MSE |
| Regression | Mean Squared Error (MSE), MAE |
| Binary Classification | Binary Cross-Entropy |

**Cross-Entropy Loss:**
```python
L = -Σ y*log(p)            # One-hot encoding
# or for single label:
L = -(y * log(pred_y))     # Where py is predicted class probability
```

#### 5. Backpropagation & Gradient Descent

Updates weights to minimize loss using chain rule:

```python
# Simplified gradient descent step
for epoch in epochs:
    pred = forward(x)                  # Forward pass
    loss = compute_loss(pred, y)       # Compute error
    
    grad = backward(loss, x)           # Backward pass (chain rule)
    
    W -= learning_rate * grad          # Weight update
```

---

## Deep Learning Architectures

### 1. Feedforward Neural Networks (FNN/MLP)

**Structure:** Fully connected layers with no spatial structure awareness.

```python
# Simple MLP architecture
class SimpleMLP:
    def __init__(self):
        self.W1 = random_weights(input_dim, hidden_dim)
        self.b1 = zeros(hidden_dim)
        
        self.W2 = random_weights(hidden_dim, output_dim)
        self.b2 = zeros(output_dim)
    
    def forward(self, X):
        z1 = X @ self.W1 + self.b1
        h = relu(z1)                      # Hidden layer
        
        z2 = h @ self.W2 + self.b2       # Output layer
        output = softmax(z2)              # For classification
    
    return output
```

### 2. Convolutional Neural Networks (CNNs)

**For image processing tasks.** Key innovation: spatial locality and parameter sharing.

#### Core Components:

| Component | Purpose | Typical Values |
|-----------|---------|----------------|
| **Conv Layer** | Extract features via filters/kernels | 3×3 or 5×5 kernels |
| **ReLU/Pooling** | Non-linearity / dimension reduction | Pool size 2×2, stride 2 |
| **BatchNorm** | Normalization for stability | After conv layers |

#### Architecture Example:

```python
class CNN:
    def __init__(self):
        # Conv1 -> ReLU -> MaxPool -> Conv2 -> ReLU -> MaxPool -> FC
        self.conv1 = weights(3, input_channels)     # 3×3 kernel
        self.bn1 = BatchNorm(input_channels)
        
        self.conv2 = weights(3, out_channels)       # Feature maps
        self.pool = max_pool(kernel=2, stride=2)    # Downsample
    
    def forward(self, x):                          # Image input (H×W×C)
        z1 = conv(x, self.conv1)                   # Feature extraction
        a1 = relu(z1)
        
        p1 = pool(a1)                              # Reduce spatial dims
        
        z2 = conv(p1, self.conv2)                  # More features
        a2 = relu(z2)
        
        flat = flatten(a2)                         # Flatten for FC
        logits = fc(flat, output_dim=classes)
    
    return softmax(logits)
```

### 3. Recurrent Neural Networks (RNNs)

**For sequential data.** Same weights used at each time step to process sequences.

#### Basic RNN Cell:

```python
def rnn_step(x_t, h_prev):
    # x_t: input at current timestep
    # h_prev: hidden state from previous timestep
    
    z = W_x @ x_t + W_h @ h_prev + b      # Combine inputs and memory
    h = tanh(z)                            # New hidden state (memory)
    
    return h, z                           # Output for prediction if needed

# Processing sequence of length T:
def rnn_forward(X):                       # X is batch × seq_len × features
    H = []                                # Store all hidden states
    
    for t in range(seq_len):
        x_t = X[:, t]                     # Extract timestep input
        h, out = rnn_step(x_t, 0)         # Initialize with zero state
        
        H.append(h)                       # Save memory at each step
    
    return stack(H), logits(out)          # Final hidden + prediction
```

#### Common RNN Variants:

- **LSTM (Long Short-Term Memory):** Uses gates to control information flow, handles long dependencies better.
- **GRU (Gated Recurrent Unit):** Simpler LSTM variant with fewer parameters.

### 4. Attention Mechanisms

**Core Idea:** Focus computation on relevant parts of input rather than processing everything equally.

#### Self-Attention:

```python
def scaled_dot_product_attention(Q, K, V):   # Query, Key, Value matrices
    
    scores = (Q @ K.T) / sqrt(d_k)           # Dot product + scaling
    attn_weights = softmax(scores)           # Normalize to probabilities
    
    output = attn_weights @ V                # Weighted sum of values
    
    return output                             # Same dimension as Q
```

**Why Scaling?** Prevents vanishing gradients from large dot products. `d_k` is key vector dimension.

---

## Transformers Architecture

### Historical Context

The **Transformer paper** ("Attention Is All You Need", 2017) introduced a new architecture that completely replaced recurrent and convolutional structures for sequence tasks, achieving SOTA on machine translation benchmarks.

### Key Innovations:

| Innovation | Pre-Transformers (RNN/CNN) | Transformers |
|------------|-----------------------------|--------------|
| **Parallelization** | Sequential processing | Full parallelism across positions |
| **Long-range dependencies** | O(n²) complexity, limited by recurrence | Direct connections via attention |
| **Positional encoding** | Implicit in RNN state transitions | Explicit positional embeddings added to inputs |

### Core Architecture Components

#### 1. Positional Encoding (PE)

Since transformers lack sequential processing like RNNs, we must inject position information:

```python
# Sinusoidal PE formula from original paper
def get_positional_encoding(pos, d_model):
    # pos: integer scalar (position index)
    
    angle_rates = 1 / np.power(10_000, 
                                   [2i/d_model for i in range(d_model//2)])
    angles = pos[:, None] * angle_rates[None, :]   # Broadcasting
    
    pe = np.concatenate([np.sin(angles), np.cos(angles)], axis=-1)
    
    return pe[:d_model]  # Return first d_model dimensions

# PE is added to input embeddings:
final_input = word_embeddings + positional_encoding
```

#### 2. Multi-Head Self-Attention (MSA)

Allows the model to attend to information from different representation subspaces simultaneously.

**Architecture:**

```python
class MultiHeadSelfAttention(nn.Module):
    def __init__(self, d_model, num_heads):
        self.num_heads = num_heads
        
        # Split dimensions across heads
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"
        
        self.d_k = d_model // num_heads      # Dimension per head
    
    def forward(self, X):                    # X: batch × seq_len × d_model
        
        split_batch_dim(X) -> [X1, ..., Xn]  # Split into heads
        
        for each_head in heads:
            Q_i = Linear(head_input, self.d_k)(each_head)   # Query projection
            K_i = Linear(each_head, self.d_k)               # Key projection
            V_i = Linear(each_head, self.d_k)               # Value projection
            
            head_output = scaled_dot_product_attention(Q_i, K_i, V_i)
        
        concat_outputs(head_outputs)         # Concatenate all heads
        
    return linear(concatenated_heads, d_model)  # Project back to full dimension


# Attention visualization:
def visualize_attention_weights(X):
    attn_scores = compute_softmax((X @ X.T) / sqrt(d))
    
    for head in attention_heads:
        print(f"Head {head} attends most strongly to:")
        top_indices = np.argsort(attn_scores[0, :, 0])[-3:]   # Top 3 positions
        print(top_indices.tolist())
```

#### 3. Encoder-Decoder Structure

**Encoder:** Processes input sequence (source)  
**Decoder:** Generates output sequence (target), attending to encoder states

### Transformer Architecture Diagrams

#### Standard Encoder:

```
┌─────────────────────────────────────────────────────┐
│              ENCODER LAYER 1                         │
│ ┌──────────┐     ┌──────────┐                       │
│ │ Self-Attn│◄──►│ Add & Norm│◄─────────────────────│
│ └──────────┘     └──────────┘                       │
│              ▲                                       │
│              │ (skip connection)                     │
│ ┌──────────┐     ┌──────────┐                       │
│ │ Feed Fwd │◄──►│ Add & Norm│ ◄─ Input Embedding +  │
│ │   Net    │     └──────────┘ PE                      │
│ └──────────┘                                             │
└─────────────────────────────────────────────────────┘

Feed Forward Network (FFN) per layer:
    Linear(2*d_model) -> ReLU/GeLU -> Linear(d_model)
```

#### Decoder Structure (simplified):

```
Decoder Layer:
  ┌──────────────────────┐     ┌───────────────────────┐
  │ Masked Self-Attention│◄──►│ Add & Norm             │
  │ (causal attention)   │    │                        │
  └──────────────────────┘     └───────────────────────┘
              ▲                              ▲
              │ (skip connection)            │
  ┌──────────┴──────────┐     ┌────────────┴──────────┐
  │ Enc-Dec Attention   │◄──►│ Add & Norm             │
  │ (attends to encoder)│    │                        │
  └─────────────────────┘     └───────────────────────┘
              ▲                              ▲
              │ (skip connection)            │
  ┌──────────┴──────────┐     ┌────────────┴──────────┐
  │ Feed Forward Net    │◄──►│ Add & Norm             │ ◄─ Target Embedding + PE
  │                     │    │                        │
  └─────────────────────┘     └───────────────────────┘

Output: Linear(d_model, vocab_size) -> Softmax
```

### Complete Transformer Implementation (Python/PyTorch-style)

```python
import torch.nn as nn
from typing import Tuple

class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding."""
    
    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * 
                           (-torch.log(torch.tensor(10000.0)) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
    
    def forward(self, x):                    # x: batch × seq_len × d_model
        return x + self.pe[:x.size(1)]       # Add PE to embeddings


class MultiHeadAttention(nn.Module):
    """Multi-Head Self Attention."""
    
    def __init__(self, embed_dim: int, num_heads: int, dropout=0.1):
        super().__init__()
        
        assert embed_dim % num_heads == 0
        
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        
        # Linear projections for Q/K/V (same input/output dims)
        self.q_linear = nn.Linear(embed_dim, embed_dim)
        self.k_linear = nn.Linear(embed_dim, embed_dim)
        self.v_linear = nn.Linear(embed_dim, embed_dim)
        
        # Output projection back to full dimension
        self.out_proj = nn.Linear(embed_dim, embed_dim)
    
    def forward(self, x, mask=None):         # x: batch × seq_len × d_model
        
        B, T, C = x.shape                    # Dimensions
    
        Q = self.q_linear(x).reshape(B, T, 
                                     self.num_heads, self.head_dim)   # [B,T,C] -> [B,num_heads,T,d_k]
        K = self.k_linear(x).reshape(B, T, 
                                     self.num_heads, self.head_dim)
        V = self.v_linear(x).reshape(B, T, 
                                     self.num_heads, self.head_dim)
    
        # Transpose heads: [batch, num_heads, seq_len, head_dim] -> [num_heads, batch, seq_len, head_dim]
        Q, K, V = map(lambda t: t.transpose(1, 2), (Q, K, V))      # Move heads to first dim
    
        scaled_QK = Q @ K.transpose(-2, -1) / math.sqrt(self.head_dim)   # [num_heads,B,T,T]
    
        attn_weights = F.softmax(scaled_QK + 
                                (mask.unsqueeze(0).repeat(self.num_heads, 1, 1)) if mask is not None else 0, dim=-1)
    
        out = attn_weights @ V                          # Attention output
    
        return out.transpose(1, 2).reshape(B, T, C)     # Project back to original shape


class TransformerEncoderLayer(nn.Module):
    """Single encoder layer with multi-head attention and feed-forward."""
    
    def __init__(self, d_model: int, num_heads: int, dim_feedforward=2048, dropout=0.1):
        super().__init__()
        
        self.self_attn = MultiHeadAttention(d_model, num_heads)
        # Feed forward network (expand then reduce dimensions)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, dim_feedforward),
            nn.GELU(),  # Or ReLU/LeakyReLU
            nn.Dropout(dropout),
            nn.Linear(dim_feedforward, d_model)
        )
        
        # Layer normalization (applied after each sublayer + residual connection)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
    
    def forward(self, x):                    # Residual connections: x_norm -> sublayer(x_norm) -> norm(sublayer_out + x_norm)
        
        x = self.add_residual(self.self_attn(self.norm1(x)))      # Self-attention block
    
        return self.add_residual(self.ffn(self.norm2(x)))         # Feed-forward block


class TransformerEncoder(nn.Module):
    """Complete encoder stack."""
    
    def __init__(self, vocab_size: int, d_model: int, num_heads: int, 
                 num_layers: int, max_seq_len: int = 512):
        super().__init__()
        
        self.embedding = nn.Embedding(vocab_size, d_model)          # Word embeddings
        
        self.pos_encoder = PositionalEncoding(d_model, max_seq_len) # Add PE
    
    def forward(self, x):                                           # x: batch × seq_len (integer indices)
        
        x = self.embedding(x).unsqueeze(1)                         # [B,T] -> [B,1,T,d_model]
    
        return pos_encoder(x)                                       # Embeddings + positional encoding


class TransformerDecoderLayer(nn.Module):
    """Single decoder layer with 3 attention mechanisms."""
    
    def __init__(self, d_model: int, num_heads: int, dim_feedforward=2048, dropout=0.1):
        super().__init__()
        
        self.self_attn = MultiHeadAttention(d_model, num_heads)      # Masked self-attention (causal)
    
    def forward(self, x, memory, tgt_mask=None, mem_mask=None):
        """x: decoder input; memory: encoder output"""
        
        pass  # Implementation omitted for brevity


class Transformer(nn.Module):
    """Complete transformer model."""
    
    def __init__(self, vocab_size: int, d_model: int, num_heads: int, 
                 num_layers_encoder: int = 6, num_layers_decoder: int = 6,
                 dim_feedforward=2048, dropout=0.1):
        super().__init__()
        
        self.encoder = TransformerEncoder(vocab_size, d_model, num_heads, 
                                          num_layers_encoder)
    
    def forward(self, src, tgt=None):                               # Encoder-only or encoder-decoder
        """src: source sequence (batch × seq_len); tgt: target for decoder"""
    
        return self.encoder(src)                                     # Or both encoder and decoder


class TransformerClassifier(nn.Module):
    """Transformer-based classification model."""
    
    def __init__(self, vocab_size: int, d_model: int, num_heads: int, 
                 num_layers: int = 2, dropout=0.1):
        super().__init__()
        
        self.transformer_encoder = TransformerEncoder(vocab_size, d_model, num_heads, num_layers)
    
    def forward(self, x):                                           # x: batch × seq_len
    
        h = self.encoder(x)                                         # [B,T,d_model]
        cls_token = torch.zeros(h.size(0), 1, d_model).to(x.device) # Learnable or fixed CLS token
        
        return fc_linear(torch.cat([cls_token, h], dim=1), num_classes)   # Pool via CLS token


class TransformerLM(nn.Module):
    """Transformer language model (decoder-only for text generation)."""
    
    def __init__(self, vocab_size: int, d_model: int, num_heads: int, 
                 max_seq_len: int = 512, dropout=0.1):
        super().__init__()
        
        self.embedding = nn.Embedding(vocab_size, d_model)          # Input embeddings
    
    def forward(self, x):                                           # x: batch × seq_len (input tokens)
    
        h = embedding(x).transpose(1, 2)                            # [B,T,d] -> [T,B,d] for decoder
        
        return logits                                               # Output logits over vocabulary


# Training loop example with transformer classification model:

def train_transformer(model, dataloader, optimizer, criterion):
    """Train a transformer classifier on batches of token sequences."""
    
    for batch_idx, (x_batch, y_batch) in enumerate(dataloader):
        x = x_batch.to(device)                                      # Input sequence
        
        pred = model(x).squeeze(1)                                   # [B] predictions
    
        loss = criterion(pred, y_batch)                              # Cross-entropy or other loss
    
        optimizer.zero_grad()                                        # Reset gradients
        
        loss.backward()                                              # Backpropagation
    
    return loss.item()                                               # Return batch loss for monitoring
```

---

## Applications & Use Cases

### Classification Tasks:

| Task | Architecture Choice | Notes |
|------|---------------------|--------|
| Text classification (sentiment, topic) | Transformer encoder + CLS pooling | Most effective |
| Image classification | CNN or Vision Transformer (ViT) | ViT treats image as sequence of patches |
| Audio event detection | 1D-CNN or transformer on spectrogram features | |

### Sequence Tasks:

| Task | Architecture Choice | Notes |
|------|---------------------|--------|
| Machine translation | Encoder-decoder Transformer (original architecture) | Standard approach |
| Text generation / chatbot | Decoder-only Transformer (like GPT series) | Autoregressive generation |
| Named entity recognition | Bidirectional LSTM or BERT encoder + CRF layer | Contextual embeddings help |

### Advanced Architectures:

#### Vision Transformers (ViT):

```python
class ViT(nn.Module):
    """Vision transformer - treats image as sequence of patches."""
    
    def __init__(self, img_size=224, patch_size=16, d_model=768, num_heads=12):
        super().__init__()
        
        self.patch_dim = 3 * (patch_size ** 2)                     # RGB channels
        
        n_patches = (img_size // patch_size)**2                    # Number of patches
    
    def forward(self, x):                                          # x: batch × H × W × C
    
        B, _, H, W = x.shape                                       
        x = x.reshape(B, -1, self.patch_dim)                        # [B,H*W,C]
    
        cls_tokens = torch.zeros(B, 1, d_model).to(x.device)       # Add CLS token
        
        return transformer_encoder(cls_tokens + positional_encoding)


class BERT(nn.Module):
    """BERT model - bidirectional encoder for NLP tasks."""
    
    def __init__(self, vocab_size=30522, embed_dim=768, num_heads=12, 
                 num_layers=12, max_seq_len=512):
        super().__init__()
        
        self.embedding = nn.Embedding(vocab_size + 2, embed_dim)   # +BOS/EOS tokens
    
    def forward(self, x):                                          # x: [batch × seq_len]
    
        h = transformer_encoder(x)                                  # Bidirectional
        
        return h                                                   # Contextualized token embeddings


class GPT(nn.Module):
    """GPT model - decoder-only for language modeling."""
    
    def __init__(self, vocab_size=50304, embed_dim=768, num_heads=12, 
                 num_layers=12, max_seq_len=2048):
        super().__init__()
        
        self.embedding = nn.Embedding(vocab_size + 2, embed_dim)   # Input embeddings
    
    def forward(self, x):                                          # Autoregressive generation
        
        h = decoder_transformer(x)                                   # Causal attention only
        
        return logits                                               # Next token prediction


# Pre-trained Transformer Models (Hugging Face API example):

from transformers import BertTokenizer, BertModel, GPT2LMHeadModel
import torch

tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
model = BertModel.from_pretrained("bert-base-uncased")  # Fine-tune for classification

inputs = tokenizer.encode_plus(
    "This is a sample text.", 
    return_tensors="pt", max_length=512, padding=True)

outputs = model(**inputs)                                        # Get contextual embeddings


# Custom fine-tuning with Hugging Face transformers:

from transformers import BertForSequenceClassification
model_for_cls = BertForSequenceClassification.from_pretrained(
    "bert-base-uncased", num_labels=2)  # Binary classification task


def train_transformer_hf(model, dataloader):                       # Using Trainer API
    from transformers import Trainer, TrainingArguments
    
    trainer = Trainer(
        model=model,
        args=TrainingArguments("output_dir"),
        train_dataset=dataloader.dataset,
    )
    
    trainer.train()                                                # Train with Hugging Face pipeline


# Summary comparison table:

"""
┌─────────────────────┬──────────────────┬─────────────────┐
│ Architecture        │ Best For         │ Key Characteristic │
├─────────────────────┼──────────────────┼───────────────────┤
│ MLP (FNN)           │ Simple tabular   │ Fully connected,  │
│                     │ data             │ no spatial/       │
│                     │                  │ temporal awareness │
├─────────────────────┼──────────────────┼───────────────────┤
│ CNN                 │ Images           │ Spatial locality, │
│                     │ (2D)             │ parameter sharing │
├─────────────────────┼──────────────────┼───────────────────┤
│ RNN/LSTM/GRU        │ Time series      │ Sequential         │
│                     |                  │ processing          │
├─────────────────────┼──────────────────┼───────────────────┤
│ Transformer          │ Text, vision     │ Parallel           │
│                     | language models  │ attention, long-   │
│                     | (NLP)            │ range dependencies │
└─────────────────────┴──────────────────┴───────────────────┘

"""


## Key Takeaways:

1. **Neural Networks**: Foundation of deep learning; learn hierarchical representations through layered composition.

2. **CNNs** excel at 2D spatial data (images) via local receptive fields and parameter sharing.

3. **RNNs/LSTMs** handle sequential data but suffer from training parallelization limits and limited memory retention over long sequences.

4. **Transformers** use self-attention to directly model relationships between all positions in a sequence, enabling:
   - Full parallel computation during training
   - Omitting recurrent/convolutional structures entirely for certain tasks
   - Scaling to massive datasets with hundreds of billions of parameters (e.g., GPT series)

5. **Hybrid approaches** often combine architectures (CNN encoder + transformer decoder, etc.) depending on task requirements.

6. **Modern practice**: Pre-trained large-scale models (BERT, RoBERTa, GPT-3/4, LLaMA) dominate NLP tasks; Vision Transformers are competitive with CNNs for image recognition.

---

## Further Reading:

1. **"Attention Is All You Need"** - The original Transformer paper
2. **Deep Learning Books**: 
   - "Dive into Deep Learning" (free online)
   - "Deep Learning" by Goodfellow et al. ("The Bible of DL")
3. **Courses**: Fast.ai, Coursera's DeepLearning.AI
