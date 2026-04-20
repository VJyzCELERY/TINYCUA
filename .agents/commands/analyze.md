---
description: Analyzes the project structure and runs system tests to verify everything works
subtask: true
---

Analyze the project structure and run system tests to verify everything works.

**Project to Analyze**: $ARGUMENTS

## Instructions

1. **Understand the Project**: Analyze the project structure, dependencies, and architecture
   - Use Glob to list files
   - Use Read to examine key configuration files (package.json, pyproject.toml, Makefile, etc.)
   - Identify the tech stack and build tools

2. **Identify Test Scenarios**: Determine what scenarios need testing based on project type:
   - Fresh Installation
   - Development Server
   - Build Process
   - Test Suite
   - Linting
   - Type Checking
   - Runtime Execution

3. **Run Tests**: Execute each test scenario:
   - Use Bash to run commands
   - Capture output and results
   - Note any failures

4. **Create Report**: Generate a comprehensive system test report at `{project_dir}/system-test-report.md`:
   ```markdown
   # System Test Report: [Project Name]

   **Date**: [YYYY-MM-DD]
   **Project**: [path]

   ## Test Results

   | Scenario | Status | Notes |
   |----------|--------|-------|
   | Installation | PASS/FAIL | |
   | Build | PASS/FAIL | |
   | Tests | PASS/FAIL | |
   | Linting | PASS/FAIL | |
   | Type Check | PASS/FAIL | |
   | Runtime | PASS/FAIL | |

   ## Summary

   [Overall assessment]
   ```

5. **Report Completion**: Summarize findings

## Important
- Run actual test commands - don't assume results
- Document any errors or failures
- Create the report file using Write tool

Begin by analyzing the project structure and then running tests.