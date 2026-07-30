# Neural Networks and Transformers Study Guide

A comprehensive learning resource covering foundational concepts to advanced topics in neural networks and transformer architectures.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Fundamentals of Neural Networks](#fundamentals-of-neural-networks)
3. [Backpropagation and Gradient Descent](#backpropagation-and-gradient-descent)
4. [Deep Dive into Transformers](#deep-dive-into-transformers)
5. [Encoders and Decoders](#encoders-and-decoders)
6. [Practical Exercise: Building a Simple Transformer](#practical-exercise-building-a-simple-transformer)
7. [Study Plan and Resources](#study-plan-and-resources)

---

## Introduction

Neural networks and transformers are foundational technologies in modern artificial intelligence. Neural networks inspired by biological neural systems form the basis of machine learning, while transformers revolutionized natural language processing with their self-attention mechanisms. This guide will take you from basic concepts to understanding how these architectures work under the hood.

---

## Fundamentals of Neural Networks

### What is a Neural Network?

A neural network is a computational model inspired by biological neurons. It consists of layers of interconnected nodes (neurons) that process information through weighted connections.

### Basic Components

#### Neuron (Perceptron)
The simplest unit of a neural network:
- Takes multiple inputs
- Applies weights to each input
- Adds a bias term
- Applies an activation function

Mathematical representation:
```
z = w₁x₁ + w₂x₂ + ... + wₙxₙ + b
a = f(z)
```

Where:
- `wᵢ` are weights
- `xᵢ` are inputs
- `b` is bias
- `f()` is activation function (e.g., ReLU, sigmoid)

### Neural Network Architecture

#### Layers
1. **Input Layer**: Receives raw data
2. **Hidden Layers**: Process information through transformations
3. **Output Layer**: Produces final predictions

#### Types of Neural Networks

| Type | Use Case | Key Feature |
|------|----------|-------------|
| MLP (Multi-Layer Perceptron) | Classification, Regression | Fully connected layers |
| CNN (Convolutional Neural Network) | Image processing | Convolution operations |
| RNN (Recurrent Neural Network) | Sequential data | Memory cells for sequences |

### Activation Functions

Different activation functions introduce non-linearity:

```python
# Common activation functions
import numpy as np

def relu(x):
    return max(0, x)  # Rectified Linear Unit

def sigmoid(x):
    return 1 / (1 + np.exp(-x))  # For probabilities

def tanh(x):
    return np.tanh(x)  # Normalized output (-1 to 1)

def softmax(logits):
    exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
    return exp_logits / np.sum(exp_logits)  # Probability distribution
```

---

## Backpropagation and Gradient Descent

### The Learning Process

Neural networks learn by adjusting their weights to minimize prediction error. This is achieved through:

1. **Forward Pass**: Compute predictions
2. **Loss Calculation**: Measure error
3. **Backward Pass (Backpropagation)**: Compute gradients
4. **Weight Update**: Adjust parameters via gradient descent

### Loss Functions

Different tasks require different loss functions:

```python
import numpy as np

def mse_loss(y_true, y_pred):
    """Mean Squared Error for regression"""
    return np.mean((y_true - y_pred) ** 2)

def cross_entropy_loss(y_true, y_pred):
    """Cross-entropy for classification (with numerical stability)"""
    epsilon = 1e-15
    y_pred = np.clip(y_pred, epsilon, 1 - epsilon)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))

def categorical_cross_entropy(y_true_probs, y_pred_probs):
    """Cross-entropy for multi-class classification"""
    num_classes = len(y_pred_probs[0])
    epsilon = 1e-15
    log_probs = np.log(np.clip(y_pred_probs, epsilon, 1 - epsilon))
    return -np.mean([log_probs[i][y_true] for i, y_true in enumerate(y_true_probs)])
```

### Backpropagation Algorithm

Backpropagation uses the chain rule to compute gradients:

```python
import numpy as np

class SimpleNeuralNetwork:
    """Minimal neural network demonstrating backpropagation"""
    
    def __init__(self, input_size, hidden_size, output_size):
        # Xavier initialization for better training dynamics
        self.W1 = np.random.randn(input_size, hidden_size) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros((1, hidden_size))
        self.W2 = np.random.randn(hidden_size, output_size) * np.sqrt(2.0 / hidden_size)
        self.b2 = np.zeros((1, output_size))
        
    def forward(self, X):
        """Forward pass with intermediate values for backprop"""
        # First layer: linear + activation
        self.z1 = X @ self.W1 + self.b1  # Linear combination
        self.a1 = np.maximum(0, self.z1)  # ReLU activation
        
        # Second layer (output without activation for regression)
        self.z2 = self.a1 @ self.W2 + self.b2
        
        return self.z2
    
    def backward(self, X, y, z2):
        """Backpropagation using chain rule"""
        m = X.shape[0]  # Batch size
        
        # Output layer gradient (MSE loss derivative)
        dz2 = (z2 - y) / m  # Error signal from output
        
        # Gradients for second layer weights and bias
        dW2 = np.outer(self.a1, dz2)  # Shape: (hidden_size, output_size)
        db2 = np.sum(dz2, axis=0, keepdims=True)  # Sum over batch dimension
        
        # Backpropagate to first layer
        da1 = dz2 @ self.W2.T  # Chain rule: dL/da1 = dL/dz2 * dz2/da1
        dz1 = np.where(self.z1 > 0, da1, 0)  # ReLU derivative
        
        # Gradients for first layer
        dW1 = np.outer(X, dz1)
        db1 = np.sum(dz1, axis=0, keepdims=True)
        
        return {
            'dW1': dW1, 'db1': db1,
            'dW2': dW2, 'db2': db2
        }
    
    def update_weights(self, gradients, learning_rate=0.01):
        """Gradient descent weight update"""
        self.W1 -= learning_rate * self.W1.grad if hasattr(self.W1, 'grad') else 0
```

### Complete Backpropagation Example

```python
import numpy as np

class NeuralNetworkWithBackprop:
    """Full neural network with backpropagation and gradient descent"""
    
    def __init__(self, input_dim, hidden_dim, output_dim):
        # Xavier/Glorot initialization for better convergence
        scale1 = np.sqrt(2.0 / (input_dim + hidden_dim))
        scale2 = np.sqrt(2.0 / (hidden_dim + output_dim))
        
        self.W1 = np.random.randn(input_dim, hidden_dim) * scale1
        self.b1 = np.zeros((1, hidden_dim))
        self.W2 = np.random.randn(hidden_dim, output_dim) * scale2
        self.b2 = np.zeros((1, output_dim))
        
    def forward(self, X):
        """Forward pass with caching for backprop"""
        # Layer 1: Linear + ReLU
        self.z1 = X @ self.W1 + self.b1
        self.a1 = np.maximum(0, self.z1)  # ReLU activation
        
        # Output layer (no activation for regression)
        self.z2 = self.a1 @ self.W2 + self.b2
        
        return self.z2
    
    def backward(self, X, y):
        """Backpropagation using chain rule"""
        m = X.shape[0]  # Batch size
        
        # Output layer gradients (MSE loss: L = (y - ŷ)²/2m)
        dz2 = (self.z2 - y) / m  # dL/dz2
        
        dW2 = np.outer(self.a1, dz2)  # Chain rule: dL/dW2 = da1^T * dz2
        db2 = np.sum(dz2, axis=0, keepdims=True)
        
        # Backpropagate through hidden layer
        da1 = dz2 @ self.W2.T  # Chain rule: dL/da1 = dz2 * W2^T
        
        # ReLU derivative: only active neurons contribute to gradient
        dz1 = np.where(self.z1 > 0, da1, 0)
        
        dW1 = np.outer(X, dz1)
        db1 = np.sum(dz1, axis=0, keepdims=True)
        
        return {
            'dW1': dW1, 'db1': db1,
            'dW2': dW2, 'db2': db2
        }
    
    def update(self, gradients, lr=0.01):
        """Gradient descent weight updates"""
        self.W1 -= lr * gradients['dW1']
        self.b1 -= lr * gradients['db1']
        self.W2 -= lr * gradients['dW2']
        self.b2 -= lr * gradients['db2']
```

### Momentum and Adam Optimizers

Simple gradient descent can oscillate; momentum helps:

```python
class SGDWithMomentum:
    """Stochastic Gradient Descent with momentum"""
    
    def __init__(self, param_list, lr=0.01, momentum=0.9):
        self.lr = lr
        self.momentum = momentum
        self.velocity = {param.name: np.zeros_like(param.data) 
                        for param in param_list}
        
    def step(self, gradients):
        """Update weights with momentum"""
        v = self.velocity
        
        for name, grad in gradients.items():
            # Velocity update: blend old velocity with new gradient
            if hasattr(grad, 'shape'):  # NumPy array
                v[name] = self.momentum * v[name] + (1 - self.momentum) * grad
            else:  # PyTorch tensor or similar
                v[name].data.copy_(self.momentum * v[name] + grad)
            
            if hasattr(grad, 'shape'):
                getattr(self, name).data.add_(-0.01 * grad)

class AdamOptimizer:
    """Adam optimizer with bias correction"""
    
    def __init__(self, param_list, lr=0.001, betas=(0.9, 0.999), eps=1e-8):
        self.lr = lr
        self.betas = betas
        self.eps = eps
        self.m = {p.name: np.zeros_like(p.data) for p in param_list}  # First moment
        self.v = {p.name: np.zeros_like(p.data) for p in param_list}  # Second moment
        
    def step(self, gradients):
        """Adam update with bias correction"""
        t = len([g for g in gradients.values() if hasattr(g, 'shape')]) + 1
        
        for name, grad in gradients.items():
            self.m[name] = self.betas[0] * self.m[name] + (1 - self.betas[0]) * grad
            self.v[name] = self.betas[1] * self.v[name] + (1 - self.betas[1]) * (grad ** 2)
            
            # Bias correction for early training steps
            m_hat = self.m[name] / (1 - self.betas[0] ** t)
            v_hat = self.v[name] / (1 - self.betas[1] ** t)
            
            param = getattr(self, name) if hasattr(self, name) else None
            if param is not None:
                param.data.add_(-self.lr * m_hat / (np.sqrt(v_hat) + self.eps))
```

---

## Deep Dive into Transformers

### The Transformer Architecture

Transformers revolutionized NLP with their attention-based architecture introduced in "Attention Is All You Need" (2017). Unlike RNNs that process sequences sequentially, transformers use parallel computation through attention mechanisms.

### Self-Attention Mechanism

Self-attention allows each position to attend to all other positions, capturing long-range dependencies:

```python
import numpy as np

class MultiHeadSelfAttention:
    """Multi-head self-attention mechanism"""
    
    def __init__(self, d_model, num_heads):
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"
        
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        
        # Learnable linear projections for multi-head attention
        self.query_proj = np.random.randn(d_model, d_model) / np.sqrt(d_model)
        self.key_proj = np.random.randn(d_model, d_model) / np.sqrt(d_model)
        self.value_proj = np.random.randn(d_model, d_model) / np.sqrt(d_model)
        
    def forward(self, x, mask=None):
        """Forward pass with multi-head attention"""
        batch_size, seq_len, d_model = x.shape
        
        # Project to query, key, value spaces
        Q = x @ self.query_proj  # (batch, seq, d_model)
        K = x @ self.key_proj
        V = x @ self.value_proj
        
        # Reshape for multi-head attention
        Q = Q.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        K = K.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        V = V.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        
        # Compute attention scores: QK^T / sqrt(d_k)
        scores = np.matmul(Q, K.transpose(0, 1, 3, 2)) / np.sqrt(self.head_dim)
        
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        
        # Apply softmax to get attention weights
        attn_weights = np.softmax(scores, axis=-1)
        
        # Aggregate values with attention weights
        out = np.matmul(attn_weights, V).transpose(0, 2, 3, 1).reshape(batch_size, seq_len, d_model)
        
        return out, attn_weights
    
    def backward(self, x, dy):
        """Backward pass for multi-head attention"""
        batch_size, seq_len, d_model = x.shape
        
        # Reshape inputs
        Q = x @ self.query_proj.reshape(1, -1).T
        K = x @ self.key_proj
        V = x @ self.value_proj
        
        Q = Q.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        K = K.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        V = V.reshape(batch_size, seq_len, self.num_heads, self.head_dim).transpose(0, 2, 1, 3)
        
        # Attention scores and weights
        d_k = np.sqrt(self.head_dim)
        K_T = K.transpose(0, 1, 3, 2)
        attn_scores = (Q @ K_T) / d_k
        
        epsilon = 1e-9
        attn_weights = np.exp(attn_scores - np.max(attn_scores, axis=-1, keepdims=True)) \
                     + epsilon
        attn_weights /= (np.sum(attn_weights, axis=-1, keepdims=True) + epsilon)
        
        # Backward through value projection
        dV = attn_weights @ V.reshape(batch_size, seq_len, -1).T  # (batch, heads, seq, head_dim) -> (heads, batch, seq, head_dim)
        
        # Reshape for backward through attention scores
        d_scores = dV.reshape(batch_size, self.num_heads, seq_len, self.head_dim).transpose(0, 2, 0, 3, 2) \
                 .reshape(batch_size * seq_len, self.num_heads, self.head_dim) \
                 .reshape(self.num_heads, batch_size, seq_len, self.head_dim).T
        
        d_Q = np.matmul(d_scores, V.reshape(batch_size, seq_len, -1))
        
        return {
            'dQ': d_Q,
            'dK': K @ dV.T / d_k,
            'dV': dV
        }
```

### Positional Encoding

Transformers lack recurrence and convolution, so they need explicit positional information:

```python
import numpy as np

class PositionalEncoding:
    """Learnable or fixed positional encoding for transformers"""
    
    def __init__(self, d_model, max_len=5000):
        self.d_model = d_model
        self.max_len = max_len
        
        # Learnable positional embeddings
        self.positional_encoding = np.random.randn(max_len, d_model) * 0.1
    
    def forward(self, x):
        """Add positional encoding to input"""
        batch_size, seq_len, d_model = x.shape
        
        # Scale down high-frequency components for better learning
        scale = np.arange(1, d_model + 1) ** (-0.5)
        
        pe = self.positional_encoding[:seq_len] @ scale.reshape(1, -1)
        
        return x + pe
    
    def backward(self, x_encoded, dy):
        """Backward pass for positional encoding"""
        # Positional encoding is added element-wise, so gradients flow directly
        dx = dy  # Gradients flow to input unchanged
        dpe = np.zeros_like(self.positional_encoding[:x.shape[1]])
        
        return {
            'dx': dx,
            'd_pe': dpe
        }

class SinusoidalPositionEncoding:
    """Fixed sinusoidal positional encoding (like original Transformer paper)"""
    
    def __init__(self, d_model):
        self.d_model = d_model
    
    def forward(self, seq_len):
        """Generate positional encodings for sequence length"""
        
        # Position indices
        position_idx = np.arange(seq_len).reshape(1, -1)
        
        # 2D embedding matrix [pos, dim]
        pe = np.zeros((seq_len, self.d_model))
        
        odd_indices = range(0, self.d_model, 2)
        even_indices = range(1, self.d_model, 2)
        
        for pos in range(seq_len):
            for i in odd_indices:
                pe[pos, i] = np.sin(pos / 10000 ** (2 * i / self.d_model))
            for i in even_indices:
                pe[pos, i] = np.cos(pos / 10000 ** (2 * i / self.d_model))
        
        return pe
    
    def backward(self, x_encoded, dy):
        """Backward pass - positional encoding is fixed"""
        return {'dx': dy}
```

### Layer Normalization

Layer normalization stabilizes training by normalizing across features:

```python
import numpy as np

class LayerNormalization:
    """Layer normalization for transformer layers"""
    
    def __init__(self, d_model, eps=1e-5):
        self.d_model = d_model
        self.eps = eps
        
        # Learnable scale and shift parameters
        self.gamma = np.ones(d_model)  # Scale
        self.beta = np.zeros(d_model)  # Shift
    
    def forward(self, x, residual=None):
        """Forward pass with optional skip connection"""
        
        mean = np.mean(x, axis=-1, keepdims=True)
        variance = np.var(x, axis=-1, keepdims=True)
        
        normalized = (x - mean) / np.sqrt(variance + self.eps)
        
        scaled = normalized * self.gamma + self.beta
        
        if residual is not None:
            output = x + scaled  # Residual connection
            
        return output
    
    def backward(self, x, dy):
        """Backward pass for layer normalization"""
        
        mean = np.mean(x, axis=-1, keepdims=True)
        variance = np.var(x, axis=-1, keepdims=True)
        
        normalized = (x - mean) / np.sqrt(variance + self.eps)
        
        dx_normalized = dy * self.gamma
        
        # Gradients for scale and shift parameters
        dgamma = np.sum(dy * normalized, axis=0, keepdims=False)
        dbeta = np.sum(dy, axis=0, keepdims=False)
        
        # Gradient through normalization
        one_over_var = 1 / np.sqrt(np.var(x, axis=-1, keepdims=True) + self.eps)
        dx = (one_over_var * dx_normalized).reshape(-1, x.shape[-1])
        
        return {
            'dx': dx,
            'dgamma': dgamma,
            'dbeta': dbeta
        }

class RMSNorm:
    """Root Mean Square Layer Normalization (no affine transformation)"""
    
    def __init__(self, d_model):
        self.d_model = d_model
    
    def forward(self, x):
        """RMS normalization"""
        
        rms = np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True))
        normalized = x / (rms + 1e-5)
        
        return normalized
    
    def backward(self, x, dy):
        """Backward pass for RMS norm"""
        
        rms = np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True))
        one_over_rms = 1 / (rms + 1e-5)
        
        dx = dy * one_over_rms
        
        return {'dx': dx}
```

---

## Encoders and Decoders

### Transformer Encoder Architecture

Encoders process input sequences and produce contextual representations:

```python
import numpy as np

class TransformerEncoderLayer:
    """Transformer encoder layer with multi-head attention and feed-forward"""
    
    def __init__(self, d_model, num_heads, ff_dim=4 * d_model, dropout_rate=0.1):
        self.d_model = d_model
        self.num_heads = num_heads
        
        # Multi-head self-attention
        self.attention = MultiHeadSelfAttention(d_model, num_heads)
        
        # Layer normalization before attention (pre-norm)
        self.norm1 = LayerNormalization(d_model)
        
        # Feed-forward network
        self.ff = np.random.randn(d_model, ff_dim) * np.sqrt(2.0 / d_model)
        self.ff_gamma = np.ones(ff_dim)
        self.ff_beta = np.zeros(ff_dim)
        
        # Second layer normalization
        self.norm2 = LayerNormalization(d_model)
    
    def forward(self, x):
        """Encoder forward pass"""
        
        # Self-attention with residual connection
        attn_output = self.attention.forward(x)
        x_after_attn = x + attn_output
        
        # Feed-forward with residual
        ff_input = self.norm1.forward(x_after_attn)
        ff_output = ff_input @ self.ff * self.ff_gamma + self.ff_beta
        
        return x + ff_output
    
    def backward(self, x, dy):
        """Backward pass for encoder"""
        
        # Gradient through feed-forward
        dff = np.sum(dy, axis=0)  # Shape: (d_model,)
        
        dx_after_attn = self.norm1.backward(x_after_attn, dy - dff)
        
        return {
            'dx': dx,
            'dff': dff
        }

class TransformerDecoderLayer:
    """Transformer decoder layer with causal masking"""
    
    def __init__(self, d_model, num_heads, ff_dim=4 * d_model):
        self.d_model = d_model
        
        # Causal attention (mask future positions)
        self.attention = MultiHeadSelfAttention(d_model, num_heads, causal=True)
        
        # Cross-attention to encoder output
        self.cross_attention = MultiHeadCrossAttention(
            d_model, num_heads, encoder_dim=d_model
        )
        
        # Layer normalizations
        self.norm1 = LayerNormalization(d_model)
        self.norm2 = LayerNormalization(d_model)
    
    def forward(self, x, memory):
        """Decoder forward pass with causal masking"""
        
        # Causal attention (self-attention on decoder input)
        attn_output = self.attention.forward(x, mask=causal_mask)
        x_after_attn = x + attn_output
        
        # Cross-attention to encoder memory
        cross_attn_input = self.norm2.forward(x_after_attn)
        cross_attn_output = cross_attn_input @ self.cross_attention.weights
        
        return x + cross_attn_output

class TransformerEncoder:
    """Full transformer encoder stack"""
    
    def __init__(self, d_model=512, num_heads=8, num_layers=6, ff_dim=2048):
        self.d_model = d_model
        self.num_layers = num_layers
        
        # Positional encoding
        self.pos_encoding = SinusoidalPositionEncoding(d_model)
        
        # Encoder layers
        self.layers = [
            TransformerEncoderLayer(d_model, num_heads, ff_dim) 
            for _ in range(num_layers)
        ]
    
    def forward(self, x):
        """Forward pass through encoder"""
        
        batch_size, seq_len, d_model = x.shape
        
        # Add positional encoding
        x_with_pos = self.pos_encoding.forward(x)
        
        # Pass through encoder layers
        for layer in self.layers:
            x = layer.forward(x)
        
        return x
    
    def backward(self, x, dy):
        """Backward pass through encoder"""
        
        # Accumulate gradients
        dW1_total = np.zeros_like(self.W1)
        db1_total = np.zeros_like(self.b1)
        
        for layer in self.layers:
            grad = layer.backward(x, dy)
            
            dW1_total += grad['dW1']
            db1_total += grad['db1']
        
        return {
            'dW1': dW1_total,
            'db1': db1_total
        }

class TransformerDecoder:
    """Full transformer decoder stack"""
    
    def __init__(self, d_model=512, num_heads=8, num_layers=6, ff_dim=2048):
        self.d_model = d_model
        
        # Positional encoding for decoder (different from encoder)
        self.pos_encoding_decoder = SinusoidalPositionEncoding(d_model)
        
        # Decoder layers
        self.layers = [
            TransformerDecoderLayer(d_model, num_heads, ff_dim) 
            for _ in range(num_layers)
        ]
    
    def forward(self, x, memory):
        """Forward pass through decoder with causal masking"""
        
        batch_size, seq_len, d_model = x.shape
        
        # Add positional encoding
        x_with_pos = self.pos_encoding_decoder.forward(x)
        
        # Pass through decoder layers
        for layer in self.layers:
            x = layer.forward(x, memory)
        
        return x

class Transformer:
    """Complete encoder-decoder transformer architecture"""
    
    def __init__(self, d_model=512, num_heads=8, src_vocab_size=10000, 
                 tgt_vocab_size=10000, max_seq_len=512):
        self.d_model = d_model
        
        # Embeddings
        self.src_embedding = np.random.randn(src_vocab_size, d_model) * 0.1
        self.tgt_embedding = np.random.randn(tgt_vocab_size, d_model) * 0.1
        
        # Encoder and decoder
        self.encoder = TransformerEncoder(d_model, num_heads)
        self.decoder = TransformerDecoder(d_model, num_heads)
        
        # Output projection
        self.output_projection = np.random.randn(tgt_vocab_size, d_model) * 0.1
    
    def forward(self, src_seq, tgt_seq):
        """Forward pass through encoder-decoder"""
        
        batch_size, src_len, _ = src_seq.shape
        
        # Embed source sequence
        src_emb = self.src_embedding[src_seq]  # (batch, seq, d_model)
        
        # Pass through encoder
        enc_output = self.encoder.forward(src_emb)
        
        # Embed target and get causal mask
        tgt_emb = self.tgt_embedding[tgt_seq]
        
        # Decode
        dec_output = self.decoder.forward(tgt_emb, enc_output)
        
        # Project to vocabulary
        logits = dec_output @ self.output_projection
        
        return logits
    
    def backward(self, src_seq, tgt_seq, dlogits):
        """Backward pass through encoder-decoder"""
        
        batch_size, src_len, _ = src_seq.shape
        
        # Embed source sequence
        src_emb = self.src_embedding[src_seq]
        
        # Pass through encoder and get gradients
        enc_grads = self.encoder.backward(src_emb, dlogits)
        
        return {
            'dW_src': np.sum(dlogits, axis=(0, 2)),
            **enc_grads
        }

class CausalMask:
    """Causal mask for decoder self-attention"""
    
    @staticmethod
    def create_causal_mask(seq_len):
        """Create upper triangular mask for causal attention"""
        
        # Create sequence indices
        i = np.arange(seq_len).reshape(1, -1)
        j = np.arange(seq_len).reshape(-1, 1)
        
        # Upper triangular matrix (False means attend to this position)
        mask = j >= i
        
        return mask

class MultiHeadCrossAttention:
    """Multi-head cross-attention for decoder"""
    
    def __init__(self, d_model, num_heads, encoder_dim):
        self.d_model = d_model
        
        # Query from decoder keys/values from encoder memory
        self.query_proj = np.random.randn(d_model, d_model) / np.sqrt(d_model)
        self.key_proj = np.random.randn(encoder_dim, d_model) / np.sqrt(d_model)
        self.value_proj = np.random.randn(encoder_dim, d_model) / np.sqrt(d_model)
    
    def forward(self, query, memory):
        """Cross-attention: attend to encoder output"""
        
        batch_size, tgt_len, _ = query.shape
        
        # Project query and keys/values from memory
        Q = query @ self.query_proj
        K = memory @ self.key_proj
        V = memory @ self.value_proj
        
        # Compute attention weights
        scores = np.matmul(Q, K.transpose(0, 2, 3, 1)) / np.sqrt(self.d_model)
        
        attn_weights = np.softmax(scores, axis=-1)
        
        # Aggregate values
        out = np.matmul(attn_weights, V).transpose(0, 2, 3, 1).reshape(batch_size, tgt_len, d_model)
        
        return out
```

---

## Practical Exercise: Building a Simple Transformer

Let's build a minimal transformer that can learn to predict the next character in a sequence. This hands-on exercise will solidify your understanding of all the concepts we've covered.

### Exercise 1: Character-Level Language Model

Create a simple transformer that learns from text:

```python
import numpy as np

class SimpleTransformer:
    """Minimal transformer for language modeling"""
    
    def __init__(self, vocab_size=27, embedding_dim=32, num_heads=4, 
                 num_layers=1, dropout_rate=0.1):
        
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        
        # Embedding layer (shared for input and output)
        self.embedding = np.random.randn(vocab_size, embedding_dim) * 0.1
        
        # Positional embeddings
        max_len = 512
        pe = np.zeros((max_len, embedding_dim))
        
        position_idx = np.arange(max_len).reshape(1, -1)
        for pos in range(max_len):
            for i in range(0, embedding_dim, 2):
                pe[pos, i] = np.sin(pos / 10000 ** (2 * i / embedding_dim))
                pe[pos, i + 1] = np.cos(pos / 10000 ** ((2 * i + 2) / embedding_dim))
        
        self.positional_encoding = pe[:512]
        
        # Multi-head attention parameters
        assert embedding_dim % num_heads == 0
        
        head_dim = embedding_dim // num_heads
        
        self.query_proj = np.random.randn(embedding_dim, embedding_dim) * 0.02
        self.key_proj = np.random.randn(embedding_dim, embedding_dim) * 0.02
        self.value_proj = np.random.randn(embedding_dim, embedding_dim) * 0.02
        
        # Feed-forward network
        ff_dim = 4 * embedding_dim
        
        self.ff1 = np.random.randn(embedding_dim, ff_dim) * 0.02
        self.ff2 = np.random.randn(ff_dim, embedding_dim) * 0.02
        
    def forward(self, x):
        """Forward pass through the transformer"""
        
        batch_size, seq_len, _ = x.shape
        
        # Add positional encoding
        pos_emb = self.positional_encoding[:seq_len].repeat(batch_size, axis=0)
        x_with_pos = x + pos_emb
        
        # Multi-head attention
        Q = x_with_pos @ self.query_proj
        K = x_with_pos @ self.key_proj
        V = x_with_pos @ self.value_proj
        
        # Reshape for multi-head
        head_dim = self.embedding_dim // 4  # Assuming 4 heads
        
        Q = Q.reshape(batch_size, seq_len, 4, head_dim).transpose(0, 2, 1, 3)
        K = K.reshape(batch_size, seq_len, 4, head_dim).transpose(0, 2, 1, 3)
        V = V.reshape(batch_size, seq_len, 4, head_dim).transpose(0, 2, 1, 3)
        
        # Attention scores and weights
        d_k = np.sqrt(head_dim)
        attn_scores = Q @ K.transpose(0, 1, 3, 2) / d_k
        
        epsilon = 1e-9
        attn_weights = np.exp(attn_scores - np.max(attn_scores, axis=-1, keepdims=True)) \
                     + epsilon
        attn_weights /= (np.sum(attn_weights, axis=-1, keepdims=True) + epsilon)
        
        # Aggregate values
        out = np.matmul(attn_weights, V).transpose(0, 2, 3, 1).reshape(batch_size, seq_len, embedding_dim)
        
        return out
    
    def backward(self, x, dy):
        """Backward pass"""
        
        batch_size, seq_len, _ = x.shape
        
        # Multi-head attention gradients (simplified)
        dW_q = np.sum(dy, axis=(0, 2)) / self.embedding_dim
        db_q = np.sum(dy, axis=0)
        
        return {
            'dW_q': dW_q,
            'db_q': db_q
        }

# Training loop example
def train_transformer(model, text_data, epochs=10):
    """Simple training loop"""
    
    batch_size = 4
    seq_len = 32
    
    for epoch in range(epochs):
        total_loss = 0
        
        # Sample mini-batches
        indices = np.random.choice(len(text_data), len(text_data) // batch_size, replace=False)
        
        for i in range(len(indices)):
            start_idx = indices[i]
            
            # Get input sequence
            x = text_data[start_idx:start_idx + seq_len]
            
            # Forward pass
            logits = model.forward(x)
            
            # Compute loss (simplified cross-entropy)
            loss = np.mean((logits - x) ** 2)
            
            total_loss += loss
            
            # Backward pass
            grads = model.backward(x, (logits - x))
        
        print(f"Epoch {epoch}, Loss: {total_loss / len(indices):.4f}")

# Usage example
if __name__ == "__main__":
    # Create transformer
    model = SimpleTransformer(vocab_size=27, embedding_dim=32, num_heads=4)
    
    # Sample text data (replace with actual data)
    text_data = np.array([[0, 1, 2], [3, 4, 5]] * 100)
    
    # Train the model
    train_transformer(model, text_data, epochs=5)
```

### Exercise 2: Analyzing Attention Patterns

Create a visualization to understand what your transformer is learning:

```python
import numpy as np
import matplotlib.pyplot as plt

def visualize_attention(attention_weights):
    """Visualize attention patterns"""
    
    batch_size, num_heads, seq_len, _ = attention_weights.shape
    
    fig, axes = plt.subplots(num_heads, 1, figsize=(num_heads * 4, num_heads * 3))
    
    for i in range(num_heads):
        # Get attention weights for first sequence
        attn = np.abs(attention_weights[0, i].flatten())
        
        im = ax[i].imshow(attn, aspect='auto', cmap='viridis')
        ax[i].set_title(f'Attention Head {i}')
        plt.colorbar(im, ax=ax[i])
    
    plt.tight_layout()
    plt.show()

# Example usage with real data
def analyze_attention_patterns(model, input_seq):
    """Analyze attention patterns for a given sequence"""
    
    batch_size = 1
    seq_len = len(input_seq)
    
    # Forward pass to get attention weights
    attention_weights, _ = model.attention.forward(
        x_with_pos, causal_mask=causal_mask(seq_len)
    )
    
    print(f"Attention shape: {attention_weights.shape}")
    print(f"\nSample attention weights (first head):")
    print(attention_weights[0, 0])

# Exercise 3: Hyperparameter Tuning Experiment
def hyperparameter_experiment():
    """Experiment with different configurations"""
    
    configs = [
        {'embedding_dim': 16, 'num_heads': 2, 'ff_dim': 64},
        {'embedding_dim': 32, 'num_heads': 4, 'ff_dim': 128},
        {'embedding_dim': 64, 'num_heads': 8, 'ff_dim': 256}
    ]
    
    results = []
    
    for i, config in enumerate(configs):
        model = SimpleTransformer(**config)
        
        # Train and evaluate
        loss_before = train_and_evaluate(model, text_data, epochs=3)
        
        results.append({
            'embedding_dim': config['embedding_dim'],
            'num_heads': config['num_heads'],
            'loss': loss_before
        })
    
    print("\nHyperparameter comparison:")
    for result in results:
        print(f"Embedding={result['embedding_dim']}, Heads={result['num_heads']}: Loss={result['loss']:.4f}")

# Exercise 4: Building a Small Language Model
def build_mini_lm():
    """Build a working character-level language model"""
    
    # Simple vocabulary mapping
    vocab = {chr(65 + i): i for i in range(26)}  # A-Z
    vocab[' '] = 26
    
    def text_to_indices(text):
        return [vocab.get(c, 0) for c in text]
    
    def indices_to_text(indices):
        return ''.join([chr(i + 65) if i < 26 else ' ' for i in indices])
    
    # Create training data
    training_text = "The quick brown fox jumps over the lazy dog. " * 10
    
    model = SimpleTransformer(vocab_size=30, embedding_dim=32, num_heads=4)
    
    # Train
    train_transformer(model, text_to_indices(training_text), epochs=5)
    
    # Generate text (simple greedy decoding)
    start_token = 65  # 'A'
    generated = [start_token]
    
    for _ in range(30):
        input_seq = np.array([generated[-1]] + [0] * (seq_len - 1))
        
        logits = model.forward(input_seq)
        next_token = np.argmax(logits[0, -1])
        generated.append(next_token)
    
    print("Generated text:")
    print(indices_to_text(generated))

# Exercise 5: Understanding Gradient Flow
def analyze_gradient_flow():
    """Analyze how gradients flow through the network"""
    
    model = SimpleTransformer(vocab_size=27, embedding_dim=32, num_heads=4)
    
    # Create sample input
    x = np.random.randn(1, 8, 32) * 0.1
    
    # Forward pass with gradient tracking
    def forward_with_tracking():
        Q = x @ model.query_proj
        K = x @ model.key_proj
        V = x @ model.value_proj
        
        scores = Q @ K.transpose(0, 1, 3, 2) / np.sqrt(model.embedding_dim // 4)
        
        attn_weights = np.exp(scores - np.max(scores, axis=-1, keepdims=True)) \
                     + 1e-9
        attn_weights /= (np.sum(attn_weights, axis=-1, keepdims=True) + 1e-9)
        
        out = np.matmul(attn_weights, V).transpose(0, 2, 3, 1).reshape(x.shape[0], x.shape[1], model.embedding_dim)
        
        return out
    
    # Compute gradients and analyze norm
    dy = np.random.randn(*x.shape) * 0.01
    dx = forward_with_tracking().backward(x, dy)
    
    print(f"Input gradient norm: {np.linalg.norm(dx):.4f}")
    print(f"Output gradient norm: {np.linalg.norm(dy):.4f}")

# Exercise 6: Training with Different Optimizers
def compare_optimizers():
    """Compare SGD, Adam, and RMSProp on the transformer"""
    
    optimizers = {
        'SGD': lambda params, grads: update_sgd(params, grads, lr=0.01),
        'Adam': lambda params, grads: update_adam(params, grads, lr=0.001),
        'RMSProp': lambda params, grads: update_rmsprop(params, grads, lr=0.01)
    }
    
    for name, optimizer in optimizers.items():
        model = SimpleTransformer(vocab_size=27, embedding_dim=32, num_heads=4)
        
        # Train with this optimizer
        loss_history = train_with_optimizer(model, text_data, epochs=5, 
                                            optimizer=optimizer)
    
    print("\nOptimizer comparison:")
    for name, history in optimizers.items():
        print(f"{name}: Final Loss = {history[-1]:.4f}")

# Main execution
if __name__ == "__main__":
    # Run exercises
    print("=== Exercise 1: Building a Simple Transformer ===")
    model = SimpleTransformer(vocab_size=27, embedding_dim=32, num_heads=4)
    
    print("\n=== Exercise 5: Gradient Flow Analysis ===")
    analyze_gradient_flow()

# Save the study guide for reference
print("\nStudy Guide Complete!")
```

---

## Study Plan and Resources

### Recommended Learning Schedule

#### Week 1-2: Fundamentals of Neural Networks
- **Days 1-3**: Basic neural network concepts (perceptrons, layers, activation functions)
- **Days 4-7**: Forward/backward propagation, gradient descent
- **Days 8-10**: Implementing a simple MLP from scratch
- **Day 11-12**: Understanding optimization algorithms (SGD, momentum, Adam)

#### Week 3-4: Deep Dive into Transformers
- **Days 15-17**: Self-attention mechanism and positional encoding
- **Days 18-20**: Layer normalization and feed-forward networks
- **Days 21-23**: Encoder-decoder architecture
- **Days 24-26**: Multi-head attention implementation

#### Week 5: Practical Application
- **Days 29-31**: Building a character-level language model
- **Days 32-34**: Analyzing attention patterns and gradient flow
- **Days 35-37**: Hyperparameter tuning experiments
- **Days 38-39**: Final project: Build your own transformer

### Recommended Resources

#### Free Online Courses
1. **Andrew Ng's Deep Learning Specialization** (Coursera) - Complete foundation
2. **Fast.ai Practical Deep Learning** - Top-down approach with code-first learning
3. **Stanford CS224n** - Natural language processing with transformers
4. **Hugging Face Course** - Practical transformer fine-tuning

#### Books and Documentation
1. **"Deep Learning" by Goodfellow, Bengio, Courville** - Comprehensive textbook
2. **"Dive into Deep Learning"** (d2l.ai) - Free online book with code examples
3. **Transformer Architecture Paper**: "Attention Is All You Need" (Vaswani et al., 2017)

#### Practice Platforms
1. **Kaggle** - Competitions and datasets for practice
2. **Hugging Face Datasets** - Large-scale NLP datasets
3. **Google Colab** - Free GPU access for experiments

### Key Concepts Checklist

After studying, you should be able to:

- [ ] Explain how a simple neural network processes information
- [ ] Derive the backpropagation algorithm using chain rule
- [ ] Implement gradient descent with momentum and Adam optimizer
- [ ] Explain self-attention mechanism mathematically
- [ ] Implement multi-head attention from scratch
- [ ] Understand positional encoding necessity in transformers
- [ ] Implement layer normalization variants (LayerNorm, RMSNorm)
- [ ] Explain encoder-decoder architecture differences
- [ ] Build a working transformer from scratch
- [ ] Analyze and visualize attention patterns
- [ ] Debug training issues (vanishing gradients, etc.)

### Final Tips for Success

1. **Code First**: Don't just read - implement each concept yourself
2. **Visualize**: Plot loss curves, attention maps, and gradient norms
3. **Debug Systematically**: Use print statements to track values through layers
4. **Start Small**: Build a 2-layer network before jumping to full transformers
5. **Read Papers Carefully**: Focus on equations and architecture diagrams

### Quick Reference: Key Equations

```python
# Neural Network Forward Pass
z = Wx + b
a = f(z)  # Activation function

# Backpropagation (Chain Rule)
dL/dW = da/dz * dz/dW * dL/da
dL/db = dL/da * da/db

# Self-Attention Scores
score(Q, K) = QK^T / sqrt(d_k)

# Attention Weights (Softmax)
alpha = softmax(score(Q, K))

# Attention Output
Output = alphaV

# Positional Encoding (Sinusoidal)
PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^((2i+1)/d_model))
```

---

## Conclusion

This study guide has covered the essential concepts of neural networks and transformers from first principles. By working through the practical exercises and following the learning schedule, you'll gain a deep understanding of how these powerful models work under the hood.

Remember: The best way to learn is by doing. Implement each concept yourself, experiment with different architectures, and don't hesitate to revisit earlier concepts as they become more relevant in advanced topics.

Good luck with your studies! 🚀
