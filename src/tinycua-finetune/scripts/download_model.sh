#!/bin/bash
# Download Qwen2.5-VL-7B-Instruct model from HuggingFace
# Usage: bash scripts/download_model.sh [MODEL_ID] [OUTPUT_DIR]
# Default: Qwen/Qwen2.5-VL-7B-Instruct -> models/base

set -e

MODEL_ID="${1:-Qwen/Qwen2.5-VL-7B-Instruct}"
OUTPUT_DIR="${2:-models/base}"

echo "=========================================="
echo "TINYCUA Model Downloader"
echo "=========================================="
echo "Model: $MODEL_ID"
echo "Output: $OUTPUT_DIR"
echo "=========================================="

# Check if model already exists
if [ -d "$OUTPUT_DIR" ]; then
    echo "Model already exists at $OUTPUT_DIR"
    echo "To re-download, delete the directory first: rm -rf $OUTPUT_DIR"
    exit 0
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check for git lfs
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed"
    exit 1
fi

# Method 1: Try huggingface-cli (recommended)
if command -v huggingface-cli &> /dev/null; then
    echo "Using huggingface-cli to download..."
    huggingface-cli download "$MODEL_ID" --local-dir "$OUTPUT_DIR"
else
    # Method 2: Fallback to git clone
    echo "huggingface-cli not found, using git clone..."
    
    # Install git lfs if not present
    if ! command -v git-lfs &> /dev/null; then
        echo "Installing git-lfs..."
        brew install git-lfs 2>/dev/null || pip install git-lfs
    fi
    
    git lfs install
    
    # Clone the model repository
    echo "Cloning model repository..."
    git clone "https://huggingface.co/$MODEL_ID" "$OUTPUT_DIR"
fi

echo "=========================================="
echo "Download complete!"
echo "Model saved to: $OUTPUT_DIR"
echo "=========================================="

# Verify the download
if [ -f "$OUTPUT_DIR/config.json" ]; then
    echo "✓ Model config.json found"
else
    echo "✗ Warning: config.json not found"
fi

if [ -f "$OUTPUT_DIR/model.safetensors" ] || [ -f "$OUTPUT_DIR/pytorch_model.bin" ]; then
    echo "✓ Model weights found"
else
    echo "✗ Warning: Model weights not found"
fi
