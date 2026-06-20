#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# WildClawBench - Simple Benchmark Runner
#
# Usage:
#   bash benchmark.sh              # Interactive setup (first time) or run
#   bash benchmark.sh run          # Run with saved config
#   bash benchmark.sh config       # Change provider configuration
#   bash benchmark.sh build        # Build agent Docker images
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
# Build Agent Docker Images
# ---------------------------------------------------------------------------
do_build() {
  local agent="${1:-all}"
  
  echo ""
  echo "=========================================="
  echo "  Building Agent Docker Images"
  echo "=========================================="
  echo ""
  
  cd "${PROJECT_DIR}"
  
  case "$agent" in
    hermes)
      log_info "Building Hermes agent image..."
      docker compose --profile hermes build hermes-agent
      ;;
    opencode)
      log_info "Building OpenCode agent image..."
      docker compose --profile opencode build opencode-agent
      ;;
    openclaw)
      log_info "Building OpenClaw agent image..."
      docker compose --profile openclaw build openclaw-agent
      ;;
    all)
      log_info "Building all agent images..."
      docker compose --profile hermes --profile opencode --profile openclaw build
      ;;
    *)
      log_error "Unknown agent: $agent"
      echo "  Valid agents: hermes, opencode, openclaw, all"
      exit 1
      ;;
  esac
  
  echo ""
  log_success "Build complete!"
  echo ""
}

