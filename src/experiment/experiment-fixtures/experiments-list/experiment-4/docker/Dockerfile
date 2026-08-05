ARG BASE_IMAGE
FROM ${BASE_IMAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium python3 python3-pip \
    && if ! command -v python >/dev/null; then ln -s /usr/bin/python3 /usr/local/bin/python; fi \
    && python3 -m pip install --no-cache-dir --break-system-packages ruff==0.12.4 playwright==1.54.0 uv==0.11.20 \
    && rm -rf /var/lib/apt/lists/*
