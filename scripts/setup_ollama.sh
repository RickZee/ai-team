#!/bin/bash
# AI Team - Ollama Setup Script
# Installs Ollama, pulls required models, verifies them, and creates .env with role assignments.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
USE_SMALL=false

# VRAM estimates (GB) - approximate for loading + inference (model_name -> GB)
vram_gb() {
    case "$1" in
        qwen3:32b|qwen2.5-coder:32b|deepseek-r1:32b) echo 22 ;;
        qwen3:14b|qwen2.5-coder:14b|deepseek-r1:14b) echo 10 ;;
        deepseek-coder-v2:16b) echo 12 ;;
        *) echo "?" ;;
    esac
}

# Results for summary table (parallel array to MODELS)
MODEL_STATUS=()
MODELS=()

print_status()  { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error()   { echo -e "${RED}[✗]${NC} $1"; }
print_info()    { echo -e "${BLUE}[i]${NC} $1"; }
print_step()    { echo -e "${CYAN}${BOLD}▶${NC} $1"; }

usage() {
    echo "Usage: $0 [--small]"
    echo "  --small    Pull :14b variants for qwen3, qwen2.5-coder, deepseek-r1 (lower VRAM)"
    echo "  (default)  Pull :32b variants for those models; deepseek-coder-v2:16b is always 16b"
    exit 0
}

# Parse args
for arg in "$@"; do
    case "$arg" in
        --small) USE_SMALL=true ;;
        -h|--help) usage ;;
        *) print_error "Unknown option: $arg"; usage ;;
    esac
done

# Set model list based on --small
if [[ "$USE_SMALL" == true ]]; then
    MODELS=( "qwen3:14b" "qwen2.5-coder:14b" "deepseek-r1:14b" "deepseek-coder-v2:16b" )
    print_info "Using small (14b) variants for lower VRAM"
else
    MODELS=( "qwen3:32b" "qwen2.5-coder:32b" "deepseek-r1:32b" "deepseek-coder-v2:16b" )
    print_info "Using 32b variants (ensure sufficient VRAM)"
fi

cleanup() {
    local err=$?
    if [[ $err -ne 0 ]]; then
        print_error "Script failed (exit $err). Check output above."
    fi
}
trap cleanup ERR

# --- Check OS ---
check_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        print_status "Detected macOS"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        print_status "Detected Linux"
    else
        print_error "Unsupported OS: $OSTYPE"
        exit 1
    fi
}

# --- Install Ollama if missing ---
install_ollama() {
    echo ""
    print_step "Checking Ollama installation..."
    if command -v ollama &>/dev/null; then
        print_status "Ollama already installed: $(ollama --version 2>/dev/null || echo 'unknown')"
    else
        print_info "Ollama not found. Installing..."
        if ! curl -fsSL https://ollama.ai/install.sh | sh; then
            print_error "Ollama install failed. See https://ollama.com/download"
            exit 1
        fi
        print_status "Ollama installed"
    fi
}

# --- Start Ollama server if not running ---
start_ollama() {
    echo ""
    print_step "Checking Ollama service..."
    if curl -sf "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
        print_status "Ollama service is already running at $OLLAMA_BASE_URL"
    else
        print_info "Starting Ollama server..."
        ( ollama serve &>/dev/null & )
        local wait_count=0
        while ! curl -sf "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; do
            sleep 1
            ((wait_count++)) || true
            if [[ $wait_count -gt 15 ]]; then
                print_error "Ollama did not start within 15s. Try: ollama serve"
                exit 1
            fi
        done
        print_status "Ollama started"
    fi
}

# --- Pull models with progress (ollama pull already shows progress) ---
pull_models() {
    echo ""
    print_step "Pulling models (progress below)..."
    echo ""
    for model in "${MODELS[@]}"; do
        echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
        print_info "Pulling: ${BOLD}$model${NC}"
        if ollama pull "$model"; then
            print_status "Pulled: $model"
            MODEL_STATUS+=("OK")
        else
            print_error "Failed to pull: $model"
            MODEL_STATUS+=("FAIL")
        fi
        echo ""
    done
}

