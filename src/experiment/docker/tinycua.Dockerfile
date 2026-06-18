FROM python:3.12-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv
COPY src/tinycua-sdk ./tinycua-sdk
COPY src/tinycua ./tinycua
COPY src/experiment/docker/tinycua_entrypoint.py ./tinycua_entrypoint.py
RUN uv pip install --no-cache-dir --system ./tinycua-sdk \
 && uv pip install --no-cache-dir --system ./tinycua

CMD ["python", "/app/tinycua_entrypoint.py"]
