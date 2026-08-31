FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip config set global.timeout 300 \
    && pip install --upgrade pip
COPY ai_workflow_service/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY vendor/TinyTroupe /tmp/TinyTroupe
RUN pip install /tmp/TinyTroupe
COPY ai_workflow_service ./ai_workflow_service
RUN mkdir -p /app/ai_workflow_service/data

EXPOSE 8020
CMD ["uvicorn", "ai_workflow_service.main:app", "--host", "0.0.0.0", "--port", "8020"]
