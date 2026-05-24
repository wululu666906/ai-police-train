# 腾讯云部署说明

> 通用步骤与故障排查见 **[DEPLOY.md](./DEPLOY.md)**。下文为腾讯云快速指引。

这份项目现在推荐使用“单容器同域部署”：

- `FastAPI` 提供后端接口
- `Vue` 构建产物由后端同域托管
- 浏览器访问时不需要再额外配置前端接口地址

## 1. 部署前准备

服务器建议：

- Linux x86_64
- 已安装 Docker
- 已开放 `8000` 端口

在项目中准备环境变量：

```bash
cp backend/.env.example backend/.env
```

至少需要补齐：

- `JWT_SECRET_KEY`
- `DASHSCOPE_API_KEY` 或 `DEEPSEEK_API_KEY`
- 如需外部数据库，再修改 `DATABASE_URL`

如果继续使用 SQLite，保留：

```env
DATABASE_URL=sqlite:///ai_police.db
```

## 2. Docker Compose 部署

在项目根目录执行：

```bash
bash scripts/server_deploy.sh
# 或
docker compose up -d --build
```

启动后访问：

- 首页：`http://服务器公网IP:8000`
- 健康检查：`http://服务器公网IP:8000/healthz`
- 接口文档：`http://服务器公网IP:8000/docs`

## 3. 目录说明

当前部署以根目录为唯一来源：

- 根目录 `Dockerfile`：生产镜像构建入口
- 根目录 `docker-compose.yml`：推荐启动方式
- 根目录 `start.sh`：容器启动脚本
- `backend/.env.example`：环境变量模板

`deploy_cloud_bundle/` 仅可视为历史参考，不再建议作为正式部署源。

## 4. 常用命令

查看日志：

```bash
docker compose logs -f
```

重启：

```bash
docker compose up -d --build
```

停止：

```bash
docker compose down
```
