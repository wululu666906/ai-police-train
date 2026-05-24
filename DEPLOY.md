# 云服务器部署指南

本项目采用 **单容器同域部署**：Vue 构建产物由 FastAPI 托管，浏览器访问同一端口即可，无需单独配置前端 API 地址。

## 上线前清单（5 步）

1. 服务器安装 Docker + Compose，放行端口 `8000`（或自定义 `APP_PORT`）
2. 上传代码（`git clone` 或 `python scripts/package_release.py` 生成的 zip）
3. `cp backend/.env.example backend/.env`，填写 **JWT_SECRET_KEY** 与 **LLM API Key**
4. `bash scripts/server_deploy.sh`（或 `docker compose up -d --build`）
5. 浏览器打开 `http://公网IP:8000`，登录后 **立即修改** 默认密码 `123456`

## 一、服务器要求

| 项目 | 建议 |
|------|------|
| 系统 | Linux x86_64（Ubuntu 22.04 / CentOS 7+） |
| 内存 | ≥ 4GB |
| 磁盘 | ≥ 20GB |
| 软件 | Docker 24+、Docker Compose v2 |
| 端口 | 开放 `8000`（或自定义 `APP_PORT`） |

## 二、上传代码到服务器

任选一种方式：

1. **Git**：`git clone` 到服务器（不要提交 `backend/.env`）
2. **压缩包**：本地执行 `python scripts/package_release.py`，将 `release/*.zip` 上传解压

解压后目录应包含：`Dockerfile`、`docker-compose.yml`、`start.sh`、`backend/`、`frontend/`、`scripts/`。

## 三、配置环境变量（必做）

```bash
cd /path/to/项目根目录
cp backend/.env.example backend/.env
nano backend/.env   # 或 vim
```

至少修改：

```env
JWT_SECRET_KEY=请改为至少32位随机字符串
DASHSCOPE_API_KEY=你的通义密钥
# 或 DEEPSEEK_API_KEY=你的 DeepSeek 密钥
```

可选：

```env
LLM_PROVIDER=qwen
DATABASE_URL=sqlite:///data/ai_police.db
```

生产环境 **不要** 使用示例里的 `replace-with-a-long-random-secret`。

## 四、一键部署（推荐）

```bash
chmod +x scripts/server_deploy.sh start.sh
bash scripts/server_deploy.sh
```

脚本会：检查 `.env` → 创建 `data/` → `docker compose up -d --build` → 访问 `/healthz`。

## 五、手动部署

```bash
mkdir -p data/chroma_db
touch data/ai_police.db

python3 scripts/deploy_check.py

docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/healthz
```

## 六、访问地址

| 用途 | URL |
|------|-----|
| 系统首页 | `http://<公网IP>:8000` |
| 健康检查 | `http://<公网IP>:8000/healthz` |
| API 文档 | `http://<公网IP>:8000/docs` |

默认账号（`init_db.py` 首次初始化）：

- 管理员：`admin` / `123456`
- 学员：`student001` / `123456`

**上线后请立即修改密码。**

## 七、数据持久化

| 宿主机路径 | 内容 |
|------------|------|
| `./data/ai_police.db` | SQLite 业务库 |
| `./data/chroma_db/` | 知识库向量（若启用 RAG） |

备份时复制整个 `data/` 目录即可。重建容器不会丢数据。

## 八、常用运维命令

```bash
# 查看日志
docker compose logs -f

# 重启（改代码或 .env 后）
docker compose up -d --build

# 停止
docker compose down

# 仅检查配置是否满足部署
python3 scripts/deploy_check.py
```

## 九、安全组 / 防火墙

- 入站放行 TCP `8000`（或你设置的 `APP_PORT`）
- 生产环境建议前面加 Nginx + HTTPS，仅反代到 `127.0.0.1:8000`

## 十、可选：PostgreSQL

若不用 SQLite，在 `backend/.env` 设置完整连接串，例如：

```env
DATABASE_URL=postgresql+psycopg2://user:pass@db-host:5432/ai_police
```

并去掉 `docker-compose.yml` 里对 `DATABASE_URL` 的覆盖。需自行准备 PostgreSQL 实例。

## 十一、故障排查

| 现象 | 处理 |
|------|------|
| 页面打不开 | `docker compose ps` 看容器是否 Up；检查安全组 |
| `healthz` 失败 | `docker compose logs -f` 看 Python 报错 |
| AI 不回复 | 检查 `.env` 中 API Key、服务器能否访问外网 |
| 数据库为空 | 确认 `data/ai_police.db` 是文件不是目录；删错误目录后 `touch data/ai_police.db` 再重启 |

## 十二、部署入口说明

**仅使用项目根目录这一套文件**，不要再用 `deploy_cloud_bundle/`（历史包，已过时）：

- `Dockerfile` — 多阶段构建前端 + 后端
- `docker-compose.yml` — 生产编排
- `start.sh` — 容器内启动（初始化库 + uvicorn）
- `backend/.env.example` — 环境变量模板
