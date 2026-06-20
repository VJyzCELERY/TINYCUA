#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# WildClawBench - Simple Benchmark Runner
#
# Usage:
#   bash benchmark.sh              # Interactive setup (first time) or run
#   bash benchmark.sh run          # Run with saved config
#   bash benchmark.sh config       # Change provider configuration
#   bash benchmark.sh status       # Show results
#   bash benchmark.sh help         # Show help
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
CONFIG_FILE="${PROJECT_DIR}/.provider-config"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------------------------------------------------------------------------
# Docker Check & Start
# ---------------------------------------------------------------------------
ensure_docker() {
  # Check if Docker is installed
  if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed"
    log_info "Install from: https://docs.docker.com/get-docker/"
    exit 1
  fi
  
  # Check if Docker daemon is running
  if ! docker info &> /dev/null 2>&1; then
    log_warn "Docker daemon is not running. Starting Docker..."
    
    # Try to start Docker Desktop on macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
      open -a Docker
      log_info "Waiting for Docker to start..."
      
      # Wait up to 60 seconds
      local timeout=60
      local elapsed=0
      while ! docker info &> /dev/null 2>&1; do
        sleep 2
        elapsed=$((elapsed + 2))
        if [[ $elapsed -ge $timeout ]]; then
          log_error "Docker failed to start within ${timeout} seconds"
          log_info "Please start Docker Desktop manually and try again"
          exit 1
        fi
        echo -n "."
      done
      echo ""
      log_success "Docker is ready"
    else
      # Linux - try systemctl
      if command -v systemctl &> /dev/null; then
        sudo systemctl start docker
        sleep 3
        if ! docker info &> /dev/null 2>&1; then
          log_error "Failed to start Docker"
          exit 1
        fi
        log_success "Docker is ready"
      else
        log_error "Please start Docker manually"
        exit 1
      fi
    fi
  else
    log_info "Docker is running"
  fi
}

# ---------------------------------------------------------------------------
# SearXNG Management
# ---------------------------------------------------------------------------
SEARXNG_URL="http://localhost:8888"

start_searxng() {
  log_info "Starting SearXNG..."
  
  cd "${PROJECT_DIR}"
  
  # Pull latest image and start container
  if docker compose up -d searxng 2>&1; then
    log_success "SearXNG container started"
  else
    log_error "Failed to start SearXNG"
    return 1
  fi
  
  # Wait for health check
  log_info "Waiting for SearXNG to be ready..."
  local timeout=30
  local elapsed=0
  while ! curl -sf "${SEARXNG_URL}/healthz" > /dev/null 2>&1; do
    sleep 2
    elapsed=$((elapsed + 2))
    if [[ $elapsed -ge $timeout ]]; then
      log_error "SearXNG failed to start within ${timeout} seconds"
      return 1
    fi
    echo -n "."
  done
  echo ""
  
  log_success "SearXNG is ready at ${SEARXNG_URL}"
  export SEARXNG_URL
}

stop_searxng() {
  log_info "Stopping SearXNG..."
  cd "${PROJECT_DIR}"
  docker compose down searxng 2>&1
  log_success "SearXNG stopped"
}

