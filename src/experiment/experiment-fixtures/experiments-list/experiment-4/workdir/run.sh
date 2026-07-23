#!/bin/sh
set -eu

: "${PORT:=8765}"
export PORT

install_dependencies() {
  # AGENT_DEPENDENCY_COMMANDS_BEGIN
  uv sync
  # AGENT_DEPENDENCY_COMMANDS_END
}

build_app() {
  # AGENT_BUILD_COMMANDS_BEGIN
  uv run python -m compileall -q .
  # AGENT_BUILD_COMMANDS_END
}

start_app() {
  # AGENT_START_COMMAND_BEGIN
  exec uv run python app.py --port "$PORT"
  # AGENT_START_COMMAND_END
}

install_dependencies
build_app
start_app &
app_pid=$!
trap 'kill "$app_pid" 2>/dev/null || true; wait "$app_pid" 2>/dev/null || true' EXIT INT TERM
sleep 1
kill -0 "$app_pid" 2>/dev/null
printf '%s\n' "$app_pid"
wait "$app_pid"
