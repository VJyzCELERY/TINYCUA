# TUI Component Unit Tests

## Overview
This directory contains unit tests for TinyCUA's TUI (Text User Interface) and Client/Service components.

## Test Files

| File | Coverage |
|------|----------|
| `test_tui.py` | TUI widgets and app (OutputPanel, StatusBar, TinyCUAApp) |
| `test_cli_commands.py` | CLI command handlers (run, deploy, chat, tui) |
| `test_repl.py` | REPL functionality and command processing |
| `test_user_config.py` | User configuration (load, save, defaults) |
| `conftest.py` | Shared fixtures |

## Running Tests

```bash
# Run all unit tests
pytest src/tinycua/tests/unit/ -v

# Run with coverage
pytest src/tinycua/tests/unit/ --cov=tinycua --cov-report=term-missing

# Run specific test file
pytest src/tinycua/tests/unit/test_tui.py -v

# Run with specific keyword
pytest src/tinycua/tests/unit/ -k "test_output"
```

## Test Patterns Used

1. **Fixtures** - Use `conftest.py` for shared test fixtures
2. **Mocks** - Mock external dependencies (PromptSession, console, backend)
3. **Class-based** - Group tests by component using test classes
4. **Descriptive names** - Test names describe behavior, not implementation

## Default Model
Tests use `qwen/qwen3.5-9b` via an OpenAI-compatible endpoint as the default model configuration.