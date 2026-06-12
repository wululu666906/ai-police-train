# -*- coding: utf-8 -*-
"""Deploy to cloud server and run acceptance checks (paths + APIs)."""
from __future__ import annotations

import base64
import io
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = os.environ.get("DEPLOY_HOST", "129.211.8.122")
USER = os.environ.get("DEPLOY_USER", "ubuntu")
PASSWORD = os.environ.get("DEPLOY_PASSWORD", "")
REMOTE_DIR = "/opt/ai-police-sim"

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", ".pytest_cache",
    "chroma_db", "data", "release", "deploy_cloud_bundle", "deploy_native_bundle",
    "duiyou", ".cursor", ".idea", ".vscode", "terminals",
}
SKIP_FILES = {".env", ".db", ".sqlite3", ".pyc", ".zip", ".log"}


NGINX_CONF = """server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    client_max_body_size 50m;

    location /api/ {
        rewrite ^/api/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /assets/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location = /favicon.svg {
        proxy_pass http://127.0.0.1:8001;
    }

    location = /icons.svg {
        proxy_pass http://127.0.0.1:8001;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""


def build_env() -> str:
    local = ROOT / "backend" / ".env"
    example = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    vals: dict[str, str] = {}
    if local.exists():
        for line in local.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                vals[k.strip()] = v.strip()
    jwt = vals.get("JWT_SECRET_KEY") or vals.get("SECRET_KEY") or secrets.token_urlsafe(48)
    lines = []
    for line in example.splitlines():
        if line.startswith("JWT_SECRET_KEY="):
            lines.append(f"JWT_SECRET_KEY={jwt}")
        elif line.startswith("DEEPSEEK_API_KEY=") and vals.get("DEEPSEEK_API_KEY"):
            lines.append(f"DEEPSEEK_API_KEY={vals['DEEPSEEK_API_KEY']}")
        elif line.startswith("IFLYTEK_API_KEY=") and vals.get("IFLYTEK_API_KEY"):
            lines.append(f"IFLYTEK_API_KEY={vals['IFLYTEK_API_KEY']}")
        elif line.startswith("IFLYTEK_APP_ID=") and vals.get("IFLYTEK_APP_ID"):
            lines.append(f"IFLYTEK_APP_ID={vals['IFLYTEK_APP_ID']}")
        elif line.startswith("IFLYTEK_API_SECRET=") and vals.get("IFLYTEK_API_SECRET"):
            lines.append(f"IFLYTEK_API_SECRET={vals['IFLYTEK_API_SECRET']}")
        else:
            lines.append(line)
    body = "\n".join(lines) + "\n"
    if vals.get("DEEPSEEK_API_KEY"):
        body = body.replace("LLM_PROVIDER=qwen", "LLM_PROVIDER=deepseek")
        body = body.replace("EMBEDDING_PROVIDER=qwen", "EMBEDDING_PROVIDER=deepseek")
    return body


def should_skip(rel: Path) -> bool:
    if any(p in SKIP_DIRS for p in rel.parts):
        return True
    name = rel.name
    if name == ".env":
        return True
    return any(name.endswith(s) for s in SKIP_FILES)


def make_zip() -> bytes:
    dist = ROOT / "frontend" / "dist"
    if not (dist / "index.html").exists():
        raise FileNotFoundError("frontend/dist missing — run npm run build first")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in (ROOT / "backend", dist, ROOT / "deploy", ROOT / "scripts"):
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(ROOT)
                if should_skip(rel):
                    continue
                if folder.name == "scripts" and path.name.startswith("_remote"):
                    continue
                if path.name in {"remote_deploy_acceptance.py", "native_deploy_remote.py"}:
                    continue
                zf.write(path, str(rel).replace("\\", "/"))
        for name in ("README.md", "DEPLOY.md", "start.sh"):
            p = ROOT / name
            if p.exists():
                zf.write(p, name)
    return buf.getvalue()


def safe_print(text: str) -> None:
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout.buffer.write(text.encode(enc, errors="replace"))
    if not text.endswith("\n"):
        sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def run_remote(client: paramiko.SSHClient, script: str, timeout: int = 1800) -> tuple[int, str]:
    _, stdout, stderr = client.exec_command(f"bash -s <<'DEPLOY_EOF'\n{script}\nDEPLOY_EOF", timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        safe_print(out)
    if err.strip():
        safe_print("STDERR: " + err)
    return code, out + err


def http_check(url: str, method: str = "GET", data: bytes | None = None) -> tuple[int, str]:
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")[:500]
    except Exception as exc:
        return -1, str(exc)


def acceptance_tests() -> list[tuple[str, bool, str]]:
    base = f"http://{HOST}"
    results: list[tuple[str, bool, str]] = []

    code, body = http_check(f"{base}/")
    ok = code == 200 and ("index" in body.lower() or "app" in body)
    results.append(("GET / 前端首页", ok, f"http={code}"))

    code, body = http_check(f"{base}/healthz")
    results.append(("GET /healthz", code == 200 and "ok" in body, body[:80]))

    code, body = http_check(f"{base}/api/healthz")
    results.append(("GET /api/healthz", code == 200 and "ok" in body, body[:80]))

    login_data = urllib.parse.urlencode({"username": "admin", "password": "123456"}).encode()
    code, body = http_check(f"{base}/api/auth/token", "POST", login_data)
    has_token = "access_token" in body
    results.append(("POST /api/auth/token 登录", code == 200 and has_token, body[:120]))

    if has_token:
        import ssl

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        token = json.loads(body)["access_token"]
        req = urllib.request.Request(f"{base}/api/speech/iflytek/status")
        req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                sb = resp.read().decode()
                results.append(("GET /api/speech/iflytek/status", resp.status == 200, sb[:100]))
        except Exception as exc:
            results.append(("GET /api/speech/iflytek/status", False, str(exc)))

    code, body = http_check(f"{base}/assets/")
    results.append(("GET /assets/ 静态资源目录", code in (200, 403), f"http={code}"))

    return results


def main() -> int:
    pwd = PASSWORD or os.environ.get("DEPLOY_PASSWORD", "")
    if not HOST or not pwd:
        safe_print("Set DEPLOY_HOST and DEPLOY_PASSWORD before running.")
        return 1

    safe_print("Building deploy package...")
    payload = make_zip()
    safe_print(f"Package size: {len(payload) / 1024 / 1024:.2f} MB")
    env_b64 = base64.b64encode(build_env().encode()).decode()
    nginx_b64 = base64.b64encode(NGINX_CONF.encode()).decode()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=pwd, timeout=30)
    safe_print(f"Connected to {HOST}")

    deploy_script = f"""
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip nginx unzip curl

