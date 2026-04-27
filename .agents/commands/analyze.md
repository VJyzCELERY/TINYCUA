---
description: Analyzes the project structure and runs system tests to verify everything works
subtask: true
---

Analyze the project structure and run system tests to verify everything works.

**Project to Analyze**: $1
**Test Focus (Optional)**: $2 (specific tests to run, e.g., "tests", "build", "lint")

If no focus is provided, run all test scenarios.

## Instructions

1. **Understand the Project**: Analyze the project structure, dependencies, and architecture
   - Use Glob to list files
   - Use Read to examine key configuration files

2. **Determine Test Scenarios**: Based on $2:
   - If "tests" or no focus: include Test Suite
   - If "build" or no focus: include Build Process
   - If "lint" or no focus: include Linting
   - If "install" or no focus: include Fresh Installation
   - If "type" or no focus: include Type Checking

3. **Run Tests**: Execute each test scenario:
   - Use Bash to run commands
   - Capture output and results

4. **Create Report**: Generate system test report at `{project_dir}/system-test-report.md`

5. **Report Completion**: Summarize findings

## Important
- Run actual test commands - don't assume results
- Document any errors or failures

Begin by analyzing the project structure and then running tests.