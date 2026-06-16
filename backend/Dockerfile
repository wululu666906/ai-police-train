FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        sqlite3 \
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
        libjpeg62-turbo \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    'cd /app' \
    'mkdir -p data/chroma_db' \
    'if [[ ! -f data/ai_police.db ]]; then' \
    '  : > data/ai_police.db' \
    'fi' \
    'python init_db.py' \
    'exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"' \
    > /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

CMD ["/bin/bash", "/app/docker-entrypoint.sh"]
