# Neural Network Training: Comprehensive Study Guide

## Table of Contents
1. [Introduction to Neural Network Training](#introduction-to-neural-network-training)
2. [Backpropagation Algorithm](#backpropagation-algorithm)
3. [Optimizers: SGD and Adam](#optimizers-sgd-and-adam)
4. [Loss Functions](#loss-functions)
5. [Training Process Overview](#training-process-overview)

---

## Introduction to Neural Network Training

Neural network training is the process of adjusting a model's internal parameters (weights and biases) to minimize prediction error on training data. This is achieved through an iterative optimization process that combines:

- **Forward Propagation**: Computing predictions from input data
- **Loss Computation**: Measuring how wrong those predictions are
- **Backpropagation**: Calculating gradients of the loss with respect to parameters
- **Optimization**: Updating parameters to reduce future error

The core equation for weight updates is:

```
w_new = w_old - learning_rate × gradient
```

Where `gradient` comes from backpropagation and `learning_rate` controls step size.

---

## Backpropagation Algorithm

### What is Backpropagation?

Backpropagation (short for "backward propagation of errors") is an efficient algorithm for computing gradients in neural networks. It uses the **chain rule** from calculus to propagate error signals backward through the network layers, calculating how much each weight and bias contributed to the final prediction error.

### How Backpropagation Works

#### Step-by-Step Process:

1. **Forward Pass**: Input data flows through the network, producing predictions
2. **Loss Calculation**: Compute loss between predictions and true labels
3. **Backward Pass**: 
   - Start at output layer
   - Apply chain rule to compute gradients layer by layer
   - For each weight w_ij connecting neurons i and j:

```
∂L/∂w_ij = ∂L/∂a_j × ∂a_j/∂z_j × a_i
```

Where:
- `L` = loss function value
- `a_j` = activation of neuron j
- `z_j` = weighted input to neuron j (before activation)
- `a_i` = activation of neuron i

4. **Parameter Update**: Adjust weights and biases using gradients

### Mathematical Foundation

#### The Chain Rule Application:

For a network with layers L₁, L₂, ..., Lₙ, the gradient computation follows:

```
∂L/∂w^(l) = ∂a^(l)/∂z^(l) × ∂z^(l)/∂w^(l)
           = δ^(l) × a^(l-1)
```

Where `δ^(l)` is the error term at layer l:

```
For output layer (supervised learning):
  δ^L = ∂L/∂a^L × σ'(z^L)

For hidden layers:
  δ^l = ((w^(l+1))^T × δ^(l+1)) ⊙ σ'(z^l)
```

Where `⊙` denotes element-wise multiplication.

### Activation Function Derivatives

The backpropagation gradient depends on activation function derivatives:

| Activation | Formula | Derivative σ'(z) |
|------------|---------|------------------|
| Sigmoid | 1/(1+e⁻ᶻ) | σ(z)(1-σ(z)) |
| Tanh | tanh(z) | 1 - tanh²(z) |
| ReLU | max(0,z) | 1 if z>0, else 0 |
| LeakyReLU | max(αz, z) | 1 or α |

### Gradient Flow Example

Consider a simple network with one hidden layer:

```
Input → [Neuron h₁] → Output neuron o
           ↓
         [Neuron h₂]
```

Backpropagation computes:
1. **Output error**: δ^L = (prediction - target) × σ'(z^L)
2. **Hidden layer errors**: 
   - δ¹_h₁ = w_ho_L × δ^L × σ'(z¹_h₁)
   - δ¹_h₂ = w_ho_L × δ^L × σ'(z¹_h₂)

### Why Backpropagation is Efficient

- **Single backward pass** computes gradients for ALL parameters
- **Reuses intermediate derivatives**: Computation graph approach stores activations from forward pass and reuses them
- **O(n²)** complexity for n-layer networks (vs O(n³) naive approaches)

---

## Optimizers: SGD and Adam

### What is an Optimizer?

An optimizer determines HOW to update network parameters based on computed gradients. Different optimizers use different strategies to navigate the loss landscape toward minima.

---

### Stochastic Gradient Descent (SGD)

#### Algorithm:

```
For each mini-batch:
  1. Compute gradient g = ∇_w L(w, batch)
  2. Update weights: w ← w - η × g
```

Where `η` is the learning rate.

#### Key Properties:

| Property | Description |
|----------|-------------|
| **Update Rule** | Direct descent along negative gradient |
| **Learning Rate** | Fixed or scheduled (e.g., decay over epochs) |
| **Convergence** | Can get stuck in local minima, but often generalizes well |
| **Computational Cost** | Low per iteration |

#### Learning Rate Scheduling:

Common strategies to improve SGD convergence:

```python
# Step decay
learning_rate = initial_lr * 0.1^(epoch // step_size)

# Exponential decay  
learning_rate = initial_lr / (1 + decay_rate × epoch)

# Cosine annealing
learning_rate = min_lr + 0.5 × (max_lr - min_lr) × (1 + cos(π × epoch/total_epochs))
```

---

### SGD with Momentum

#### Algorithm:

```python
v_t = μ × v_{t-1} + η × g_t          # Velocity update
w ← w - v_t                          # Weight update
```

Where `μ` (mu) is the momentum coefficient, typically 0.9.

#### How Momentum Works:

- Accumulates gradients in a moving average way
- Helps escape local minima and saddle points
- Reduces oscillations in parameter updates
- Analogy: Like a ball rolling down a hill with inertia

```
        ^
       / \     (oscillating gradient)
      /   \
-----/-----\----→  (smoothed velocity)
    /
   ↓  (momentum carries you forward)
```

#### Momentum Values:

| μ Value | Behavior |
|---------|----------|
| 0.9     | Standard momentum, good balance |
| 0.95+   | High momentum, faster convergence but may overshoot |
| 0.85-0.9| Conservative, more stable training |

---

### Adam Optimizer (Adaptive Moment Estimation)

#### Algorithm:

Adam combines ideas from Momentum and RMSProp with adaptive learning rates per parameter.

```python
# First moment estimate (mean of gradients)
m_t = β₁ × m_{t-1} + (1 - β₁) × g_t

# Second moment estimate (uncentered variance)
v_t = β₂ × v_{t-1} + (1 - β₂) × g²_t

# Bias correction for initialization
m̂_t = m_t / (1 - β₁^t)
v̂_t = v_t / (1 - β₂^t)

# Parameter update
w ← w - η × m̂_t / (√(v̂_t) + ε)
```

#### Default Hyperparameters:

| Parameter | Typical Value | Purpose |
|-----------|---------------|---------|
| β₁        | 0.9           | First moment decay rate |
| β₂        | 0.999         | Second moment decay rate |
| ε         | 1e-8          | Numerical stability |

#### Why Adam is Popular:

1. **Adaptive Learning Rates**: Each parameter gets its own learning rate based on gradient history
2. **Momentum Built-in**: First moment estimation provides momentum-like behavior
3. **Fast Convergence**: Often requires less tuning than SGD
4. **Robustness**: Works well across many problems with minimal hyperparameter search

---

### Optimizer Comparison Table

| Feature | SGD | SGD+Momentum | RMSProp | Adam |
|---------|-----|--------------|--------|------|
| **Learning Rate** | Global (shared) | Global | Per-parameter adaptive | Per-parameter adaptive |
| **Adaptation Speed** | Slow | Medium | Fast | Very fast |
| **Memory Required** | Low | Medium | Medium | High (stores 2 moments per param) |
| **Hyperparameter Tuning** | High effort | Medium | Medium | Low |
| **Generalization** | Often best | Good | Good | Good, sometimes overfits |
| **Best For** | Large batch, fine-tuning | Standard training | Non-stationary objectives | Quick prototyping, most tasks |

#### When to Use Each:

- **SGD with Momentum**: Production models where generalization is critical
- **Adam**: Research/prototyping, when time for tuning SGD is limited
- **RMSProp**: Problems with sparse gradients or non-stationary objectives
- **AMSGrad**: Variant of Adam that avoids overfitting issues in some cases

---

### Advanced Optimizer Variants

#### AdamW (Weight Decay Decoupled)

Separates weight decay from optimization:

```python
w ← w - η × m̂_t / (√(v̂_t) + ε) - λ × w  # Weight decay applied directly
```

Better than L2 regularization with Adam for many tasks.

#### Lion Optimizer

Newer optimizer gaining popularity, simpler than Adam:

```python
m_t = μ × m_{t-1} + η × sign(g_t) × g_t
v_t = β₂ × v_{t-1} + (1 - β₂) × |g_t|²
w ← w - η × m̂_t / (√(v̂_t) + ε)
```

---

## Loss Functions

### What is a Loss Function?

A loss function (also called cost or objective function) measures the difference between predicted and actual values. The goal of training is to minimize this loss.

Formally: `L(y, ŷ)` where:
- `y` = true label
- `ŷ` = model prediction

---

### Mean Squared Error (MSE)

#### Use Case: Regression problems with continuous targets

```python
MSE(y, ŷ) = 1/n × Σ(y_i - ŷ_i)²
```

#### Properties:

| Property | Description |
|----------|-------------|
| **Differentiable** | Yes (smooth gradient everywhere except at exact match) |
| **Penalty Type** | Squared error penalizes large errors more heavily |
| **Gradient** | ∂L/∂ŷ = 2(n-1)(y - ŷ)/n² |

#### Example: Predicting house prices

```python
# True price: $500k, Predicted: $480k
MSE = (500 - 480)² / n = 400/n

# If prediction was $300k instead:
MSE = (500 - 300)² / n = 40,000/n  # Much worse!
```

---

### Binary Cross-Entropy

#### Use Case: Binary classification (2 classes)

```python
BCE(y, p) = -[y × log(p) + (1-y) × log(1-p)]
```

Where:
- `y ∈ {0, 1}` is the true label
- `p` is predicted probability of class 1

#### Properties:

| Property | Description |
|----------|-------------|
| **Range** | (0, ∞) - always positive |
| **Gradient at p=0.5** | Maximum gradient when prediction is uncertain |
| **Numerical Stability** | Use log-sigmoid trick to avoid overflow |

#### Implementation with Numerical Stability:

```python
import torch

def stable_bce_loss(y_true, y_pred):
    """Stable binary cross-entropy implementation"""
    eps = 1e-8
    # Clip predictions to avoid log(0)
    p_clipped = torch.clamp(y_pred, eps, 1 - eps)
    loss = -(y_true * torch.log(p_clipped) + 
              (1 - y_true) * torch.log(1 - p_clipped))
    return loss.mean()
```

---

### Categorical Cross-Entropy

#### Use Case: Multiclass classification (>2 classes, mutually exclusive)

```python
CCE(y, ŷ) = -Σ_j y_j × log(ŷ_j)
```

Where:
- `y` is one-hot encoded label (e.g., [0, 1, 0] for class 2 of 3)
- `ŷ` is probability distribution over classes

#### Properties:

| Property | Description |
|----------|-------------|
| **Input** | One-hot encoded labels or class indices |
| **Output Layer** | Requires softmax activation |
| **Gradient Flow** | Encourages confident predictions for correct class |

---

### Hinge Loss (for SVMs)

#### Use Case: Margin-based classification, particularly with Support Vector Machines

```python
Hinge(y, ŷ) = max(0, 1 - y × ŷ)
```

Where `y ∈ {-1, +1}` and `ŷ` is the predicted score (not probability).

#### Properties:

| Property | Description |
|----------|-------------|
| **Non-differentiable at** | y × ŷ = 1 |
| **SVM Connection** | Foundation of Support Vector Machines |
| **Margin Maximization** | Encourages large margins between classes |

---

### Loss Function Comparison Table

| Loss Type | Problem Type | Gradient Behavior | Best For |
|-----------|--------------|-------------------|----------|
| **MSE** | Regression | Smooth everywhere | Continuous targets, Gaussian noise |
| **MAE (L1)** | Regression | Constant gradient magnitude | Robust to outliers |
| **BCE** | Binary Classification | High when uncertain | 2-class problems with sigmoid output |
| **CCE** | Multiclass Classification | Encourages confident predictions | Image classification, NLP token prediction |
| **Hinge** | Margin-based Classification | Non-smooth at boundary | SVM-style models |
| **KL Divergence** | Distribution matching | Smooth, information-theoretic | Generative models, VAEs |

---

### Advanced Loss Functions

#### Focal Loss (for Class Imbalance)

Addresses the problem where easy examples dominate training:

```python
Focal(y, p, γ=2) = -α × (1-p)^γ × log(p) if y=1 else -(p)^γ × log(1-p)
```

Where `γ` down-weights easy examples.

#### Label Smoothing

Prevents model from becoming over-confident:

```python
Loss(y, ŷ) = -Σ ((1-ε) × y + ε/K) × log(ŷ)
```

Where `K` is number of classes and `ε` is smoothing factor (e.g., 0.1).

---

## Training Process Overview

### Complete Training Pipeline

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Define model, loss function, and optimizer
model = YourModel()
criterion = nn.CrossEntropyLoss()  # or MSE, BCE, etc.
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

# Training loop
for epoch in range(num_epochs):
    for batch_x, batch_y in train_loader:
        # Forward pass
        optimizer.zero_grad()           # Clear previous gradients
        predictions = model(batch_x)    # Compute outputs
        loss = criterion(predictions, batch_y)  # Compute loss
        
        # Backward pass (backpropagation)
        loss.backward()                 # Compute gradients via .backward()
        
        # Parameter update
        optimizer.step()                # Apply gradient updates
        
        if epoch % 10 == 0:
            print(f"Epoch {epoch}, Loss: {loss.item():.4f}")
```

### Key Training Concepts

#### Learning Rate Schedule Examples:

```python
# 1. StepLR - decrease learning rate every step_size epochs
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, 
                                            step_size=30, gamma=0.1)

# 2. ReduceLROnPlateau - decrease when validation loss stops improving
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode='min', factor=0.5, patience=5)

# 3. CosineAnnealingLR - smooth cosine decay
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
    optimizer, T_max=num_epochs)
```

#### Weight Decay (Regularization):

Prevents overfitting by penalizing large weights:

```python
optimizer = torch.optim.Adam(model.parameters(), 
                             lr=0.001, weight_decay=1e-5)
```

---

## Quick Reference: Choosing Components

### When to Use What:

#### Optimizer Selection:

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Research/prototyping | Adam | Fast convergence, less tuning needed |
| Production/fine-tuning | SGD+Momentum | Often better generalization |
| Sparse gradients | RMSProp/Adam | Adaptive learning rates help |
| Very large datasets | AdamW | Decoupled weight decay improves generalization |

#### Loss Function Selection:

| Problem Type | Recommended Loss | Output Activation |
|--------------|------------------|-------------------|
| Continuous target (regression) | MSE or MAE | Linear (no activation) |
| 2-class classification | Binary Cross-Entropy | Sigmoid |
| Multi-class (>2) classification | Categorical Cross-Entropy | Softmax |
| Ranking problems | Hinge Loss / Pairwise BCE | No specific activation needed |

---

## Summary Checklist for Neural Network Training

### Before Training:

- [ ] Select appropriate loss function for your problem type
- [ ] Choose optimizer (Adam for speed, SGD+Momentum for generalization)
- [ ] Set initial learning rate (start with 1e-3 to 1e-4)
- [ ] Consider weight decay if overfitting is a concern

### During Training:

- [ ] Monitor training loss (should decrease monotonically)
- [ ] Track validation metrics (to detect overfitting)
- [ ] Use learning rate scheduling for better convergence
- [ ] Apply data augmentation when possible

### After Training:

- [ ] Evaluate on held-out test set
- [ ] Check if model needs fine-tuning with different hyperparameters
- [ ] Consider ensemble methods if variance is high

---

## Further Reading

### Key Papers:

1. **Backpropagation**: Rumelhart, Hinton & Williams (1986) - "Learning Representations by Back-propagating Errors"
2. **Adam Optimizer**: Kingma & Ba (2014) - "Adam: A Method for Stochastic Optimization"
3. **SGD with Momentum**: Polyak & Böttinger (1992)

### Recommended Resources:

- [Gradient Descent and Backpropagation Guide](https://developer.nvidia.com/blog/a-data-scientists-guide-to-gradient-descent-and-backpropagation-algorithms/)
- [Optimizers Comparison Studies](https://apxml.com/courses/deep-learning-regularization-optimization/chapter-6-adaptive-optimizers/choosing-optimizers-guidelines)

---

*Document generated for Neural Networks and Transformers comprehensive study documentation.*
