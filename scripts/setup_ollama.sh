#!/bin/bash
# AI Team - Ollama Setup Script
# Installs Ollama and downloads required models

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

# Choose models based on your VRAM (uncomment one section)

# For 8GB VRAM (minimum)
# MODELS=("qwen3:8b" "qwen2.5-coder:7b" "deepseek-coder:6.7b")

# For 12-16GB VRAM (recommended)
MODELS=("qwen3:14b" "qwen2.5-coder:14b" "deepseek-coder-v2:16b" "deepseek-r1:14b")

# For 24GB+ VRAM (optimal)
# MODELS=("qwen3:32b" "qwen2.5-coder:32b" "deepseek-r1:32b" "deepseek-coder-v2:33b")

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           AI Team - Ollama Setup Script                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_status() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_info() { echo -e "${BLUE}[i]${NC} $1"; }

# Check OS
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

# Check hardware
check_hardware() {
    echo ""
    print_info "Checking hardware..."
    
    if [[ "$OS" == "macos" ]]; then
        if [[ $(uname -m) == "arm64" ]]; then
            print_status "Apple Silicon detected - GPU acceleration available"
        else
            print_warning "Intel Mac - No GPU acceleration"
        fi
    else
        if command -v nvidia-smi &> /dev/null; then
            GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "")
            if [[ -n "$GPU_INFO" ]]; then
                print_status "NVIDIA GPU: $GPU_INFO"
            fi
        else
            print_warning "No NVIDIA GPU detected - CPU mode (slower)"
        fi
    fi
}

# Install Ollama
install_ollama() {
    echo ""
    print_info "Checking Ollama installation..."
    
    if command -v ollama &> /dev/null; then
        print_status "Ollama already installed"
    else
        print_info "Installing Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh
        print_status "Ollama installed"
    fi
}

# Start Ollama service
start_ollama() {
    echo ""
    print_info "Checking Ollama service..."
    
    if curl -s "${OLLAMA_BASE_URL}/api/tags" > /dev/null 2>&1; then
        print_status "Ollama service is running"
    else
        print_info "Starting Ollama..."
        ollama serve &> /dev/null &
        sleep 3
        
        if curl -s "${OLLAMA_BASE_URL}/api/tags" > /dev/null 2>&1; then
            print_status "Ollama started"
        else
            print_error "Failed to start Ollama"
            print_info "Try: ollama serve"
            exit 1
        fi
    fi
}

# Download models
download_models() {
    echo ""
    print_info "Downloading models (this may take a while)..."
    echo ""
    
    for model in "${MODELS[@]}"; do
        echo -e "${BLUE}────────────────────────────────────────────────${NC}"
        print_info "Pulling: $model"
        
        if ollama pull "$model"; then
            print_status "Downloaded: $model"
        else
            print_error "Failed: $model"
        fi
        echo ""
    done
}

# Test models
test_models() {
    echo ""
    print_info "Testing models..."
    
    for model in "${MODELS[@]}"; do
        RESPONSE=$(ollama run "$model" "Say 'Ready' if working." 2>/dev/null | head -1)
        
        if [[ "$RESPONSE" == *"Ready"* ]] || [[ "$RESPONSE" == *"ready"* ]]; then
            print_status "$model: OK"
        else
            print_warning "$model: Check manually"
        fi
    done
}

# Generate .env
generate_env() {
    echo ""
    print_info "Generating .env..."
    
    cat > .env << EOF
# AI Team Configuration
OLLAMA_BASE_URL=${OLLAMA_BASE_URL}
OLLAMA_TIMEOUT=300

# Model Assignments
OLLAMA_MANAGER_MODEL=${MODELS[0]}
OLLAMA_PRODUCT_OWNER_MODEL=${MODELS[0]}
OLLAMA_ARCHITECT_MODEL=${MODELS[3]:-${MODELS[0]}}
OLLAMA_CLOUD_ENGINEER_MODEL=${MODELS[1]}
OLLAMA_DEVOPS_MODEL=${MODELS[1]}
OLLAMA_BACKEND_DEVELOPER_MODEL=${MODELS[2]}
OLLAMA_FRONTEND_DEVELOPER_MODEL=${MODELS[1]}
OLLAMA_QA_ENGINEER_MODEL=${MODELS[0]}

# Settings
OLLAMA_TEMPERATURE=0.7
GUARDRAIL_MAX_RETRIES=3
LOG_LEVEL=INFO
CREW_VERBOSE=true
EOF
    
    print_status "Created .env"
}

# Summary
print_summary() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    Setup Complete!                         ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    print_status "Models downloaded: ${#MODELS[@]}"
    echo ""
    print_info "Next steps:"
    echo "    1. poetry install"
    echo "    2. poetry run python -m ai_team.main"
    echo ""
}

# Main
main() {
    check_os
    check_hardware
    install_ollama
    start_ollama
    download_models
    test_models
    generate_env
    print_summary
}

main "$@"
