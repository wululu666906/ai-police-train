# AI虚拟警情处置模拟训练平台

## 本地部署端口说明（以本节为准）

- 稳定本地部署：使用 Docker 单容器，占用 `http://localhost:5555/`。
- 实时开发模式：使用 `.\scripts\dev-restart.ps1`，前端 Vite 占用 `http://localhost:5556/`，后端占用 `http://127.0.0.1:8000/`。
- `5555` 不再用于 Vite 热更新，避免 Docker 容器和开发服务器抢占同一个端口。
- 本地与 Docker 默认统一使用 `data/ai_police.db`，`backend/ai_police.db` 仅视为旧本机库。

稳定部署：

```powershell
.\scripts\docker-deploy.ps1
```

实时开发：

```powershell
.\scripts\dev-restart.ps1
```

基于 `FastAPI + Vue 3 + SQLite/可选外部数据库 + LLM/RAG` 的警情处置训练平台，面向案件导入、场景训练、对话评估和学生训练记录管理。

**面向用户**：警校生、接受岗前/在职培训的基层民警；教官与教务管理员负责内容发布与学员管理。

## 项目文档

完整材料（调研报告、产品说明、技术摘要）见 **[docs/](./docs/)** 目录，主文档为 [docs/01-调研报告.md](./docs/01-调研报告.md)（含需求原因、竞品分析与调研结论）。

## 源码压缩包

生成可交付的源码包（不含 `node_modules`、`venv`、数据库、`.env` 等）：

```bash
python scripts/package_release.py
```

输出文件位于 `release/` 目录，解压后请阅读包内 `打包说明.txt`。

## 本地启动

稳定本地部署推荐使用 Docker 单容器入口：

```powershell
.\scripts\docker-deploy.ps1
```

浏览器访问 `http://localhost:5555/`。

如需实时热更新开发，再使用：

```powershell
.\scripts\dev-restart.ps1
```

浏览器访问 `http://localhost:5556/`。前端使用 Vite 热更新，后端使用 `uvicorn --reload`。该模式启动前会停止 Docker compose，避免与 `5555` 冲突。

后端：

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python init_db.py
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认访问：

- 前端开发环境：`http://localhost:5556`
- 后端接口文档：`http://127.0.0.1:8000/docs`

## 数据库路径说明

项目默认使用 SQLite，数据库文件位于：

```text
data/ai_police.db
```

`backend/database.py` 默认使用根目录 `data/`，本地 dev 与 Docker 单容器保持同一份数据，因此推荐这样配置：

```env
DATABASE_URL=sqlite:///../data/ai_police.db
```

`backend/ai_police.db` 是旧本机库，保留用于必要时手工迁移；新的本地开发和 Docker 部署都应使用 `data/ai_police.db`。

## 常用维护脚本

- `python backend/cleanup_training_data.py`
  用于清理和修复历史文本乱码、异常分值和 JSON 字段。
- `python backend/cleanup_history_artifacts.py`
  用于预览或清理孤儿训练记录与纯问号占位消息。

示例：

```bash
python backend/cleanup_history_artifacts.py --report backend/history-artifacts-preview.json
python backend/cleanup_history_artifacts.py --apply --report backend/history-artifacts-apply.json
```

## 云部署

当前项目推荐直接使用根目录部署入口：

```bash
cp backend/.env.example backend/.env
docker compose up -d --build
```

部署说明见：

- **[DEPLOY.md](./DEPLOY.md)**（云服务器通用）
- [DEPLOY_TENCENT_CLOUD.md](./DEPLOY_TENCENT_CLOUD.md)（腾讯云简要）

## 部署提醒

- 生产环境请替换 `JWT_SECRET_KEY`
- 不要提交真实 `.env`
- 若改用 PostgreSQL，请显式设置完整 `DATABASE_URL`
- 若前后端分离部署，再补充 CORS 白名单配置
- 根目录 `Dockerfile` 和 `docker-compose.yml` 现在是唯一推荐部署入口
