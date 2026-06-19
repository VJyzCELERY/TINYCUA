#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  printf '%s\n' "Created .env from .env.example"
fi

docker compose build
docker compose pull searxng
