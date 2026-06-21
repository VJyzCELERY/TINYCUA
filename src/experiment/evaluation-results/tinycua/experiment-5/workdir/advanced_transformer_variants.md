# Advanced Transformer Variants: BERT, GPT, Vision Transformers (ViT), T5 Architectures

## Table of Contents
1. [BERT - Bidirectional Encoder Representations from Transformers](#bert)
2. [GPT - Generative Pre-trained Transformers](#gpt)
3. [Vision Transformers (ViT)](#vit)
4. [T5 - Text-to-Text Transfer Transformer](#t5)
5. [Comparison Table](#comparison-table)

---

## <a name="bert"></a>1. BERT - Bidirectional Encoder Representations from Transformers

### Overview
BERT (Bidirectional Encoder Representations from Transformers), introduced by Google in 2018, revolutionized natural language processing by pre-training deep bidirectional representations from unlabeled text using both left and right context simultaneously.

**Paper:** [Devlin et al., "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding" (2018)](https://arxiv.org/abs/1810.04805)

### Architecture

#### Key Components
- **Transformer Encoder Only**: BERT uses only the encoder layers from the Transformer architecture (no decoder)
- **Bidirectional Attention**: Unlike traditional models that process text in one direction, BERT attends to both left and right context simultaneously
- **12 layers** (Base), **24 layers** (Large) with 768/1024 hidden dimensions respectively
- **Multi-head Self-Attention**: Uses 12 attention heads per layer

#### Input Representations
BERT combines three types of embeddings:
1. **Token Embeddings**: Word/piece representations
2. **Positional Encodings**: Absolute position information (learned or sinusoidal)
3. **Segment IDs**: For distinguishing between different sentences (in MLM task)

### Pre-Training Tasks

#### 1. Masked Language Modeling (MLM)
- **Objective**: Predict masked tokens in a sentence
- **Process**: Randomly mask 15% of input tokens, predict the original token
- **Bidirectional Context**: Models can use both left and right context for prediction
- **Example**: "[MASK] is a [MASK] that helps you learn."

#### 2. Next Sentence Prediction (NSP)
- **Objective**: Predict whether sentence B follows sentence A
- **Process**: Given two sentences, predict if they are consecutive in the original text
- **Note**: NSP was later removed from BERT as it didn't help much on downstream tasks

### Fine-Tuning Strategy

BERT is designed for fine-tuning rather than direct inference:

1. **Load pre-trained weights** (e.g., `bert-base-uncased`)
2. **Add task-specific output layer** (classification head, etc.)
3. **Continue training** on downstream task dataset
4. **Share embeddings** between pre-training and fine-tuning phases

#### Common Fine-Tuning Tasks
- Text Classification (sentiment analysis, named entity recognition)
- Question Answering (SQuAD format)
- Natural Language Inference (MNLI, RTE)
- Named Entity Recognition (NER)

### BERT Variants

| Variant | Description | Parameters |
|---------|-------------|------------|
| `bert-base` | 12 layers, 768 hidden dims | ~110M |
| `bert-large` | 24 layers, 1024 hidden dims | ~340M |
| `distilbert` | Distilled to 33% size, faster inference | ~66M |
| `roberta` | Improved pre-training (RoPE positions) | ~125M |
| `albert` | Attention is all you need (parameter sharing) | ~40-70M |

### Use Cases
- Sentiment analysis
- Text classification
- Named entity recognition
- Question answering
- Natural language inference
- Machine translation (with fine-tuning)

---

## <a name="gpt"></a>2. GPT - Generative Pre-trained Transformers

### Overview
GPT (Generative Pre-trained Transformer), introduced by OpenAI in 2018, is a decoder-only transformer designed for autoregressive language generation. Unlike BERT's bidirectional approach, GPT generates text one token at a time using causal masking.

**Paper:** [Radford et al., "Improving Language Understanding by Generative Pre-Training" (2018)](https://openai.com/gpt/)

### Architecture

#### Key Components
- **Transformer Decoder Only**: Uses only decoder layers with causal attention
- **Causal Masking**: Prevents tokens from attending to future positions
- **Autoregressive Generation**: Generates text token-by-token
- **KV Caching**: Optimizes inference by caching key-value matrices

#### Self-Attention Mechanism
In GPT, the self-attention mechanism is modified with causal masking:

```python
# Causal attention mask ensures token i can only attend to tokens j <= i
mask = torch.triu(torch.tensor(-float('inf')), diagonal=1)  # Upper triangle masked
```

#### Architecture Evolution

| Model | Layers | Hidden Dims | Heads | Parameters |
|-------|--------|-------------|-------|------------|
| GPT-1 | 12 | 768 | 12 | ~117M |
| GPT-2 | 48/34 | 1024/1280 | 16/25 | 1.5B / 1.2B |
| GPT-3 | 96 (Ada), 116 (Curie) | 768-1536 | 12-32 | 175B - 1760B+ |

### Pre-Training: Autoregressive Language Modeling

#### Objective
Predict the next token in a sequence given all previous tokens.

**Process:**
1. Input: `[token_1, token_2, ..., token_n]`
2. Model predicts probability distribution for `token_{n+1}`
3. Sample from distribution to generate new text

**Loss Function:** Cross-entropy loss over next-token prediction

```python
# Example training objective
loss = -log(P(next_token | all_previous_tokens))
```

### Fine-Tuning Strategies

#### 1. Supervised Fine-Tuning (SFT)
- Load pre-trained GPT weights
- Add task-specific instructions/prompts
- Train on labeled data with prompt-completion format

**Example:**
```
Prompt: "What is the capital of France?"
Completion: "Paris is the capital of France."
```

#### 2. Instruction Tuning (GPT-3.5/4 style)
- Format inputs as natural language instructions
- Train on instruction-following datasets
- Improves ability to follow complex prompts

#### 3. Continued Pre-training
- Further pre-train on domain-specific data
- Example: Fine-tune GPT on medical texts for healthcare applications

### Key Features

| Feature | Description |
|---------|-------------|
| **Causal Attention** | Tokens only attend to previous positions |
| **Autoregressive** | Generates text sequentially, one token at a time |
| **In-context Learning** | Can perform tasks without fine-tuning by providing examples in prompt |
| **Zero-shot/Few-shot** | Generalizes to unseen tasks via prompting |

### Use Cases
- Text generation (creative writing, summarization)
- Code generation (GitHub Copilot)
- Chatbots and conversational AI
- Content creation
- Data augmentation
- Translation (with domain-specific fine-tuning)

---

## <a name="vit"></a>3. Vision Transformers (ViT)

### Overview
Vision Transformer (ViT), introduced by Google in 2020, adapts the Transformer architecture originally designed for NLP to computer vision tasks. ViT treats images as sequences of patches rather than grids of pixels.

**Paper:** [Dosovitskiy et al., "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scalable Sizes" (2020)](https://arxiv.org/abs/2010.11929)

### Architecture

#### Key Innovation: Patch Embedding
Instead of using CNNs, ViT divides images into fixed-size patches and processes them as sequences:

**Process:**
1. **Split image**: Divide H×W image into N×N patches of size P×P pixels
   - Example: 224×224 image with 16×16 patches → 196 patches (224/16 = 14)
2. **Flatten patches**: Each patch becomes a flat vector of P²×C dimensions
3. **Linear projection**: Project each patch to D-dimensional embedding space
4. **Add embeddings**: Combine with learnable class token and positional embeddings

```python
# Patch embedding formula
patch_embedding = Linear(P × P × C, D)  # e.g., 16×16×3 → 768
```

#### Architecture Components

| Component | Description |
|-----------|-------------|
| **Class Token** | Learnable embedding prepended to patch embeddings for classification |
| **Positional Embeddings** | Absolute position information (unlike CNNs which have implicit spatial inductive bias) |
| **Transformer Encoder** | Standard Transformer encoder with multi-head self-attention |
| **MLP Head** | Final classification layer after pooling/class token |

### Pre-Training Strategy

#### Self-Supervised Learning
ViT uses contrastive pre-training or masked image modeling:

1. **Masked Autoencoders (MAE)**: Mask 75% of patches, reconstruct them
2. **Contrastive Learning**: Learn representations that distinguish different images
3. **ImageNet Pre-training**: Train on millions of ImageNet images for downstream transfer

### ViT Variants

| Variant | Description | Key Feature |
|---------|-------------|-------------|
| **ViT-B/16** | Base model, 16×16 patches | Standard ViT |
| **ViT-L/14** | Large model, 14×14 patches | Higher resolution |
| **DeiT** | Data-efficient image transformer | Uses distillation techniques |
| **Swin Transformer** | Hierarchical with shifted windows | Efficient for high-resolution images |
| **Perceiver IO** | General-purpose sequence-to-sequence | Handles variable-length inputs |

### CLIP and Vision-Language Models

CLIP (Contrastive Language-Image Pre-training) combines ViT with text transformers:

```
┌─────────────┐     Contrastive Learning     ┌─────────────┐
│  Image      │ ────────────────────►        │   Text      │
│    ViT      │                              │   Transformer│
│  (ViT-L/14) │                              │              │
└─────────────┘                              └─────────────┘
```

**Training:** Contrastive loss aligns image and text embeddings from same samples.

### Use Cases
- Image classification
- Object detection (with detection heads)
- Semantic segmentation
- Visual question answering
- Zero-shot image recognition
- Image captioning
- Medical imaging analysis

---

## <a name="t5"></a>4. T5 - Text-to-Text Transfer Transformer

### Overview
T5 (Text-to-Text Transfer Transformer), introduced by Google in 2019, reformulates all NLP tasks as text-to-text problems: "Input text → Output text". This unified framework simplifies model architecture and training.

**Paper:** [Raffel et al., "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer" (2019)](https://arxiv.org/abs/1910.10683)

### Architecture

#### Key Components
- **Full Encoder-Decoder**: Unlike BERT/GPT, T5 uses both encoder and decoder
- **Unidirectional Causal Attention**: Both encoder and decoder use causal masking
- **No Positional Embeddings in Decoder**: Uses relative positions via attention
- **LayerNorm Placement**: Applied before sub-layers (unlike original Transformer)

```python
# T5 Architecture Flow:
Input Text ──► Encoder ──► Cross-Attention ──► Decoder ──► Output Text
           ↑              ↓                      ↑
      Embeddings  Cross-Attention   Embeddings   Causal Masking
```

#### Training Paradigm: Text-to-Text
All tasks are reformulated as sequence-to-sequence problems:

| Task | Original Format | T5 Format |
|------|----------------|-----------|
| Classification | Input → Label | "classify: [text] → label" |
| QA | Question + Context → Answer | "qa: [context] [question] → answer" |
| Translation | Source → Target | "translate English to French: [source] → target" |

### Pre-Training Task

#### Span Corruption (Masked Language Modeling)
T5 pre-trains by masking spans of text rather than single tokens:

**Process:**
1. Mask 15% of input tokens in contiguous spans
2. Predict span using surrounding context and decoder
3. Learn to reconstruct masked text from partial information

```python
# Example: Original → Masked → Prediction
Original: "The cat sat on the mat."
Masked:   "The [MASK] sat on the [MASK]."
Prediction:"cat" "mat"
```

### Fine-Tuning Strategy

#### Universal Encoder-Decoder Architecture
T5 can be fine-tuned for any NLP task with minimal changes:

1. **Load pre-trained T5 weights** (e.g., `t5-base`, `t5-large`)
2. **Format input as text-to-text prompt**
3. **Train on downstream task data**
4. **Use same architecture across tasks**

#### Prompt Engineering
T5 excels at prompt-based learning:

```python
# Few-shot example without additional training
prompt = "Summarize these reviews:\n" + reviews + "\nSummary:"
model.predict(prompt)  # Generates summary directly
```

### T5 Variants

| Variant | Parameters | Description |
|---------|------------|-------------|
| `t5-small` | ~60M | Fast, lightweight |
| `t5-base` | ~220M | Good balance (baseline) |
| `t5-large` | ~770M | High performance |
| `t5-3b` | ~3.1B | Large scale |
| `flan-t5-small/large/xxl` | 60M - 11B | Instruction-tuned variants |

### Flan-T5: Instruction Tuning

Flan-T5 is a family of instruction-tuned T5 models:

**Training:**
- Pre-train on ~37k instruction-response pairs
- Format all tasks as natural language instructions
- Examples: "Write a poem about...", "Summarize the following text..."

### Use Cases
- Machine translation
- Question answering (SQuAD, Natural Questions)
- Text summarization
- Named entity recognition
- Text classification (sentiment, spam detection)
- Paraphrase generation
- Dialogue systems
- Code generation

---

## <a name="comparison-table"></a>5. Comparison Table

| Feature | BERT | GPT | ViT | T5 |
|---------|------|-----|-----|-----|
| **Architecture** | Encoder-only | Decoder-only | Encoder-only (Vision) | Full Encoder-Decoder |
| **Attention Direction** | Bidirectional | Causal (unidirectional) | Bidirectional | Causal (both encoder & decoder) |
| **Pre-training Task** | MLM + NSP | Autoregressive LM | Contrastive/Masked Image | Span Corruption |
| **Primary Use Case** | Understanding (classification, QA) | Generation (text completion) | Vision tasks (image recognition) | Universal NLP (sequence-to-sequence) |
| **Input Format** | Tokens with segment IDs | Text prompts | Patches + class token | Text-to-text prompts |
| **Output Format** | Classification logits | Generated tokens | Image embeddings/classes | Generated text sequences |
| **Key Innovation** | Bidirectional context | Autoregressive generation | Images as patch sequences | Unified text-to-text paradigm |

### Summary Table: Architectural Differences

```
┌─────────────────┬──────────────────────┬──────────────────────┬─────────────────────┐
│   Model         │    Attention Mask    │      Flow            │     Best For        │
├─────────────────┼──────────────────────┼──────────────────────┼─────────────────────┤
│ BERT            │ Bidirectional (full) │ Input ←→ Output      │ NLP Understanding   │
│                 │                      │                      │                     │
│ GPT             │ Causal (forward only)│ Input → Generate     │ Text Generation     │
│                 │                      │                      │                     │
│ ViT             │ Bidirectional        │ Image Patches → Class│ Computer Vision     │
│                 │                      │                      │                     │
│ T5              │ Causal Encoder+Decoder│ Text In → Text Out  │ Universal NLP Tasks │
└─────────────────┴──────────────────────┴──────────────────────┴─────────────────────┘
```

### When to Use Each Model

| Scenario | Recommended Model | Reason |
|----------|-------------------|--------|
| Text Classification | BERT | Bidirectional context captures semantics better |
| Text Generation | GPT | Autoregressive decoding produces coherent text |
| Image Recognition | ViT | Native vision transformer with patch processing |
| Machine Translation | T5 | Encoder-decoder architecture designed for seq2seq |
| Question Answering | BERT or T5 | Both excel depending on task (BERT for extraction, T5 for generation) |
| Zero-shot Learning | GPT/CLIP | Strong generalization via pre-training |

---

## References and Further Reading

### Original Papers
1. **BERT**: Devlin et al., "BERT: Pre-training of Deep Bidirectional Transformers" (2018)
   - URL: https://arxiv.org/abs/1810.04805

2. **GPT**: Radford et al., "Improving Language Understanding by Generative Pre-Training" (2018)
   - URL: https://openai.com/gpt/

3. **ViT**: Dosovitskiy et al., "An Image is Worth 16x16 Words" (2020)
   - URL: https://arxiv.org/abs/2010.11929

4. **T5**: Raffel et al., "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer" (2019)
   - URL: https://arxiv.org/abs/1910.10683

### Hugging Face Documentation
- BERT: https://huggingface.co/docs/transformers/model_doc/bert
- GPT: https://huggingface.co/docs/transformers/model_doc/gpt2
- ViT: https://huggingface.co/models?search=ViT
- T5: https://huggingface.co/docs/transformers/model_doc/t5

### Key Libraries
- **Transformers**: Hugging Face's model library for all architectures
- **PyTorch/TensorFlow**: Frameworks for training custom implementations
- **PEFT**: Parameter-efficient fine-tuning (LoRA, QLoRA)

---

*Document generated as part of Comprehensive Study Documentation on Neural Networks and Transformers.*