searxng_status() {
  if curl -sf "${SEARXNG_URL}/healthz" > /dev/null 2>&1; then
    log_success "SearXNG is running at ${SEARXNG_URL}"
    return 0
  else
    log_warn "SearXNG is not running"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Interactive Setup Wizard
# ---------------------------------------------------------------------------
do_setup_wizard() {
  echo ""
  echo "=========================================="
  echo "  WildClawBench - Provider Setup"
  echo "=========================================="
  echo ""
  echo "Choose your LLM provider:"
  echo ""
  echo "  1) LM Studio (local)     - http://localhost:1234/v1"
  echo "  2) Ollama (local)        - http://localhost:11434/v1"
  echo "  3) vLLM (local/remote)   - http://localhost:8000/v1"
  echo "  4) OpenRouter (cloud)    - https://openrouter.ai/api/v1"
  echo "  5) Custom local server   - Your own localhost port"
  echo "  6) Custom remote API     - Full URL endpoint"
  echo ""
  
  local choice
  read -p "  Enter choice [1-6] (default: 1): " choice
  choice="${choice:-1}"
  
  local provider_name="lm-studio"
  local api_base="http://localhost:1234/v1"
  local api_key_env="LM_STUDIO_API_KEY"
  
  case "$choice" in
    1)
      provider_name="lm-studio"
      api_base="http://localhost:1234/v1"
      api_key_env="LM_STUDIO_API_KEY"
      ;;
    2)
      provider_name="ollama"
      api_base="http://localhost:11434/v1"
      api_key_env="OLLAMA_API_KEY"
      ;;
    3)
      provider_name="vllm"
      api_base="http://localhost:8000/v1"
      api_key_env="VLLM_API_KEY"
      ;;
    4)
      provider_name="openrouter"
      api_base="https://openrouter.ai/api/v1"
      api_key_env="OPENROUTER_API_KEY"
      ;;
    5)
      provider_name="local-custom"
      echo ""
      echo "  Enter your local server port or URL:"
      echo "  Examples: 8080, 5000, http://localhost:9090/v1"
      echo ""
      read -p "  Port or URL: " custom_input
      custom_input="${custom_input:-8080}"
      
      # If just a port number, build the URL
      if [[ "$custom_input" =~ ^[0-9]+$ ]]; then
        api_base="http://localhost:${custom_input}/v1"
      else
        api_base="${custom_input}"
      fi
      api_key_env="LOCAL_CUSTOM_API_KEY"
      ;;
    6)
      provider_name="custom"
      read -p "  Enter API base URL: " api_base
      api_base="${api_base:-http://localhost:8000/v1}"
      read -p "  Enter API key env var name (or leave empty): " api_key_env
      api_key_env="${api_key_env:-CUSTOM_API_KEY}"
      ;;
    *)
      log_error "Invalid choice"
      exit 1
      ;;
  esac
  
  echo ""
  echo "  Provider: ${provider_name}"
  echo "  API Base: ${api_base}"
  echo ""
  
  # Check if local server is running
  if [[ "$provider_name" == "lm-studio" || "$provider_name" == "ollama" || "$provider_name" == "vllm" || "$provider_name" == "local-custom" ]]; then
    check_local_server "$provider_name" "$api_base"
  fi
  
  # Get model name
  local model
  read -p "  Enter model name (default: qwen3.5-9b): " model
  model="${model:-qwen3.5-9b}"
  
  # Get API key if needed
  local api_key=""
  if [[ "$provider_name" == "openrouter" ]] || [[ "$provider_name" == "custom" ]]; then
    read -p "  Enter API key (or press Enter to skip): " api_key
  fi
  
  # Save configuration
  save_config "$provider_name" "$api_base" "$api_key_env" "$model" "$api_key"
  
  echo ""
  log_success "Configuration saved to ${CONFIG_FILE}"
  echo ""
}

# ---------------------------------------------------------------------------
# Check Local Server
# ---------------------------------------------------------------------------
check_local_server() {
  local provider="$1"
  local api_base="$2"
  
  log_info "Checking if ${provider} server is running at ${api_base}..."
  
  # Check if server is responding
  if curl -s --connect-timeout 2 "${api_base}/models" > /dev/null 2>&1; then
    log_success "${provider} server is running"
    return 0
  fi
  
  log_warn "${provider} server is not running"
  echo ""
  
  if [[ "$provider" == "local-custom" ]]; then
    echo "  Please start your server at ${api_base} before running benchmarks."
    echo ""
    read -p "  Press Enter when server is ready..."
  else
    echo "  Would you like me to start ${provider}?"
    echo ""
    
    local start_choice
    read -p "  Start ${provider}? [Y/n]: " start_choice
    start_choice="${start_choice:-Y}"
    
    if [[ "$start_choice" == "Y" || "$start_choice" == "y" ]]; then
      start_local_server "$provider"
    else
      echo ""
      log_warn "Please start ${provider} manually before running benchmarks"
      echo "  LM Studio: /Users/jonaja29/.lmstudio/bin/lms server start"
      echo "  Ollama: ollama serve"
      echo "  vLLM: vllm serve <model>"
      echo ""
      read -p "  Press Enter when server is ready..."
    fi
  fi
}

