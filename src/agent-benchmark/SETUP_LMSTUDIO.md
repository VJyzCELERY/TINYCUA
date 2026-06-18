# WildClawBench + LM Studio Setup Guide

## Overview

This guide covers setting up WildClawBench to run with Qwen 3.5-9B via LM Studio on an Ubuntu VirtualBox VM.

## Prerequisites

- VirtualBox with Ubuntu 22.04+ VM
- 16GB+ RAM (Qwen 3.5-9B needs ~8GB VRAM/RAM)
- Docker installed in VM
- LM Studio installed

## Issues Found & Fixed

### 1. Docker Containers Exit Immediately (CRITICAL)

**Problem:** Containers ran `bash` and exited in 0.2s without executing any tasks.

**Fix:** Added entrypoint script `scripts/entrypoint_lmstudio.sh` that processes tasks via LM Studio API.

### 2. Hermes Env Var Mismatch (CRITICAL)

**Problem:** `hermes_agent.py` passed `HERMES_API_BASE` but entrypoint expected `HERMES_BASE_URL`.

**Fix:** Updated `hermes_agent.py` to pass `HERMES_BASE_URL`.

### 3. OpenCode Uses Wrong Docker Image (CRITICAL)

**Problem:** `OpenCodeAgent` used `wildclawbench-ubuntu:v1.3` (OpenClaw image) without OpenCode agent code.

**Fix:** Added entrypoint script that works with any Ubuntu-based image.

### 4. Localhost Networking Issue (CRITICAL)

**Problem:** `localhost` inside Docker != host LM Studio.

**Fix:** Use `host.docker.internal:1234` instead of `localhost:1234`.

### 5. API Key Check for LM Studio (MODERATE)

**Problem:** Code failed if API key env var empty. LM Studio doesn't need a key.

**Fix:** Skip API key check for `LM_STUDIO_API_KEY`.

### 6. Proxy Interference (MODERATE)

**Problem:** System proxy settings interfered with local API calls.

**Fix:** Unset proxy env vars in entrypoint script.

## Setup Instructions

### Step 1: Install LM Studio on Ubuntu VM

```bash
# Download LM Studio AppImage
wget https://lmstudio.ai/downloads/linux -O LMStudio.AppImage

# Make executable and run
chmod +x LMStudio.AppImage
./LMStudio.AppImage
```

### Step 2: Download Qwen 3.5-9B Model

1. Open LM Studio
2. Search for "Qwen 3.5 9B" or "Qwen/Qwen3.5-9B"
3. Download the model (GGUF format recommended)
4. Load the model in LM Studio

### Step 3: Start LM Studio Server

1. Go to "Local Server" tab in LM Studio
2. Click "Start Server"
3. Default port: 1234
4. Verify: `curl http://localhost:1234/v1/models`

### Step 4: Configure WildClawBench

The config files are already set up:

- `opencode-config.yaml` → Points to LM Studio
- `hermes-config.yaml` → Points to LM Studio
- `.env` → Has `LM_STUDIO_API_KEY=lm-studio`

### Step 5: Run Benchmarks

```bash
cd src/agent-benchmark

# Run all agents with all categories
bash benchmark.sh run

# Run specific agent
bash benchmark.sh run --agent opencode

# Run specific category
bash benchmark.sh run --category 02_Code_Intelligence

# Run with specific model
bash benchmark.sh run --model qwen3.5-9b
```

## Test Cases

### 01_Productivity_Flow
- `productivity_01.yaml`: File organization script
- `productivity_02.yaml`: Markdown report from CSV

### 02_Code_Intelligence
- `code_01.yaml`: Binary search implementation
- `code_02.yaml`: Code refactoring

### 03_Search_Retrieval
- `search_01.yaml`: Web content extraction

### 04_Data_Processing
- `data_01.yaml`: CSV transformation

### 05_Safety_Alignment
- `safety_01.yaml`: Security code review

## Running on VirtualBox Ubuntu VM

Since Docker containers use `--platform linux/amd64`, they work natively on x86_64 Ubuntu (no QEMU emulation needed).

1. Start your VirtualBox Ubuntu VM
2. Open terminal in VM
3. Follow Steps 1-5 above

**Important:** LM Studio server must be running before starting benchmarks.

## Verification

After running benchmarks, check results:

```bash
# Show latest results
bash benchmark.sh status

# Check specific output
cat output/opencode/summary_all.json
cat output/hermesagent/summary_all.json
```

## Troubleshooting

### "Connection refused" error
- Ensure LM Studio server is running
- Check: `curl http://localhost:1234/v1/models`
- Verify no firewall blocking port 1234

### Docker permission denied
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### Model not found in LM Studio
- Download the model first
- Ensure model is loaded (click "Load" in LM Studio)
- Check model name matches config: `qwen3.5-9b`
