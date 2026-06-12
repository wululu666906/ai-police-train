FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

ARG VITE_API_URL=/api
ARG VITE_SPEECH_PROVIDER=auto
ARG VITE_IFLYTEK_VAD_EOS=1600

ENV VITE_API_URL=$VITE_API_URL \
    VITE_SPEECH_PROVIDER=$VITE_SPEECH_PROVIDER \
    VITE_IFLYTEK_VAD_EOS=$VITE_IFLYTEK_VAD_EOS

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY backend/ ./
COPY frontend /app/frontend
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    'cd /app/backend' \
    'mkdir -p data/chroma_db' \
    'if [[ ! -f data/ai_police.db ]]; then' \
    '  : > data/ai_police.db' \
    'fi' \
    'python init_db.py' \
    'exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"' \
    > /app/start.sh \
    && chmod +x /app/start.sh

EXPOSE 8000

CMD ["/bin/bash", "/app/start.sh"]
