---
description: Creates implementation-plan.md and task.md from spec.md and design.md
subtask: true
---

Create an implementation plan from existing spec.md and design.md files.

**Target Directory**: $1

## Instructions

1. **Locate spec.md**: Search for spec.md in `$1` or its subdirectories
2. **Locate design.md**: Find design.md in the same directory as spec.md
3. **Read and Analyze**: Read both files to understand the requirements and design
4. **Create implementation-plan.md**: Generate a detailed implementation plan in the same directory as spec.md with:
   - Context (priority, effort, dependencies)
   - Proposed Changes (with NEW/MODIFY/DELETE actions)
   - Architecture Changes
   - Verification Plan
   - Dependencies
   - Risks and Mitigations
5. **Create task.md**: Generate a task checklist with these phases:
   - Implementation Phase
   - Testing Phase
   - Verification Phase
   - Documentation Phase
   - Review and Merge
6. **Use Task IDs**: Add `<!-- id: N -->` tags to each task for tracking

## Important
- Do NOT make any code changes - only create planning documents
- Output files must be in the same directory as spec.md
- Make the implementation plan detailed and actionable

## Templates Reference
- Implementation plan template: `~/.config/opencode/templates/implementation-plan.md`
- Task template: `~/.config/opencode/templates/task.md`

Begin by locating spec.md and design.md, then create the implementation plan and tasks.