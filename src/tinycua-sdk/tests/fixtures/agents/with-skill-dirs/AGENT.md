---
name: skill-dirs-agent
description: An agent with external skill directories
model: gpt-4o
provider: openai
skills:
  - custom-skill
skill_dirs:
  - /tmp/custom-skills
  - ~/my-skills
auto_load_dependencies: false
tools:
  - search_web
policy:
  max_tool_calls: 15
  temperature: 0.7
---

# Agent Instructions
You are an agent with external skill directories.
