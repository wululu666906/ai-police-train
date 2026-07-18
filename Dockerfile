FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

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
    && apt-get install -y --no-install-recommends \
        build-essential \
        sqlite3 \
        ffmpeg \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
        libjpeg62-turbo \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY backend/ ./
COPY data/face_models /app/data/face_models
COPY frontend /app/frontend
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Download and cache PaddleOCR's Chinese models while building the image.
# Runtime document parsing must not depend on the server having outbound access.
RUN python -c "from services.document_extract_service import document_extract_service; document_extract_service._load_paddle_ocr()"

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
