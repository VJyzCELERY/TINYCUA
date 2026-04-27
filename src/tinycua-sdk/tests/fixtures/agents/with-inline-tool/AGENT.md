---
name: inline-tool-agent
tools:
  - tool: |
      @tool
      def custom_adder(a: int, b: int) -> int:
          """Add two numbers."""
          return a + b
---

# Instructions
Use the custom adder tool.
