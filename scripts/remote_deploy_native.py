# -*- coding: utf-8 -*-
"""Deploy latest main branch to cloud server (native nginx + uvicorn)."""
from __future__ import annotations

import base64
import io
import os
import secrets
import subprocess
import sys
import zipfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = os.environ.get("DEPLOY_HOST", "")
USER = os.environ.get("DEPLOY_USER", "panglihao")
PASSWORD = os.environ.get("DEPLOY_PASSWORD", "")
PORT = int(os.environ.get("DEPLOY_PORT", "5175"))
REMOTE_DIR = os.environ.get("DEPLOY_DIR", "/opt/ai-police-sim")
DEFAULT_NODE = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", ".pytest_cache",
    "chroma_db", "data", "release", "deploy_cloud_bundle", "deploy_native_bundle",
    "duiyou", ".cursor", ".idea", ".vscode", "terminals",
}
SKIP_FILES = {".env", ".db", ".sqlite3", ".pyc", ".zip", ".log"}


def build_frontend() -> None:
    print("Building frontend (VITE_API_URL=/api)...")
    env = {**dict(__import__("os").environ), "VITE_API_URL": "/api"}
    vite_js = ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    node_exe = Path(os.environ.get("NODE_EXE", str(DEFAULT_NODE)))
    if node_exe.exists() and vite_js.exists():
        cmd = [str(node_exe), str(vite_js), "build"]
        use_shell = False
    else:
        cmd = ["npm", "run", "build"]
        use_shell = True
    subprocess.run(
        cmd,
        cwd=ROOT / "frontend",
        env=env,
        check=True,
        shell=use_shell,
    )
    dist = ROOT / "frontend" / "dist" / "index.html"
    if not dist.exists():
        raise RuntimeError("frontend build failed: dist/index.html missing")


def build_env_content() -> str:
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
    if ".bak_" in name or name.endswith(".bak"):
        return True
    if name.endswith(".db") or name.endswith(".sqlite3"):
        return True
    return any(name.endswith(s) for s in SKIP_FILES)


def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder, label in [
            (ROOT / "backend", "backend"),
            (ROOT / "frontend" / "dist", "frontend/dist"),
            (ROOT / "deploy", "deploy"),
            # deploy/scripts included via deploy tree
            (ROOT / "scripts", "scripts"),
        ]:
            for path in folder.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(ROOT)
                if should_skip(rel):
                    continue
                if label == "scripts" and path.name in {
                    "remote_deploy_native.py",
                    "_remote",
                }:
                    continue
                if label == "scripts" and path.name.startswith("_"):
                    continue
                zf.write(path, str(rel).replace("\\", "/"))
    return buf.getvalue()


def safe_print(text: str) -> None:
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout.buffer.write((text + "\n").encode(enc, errors="replace"))


def run_remote(client: paramiko.SSHClient, cmd: str, timeout: int = 1800) -> tuple[int, str]:
    redacted = cmd.replace(PASSWORD, "***") if PASSWORD else cmd
    if PASSWORD:
        redacted = redacted.replace(base64.b64encode(PASSWORD.encode()).decode(), "***")
    safe_print(f">>> {redacted[:160]}...")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        safe_print(out.rstrip())
    if err.strip():
        safe_print("STDERR: " + err.rstrip())
    return code, out + err


def remote_sudo_prelude() -> str:
    password_b64 = base64.b64encode(PASSWORD.encode()).decode()
    return f"""
SUDO_PASSWORD=$(printf %s '{password_b64}' | base64 -d)
sudo() {{
  printf '%s\\n' "$SUDO_PASSWORD" | command sudo -S -p '' "$@"
}}
"""


