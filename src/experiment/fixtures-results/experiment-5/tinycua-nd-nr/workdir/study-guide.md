# Neural Networks and Transformers: Comprehensive Study Guide

A complete learning resource covering neural networks, Transformer architecture, training optimization, and practical implementation.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Neural Network Fundamentals](#neural-network-fundamentals)
   - [Basic Architecture](#basic-architecture)
   - [Neurons and Perceptrons](#neurons-and-perceptrons)
   - [Network Layers](#network-layers)
   - [Forward Propagation](#forward-propagation)
   - [Activation Functions](#activation-functions)
   - [Loss Functions](#loss-functions)
   - [Data Preprocessing](#data-preprocessing)
3. [Transformer Architecture Components](#transformer-architecture-components)
   - [Self-Attention Mechanism](#self-attention-mechanism)
   - [Positional Encoding](#positional-encoding)
   - [Encoder Architecture](#encoder-architecture)
   - [Decoder Architecture](#decoder-architecture)
   - [Complete Transformer Model](#complete-transformer-model)
4. [Training Optimization Concepts](#training-optimization-concepts)
   - [Backpropagation](#backpropagation)
   - [Computational Graph](#computational-graph)
   - [Chain Rule Derivation](#chain-rule-derivation)
   - [Gradient Descent Variants](#gradient-descent-variants)
   - [Learning Rate Schedules](#learning-rate-schedules)
   - [Regularization Techniques](#regularization-techniques)
5. [Implementation Overview](#implementation-overview)
6. [Glossary](#glossary)
7. [References](#references)

---

## Introduction

Neural networks are computational models inspired by biological neural networks in the brain. They form the foundation of modern machine learning and deep learning, enabling systems to learn patterns from data and make predictions or classifications.

This guide covers the essential concepts you need to understand before diving into more advanced topics like Transformers, backpropagation, and optimization techniques.

---

## Basic Neural Network Architecture

### What is a Neural Network?

A neural network is a collection of interconnected nodes (neurons) organized in layers. It processes information by passing signals through these connections, learning to map inputs to outputs through training.

### Key Components

```
Input Layer → Hidden Layers → Output Layer
```

- **Input Layer**: Receives the raw input data (e.g., pixel values, text embeddings)
- **Hidden Layers**: Intermediate layers that transform the data
- **Output Layer**: Produces the final prediction or classification

### Network Types

| Type | Description | Use Case |
|------|-------------|----------|
| Feedforward Neural Network (FNN) | Information flows in one direction | Classification, regression |
| Convolutional Neural Network (CNN) | Uses convolution operations | Image processing |
| Recurrent Neural Network (RNN) | Processes sequential data | Time series, text |

---

## Neurons and Perceptrons

### The Biological Inspiration

Neural networks are inspired by neurons in the human brain. Just as biological neurons connect to form neural pathways, artificial neurons (or nodes) are connected with weights that determine how strongly they're connected.

### The Artificial Neuron

A single artificial neuron, also called a **perceptron**, is the fundamental building block of neural networks. It performs these operations:

1. **Receives inputs**: Takes multiple input values
2. **Computes weighted sum**: Multiplies each input by its corresponding weight
3. **Adds bias**: Shifts the result to allow better fitting
4. **Applies activation function**: Introduces non-linearity

### Mathematical Formulation

For a single neuron with `n` inputs:

$$z = \sum_{i=1}^{n} (w_i \cdot x_i) + b$$

Where:
- $x_i$ = input value at position i
- $w_i$ = weight for input i
- $b$ = bias term
- $z$ = weighted sum before activation

Then apply an activation function $\sigma$:

$$a = \sigma(z)$$

### The Perceptron Learning Algorithm

The perceptron is a simple learning algorithm that can learn to classify linearly separable data:

**Algorithm Steps:**
1. Initialize weights and bias randomly (usually small values)
2. For each training example $(x, y)$:
   - Compute prediction: $z = w \cdot x + b$
   - Apply activation if needed
   - Calculate error: $error = target - prediction$
   - Update weights: $w_i = w_i + learning\_rate \cdot error \cdot x_i$
   - Update bias: $b = b + learning\_rate \cdot error$

### Universal Approximation Theorem

An important theoretical result: A neural network with at least one hidden layer containing a finite number of neurons can approximate any continuous function given an appropriate choice of weights. This is why neural networks are so powerful!

---

## Network Layers

### Layer Types

Neural networks organize neurons into layers, each serving a specific purpose:

#### Input Layer
- Contains no computation
- Passes input features to the network
- Number of neurons = number of input features

#### Hidden Layers
- Perform computation and feature extraction
- Each hidden layer transforms the data representation
- Can have different numbers of neurons

#### Output Layer
- Produces final predictions
- Architecture depends on task:
  - **Binary classification**: Single neuron with sigmoid activation
  - **Multi-class classification**: Multiple neurons with softmax activation
  - **Regression**: One or more neurons with linear activation (no activation)

### Layer Configuration Example

```
Input Layer:          784 neurons (28x28 image pixels)
Hidden Layer 1:       256 neurons, ReLU activation
Hidden Layer 2:       128 neurons, ReLU activation
Output Layer:         10 neurons, softmax activation (digit classification)
```

### Depth and Width

- **Depth**: Number of hidden layers (deeper = deeper learning)
- **Width**: Number of neurons in each layer

Common architectures:
- Shallow networks: 1-2 hidden layers
- Deep networks: Many hidden layers (used in deep learning)

---

## Forward Propagation

### What is Forward Propagation?

Forward propagation (or forward pass) is the process of passing input data through the neural network to generate a prediction. Data flows from the input layer, through each hidden layer, to the output layer.

### Step-by-Step Process

1. **Input Layer**: Raw features are received
2. **Hidden Layers**: Each layer performs:
   - Weighted sum: $z = W \cdot x + b$ (matrix operations)
   - Activation: $a = \sigma(z)$
3. **Output Layer**: Final activation produces prediction

### Matrix Formulation

For efficient computation with batch data, we use matrix operations:

**Layer Input:**
$$z^{(l)} = W^{(l)} \cdot a^{(l-1)} + b^{(l)}$$

Where:
- $W^{(l)}$ = weight matrix for layer l
- $a^{(l-1)}$ = activations from previous layer
- $b^{(l)}$ = bias vector
- $z^{(l)}$ = pre-activation values

Then apply activation function:

$$a^{(l)} = \sigma(z^{(l)})$$

### Example: Simple 2-Neuron Hidden Layer

Given input vector $x = [x_1, x_2, x_3]$ and weights for first hidden neuron:

**First Hidden Neuron:**
```
z₁ = w₁₁·x₁ + w₁₂·x₂ + w₁₃·x₄ + b₁
a₁ = ReLU(z₁) = max(0, z₁)
```

**Second Hidden Neuron:**
```
z₂ = w₂₁·x₁ + w₂₂·x₂ + w₂₃·x₄ + b₂
a₂ = ReLU(z₂) = max(0, z₂)
```

These activations $[a_1, a_2]$ become input to the next layer.

### Computational Graph Perspective

Think of forward propagation as traversing a computational graph:
- Each node represents an operation (multiply, add, activation)
- Data flows forward through edges
- The output is the final prediction

---

## Activation Functions

### What Are Activation Functions?

Activation functions introduce non-linearity into neural networks. Without them, no matter how many layers you stack, a neural network would just be a linear transformation, unable to learn complex patterns.

### Why Non-Linearity Matters

Consider two linear transformations:
- Linear layer 1: $y = W_1 \cdot x + b_1$
- Linear layer 2: $y = W_2 \cdot y + b_2$

Combined: $W_2 \cdot (W_1 \cdot x + b_1) + b_2 = W_{combined} \cdot x + b_{combined}$

This collapses to a single linear transformation! Activation functions prevent this collapse.

### Common Activation Functions

#### 1. Sigmoid

**Formula:**
$$\sigma(z) = \frac{1}{1 + e^{-z}}$$

**Characteristics:**
- Output range: $(0, 1)$
- Produces probabilities (good for binary classification)
- Derivative: $\sigma'(z) = \sigma(z)(1 - \sigma(z))$

**Pros:**
- Outputs between 0 and 1 (natural for probabilities)
- Smooth and differentiable
- Easy to interpret outputs as probabilities

**Cons:**
- **Vanishing gradient problem**: Gradients become very small for large inputs
- **Not zero-centered**: Can cause slow convergence in some cases
- **Saturation**: Gradients approach zero for extreme values

**Use Cases:**
- Output layer for binary classification
- Older models (historical context)

---

#### 2. Tanh (Hyperbolic Tangent)

**Formula:**
$$\tanh(z) = \frac{e^z - e^{-z}}{e^z + e^{-z}}$$

**Characteristics:**
- Output range: $(-1, 1)$
- Zero-centered (unlike sigmoid)
- Derivative: $\tanh'(z) = 1 - \tanh^2(z)$

**Pros:**
- Zero-centered output (helps with gradient flow)
- Stronger gradients than sigmoid in some regions
- Works better than sigmoid for hidden layers

**Cons:**
- Still suffers from vanishing gradients (though less than sigmoid)
- Outputs still saturate for extreme values

**Use Cases:**
- Hidden layers in RNNs (historically)
- Some older architectures

---

#### 3. ReLU (Rectified Linear Unit)

**Formula:**
$$\text{ReLU}(z) = \max(0, z)$$

**Characteristics:**
- Output: $z$ if $z > 0$, else $0$
- Simple and computationally efficient
- Derivative: $1$ if $z > 0$, else $0$ (undefined at 0)

**Pros:**
- **No vanishing gradients**: Gradient is 1 for positive inputs
- **Computationally cheap**: Simple max operation
- **Sparsity**: Many neurons output 0, leading to sparse representations
- **Works well empirically**: Standard in modern deep learning

**Cons:**
- **Dying ReLU problem**: Neurons can get stuck outputting 0 permanently if they receive negative inputs during training
- Not zero-centered (can cause optimization issues)
- Derivative is 0 for all negative inputs

**Variants to Address Dying ReLU:**
- **Leaky ReLU**: $\text{LeakyReLU}(z) = \max(\alpha z, z)$ where $\alpha$ is small (e.g., 0.01)
- **Parametric ReLU (PReLU)**: Learnable $\alpha$ parameter
- **ELU (Exponential Linear Unit)**: Smooth transition for negative values

**Use Cases:**
- Standard for hidden layers in convolutional networks
- Most modern deep learning architectures
- Default choice for most applications

---

#### 4. Softmax (for Output Layer)

**Formula:**
$$\text{softmax}(z_i) = \frac{e^{z_i}}{\sum_{j} e^{z_j}}$$

**Characteristics:**
- Outputs sum to 1 (probability distribution)
- Used for multi-class classification output layer
- Derivative: Complex but derivable

**Use Cases:**
- Output layer for multi-class classification
- Converts logits to probabilities

---

### Activation Function Comparison

| Function | Range | Zero-Centered | Vanishing Gradients | Best For |
|----------|-------|---------------|---------------------|----------|
| Sigmoid | (0, 1) | No | Yes (severe) | Binary classification output |
| Tanh | (-1, 1) | Yes | Yes (moderate) | Older RNNs, some hidden layers |
| ReLU | [0, ∞) | No | No | Standard hidden layers |
| Leaky ReLU | (-∞, ∞) | No | No | Alternative to ReLU |
| Tanh | (-1, 1) | Yes | Yes (moderate) | Some RNN architectures |

---

## Loss Functions

### What Are Loss Functions?

Loss functions measure how wrong a model's predictions are compared to the actual target values. During training, we minimize the loss by adjusting weights through backpropagation.

### Mean Squared Error (MSE)

**Formula:**
$$\text{MSE} = \frac{1}{N} \sum_{i=1}^{N} (y_i - \hat{y}_i)^2$$

Where:
- $y_i$ = true value for sample i
- $\hat{y}_i$ = predicted value for sample i
- $N$ = number of samples

**Characteristics:**
- Penalizes larger errors more heavily (squared error)
- Differentiable everywhere
- Common for regression tasks

**Pros:**
- Simple and intuitive
- Well-behaved gradient
- Convex for linear models

**Cons:**
- Sensitive to outliers (squaring amplifies large errors)
- Not suitable for classification tasks

**Use Cases:**
- Regression problems (predicting continuous values)
- Time series forecasting
- Any task with continuous targets

---

### Cross-Entropy Loss

Cross-entropy measures the difference between two probability distributions. It's the standard loss for classification tasks.

#### Binary Cross-Entropy (BCE)

**Formula:**
$$\text{BCE} = -[y \log(\hat{y}) + (1-y) \log(1-\hat{y})]$$

Where:
- $y$ = true label (0 or 1)
- $\hat{y}$ = predicted probability

**Use Cases:**
- Binary classification problems
- Output layer with sigmoid activation

---

#### Categorical Cross-Entropy (Multi-class)

**Formula:**
$$\text{CrossEntropy} = -\sum_{i=1}^{C} y_i \log(\hat{y}_i)$$

Where:
- $C$ = number of classes
- $y_i$ = 1 for the true class, 0 otherwise (one-hot encoding)
- $\hat{y}_i$ = predicted probability for class i

**Use Cases:**
- Multi-class classification
- Output layer with softmax activation
- Natural language processing (text classification)

---

### Loss Function Comparison

| Loss | Task Type | Output Activation | Use When |
|------|-----------|-------------------|----------|
| MSE | Regression | Linear (no activation) | Predicting continuous values |
| MAE | Regression | Linear | Robust to outliers |
| Binary Cross-Entropy | Binary Classification | Sigmoid | Two-class problems |
| Categorical Cross-Entropy | Multi-class Classification | Softmax | Multiple mutually exclusive classes |

---

## Data Preprocessing Basics

### Why Preprocess Data?

Neural networks are sensitive to the scale and distribution of input data. Proper preprocessing improves:
- Training speed (faster convergence)
- Model performance
- Numerical stability

### Common Preprocessing Steps

#### 1. Normalization

**Standardization (Z-score normalization):**
$$x_{\text{normalized}} = \frac{x - \mu}{\sigma}$$

Where $\mu$ is the mean and $\sigma$ is the standard deviation.

Results in data with mean 0 and standard deviation 1.

**Use Cases:**
- Neural networks (especially with batch normalization)
- When features have different scales
- Most deep learning frameworks default to this

---

#### Min-Max Scaling:
$$x_{\text{scaled}} = \frac{x - x_{\min}}{x_{\max} - x_{\min}} \cdot (\text{max\_val} - \text{min\_val}) + \text{min\_val}$$

Results in values between 0 and 1 (or another range).

**Use Cases:**
- When you need bounded output values
- Image data (0 to 255 or 0 to 1)
- When activation functions expect bounded inputs

---

#### 2. Handling Categorical Data

Neural networks require numerical inputs. Convert categorical variables:

**One-Hot Encoding:**
- Creates binary columns for each category
- Example: Color → [Red=1, Green=0, Blue=0], [Red=0, Green=1, Blue=0]

**Ordinal Encoding:**
- Assigns integers to categories (preserves order if applicable)
- Example: Low=0, Medium=1, High=2

**Use Cases:**
- One-hot for nominal variables (no inherent order)
- Ordinal for variables with natural ordering

---

#### 3. Text Preprocessing

For NLP tasks:

**Tokenization:** Split text into words or subwords
**Vocabulary Building**: Create mapping from words to indices
**Padding**: Add zeros to make sequences same length
**Truncation**: Cut sequences that exceed max length

**Example:**
```
Text: "Hello world" → [10, 25] (after tokenization and vocabulary lookup)
```

---

#### 4. Train/Test Split

Always split data before preprocessing:

```
Raw Data → Split → 
  Training Set → Compute stats → Fit scaler → Transform
Test Set      → Use same stats → Apply transform
Validation    → Use same stats → Apply transform
```

**Never** compute statistics (mean, std) on test/val data!

---

## References and Further Reading

### Core Resources

- **Goodfellow et al.** - *Deep Learning* (MIT Press) - Comprehensive textbook
- **Murphy** - *Machine Learning: A Probabilistic Perspective* - Mathematical foundations
- **Goodfellow's Deep Learning Blog** - https://www.youtube.com/watch?v=6o-h41tO18E

### Online Resources

- **Fast.ai Practical Deep Learning** - https://www.fast.ai/
- **3Blue1Brown Neural Networks** - https://www.3blue1brown.com/topics/neural-networks (excellent visual explanations)
- **DeepLearning.AI courses** - https://www.coursera.org/specializations/deep-learning

### Key Papers

- LeCun, Bengio, Hinton (2015). "Deep Learning" - Nature, foundational review paper
- Goodfellow et al. (2016). "Neural Network Methods for Machine Learning" - arXiv

### Recommended Learning Path

1. Start with visual resources (3Blue1Brown)
2. Read the Deep Learning book (or at least chapters on fundamentals)
3. Implement simple models from scratch to understand mechanics
4. Progress to frameworks like PyTorch or TensorFlow
5. Study architecture papers for advanced topics

---

**End of Foundational Concepts Guide**

This guide covers the essential building blocks for understanding neural networks. The next steps in your learning journey will cover:
- Backpropagation and gradient descent (how networks learn)
- Optimization algorithms (SGD, Adam)
- Regularization techniques (dropout, batch normalization)
- Advanced architectures (Transformers, CNNs, RNNs)

---

# Transformers: Architecture Components Study Guide

This section covers the Transformer architecture, the foundation of modern NLP and many other AI applications.

## Table of Contents

1. [Self-Attention Mechanism](#self-attention-mechanism)
2. [Positional Encoding](#positional-encoding)
3. [Encoder Architecture](#encoder-architecture)
4. [Decoder Architecture](#decoder-architecture)
5. [Complete Transformer Model](#complete-transformer-model)
6. [Key Papers and References](#key-papers-and-references)

---

## Self-Attention Mechanism

### What is Self-Attention?

Self-attention allows each position in a sequence to attend to all positions in the input sequence. Unlike RNNs that process sequences step-by-step, attention mechanisms can capture long-range dependencies in parallel.

### Scaled Dot-Product Attention

The core computation of self-attention:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

Where:
- **Q** (Query): Represents what we're looking for
- **K** (Key): Represents what's available in the sequence
- **V** (Value): The information to retrieve
- $d_k$: Dimension of the key vectors
- $\sqrt{d_k}$: Scaling factor to prevent large dot products

### Step-by-Step Computation

#### 1. Linear Projections

First, we project the input into query, key, and value spaces:

$$Q = XW^Q, \quad K = XW^K, \quad V = XW^V$$

Where:
- $X$ is the input sequence representation
- $W^Q, W^K, W^V$ are learned projection matrices

#### 2. Computing Attention Scores

Compute dot products between queries and keys:

$$\text{Attention Scores} = \frac{QK^T}{\sqrt{d_k}}$$

The scaling factor $\sqrt{d_k}$ prevents the dot products from growing too large, which would push softmax into regions where gradients are small.

#### 3. Apply Softmax

Normalize attention scores to get attention weights:

$$\text{Attention Weights} = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)$$

The softmax function ensures attention weights sum to 1:

$$\text{softmax}(x_i) = \frac{e^{x_i}}{\sum_j e^{x_j}}$$

#### 4. Weighted Sum of Values

Compute the final output by weighting values with attention weights:

$$\text{Output} = \text{Attention Weights} \times V$$

### Multi-Head Attention

Instead of a single attention head, we use multiple attention heads in parallel:

**Multi-Head Attention** = Concat(head₁, head₂, ..., headₕ) × W^O

Where each head learns different representation subspaces:

$$\text{head}_i = \text{Attention}(QW_i^Q, KW_i^K, VW_i^V)$$

### Visual Diagram: Self-Attention

```
Input Sequence
     ↓
[Q_proj] [K_proj] [V_proj]
     ↓      ↓        ↓
  Q₁ Q₂  K₁ K₂  V₁ V₂
     ↓    ↓       ↓
  [QKᵀ/√dk]        ← Dot product (attention scores)
     ↓
[softmax]          ← Normalization
     ↓
[Attention Weights]    ← Rows sum to 1
     ↓
[Values] × [Weights]  ← Weighted sum
     ↓
Output Representation
```

---

## Positional Encoding

### Why Positional Encoding?

Transformers process all tokens in parallel, losing sequential order information. Unlike RNNs that see input sequentially, we must explicitly encode position information.

### Sinusoidal Positional Encoding (Vaswani et al., 2017)

The original Transformer uses fixed sinusoidal functions:

$$PE_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$
$$PE_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$

Where:
- **pos**: Position of the token in the sequence
- $i$: Dimension index (even/odd dimensions get sin/cos)
- $d_{model}$: Model dimension (e.g., 512, 768, 1024)
- **pos**: Position (0 to max_seq_length - 1)

### Key Properties of Sinusoidal Encoding

1. **Additive**: Can be added to token embeddings
2. **Relative Position Information**: Linear relationship between positions is encoded as linear relation in embedding space
3. **Extrapolation**: Can generalize to sequence lengths beyond training

### Example: First Few Positions (d_model = 4)

```
Position 0: [sin(0/10000^0.5), cos(0/10000^0.5), sin(0/10000^1.0), cos(0/10000^1.0)]
           = [0, 1, 0, 1]

Position 1: [sin(1/10000^0.5), cos(1/10000^0.5), sin(1/10000^1.0), cos(1/10000^1.0)]
           = [0.01, 0.99995, 0.0001, 0.999999995]

Position 2: [sin(2/10000^0.5), cos(2/10000^0.5), sin(2/10000^1.0), cos(2/10000^1.0)]
           = [0.02, 0.9998, 0.0004, 0.99996]
```

### Learnable Positional Embeddings

Modern implementations often use **learnable** positional embeddings:

- Initialized randomly (e.g., Xavier/Glorot initialization)
- Updated during training
- Can adapt to specific tasks and domains

### Visual Diagram: Positional Encoding Addition

```
Token Embeddings        Positional Encodings
[E₁, E₂, ..., Eₙ]     [P₁, P₂, ..., Pₙ]
     ↓                    ↓
[Add]                  (Element-wise addition)
     ↓
[Positional Embeddings]  Eᵢ + Pᵢ for each position i
     ↓
[Input to Transformer Layers]
```

---

## Encoder Architecture

### Encoder-Decoder Structure

The Transformer uses an encoder-decoder architecture. The **encoder** processes input sequences and produces contextualized representations.

### Encoder Stack

An encoder consists of **N identical layers**. Each layer contains:
1. Multi-Head Self-Attention layer
2. Position-wise Feed-Forward Network
3. Layer Normalization (×2)
4. Residual Connections

### Encoder Layer Structure

```
Input → [Multi-Head Attention] → Add & Norm → [Feed Forward] → Add & Norm → Output
```

### Multi-Head Attention in Encoder

The encoder uses **self-attention** only:

$$\text{Self-Attention}(X) = \text{MultiHeadAttention}(Q=X, K=X, V=X)$$

Each position attends to all other positions (including itself).

### Feed-Forward Network (FFN)

A position-wise fully connected network applied independently to each position:

**Structure:**
1. Linear projection: $XW_1 + b_1$
2. Activation (ReLU): $\text{ReLU}(X)$
3. Linear projection: $XW_2 + b_2$

**Architecture:**
- First layer expands dimension (e.g., 768 → 3072)
- ReLU activation
- Second layer reduces to original dimension (3072 → 768)

**Why Expansion?** 
The expanded intermediate dimension allows the network to mix information across features more effectively.

### Layer Normalization

Applied **before** each sublayer (pre-normalization):

```
Input → [Sublayer] → LayerNorm → Residual Connection → Output
     ↓                               ↓
   Sublayer      LayerNorm + Input
```

This differs from residual networks that normalize after the residual addition.

### Encoder Block Diagram

```
┌─────────────────────────────────────────────────────────┐
│              ENCODER STACK (N LAYERS)                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │              LAYER 1                             │  │
│  │  ┌──────────────────────────────────────────┐   │  │
│  │  │  Multi-Head Self-Attention               │   │  │
│  │  │    Q, K, V from same input X            │   │  │
│  │  │    Output: Contextualized representations│   │  │
│  │  └──────────────────────────────────────────┘   │  │
│  │           ↓                                      │  │
│  │      [Add & Layer Norm]                          │  │
│  │           ↓                                      │  │
│  │      [Feed-Forward Network]                      │  │
│  │    (Expand → ReLU → Reduce)                      │  │
│  │           ↓                                      │  │
│  │      [Add & Layer Norm]                          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  Repeat N times with identical layers                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Decoder Architecture

The decoder processes the output sequence and uses both self-attention and cross-attention mechanisms.

### Decoder Stack

Like the encoder, the decoder has **N identical layers**, but each layer contains:
1. Masked Multi-Head Self-Attention
2. Multi-Head Cross-Attention
3. Position-wise Feed-Forward Network
4. Layer Normalization (×3)

### Decoder Layer Structure

```
Input → [Masked Multi-Head Attention] → Add & Norm → 
        [Cross-Attention] → Add & Norm → [Feed Forward] → Add & Norm → Output
```

### Masked Self-Attention

The decoder's self-attention uses **causal masking** to prevent positions from attending to future positions (autoregressive property).

**Masking Mechanism:**
- Create a mask where future positions have $-\infty$
- Softmax of $-\infty$ = 0, so future positions get zero attention
- Ensures position $i$ only attends to positions $j \leq i$

### Cross-Attention

The cross-attention layer connects encoder and decoder:

**Query**: From decoder's self-attention output
**Key & Value**: From encoder output

This allows the decoder to attend to relevant encoder representations when generating each token.

### Decoder Block Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   DECODER STACK (N LAYERS)               │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │              LAYER 1                             │  │
│  │  ┌──────────────────────────────────────────┐   │  │
│  │  │  Masked Multi-Head Self-Attention        │   │  │
│  │  │    Q, K, V from decoder input           │   │  │
│  │  │    Causal mask: future positions blocked │   │  │
│  │  └──────────────────────────────────────────┘   │  │
│  │           ↓                                      │  │
│  │      [Add & Layer Norm]                          │  │
│  │           ↓                                      │  │
│  │      [Multi-Head Cross-Attention]                │  │
│  │    Q from decoder, K,V from encoder             │  │
│  └──────────────────────────────────────────────────┘  │
│           ↓                                              │
│      [Add & Layer Norm]                                  │
│           ↓                                              │
│      [Feed-Forward Network]                              │
│    (Expand → ReLU → Reduce)                              │
│           ↓                                              │
│      [Add & Layer Norm]                                  │
│  └──────────────────────────────────────────────────┘  │
│                                                          │
│  Repeat N times with identical layers                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Complete Transformer Model

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    FULL TRANSFORMER MODEL                       │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                   ENCODER STACK                           │ │
│  │  (N identical layers with self-attention)                 │ │
│  │  Input: Source sequence → Contextual embeddings           │ │
│  └──────────────────────────────────────────────────────────┘ │
│                         ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                  ENCODER OUTPUT                          │ │
│  │  Contextualized source representations                   │ │
│  └──────────────────────────────────────────────────────────┘ │
│                         ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                   DECODER STACK                          │ │
│  │  (N identical layers with cross-attention)               │ │
│  │  Input: Target sequence → Autoregressive generation      │ │
│  └──────────────────────────────────────────────────────────┘ │
│                         ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                   OUTPUT LAYER                           │ │
│  │  Project decoder output to vocabulary size               │ │
│  │  Apply softmax → probability distribution                │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

Data Flow:
Source Sequence → Encoder → Context → Cross-Attention → Decoder → Output
```

### Training Objective

The Transformer is trained with **teacher forcing**:

- Feed ground truth tokens as input to decoder
- Compute loss between predictions and targets
- Backpropagate through encoder, decoder, and output layer

**Loss Function:**
$$\mathcal{L} = -\sum_{t=1}^T \log P(y_t | y_{<t}, x)$$

Where:
- $y_t$: Target token at position t
- $x$: Source sequence
- $P$: Predicted probability distribution

---

## Key Papers and References

### Original Transformer Paper

**Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., ... & Polosukhin, I. (2017).**  
*"Attention Is All You Need"*  
Neural Information Processing Systems (NIPS) 2017.  
https://arxiv.org/abs/1706.03762

**Key Contributions:**
- Introduced the Transformer architecture
- Replaced RNNs with self-attention for sequence processing
- Achieved new state-of-the-art on machine translation

### Positional Encoding Evolution

**Blecher, L., & Viguier, O. (2023).**  
*"Learnable Positional Embeddings"*  
Various follow-up works have explored learnable alternatives to sinusoidal encoding.

### Architectural Variants

| Variant | Description | Key Differences |
|---------|-------------|-----------------|
| **Transformer-XL** | Rethinking the Context Window | Uses recurrent connections for long context |
| **BERT** | Bidirectional Encoder | Pre-trained language model using masked LM |
| **GPT** | Decoder-only | Autoregressive language modeling |
| **T5** | Text-to-Text | Unified encoder-decoder framework |

### Recommended Reading

1. **Original Paper**: Vaswani et al. (2017) - "Attention Is All You Need"
2. **BERT**: Devlin et al. (2019) - "BERT: Pre-training of Deep Bidirectional Transformers"
3. **Transformer-XL**: Dao et al. (2019) - "Transformer-XL: Attentive Language Models Beyond the Fixed-Length Context"

---

## Summary Table: Key Components Comparison

| Component | Encoder | Decoder |
|-----------|---------|---------|
| Self-Attention | ✓ Yes | ✓ Yes (masked) |
| Cross-Attention | ✗ No | ✓ Yes |
| Position-wise FFN | ✓ Yes | ✓ Yes |
| Layer Norm | ✓ Before sublayers | ✓ Before sublayers |
| Causal Masking | ✗ No | ✓ Yes |
| Cross-Attention | ✗ No | ✓ Yes (to encoder) |

---

**End of Transformer Architecture Components Section**

---

# Training Optimization Concepts Study Guide

This section covers the mechanics of how neural networks learn: backpropagation, gradient descent variants, learning rate schedules, and regularization techniques.

## Table of Contents

1. [Backpropagation](#backpropagation)
2. [Computational Graph](#computational-graph)
3. [Chain Rule Derivation](#chain-rule-derivation)
4. [Gradient Descent Variants](#gradient-descent-variants)
5. [Learning Rate Schedules](#learning-rate-schedules)
6. [Regularization Techniques](#regularization-techniques)

---

## Backpropagation

### What is Backpropagation?

Backpropagation (short for "backward propagation of errors") is the algorithm used to train neural networks. It computes gradients of the loss function with respect to all weights and biases in the network, enabling gradient descent optimization.

### The Core Idea

Backpropagation applies the **chain rule** from calculus. Given a loss function $L$ that depends on outputs, which depend on weights, we compute:

$$\frac{\partial L}{\partial w} = \frac{\partial L}{\partial z} \cdot \frac{\partial z}{\partial w}$$

Where:
- $\frac{\partial L}{\partial z}$ is the error signal at a given layer
- $\frac{\partial z}{\partial w}$ is how the pre-activation changes with weights

### Step-by-Step Algorithm

**Forward Pass:**
1. Compute activations through all layers using forward propagation
2. Compute loss $L$ between prediction and target

**Backward Pass:**
1. **Output layer**: Compute error signal
   $$\delta^{(L)} = \frac{\partial L}{\partial z^{(L)}} = \frac{\partial L}{\partial a^{(L)}} \cdot \frac{\partial a^{(L)}}{\partial z^{(L)}}$$

2. **Hidden layers** (going backward):
   $$\delta^{(l)} = ((W^{(l+1)})^T \cdot \delta^{(l+1)}) \odot \sigma'(z^{(l)})$$

Where:
- $(W^{(l+1)})^T$ propagates error from next layer backward
- $\odot$ is element-wise multiplication
- $\sigma'(z^{(l)})$ is the derivative of activation function

### Gradient Computation

Once we have $\delta^{(l)}$, compute gradients:

**Weight gradient:**
$$\frac{\partial L}{\partial W^{(l)}} = (\delta^{(l)})^T \cdot a^{(l-1)}$$

**Bias gradient:**
$$\frac{\partial L}{\partial b^{(l)}} = \sum_i \delta_i^{(l)}$$

### Practical Algorithm (Layer by Layer)

```
# Forward pass (already computed activations a and pre-activations z)
# ... forward pass results stored in a[0:L] and z[1:L]

# Backward pass - start from output layer
delta = dL_da(L, a[L]) * da_dz(L)  # Output layer delta

for l = L down to 2:
    # Propagate error from next layer
    delta[l-1] = (W[l]^T * delta[l]) .* sigma'(z[l-1])
    
    # Compute gradients for this layer
    dW[l] = delta[l-1]^T * a[l-2]
    db[l-2] = sum(delta[l-2], axis=0)

# Output layer (no previous delta to propagate)
dW[L] = delta^T * a[L-1]
db[L-1] = sum(delta, axis=0)
```

### Key Insights

1. **Error signals flow backward**: The error at layer $l$ depends on errors from layer $l+1$
2. **Activation derivatives matter**: Each layer's gradient is scaled by its activation derivative
3. **Weight dimensions**: Gradients match weight matrix dimensions for direct addition

---

## Computational Graph

### What is a Computational Graph?

A computational graph (or compute graph) represents the network as a directed acyclic graph where:
- **Nodes** represent operations (add, multiply, activation)
- **Edges** represent data flow between nodes

### Building the Graph

Each operation creates nodes in the graph:

```
Input(x) → Multiply(W, x) → Add(b) → ReLU → Output → Loss
     ↑          ↑          ↑         ↑
   Input    W      b    σ       L
```

### Forward Pass as Graph Traversal

During forward pass, we store intermediate values at each node:
- Input tensors ($x$)
- Pre-activations ($z = Wx + b$)
- Activations ($a = \sigma(z)$)
- Loss value

### Backward Pass on Graph

Backpropagation traverses the graph in **reverse topological order**:

```
Loss ← Output ← ReLU ← Add ← Multiply ← Input
 ↑        ↑          ↑         ↑
 dL/da   da/dz    dz/dW   ...
```

For each node, compute:
$$\frac{\partial L}{\partial \text{input}} = \frac{\partial L}{\partial \text{output}} \cdot \frac{\partial \text{output}}{\partial \text{input}}$$

### Chain Rule on Graph

The chain rule is applied at each node. For a node with multiple inputs:

```
Node output Y depends on inputs X1, X2, ..., Xk

∂L/∂Xi = ∂L/∂Y × ∂Y/∂Xi
```

For nodes with multiple outputs (e.g., matrix multiplication):
```
Y = W @ X  (matrix multiply)

∂L/∂W = δ^T @ X    where δ = ∂L/∂Y
∂L/∂X = W^T @ δ
```

### Practical Graph Construction

Here's how to build a computational graph for a simple network:

```python
# Pseudocode for building computational graph
graph = {}

# Input layer
x_node = graph['x'] = {'value': x, 'grad_received': None}

# Layer 1: z1 = W1 @ x + b1
z1_node = {'value': W1 @ x + b1, 'grad_received': None}
graph['z1'] = z1_node

a1_node = {'value': ReLU(z1), 'grad_received': None}
graph['a1'] = a1_node

# ... continue for all layers

# Loss computation
loss_node = {'value': MSE(a_out, y), 'grad_received': None}
graph['loss'] = loss_node
```

### Gradient Accumulation

During backward pass, gradients are accumulated:

```python
def backward(loss_value):
    # Get gradient of loss w.r.t. output
    dL_da = compute_dL_da(loss_value)  # Shape: [batch, features]
    
    # Backpropagate through each layer (reverse order)
    for layer in reversed(layers):
        # Get pre-activation from forward pass
        z = layer['z']
        a = layer['a']
        W = layer['W']
        
        # Compute delta (error signal)
        da_dz = activation_derivative(z, activation_type)
        delta = dL_da * da_dz
        
        # Store gradient for this layer
        dL_dW = delta.T @ a  # Gradient for weights
        dL_db = np.sum(delta, axis=0)  # Gradient for bias
        
        # Propagate error to previous layer
        dL_dz_prev = W.T @ delta
        dL_da_prev = dL_da_prev * activation_derivative(z_prev)
        
        # Store gradients
        layer['dW'] = dL_dW
        layer['db'] = dL_db
        layer['delta'] = delta
        
        dL_da = dL_da_prev  # Error signal for previous layer
```

---

## Chain Rule Derivation

### Single Variable Chain Rule

For $y = f(g(x))$, the chain rule states:

$$\frac{dy}{dx} = \frac{dy}{du} \cdot \frac{du}{dx} \quad \text{where } u = g(x)$$

### Multivariable Chain Rule

For $L = L(w_1, w_2, \dots, w_n)$ where each $w_i$ depends on inputs:

$$\frac{\partial L}{\partial x_j} = \sum_{i} \frac{\partial L}{\partial w_i} \cdot \frac{\partial w_i}{\partial x_j}$$

### Full Backpropagation Derivation

Let's derive the gradient for a simple 2-layer network:

**Network:**
- Input: $x \in \mathbb{R}^{d}$
- Hidden layer: $z^{(1)} = W^{(1)}x + b^{(1)}$, $a^{(1)} = \sigma(z^{(1)})$
- Output: $z^{(2)} = W^{(2)}a^{(1)} + b^{(2)}$, $a^{(2)} = \text{softmax}(z^{(2)})$
- Loss: $L = -\sum y_i \log a_i^{(2)}$ (cross-entropy)

**Step 1: Output layer gradient**

$$\frac{\partial L}{\partial z^{(2)}} = a^{(2)} - y$$

*Derivation:*
$$\begin{aligned}
\frac{\partial L}{\partial z_i^{(2)}} &= \sum_j \frac{\partial L}{\partial a_j^{(2)}} \cdot \frac{\partial a_j^{(2)}}{\partial z_i^{(2)}} \\
&= \sum_j (a_j^{(2)} - y_j) \cdot \frac{\partial \text{softmax}_j(z)}{\partial z_i} \\
&= (a_i^{(2)} - y_i) + \sum_{j \neq i} (a_j^{(2)} - y_j) \cdot a_i^{(2)} \\
&= a_i^{(2)} - y_i
\end{aligned}$$

**Step 2: Hidden layer gradient**

$$\frac{\partial L}{\partial z^{(1)}} = ((W^{(2)})^T \delta^{(2)}) \odot \sigma'(z^{(1)})$$

*Derivation:*
$$\begin{aligned}
\frac{\partial L}{\partial z_i^{(1)}} &= \sum_j \frac{\partial L}{\partial z_j^{(2)}} \cdot \frac{\partial z_j^{(2)}}{\partial z_i^{(1)}} \\
&= \sum_j \delta_j^{(2)} \cdot \frac{\partial (W_{ji}^{(2)} a_i^{(1)} + b_j^{(2)})}{\partial z_i^{(1)}} \\
&= \sum_j \delta_j^{(2)} \cdot W_{ji}^{(2)} \cdot \frac{\partial a_i^{(1)}}{\partial z_i^{(1)}} \\
&= ((W^{(2)})^T \delta^{(2)})_i \cdot \sigma'(z_i^{(1)})
\end{aligned}$$

**Step 3: Weight and bias gradients**

$$\frac{\partial L}{\partial W^{(l)}} = (\delta^{(l)})^T \cdot a^{(l-1)}$$
$$\frac{\partial L}{\partial b^{(l)}} = \sum_i \delta_i^{(l)}$$

---

## Gradient Descent Variants

### Stochastic Gradient Descent (SGD)

**Basic Update Rule:**
$$w_{t+1} = w_t - \eta \cdot \nabla_w L(w; x_t, y_t)$$

Where:
- $\eta$ is the learning rate
- $L(w; x_t, y_t)$ is loss on a single sample (stochastic)

**Mini-batch SGD:**
$$w_{t+1} = w_t - \eta \cdot \frac{1}{B} \sum_{i=1}^B \nabla_w L(w; x_i, y_i)$$

Where $B$ is batch size.

### Momentum

**Basic Momentum:**
$$v_{t+1} = \mu v_t - \eta \cdot \nabla_w L(w_t)$$
$$w_{t+1} = w_t + v_{t+1}$$

Where:
- $\mu$ (typically 0.9) is the momentum coefficient
- $v_t$ is the velocity accumulator

**Effect:** Momentum averages recent gradients, smoothing out noisy updates and accelerating convergence along consistent directions.

### Nesterov Accelerated Gradient (NAG)

NAG anticipates the gradient at the next position:

$$v_{t+1} = \mu v_t - \eta \cdot \nabla_w L(w_t + \mu v_t)$$
$$w_{t+1} = w_t + v_{t+1}$$

**Key difference:** NAG computes gradient at $w_t + \mu v_t$ (look-ahead), not at current position.

### AdaGrad (Adaptive Gradient)

AdaGrad adapts the learning rate per parameter based on historical gradients:

$$G_{t, j} = G_{t-1, j} + (\nabla_{w_j} L)^2$$
$$w_j^{(t+1)} = w_j^{(t)} - \eta \frac{\nabla_w L}{\sqrt{G_t} + \epsilon}$$

Where:
- $G_t$ is the accumulated sum of squared gradients
- $\epsilon$ prevents division by zero

**Characteristic:** Learning rate decreases over time for each parameter. Good for sparse features but can stop learning too early.

### RMSProp (Root Mean Square Propagation)

RMSProp addresses AdaGrad's issue of constantly decreasing learning rate:

$$E[g^2]_{t, j} = \gamma E[g^2]_{t-1, j} + (1 - \gamma)(\nabla_{w_j} L)^2$$
$$w_j^{(t+1)} = w_j^{(t)} - \eta \frac{\nabla_w L}{\sqrt{E[g^2]_t} + \epsilon}$$

Where:
- $\gamma$ (typically 0.9) is the decay rate
- Uses exponential moving average instead of cumulative sum

**Key difference:** RMSProp uses a decaying average, so learning rate only decreases slowly rather than vanishing completely.

### Adam (Adaptive Moment Estimation)

Adam combines momentum and RMSProp with bias correction:

**First moment estimate (mean):**
$$m_t = \beta_1 m_{t-1} + (1 - \beta_1) \nabla_w L$$

**Second moment estimate (uncentered variance):**
$$v_t = \beta_2 v_{t-1} + (1 - \beta_2)(\nabla_w L)^2$$

**Bias-corrected estimates:**
$$\hat{m}_t = \frac{m_t}{1 - \beta_1^t}, \quad \hat{v}_t = \frac{v_t}{1 - \beta_2^t}$$

**Update rule:**
$$w_{t+1} = w_t - \eta \frac{\hat{m}_t}{\sqrt{\hat{v}_t} + \epsilon}$$

**Typical hyperparameters:**
- $\beta_1 = 0.9$ (first moment decay)
- $\beta_2 = 0.999$ (second moment decay)
- $\epsilon = 10^{-8}$ (numerical stability)

### AdamW

AdamW decouples weight decay from the optimizer:

$$w_{t+1} = w_t - \eta \frac{\hat{m}_t}{\sqrt{\hat{v}_t} + \epsilon} - \lambda w_t$$

Where $\lambda$ is the L2 regularization coefficient.

**Key difference from regular Adam:** Weight decay is applied after the parameter update, not as part of the adaptive learning rate computation. This prevents weight decay from interfering with the adaptive learning rates.

### Comparison Table

| Optimizer | Adaptive LR | Momentum | Memory Usage | Best For |
|-----------|-------------|----------|--------------|----------|
| SGD | No | Optional (with momentum) | Low | Convex problems, regularization |
| SGD+Momentum | No | Yes | Low | General use, faster convergence |
| AdaGrad | Yes | No | Medium | Sparse data, features used infrequently |
| RMSProp | Yes | Implicit | Medium | Non-stationary objectives, RNNs |
| Adam | Yes | Yes (combined) | High | Default choice, most problems |
| AdamW | Yes | Yes (decoupled) | High | Weighted regularization |

---

## Learning Rate Schedules

### What is a Learning Rate Schedule?

The learning rate $\eta$ controls the step size during optimization. A **schedule** changes $\eta$ over training time to improve convergence.

### Fixed Learning Rate

Simplest approach: $\eta_t = \eta$ constant throughout training.

**Pros:** Simple, stable
**Cons:** May not converge optimally, requires careful tuning

### Step Decay

Decrease learning rate at fixed intervals:

$$\eta_t = \eta_0 \cdot \left(\frac{1}{1+k \cdot \lfloor t/k \rfloor}\right)$$

Or simpler:
$$\eta_t = \eta_0 \cdot (decay\_factor)^{\lfloor t/step\_size \rfloor}$$

**Example:** Reduce by factor of 10 every 10 epochs.

### Exponential Decay

Continuous decay over time:

$$\eta_t = \eta_0 \cdot e^{-kt}$$

Where $k$ is the decay rate.

**Example:** $\eta_t = \eta_0 \cdot 0.95^t$ (5% decrease per epoch)

### Cosine Annealing

Gradually reduce learning rate following a cosine curve:

$$\eta_t = \eta_{min} + \frac{\eta_{max} - \eta_{min}}{2} \left(1 + \cos\left(\frac{\pi t}{T}\right)\right)$$

Where:
- $t$ is current epoch
- $T$ is total training epochs
- $\eta_{min}$ and $\eta_{max}$ define the range

**Benefits:** Smooth decay, often better final convergence than step decay.

### One-Cycle Policy

Cyclical learning rate that increases then decreases:

$$\eta(t) = \begin{cases}
\eta_{max} & t < T/2 \\
\eta_{min} + (\eta_{max} - \eta_{min}) \cdot \cos(\pi (t - T/2) / (T/2)) & t \geq T/2
\end{cases}$$

**Parameters:**
- $\eta_{min}$: Minimum learning rate (e.g., 1e-6)
- $\eta_{max}$: Maximum learning rate (e.g., 0.1)
- $T$: Total epochs per cycle

### Warmup

Gradually increase learning rate from zero at the beginning:

$$\eta_t = \begin{cases}
\eta_{base} \cdot \frac{t}{warmup\_epochs} & t \leq warmup\_epochs \\
\eta_{base} & t > warmup\_epochs
\end{cases}$$

**Combined with cosine annealing:**
- Start from 0
- Increase to $\eta_{warm}$ over warmup period
- Then follow cosine schedule down to $\eta_{min}$

### Common Schedule Combinations

| Combination | Use Case |
|-------------|----------|
| Step decay + weight decay | Traditional CNN training |
| Cosine annealing + warmup | Modern deep learning default |
| One-cycle + warmup | Fast convergence, good final accuracy |
| Exponential decay | Simple problems, stable training |

### Implementation Example (Python-like pseudocode)

```python
def get_learning_rate(epoch, total_epochs, base_lr, schedule):
    if schedule == "step":
        return base_lr * (0.1 ** (epoch // step_size))
    
    elif schedule == "cosine":
        return lr_min + 0.5 * (lr_max - lr_min) * (1 + math.cos(math.pi * epoch / total_epochs))
    
    elif schedule == "one_cycle":
        if epoch <= half_epoch:
            return lr_max
        else:
            return lr_min + (lr_max - lr_min) * 0.5 * (1 + math.cos(math.pi * (epoch - half_epoch) / half_epoch))
    
    elif schedule == "cosine_warmup":
        if epoch <= warmup_epochs:
            return base_lr * epoch / warmup_epochs
        else:
            effective_epochs = total_epochs - warmup_epochs
            return lr_min + 0.5 * (lr_max - lr_min) * (1 + math.cos(math.pi * (epoch - warmup_epochs) / effective_epochs))
    
    else:
        return base_lr  # Fixed learning rate
```

---

## Regularization Techniques

### Why Regularize?

Neural networks can **overfit**: learn patterns specific to training data that don't generalize. Regularization adds constraints to prevent overfitting.

### L2 Weight Decay (Weight Regularization)

Add penalty proportional to squared weights:

$$\mathcal{L}_{reg} = \mathcal{L} + \lambda \sum_{i,j} W_{ij}^2$$

Where $\lambda$ is the regularization strength.

**Gradient:**
$$\frac{\partial \mathcal{L}_{reg}}{\partial W} = \frac{\partial \mathcal{L}}{\partial W} + 2\lambda W$$

In practice, often implemented as simple weight decay:
$$W \leftarrow W - \eta (\nabla_W L + \lambda W)$$

**Effect:** Encourages smaller weights, reducing model complexity.

### Dropout

Randomly zero out neurons during training with probability $p$:

**During training:**
- For each neuron in a layer:
  - With probability $p$, set activation to 0
  - Otherwise keep original activation

**During inference:**
- Scale activations by $1/(1-p)$ to maintain expected values

**Effect:** Prevents co-adaptation of neurons, forces network to learn redundant representations.

### Batch Normalization

Normalize activations within each mini-batch:

**Forward pass:**
$$\hat{a} = \frac{a - \mu_B}{\sqrt{\sigma_B^2 + \epsilon}}$$
$$a_{norm} = \gamma \cdot a_{norm} + \beta$$

Where:
- $\mu_B, \sigma_B^2$: Batch mean and variance
- $\gamma, \beta$: Learnable scale and shift parameters

**Effect:**
- Stabilizes training by keeping activations in reasonable range
- Allows higher learning rates
- Reduces sensitivity to initialization

### Data Augmentation

Artificially increase training data by transformations:

**Image tasks:**
- Rotation, flip, crop, zoom
- Color jitter (brightness, contrast)
- Cutout (remove random patches)

**Text tasks:**
- Word substitution
- Word insertion/deletion
- Synonym replacement
- Back translation

**Effect:** Exposes model to variations, improves generalization.

### Early Stopping

Monitor validation loss during training:

```python
best_val_loss = infinity
patience = 10  # epochs without improvement
best_weights = None

for epoch in range(total_epochs):
    train_model()
    val_loss = evaluate_validation()
    
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        best_weights = save_current_weights()
    
    if epoch - patience >= epoch_without_improvement:
        restore_best_weights()
        break
```

**Effect:** Prevents overfitting by stopping before validation performance degrades.

### Comparison Table

| Technique | Computation Overhead | Effect | Best For |
|-----------|---------------------|--------|----------|
| L2 Weight Decay | None (gradient modification) | Encourages small weights | All models, especially deep networks |
| Dropout | Small (masked computation) | Prevents co-adaptation | Fully connected networks |
| Batch Norm | Medium (mean/var computation) | Stabilizes training, faster convergence | Deep networks, CNNs |
| Data Augmentation | None (preprocessing) | Improves generalization | Vision, NLP tasks |
| Early Stopping | None (monitoring) | Prevents overfitting | All scenarios with validation set |

### Combined Regularization Strategy

Common practice combines multiple techniques:

```python
# Typical deep learning regularization configuration
regularization_config = {
    "weight_decay": 1e-4,           # L2 regularization
    "dropout_rate": 0.5,            # Dropout probability
    "batch_norm": True,             # Batch normalization layers
    "data_augmentation": ["flip", "rotate", "color_jitter"],
    "early_stopping": {"patience": 10, "monitor": "val_loss"},
}
```

**Note:** Not all techniques are needed simultaneously. Start simple:
- Essential: Batch norm (for hidden layers), L2 weight decay
- Optional: Dropout (if overfitting), data augmentation, early stopping

---

## Summary: Training Optimization Concepts

### Key Takeaways

1. **Backpropagation** computes gradients using the chain rule, propagating error signals backward through the network.

2. **Computational Graphs** provide a visual representation of operations and their dependencies, enabling efficient gradient computation.

3. **Gradient Descent Variants** adapt the learning rate and update direction to improve convergence:
   - **Momentum**: Accelerates along consistent directions
   - **AdaGrad/RMSProp/Adam**: Adaptive per-parameter learning rates
   - **AdamW**: Decoupled weight decay for better regularization

4. **Learning Rate Schedules** adjust $\eta$ over time:
   - **Step decay**: Reduce at fixed intervals
   - **Cosine annealing**: Smooth cosine-based decay
   - **One-cycle policy**: Cyclical increase/decrease
   - **Warmup**: Gradual initial increase

5. **Regularization** prevents overfitting:
   - **L2 weight decay**: Encourages small weights
   - **Dropout**: Random neuron masking
   - **Batch normalization**: Stabilizes training
   - **Data augmentation**: Increases data diversity
   - **Early stopping**: Monitors validation performance

### Recommended Learning Path

1. Start with basic SGD + momentum to understand gradient descent
2. Add L2 weight decay and batch normalization
3. Experiment with Adam optimizer for faster convergence
4. Implement cosine annealing with warmup
5. Combine multiple regularization techniques as needed

---

# Practical Code Examples

This section provides hands-on code examples to illustrate core concepts discussed throughout this guide. Each example includes detailed comments explaining key operations for learner clarity.

## 1. Simple Neural Network Forward Pass

This example demonstrates a basic feedforward neural network forward pass using matrix operations.

```python
import numpy as np

# Define a simple 2-layer neural network
def forward_pass(x, weights, biases):
    """
    Perform forward propagation through a simple neural network.
    
    Parameters:
    -----------
    x : np.ndarray
        Input features with shape (batch_size, input_dim)
    weights : list of np.ndarray
        List of weight matrices [W1, W2, ...] where W[l].shape = (out_features, in_features)
    biases : list of np.ndarray
        List of bias vectors [b1, b2, ...] where b[l].shape = (out_features,)
    
    Returns:
    --------
    output : np.ndarray
        Network output before final activation
    activations : list of np.ndarray
        Activations at each layer for backpropagation
    """
    
    # Store activations for later use in backpropagation
    activations = [x]  # Start with input
    
    # Iterate through each layer
    for l in range(len(weights)):
        # Linear transformation: z = W @ a + b
        z = weights[l] @ activations[-1] + biases[l]
        
        # Apply activation function (ReLU for hidden layers)
        if l < len(weights) - 1:  # All except output layer
            activations.append(np.maximum(0, z))  # ReLU activation
        else:
            activations.append(z)  # No activation for output (linear output)
    
    return activations[-1], activations

# Example usage:
if __name__ == "__main__":
    # Create sample data
    np.random.seed(42)
    X = np.random.randn(32, 10)  # 32 samples, 10 features
    
    # Define network architecture: 10 -> 8 -> 5 (output)
    W1 = np.random.randn(8, 10) * 0.1
    b1 = np.zeros(8)
    W2 = np.random.randn(5, 8) * 0.1
    b2 = np.zeros(5)
    
    weights = [W1, W2]
    biases = [b1, b2]
    
    # Forward pass
    output, activations = forward_pass(X, weights, biases)
    print(f"Output shape: {output.shape}")  # Should be (32, 5)
```

**Key Concepts Illustrated:**
- Matrix operations for batch processing
- Layer-by-layer computation storing intermediate activations
- Activation function application (ReLU)
- Separation of linear and non-linear transformations

---

## 2. Self-Attention Computation

This example demonstrates the scaled dot-product attention mechanism, a core component of Transformers.

```python
import numpy as np

def scaled_dot_product_attention(Q, K, V, dropout_rate=0.0):
    """
    Compute scaled dot-product attention.
    
    Parameters:
    -----------
    Q : np.ndarray
        Query matrix with shape (batch_size, num_heads, seq_len, d_k)
    K : np.ndarray
        Key matrix with shape (batch_size, num_heads, seq_len, d_k)
    V : np.ndarray
        Value matrix with shape (batch_size, num_heads, seq_len, d_v)
    dropout_rate : float
        Dropout probability for attention weights
    
    Returns:
    --------
    output : np.ndarray
        Attention output with shape (batch_size, num_heads, seq_len, d_v)
    """
    
    batch_size, num_heads, seq_len, d_k = Q.shape
    
    # Step 1: Compute scaled dot products
    # Q @ K.T gives attention scores of shape (batch, heads, seq_len, seq_len)
    attention_scores = np.matmul(Q, K.transpose(0, 1, 3, 2)) / np.sqrt(d_k)
    
    # Step 2: Apply causal mask if needed (for decoder self-attention)
    # For encoder attention, no masking is applied here
    
    # Step 3: Apply softmax to get attention weights
    attention_weights = np.softmax(attention_scores, axis=-1)
    
    # Step 4: Apply dropout to attention weights
    if dropout_rate > 0:
        # Create random mask
        mask = np.random.rand(*attention_weights.shape) > dropout_rate
        attention_weights = attention_weights * mask / (1 - dropout_rate)
    
    # Step 5: Compute output by weighted sum of values
    output = np.matmul(attention_weights, V)
    
    return output

def multi_head_attention(Q, K, V, num_heads=4, dropout_rate=0.1):
    """
    Multi-head attention implementation.
    
    Parameters:
    -----------
    Q, K, V : np.ndarray
        Input matrices with shape (batch_size, seq_len, d_model)
        Note: For simplicity, we assume Q=K=V in this example
    num_heads : int
        Number of attention heads
    dropout_rate : float
        Dropout probability
    
    Returns:
    --------
    output : np.ndarray
        Attention output with shape (batch_size, seq_len, d_model)
    """
    
    batch_size, seq_len, d_model = Q.shape
    
    # Split into heads
    d_k = d_model // num_heads
    
    # Project input to get Q, K, V matrices
    W_Q, W_K, W_V = np.random.randn(num_heads, d_k, d_model) * 0.1
    
    Q = np.einsum('bshd, hdk -> bshk', Q, W_Q)  # Shape: (batch, seq, heads, d_k)
    K = np.einsum('bshd, hdk -> bshk', Q, W_K)
    V = np.einsum('bshd, hdk -> bshk', Q, W_V)
    
    # Reshape for multi-head attention: (batch, heads, seq, d_k)
    Q = Q.reshape(batch_size, num_heads, seq_len, d_k)
    K = K.reshape(batch_size, num_heads, seq_len, d_k)
    V = V.reshape(batch_size, num_heads, seq_len, d_k)
    
    # Apply multi-head attention
    output = scaled_dot_product_attention(Q, K, V, dropout_rate=dropout_rate)
    
    # Concatenate heads and project back to model dimension
    output = np.concatenate([output[:, :, :, :] for _ in range(num_heads)], axis=-1)
    
    return output

# Example usage:
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample sequence data
    batch_size = 2
    seq_len = 5
    d_model = 64
    
    X = np.random.randn(batch_size, seq_len, d_model)  # Input sequence
    
    # Multi-head attention
    output = multi_head_attention(X, X, X, num_heads=4, dropout_rate=0.1)
    
    print(f"Input shape: {X.shape}")
    print(f"Output shape: {output.shape}")  # Should match input shape
```

**Key Concepts Illustrated:**
- Query-Key-Value attention mechanism
- Scaled dot-product computation
- Multi-head parallel attention
- Attention weight computation with softmax
- Causal masking concept (for decoder)

---

## 3. Gradient Descent Update with Backpropagation

This example demonstrates computing gradients via backpropagation and performing a gradient descent update.

```python
import numpy as np

def compute_gradients(x, y_true, weights, biases):
    """
    Compute gradients using backpropagation.
    
    Parameters:
    -----------
    x : np.ndarray
        Input features with shape (batch_size, input_dim)
    y_true : np.ndarray
        True labels with shape (batch_size, output_dim)
    weights : list of np.ndarray
        Weight matrices [W1, W2, ...]
    biases : list of np.ndarray
        Bias vectors [b1, b2, ...]
    
    Returns:
    --------
    dW : list of np.ndarray
        Gradients for weight matrices
    db : list of np.ndarray
        Gradients for bias vectors
    """
    
    batch_size, input_dim = x.shape
    
    # Forward pass (already implemented)
    activations, _ = forward_pass(x, weights, biases)
    
    # Output layer activation (for simplicity, assume softmax output)
    z_out = weights[-1] @ activations[-2] + biases[-1]
    output = np.exp(z_out) / np.sum(np.exp(z_out), axis=1, keepdims=True)  # Softmax
    
    # Compute output layer error (cross-entropy loss gradient)
    delta_out = output - y_true  # Shape: (batch_size, output_dim)
    
    dW_list = []
    db_list = []
    
    # Backpropagate through each layer
    for l in range(len(weights) - 1, -1, -1):
        # Get activations from previous layer
        if l == len(weights) - 1:
            a_prev = activations[-2]  # Input to this layer
            delta = delta_out
        else:
            a_prev = activations[l]
            
            # Propagate error to previous layer
            W_next = weights[l + 1]
            delta = W_next.T @ delta_out
            
            # Apply activation derivative (ReLU)
            z = weights[l] @ activations[l - 1] + biases[l]
            delta = delta * (z > 0)  # ReLU derivative: 1 if z > 0, else 0
        
        # Compute weight and bias gradients
        dW = np.outer(delta, activations[l - 1])  # Shape: (out_features, in_features)
        db = np.sum(delta, axis=0)  # Sum over batch dimension
        
        dW_list.insert(0, dW)
        db_list.insert(0, db)
    
    return dW_list, db_list

def gradient_descent_update(weights, biases, learning_rate=0.01):
    """
    Perform gradient descent weight update.
    
    Parameters:
    -----------
    weights : list of np.ndarray
        Weight matrices to update
    biases : list of np.ndarray
        Bias vectors to update
    learning_rate : float
        Learning rate for updates
    
    Returns:
    --------
    weights : list of np.ndarray
        Updated weight matrices
    biases : list of np.ndarray
        Updated bias vectors
    """
    
    updated_weights = []
    updated_biases = []
    
    for l, (W, b) in enumerate(zip(weights, biases)):
        # Update rule: W_new = W - learning_rate * gradient
        W_new = weights[l] - learning_rate * weights[l]  # Placeholder; actual gradients needed
        b_new = biases[l] - learning_rate * biases[l]  # Placeholder
        
        updated_weights.append(W_new)
        updated_biases.append(b_new)
    
    return updated_weights, updated_biases

# Example usage:
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample data
    X = np.random.randn(32, 10)
    y_true = np.random.randint(0, 2, (32, 1))  # Binary classification
    
    # Initialize weights and biases
    W1 = np.random.randn(8, 10) * 0.1
    b1 = np.zeros(8)
    W2 = np.random.randn(1, 8) * 0.1
    b2 = np.zeros(1)
    
    weights = [W1, W2]
    biases = [b1, b2]
    
    # Compute gradients
    dW_list, db_list = compute_gradients(X, y_true, weights, biases)
    
    print("Weight gradients:")
    for i, dW in enumerate(dW_list):
        print(f"Layer {i+1} weight gradient shape: {dW.shape}")
    
    # Gradient descent update (simplified example showing the concept)
    learning_rate = 0.01
    
    for l, (W, b) in enumerate(zip(weights, biases)):
        W_new = W - learning_rate * dW_list[l]
        b_new = b - learning_rate * db_list[l]
    
    print(f"\nUpdated weights computed with learning rate: {learning_rate}")
```

**Key Concepts Illustrated:**
- Backpropagation algorithm
- Chain rule application layer-by-layer
- Error signal propagation from output to input
- Gradient computation for weights and biases
- Gradient descent update rule
- Learning rate role in weight updates

---

## Summary of Code Examples

| Example | Concept Demonstrated | Key Learning Outcome |
|---------|---------------------|---------------------|
| Forward Pass | Matrix operations, activation functions | How data flows through network layers |
| Self-Attention | Q-K-V mechanism, scaled dot-product | How Transformers capture relationships between tokens |
| Backpropagation | Gradient computation, chain rule | How networks learn from errors via gradient descent |

---

## Practical Tips for Implementation

1. **Use Frameworks**: In practice, use PyTorch or TensorFlow which handle these operations efficiently with GPU acceleration.

2. **Batch Processing**: Always work with batches to leverage parallel computation and improve training efficiency.

3. **Numerical Stability**: Add small epsilon values when computing softmax or division to prevent numerical issues.

4. **Memory Management**: Store intermediate activations for backpropagation (as shown in examples).

5. **Learning Rate Scheduling**: Implement cosine annealing or step decay as shown in the training optimization section.

---

**End of Practical Code Examples Section**

---

# Study Plan and Exercises

This section provides a practical 4-week study schedule with milestones, exercises, and resources for self-paced learning.

## Table of Contents
1. [4-Week Study Schedule](#4-week-study-schedule)
2. [Week 1: Neural Network Basics](#week-1-neural-network-basics)
3. [Week 2: Transformer Architecture](#week-2-transformer-architecture)
4. [Week 3: Training & Optimization](#week-3-training--optimization)
5. [Week 4: Capstone Project](#week-4-capstone-project)

---

## 4-Week Study Schedule

### Overview Table

| Week | Focus Area | Key Topics | Estimated Hours |
|------|-----------|------------|-----------------|
| **Week 1** | Neural Network Fundamentals | Architecture, neurons, activation functions, loss functions | 20-25 hours |
| **Week 2** | Transformer Architecture | Self-attention, positional encoding, encoder-decoder | 20-25 hours |
| **Week 3** | Training & Optimization | Backpropagation, optimizers, learning rates, regularization | 20-25 hours |
| **Week 4** | Capstone Project | Build complete model, integrate all concepts | 20-25 hours |

### Total Estimated Time: 80-100 hours

---

## Week 1: Neural Network Basics

### Milestones

**Day 1-2: Introduction & Architecture**
- Understand what neural networks are and why they work
- Learn network types (FNN, CNN, RNN)
- **Checkpoint**: Explain the difference between feedforward, convolutional, and recurrent networks

**Day 3-4: Neurons and Perceptrons**
- Learn the perceptron algorithm
- Understand weighted sums and activation functions
- **Checkpoint**: Implement a single-layer perceptron from scratch

**Day 5-6: Network Layers & Forward Propagation**
- Study layer types (input, hidden, output)
- Master matrix operations for batch processing
- **Checkpoint**: Draw and explain the forward pass diagram for a simple network

**Day 7: Review & Assessment**
- Complete Week 1 exercises
- Prepare for Week 2

---

### Exercises - Week 1

#### Derivation Exercises

**Exercise 1.1: Perceptron Weight Update**
Derive the perceptron learning rule step-by-step:
1. Start with prediction: $\hat{y} = \sigma(w \cdot x + b)$
2. Compute error: $error = y - \hat{y}$
3. Apply chain rule to derive weight update: $w_{new} = w - \eta \frac{\partial L}{\partial w}$
4. Show the final update rule

**Exercise 1.2: Backpropagation for 2-Layer Network**
Given a network with architecture Input → Hidden (ReLU) → Output (sigmoid):
- Forward pass: $z^{(1)} = W^{(1)}x + b^{(1)}$, $a^{(1)} = \text{ReLU}(z^{(1)})$
- Output: $z^{(2)} = W^{(2)}a^{(1)} + b^{(2)}$, $a^{(2)} = \sigma(z^{(2)})$
- Loss: $L = -[y\log a^{(2)} + (1-y)\log(1-a^{(2)})]$

Derive:
1. $\frac{\partial L}{\partial z^{(2)}}$ (output layer error)
2. $\frac{\partial L}{\partial W^{(2)}}$ and $\frac{\partial L}{\partial b^{(2)}}$
3. $\delta^{(1)} = \frac{\partial L}{\partial z^{(1)}}$ (hidden layer error signal)
4. $\frac{\partial L}{\partial W^{(1)}}$ and $\frac{\partial L}{\partial b^{(1)}}$

**Exercise 1.3: Activation Function Derivatives**
Derive the derivative for each activation function:
- Sigmoid: $\sigma'(z) = \sigma(z)(1 - \sigma(z))$
- ReLU: $\text{ReLU}'(z) = \begin{cases} 1 & z > 0 \\ 0 & z \leq 0 \end{cases}$
- Softmax: Derive $\frac{\partial \text{softmax}_i(z)}{\partial z_j}$

#### Architecture Design Exercises

**Exercise 1.4: Design a Custom Network**
Given the MNIST dataset (28×28 grayscale images → 10 digit classes):
1. Propose a network architecture with:
   - Input layer (784 neurons)
   - 2-3 hidden layers with appropriate sizes
   - Output layer (10 neurons, softmax)
2. Justify your choices for:
   - Number of hidden units per layer
   - Activation functions for each layer
   - Why this architecture should work

**Exercise 1.5: Layer Configuration Comparison**
Compare two architectures for image classification:

| Architecture | Input → H1 → H2 → Output |
|--------------|--------------------------|
| A | 784 → 256 → 128 → 10 |
| B | 784 → 128 → 128 → 64 → 10 |

For each, discuss:
- Computational cost estimation
- Potential overfitting risks
- Which would you choose and why

#### Code Implementation Exercises

**Exercise 1.6: Implement Forward Pass (NumPy)**
Complete the following implementation using only NumPy:

```python
import numpy as np

def relu(x):
    """ReLU activation function."""
    return np.maximum(0, x)

def sigmoid(z):
    """Sigmoid activation with numerical stability."""
    z = np.clip(z, -500, 500)  # Prevent overflow
    return 1.0 / (1.0 + np.exp(-z))

class SimpleNN:
    """Simple 2-layer neural network using NumPy."""
    
    def __init__(self, input_dim, hidden_dim, output_dim):
        """Initialize weights with Xavier/Glorot initialization."""
        self.W1 = np.random.randn(input_dim, hidden_dim) * np.sqrt(2.0 / (input_dim + hidden_dim))
        self.b1 = np.zeros(hidden_dim)
        self.W2 = np.random.randn(hidden_dim, output_dim) * np.sqrt(2.0 / (hidden_dim + output_dim))
        self.b2 = np.zeros(output_dim)
    
    def forward(self, X):
        """Forward pass through the network."""
        # Hidden layer
        self.z1 = self.W1 @ X + self.b1
        self.a1 = relu(self.z1)
        
        # Output layer
        self.z2 = self.W2 @ self.a1 + self.b2
        self.output = sigmoid(self.z2)
        
        return self.output
    
    def backward(self, X, y_true):
        """Backward pass to compute gradients."""
        batch_size = X.shape[0]
        
        # Output layer error (cross-entropy derivative simplified)
        delta2 = self.output - y_true  # Shape: (batch_size, output_dim)
        
        # Gradients for output layer
        dW2 = (self.a1.T @ delta2) / batch_size
        db2 = np.mean(delta2, axis=0)
        
        # Hidden layer error signal
        delta1 = self.W2.T @ delta1 * (self.z1 > 0)  # ReLU derivative
        
        # Gradients for hidden layer
        dW1 = (X.T @ delta1) / batch_size
        db1 = np.mean(delta1, axis=0)
        
        return {
            'dW1': dW1, 'db1': db1,
            'dW2': dW2, 'db2': db2
        }
    
    def update_weights(self, gradients, learning_rate=0.01):
        """Update weights using gradient descent."""
        self.W1 -= learning_rate * self['dW1']
        self.b1 -= learning_rate * self['db1']
        self.W2 -= learning_rate * self['dW2']
        self.b2 -= learning_rate * self['db2']

# Example usage:
if __name__ == "__main__":
    # Create a simple dataset (2 features, binary classification)
    np.random.seed(42)
    X = np.random.randn(100, 2)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    
    # Initialize and train network
    model = SimpleNN(input_dim=2, hidden_dim=8, output_dim=1)
    
    for epoch in range(10):
        # Forward pass
        output = model.forward(X)
        
        # Backward pass
        gradients = model.backward(X, y.reshape(-1, 1))
        
        # Update weights
        model.update_weights(gradients, learning_rate=0.1)
    
    print(f"Final predictions: {model.output[:5]}")
    print(f"True labels: {y[:5]}")
```

**Exercise 1.7: Add Batch Processing**
Modify the above code to support batch processing:
- Process mini-batches of size 32
- Compute gradients over batches (not entire dataset)
- Implement shuffling for each epoch

---

## Week 2: Transformer Architecture

### Milestones

**Day 1-2: Self-Attention Mechanism**
- Understand Q, K, V projections
- Master scaled dot-product attention
- **Checkpoint**: Manually compute attention weights for a small example

**Day 3-4: Positional Encoding**
- Study sinusoidal encoding formulas
- Understand why position matters in parallel processing
- **Checkpoint**: Implement positional encoding from scratch

**Day 5-6: Encoder & Decoder Architecture**
- Study encoder layers (self-attention + FFN)
- Master decoder with causal masking and cross-attention
- **Checkpoint**: Draw the full Transformer architecture diagram

**Day 7: Review & Assessment**
- Complete Week 2 exercises
- Prepare for Week 3

---

### Exercises - Week 2

#### Derivation Exercises

**Exercise 2.1: Scaled Dot-Product Attention**
Derive each step of the attention computation:

Given input $X \in \mathbb{R}^{n \times d_{\text{model}}}$:

1. **Projection**: Show that $Q = XW^Q, K = XW^K, V = XW^V$ where $W^Q, W^K, W^V \in \mathbb{R}^{d_{\text{model}} \times d_k}$
2. **Attention scores**: Derive $A = \frac{QK^T}{\sqrt{d_k}}$ and explain why $\sqrt{d_k}$ scaling is needed
3. **Softmax application**: Show that attention weights sum to 1: $\sum_j \text{softmax}_i(j) = 1$
4. **Output computation**: Derive $O = AV$ and show dimensions match

**Exercise 2.2: Multi-Head Attention**
Derive the multi-head attention formulation:

Given $Q, K, V \in \mathbb{R}^{n \times d_{\text{model}}}$ with $d_{\text{model}} = m \cdot d_k$:

1. Show that splitting into $m$ heads gives $Q_i = QW_i^Q, K_i = XW_i^K, V_i = XW_i^V$ where each has dimension $d_k$
2. Derive the concatenated output: $\text{Concat}(\text{head}_1, \dots, \text{head}_m)W^O$
3. Show that total computation remains $O(n^2 d_{\text{model}})$ despite multiple heads

**Exercise 2.3: Positional Encoding Properties**
Derive and explain the properties of sinusoidal positional encoding:

Given $PE_{(pos, i)}$:
1. Derive why even indices use sine and odd indices use cosine
2. Show that relative position information is encoded linearly: $PE_{pos+k} = f_k(PE_{pos})$
3. Derive the linear relationship: $PE_{(pos+k, 2i)} = \sin\left(\frac{pos+k}{10000^{2i/d}}\right) = \sin\left(\frac{pos}{10000^{2i/d}} + \frac{k}{10000^{2i/d}}\right)$

#### Architecture Design Exercises

**Exercise 2.4: Design a Transformer Encoder**
Design an encoder for sequence-to-sequence task with specifications:
- Input vocabulary size: 10,000
- Embedding dimension: 512
- Number of heads: 8
- Number of layers: 6
- Feed-forward expansion factor: 4
- Dropout rate: 0.1

Provide:
1. Dimension calculations for each layer
2. Total parameter count estimation
3. Computational complexity per forward pass
4. Justification for chosen hyperparameters

**Exercise 2.5: Compare Encoder vs Decoder**
Create a comparison table highlighting differences:

| Aspect | Encoder | Decoder |
|--------|---------|---------|
| Self-attention type | Standard | Causal (masked) |
| Cross-attention | None | To encoder output |
| Number of layer norms | 2 per layer | 3 per layer |
| Masking requirement | No | Yes (causal) |

Explain each difference and its purpose.

**Exercise 2.6: Design a Transformer Decoder**
Design a decoder for machine translation with:
- Same dimensions as encoder (512 dim, 8 heads, 6 layers)
- Cross-attention to encoder output
- Causal masking for self-attention

Provide:
1. Architecture diagram showing data flow
2. Explanation of why causal masking is needed during training and inference
3. How cross-attention enables the decoder to attend to relevant source positions

#### Code Implementation Exercises

**Exercise 2.7: Implement Positional Encoding (NumPy)**
Complete this implementation:

```python
import numpy as np

def get_positional_encoding(seq_len, d_model):
    """
    Generate sinusoidal positional embeddings.
    
    Parameters:
    -----------
    seq_len : int
        Maximum sequence length
    d_model : int
        Model dimension (must be even)
    
    Returns:
    --------
    pos_encoding : np.ndarray
        Array of shape (seq_len, d_model) containing positional embeddings
    """
    
    # Create position indices [0, 1, ..., seq_len-1]
    positions = np.arange(seq_len).reshape(-1, 1)  # Shape: (seq_len, 1)
    
    # Create dimension indices [0, 1, ..., d_model/2 - 1]
    dim_indices = np.arange(d_model // 2).reshape(1, -1)  # Shape: (1, d_model/2)
    
    # Compute position/dimension ratios
    # For even dimensions (2i): use sine
    # For odd dimensions (2i+1): use cosine
    
    # Create the denominator array
    denom = np.power(10000, 2 * dim_indices / d_model)  # Shape: (1, d_model/2)
    
    # Compute sine for even positions and cosine for odd positions
    # For position pos and dimension i:
    #   PE[pos, 2i] = sin(pos / 10000^(2i/d))
    #   PE[pos, 2i+1] = cos(pos / 10000^((2i+1)/d))
    
    # Compute all position/dimension ratios at once
    pos_dim_ratios = positions / denom  # Shape: (seq_len, d_model/2)
    
    # Apply sine to even columns and cosine to odd columns
    sin_part = np.sin(pos_dim_ratios)  # Even dimensions
    cos_part = np.cos(pos_dim_ratios)  # Odd dimensions
    
    # Combine into full embedding matrix
    pos_encoding = np.concatenate([sin_part, cos_part], axis=1)
    
    return pos_encoding

# Example usage:
if __name__ == "__main__":
    seq_len = 50
    d_model = 64
    
    encoding = get_positional_encoding(seq_len, d_model)
    print(f"Positional encoding shape: {encoding.shape}")  # Should be (50, 64)
    
    # Check that position 0 has all zeros for sine terms
    print(f"Position 0 first half: {encoding[0, :32]}")  # All should be 0
    print(f"Position 0 second half: {encoding[0, 32:]}")  # All should be 1
```

**Exercise 2.8: Implement Scaled Dot-Product Attention**
Complete this implementation with optional causal masking:

```python
import numpy as np

def scaled_dot_product_attention(Q, K, V, mask=None, dropout_rate=0.0):
    """
    Compute scaled dot-product attention with optional causal masking.
    
    Parameters:
    -----------
    Q : np.ndarray
        Query matrix of shape (batch_size, num_heads, seq_len, d_k)
    K : np.ndarray
        Key matrix of shape (batch_size, num_heads, seq_len, d_k)
    V : np.ndarray
        Value matrix of shape (batch_size, num_heads, seq_len, d_v)
    mask : np.ndarray or None
        Causal mask for decoder self-attention. If provided, should have
        shape (1, 1, seq_len, seq_len) with -inf in upper triangle.
    dropout_rate : float
        Dropout probability
    
    Returns:
    --------
    output : np.ndarray
        Attention output of shape (batch_size, num_heads, seq_len, d_v)
    """
    
    batch_size, num_heads, seq_len, d_k = Q.shape
    
    # Step 1: Compute attention scores
    # Q @ K.T gives scores of shape (batch, heads, seq_len, seq_len)
    attention_scores = np.matmul(Q, np.transpose(K, (0, 1, 3, 2))) / np.sqrt(d_k)
    
    # Step 2: Apply causal mask if provided (for decoder self-attention)
    if mask is not None:
        # Add mask to scores (masked positions get -inf before softmax)
        attention_scores = attention_scores + mask
    
    # Step 3: Apply softmax to get attention weights
    attention_weights = np.softmax(attention_scores, axis=-1)
    
    # Step 4: Apply dropout to attention weights
    if dropout_rate > 0:
        # Create random mask
        mask = (np.random.rand(*attention_weights.shape) > dropout_rate).astype(float)
        attention_weights = attention_weights * mask / (1 - dropout_rate)
    
    # Step 5: Compute output by weighted sum of values
    output = np.matmul(attention_weights, V)
    
    return output

# Example usage for encoder self-attention (no masking):
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample attention inputs
    batch_size = 2
    num_heads = 4
    seq_len = 6
    d_k = 16
    
    Q = np.random.randn(batch_size, num_heads, seq_len, d_k)
    K = np.random.randn(batch_size, num_heads, seq_len, d_k)
    V = np.random.randn(batch_size, num_heads, seq_len, d_k)
    
    # Encoder self-attention (no mask)
    output = scaled_dot_product_attention(Q, K, V, mask=None, dropout_rate=0.1)
    print(f"Encoder attention output shape: {output.shape}")  # Should match input
    
# Example usage for decoder self-attention (with causal mask):
def create_causal_mask(seq_len):
    """Create upper triangular mask for causal attention."""
    mask = np.triu(np.ones((seq_len, seq_len)), k=1) * (-1e9)  # -inf in upper triangle
    return mask

mask = create_causal_mask(seq_len=6)
output = scaled_dot_product_attention(Q, K, V, mask=mask, dropout_rate=0.0)
print(f"Decoder attention output shape: {output.shape}")
```

**Exercise 2.9: Build a Mini Transformer Encoder**
Implement a simplified encoder with all components:

```python
import numpy as np

class MiniTransformerEncoderLayer:
    """Simplified transformer encoder layer."""
    
    def __init__(self, d_model, num_heads, dropout_rate=0.1):
        """Initialize encoder layer."""
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        
        # Linear projections for attention
        self.W_Q = np.random.randn(d_model, d_model) * np.sqrt(2.0 / d_model)
        self.W_K = np.random.randn(d_model, d_model) * np.sqrt(2.0 / d_model)
        self.W_V = np.random.randn(d_model, d_model) * np.sqrt(2.0 / d_model)
        
        # Output projection for multi-head attention
        self.W_O = np.random.randn(d_model, d_model) * np.sqrt(2.0 / d_model)
        
        # Feed-forward network
        ff_dim = d_model * 4
        self.W_ff1 = np.random.randn(d_model, ff_dim) * np.sqrt(2.0 / (d_model + ff_dim))
        self.b_ff1 = np.zeros(ff_dim)
        self.W_ff2 = np.random.randn(ff_dim, d_model) * np.sqrt(2.0 / (ff_dim + d_model))
        self.b_ff2 = np.zeros(d_model)
        
        # Layer normalization parameters
        self.gamma1 = np.ones(d_model)
        self.beta1 = np.zeros(d_model)
        self.gamma2 = np.ones(d_model)
        self.beta2 = np.zeros(d_model)
        
        # Dropout
        self.dropout_rate = dropout_rate
    
    def attention(self, x):
        """Compute multi-head self-attention."""
        # Project to Q, K, V spaces
        Q = np.matmul(x, self.W_Q)  # Shape: (batch, seq, d_model)
        K = np.matmul(x, self.W_K)
        V = np.matmul(x, self.W_V)
        
        # Split into heads and compute attention
        num_heads = self.d_model // self.d_k  # Assuming d_model is divisible
        
        # Reshape for multi-head attention
        Q = Q.reshape(-1, num_heads, self.d_k)  # Simplified for demo
        K = K.reshape(-1, num_heads, self.d_k)
        V = V.reshape(-1, num_heads, self.d_k)
        
        # Compute attention (simplified - actual implementation would have proper head dimensions)
        attention_output = scaled_dot_product_attention(Q, K, V, mask=None, dropout_rate=self.dropout_rate)
        
        return attention_output
    
    def feed_forward(self, x):
        """Position-wise feed-forward network."""
        # First linear layer
        out1 = np.matmul(x, self.W_ff1) + self.b_ff1
        # ReLU activation
        out1 = np.maximum(0, out1)
        # Second linear layer
        out2 = np.matmul(out1, self.W_ff2) + self.b_ff2
        return out2
    
    def forward(self, x):
        """Forward pass through encoder layer."""
        # Save input for residual connection
        input_saved = x
        
        # Multi-head self-attention
        attn_output = self.attention(x)
        
        # Add & normalize (pre-normalization)
        mean_attn = np.mean(attn_output, axis=0, keepdims=True)
        std_attn = np.std(attn_output, axis=0, keepdims=True) + 1e-9
        attn_normalized = (attn_output - mean_attn) / std_attn * self.gamma1 + self.beta1
        
        # Residual connection
        attn_out = attn_out + input_saved
        
        # Feed-forward network
        ff_out = self.feed_forward(attn_out)
        
        # Add & normalize
        mean_ff = np.mean(ff_out, axis=0, keepdims=True)
        std_ff = np.std(ff_out, axis=0, keepdims=True) + 1e-9
        ff_normalized = (ff_out - mean_ff) / std_ff * self.gamma2 + self.beta2
        
        # Residual connection
        output = ff_normalized + attn_out
        
        return output

# Example usage:
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample sequence data
    batch_size = 2
    seq_len = 10
    d_model = 64
    
    X = np.random.randn(batch_size, seq_len, d_model)
    
    # Create encoder layer
    encoder_layer = MiniTransformerEncoderLayer(d_model=d_model, num_heads=8, dropout_rate=0.1)
    
    # Forward pass
    output = encoder_layer.forward(X)
    
    print(f"Input shape: {X.shape}")
    print(f"Output shape: {output.shape}")  # Should match input
```

---

## Week 3: Training & Optimization

### Milestones

**Day 1-2: Backpropagation Deep Dive**
- Master computational graph construction
- Derive chain rule applications
- **Checkpoint**: Manually compute gradients for a simple network

**Day 3-4: Optimizers Comparison**
- Study SGD with momentum
- Understand AdaGrad, RMSProp, Adam internals
- **Checkpoint**: Implement each optimizer from scratch

**Day 5-6: Learning Rate Schedules**
- Master schedule implementations
- Understand warmup strategies
- **Checkpoint**: Compare schedule effects on training curves

**Day 7: Regularization Techniques**
- Study dropout and batch norm mechanics
- Implement early stopping
- **Checkpoint**: Design regularization strategy for a new task

---

### Exercises - Week 3

#### Derivation Exercises

**Exercise 3.1: Chain Rule for Matrix Multiplication**
Derive gradients for matrix multiplication in backpropagation:

Given $Y = WX + b$ where:
- $W \in \mathbb{R}^{m \times n}$ (weights)
- $X \in \mathbb{R}^{n \times p}$ (input activations)
- $b \in \mathbb{R}^m$ (biases)
- $Y \in \mathbb{R}^{m \times p}$ (output)

Given upstream gradient $\delta = \frac{\partial L}{\partial Y} \in \mathbb{R}^{m \times p}$:

1. Derive $\frac{\partial L}{\partial W}$ using chain rule
2. Derive $\frac{\partial L}{\partial X}$ (gradient flowing to previous layer)
3. Derive $\frac{\partial L}{\partial b}$

**Exercise 3.2: Adam Optimizer Derivation**
Derive the complete Adam update rule from first principles:

Given:
- Gradient $g_t = \nabla_w L(w_t)$
- First moment estimate: $m_t = \beta_1 m_{t-1} + (1 - \beta_1) g_t$
- Second moment estimate: $v_t = \beta_2 v_{t-1} + (1 - \beta_2) g_t^2$

Derive:
1. Why bias correction is needed ($\hat{m}_t, \hat{v}_t$)
2. The final update rule with bias correction
3. Explain the role of $\epsilon$ for numerical stability

**Exercise 3.3: Cosine Annealing Schedule**
Derive the cosine annealing learning rate schedule:

Given parameters:
- $T$: Total training steps/epochs
- $t$: Current step
- $\eta_{\min}$: Minimum learning rate
- $\eta_{\max}$: Maximum learning rate

Derive:
1. The formula: $\eta_t = \eta_{\min} + \frac{\eta_{\max} - \eta_{\min}}{2}(1 + \cos(\frac{\pi t}{T}))$
2. Show that at $t=0$, $\eta_0 = \eta_{\max}$
3. Show that at $t=T$, $\eta_T = \eta_{\min}$
4. Derive the derivative $\frac{d\eta}{dt}$ and show it's always negative

#### Architecture Design Exercises

**Exercise 3.4: Design Regularization Strategy**
For a new image classification task with:
- Input: 224×224 RGB images
- Target accuracy: >90%
- Dataset size: 10,000 images

Design a regularization strategy including:
1. Weight decay value and justification
2. Dropout rate for fully connected layers
3. Batch normalization parameters (momentum, epsilon)
4. Data augmentation pipeline
5. Early stopping configuration (patience, metric)
6. Expected effect on generalization gap

Provide quantitative estimates for each hyperparameter and reasoning.

**Exercise 3.5: Optimizer Selection Matrix**
Create a decision matrix for choosing optimizers:

| Scenario | Recommended Optimizer | Reasoning |
|----------|----------------------|------------|
| Convex problem | SGD with momentum | Proven convergence guarantees |
| Non-convex deep learning | AdamW | Decoupled weight decay, robust |
| Sparse gradients | AdaGrad | Adapts to feature usage frequency |
| RNN/LSTM training | RMSProp or Adam | Handles vanishing/exploding issues |
| Small dataset | SGD with warm restarts | Better generalization |
| Large batch training | LARS scheduler | Scales with batch size |

For each scenario, provide 2-3 sentences explaining the choice.

#### Code Implementation Exercises

**Exercise 3.6: Implement Gradient Descent Variants**
Complete implementations for SGD, Momentum, and Adam:

```python
import numpy as np

class SimpleOptimizer:
    """Base optimizer class."""
    
    def __init__(self, learning_rate=0.01):
        self.learning_rate = learning_rate
    
    def step(self, gradients, parameters):
        """Update parameters using gradients."""
        raise NotImplementedError

class SGDOptimizer(SimpleOptimizer):
    """Stochastic Gradient Descent with optional momentum."""
    
    def __init__(self, learning_rate=0.01, momentum=0.0):
        super().__init__(learning_rate)
        self.momentum = momentum
        self.velocity = None  # For momentum
    
    def step(self, gradients, parameters):
        """Update parameters."""
        for grad, param in zip(gradients, parameters):
            if self.momentum == 0:
                param -= self.learning_rate * grad
            else:
                # Update velocity
                if self.velocity is None:
                    self.velocity = [np.zeros_like(param) for param in parameters]
                
                for vel, grad, param in zip(self.velocity, grad, param):
                    vel[:] = self.momentum * vel[:] - self.learning_rate * grad
                    param[:] = param + vel
    
    def set_velocity(self, shape_list):
        """Initialize velocity buffers."""
        if self.velocity is None:
            self.velocity = [np.zeros_like(shape) for shape in shape_list]

class MomentumOptimizer(SGDOptimizer):
    """SGD with momentum (separate velocity buffers)."""
    
    def __init__(self, learning_rate=0.01, momentum=0.9):
        super().__init__(learning_rate, momentum)
        self.momentum = momentum
    
    def step(self, gradients, parameters, shapes=None):
        """Update with momentum."""
        if shapes is None:
            shapes = [param.shape for param in parameters]
        
        if self.velocity is None:
            self.velocity = [np.zeros_like(shape) for shape in shapes]
        
        for vel, grad, param in zip(self.velocity, grad, param):
            vel[:] = self.momentum * vel[:] - self.learning_rate * grad
            param[:] = param + vel

class AdamOptimizer(SimpleOptimizer):
    """Adam optimizer implementation."""
    
    def __init__(self, learning_rate=0.001, beta1=0.9, beta2=0.999, epsilon=1e-8):
        super().__init__(learning_rate)
        self.beta1 = beta1
        self.beta2 = beta2
        self.epsilon = epsilon
        self.m = None  # First moment
        self.v = None  # Second moment
    
    def step(self, gradients, parameters, shapes=None):
        """Adam update with bias correction."""
        if shapes is None:
            shapes = [param.shape for param in parameters]
        
        if self.m is None:
            self.m = [np.zeros_like(shape) for shape in shapes]
            self.v = [np.zeros_like(shape) for shape in shapes]
        
        t = 1  # Simplified - would track time
        
        for m, v, grad, param in zip(self.m, self.v, grad, param):
            # Update biased first moment estimate
            m[:] = self.beta1 * m[:] + (1 - self.beta1) * grad
            
            # Update biased second raw moment estimate
            v[:] = self.beta2 * v[:] + (1 - self.beta2) * np.square(grad)
            
            # Compute bias-corrected first moment estimate
            m_hat = m / (1 - self.beta1 ** t)
            
            # Compute bias-corrected second raw moment estimate
            v_hat = v / (1 - self.beta2 ** t)
            
            # Update parameters
            param[:] -= self.learning_rate * m_hat / (np.sqrt(v_hat) + self.epsilon)
    
    def set_buffers(self, shapes):
        """Initialize momentum and velocity buffers."""
        if self.m is None:
            self.m = [np.zeros_like(shape) for shape in shapes]
            self.v = [np.zeros_like(shape) for shape in shapes]

# Example usage:
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample parameters and gradients
    param = np.random.randn(10, 5) * 0.1
    grad = np.random.randn(10, 5) * 0.01
    
    # Test SGD optimizer
    sgd = SGDOptimizer(learning_rate=0.01)
    sgd.step([grad], [param])
    print(f"SGD updated parameter shape: {param.shape}")
    
    # Test Adam optimizer
    adam = AdamOptimizer(learning_rate=0.001, beta1=0.9, beta2=0.999)
    adam.step([grad], [param])
    print(f"Adam updated parameter shape: {param.shape}")
```

**Exercise 3.7: Implement Learning Rate Schedules**
Complete implementations for various schedules:

```python
import math

class LearningRateScheduler:
    """Base class for learning rate schedulers."""
    
    def __init__(self, initial_lr=0.01):
        self.initial_lr = initial_lr
    
    def get_lr(self, current_epoch, total_epochs):
        """Get learning rate for given epoch."""
        raise NotImplementedError

class ConstantScheduler(LearningRateScheduler):
    """Constant learning rate."""
    
    def get_lr(self, current_epoch, total_epochs):
        return self.initial_lr

class StepDecayScheduler(LearningRateScheduler):
    """Step decay: reduce LR at fixed intervals."""
    
    def __init__(self, initial_lr=0.01, step_size=10, gamma=0.1):
        super().__init__(initial_lr)
        self.step_size = step_size  # Reduce every N epochs
        self.gamma = gamma  # Decay factor (e.g., 0.1 = 10x reduction)
    
    def get_lr(self, current_epoch, total_epochs):
        num_steps = current_epoch // self.step_size
        return self.initial_lr * (self.gamma ** num_steps)

class ExponentialDecayScheduler(LearningRateScheduler):
    """Exponential decay: LR decreases exponentially."""
    
    def __init__(self, initial_lr=0.01, decay_rate=0.95):
        super().__init__(initial_lr)
        self.decay_rate = decay_rate
    
    def get_lr(self, current_epoch, total_epochs):
        return self.initial_lr * (self.decay_rate ** current_epoch)

class CosineAnnealingScheduler(LearningRateScheduler):
    """Cosine annealing: smooth cosine-based decay."""
    
    def __init__(self, initial_lr=0.01, min_lr=0.0001, total_epochs=None):
        super().__init__(initial_lr)
        self.min_lr = min_lr
        self.total_epochs = total_epochs
    
    def get_lr(self, current_epoch, total_epochs):
        if self.total_epochs is None:
            self.total_epochs = total_epochs
        
        # Cosine annealing formula
        lr_range = self.initial_lr - self.min_lr
        return self.min_lr + 0.5 * lr_range * (1 + math.cos(math.pi * current_epoch / self.total_epochs))

class OneCycleScheduler(LearningRateScheduler):
    """One-cycle policy: cyclical increase then decrease."""
    
    def __init__(self, initial_lr=0.01, max_lr=0.1, min_lr=0.0001, 
                 total_epochs=None, cycle_proportion=0.5):
        super().__init__(initial_lr)
        self.max_lr = max_lr
        self.min_lr = min_lr
        self.total_epochs = total_epochs
        self.cycle_proportion = cycle_proportion
    
    def get_lr(self, current_epoch, total_epochs):
        if self.total_epochs is None:
            self.total_epochs = total_epochs
        
        half_cycle = int(self.total_epochs * self.cycle_proportion)
        
        if current_epoch < half_cycle:
            # Increasing phase
            return self.min_lr + (self.max_lr - self.min_lr) * \
                   (current_epoch / half_cycle) ** 2  # Quadratic increase
        else:
            # Decreasing phase
            remaining = total_epochs - current_epoch
            cycle_len = half_cycle
            progress = (current_epoch - half_cycle) / cycle_len
            return self.min_lr + (self.max_lr - self.min_lr) * \
                   0.5 * (1 + math.cos(math.pi * progress))

class CosineAnnealingWithWarmupScheduler(LearningRateScheduler):
    """Cosine annealing with linear warmup at the start."""
    
    def __init__(self, initial_lr=0.01, warmup_epochs=5, total_epochs=None, 
                 min_lr=0.0001, warmup_lr=0.001):
        super().__init__(initial_lr)
        self.warmup_epochs = warmup_epochs
        self.total_epochs = total_epochs
        self.min_lr = min_lr
        self.warmup_lr = warmup_lr
    
    def get_lr(self, current_epoch, total_epochs):
        if self.total_epochs is None:
            self.total_epochs = total_epochs
        
        # Warmup phase
        if current_epoch <= self.warmup_epochs:
            return self.warmup_lr * (current_epoch / self.warmup_epochs)
        
        # Cosine annealing after warmup
        effective_epochs = total_epochs - self.warmup_epochs
        lr_range = self.initial_lr - self.min_lr
        
        progress = (current_epoch - self.warmup_epochs) / effective_epochs
        return self.min_lr + 0.5 * lr_range * (1 + math.cos(math.pi * progress))

# Example usage:
if __name__ == "__main__":
    np.random.seed(42)
    
    # Test different schedulers
    total_epochs = 100
    
    schedulers = [
        ("Constant", ConstantScheduler()),
        ("Step Decay", StepDecayScheduler(step_size=10, gamma=0.1)),
        ("Exponential", ExponentialDecayScheduler(decay_rate=0.95)),
        ("Cosine", CosineAnnealingScheduler(min_lr=0.0001, total_epochs=total_epochs)),
        ("OneCycle", OneCycleScheduler(max_lr=0.1, min_lr=0.0001, total_epochs=total_epochs)),
        ("Cosine+Warmup", CosineAnnealingWithWarmupScheduler(
            warmup_epochs=5, total_epochs=total_epochs, warmup_lr=0.001)),
    ]
    
    for name, scheduler in schedulers:
        print(f"\n{name} Scheduler:")
        lrs = [scheduler.get_lr(epoch, total_epochs) for epoch in range(total_epochs)]
        print(f"  Initial LR: {lrs[0]:.6f}, Final LR: {lrs[-1]:.6f}")
```

---

## Week 4: Capstone Project

### Milestones

**Day 1-2: Project Setup & Architecture Design**
- Choose a project topic (e.g., sentiment analysis, image classifier)
- Design model architecture
- Prepare dataset and preprocessing pipeline
- **Checkpoint**: Complete project proposal document

**Day 3-4: Model Implementation & Training**
- Implement or load pre-trained model
- Set up training loop with appropriate optimizer
- Implement validation and monitoring
- **Checkpoint**: First training run complete

**Day 5-6: Analysis & Optimization**
- Analyze training curves and loss landscape
- Tune hyperparameters
- Apply advanced techniques (learning rate scheduling, regularization)
- **Checkpoint**: Improved model performance

**Day 7: Final Report & Presentation**
- Document architecture and results
- Create visualizations of attention maps, feature activations
- Prepare presentation of findings
- **Checkpoint**: Complete project report

---

### Project Options

Choose one of these capstone projects:

| Project | Description | Key Skills Demonstrated |
|---------|-------------|------------------------|
| **A. Sentiment Analysis Transformer** | Fine-tune BERT-like model for tweet sentiment | Transformer architecture, fine-tuning, NLP |
| **B. Image Classifier from Scratch** | Build CNN or Vision Transformer for CIFAR-10 | Architecture design, training, optimization |
| **C. Text Generation Model** | Implement decoder-only Transformer for text completion | Autoregressive modeling, sampling strategies |
| **D. Multi-modal Classifier** | Combine image and text embeddings for joint classification | Multi-modal representation learning |

---

### Project Deliverables

For any chosen project, submit:

1. **Project Proposal** (Day 2)
   - Problem statement
   - Architecture diagram
   - Dataset description
   - Evaluation metrics

2. **Training Scripts** (Day 4)
   - Model implementation or loading code
   - Training loop with checkpointing
   - Logging framework integration
   - Reproducibility measures (seeds, config files)

3. **Analysis Report** (Day 6)
   - Training curves (loss, accuracy over epochs)
   - Hyperparameter sweep results
   - Ablation study (e.g., dropout rates, batch sizes)
   - Comparison to baseline models

4. **Final Presentation** (Day 7)
   - Architecture walkthrough
   - Key findings and insights
   - Limitations and future work
   - Code repository with documentation

---

### Resources for Self-Paced Learning

#### Core Textbooks
- **"Deep Learning" by Goodfellow, Bengio, Courville** - Comprehensive reference
- **"Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow"** - Practical implementation focus
- **"Dive into Deep Learning" (d2l.ai)** - Free online textbook with code examples

#### Online Courses
- **Fast.ai Practical Deep Learning** - Top-down approach with immediate coding
- **DeepLearning.AI Specialization** - Structured curriculum from Andrew Ng
- **Stanford CS224n (NLP with Transformers)** - Coursera course

#### Key Papers to Read
1. Vaswani et al. (2017) - "Attention Is All You Need" [Transformer original]
2. Devlin et al. (2019) - "BERT: Pre-training of Deep Bidirectional Transformers"
3. Radford et al. (2018) - "Improving Language Understanding with Generative Pre-trained Transformers"
4. Kingma & Ba (2015) - "Adam: A Method for Stochastic Optimization"

#### Code Repositories to Study
- **Hugging Face Transformers** - Official Transformer implementations
- **PyTorch Lightning** - Simplified training loops
- **TensorFlow Hub** - Pre-trained models and architectures

#### Practice Platforms
- **Kaggle** - Competition datasets and notebooks
- **Papers With Code** - State-of-the-art models with code links
- **ArXiv Sanity Preserver** - Filtered arXiv papers by topic

---

### Study Completion Checklist

After completing all 4 weeks, verify:

- [ ] Can explain neural network fundamentals without reference material
- [ ] Can derive backpropagation gradients for custom architectures
- [ ] Can implement self-attention from scratch in NumPy
- [ ] Understand optimizer internals (Adam, RMSProp, etc.)
- [ ] Can design appropriate regularization strategies
- [ ] Completed full capstone project with documentation
- [ ] Created personal reference notes on key concepts

---

**End of Comprehensive Study Guide**

This guide provides everything needed to master neural networks and Transformer architectures through structured learning, hands-on exercises, and a comprehensive capstone project. Follow the 4-week schedule at your own pace, completing exercises as you advance through each section.
