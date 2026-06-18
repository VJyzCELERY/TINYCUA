#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# WildClawBench - Setup & Run Script
#
# One script to setup and run benchmarks for all 4 agents sequentially.
# Limited resources: only 1 agent runs at a time, results saved, next agent starts.
#
# Usage:
#   bash benchmark.sh setup              # Full setup (deps, images, data, env)
#   bash benchmark.sh run                # Run all agents sequentially
#   bash benchmark.sh run --model X      # Run all agents with specific model
#   bash benchmark.sh run --category X   # Run specific category for all agents
#   bash benchmark.sh run --agent X      # Run only specific agent
#   bash benchmark.sh status             # Show latest results
#   bash benchmark.sh help               # Show help
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging
log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo -e "${CYAN}[STEP]${NC} $1"; }

# All harnesses
HARNESS_LIST="openclaw opencode hermesagent"

# Get image tarball for harness
get_tarball() {
  case "$1" in
    openclaw)    echo "wildclawbench-ubuntu_v1.3.tar" ;;
    opencode)    echo "wildclawbench-ubuntu_v1.3.tar" ;;
    hermesagent) echo "wildclawbench-hermes-agent-v0.5.tar.gz" ;;
  esac
}

# Get docker image tag for harness
get_tag() {
  case "$1" in
    openclaw)    echo "wildclawbench-ubuntu:v1.3" ;;
    opencode)    echo "wildclawbench-ubuntu:v1.3" ;;
    hermesagent) echo "wildclawbench-hermes-agent:v0.5" ;;
  esac
}

# ─── CHECK (pre-flight) ─────────────────────────────────────────────────────
do_check() {
  echo ""
  echo "=========================================="
  echo "  WildClawBench Pre-flight Check"
  echo "=========================================="
  echo ""

  local all_ok=true

  # 1. Prerequisites
  log_step "Prerequisites"
  if command -v docker &>/dev/null; then
    if docker info &>/dev/null 2>&1; then
      log_success "Docker installed & running"
    else
      log_error "Docker installed but NOT running — start Docker Desktop"
      all_ok=false
    fi
  else
    log_error "Docker not found — install: https://docs.docker.com/get-docker/"
    all_ok=false
  fi

  if command -v uv &>/dev/null; then
    log_success "uv installed"
  else
    log_error "uv not found — install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    all_ok=false
  fi

  if command -v hf &>/dev/null || command -v huggingface-cli &>/dev/null; then
    log_success "huggingface-hub installed"
  else
    log_warn "huggingface-hub not found (needed to download images)"
    echo "         Install: pip install -U 'huggingface_hub[cli]'"
  fi

  if command -v python3 &>/dev/null; then
    log_success "Python $(python3 --version 2>&1 | awk '{print $2}')"
  else
    log_error "Python3 not found"
    all_ok=false
  fi

  # 2. Python dependencies
  echo ""
  log_step "Python dependencies"
  cd "${PROJECT_DIR}"
  if python3 -c "import agent_benchmark" &>/dev/null 2>&1; then
    log_success "agent_benchmark package installed"
  else
    log_warn "agent_benchmark not installed — run: bash benchmark.sh setup"
    all_ok=false
  fi

  # 3. Docker images
  echo ""
  log_step "Docker images"
  local images_missing=0
  for harness in ${HARNESS_LIST}; do
    local tag
    tag=$(get_tag "${harness}")
    if docker image inspect "${tag}" &>/dev/null 2>&1; then
      log_success "${harness}: ${tag}"
    else
      log_warn "${harness}: ${tag} — not loaded (run: bash benchmark.sh setup)"
      images_missing=$((images_missing + 1))
    fi
  done
  if [[ ${images_missing} -gt 0 ]]; then
    all_ok=false
  fi

  # 4. Environment
  echo ""
  log_step "Environment (.env)"
  local env_file="${PROJECT_DIR}/.env"
  if [[ -f "${env_file}" ]]; then
    log_success ".env exists"
    # Check if keys are set (not placeholder)
    source "${env_file}"
    if [[ "${OPENROUTER_API_KEY:-}" == "your_api_key_here" || -z "${OPENROUTER_API_KEY:-}" ]]; then
      log_warn "OPENROUTER_API_KEY not set — edit .env"
      all_ok=false
    else
      log_success "OPENROUTER_API_KEY set"
    fi
    if [[ "${BRAVE_API_KEY:-}" == "your_brave_key_here" || -z "${BRAVE_API_KEY:-}" ]]; then
      log_warn "BRAVE_API_KEY not set (optional, needed for search tasks)"
    else
      log_success "BRAVE_API_KEY set"
    fi
  else
    log_warn ".env not found — run: bash benchmark.sh setup"
    all_ok=false
  fi

  # Summary
  echo ""
  echo "=========================================="
  if [[ "${all_ok}" == "true" ]]; then
    log_success "All checks passed — ready to run benchmarks!"
    echo ""
    echo "  Next: bash benchmark.sh run"
  else
    log_warn "Some issues found — fix them before running benchmarks"
    echo ""
    echo "  Quick fix: bash benchmark.sh setup"
  fi
  echo "=========================================="
  echo ""
}

