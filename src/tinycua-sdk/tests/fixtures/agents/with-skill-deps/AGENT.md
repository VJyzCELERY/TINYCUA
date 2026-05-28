---
name: skill-deps-agent
description: An agent with skill dependencies
model: gpt-4o
provider: openai
skills:
  - web-researcher
auto_load_dependencies: true
tools:
  - search_web
policy:
  max_tool_calls: 15
  temperature: 0.7
---

# Agent Instructions
You are a research assistant with skill dependencies.
