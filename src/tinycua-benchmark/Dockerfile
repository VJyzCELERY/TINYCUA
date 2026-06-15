# TinyCUA Benchmark Docker Image
# Builds a container for WildClawBench benchmark evaluation
# See src/tinycua/docs/benchmark/README.md for usage instructions

FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies required by WildClawBench adapter contract
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    coreutils \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv

# Set up application directory
WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY src/tinycua-sdk/pyproject.toml ./tinycua-sdk/
COPY src/tinycua/pyproject.toml ./tinycua/

# Copy source code
COPY src/tinycua-sdk ./tinycua-sdk
COPY src/tinycua ./tinycua

# Install tinycua-sdk first (dependency of tinycua), then tinycua
RUN uv pip install --no-cache-dir --system ./tinycua-sdk && \
    uv pip install --no-cache-dir --system ./tinycua

# Copy entrypoint script
COPY src/tinycua-benchmark/scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Configure working directory for benchmark tasks
WORKDIR /tmp_workspace

ENTRYPOINT ["/app/entrypoint.sh"]
