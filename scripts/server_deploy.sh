#!/usr/bin/env bash
# 在云服务器项目根目录执行：bash scripts/server_deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[1/5] 检查环境..."
if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "    已从模板创建 backend/.env，请编辑后重新运行本脚本。"
  exit 1
fi

python3 scripts/deploy_check.py || exit 1

echo "[2/5] 准备数据目录..."
mkdir -p data/chroma_db
if [[ ! -f data/ai_police.db ]]; then
  : > data/ai_police.db
fi

echo "[3/5] 构建并启动容器..."
docker compose up -d --build

APP_PORT="${APP_PORT:-8000}"

echo "[4/5] 等待服务就绪..."
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${APP_PORT}/healthz" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[5/5] 健康检查..."
curl -fsS "http://127.0.0.1:${APP_PORT}/healthz" && echo ""

echo ""
echo "部署完成。浏览器访问：http://<服务器公网IP>:${APP_PORT}"
echo "默认账号：admin / 123456  （首次登录后请修改密码）"
echo "查看日志：docker compose logs -f"