# ─── SETUP ──────────────────────────────────────────────────────────────────
do_setup() {
  echo ""
  echo "=========================================="
  echo "  WildClawBench Setup"
  echo "=========================================="
  echo ""

  # 1. Check prerequisites
  log_step "1/5 Checking prerequisites..."
  local missing=()
  command -v docker &>/dev/null || missing+=("docker")
  command -v uv &>/dev/null     || missing+=("uv (curl -LsSf https://astral.sh/uv/install.sh | sh)")

  if command -v hf &>/dev/null; then
    log_success "hf CLI installed"
  elif uv run python -c "import huggingface_hub" &>/dev/null 2>&1; then
    log_success "huggingface_hub (Python) installed — will use Python fallback"
  else
    missing+=("huggingface-hub (pip install -U 'huggingface_hub' or: curl -LsSf https://hf.co/cli/install.sh | bash)")
  fi

  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "Missing prerequisites:"
    for m in "${missing[@]}"; do echo "  - $m"; done
    exit 1
  fi
  log_success "Prerequisites OK"

  # 2. Install Python deps
  log_step "2/5 Installing Python dependencies..."
  cd "${PROJECT_DIR}"
  uv pip install -e ".[dev]" 2>/dev/null || uv pip install -e "."
  log_success "Python dependencies installed"

  # 3. Setup .env (must happen before Docker image download for HF_TOKEN)
  log_step "3/5 Setting up environment..."
  local env_file="${PROJECT_DIR}/.env"
  local env_example="${PROJECT_DIR}/.env.example"

  if [[ ! -f "${env_file}" ]]; then
    if [[ -f "${env_example}" ]]; then
      cp "${env_example}" "${env_file}"
      log_success "Created .env from .env.example"
    else
      cat > "${env_file}" <<'ENVEOF'
# WildClawBench Environment Configuration
OPENROUTER_API_KEY=your_api_key_here
BRAVE_API_KEY=your_brave_key_here
DEFAULT_MODEL=openrouter/stepfun/step-3.5-flash:free
JUDGE_MODEL=openai/gpt-5.4
LOG_LEVEL=INFO
TIMEOUT=600
ENVEOF
      log_success "Created .env with defaults"
    fi
    echo ""
    log_warn "Edit .env to set your API keys before running benchmarks"
  else
    log_info ".env already exists"
  fi

  # 4. Download Docker images
  log_step "4/5 Downloading Docker images..."
  local download_dir="${PROJECT_DIR}/Images"
  mkdir -p "${download_dir}"

  for harness in ${HARNESS_LIST}; do
    local tarball
    tarball=$(get_tarball "${harness}")
    local tag
    tag=$(get_tag "${harness}")

    # Check if image already loaded
    if docker image inspect "${tag}" &>/dev/null; then
      log_info "${harness} image already loaded (${tag})"
      continue
    fi

    log_info "Downloading ${harness}..."

    if command -v hf &>/dev/null; then
      hf download internlm/WildClawBench "Images/${tarball}" \
        --repo-type dataset --local-dir "${PROJECT_DIR}" 2>/dev/null || true
    else
      # Python fallback for environments without the hf CLI
      uv run python -c "
import os, sys
os.environ.setdefault('HF_TOKEN', os.environ.get('HF_TOKEN', ''))
from huggingface_hub import hf_hub_download
try:
    hf_hub_download(
        repo_id='internlm/WildClawBench',
        filename='Images/${tarball}',
        repo_type='dataset',
        local_dir='${PROJECT_DIR}',
    )
    print('Downloaded ${tarball}')
except Exception as e:
    print(f'Failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1 || true
    fi

    if [[ -f "${download_dir}/${tarball}" ]]; then
      log_info "Loading ${harness} into Docker..."
      docker load -i "${download_dir}/${tarball}"
      log_success "${harness} loaded (${tag})"
    else
      log_warn "Failed to download ${harness} image, skipping"
    fi
  done

  echo ""
  echo "=========================================="
  log_success "Setup complete!"
  echo ""
  echo "Next: Edit .env, then run:"
  echo "  bash benchmark.sh run"
  echo "=========================================="
}

# ─── RUN ────────────────────────────────────────────────────────────────────
do_run() {
  local category="all"
  local model=""
  local agent=""
  local parallel=1
  local no_score=""
  local verbose_flag=""

  # Parse run options
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --category) category="$2"; shift 2 ;;
      --model)    model="$2"; shift 2 ;;
      --agent)    agent="$2"; shift 2 ;;
      --parallel) parallel="$2"; shift 2 ;;
      --no-score) no_score="--no-score"; shift ;;
      --verbose|-v) verbose_flag="--verbose"; shift ;;
      *) log_error "Unknown option: $1"; exit 1 ;;
    esac
  done

  # Check .env
  if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
    log_error ".env not found. Run: bash benchmark.sh setup"
    exit 1
  fi
  source "${PROJECT_DIR}/.env"

  # Determine which agents to run
  local agents_to_run
  if [[ -n "${agent}" ]]; then
    agents_to_run="${agent}"
  else
    agents_to_run="${HARNESS_LIST}"
  fi

  # Build model flag
  local model_flag=""
  if [[ -n "${model}" ]]; then
    model_flag="--model ${model}"
  fi

  echo ""
  echo "=========================================="
  echo "  WildClawBench Benchmark Run"
  echo "=========================================="
  echo "  Category : ${category}"
  echo "  Model    : ${model:-from .env}"
  echo "  Agents   : ${agents_to_run}"
  echo "  Sequential: Yes (one at a time)"
  echo "  Scoring  : $([ -n "${no_score}" ] && echo "disabled" || echo "enabled")"
  echo "  Verbose  : $([ -n "${verbose_flag}" ] && echo "yes" || echo "no")"
  echo "=========================================="
  echo ""

  local start_time
  start_time=$(date +%s)
  local total=0
  local passed=0
  local failed=0
  local results=()

  for harness in ${agents_to_run}; do
    total=$((total + 1))
    local harness_start
    harness_start=$(date +%s)

    echo ""
    log_step "Running ${harness} (${total} of $(echo ${agents_to_run} | wc -w | tr -d ' '))..."
    echo "────────────────────────────────────────"

    # Run the harness
    cd "${PROJECT_DIR}"
    local exit_code=0

    if [[ "${harness}" == "openclaw" ]]; then
      uv run python3 eval/run_batch.py \
        --category "${category}" \
        --parallel "${parallel}" \
        ${model_flag} \
        ${no_score} \
        ${verbose_flag} || exit_code=$?
    else
      uv run python3 eval/run_batch.py \
        --harness "${harness}" \
        --category "${category}" \
        --parallel "${parallel}" \
        ${model_flag} \
        ${no_score} \
        ${verbose_flag} || exit_code=$?
    fi

    local harness_end
    harness_end=$(date +%s)
    local harness_duration=$((harness_end - harness_start))

    if [[ ${exit_code} -eq 0 ]]; then
      passed=$((passed + 1))
      results+=("${harness}:PASS:${harness_duration}")
      log_success "${harness} completed (${harness_duration}s)"
    else
      failed=$((failed + 1))
      results+=("${harness}:FAIL:${harness_duration}")
      log_error "${harness} failed (${harness_duration}s, exit code: ${exit_code})"
    fi

    echo "────────────────────────────────────────"
  done

  local end_time
  end_time=$(date +%s)
  local total_duration=$((end_time - start_time))

  # Summary
  echo ""
  echo "=========================================="
  echo "  Benchmark Summary"
  echo "=========================================="
  echo "  Total time : ${total_duration}s"
  echo "  Agents run : ${total}"
  echo "  Passed     : ${passed}"
  echo "  Failed     : ${failed}"
  echo ""
  echo "  Results:"
  for r in "${results[@]}"; do
    IFS=':' read -r name status dur <<< "${r}"
    if [[ "${status}" == "PASS" ]]; then
      echo -e "    ${GREEN}✓${NC} ${name} (${dur}s)"
    else
      echo -e "    ${RED}✗${NC} ${name} (${dur}s)"
    fi
  done
  echo ""
  echo "  Output dir: ${PROJECT_DIR}/output/"
  echo "=========================================="

  # Save run summary
  local summary_file="${PROJECT_DIR}/output/run_summary.json"
  mkdir -p "${PROJECT_DIR}/output"
  cat > "${summary_file}" <<SUMEOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_seconds": ${total_duration},
  "category": "${category}",
  "model": "${model:-from .env}",
  "agents": {
$(for r in "${results[@]}"; do
    IFS=':' read -r name status dur <<< "${r}"
    echo "    \"${name}\": {\"status\": \"${status}\", \"duration_seconds\": ${dur}},"
  done | sed '$ s/,$//')
  }
}
SUMEOF

  log_success "Summary saved to ${summary_file}"
}