# --- Verify each model with a simple test prompt ---
verify_models() {
    echo ""
    print_step "Verifying each model with a test prompt..."
    local idx=0
    for model in "${MODELS[@]}"; do
        print_info "Testing: $model"
        local out
        out=$(ollama run "$model" "Reply with exactly: OK" --verbose 2>/dev/null | head -5 || true)
        if [[ "$out" == *"OK"* ]] || [[ "$out" == *"ok"* ]]; then
            print_status "$model: responds OK"
            MODEL_STATUS[$idx]="OK"
        else
            print_warning "$model: could not confirm (run manually if needed)"
            [[ "${MODEL_STATUS[$idx]:-}" != "OK" ]] && MODEL_STATUS[$idx]="CHECK"
        fi
        ((idx++)) || true
    done
}

# --- VRAM usage estimates ---
report_vram() {
    echo ""
    print_step "VRAM usage estimates (approximate load + inference):"
    echo ""
    for model in "${MODELS[@]}"; do
        local vram
        vram=$(vram_gb "$model")
        echo -e "  ${BOLD}$model${NC}  →  ${YELLOW}~${vram} GB${NC}"
    done
    echo ""
    print_info "Reduce memory: use $0 --small for :14b variants where applicable."
}

# --- Create .env with recommended model assignments per agent role ---
generate_env() {
    echo ""
    print_step "Creating .env with recommended model assignments..."
    local qwen="${MODELS[0]}"      # qwen3 — general/reasoning
    local coder="${MODELS[1]}"    # qwen2.5-coder — code
    local deepseek_code="${MODELS[3]}"  # deepseek-coder-v2 — code
    local deepseek_r1="${MODELS[2]}"    # deepseek-r1 — reasoning

    # .env at repo root (we cd there in main)
    local env_file=".env"
    cat > "$env_file" << EOF
# AI Team — generated by scripts/setup_ollama.sh
# Ollama (required for local agents)
OLLAMA_BASE_URL=${OLLAMA_BASE_URL}
OLLAMA_TIMEOUT=300

# Model assignments per agent role (recommendations)
OLLAMA_MANAGER_MODEL=${qwen}
OLLAMA_PRODUCT_OWNER_MODEL=${qwen}
OLLAMA_ARCHITECT_MODEL=${deepseek_r1}
OLLAMA_BACKEND_DEVELOPER_MODEL=${coder}
OLLAMA_FRONTEND_DEVELOPER_MODEL=${coder}
OLLAMA_FULLSTACK_DEVELOPER_MODEL=${coder}
OLLAMA_DEVOPS_MODEL=${coder}
OLLAMA_CLOUD_ENGINEER_MODEL=${coder}
OLLAMA_QA_ENGINEER_MODEL=${deepseek_code}

# Optional
OLLAMA_TEMPERATURE=0.7
LOG_LEVEL=INFO
CREW_VERBOSE=true
EOF
    print_status "Created $env_file"
}

# --- Summary table ---
print_summary() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                         Setup Summary                                ║${NC}"
    echo -e "${BLUE}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    printf "${BLUE}║${NC} %-28s %-12s %-20s ${BLUE}║${NC}\n" "Model" "Status" "VRAM (est.)"
    echo -e "${BLUE}╠══════════════════════════════════════════════════════════════════════╣${NC}"
    local idx=0
    for model in "${MODELS[@]}"; do
        local status="${MODEL_STATUS[$idx]:-?}"
        local vram
        vram=$(vram_gb "$model")
        local status_color=$GREEN
        [[ "$status" != "OK" ]] && status_color=$YELLOW
        printf "${BLUE}║${NC} %-28s ${status_color}%-12s${NC} %-20s ${BLUE}║${NC}\n" "$model" "$status" "~${vram} GB"
        ((idx++)) || true
    done
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    print_info "Next steps: poetry install && poetry run ai-team (or python -m ai_team.main)"
    echo ""
}

# --- Hardware hint (optional) ---
check_hardware() {
    echo ""
    print_step "Hardware check..."
    if [[ "${OS:-}" == "macos" ]]; then
        if [[ $(uname -m) == "arm64" ]]; then
            print_status "Apple Silicon — GPU acceleration available"
        else
            print_warning "Intel Mac — CPU only"
        fi
    else
        if command -v nvidia-smi &>/dev/null; then
            local gpu
            gpu=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)
            print_status "NVIDIA: $gpu"
        else
            print_warning "No NVIDIA GPU — CPU mode (slower)"
        fi
    fi
}

# --- Main ---
main() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           AI Team — Ollama Setup Script                    ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$SCRIPT_DIR"

    check_os
    check_hardware
    install_ollama
    start_ollama
    pull_models
    verify_models
    report_vram
    generate_env
    print_summary
}

main "$@"
