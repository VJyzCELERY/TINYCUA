---
name: agent-with-custom-loop
description: An agent with custom loop configuration for specialized processing
model: gpt-4o-mini
provider: openai
tools:
  - bash
  - read_file
loop:
  type: custom
  class_name: ReasoningLoop
  source: |
    from tinycua_sdk.agent.loops import DefaultLoop
    
    class ReasoningLoop(DefaultLoop):
        """Custom loop with enhanced reasoning capabilities."""
        
        async def process(self, agent, user_input):
            # Add reasoning step before tool execution
            reasoning = await self.think(agent, user_input)
            return await super().process(agent, user_input)
        
        async def think(self, agent, user_input):
            """Think about the best approach."""
            # Custom reasoning logic here
            return reasoning
policy:
  max_tool_calls: 20
  temperature: 0.3
---

# Instructions
You are an agent with custom reasoning capabilities.

Think through complex problems step by step:
1. Understand the requirements
2. Plan your approach
3. Execute methodically
4. Verify results

Use the thinking process to provide well-reasoned responses.