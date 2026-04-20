---
description: Initiates the development workflow - coordinates the team
subtask: true
---

Coordinate the entire development workflow.

**Development Query**: $ARGUMENTS

## Instructions

1. **Understand the Request**: Analyze what the user wants to build
2. **Initialize Development Directory**: Create the dev folder structure
   - `{dev_dir}/stages/stage-N/` for each stage
3. **Gather Context**: Read the existing project to understand the codebase and conventions
4. **Write PRD**: Create a Product Requirements Document with:
   - Product overview and goals
   - User stories with acceptance criteria
   - Functional requirements
   - Non-functional requirements
5. **Create Roadmap**: Break the PRD into numbered stages with deliverables
6. **Execute Stages**: For each stage:
   a. Create specs.md + design.md (act as Implementation Planner)
   b. Review and approve the plan
   c. Implement the code (act as Software Engineer using TDD)
   d. Review the implementation
   e. Test the implementation
7. **Final Review**: Check for outstanding issues and assign fixes
8. **Signal Completion**: Report final status

## Alternative Commands (Use When Appropriate)
- `/implementation-plan <directory>` - Creates implementation-plan.md and task.md from spec.md and design.md
- `/implement-plan <directory>` - Executes implementation plan
- `/review-project <directory>` - Review a project directory and generate a report
- `/validate-review <review-file>` - Validate findings from a previous review
- `/review-implement <review-file>` - Implement fixes for review findings

## Constraints
- All development documentation MUST be written to the dev directory
- Source code changes should be in the project's source directories

## Templates
- Implementation plan template: `~/.config/opencode/templates/implementation-plan.md`
- Task template: `~/.config/opencode/templates/task.md`
- Review template: `~/.config/opencode/templates/REVIEW-template.md`

Begin by understanding the query, gathering project context, and creating the PRD and roadmap.