def acceptance_checks(client: paramiko.SSHClient) -> bool:
    checks = remote_sudo_prelude() + r"""
set -e
BASE=https://127.0.0.1
CURL="curl -fsSk"
echo "=== path layout ==="
test -f /opt/ai-police-sim/frontend/dist/index.html && echo OK_dist_index
test -f /opt/ai-police-sim/backend/main.py && echo OK_backend_main
test -d /opt/ai-police-sim/frontend/dist/assets && echo OK_dist_assets
python3 -c "
from pathlib import Path
p=Path('/opt/ai-police-sim/backend/main.py').resolve()
d=(p.parent/'../frontend/dist').resolve()
print('backend_main', p)
print('frontend_dist', d)
print('dist_exists', d.joinpath('index.html').is_file())
"

echo "=== HTTPS checks (nginx :443) ==="
$CURL -o /dev/null -w "http_redirect=%{http_code}\n" http://127.0.0.1/ || true
$CURL -o /dev/null -w "home=%{http_code}\n" https://127.0.0.1/
$CURL https://127.0.0.1/healthz && echo
$CURL https://127.0.0.1/api/healthz && echo
HTML=$($CURL https://127.0.0.1/)
echo "$HTML" | grep -q '/assets/' && echo OK_html_assets_path
ASSET=$(echo "$HTML" | grep -oE '/assets/[^"]+\.js' | head -1)
test -n "$ASSET" && $CURL -o /dev/null -w "asset=%{http_code}\n" "https://127.0.0.1$ASSET"
TOKEN=$($CURL -X POST https://127.0.0.1/api/auth/token -d 'username=admin&password=123456')
echo "$TOKEN" | grep -q access_token && echo OK_login_api

echo "=== public IP :443 ==="
$CURL -m 8 -o /dev/null -w "public_home=%{http_code}\n" https://{HOST}/ || echo public_home_fail
sudo supervisorctl status
sudo systemctl is-active nginx
""".replace("{HOST}", HOST)
    code, out = run_remote(client, checks, timeout=120)
    required = [
        "OK_dist_index",
        "OK_dist_assets",
        "dist_exists",
        "home=200",
        "OK_html_assets_path",
        "OK_login_api",
    ]
    ok = code == 0 and all(k in out for k in required)
    safe_print("\n=== ACCEPTANCE: " + ("PASS" if ok else "FAIL") + " ===")
    return ok


def require_deploy_credentials() -> None:
    if not HOST or not PASSWORD:
        raise SystemExit(
            "Set DEPLOY_HOST and DEPLOY_PASSWORD (optional: DEPLOY_USER, DEPLOY_PORT, DEPLOY_DIR) before running."
        )


def remote_home_dir(client: paramiko.SSHClient) -> str:
    _, stdout, _ = client.exec_command("printf %s \"$HOME\"")
    value = stdout.read().decode("utf-8", errors="replace").strip()
    return value or f"/home/{USER}"


def build_supervisor_backend_conf(remote_home: str) -> str:
    return f"""[program:ai-police-backend]
directory={REMOTE_DIR}/backend
command={REMOTE_DIR}/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001
autostart=true
autorestart=true
startsecs=5
stopwaitsecs=10
user={USER}
stdout_logfile=/var/log/ai-police-sim/backend.out.log
stderr_logfile=/var/log/ai-police-sim/backend.err.log
environment=HOME="{remote_home}",PATH="{REMOTE_DIR}/backend/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
"""


