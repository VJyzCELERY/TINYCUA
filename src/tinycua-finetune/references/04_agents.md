# Computer Use Agents: Research Survey

This document surveys research on computer use agents, focusing on how LLMs can be trained to interact with computers, use tools, and perform autonomous tasks.

---

## 1. Toolformer: Language Models Learn to Use Tools

**Reference**: Toolformer: Language Models Can Teach Themselves to Use Tools  
**Year**: 2023  
**Source**: https://arxiv.org/abs/2302.04761

### Summary
- First major work showing LLMs can learn to use external tools (APIs)
- Self-supervised approach: model discovers when to call tools
- Trained on synthetic data with tool calls
- Tools: calculator, search, translation, calendar APIs

### Key Findings
- Models learn to use tools without explicit supervision
- Tool use improves factual accuracy significantly
- Zero-shot tool use after fine-tuning

### Citation
```
@article{toolformer_2023,
  title={Toolformer: Language Models Can Teach Themselves to Use Tools},
  author={Schick, Timo and Dwivedi-Yu, Jane and others},
  journal={arXiv preprint arXiv:2302.04761},
  year={2023}
}
```

---

## 2. Reflexion: Language Agents with Verbal Reinforcement

**Reference**: Reflexion: Language Agents with Verbal Reinforcement  
**Year**: 2023  
**Source**: https://arxiv.org/abs/2303.11366

### Summary
- Introduces verbal reinforcement for agent learning
- Agent reflects on past errors through written feedback
- No parameter updates - learns from self-generated feedback

### Key Findings
- Improves success rate on AlfWorld tasks
- Can learn new tasks without additional training
- Works with any base LLM

### Citation
```
@article{reflexion_2023,
  title={Reflexion: Language Agents with Verbal Reinforcement},
  author={Shinn, Noah and Labash, Federico and Gopinath, Ashish},
  journal={arXiv preprint arXiv:2303.11366},
  year={2023}
}
```

---

## 3. Visual Agent Benchmark

**Reference**: Visual Agent Benchmark  
**Year**: 2024  
**Source**: https://arxiv.org/abs/2405.10740

### Summary
- Comprehensive benchmark for vision-language agents
- Tests agent capabilities on screenshot understanding
- Tasks: UI navigation, form filling, data extraction

### Key Findings
- Current VLMs struggle with computer use tasks
- Multi-modal reasoning is critical
- Gap between benchmark and real-world use

### Citation
```
@article{visual_agent_2024,
  title={Visual Agent Benchmark},
  author={Various},
  journal={arXiv preprint arXiv:2405.10740},
  year={2024}
}
```

---

## 4. Anthropic Computer Use

**Reference**: Anthropic Computer Use Demo  
**Year**: 2024  
**Source**: https://www.anthropic.com/blog/claude-computer-use-demo

### Summary
- Claude model can interact with computer
- Takes screenshots, performs actions
- Autonomous task completion

### Key Findings
- First commercial implementation of computer use agent
- Uses chain-of-thought for planning actions
- Claude 3.5 outperforms other models

### Citation
```
@article{anthropic_computer_use_2024,
  title={Anthropic Computer Use Demo},
  author={Anthropic},
  year={2024},
  url={https://www.anthropic.com/blog/claude-computer-use-demo}
}
```

---

## 5. Related Research: Agent Frameworks

### AutoGen
- Multi-agent collaboration framework
- Tool use and conversation orchestration

### LangChain Agents
- Popular framework for building LLM agents
- ReAct prompt engineering

### OpenAI Function Calling
- GPT models with native function calling
- Structured tool use without fine-tuning

---

## 6. Training Data for Computer Use Agents

### Key Datasets

| Dataset | Focus | Link |
|---------|-------|------|
| **ToolBench** | Tool use | https://github.com/THUDM/ToolBench |
| **API-Bank** | API calling | https://github.com/AlibabaResearch/DAMO-ConvAI/tree/main/api-bank |
| **ALFWorld** | Embodied AI | https://alfworld.github.io/ |
| **VisualWebArena** | Visual agents | https://visualwebarena.github.io/ |

### Dataset Characteristics
- Tool definitions and descriptions
- Multi-step reasoning chains
- Screen screenshots for VLM agents

---

## 7. Fine-tuning Approaches

### Dataset Format for Computer Use

```json
{
  "instruction": "Click the submit button and enter 'hello'",
  "image": "screenshot.png",
  "tool_calls": [
    {
      "name": "click",
      "args": {"x": 150, "y": 320},
      "result": "Clicked"
    },
    {
      "name": "type",
      "args": {"text": "hello"},
      "result": "Typed"
    }
  ]
}
```

### Key Training Considerations
- Response-only masking (only train on tool outputs)
- Multi-turn conversation format
- Tool call formatting with special tokens

---

## 8. Key Takeaways for Your Thesis

1. **Computer use agents** require:
   - Vision capability for screenshot understanding
   - Tool definition and calling
   - Multi-step reasoning

2. **Training data** needs:
   - Tool manifests with descriptions
   - Screenshot-image pairs
   - Reasoning chains

3. **Best model choice**: Qwen3.5-VL-9B
   - Native multimodal (early fusion)
   - Supports tool calling
   - Fits in 16GB with QLoRA

4. **PEFT method**: QLoRA
   - Fits 9B in 10-12GB
   - Works with vision models
   - Minimal quality loss

---

## 9. Recommended Papers for Further Reading

1. **Toolformer** (2023) - Foundation for tool use
2. **Reflexion** (2023) - Self-reflection agents
3. **Anthropic Computer Use** (2024) - Commercial implementation
4. **VisualWebArena** (2024) - Visual agent benchmark

---

*Last updated: 2026-05-06*