# ---------------------------------------------------------------------------
# Interactive Setup Wizard
# ---------------------------------------------------------------------------
do_setup_wizard() {
  echo ""
  echo "=========================================="
  echo "  WildClawBench - Provider Setup"
  echo "=========================================="
  
  # --- Agent Provider Setup ---
  echo ""
  echo "  [Agent Provider]"
  echo ""
  read -p "  Provider name (e.g. lm-studio, ollama, openrouter): " provider_name
  provider_name="${provider_name:-lm-studio}"
  
  read -p "  Base URL (e.g. http://localhost:1234/v1): " api_base
  api_base="${api_base:-http://localhost:1234/v1}"
  
  read -p "  Model name: " model
  model="${model:-qwen3.5-9b}"
  
  read -p "  API key (leave empty for local): " api_key
  api_key="${api_key:-}"
  
  # --- Judge Provider Setup ---
  echo ""
  echo "  [Judge Provider] (for grading responses)"
  echo ""
  read -p "  Judge provider name (e.g. openrouter, lm-studio): " judge_name
  judge_name="${judge_name:-openrouter}"
  
  read -p "  Judge base URL (e.g. https://openrouter.ai/api/v1): " judge_base_url
  judge_base_url="${judge_base_url:-https://openrouter.ai/api/v1}"
  
  read -p "  Judge model name: " judge_model
  judge_model="${judge_model:-openai/gpt-5.4}"
  
  read -p "  Judge API key: " judge_api_key
  judge_api_key="${judge_api_key:-}"
  
  # --- Runtime Settings ---
  echo ""
  echo "  Task timeout:"
  echo "    - Enter seconds (e.g. 600 for 10 minutes)"
  echo "    - Type 'unlimited' for no timeout"
  echo ""
  local timeout
  read -p "  Timeout (default: 600): " timeout
  timeout="${timeout:-600}"
  
  # Save configuration to .env
  save_env_config "$provider_name" "$api_base" "$model" "$api_key" "$judge_name" "$judge_base_url" "$judge_model" "$judge_api_key" "$timeout"
  
  echo ""
  log_success "Configuration saved to .env"
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
save_env_config() {
  local provider="$1"
  local api_base="$2"
  local model="$3"
  local api_key="${4:-}"
  local judge_name="${5:-openrouter}"
  local judge_base_url="${6:-https://openrouter.ai/api/v1}"
  local judge_model="${7:-openai/gpt-5.4}"
  local judge_api_key="${8:-}"
  local timeout="${9:-600}"
  
  cat > "${PROJECT_DIR}/.env" << EOF
# Agent Benchmark Environment Configuration
# Generated by benchmark.sh

# Provider (agent harness)
PROVIDER_NAME=${provider}
PROVIDER_BASE_URL=${api_base}
PROVIDER_MODEL=${model}
PROVIDER_API_KEY=${api_key}

# Judge Provider (for grading responses)
JUDGE_PROVIDER_NAME=${judge_name}
JUDGE_PROVIDER_BASE_URL=${judge_base_url}
JUDGE_PROVIDER_MODEL=${judge_model}
JUDGE_PROVIDER_API_KEY=${judge_api_key}

# Local search
SEARXNG_URL=http://localhost:8888

# Runtime
LOG_LEVEL=INFO
TIMEOUT=${timeout}
EOF
}

# ---------------------------------------------------------------------------
# Load Configuration
# ---------------------------------------------------------------------------
load_config() {
  local env_file="${PROJECT_DIR}/.env"
  
  if [[ ! -f "$env_file" ]] || [[ ! -s "$env_file" ]]; then
    return 1
  fi
  
  # Source the .env file
  set -a
  source "$env_file"
  set +a
  
  # Check if required vars are set
  if [[ -z "${PROVIDER_NAME:-}" || -z "${PROVIDER_BASE_URL:-}" ]]; then
    return 1
  fi
  
  # Export for child processes
  export PROVIDER_NAME="${PROVIDER_NAME}"
  export PROVIDER_API_BASE="${PROVIDER_BASE_URL}"
  export PROVIDER_MODEL="${PROVIDER_MODEL}"
  export PROVIDER_TIMEOUT="${TIMEOUT:-600}"
  
  # Export judge provider settings
  export JUDGE_PROVIDER_NAME="${JUDGE_PROVIDER_NAME:-openrouter}"
  export JUDGE_PROVIDER_BASE_URL="${JUDGE_PROVIDER_BASE_URL:-https://openrouter.ai/api/v1}"
  export JUDGE_PROVIDER_MODEL="${JUDGE_PROVIDER_MODEL:-openai/gpt-5.4}"
  export JUDGE_PROVIDER_API_KEY="${JUDGE_PROVIDER_API_KEY:-}"
  
  return 0
}

# ---------------------------------------------------------------------------
# Show Current Config
# ---------------------------------------------------------------------------
show_config() {
  local env_file="${PROJECT_DIR}/.env"
  
  if [[ -f "$env_file" ]]; then
    # Source to get values
    set -a
    source "$env_file"
    set +a
    
    echo ""
    echo "Current configuration:"
    echo "  Provider: ${PROVIDER_NAME:-lm-studio}"
    echo "  Base URL: ${PROVIDER_BASE_URL:-http://localhost:1234/v1}"
    echo "  Model:    ${PROVIDER_MODEL:-qwen3.5-9b}"
    echo ""
    echo "  Judge:    ${JUDGE_PROVIDER_NAME:-openrouter}"
    echo "  Judge URL: ${JUDGE_PROVIDER_BASE_URL:-https://openrouter.ai/api/v1}"
    echo "  Judge Model: ${JUDGE_PROVIDER_MODEL:-openai/gpt-5.4}"
    echo ""
    echo "  Timeout:  ${TIMEOUT:-600}"
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
  
  # Parse command line overrides
  local category="all"
  local agent=""
  local parallel=1
  local timeout=""
  
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --category) category="$2"; shift 2 ;;
      --agent)    agent="$2"; shift 2 ;;
      --parallel) parallel="$2"; shift 2 ;;
      --model)    PROVIDER_MODEL="$2"; shift 2 ;;
      --api-base) PROVIDER_API_BASE="$2"; shift 2 ;;
      --timeout)  timeout="$2"; shift 2 ;;
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
  echo "  Base URL : ${PROVIDER_API_BASE}"
  echo "  Model    : ${PROVIDER_MODEL}"
  echo "  Judge    : ${JUDGE_PROVIDER_NAME} / ${JUDGE_PROVIDER_MODEL}"
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
  export PROVIDER_NAME PROVIDER_API_BASE PROVIDER_MODEL
  export JUDGE_PROVIDER_NAME JUDGE_PROVIDER_BASE_URL JUDGE_PROVIDER_MODEL JUDGE_PROVIDER_API_KEY
  
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
    
    # Build command with optional timeout
    local cmd="uv run python3 eval/run_batch.py --harness ${harness} --category ${category} --parallel ${parallel} --model ${PROVIDER_MODEL}"
    # Use CLI timeout if provided, otherwise use config timeout
    local effective_timeout="${timeout:-${PROVIDER_TIMEOUT:-600}}"
    if [[ -n "$effective_timeout" ]]; then
      cmd="${cmd} --timeout ${effective_timeout}"
    fi
    
    # Run and capture output to display progress
    local output_file=$(mktemp)
    local exit_code=0
    
    eval "$cmd" 2>&1 | tee "$output_file" || exit_code=$?
    
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
  build [agent]   Build agent Docker images (hermes|opencode|openclaw|all)
  status          Show results
  searxng         Manage SearXNG (up|down|status)
  help            Show this help

Options:
  --category CAT  Task category (default: all)
  --agent AGENT   Run specific agent only (openclaw|opencode|hermesagent)
  --model MODEL   Override model name
  --api-base URL  Override API base URL
  --parallel N    Parallel tasks per agent (default: 1)
  --timeout N     Task timeout: seconds or 'unlimited' (default: 600)

Examples:
  bash benchmark.sh                    # First time: setup wizard
  bash benchmark.sh run                # Run with saved config
  bash benchmark.sh config             # Change provider
  bash benchmark.sh build              # Build all agent images
  bash benchmark.sh build hermes       # Build Hermes only
  bash benchmark.sh run --model llama3 # Override model
  bash benchmark.sh run --agent opencode
  bash benchmark.sh searxng up         # Start SearXNG manually
  bash benchmark.sh searxng down       # Stop SearXNG
  bash benchmark.sh searxng status     # Check SearXNG status

Docker Compose Profiles:
  The agent images are built using Docker Compose profiles:
    --profile hermes    Hermes agent
    --profile opencode  OpenCode agent
    --profile openclaw  OpenClaw agent

Configuration:
  Configuration is saved to .env file.
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
    build)   shift; do_build "${1:-all}" ;;
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
