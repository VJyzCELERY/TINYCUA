# Deep Learning Architectures Overview: CNNs for Vision, RNNs/LSTMs/GRUs for Sequences

## Table of Contents
1. [Convolutional Neural Networks (CNNs)](#convolutional-neural-networks-cnns)
   - [What are CNNs?](#what-are-cnns)
   - [Key Components & Architecture](#key-components--architecture)
   - [Common Layer Types](#common-layer-types)
   - [Popular CNN Architectures](#popular-cnn-architectures)
2. [Recurrent Neural Networks (RNNs)](#recurrent-neural-networks-rnns)
   - [What are RNNs?](#what-are-rnns)
   - [Basic RNN Structure](#basic-rnn-structure)
   - [Limitations of Basic RNNs](#limitations-of-basic-rnns)
3. [Long Short-Term Memory (LSTM)](#long-short-term-memory-lstm)
   - [What are LSTMs?](#what-are-lstms)
   - [The Three Gates](#the-three-gates)
   - [State Representation](#state-representation)
4. [Gated Recurrent Units (GRU)](#gated-recurrent-units-gru)
   - [What are GRUs?](#what-are-grus)
   - [Simplified Gate Structure](#simplified-gate-structure)
5. [Comparison Table: CNN vs RNN/LSTM/GRU](#comparison-table-cnn-vs-rnnlstmgru)
6. [Use Cases & Applications](#use-cases--applications)

---

## Convolutional Neural Networks (CNNs)

### What are CNNs?

Convolutional Neural Networks (CNNs), also known as convnets or covnets, are deep learning architectures specifically designed for processing structured grid-like data such as images. They form the foundation of modern computer vision and image processing tasks.

**Key Characteristics:**
- **Spatial hierarchy**: CNNs automatically learn hierarchical features from raw pixels to complex object parts
- **Translation invariance**: Same feature detection regardless of position in input (thanks to weight sharing)
- **Parameter efficiency**: Convolution operations share weights across spatial locations, reducing parameters vs fully connected networks

**Primary Applications:**
- Image classification
- Object detection
- Image segmentation
- Facial recognition
- Medical image analysis
- Autonomous vehicle perception

### Key Components & Architecture

A typical CNN architecture consists of the following components:

```
Input Image → Convolutional Layer → Activation → Pooling Layer → 
Convolutional Layer → Activation → Pooling Layer → ... → Fully Connected Layers → Output
```

#### Core Operations:

1. **Convolution**: Applies learnable filters (kernels) to extract features at different scales
2. **Activation**: Introduces non-linearity (ReLU, Leaky ReLU, etc.)
3. **Pooling**: Reduces spatial dimensions while preserving important information
4. **Fully Connected Layers**: Aggregate learned features for final classification/regression

### Common Layer Types

#### 1. Convolutional Layer
- Applies multiple filters to extract different feature types
- Parameters: weights (kernel matrices) + biases per filter
- Output size depends on kernel size, stride, and padding
- **Weight sharing** reduces parameters significantly

#### 2. Activation Functions
| Type | Formula | Properties |
|------|---------|------------|
| ReLU | f(x) = max(0, x) | Computationally efficient, introduces non-linearity |
| Leaky ReLU | f(x) = max(αx, x) | Allows small negative slopes to prevent "dying neurons" |
| Sigmoid | f(x) = 1/(1+e^(-x)) | Bounded output [0,1], used for binary classification |
| Tanh | f(x) = (e^(2x)-1)/(e^(2x)+1) | Bounded output [-1,1] |

#### 3. Pooling Layers
- **Max Pooling**: Takes maximum value in each pooling window; preserves dominant features
- **Average Pooling**: Takes average; provides smoothing effect
- Reduces spatial dimensions by factor of stride (typically 2×)
- Helps with overfitting and translation invariance

#### 4. Fully Connected (Dense) Layers
- Connect every neuron from previous layer to all neurons in current layer
- Used near output for classification/regression tasks
- High parameter count; typically placed after pooling reduces dimensions

### Popular CNN Architectures

| Architecture | Year | Key Innovation | ImageNet Top-1 Accuracy |
|--------------|------|----------------|-------------------------|
| LeNet-5 | 1998 | First practical CNN for digit recognition | - |
| AlexNet | 2012 | Deep network, ReLU, dropout | ~60% |
| VGG | 2014 | Small conv kernels (3×3), depth | ~73.8% |
| ResNet | 2015 | Skip connections/residual learning | ~92.7% |
| EfficientNet | 2019 | Compound scaling of width/depth/resolution | ~84% |

**ResNet Architecture Highlights:**
- Introduces **skip connections** (residual blocks) that bypass one or more layers
- Allows training of very deep networks (hundreds/thousands of layers)
- Solves the "vanishing gradient" problem in deep networks

---

## Recurrent Neural Networks (RNNs)

### What are RNNs?

Recurrent Neural Networks (RNNs) are neural network architectures designed to handle **sequential data**. Unlike CNNs that process inputs independently, RNNs maintain an internal "memory" of previous information through hidden states.

**Key Characteristics:**
- **Sequential processing**: Processes input step-by-step (time steps or sequence positions)
- **Hidden state**: Carries information from previous time steps to current computation
- **Bidirectional variants**: Can process sequences forward and backward for context

**Primary Applications:**
- Language modeling
- Machine translation
- Speech recognition
- Time series prediction
- Text generation
- Sentiment analysis

### Basic RNN Structure

```
Input sequence: x₁, x₂, ..., xₜ
Hidden states:  h₁, h₂, ..., hₜ

At each time step t:
    hₜ = f(W·xₜ + U·hₜ₋₁ + b)
    
Where:
- W: weights from input to hidden state
- U: weights from previous hidden state (recurrent connections)
- b: bias term
- f: activation function (typically tanh or ReLU)
```

**Key Insight:** The same parameters (W, U, b) are reused at each time step, making RNNs parameter-efficient for sequences of any length.

### Basic RNN Limitations

#### 1. Vanishing Gradient Problem
- Gradients diminish exponentially as they propagate back through many time steps
- Makes it difficult to learn long-term dependencies
- Network struggles to connect events separated by many steps

#### 2. Exploding Gradient Problem
- Gradients can grow unbounded during training
- Causes unstable training and weight updates
- Requires gradient clipping to mitigate

#### 3. Limited Context Window
- Standard RNNs struggle with sequences longer than ~50-100 time steps
- Information from early inputs may be lost by the time it matters later in sequence

### When Basic RNN Works Well:
- Short-term dependencies (recent context)
- Simple sequential patterns
- Small vocabulary or limited sequence length

---

## Long Short-Term Memory (LSTM)

### What are LSTMs?

Long Short-Term Memory networks (LSTMs) are a sophisticated variant of RNNs designed to overcome the vanishing/exploding gradient problems. They introduce **gated mechanisms** that allow selective control over information flow through time.

**Key Innovation:**
- Can learn dependencies across hundreds or thousands of time steps
- Maintains long-term context effectively
- State-of-the-art (until Transformers) for many sequence tasks

### The Three Gates

LSTMs use three specialized gates to regulate information:

#### 1. Forget Gate
```python
# Decides what information to discard from cell state
fₜ = σ(W_f · [hₜ₋₁, xₜ] + b_f)
# Where σ is sigmoid (outputs values in [0,1])
```
- Values close to 1: "keep this information"
- Values close to 0: "forget this information"

#### 2. Input Gate
```python
# Decides what new information to store
iₜ = σ(W_i · [hₜ₋₁, xₜ] + b_i)
C̃ₜ = tanh(W_c · [hₜ₋₁, xₜ] + b_c)  # Candidate cell state
```
- iₜ: controls how much to update the cell state
- C̃ₜ: candidate new information

#### 3. Output Gate
```python
# Decides what to output based on current cell state
oₜ = σ(W_o · [hₜ₋₁, xₜ] + b_o)
hₜ = oₜ * Cₜ  # Hidden state is filtered cell state
```

### LSTM Cell Structure Visualization

```
                    ┌─────────────┐
   Input (xₜ) ────→│            │
                  →│  Forget    │─────→ fₜ
   Previous        │ Gate      │       │
   Hidden          └───────────┘       ↓
   State (hₜ₋₁) ──→                    ┌─────────────┐
                              ┌───────→│            │
                              │  Input │───────→ iₜ
                              │ Gate   │         │
                              └────────┴─────────↓
                                                  C̃ₜ (candidate)
                                                  ↓
                                         ┌─────────────────┐
                                         │ Cell State     │←───────┐
                                         │ (Cₜ)           │       │
                                         └─────────────────┘       ↓
                                                                     hₜ
                                                  ┌─────────────┐      ↑
   Output            ───────────────────────────→│  Output    │───────→ oₜ
   Gate         ────────────────────────────────→│   Gate     │
          (filters cell state)                   └─────────────┘
```

**Key Points:**
- **Cell State (Cₜ)**: Main information highway; flows unchanged through time when gates allow
- **Hidden State (hₜ)**: Output representation used for predictions and next step input
- Gates use sigmoid activation (outputs 0-1) to control flow
- Cell state uses tanh for bounded values (-1 to 1)

### LSTM Advantages Over Basic RNNs:
✓ Can remember information over long sequences  
✓ Selective memory through gates  
✓ Robust training with stable gradients  
✓ State-of-the-art performance on many sequence tasks  

---

## Gated Recurrent Units (GRU)

### What are GRUs?

Gated Recurrent Units (GRUs) are another RNN variant that combines the best aspects of LSTMs and basic RNNs, using a simplified gate structure with fewer parameters.

**Key Innovation:**
- Merges cell state and hidden state into single representation
- Uses update gate to balance old and new information
- Maintains gating mechanism for selective memory

### Simplified Gate Structure

GRUs use two gates:

#### 1. Reset Gate (rₜ)
```python
# Determines how much past information to forget when computing candidate
rₜ = σ(W_r · [hₜ₋₁, xₜ] + b_r)
```
- Controls how much of previous state influences new candidate computation

#### 2. Update Gate (zₜ)
```python
# Decides how much to update hidden state with new information
zₜ = σ(W_z · [hₜ₋₁, xₜ] + b_z)
```
- Values close to 1: "use current input heavily"
- Values close to 0: "keep previous hidden state"

#### GRU Update Equation:
```python
# Candidate new state (using reset gate for context)
C̃ₜ = tanh(W · [rₜ ⊙ hₜ₋₁, xₜ] + b)

# New hidden state is weighted combination of old and candidate
hₜ = zₜ * hₜ₋₁ + (1 - zₜ) * C̃ₜ
```

### GRU vs LSTM Comparison:

| Aspect | LSTM | GRU |
|--------|------|-----|
| Parameters | More (3 gates, separate cell/hidden state) | Fewer (2 gates, single state) |
| Complexity | Higher | Lower |
| Training Speed | Slower | Faster |
| Performance | Slightly better on complex tasks | Comparable to LSTM |

---

## Comparison Table: CNN vs RNN/LSTM/GRU

| Aspect | CNN | RNN | LSTM | GRU |
|--------|-----|-----|------|-----|
| **Data Type** | Images, grids | Sequences | Sequences | Sequences |
| **Parameter Sharing** | Spatial (weights shared across positions) | Temporal (same weights each time step) | Temporal + Gated | Temporal + Gated |
| **Memory** | Limited (local receptive fields) | Long-term via hidden state | Very long via cell state gates | Long via update gate |
| **Directionality** | Bidirectional CNNs possible | Unidirectional by default | Can be bidirectional | Can be bidirectional |
| **Parallelization** | Excellent (convolutions parallelizable) | Poor (sequential dependency) | Good with LSTM cells | Good with GRU cells |
| **Training Speed** | Fast (highly parallelized) | Slow (sequential) | Moderate | Faster than LSTM |
| **Typical Use Cases** | Image recognition, segmentation | Language modeling, time series | Complex sequences, translation | NLP tasks needing efficient training |

---

## Use Cases & Applications

### CNN Applications:

1. **Image Classification**: Identify what objects appear in an image (e.g., "cat", "dog")
2. **Object Detection**: Locate and classify multiple objects with bounding boxes
3. **Semantic Segmentation**: Assign class label to each pixel
4. **Face Recognition**: Verify/identify individuals from facial features
5. **Medical Imaging**: Detect tumors, fractures in X-rays/MRI scans

**Example CNN Architecture for Image Classification:**
```
Input: 28×28 grayscale image → 
Conv(3×3) → ReLU → MaxPool(2×2) → Conv(3×3) → ReLU → MaxPool(2×2) → 
Conv(3×3) → ReLU → MaxPool(2×2) → Flatten → Dense(128, ReLU) → Dropout → Dense(10, softmax)
```

### RNN/LSTM/GRU Applications:

1. **Machine Translation**: Translate text from one language to another
2. **Text Generation**: Write creative content, complete sentences
3. **Speech Recognition**: Convert audio signals to text transcripts
4. **Sentiment Analysis**: Determine positive/negative sentiment in reviews
5. **Time Series Forecasting**: Predict stock prices, weather patterns
6. **Chatbots/Conversational AI**: Maintain conversation context

**Example LSTM Architecture for Language Modeling:**
```
Input: Character embeddings (or word vectors) → 
Embedding Layer → LSTM Bidirectional [Forward + Backward] → 
Concatenate → Dense(softmax over vocabulary)
```

---

## Key Takeaways

### CNNs are the choice when:
- ✓ Working with images or grid-based data
- ✓ Need to detect spatial patterns and objects
- ✓ Require translation invariance (object position doesn't matter)
- ✓ Can leverage parallel computation for training speed

### RNNs/LSTMs/GRUs are the choice when:
- ✓ Dealing with sequences (text, audio, time series)
- ✓ Context from previous elements matters
- ✓ Information needs to persist across many time steps
- ✓ Order of input is important (A before B means different than B before A)

### Modern Note:
While CNNs and RNNs were dominant for years, **Transformers** have become the state-of-the-art architecture for NLP tasks due to their self-attention mechanism enabling parallel training and handling long-range dependencies more effectively. However, CNNs remain essential for vision tasks, and hybrid models often combine these architectures' strengths.

---

## Further Reading

### Key Papers:
- **CNN**: "ImageNet Classification with Deep Convolutional Neural Networks" (AlexNet, 2012)
- **ResNet**: "Deep Residual Learning for Image Recognition" (He et al., 2015)
- **LSTM**: "Long Short-Term Memory" (Hochreiter & Schmidhuber, 1997)
- **GRU**: "Learning Phrase Representations using RNN Encoder-Decoder" (Cho et al., 2014)

### Recommended Resources:
- [PyTorch CNN Tutorial](https://pytorch.org/tutorials/beginner/blitz/cifar10_tutorial.html)
- [Keras Sequential API Examples](https://keras.io/examples/)
- [3Blue1Brown Neural Networks (YouTube)](https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6RIs84gY7_2e50S2aO7I)

---

*Document generated for: Research on Neural Networks and Transformers - Comprehensive Study Documentation*
*Task: Deep Learning Architectures Overview: CNNs for vision, RNNs/LSTMs/GRUs for sequences*
