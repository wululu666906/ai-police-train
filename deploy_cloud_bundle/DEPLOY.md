# 部署说明

这个目录是独立部署副本，原项目未被改动。

## 目录说明

- `backend/`：FastAPI 后端，包含 SQLite 数据库和 ChromaDB 数据。
- `frontend/`：Vue 前端源码，云端构建后由后端统一托管。
- `Dockerfile`：单容器部署方案，适合大多数云平台。
- `start.sh`：容器启动命令。

## 推荐部署方式

推荐直接使用 `Dockerfile` 部署。容器启动后：

- 前端页面由 FastAPI 同域提供
- API 与页面共用同一个域名
- 健康检查地址：`/api/health`

## 云端环境变量

至少配置以下变量：

- `SECRET_KEY`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DATABASE_URL`：默认可用 `sqlite:///./ai_police.db`

可选：

- `ALLOWED_ORIGINS`：如果你后续把前后端拆开部署，再填写逗号分隔的域名

## 不建议上传的内容

不要把本地开发环境一起传上去：

- `frontend/node_modules`
- `backend/venv`
- 本地真实 `.env`

## 本地验证

### 前端构建

```bash
cd frontend
npm install
npm run build
```

### 后端启动

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```
