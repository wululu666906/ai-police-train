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

## Pulling the prebuilt deployment image

Pushing the `codex/github-deploy-bundle` branch builds a Linux image in GitHub
Container Registry. It includes Python packages, Node build output, ffmpeg,
PDF rendering support, Chinese fonts, InsightFace models, and cached PaddleOCR
models. The image build also verifies OpenCV, ONNX Runtime, pypdfium2, ffmpeg,
and InsightFace model loading. The server therefore does not install
dependencies or download models.

```bash
git clone -b codex/github-deploy-bundle https://github.com/wululu666906/ai-police-train.git
cd ai-police-train
cp backend/.env.example backend/.env
# Set JWT_SECRET_KEY and an LLM provider API key in backend/.env.
docker compose -f docker-compose.image.yml pull
docker compose -f docker-compose.image.yml up -d
curl http://127.0.0.1:5555/healthz
```

If the GitHub package is private, authenticate the server once with a GitHub
personal access token that has `read:packages` before running the pull.
