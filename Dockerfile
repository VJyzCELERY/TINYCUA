# TinyCUA Benchmark Docker Image
# Builds a container for WildClawBench benchmark evaluation.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    coreutils \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv

WORKDIR /app

COPY src/tinycua-sdk/pyproject.toml ./tinycua-sdk/
COPY src/tinycua/pyproject.toml ./tinycua/
COPY src/tinycua-sdk ./tinycua-sdk
COPY src/tinycua ./tinycua

RUN uv pip install --no-cache-dir --system ./tinycua-sdk && \
    uv pip install --no-cache-dir --system ./tinycua

COPY src/tinycua-benchmark/scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

WORKDIR /tmp_workspace

ENTRYPOINT ["/app/entrypoint.sh"]
