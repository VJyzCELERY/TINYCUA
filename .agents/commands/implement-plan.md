---
description: Executes implementation plan using the Software Engineer workflow
subtask: true
---

Execute an implementation plan from implementation-plan.md and task.md.

**Target Directory**: $1

## Instructions

1. **Locate implementation files**: Find implementation-plan.md and task.md in `$1`
2. **Read implementation-plan.md**: Understand the proposed changes and architecture
3. **Read task.md**: Review the task checklist
4. **Execute Tasks**: Implement each task in order, following TDD workflow:
   - Write tests first (RED)
   - Implement code to pass tests (GREEN)
   - Refactor if needed
   - Run tests to verify
5. **Update Progress**: Update task.md as tasks are completed (use `[x]` for completed, `[ ]` for pending)
6. **Report Status**: Report progress against the task checklist

## TDD Workflow
- **RED**: Write failing tests first
- **GREEN**: Write minimal code to pass tests
- **REFACTOR**: Improve code quality while keeping tests green

## Constraints
- Do NOT modify implementation-plan.md - it serves as the source of truth
- Only update task.md to track progress
- Follow existing codebase conventions

## Available Commands
- Use `/review-project <directory>` to review your implementation
- Use `/validate-review <review-file>` to validate review findings

Begin by reading the implementation-plan.md and task.md, then start executing tasks in order.