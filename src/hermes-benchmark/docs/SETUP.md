# Hermes Benchmark Setup Guide (Ubuntu)

## Overview

This benchmark runs **Qwen 3.5 9B** via the **Hermes Agent** harness against the [WildClawBench](https://github.com/internlm/WildClawBench) task suite (60 tasks across 6 categories). It mirrors the `tinycua-benchmark` structure and is compatible with WildClawBench's `hermesagent` backend.

**Tested on:** Ubuntu 22.04 LTS / 24.04 LTS

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker CE | >= 24.0 | With `docker compose` v2 plugin |
| Python | >= 3.11 | For running WildClawBench eval scripts |
| uv | >= 0.11 | Python package manager |
| HuggingFace CLI | latest | For downloading images and task data |
| yt-dlp | latest | For YouTube video downloads (prepare script) |
| ffmpeg | latest | Video processing |
| gdown | latest | Google Drive downloads (SAM3 weights) |
| Git | >= 2.0 | For cloning repos |

---

## 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    ca-certificates curl gnupg git \
    python3 python3-pip python3-venv \
    ffmpeg \
    build-essential
```

---

## 2. Install Docker CE

```bash
# Add Docker's official GPG key
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow your user to run Docker without sudo
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

> **Important:** Log out and back in (or run `newgrp docker`) so the group change takes effect.

---

## 3. (Optional) Install NVIDIA Container Toolkit

Only needed if running Qwen 3.5 9B **locally on GPU** inside Docker.

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## 4. Install uv (Python Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or source ~/.zshrc
```

---

## 5. Clone WildClawBench

```bash
git clone https://github.com/internlm/WildClawBench.git
cd WildClawBench
```

---

## 6. Download the Hermes Agent Docker Image

```bash
pip install -U "huggingface_hub[cli]"

# Download the Hermes Agent image
hf download internlm/WildClawBench Images/wildclawbench-hermes-agent-v0.5.tar.gz \
    --repo-type dataset --local-dir .

# Load into Docker
docker load -i Images/wildclawbench-hermes-agent-v0.5.tar.gz
```

Verify:
```bash
docker images | grep hermes-agent
# Expected: wildclawbench-hermes-agent:v0.5
```

---

## 7. Download Task Data

```bash
hf download internlm/WildClawBench workspace --repo-type dataset --local-dir .
```

---

## 8. Prepare Data (Videos, Weights, Git Repos)

```bash
pip install yt-dlp gdown

# Run the preparation script
bash script/prepare.sh
```

This script will:
- Download 3 YouTube videos (football match, lecture, product launch)
- Extract the first half of the football match
- Copy videos to task directories that need them
- Extract `dot_git.tar.gz` for Safety Alignment tasks
- Download SAM3 model weights for Code Intelligence tasks

> **Note:** YouTube downloads may require authentication. If you see "Sign in to confirm you're not a bot", try:
> - Install [Deno](https://deno.land/): `curl -fsSL https://deno.land/install.sh | sh`
> - Use `--cookies-from-browser firefox` (Firefox works better on headless Ubuntu)
> - Or use `yt-dlp --cookies cookies.txt` with an exported cookies file

---

## 9. Configure Environment

Create a `.env` file in the WildClawBench root:

```bash
cat > .env << 'EOF'
# Model endpoint (your Qwen 3.5 9B API)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# For search tasks
BRAVE_API_KEY=your_brave_search_key_here

# Judge model for grading (optional)
JUDGE_MODEL=openai/gpt-5.4
EOF
```

---

## 10. Run Qwen 3.5 9B

### Option A: Via OpenRouter (cloud, simplest)

```bash
bash script/run.sh hermesagent --category all --parallel 4 --model openrouter/qwen/qwen3.5-9b
```

### Option B: Local vLLM (GPU, self-hosted)

Start vLLM on the host:
```bash
pip install vllm
vllm serve Qwen/Qwen3.5-9B --port 8000
```

Create `my_api.json` in WildClawBench root:
```json
{
  "providers": {
    "local-qwen": {
      "baseUrl": "http://host.docker.internal:8000/v1",
      "models": [
        {
          "id": "qwen3.5-9b",
          "name": "Qwen 3.5 9B"
        }
      ]
    }
  }
}
```

Run with local config:
```bash
python3 eval/run_batch.py \
    --agent-backend hermesagent \
    --models-config my_api.json \
    --model local-qwen/qwen3.5-9b \
    --category all \
    --parallel 4
```

### Option C: Local Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:9b
ollama serve  # runs on port 11434
```

Create `my_api.json`:
```json
{
  "providers": {
    "local-qwen": {
      "baseUrl": "http://host.docker.internal:11434/v1",
      "models": [
        {
          "id": "qwen3.5:9b",
          "name": "Qwen 3.5 9B"
        }
      ]
    }
  }
}
```

```bash
python3 eval/run_batch.py \
    --agent-backend hermesagent \
    --models-config my_api.json \
    --model local-qwen/qwen3.5:9b \
    --category all \
    --parallel 4
```

---

## 11. Run Commands Reference

### Full suite (all 60 tasks, 4 parallel):
```bash
bash script/run.sh hermesagent --category all --parallel 4 --model openrouter/qwen/qwen3.5-9b
```

### Single category:
```bash
bash script/run.sh hermesagent --category 01_Productivity_Flow --parallel 4 --model openrouter/qwen/qwen3.5-9b
```

### Single task:
```bash
bash script/run.sh hermesagent \
    --task tasks/06_Safety_Alignment/06_Safety_Alignment_task_1_file_overwrite.md \
    --model openrouter/qwen/qwen3.5-9b
```

### Available categories:
| Category | Tasks |
|----------|-------|
| `01_Productivity_Flow` | 10 |
| `02_Code_Intelligence` | 12 |
| `03_Social_Interaction` | 6 |
| `04_Search_Retrieval` | 11 |
| `05_Creative_Synthesis` | 11 |
| `06_Safety_Alignment` | 10 |

---

## 12. Check Results

Results are saved under `output/hermesagent/<category>/<task_id>/<model_timestamp_runid>/`:

```
output/hermesagent/
├── 01_Productivity_Flow/
│   └── task_id/
│       └── qwen3.5-9b_20260617_abc123/
│           ├── score.json       # Per-metric scores (0.00-1.00)
│           ├── usage.json       # Token counts, cost, elapsed time
│           ├── agent.log        # Agent execution log
│           ├── chat.jsonl       # Full conversation trace
│           └── task_output/     # Files produced by the agent
├── 02_Code_Intelligence/
├── 03_Social_Interaction/
├── 04_Search_Retrieval/
├── 05_Creative_Synthesis/
├── 06_Safety_Alignment/
└── summary_all.json            # Global summary
```

---

## 13. Cleanup

If a run is interrupted, remove leftover containers:
```bash
docker ps -a --filter "ancestor=wildclawbench-hermes-agent:v0.5" -q | xargs -r docker rm -f
```

To remove all WildClawBench images:
```bash
docker rmi wildclawbench-hermes-agent:v0.5
```

---

## Ubuntu-Specific Notes

### Docker socket permissions
If you get `permission denied` when running Docker:
```bash
sudo usermod -aG docker $USER
# Log out and back in, or:
newgrp docker
```

### `host.docker.internal` not resolving
On older Docker versions (< 20.10) on Linux, `host.docker.internal` may not work. The `docker-compose.yml` already includes:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```
If running outside docker-compose, add `--add-host=host.docker.internal:host-gateway` to your `docker run` command.

### Disk space
The Hermes Agent image is ~5GB. The full workspace with videos is ~10GB. Ensure you have at least **20GB free** before starting.

### Firewall / proxy
If behind a corporate proxy, configure Docker proxy:
```bash
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo tee /etc/systemd/system/docker.service.d/proxy.conf << 'EOF'
[Service]
Environment="HTTP_PROXY=http://proxy:port"
Environment="HTTPS_PROXY=http://proxy:port"
Environment="NO_PROXY=localhost,127.0.0.1,host.docker.internal"
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### Headless server (no display)
All commands work headless. Docker Desktop is not required — `docker-ce` is sufficient. The benchmark runs entirely in containers with no GUI.

### GPU passthrough for local inference
If running vLLM locally and the container needs GPU access:
```bash
docker run --gpus all ...  # instead of just docker run
```
For docker-compose, add:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `permission denied while trying to connect to Docker daemon` | Run `sudo usermod -aG docker $USER && newgrp docker` |
| `TASK_PROMPT not set` | Benchmark harness must inject this; ensure you're using `run_batch.py` |
| `HERMES_BASE_URL not set` | Set it in `.env` or pass via environment |
| `host.docker.internal` unreachable | Add `--add-host=host.docker.internal:host-gateway` to docker run |
| YouTube download fails | Install Deno or use `--cookies-from-browser firefox` |
| Container left running | Run `docker ps -a --filter "ancestor=wildclawbench-hermes-agent:v0.5" -q \| xargs -r docker rm -f` |
| `No space left on device` | Prune Docker: `docker system prune -a` or increase disk |
| vLLM OOM | Reduce `--max-model-len` or use a smaller quantization (AWQ/GPTQ) |
| Slow downloads | Use `hf download` with `--workers 8` for parallel downloads |
