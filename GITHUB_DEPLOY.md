# GitHub Deployment

This repository stores the required InsightFace ONNX files with Git LFS.
Do not build the Docker image until the LFS objects are present.

```bash
git clone https://github.com/wululu666906/ai-police-train.git
cd ai-police-train
git lfs pull
cp backend/.env.example backend/.env
# Set JWT_SECRET_KEY and at least one LLM provider API key in backend/.env.
docker compose up -d --build
curl http://127.0.0.1:5555/healthz
```

The repository intentionally excludes `backend/.env`, SQLite databases,
knowledge-base data, uploaded media, face-profile images, virtual environments,
and JavaScript dependency directories. Python and Node dependencies are restored
reproducibly from `backend/requirements.txt` and `frontend/package-lock.json`.