def main() -> int:
    require_deploy_credentials()
    build_frontend()
    payload = make_zip()
    safe_print(f"Package size: {len(payload) / 1024 / 1024:.2f} MB")

    env_b64 = base64.b64encode(build_env_content().encode()).decode()
    le_conf = (ROOT / "deploy" / "nginx" / "ai-police-sim-letsencrypt.conf").read_text(encoding="utf-8")
    le_b64 = base64.b64encode(le_conf.encode()).decode()
    fallback_conf = (ROOT / "deploy" / "nginx" / "ai-police-sim.conf").read_text(encoding="utf-8")
    fallback_b64 = base64.b64encode(fallback_conf.encode()).decode()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    safe_print(f"Connected to {HOST}")
    remote_home = remote_home_dir(client)

    run_remote(client, f"docker compose -f {remote_home}/ai-police-platform/app_src/docker-compose.yml down 2>/dev/null || true")
    run_remote(client, "sudo pkill -f 'uvicorn main:app' 2>/dev/null || true")

    sftp = client.open_sftp()
    with sftp.file(f"{remote_home}/ai_police_deploy.zip", "wb") as f:
        f.write(payload)
    sftp.close()

    supervisor_conf_b64 = base64.b64encode(build_supervisor_backend_conf(remote_home).encode()).decode()

    setup = f"""
set -euo pipefail
{remote_sudo_prelude()}
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip nginx unzip supervisor curl ffmpeg

BACKUP_DIR=$(mktemp -d)
if [ -d {REMOTE_DIR}/data ]; then
  cp -a {REMOTE_DIR}/data "$BACKUP_DIR/data"
fi
if [ -d {REMOTE_DIR}/backend/static/videos ]; then
  mkdir -p "$BACKUP_DIR/static"
  cp -a {REMOTE_DIR}/backend/static/videos "$BACKUP_DIR/static/videos"
fi
if [ -d {REMOTE_DIR}/backend/static/thumbnails ]; then
  mkdir -p "$BACKUP_DIR/static"
  cp -a {REMOTE_DIR}/backend/static/thumbnails "$BACKUP_DIR/static/thumbnails"
fi

sudo rm -rf {REMOTE_DIR}
sudo mkdir -p {REMOTE_DIR}
sudo unzip -o {remote_home}/ai_police_deploy.zip -d {REMOTE_DIR}
sudo chown -R {USER}:{USER} {REMOTE_DIR}

if [ -d "$BACKUP_DIR/data" ]; then
  rm -rf {REMOTE_DIR}/data
  cp -a "$BACKUP_DIR/data" {REMOTE_DIR}/data
fi
if [ -d "$BACKUP_DIR/static/videos" ]; then
  rm -rf {REMOTE_DIR}/backend/static/videos
  mkdir -p {REMOTE_DIR}/backend/static
  cp -a "$BACKUP_DIR/static/videos" {REMOTE_DIR}/backend/static/videos
fi
if [ -d "$BACKUP_DIR/static/thumbnails" ]; then
  rm -rf {REMOTE_DIR}/backend/static/thumbnails
  mkdir -p {REMOTE_DIR}/backend/static
  cp -a "$BACKUP_DIR/static/thumbnails" {REMOTE_DIR}/backend/static/thumbnails
fi
sudo chown -R {USER}:{USER} {REMOTE_DIR}

cd {REMOTE_DIR}
find scripts -name '*.sh' -exec sed -i 's/\\r$//' {{}} +
chmod +x scripts/install_backend.sh
PROJECT_DIR={REMOTE_DIR} bash scripts/install_backend.sh

echo '{env_b64}' | base64 -d > {REMOTE_DIR}/backend/.env
chmod 600 {REMOTE_DIR}/backend/.env

sudo mkdir -p /var/log/ai-police-sim
sudo chown {USER}:{USER} /var/log/ai-police-sim

sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/ai-police-sim 2>/dev/null || true
sudo rm -f /etc/nginx/sites-available/ai-police-sim 2>/dev/null || true
sudo mkdir -p /etc/ssl/private /etc/ssl/certs
if [ ! -f /etc/ssl/certs/ai-police-selfsigned.crt ]; then
  sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout /etc/ssl/private/ai-police-selfsigned.key \
    -out /etc/ssl/certs/ai-police-selfsigned.crt \
    -subj "/CN={HOST}" \
    -addext "subjectAltName=IP:{HOST}"
fi
if [ -f /etc/letsencrypt/live/ai-police-ip/fullchain.pem ]; then
  echo '{le_b64}' | base64 -d | sudo tee /etc/nginx/conf.d/ai-police-sim.conf
else
  echo '{fallback_b64}' | base64 -d | sudo tee /etc/nginx/conf.d/ai-police-sim.conf
fi
sudo mkdir -p /var/www/certbot
sudo chown -R www-data:www-data /var/www/certbot
for port in 80 443; do
  if sudo ss -tlnp | grep -q ":${{port}} "; then
    sudo fuser -k ${{port}}/tcp 2>/dev/null || true
    sleep 1
  fi
done
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

sudo rm -f /etc/supervisor/conf.d/ai-police-nginx.conf 2>/dev/null || true

echo '{supervisor_conf_b64}' | base64 -d | sudo tee /etc/supervisor/conf.d/ai-police-backend.conf >/dev/null
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart ai-police-backend || sudo supervisorctl start ai-police-backend

sleep 4
"""
    code, _ = run_remote(client, setup, timeout=1800)
    if code != 0:
        client.close()
        return 1

    apply_letsencrypt_nginx(client)
    passed = acceptance_checks(client)
    client.close()

    safe_print(f"\n访问地址: https://{HOST}/")
    safe_print("默认账号: admin / 123456")
    return 0 if passed else 1


