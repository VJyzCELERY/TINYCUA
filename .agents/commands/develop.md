---
description: Initiates the development workflow - coordinates the team
subtask: true
---

Coordinate the entire development workflow.

**Development Query**: $ARGUMENTS
**Development Directory**: $1 (optional - defaults to "dev", use "specs" to store in git-tracked folder)

## Directory Convention

**Default**: Use `dev/` folder for development artifacts (ignored by git)
**Optional**: Use `specs/` folder if you want development tracked in git history

The development directory contains:
- prd.md - Product Requirements Document
- roadmap.md - Roadmap with stages
- {STAGE_ID}-{STAGE_NAME}/ - Each stage folder

## Stage Naming Convention

Each roadmap stage MUST follow this format:
```
{STAGE_ID}-{STAGE_NAME}
```

Examples:
- `01-user-authentication`
- `02-api-endpoints`
- `03-database-migration`
- `04-payment-integration`

Each stage folder contains:
- `specs.md` - Implementation specifications
- `design.md` - Design document
- `implementation-plan.md` - Implementation plan
- `task.md` - Task checklist

## Instructions

1. **Determine Directory**: Use `$1` if provided, otherwise default to "dev"
2. **Understand the Request**: Analyze what the user wants to build
3. **Initialize Development Directory**: Create the folder structure:
   ```
   {dev_dir}/
   ├── prd.md
   ├── roadmap.md
   └── {STAGE_ID}-{STAGE_NAME}/
       ├── specs.md
       ├── design.md
       ├── implementation-plan.md
       └── task.md
   ```
4. **Gather Context**: Read the existing project to understand the codebase
5. **Write PRD**: Create prd.md with product overview, user stories, requirements
6. **Create Roadmap**: Break into stages using format `{ID}-{NAME}`
7. **Execute Stages**: For each stage:
   a. Create specs.md + design.md
   b. Create implementation-plan.md + task.md
   c. Implement the code
   d. Review and test
8. **Final Review**: Check for outstanding issues
9. **Report Completion**: Summarize results

## Alternative Commands
- `/implementation-plan <dir>` - Creates implementation-plan.md from spec.md/design.md
- `/implement-plan <dir>` - Executes implementation plan
- `/review-project <dir>` - Reviews project and generates report at `./reviews/`
- `/validate-review <file>` - Validates review findings and updates `./reviews/` report
- `/review-implement <file>` - Implements fixes and updates `./reviews/` statuses

## Important
- Stage IDs must be zero-padded (01, 02, 03...)
- Use kebab-case for stage names (lowercase with hyphens)
- Development docs go to the specified directory
- Source code goes to project's source directories

Begin by understanding the query and creating the development structure.