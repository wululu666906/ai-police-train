# -*- coding: utf-8 -*-
"""现网快速增量部署（平台后端 docker cp + 前端 dist + 工作流 volume 重启）。

原则：
- 禁止打包 backend/venv、data、整棵 backend
- 禁止每次 docker build 全项目
- 工作流代码改完只需 scp + docker restart（依赖已 commit 到 runtime 镜像）
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "82.156.126.212"
USER = "panglihao"
PASSWORD = os.environ.get("DEPLOY_PASSWORD", "")
REMOTE = "/home/panglihao/ai-police-sim"
STAMP = time.strftime("%Y%m%d-%H%M%S")
DOCKER = "unix:///run/user/1002/docker.sock"

BACKEND_GLOBS = [
    "backend/*.py",
    "backend/requirements.txt",
    "backend/routers/**/*.py",
    "backend/services/**/*.py",
    "backend/config/**/*.py",
]
WF_GLOBS = ["ai_workflow_service/**/*.py", "ai_workflow_service/requirements.txt"]


def log(msg: str) -> None:
    print(msg, flush=True)


def changed_files() -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD", "--", "backend", "ai_workflow_service", "frontend/src"],
            cwd=ROOT,
            text=True,
            errors="replace",
        )
        names = [line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        names = []
    files: list[Path] = []
    if names:
        for name in names:
            p = ROOT / name
            if p.is_file() and not p.name.startswith(".env"):
                files.append(p)
    else:
        for pattern in BACKEND_GLOBS + WF_GLOBS:
            for p in ROOT.glob(pattern):
                if p.is_file() and "__pycache__" not in p.parts:
                    files.append(p)
    # dedupe
    seen: set[str] = set()
    out_files: list[Path] = []
    for p in files:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            out_files.append(p)
    return out_files


def build_tar(files: list[Path], include_dist: bool) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in files:
            tar.add(p, arcname=p.relative_to(ROOT).as_posix())
        if include_dist:
            dist = ROOT / "frontend" / "dist"
            for p in dist.rglob("*"):
                if p.is_file() and ".bak" not in p.name:
                    tar.add(p, arcname=p.relative_to(ROOT).as_posix())
    return buf.getvalue()


REMOTE_APPLY = f"""#!/usr/bin/env bash
set -euo pipefail
export DOCKER_HOST={DOCKER}
cd {REMOTE}
STAMP={STAMP}
APP_IMAGE=ai-police-train:codex-runtime-$STAMP
TAR=/tmp/fast-$STAMP.tar.gz
INCLUDE_DIST=${{INCLUDE_DIST:-0}}

echo "[1] 解压增量包"
tar -xzf "$TAR" -C {REMOTE}

if [ "$INCLUDE_DIST" = "1" ]; then
  echo "[2] 前端 dist 已更新（Nginx 读宿主机 frontend/dist）"
fi

echo "[3] docker cp 后端变更到运行中容器"
docker exec ai_police_app mkdir -p /app/backend/routers /app/backend/services
if [ -d backend/routers ]; then docker cp backend/routers/. ai_police_app:/app/backend/routers/; fi
if [ -d backend/services ]; then docker cp backend/services/. ai_police_app:/app/backend/services/; fi
shopt -s nullglob
for f in backend/*.py backend/requirements.txt; do
  [ -f "$f" ] || continue
  docker cp "$f" "ai_police_app:/app/backend/$(basename "$f")"
done
shopt -u nullglob
if [ "$INCLUDE_DIST" = "1" ] && [ -d frontend/dist ]; then
  docker exec ai_police_app rm -rf /app/frontend/dist
  docker exec ai_police_app mkdir -p /app/frontend/dist
  docker cp frontend/dist/. ai_police_app:/app/frontend/dist/
fi

echo "[4] 冒烟 + commit + 重启 app"
docker exec ai_police_app python -m py_compile /app/backend/main.py
docker commit ai_police_app "$APP_IMAGE"
if grep -q '^APP_IMAGE=' .env; then sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$APP_IMAGE|" .env; else echo "APP_IMAGE=$APP_IMAGE" >> .env; fi
docker compose -f docker-compose.image.yml up -d --no-deps app
sleep 6
curl -fsS http://127.0.0.1:15176/healthz

if [ -d ai_workflow_service ] && docker ps -a --format '{{{{.Names}}}}' | grep -q '^ai_police_workflow$'; then
  echo "[5] 工作流：volume 已挂载，仅 restart"
  docker restart ai_police_workflow
  for i in $(seq 1 40); do
    curl -fsS http://127.0.0.1:8020/healthz >/dev/null 2>&1 && break
    sleep 2
  done
  curl -fsS http://127.0.0.1:8020/healthz || true
fi

echo FAST_DEPLOY_OK stamp=$STAMP
"""


def main() -> int:
    if not PASSWORD:
        log("请设置 DEPLOY_PASSWORD")
        return 2

    files = changed_files()
    include_dist = any("frontend/src" in p.as_posix() for p in files) or not (ROOT / "frontend" / "dist" / "index.html").exists()
    if include_dist and (ROOT / "frontend" / "dist" / "index.html").exists():
        log("检测到前端源码变更或需同步 dist，请确保已 npm run build")

    payload = build_tar(files, include_dist=include_dist and (ROOT / "frontend" / "dist").exists())
    log(f"增量文件数={len(files)} dist={'是' if include_dist else '否'} 包大小={len(payload)/1024/1024:.1f}MB")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, 22, USER, PASSWORD, timeout=60, banner_timeout=60, auth_timeout=60)
    sftp = client.open_sftp()
    tar_path = f"/tmp/fast-{STAMP}.tar.gz"
    with sftp.file(tar_path, "wb") as rf:
        rf.write(payload)
    apply_path = f"/tmp/fast-apply-{STAMP}.sh"
    with sftp.file(apply_path, "w") as rf:
        rf.write(REMOTE_APPLY)
    sftp.chmod(apply_path, 0o755)
    sftp.close()

    env_prefix = "INCLUDE_DIST=1 " if include_dist else ""
    log("应用增量（通常 1-3 分钟）...")
    _, stdout, stderr = client.exec_command(f"{env_prefix}bash {apply_path}", timeout=600)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    print(out[-8000:])
    if err.strip():
        print("ERR:", err[-2000:])
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