# ─── STATUS ─────────────────────────────────────────────────────────────────
do_status() {
  local output_dir="${PROJECT_DIR}/output"

  echo ""
  echo "=========================================="
  echo "  WildClawBench Results Status"
  echo "=========================================="

  if [[ ! -d "${output_dir}" ]]; then
    echo "  No results found. Run benchmarks first."
    echo "=========================================="
    return
  fi

  for harness in ${HARNESS_LIST}; do
    local harness_dir="${output_dir}/${harness}"
    echo ""
    echo "  ${harness}:"
    if [[ -d "${harness_dir}" ]]; then
      local count
      count=$(find "${harness_dir}" -name "score.json" 2>/dev/null | wc -l | tr -d ' ')
      echo "    Tasks completed: ${count}"
      if [[ ${count} -gt 0 ]]; then
        echo "    Latest run:"
        find "${harness_dir}" -name "score.json" -exec stat -f "%m %N" {} \; 2>/dev/null \
          | sort -rn | head -1 | awk '{print "      " $2}'
      fi
    else
      echo "    No results"
    fi
  done

  # Show latest summary
  if [[ -f "${output_dir}/run_summary.json" ]]; then
    echo ""
    echo "  Latest run summary:"
    cat "${output_dir}/run_summary.json"
  fi

  echo ""
  echo "=========================================="
}