# ---------------------------------------------------------------------------
# Start Local Server
# ---------------------------------------------------------------------------
start_local_server() {
  local provider="$1"
  
  case "$provider" in
    lm-studio)
      log_info "Starting LM Studio..."
      if command -v lms &> /dev/null; then
        lms server start &
        sleep 3
        log_success "LM Studio started"
      elif [[ -f "/Users/jonaja29/.lmstudio/bin/lms" ]]; then
        /Users/jonaja29/.lmstudio/bin/lms server start &
        sleep 3
        log_success "LM Studio started"
      else
        log_error "LM Studio CLI not found"
        echo "  Please start LM Studio manually"
        return 1
      fi
      ;;
    ollama)
      log_info "Starting Ollama..."
      if command -v ollama &> /dev/null; then
        ollama serve &
        sleep 3
        log_success "Ollama started"
      else
        log_error "Ollama not installed"
        echo "  Install: brew install ollama"
        return 1
      fi
      ;;
    vllm)
      log_error "vLLM must be started manually"
      echo "  Example: vllm serve <model> --port 8000"
      return 1
      ;;
  esac
}

# ---------------------------------------------------------------------------
# Save Configuration
# ---------------------------------------------------------------------------
save_config() {
  local provider="$1"
  local api_base="$2"
  local api_key_env="$3"
  local model="$4"
  local api_key="${5:-}"
  
  cat > "$CONFIG_FILE" << EOF
# WildClawBench Provider Configuration
# Generated by benchmark.sh

PROVIDER=${provider}
API_BASE=${api_base}
API_KEY_ENV=${api_key_env}
MODEL=${model}
EOF
  
  # Save API key to .env if provided
  if [[ -n "$api_key" ]]; then
    local env_file="${PROJECT_DIR}/.env"
    if [[ -f "$env_file" ]]; then
      # Update existing key
      if grep -q "^${api_key_env}=" "$env_file"; then
        sed -i.bak "s/^${api_key_env}=.*/${api_key_env}=${api_key}/" "$env_file"
        rm -f "${env_file}.bak"
      else
        echo "${api_key_env}=${api_key}" >> "$env_file"
      fi
    else
      echo "${api_key_env}=${api_key}" > "$env_file"
    fi
    log_info "API key saved to .env"
  fi
}

# ---------------------------------------------------------------------------
# Load Configuration
# ---------------------------------------------------------------------------
load_config() {
  if [[ ! -f "$CONFIG_FILE" ]]; then
    return 1
  fi
  
  # Check if file has content
  if [[ ! -s "$CONFIG_FILE" ]]; then
    return 1
  fi
  
  # Source the config file
  source "$CONFIG_FILE"
  
  # Check if required vars are set
  if [[ -z "${PROVIDER:-}" || -z "${API_BASE:-}" ]]; then
    return 1
  fi
  
  # Export for child processes
  export PROVIDER_NAME="${PROVIDER:-lm-studio}"
  export PROVIDER_API_BASE="${API_BASE:-http://localhost:1234/v1}"
  export PROVIDER_API_KEY_ENV="${API_KEY_ENV:-LM_STUDIO_API_KEY}"
  export PROVIDER_MODEL="${MODEL:-qwen3.5-9b}"
  
  # Load .env file if it exists
  local env_file="${PROJECT_DIR}/.env"
  if [[ -f "$env_file" ]]; then
    set -a
    source "$env_file"
    set +a
  fi
  
  return 0
}

# ---------------------------------------------------------------------------
# Show Current Config
# ---------------------------------------------------------------------------
show_config() {
  if [[ -f "$CONFIG_FILE" ]]; then
    echo ""
    echo "Current configuration:"
    echo "  Provider: ${PROVIDER:-lm-studio}"
    echo "  API Base: ${API_BASE:-http://localhost:1234/v1}"
    echo "  Model:    ${MODEL:-qwen3.5-9b}"
    echo ""
  else
    echo ""
    echo "No configuration found. Run: bash benchmark.sh config"
    echo ""
  fi
}

# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------
do_run() {
  # Ensure Docker is running
  ensure_docker
  
  # Load config or run setup wizard
  if ! load_config; then
    echo ""
    log_info "No configuration found. Let's set up your LLM provider."
    do_setup_wizard
    load_config
  fi
  
  # Check if local server is running
  if [[ "$PROVIDER_NAME" == "lm-studio" || "$PROVIDER_NAME" == "ollama" || "$PROVIDER_NAME" == "vllm" ]]; then
    if ! curl -s --connect-timeout 2 "${PROVIDER_API_BASE}/models" > /dev/null 2>&1; then
      log_warn "${PROVIDER_NAME} server is not running"
      echo ""
      read -p "  Start ${PROVIDER_NAME} now? [Y/n]: " start_choice
      start_choice="${start_choice:-Y}"
      
      if [[ "$start_choice" == "Y" || "$start_choice" == "y" ]]; then
        start_local_server "$PROVIDER_NAME"
        sleep 3
      else
        log_error "Cannot run benchmark without LLM server"
        exit 1
      fi
    fi
  fi
  
  # Check if API key is needed and not set
  if [[ "$PROVIDER_NAME" == "openrouter" || "$PROVIDER_NAME" == "custom" ]]; then
    local api_key_var="${PROVIDER_API_KEY_ENV:-OPENROUTER_API_KEY}"
    local api_key_value="${!api_key_var:-}"
    
    if [[ -z "$api_key_value" ]]; then
      echo ""
      log_warn "API key not found for ${PROVIDER_NAME}"
      read -p "  Enter API key for ${api_key_var}: " api_key_value
      if [[ -n "$api_key_value" ]]; then
        export "${api_key_var}=${api_key_value}"
        # Save to .env for future use
        local env_file="${PROJECT_DIR}/.env"
        if [[ -f "$env_file" ]]; then
          if grep -q "^${api_key_var}=" "$env_file"; then
            sed -i.bak "s/^${api_key_var}=.*/${api_key_var}=${api_key_value}/" "$env_file"
            rm -f "${env_file}.bak"
          else
            echo "${api_key_var}=${api_key_value}" >> "$env_file"
          fi
        else
          echo "${api_key_var}=${api_key_value}" > "$env_file"
        fi
        log_success "API key saved"
      fi
    fi
  fi
  
  # Parse command line overrides
  local category="all"
  local agent=""
  local parallel=1
  
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --category) category="$2"; shift 2 ;;
      --agent)    agent="$2"; shift 2 ;;
      --parallel) parallel="$2"; shift 2 ;;
      --model)    PROVIDER_MODEL="$2"; shift 2 ;;
      --api-base) PROVIDER_API_BASE="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  
  # Start SearXNG for web search capabilities
  if ! searxng_status > /dev/null 2>&1; then
    start_searxng
  else
    log_success "SearXNG already running"
    export SEARXNG_URL
  fi
  
  # Show what we're running
  echo ""
  echo "=========================================="
  echo "  WildClawBench Benchmark Run"
  echo "=========================================="
  echo "  Provider : ${PROVIDER_NAME}"
  echo "  API Base : ${PROVIDER_API_BASE}"
  echo "  Model    : ${PROVIDER_MODEL}"
  echo "  Category : ${category}"
  echo "  Search   : ${SEARXNG_URL}"
  echo "=========================================="
  echo ""
  
  # Determine which agents to run
  local agents_to_run="openclaw opencode hermesagent"
  if [[ -n "${agent}" ]]; then
    agents_to_run="${agent}"
  fi
  
  # Export for Python scripts
  export PROVIDER_NAME PROVIDER_API_BASE PROVIDER_API_KEY_ENV PROVIDER_MODEL
  
  # Load .env file and export all variables for child processes
  local env_file="${PROJECT_DIR}/.env"
  if [[ -f "$env_file" ]]; then
    while IFS='=' read -r key value; do
      # Skip comments and empty lines
      [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
      export "${key}=${value}"
    done < "$env_file"
  fi
  
  # Run the benchmark
  cd "${PROJECT_DIR}"
  
  for harness in ${agents_to_run}; do
    echo ""
    log_info "Running ${harness}..."
    echo "────────────────────────────────────────"
    
    # Run and capture output to display progress
    local output_file=$(mktemp)
    local exit_code=0
    
    uv run python3 eval/run_batch.py \
      --harness "${harness}" \
      --category "${category}" \
      --parallel "${parallel}" \
      --model "${PROVIDER_MODEL}" 2>&1 | tee "$output_file" || exit_code=$?
    
    # Extract final summary from output
    if [[ -f "$output_file" ]]; then
      local completed=$(grep -oE '\[([0-9]+)/([0-9+)\]' "$output_file" | tail -1 | grep -oE '[0-9]+/[0-9]+' | cut -d/ -f1 || echo "0")
      local total=$(grep -oE '\[([0-9]+)/([0-9+)\]' "$output_file" | tail -1 | grep -oE '[0-9]+/[0-9]+' | cut -d/ -f2 || echo "0")
      local success=$(grep -c "✓" "$output_file" 2>/dev/null || echo "0")
      local failed=$(grep -c "✗" "$output_file" 2>/dev/null || echo "0")
      
      echo ""
      echo "  Progress: ${completed}/${total} tasks completed"
      echo "  Results:  ✓ ${success} passed  ✗ ${failed} failed"
    fi
    
    rm -f "$output_file"
    
    if [[ $exit_code -ne 0 ]]; then
      log_error "${harness} failed with exit code ${exit_code}"
    else
      log_success "${harness} completed"
    fi
  done
  
  echo ""
  echo "=========================================="
  log_success "Benchmark complete!"
  echo "  Results: ${PROJECT_DIR}/output/"
  echo "=========================================="
}

