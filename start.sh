#!/usr/bin/env bash
set -e

cd /app/backend

# 持久化目录（docker-compose 挂载 ./data -> /app/backend/data）
mkdir -p data/chroma_db
if [[ ! -f data/ai_police.db ]]; then
  : > data/ai_police.db
fi

python init_db.py
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