def apply_letsencrypt_nginx(client: paramiko.SSHClient) -> bool:
    """Ensure LE IP cert exists and nginx uses trusted HTTPS config."""
    le_conf = (ROOT / "deploy" / "nginx" / "ai-police-sim-letsencrypt.conf").read_text(encoding="utf-8")
    le_b64 = base64.b64encode(le_conf.encode()).decode()
    bootstrap_b64 = base64.b64encode(
        f"""
server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type "text/plain";
        allow all;
    }}
    location / {{ return 301 https://$host$request_uri; }}
}}
""".encode()
    ).decode()

    script = f"""
set -euo pipefail
{remote_sudo_prelude()}
sudo mkdir -p /var/www/certbot /etc/letsencrypt/renewal-hooks/deploy
sudo chown -R www-data:www-data /var/www/certbot

if ! command -v certbot >/dev/null 2>&1 || ! certbot --version 2>&1 | grep -qE 'certbot ([5-9]|[1-9][0-9])'; then
  sudo snap install core 2>/dev/null || true
  sudo snap refresh core 2>/dev/null || true
  sudo snap install --classic certbot
  sudo ln -sf /snap/bin/certbot /usr/bin/certbot
fi

if [ ! -f /etc/letsencrypt/live/ai-police-ip/fullchain.pem ]; then
  echo '{bootstrap_b64}' | base64 -d | sudo tee /etc/nginx/conf.d/ai-police-sim.conf
  sudo nginx -t && sudo systemctl restart nginx
  sudo systemctl stop nginx
  sudo certbot certonly --standalone --non-interactive --agree-tos \\
    --register-unsafely-without-email \\
    --cert-name ai-police-ip \\
    --preferred-profile shortlived \\
    --ip-address {HOST}
fi

echo '{le_b64}' | base64 -d | sudo tee /etc/nginx/conf.d/ai-police-sim.conf
sudo bash -c 'printf "%s\\n" "#!/bin/sh" "systemctl reload nginx" > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh'
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
if [ -f /etc/letsencrypt/renewal/ai-police-ip.conf ] && grep -q 'authenticator = standalone' /etc/letsencrypt/renewal/ai-police-ip.conf; then
  sudo sed -i 's/^authenticator = standalone/authenticator = webroot/' /etc/letsencrypt/renewal/ai-police-ip.conf
  if ! grep -q '^webroot_path' /etc/letsencrypt/renewal/ai-police-ip.conf; then
    sudo sed -i '/^authenticator = webroot/a webroot_path = /var/www/certbot,' /etc/letsencrypt/renewal/ai-police-ip.conf
  fi
fi
sudo nginx -t
sudo systemctl restart nginx
sudo test -f /etc/letsencrypt/live/ai-police-ip/fullchain.pem && echo OK_le_nginx
"""
    _, out = run_remote(client, script, timeout=600)
    return "OK_le_nginx" in out