# ---------------------------------------------------------------------------
# CONFIG - Change provider settings
# ---------------------------------------------------------------------------
do_config() {
  do_setup_wizard
}

# ---------------------------------------------------------------------------
# STATUS
# ---------------------------------------------------------------------------
do_status() {
  local output_dir="${PROJECT_DIR}/output"
  
  echo ""
  echo "=========================================="
  echo "  WildClawBench Results"
  echo "=========================================="
  
  if [[ ! -d "$output_dir" ]]; then
    echo "  No results found"
    echo "=========================================="
    return
  fi
  
  for harness in openclaw opencode hermesagent; do
    local harness_dir="${output_dir}/${harness}"
    if [[ -d "$harness_dir" ]]; then
      echo ""
      echo "  ${harness}:"
      local count=$(find "$harness_dir" -name "score.json" 2>/dev/null | wc -l | tr -d ' ')
      echo "    Tasks completed: ${count}"
    fi
  done
  
  echo ""
  echo "=========================================="
}

# ---------------------------------------------------------------------------
# HELP
# ---------------------------------------------------------------------------
do_help() {
  cat <<'EOF'
WildClawBench - Simple Benchmark Runner

Usage:
  bash benchmark.sh [command] [options]

Commands:
  (no command)    First time: setup wizard | Otherwise: run benchmark
  run             Run benchmark with saved configuration
  config          Change provider configuration
  status          Show results
  searxng         Manage SearXNG (up|down|status)
  help            Show this help

Options:
  --category CAT  Task category (default: all)
  --agent AGENT   Run specific agent only (openclaw|opencode|hermesagent)
  --model MODEL   Override model name
  --api-base URL  Override API base URL
  --parallel N    Parallel tasks per agent (default: 1)

Examples:
  bash benchmark.sh                    # First time: setup wizard
  bash benchmark.sh run                # Run with saved config
  bash benchmark.sh config             # Change provider
  bash benchmark.sh run --model llama3 # Override model
  bash benchmark.sh run --agent opencode
  bash benchmark.sh searxng up         # Start SearXNG manually
  bash benchmark.sh searxng down       # Stop SearXNG
  bash benchmark.sh searxng status     # Check SearXNG status

Supported Providers:
  - LM Studio (local): http://localhost:1234/v1
  - Ollama (local): http://localhost:11434/v1
  - vLLM (local/remote): http://localhost:8000/v1
  - OpenRouter (cloud): https://openrouter.ai/api/v1
  - Custom local: Your own localhost server (just type port number)
  - Custom remote: Any API endpoint (full URL)

SearXNG (Local Search):
  SearXNG provides web search capabilities without API keys.
  It starts automatically when running benchmarks.
  Manual control: bash benchmark.sh searxng {up|down|status}
  Access search API: http://localhost:8888/search?q=query&format=json

Docker:
  Docker is started automatically when running benchmarks.
  If Docker is not running, the script will wait up to 60 seconds.

Configuration:
  Configuration is saved to .provider-config and reused.
  Use 'bash benchmark.sh config' to change settings.
EOF
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
main() {
  # Create .provider-config directory if needed
  touch "$CONFIG_FILE" 2>/dev/null || true
  
  case "${1:-}" in
    run)     shift; do_run "$@" ;;
    config)  do_config ;;
    status)  do_status ;;
    searxng)
      shift
      case "${1:-}" in
        up|start)   start_searxng ;;
        down|stop)  stop_searxng ;;
        status)     searxng_status ;;
        *)          log_error "Usage: benchmark.sh searxng {up|down|status}"; exit 1 ;;
      esac
      ;;
    help|-h|--help) do_help ;;
    "")      do_run ;;
    *)       log_error "Unknown command: $1"; do_help; exit 1 ;;
  esac
}

main "$@"
