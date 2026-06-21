# Neural Networks Visual Learning Aids

Comprehensive diagrams, visualizations, and illustrations to help understand neural network structures, data flow, and activation processes.

---

## Table of Contents

1. [Neural Network Structure Diagram](#neural-network-structure-diagram)
2. [Data Flow Through Layers](#data-flow-through-layers)
3. [Activation Process Visualization](#activation-process-visualization)
4. [Single Neuron Architecture](#single-neuron-architecture)
5. [Forward Propagation Flowchart](#forward-propagation-flowchart)
6. [Backpropagation Learning Process](#backpropagation-learning-process)

---

## Neural Network Structure Diagram

### Multi-Layer Perceptron (MLP) Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT LAYER                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                        │
│  │ Feature1│  │ Feature2│  │ Feature3│  │ Feature4│  ← Input Data (X)      │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘                        │
│         ↓           ↓           ↓           ↓                               │
│         ════════ HIDDEN LAYER 1 ═══════════════════════════════════════════ │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                        │
│  │ Neuron1 │  │ Neuron2 │  │ Neuron3 │  │ Neuron4 │                        │
│  │ Weighted│  │ Weighted│  │ Weighted│  │ Weighted│                        │
│  │ Sum +   │  │ Sum +   │  │ Sum +   │  │ Sum +   │                        │
│  │ Activation│Activation│Activation│Activation│    ← Hidden Layer (h)       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘                        │
│         ↓           ↓           ↓           ↓                               │
│         ════════ HIDDEN LAYER 2 ═══════════════════════════════════════════ │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                                      │
│  │ Neuron1 │  │ Neuron2 │  │ Neuron3 │  ← Deeper abstraction features       │
│  └─────────┘  └─────────┘  └─────────┘                                      │
│         ↓           ↓                                                         │
│         ════════ OUTPUT LAYER ═══════════════════════════════════════════════│
│  ┌─────────┐  ┌─────────┐                                                    │
│  │ Class1  │  │ Class2  │  ← Output Prediction (ŷ)                          │
│  └─────────┘  └─────────┘                                                    │
│                                                                              │
│  Data Flow: Input → Hidden Layer 1 → Hidden Layer 2 → Output                │
└──────────────────────────────────────────────────────────────────────────────┘

Legend:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ Direction of data flow (forward propagation)
↓ Signal passing through connections
═ Connection with weight parameters
┌ ─ ─ ┐ Neuron/Node processing unit
```

### Fully Connected Neural Network Example (3 Hidden Layers, 4096 → 2048 → 1024 → 512 → 1)

```
Input Layer:    [x₁]   [x₂]   [x₃]   [x₄]   ...   [xₙ]      (n features)
                 │     │     │     │              │
                 ├─────┼─────┼─────┼──────────────┤
                  \    |     |    /           ↓
                   \   |     |   /            ══════ HIDDEN LAYER 1
                    \  |     |  /             [h₁] [h₂] ... [hₘ]      (m neurons)
                     \ |     | /              │     │                 │
                      \|     |/               ├─────┼────────────────┤
                       └─────┴─────────────────┘     │                 ↓
                                                     ══════ HIDDEN LAYER 2
                                                      [h'₁] [h'₂] ... [h'ₖ]    (k neurons)
                                                         │               │
                                                          ├──────────────┼──────────────┤
                                                           └─────────────┘                ↓
                                                                      ══════ HIDDEN LAYER 3
                                                                       [h''₁] [h''₂] ... [h''ₚ]     (p neurons)
                                                                          │               │
                                                                           ├──────────────┼──────────────┤
                                                                            └─────────────┘                ↓
                                                                                             ══════ OUTPUT LAYER
                                                                                              [y₁] [y₂]      (output units)

Data Flow Visualization:

    ┌──────────────────────────────────────────────────────────────────────────┐
    │                                                                          │
    │   INPUT          →  HIDDEN1     →  HIDDEN2     →  HIDDEN3     → OUTPUT    │
    │   (Raw Data)      (Features)     (Deep Features)        (Prediction)      │
    │                                                                    ↓       │
    │   Pixel values /        Text embeddings /            Classification score│
    │   Word vectors /         Graph features /              Regression value  │
    │                                                                          │
    └──────────────────────────────────────────────────────────────────────────┘

```

---

## Data Flow Through Layers

### Forward Propagation Step-by-Step

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                    FORWARD PROPAGATION PROCESS                              ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   STEP 1: INPUT RECEIPT                                                    ║
║   ┌─────────────────────────────────────────────────────────────────┐     ║
║   │ X = [x₁, x₂, x₃, ..., xₙ]                                       │     ║
║   │ Example Image Input (28×28 pixels flattened):                    │     ║
║   │                                                                  │     ║
║   │  ┌───┐ ┌───┐ ┌───┐       ┌───┐ ┌───┐ ┌───┐                      │     ║
║   │  │ 0 │ │ 1 │ │ 0 │   ... │ 2 │ │ 3 │ │ 4 │  ← Pixel intensities  │     ║
║   │  └───┘ └───┘ └───┘       └───┘ └───┘ └───┘                      │     ║
║   │                                                                  │     ║
║   │  Input Vector: [0, 1, 0, ..., 2, 3, 4, ...]                     │     ║
║   └─────────────────────────────────────────────────────────────────┘     ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝

    ↓

╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   STEP 2: WEIGHTED SUMMATION                                               ║
║                                                                            ║
║        ┌─────────┐                                                         ║
║        │  x₁     │                                                         ║
║        │    \    │                                                         ║
║        │     \ w₁│                                                         ║
║        │      \   │                                                        ║
║        └───────\──┼───────────────────────────────────────────────────────┘║
║                │  │                                                        ║
║        ┌─────────┐│                                                        ║
║        │  x₂     ││  z₁ = w₁·x₁ + w₂·x₂ + ... + wₙ·xₙ + b₁               ║
║        │    \    ││                                                        ║
║        │     \ w₂│├───────────────────────────────────────────────────────┤║
║        └───────\──┼───────────────────────────────────────────────────────┘║
║                │  │                                                        ║
║   ┌─────────┐  │  z = Σ(wᵢ·xᵢ) + b                                         ║
║   │  x₃     │  │                                                           ║
║   │    \    │  │                                                            ║
║   │     \ wₙ│  │  where:                                                    ║
║   └───────\──┼─────────────────────────────────────────────────────────────╫║
║                │  b = bias term                                            ╫║
║        ┌─────────┐                                                         ╫║
║        │  xₙ     │                                                         ╫║
║        └─────────┘                                                         ╫║
║                                                                            ╫║
║   Output of this layer: z (pre-activation value)                          ╫║
║                                                                            ╚═══════════╝

    ↓

╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   STEP 3: ACTIVATION FUNCTION                                              ║
║                                                                            ║
║   a = f(z) = activation_function(pre_activation_value)                    ║
║                                                                            ║
║   Common Activation Functions:                                             ║
║                                                                            ║
║   ┌──────────────────────────────────────────────────────────────────────┐ ║
║   │ SIGMOID (f(x) = 1 / (1 + e^(-x)))                                    │ ║
║   │    Input: -3              Output: ~0.05                              │ ║
║   │    Input:  0             Output:  0.5                                │ ║
║   │    Input: +3             Output: ~0.95                               │ ║
║   └──────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
║   ┌──────────────────────────────────────────────────────────────────────┐ ║
║   │ RELU (f(x) = max(0, x))                                               │ ║
║   │    Input: -3              Output:  0 (clipped to zero)                │ ║
║   │    Input:  0             Output:  0                                   │ ║
║   │    Input: +3             Output:  3                                  │ ║
║   └──────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
║   ┌──────────────────────────────────────────────────────────────────────┐ ║
║   │ TANH (f(x) = (e^x - e^(-x)) / (e^x + e^(-x)))                         │ ║
║   │    Input: -3              Output: ~-0.99                             │ ║
║   │    Input:  0             Output:  0                                   │ ║
║   │    Input: +3             Output: ~0.99                                │ ║
║   └──────────────────────────────────────────────────────────────────────┘ ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝

    ↓

╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║   STEP 4: OUTPUT LAYER                                                     ║
║                                                                            ║
║   For Classification (Softmax):                                            ║
║                                                                            ║
║        ┌─────────┐                                                         ║
║   z₁ = │       │     e^z₁ / Σ(e^zⱼ)                                       ║
║          Output 1│     ╔═══════════════════════════════════════════════╗ ║
║        ┌─────────┴───┐                                                 ╫║
║   z₂ = │       │     e^z₂ / Σ(e^zⱼ)                                       ╫║
║          Output 2│     ╚═══════════════════════════════════════════════╝ ╫║
║        ┌─────────┬───┐                                                 ╫║
║   z₃ = │       │     e^z₃ / Σ(e^zⱼ)                                       ╫║
║          Output 3│     ...                                                ╫║
║        └─────────┴───┘            Final probabilities (sum to 1)           ╫║
║                                                                            ╚═══════╝

```

---

## Activation Process Visualization

### ReLU Activation Function Graph

```
ReLU: f(x) = max(0, x)

    y
    ↑
    │                                    ╭───────┐
    │                                  ╱         │
    │                                ╱           │
    │                              ╱             │
    │                            ╱               │
    │                          ╱                 │
    │                        ╱                   │
    │                      ╱                     │
    │                    ╱                       │
    │                  ╱                         │
    │                ╱                           │
    │              ╱                             │
    │            ╱                               │
    │          ╱                                 │
    │        ╱                                   │
    │      ╱                                     │
    │    ╱                                       │
    │  ╱                                         │
    │╱                                           │
    └─────────────────────────┴──────────────────→ x
   -3                           0                +3

Key Points:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Input < 0: Output = 0 (dead neurons for negative values)
• Input ≥ 0: Output = input (linear pass-through)
• Derivative: 1 if x > 0, 0 if x ≤ 0

Advantages:
  ✓ Simple and computationally efficient
  ✓ Helps mitigate vanishing gradient problem
  ✓ Works well in deep networks
Disadvantages:
  ❌ Can cause "dying ReLU" problem (neurons stuck at 0)


```

### Sigmoid Activation Function Graph

```
Sigmoid: f(x) = 1 / (1 + e^(-x))

    y = 1.0 ────────────────────────────────────┐
         ╲                                     │
          ╲                                    │
           ╲                                   │
            ╲                                  │
             ╲                                 │
              ╲                                │
               ╲                               │
                ╲                              │
                 ╲                             │
                  ╲                            │
                   ╲                           │
                    ╲                          │
                     ╲                         │
                      ╲                        │
                       ╲                       │
                        ╲                      │
                         ╲                     │
                          ╲                    │
                           ╲                   │
                            ╲                  │
                             ╲                 │
                              ╲                │
                               ╲               │
                                ╲              │
                                 ╲             │
                                  ╲            │
                                   ╲           │
                                    ╲          │
                                     ╲         │
                                      ╲        │
                                       ╲       │
                                        ╲      │
                                         ╲     │
                                          ╲    │
                                           ╲   │
                                            ╲  │
                                             ╲ │
                                              ╰┼──────────────────────────────────→ x
                                               └─2.0 -1.5 -1.0 -0.5  0.0  0.5  1.0  1.5  2.0

Key Points:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Output range: (0, 1) — perfect for binary classification probabilities
• Input = 0: Output = 0.5 (balanced point)
• As x → ∞: Output → 1
• As x → -∞: Output → 0

Advantages:
  ✓ Bounded output between 0 and 1
  ✓ Monotonically increasing
Disadvantages:
  ❌ Vanishing gradient problem (derivatives approach 0 for large |x|)


```

### Tanh Activation Function Graph

```
Tanh: f(x) = (e^x - e^(-x)) / (e^x + e^(-x))

    y = 1.0 ────────────────────────────────────┐
         ╲                                     │
          ╲                                    │
           ╲                                   │
            ╲                                  │
             ╲                                 │
              ╲                                │
               ╲                               │
                ╲                              │
                 ╲                             │
                  ╲                            │
                   ╲                           │
                    ╲                          │
                     ╲                         │
                      ╲                        │
                       ╲                       │
                        ╲                      │
                         ╲                     │
                          ╲                    │
                           ╲                   │
                            ╲                  │
                             ╲                 │
                              ╲                │
                               ╲               │
                                ╲              │
                                 ╲             │
                                  ╲            │
                                   ╲           │
                                    ╲          │
                                     ╲         │
                                      ╲        │
                                       ╲       │
                                        ╲      │
                                         ╲     │
                                          ╲    │
                                           ╲   │
                                            ╲  │
                                             ╰┼──────────────────────────────────→ x
                                              └─2.0 -1.5 -1.0 -0.5  0.0  0.5  1.0  1.5  2.0

Key Points:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Output range: (-1, 1) — centered around zero (better than sigmoid)
• Input = 0: Output = 0
• As x → ∞: Output → 1
• As x → -∞: Output → -1

Advantages:
  ✓ Zero-centered output (helps with gradient descent)
  ✓ Stronger gradients than sigmoid
Disadvantages:
  ❌ Still suffers from vanishing gradient for extreme values


```

### Leaky ReLU Activation Function Graph

```
Leaky ReLU: f(x) = max(α·x, x) where α is a small positive constant (e.g., 0.01)

    y
    │                                    ╭───────┐
    │                                  ╱         │
    │                                ╱           │
    │                              ╱             │
    │                            ╱               │
    │                          ╱                 │
    │                        ╱                   │
    │                      ╱                     │
    │                    ╱                       │
    │                  ╱                         │
    │                ╱                           │
    │              ╱                             │
    │            ╱                               │
    │          ╱                                 │
    │        ╱                                   │
    │      ╱                                     │
    │    ╱                                       │
    │  ╱                                         │
    │╱                                           │
    └─────────────────┬──────────────────────────→ x
                      │
                (α=0.01)
             Small positive slope for negative inputs

Key Points:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Solves "dying ReLU" problem by allowing small gradients for negative values
• More robust than standard ReLU
• Parameter α can be learned (Parametric ReLU)


```

---

## Single Neuron Architecture

### Neuron Diagram with Connections and Weights

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                           SINGLE NEURON ARCHITECTURE                       ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   INPUTS                                                                   ║
║   ┌─────────┐  ┌─────────┐  ┌─────────┐                                   ║
║   │    x₁   │  │    x₂   │  │    x₃   │   ...                            ║
║   │         │  │         │  │         │                                   ║
║   └────┬────┘  └────┬────┘  └────┬────┘                                  ║
║        │ w₁         │ w₂          │ wₙ                                    ║
║        ↓            ↓             ↓                                       ║
║   ┌───────────────────────────────────────────────────────────────────┐   ║
║   │                                                                  │   ║
║   │                        NEURON                                     │   ║
║   │                                                                  │   ║
║   │  ┌────────────────────────────────────────────────────────────┐  │   ║
║   │  │  WEIGHTED SUMMATION LAYER                                  │  │   ║
║   │  │                                                             │  │   ║
║   │  │     z = Σ(wᵢ · xᵢ) + b                                      │  │   ║
║   │  │                                                             │  │   ║
║   │  │        w₁·x₁                                               │  │   ║
║   │  │        w₂·x₂                                               │  │   ║
║   │  │       + · · ·                                              │  │   ║
║   │  │        wₙ·xₙ                                               │  │   ║
║   │  │                                                             │  │   ║
║   │  │     └──────────────┬─────────────────────────────────────┘  │   ║
║   │  │                    ↓                                         │   ║
║   │  │                    b (bias)                                 │   ║
║   │  │                    ↓                                         │   ║
║   │  │              z = Σ(wᵢ·xᵢ) + b                               │   ║
║   │  └────────────────────────────────────────────────────────────┘  │   ║
║   │                                                                  │   ║
║   │                        ↓                                         │   ║
║   │              ACTIVATION FUNCTION                                 │   ║
║   │  f(z) = RELU / SIGMOID / TANH / SOFTMAX                        │   ║
║   │                                                                  │   ║
║   │                        ↓                                         │   ║
║   │                    OUTPUT (a)                                    │   ║
║   └───────────────────────────────────────────────────────────────────┘   ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝

Mathematical Formulation:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    z = Σ(wᵢ · xᵢ) + b
          ↑        ↑
      weights   inputs

    a = f(z)
       ↑
   activation function


```

---

## Forward Propagation Flowchart

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                      FORWARD PROPAGATION COMPLETE FLOW                     ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   ┌─────────────────────┐                                                 ║
║   │   1. DATA PREPARATION│                                                 ║
║   │                       │                                                 ║
║   │  • Load training data │                                                 ║
║   │  • Normalize inputs    │                                                 ║
║   │  • Split into batches  │                                                 ║
║   └──────────┬────────────┘                                                 ║
║              ↓                                                              ║
║   ┌─────────────────────┐                                                 ║
║   │   2. INPUT LAYER    │                                                 ║
║   │                       │                                                 ║
║   │  • Receive raw input X│                                                 ║
║   │  • Shape: (batch_size, n_features)                                   ║
║   └──────────┬────────────┘                                                 ║
║              ↓                                                              ║
║   ┌─────────────────────┐                                                 ║
║   │   3. WEIGHTED SUM    │                                                 ║
║   │                       │                                                 ║
║   │  • Multiply inputs by weights: wᵢ·xᵢ                                  ║
║   │  • Sum all products + bias                                            ║
║   │  • z = Σ(wᵢ·xᵢ) + b                                                   ║
║   └──────────┬────────────┘                                                 ║
║              ↓                                                              ║
║   ┌─────────────────────┐                                                 ║
║   │   4. ACTIVATION      │                                                 ║
║   │                       │                                                 ║
║   │  • Apply activation function: a = f(z)                                ║
║   │  • ReLU, Sigmoid, Tanh, etc.                                          ║
║   └──────────┬────────────┘                                                 ║
║              ↓                                                              ║
║   ┌─────────────────────┐                                                 ║
║   │   5. NEXT LAYER      │                                                 ║
║   │                       │                                                 ║
║   │  • Pass activated output to next layer                                ║
║   │  • Repeat steps 3-4 for each hidden layer                             ║
║   └──────────┬────────────┘                                                 ║
║              ↓                                                              ║
║   ┌─────────────────────┐                                                 ║
║   │   6. OUTPUT LAYER    │                                                 ║
║   │                       │                                                 ║
║   │  • Final activation (often Softmax for classification)                 ║
║   │  • Produce prediction ŷ                                               ║
║   └──────────┬────────────┘                                                 ║
║              ↓                                                              ║
║   ┌─────────────────────┐                                                 ║
║   │   7. OUTPUT READY    │                                                 ║
║   │                       │                                                 ║
║   │  • Forward propagation complete                                       ║
║   │  • Ready for loss calculation and backpropagation                    ║
║   └─────────────────────┘                                                 ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝

```

---

## Backpropagation Learning Process

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                      BACKPROPAGATION COMPLETE FLOW                         ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   ┌─────────────────────┐                                                 ║
║   │   1. FORWARD PASS   │ ←───────────────────────────────────────────┐    ║
║   │                       │                                          ↓     ║
║   │  Input → Hidden → Output                                        ├─────┐ ║
║   └──────────┬────────────┘                                         │     │ ║
║              ↓                                                        │     │ ║
║   ┌─────────────────────┐    │   ┌───────────────────────────────────┴─────────┐ ║
║   │   2. LOSS CALCULATION│←─────────────────────────────────────────────────────┤ ║
║   │                       │     Compute loss between prediction ŷ and target y   ║
║   │  • Cross-entropy (classification)                                         │ ║
║   │    L = -[y·log(ŷ) + (1-y)·log(1-ŷ)]                                      │ ║
║   │  • MSE (regression)                                                       │ ║
║   │      L = (y - ŷ)²                                                         │ ║
║   └──────────┬────────────┘     │                                              │ ║
║              ↓                  ├───────────────────────────────────────────────┤ ║
║   ┌─────────────────────┐    │    ┌───────────────────────────────────────────┴───┐ ║
║   │   3. BACKWARD PASS   │←─┼────▶│ Compute gradients using chain rule           │ ║
║   │                       │     │                                              │ ║
║   │  • Start from output layer                                   ∂L/∂w = ∂L/∂a · ∂a/∂z · x ║
║   │    - Calculate error signals                                 ∂L/∂b = ∂L/∂a       ║
║   └──────────┬────────────┘     │                                              │ ║
║              ↓                  ├───────────────────────────────────────────────┤ ║
║   ┌─────────────────────┐    │    ┌───────────────────────────────────────────┴───┐ ║
║   │   4. GRADIENT UPDATE │←─┼────▶│ Update weights and biases                  │ ║
║   │                       │     │                                              │ ║
║   │  • w_new = w_old - learning_rate · ∂L/∂w                              │ ║
║   │    b_new = b_old - learning_rate · ∂L/∂b                               │ ║
║   └──────────┬────────────┘     └───────────────────────────────────────────────┘ ║
║              ↓                                                                      ║
║   ┌─────────────────────┐                                                 ║
║   │   5. REPEAT         │ ← Loop through all training examples            ║
║   │                       │                                                 ║
║   │  • Continue until convergence or max epochs                            ║
║   └─────────────────────┘                                                 ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝

```

---

## Visual Summary: Complete Neural Network Training Cycle

```
╔═══════════════════════════════════════════════════════════════════════════╗
║              COMPLETE NEURAL NETWORK TRAINING CYCLE                        ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║   ┌──────────────────┐     ┌───────────────┐                              ║
║   │  BATCH SIZE: n   │     │ EPOCHS: e     │                              ║
║   └────────┬─────────┘     └───────────────┘                              ║
║            ↓                                                               ║
║   ┌─────────────────────────────────────────────────────────────────────┐  ║
║   │                           TRAINING LOOP                              │  ║
║   ├─────────────────────────────────────────────────────────────────────┤  ║
║   │                                                                     │  ║
║   │  ┌──────────┐     ┌───────────┐      ┌──────────┐                  │  ║
║   │  │ Batch 1  │     │ Batch 2   │      │ ...      │                  │  ║
║   │  │ Forward  │────▶│ Forward   │─────▶│ Forward  │                  │  ║
║   │  └──────────┘     └───────────┘      └──────────┘                  │  ║
║   │                                                                     │  ║
║   │  ┌──────────┐     ┌───────────┐      ┌──────────┐                  │  ║
║   │  │ Batch 1  │     │ Batch 2   │      │ ...      │                  │  ║
║   │  │ Backward │────▶│ Backward  │─────▶│ Backward │                  │  ║
║   │  └──────────┘     └───────────┘      └──────────┘                  │  ║
║   │                                                                     │  ║
║   │  Update weights after each batch (or epoch)                         │  ║
║   │                                                                     │  ║
║   │  ┌─────────────────────────────────────────────────────────────┐   │  ║
║   │  │                      CONVERGENCE CHECK                       │   │  ║
║   │  │  • Loss decreasing?                                          │   │  ║
║   │  │  • Validation accuracy improving?                            │   │  ║
║   │  │  • Early stopping triggered?                                  │   │  ║
║   │  └─────────────────────────────────────────────────────────────┘   │  ║
║   ├─────────────────────────────────────────────────────────────────────┤  ║
║   │                                                                     │  ║
║   └─────────────────────────────────────────────────────────────────────┘  ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝

```

---

## Diagram Legend and Reference Guide

### Symbols Used in All Diagrams:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Symbol | Meaning |
|--------|---------|
| ┌ ─ ─ ┐ | Neuron/Node processing unit |
| → | Direction of data flow (forward propagation) |
| ↓ | Signal passing through connections |
| ══ | Connection with weight parameters |
| └──┬──┘ | Branching point (multiple outputs from one neuron) |
| ┌─────┴─────┐ | Merging point (summation of inputs) |

### Common Mathematical Notation:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Symbol | Meaning | Example |
|--------|---------|---------|
| xᵢ | Input feature i | x₁, x₂, ..., xₙ |
| wᵢⱼ | Weight from neuron j to i | w₁₂ = weight from hidden 2 to output 1 |
| b | Bias term | Added to weighted sum |
| z | Pre-activation value | z = Σ(wᵢ·xᵢ) + b |
| a | Activated output | a = f(z) |
| f() | Activation function | ReLU, Sigmoid, Tanh |

### Layer Naming Convention:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Layer Type | Common Name | Purpose |
|------------|-------------|---------|
| Input | Input Layer | Receives raw data (pixels, text embeddings, etc.) |
| Hidden 1 | First Hidden Layer | Extracts basic features |
| Hidden 2 | Second Hidden Layer | Combines features into patterns |
| ... | Deeper Layers | Higher-level abstractions |
| Output | Output Layer | Produces final prediction/classification |

---

## Quick Reference: Data Flow Summary

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│   INPUT      │───▶│  WEIGHTED SUM  │───▶│ ACTIVATION    │
│   (X)        │     │   + BIAS (z)   │     │   FUNCTION   │
│              │     └───────────────┘     └──────────────┘
│  Raw data    │                                        ↓
│ (pixels, etc.)                            ┌───────────────┐
└──────────────┘                           │   OUTPUT       │
                                          │   PREDICTION   │
                                           └───────────────┘

Data flows left to right through the network layers.
Each neuron performs: z = Σ(weights × inputs) + bias, then applies activation.


```

---

*This document provides visual aids for understanding neural network structures and processes.*
