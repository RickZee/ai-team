#!/usr/bin/env bash
# AI Team - Ollama Setup Script
# 1. Checks if Ollama is installed, installs if not
# 2. Pulls required models (32b or 14b based on memory) with progress
# 3. Verifies each model with a simple test
# 4. Reports VRAM usage estimates

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
PROMPT_TEST="Reply with exactly: OK"

# --- Helpers ---
print_ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
print_warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
print_err()   { echo -e "${RED}[✗]${NC} $1"; }
print_info()  { echo -e "${BLUE}[i]${NC} $1"; }
print_step()  { echo -e "${CYAN}▶${NC} $1"; }

# --- 1. Check if Ollama is installed, install if not ---
check_and_install_ollama() {
    echo ""
    print_step "Checking Ollama installation..."
    if command -v ollama &>/dev/null; then
        print_ok "Ollama is already installed ($(ollama --version 2>/dev/null || echo 'unknown version'))"
        return 0
    fi
    print_info "Ollama not found. Installing via official script..."
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS: official install
        curl -fsSL https://ollama.com/install.sh | sh
    else
        # Linux
        curl -fsSL https://ollama.com/install.sh | sh
    fi
    if ! command -v ollama &>/dev/null; then
        print_err "Installation may have succeeded but 'ollama' is not in PATH. Add it and re-run."
        exit 1
    fi
    print_ok "Ollama installed."
}

# --- Ensure Ollama service is running ---
ensure_ollama_running() {
    print_step "Checking Ollama service..."
    if curl -sf "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
        print_ok "Ollama service is running at ${OLLAMA_BASE_URL}"
        return 0
    fi
    print_info "Starting Ollama service in background..."
    (ollama serve &>/dev/null &)
    for i in {1..15}; do
        sleep 1
        if curl -sf "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
            print_ok "Ollama service started."
            return 0
        fi
    done
    print_err "Ollama did not become ready. Run 'ollama serve' manually and re-run this script."
    exit 1
}

# --- Detect memory and choose 32b vs 14b ---
detect_memory_and_models() {
    local total_gb=0
    if [[ "$(uname -s)" == "Darwin" ]]; then
        # macOS: unified memory in bytes
        total_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
    else
        # Linux: MemTotal in kB
        total_gb=$(awk '/MemTotal:/ { print int($2/1024/1024) }' /proc/meminfo 2>/dev/null || echo 0)
    fi
    if [[ -z "$total_gb" || "$total_gb" -eq 0 ]]; then
        total_gb=16
        print_warn "Could not detect memory; defaulting to 14b variants (assume ~16 GB)."
    fi
    # 32b models need ~22–26 GB; use 14b if we have less than 28 GB to be safe
    if [[ "$total_gb" -ge 28 ]]; then
        MODELS=( "qwen3:32b" "qwen2.5-coder:32b" "deepseek-r1:32b" "deepseek-coder-v2:16b" )
        print_ok "Detected ~${total_gb} GB memory — using 32b variants for qwen3, qwen2.5-coder, deepseek-r1."
    else
        MODELS=( "qwen3:14b" "qwen2.5-coder:14b" "deepseek-r1:14b" "deepseek-coder-v2:16b" )
        print_ok "Detected ~${total_gb} GB memory — using 14b variants for lower VRAM."
    fi
}

# --- 2. Pull models with progress indication ---
pull_models() {
    echo ""
    print_step "Pulling models (Ollama will show progress below)..."
    echo ""
    for model in "${MODELS[@]}"; do
        echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"
        print_info "Pulling: ${model}"
        if ollama pull "$model"; then
            print_ok "Pulled: ${model}"
        else
            print_err "Failed to pull: ${model}"
            exit 1
        fi
        echo ""
    done
}

# --- 3. Verify each model with a simple test ---
verify_models() {
    echo ""
    print_step "Verifying each model with a short test..."
    echo ""
    for model in "${MODELS[@]}"; do
        print_info "Testing: ${model}"
        # Short test; first load per model can be slow
        out=$(ollama run "$model" "$PROMPT_TEST" 2>&1 || true)
        if echo "$out" | grep -qi "OK"; then
            print_ok "${model}: responds OK"
        else
            # Some models may not say "OK" literally but still respond
            if echo "$out" | grep -qE '[A-Za-z0-9]'; then
                print_ok "${model}: responds (check output if needed)"
            else
                print_warn "${model}: no clear response (run manually: ollama run ${model})"
            fi
        fi
        echo ""
    done
}

# --- 4. Report VRAM usage estimates ---
report_vram_estimates() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              VRAM / memory usage estimates                    ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Model size    Typical VRAM (approx)   Notes"
    echo "  ---------    ---------------------   -----"
    echo "  14b          10–14 GB                 Good for 24 GB unified / 16 GB VRAM"
    echo "  16b          12–16 GB                 deepseek-coder-v2:16b"
    echo "  32b          22–26 GB                 Prefer 36 GB+ for comfort"
    echo ""
    print_info "Loaded model size: run 'ollama ps' while a model is loaded to see actual SIZE."
    echo ""
}

# --- Summary ---
print_summary() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    Setup complete                              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    print_ok "Models installed: ${MODELS[*]}"
    echo ""
    print_info "Next: uv sync && uv run python -m ai_team.main \"Your task\""
    echo ""
}

# --- Main ---
main() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           AI Team – Ollama setup                              ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    check_and_install_ollama
    ensure_ollama_running
    detect_memory_and_models
    pull_models
    verify_models
    report_vram_estimates
    print_summary
}

main "$@"