sudo mkdir -p {REMOTE_DIR}
sudo rm -rf {REMOTE_DIR}/*
cd {REMOTE_DIR}
sudo unzip -o /home/ubuntu/app_deploy.zip
sudo chown -R ubuntu:ubuntu {REMOTE_DIR}

# 路径：backend 与 frontend/dist 必须在同一项目根下
test -f {REMOTE_DIR}/backend/main.py
test -f {REMOTE_DIR}/frontend/dist/index.html
echo PATH_OK

cd {REMOTE_DIR}
sed -i 's/\\r$//' scripts/install_backend.sh start.sh 2>/dev/null || true
chmod +x scripts/install_backend.sh start.sh 2>/dev/null || true
PROJECT_DIR={REMOTE_DIR} bash scripts/install_backend.sh

echo '{env_b64}' | base64 -d > {REMOTE_DIR}/backend/.env
chmod 600 {REMOTE_DIR}/backend/.env

echo '{nginx_b64}' | base64 -d | sudo tee /etc/nginx/conf.d/ai-police-sim.conf >/dev/null
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
sudo nginx -t
sudo systemctl stop ai-police-nginx 2>/dev/null || true
sudo supervisorctl stop ai-police-nginx 2>/dev/null || true
sudo pkill -f 'nginx: master' 2>/dev/null || true
sleep 1
sudo nginx

sudo mkdir -p /var/log/ai-police-sim
sudo chown ubuntu:ubuntu /var/log/ai-police-sim
if [ -f {REMOTE_DIR}/deploy/supervisor/ai-police-backend.conf ]; then
  sudo cp {REMOTE_DIR}/deploy/supervisor/ai-police-backend.conf /etc/supervisor/conf.d/
fi
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart ai-police-backend 2>/dev/null || sudo supervisorctl start ai-police-backend

sleep 4
curl -fsS http://127.0.0.1:80/healthz
curl -fsS http://127.0.0.1:80/api/healthz
curl -fsS -X POST http://127.0.0.1:80/api/auth/token -d 'username=admin&password=123456' | head -c 120
echo
sudo supervisorctl status
ls -la {REMOTE_DIR}/frontend/dist/index.html
"""

    sftp = client.open_sftp()
    with sftp.file("/home/ubuntu/app_deploy.zip", "wb") as f:
        f.write(payload)
    sftp.close()

    code, _ = run_remote(client, deploy_script, timeout=1800)
    client.close()

    safe_print("\n=== 外网验收 ===")
    all_ok = code == 0
    for name, ok, detail in acceptance_tests():
        status = "PASS" if ok else "FAIL"
        safe_print(f"[{status}] {name} — {detail}")
        all_ok = all_ok and ok

    safe_print(f"\n访问地址: http://{HOST}/")
    safe_print("默认账号: admin / 123456")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