def issue_letsencrypt_ip_cert() -> int:
    """Request Let's Encrypt short-lived certificate for public IP (SAN=IP)."""
    require_deploy_credentials()
    # Bootstrap nginx: HTTP + ACME only (443 uses temporary self-signed until cert exists)
    bootstrap_conf = f"""
server {{
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type "text/plain";
        allow all;
    }}
    location / {{ return 301 https://$host$request_uri; }}
}}
server {{
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    server_name _;
    ssl_certificate /etc/ssl/certs/ai-police-selfsigned.crt;
    ssl_certificate_key /etc/ssl/private/ai-police-selfsigned.key;
    return 444;
}}
"""
    bootstrap_b64 = base64.b64encode(bootstrap_conf.encode()).decode()
    le_conf = (ROOT / "deploy" / "nginx" / "ai-police-sim-letsencrypt.conf").read_text(encoding="utf-8")
    le_b64 = base64.b64encode(le_conf.encode()).decode()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    safe_print(f"Connected to {HOST} — requesting Let's Encrypt IP certificate")

    issue = f"""
set -euo pipefail
{remote_sudo_prelude()}
export DEBIAN_FRONTEND=noninteractive

sudo mkdir -p /var/www/certbot /etc/letsencrypt/renewal-hooks/deploy
sudo chown -R www-data:www-data /var/www/certbot

if ! command -v certbot >/dev/null 2>&1 || ! certbot --version 2>&1 | grep -qE 'certbot ([5-9]|[1-9][0-9])'; then
  sudo snap install core 2>/dev/null || true
  sudo snap refresh core 2>/dev/null || true
  sudo snap install --classic certbot
  sudo ln -sf /snap/bin/certbot /usr/bin/certbot
fi
certbot --version

sudo mkdir -p /etc/ssl/private /etc/ssl/certs
if [ ! -f /etc/ssl/certs/ai-police-selfsigned.crt ]; then
  sudo openssl req -x509 -nodes -days 30 -newkey rsa:2048 \
    -keyout /etc/ssl/private/ai-police-selfsigned.key \
    -out /etc/ssl/certs/ai-police-selfsigned.crt \
    -subj "/CN={HOST}" \
    -addext "subjectAltName=IP:{HOST}"
fi

echo '{bootstrap_b64}' | base64 -d | sudo tee /etc/nginx/conf.d/ai-police-sim.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

if [ ! -f /etc/letsencrypt/live/ai-police-ip/fullchain.pem ]; then
  sudo systemctl stop nginx
  sudo certbot certonly --standalone --non-interactive --agree-tos \\
    --register-unsafely-without-email \\
    --cert-name ai-police-ip \\
    --preferred-profile shortlived \\
    --ip-address {HOST}
fi
sudo test -f /etc/letsencrypt/live/ai-police-ip/fullchain.pem

echo '{le_b64}' | base64 -d | sudo tee /etc/nginx/conf.d/ai-police-sim.conf
sudo cp {REMOTE_DIR}/deploy/scripts/reload-nginx.sh /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh 2>/dev/null || true
sudo bash -c 'cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh <<EOF
#!/bin/sh
systemctl reload nginx
EOF'
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx

if grep -q 'authenticator = standalone' /etc/letsencrypt/renewal/ai-police-ip.conf 2>/dev/null; then
  sudo sed -i 's/^authenticator = standalone/authenticator = webroot/' /etc/letsencrypt/renewal/ai-police-ip.conf
  if ! grep -q '^webroot_path' /etc/letsencrypt/renewal/ai-police-ip.conf; then
    sudo sed -i '/^authenticator = webroot/a webroot_path = /var/www/certbot,' /etc/letsencrypt/renewal/ai-police-ip.conf
  fi
fi
sudo certbot renew --dry-run && echo OK_renew_dry_run || echo WARN_renew_dry_run
echo OK_letsencrypt_issued
sudo openssl x509 -in /etc/letsencrypt/live/ai-police-ip/fullchain.pem -noout -issuer -dates
"""
    code, out = run_remote(client, issue, timeout=600)
    if "OK_letsencrypt_issued" not in out:
        safe_print("Let's Encrypt setup failed — see output above")
        client.close()
        return 1

    # Verify trusted chain (no -k)
    verify = f"""
set -e
curl -fsS -o /dev/null -w "trusted_home=%{{http_code}}\\n" https://{HOST}/
echo | openssl s_client -connect {HOST}:443 -servername {HOST} 2>/dev/null | openssl x509 -noout -issuer -subject
"""
    _, vout = run_remote(client, verify, timeout=60)
    passed = acceptance_checks(client)
    client.close()
    safe_print(f"\n访问地址: https://{HOST}/")
    safe_print("证书：Let's Encrypt 公网 IP 证书（shortlived，约 6 天，certbot 自动续期 + webroot）")
    safe_print("续期检查：systemctl list-timers | grep certbot")
    if "Let's Encrypt" in vout:
        safe_print("浏览器应显示受信任 HTTPS（无需再点「继续访问」）")
    return 0 if passed else 1


def enable_https_only() -> int:
    """Switch existing deployment to HTTPS without full rebuild."""
    require_deploy_credentials()
    nginx_conf = (ROOT / "deploy" / "nginx" / "ai-police-sim.conf").read_text(encoding="utf-8")
    nginx_b64 = base64.b64encode(nginx_conf.encode()).decode()
    env_b64 = base64.b64encode(build_env_content().encode()).decode()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    safe_print(f"Connected to {HOST} — enabling HTTPS")

    setup = f"""
set -euo pipefail
{remote_sudo_prelude()}
echo '{env_b64}' | base64 -d > {REMOTE_DIR}/backend/.env
chmod 600 {REMOTE_DIR}/backend/.env
sudo supervisorctl restart ai-police-backend
sleep 3

sudo mkdir -p /etc/ssl/private /etc/ssl/certs
sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout /etc/ssl/private/ai-police-selfsigned.key \
  -out /etc/ssl/certs/ai-police-selfsigned.crt \
  -subj "/CN={HOST}" \
  -addext "subjectAltName=IP:{HOST}"

sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/ai-police-sim 2>/dev/null || true
echo '{nginx_b64}' | base64 -d | sudo tee /etc/nginx/conf.d/ai-police-sim.conf
for port in 80 443; do
  if sudo ss -tlnp | grep -q ":$port "; then
    sudo fuser -k ${{port}}/tcp 2>/dev/null || true
    sleep 1
  fi
done
sudo nginx -t
sudo systemctl restart nginx
sleep 2
"""
    code, _ = run_remote(client, setup, timeout=300)
    if code != 0:
        client.close()
        return 1
    passed = acceptance_checks(client)
    client.close()
    safe_print(f"\n访问地址: https://{HOST}/")
    return 0 if passed else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--https-only":
        sys.exit(enable_https_only())
    if len(sys.argv) > 1 and sys.argv[1] == "--letsencrypt-ip":
        sys.exit(issue_letsencrypt_ip_cert())
    sys.exit(main())
