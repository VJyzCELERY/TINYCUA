ARG BASE_IMAGE
FROM ${BASE_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium \
    && python -m pip install --no-cache-dir playwright==1.54.0 ruff==0.12.4 \
    && rm -rf /var/lib/apt/lists/*