# ─── HELP ───────────────────────────────────────────────────────────────────
do_help() {
  cat <<'EOF'
WildClawBench - Setup & Run Script

Usage:
  bash benchmark.sh <command> [options]

Commands:
  check                 Pre-flight check (see what's installed)
  setup                 Full setup (deps, images, data, env)
  run                   Run all agents sequentially
  status                Show latest results
  help                  Show this help

Run Options:
  --category CAT        Task category (default: all)
                        Categories: all, 01_Productivity_Flow, 02_Code_Intelligence,
                                    03_Search_Retrieval, 04_Data_Processing,
                                    05_Safety_Alignment
  --model MODEL         Model to evaluate (default: from .env)
  --agent AGENT         Run specific agent only (openclaw|opencode|hermesagent)
  --parallel N          Parallel tasks per agent (default: 1)
  --no-score            Disable scoring (skip evaluation of task output)
  --verbose, -v         Verbose logging (shows detailed scoring breakdown)

Examples:
  bash benchmark.sh check
  bash benchmark.sh setup
  bash benchmark.sh run
  bash benchmark.sh run --model qwen3.5-9b
  bash benchmark.sh run --category 01_Productivity_Flow
  bash benchmark.sh run --agent opencode
  bash benchmark.sh run --verbose
  bash benchmark.sh run --no-score
  bash benchmark.sh status

Scoring:
  By default, each task is scored after execution on a 0.0-1.0 scale based on:
  - LLM response quality (code blocks, required imports)
  - File creation (expected files exist with correct names)
  - Code execution (scripts run without errors)
  - Output correctness (output matches expected patterns)

  Use --no-score to disable scoring for faster execution.
  Use --verbose to see detailed scoring breakdown for each criterion.

Execution Flow:
  1. Setup installs all prerequisites and downloads Docker images
  2. Run executes agents ONE AT A TIME (sequential) to conserve resources
  3. Each agent's results are saved to output/<agent>/
  4. After all agents finish, a summary is printed and saved

Environment (.env):
  OPENROUTER_API_KEY    Required for API access
  BRAVE_API_KEY         Required for search tasks
  DEFAULT_MODEL         Default model to evaluate
  JUDGE_MODEL           LLM for judge-based grading (optional)
EOF
}

# ─── MAIN ───────────────────────────────────────────────────────────────────
main() {
  if [[ $# -lt 1 ]]; then
    do_help
    exit 0
  fi

  local command="$1"
  shift

  case "${command}" in
    setup)  do_setup ;;
    run)    do_run "$@" ;;
    check)  do_check ;;
    status) do_status ;;
    help|-h|--help) do_help ;;
    *)
      log_error "Unknown command: ${command}"
      echo ""
      do_help
      exit 1
      ;;
  esac
}

main "$@"
