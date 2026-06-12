"""Full native deployment: install deps, build frontend, run app."""
import io
import os
import sys
import time

# Fix for Windows terminal encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"
APP_PORT = 5175

PY = f"{DEPLOY_DIR}/venv/bin/python3"
PIP = f"{DEPLOY_DIR}/venv/bin/pip"
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def create_client():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    log(f"Connecting to {SERVER} as {USER}...")
    c.connect(SERVER, port=22, username=USER, password=PASSWORD,
              look_for_keys=False, allow_agent=False, timeout=30)
    log("Connected.")
    return c


def run(client, cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return ec, out.strip(), err.strip()


def show(client, cmd, timeout=30):
    ec, o, e = run(client, cmd, timeout)
    print(f"  {o[:300]}")

def main():
    client = create_client()
    try:
        # === Step 1: Install Python deps ===
        log("\n=== Step 1: Install Python dependencies ===")
        ec, o, e = run(client,
            f"{PIP} install -r {DEPLOY_DIR}/backend/requirements.txt -i {MIRROR} --progress-bar off 2>&1",
            timeout=300)
        # Filter out progress bar lines
        clean_lines = [l for l in o.split("\n") if l.strip() and not any(c in l for c in ["─", "╸", "▇", "█", "▏"])]
        for line in clean_lines[-15:]:
            log(f"  {line[:200]}")
        for line in e.split("\n")[-5:]:
            if line.strip():
                log(f"  ERR: {line}")
        if ec != 0:
            log("WARNING: pip install had errors, continuing...")

        # Verify key packages
        log("\nVerifying packages...")
        for pkg in ["fastapi", "uvicorn", "sqlalchemy", "openai", "passlib", "python_multipart", "jose", "pydantic"]:
            ec_pkg, o_pkg, _ = run(client,
                f"{PY} -c 'import {pkg}; print({pkg}.__version__)' 2>&1 || echo NOT_FOUND")
            log(f"  {pkg}: {o_pkg[:50]}")

        # === Step 2: Build frontend ===
        log("\n=== Step 2: Build Frontend ===")
        log("Installing npm packages...")
        ec, o, e = run(client,
            f"cd {DEPLOY_DIR}/frontend && npm install 2>&1 | tail -10", timeout=180)
        log(f"npm install: {o[:200]}")
        if ec != 0:
            log(f"npm install failed: {e[:200]}")

        log("Building frontend...")
        ec, o, e = run(client,
            f"cd {DEPLOY_DIR}/frontend && npm run build 2>&1", timeout=180)
        log(f"Build output: {o[:300].encode('utf-8', errors='replace').decode('utf-8')}")
        if ec != 0:
            log(f"WARNING: Frontend build had issues: {e[:300].encode('utf-8', errors='replace').decode('utf-8')}")

        # Check if dist was created
        ec, o, _ = run(client, f"ls -la {DEPLOY_DIR}/frontend/dist/ 2>&1")
        log(f"Frontend dist: {o[:200]}")

        # === Step 3: Ensure ChromaDB dir ===
        log("\n=== Step 3: Prepare data directories ===")
        run(client, f"mkdir -p {DEPLOY_DIR}/data/chroma_db")

        # === Step 4: Initialize database ===
        log("\n=== Step 4: Initialize Database ===")
        ec, o, e = run(client, f"cd {DEPLOY_DIR}/backend && {PY} init_db.py 2>&1", timeout=15)
        log(f"DB init: {o[:200]}")

        # Check DB
        ec, o, _ = run(client, f"ls -la {DEPLOY_DIR}/backend/ai_police.db")
        log(f"DB file: {o}")

        # === Step 5: Start application ===
        log("\n=== Step 5: Start Application ===")
        # Kill any existing process on APP_PORT
        run(client, f"pkill -f 'uvicorn.*{APP_PORT}' 2>/dev/null || true")
        time.sleep(1)

        # Start uvicorn with nohup
        log(f"Starting uvicorn on port {APP_PORT}...")
        ec, o, e = run(client,
            f"cd {DEPLOY_DIR}/backend && nohup {PY} -m uvicorn main:app "
            f"--host 0.0.0.0 --port {APP_PORT} "
            f"--log-level info > {DEPLOY_DIR}/app.log 2>&1 & echo 'PID: '$!",
            timeout=10)
        log(f"App start: {o[:100]}")

        # Wait for it to become ready
        log("Waiting for health check...")
        ready = False
        for i in range(30):
            ec, o, e = run(client,
                f"curl -fsSo /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/healthz 2>/dev/null || echo 000",
                timeout=5)
            if o == "200":
                log(f"Health check OK! (attempt {i+1}, ~{i*2}s)")
                ready = True
                break
            if i == 5:
                # After 10s check if process is running
                ec, o, _ = run(client, f"ps aux | grep 'uvicorn.*{APP_PORT}' | grep -v grep")
                log(f"Process check: {o[:200]}")
            time.sleep(2)

        if not ready:
            log("WARNING: Health check timeout. Checking logs...")
            ec, logs, _ = run(client, f"tail -50 {DEPLOY_DIR}/app.log")
            log(f"App logs:\n{logs}")
        else:
            # === Step 6: Verification ===
            log("\n=== Step 6: Verification ===")
            ec, o, _ = run(client, f"curl -s http://127.0.0.1:{APP_PORT}/healthz")
            log(f"Health: {o}")

            ec, o, _ = run(client, f"curl -s http://127.0.0.1:{APP_PORT}/api/healthz")
            log(f"API health: {o}")

            ec, o, _ = run(client, f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/docs")
            log(f"API docs status: {o}")

            ec, o, _ = run(client,
                f"curl -s -X POST http://127.0.0.1:{APP_PORT}/auth/token "
                f"-d 'username=admin&password=123456' 2>/dev/null || echo 'Login test: failed'")
            log(f"Login test: {o[:150]}")

        # === Summary ===
        log("\n" + "="*60)
        log("DEPLOYMENT COMPLETE")
        log("="*60)
        log(f"")
        log(f"  System URL:     http://{SERVER}:{APP_PORT}")
        log(f"  Health check:   http://{SERVER}:{APP_PORT}/healthz")
        log(f"  API Docs:       http://{SERVER}:{APP_PORT}/docs")
        log(f"")
        log(f"  Default admin:   admin / 123456")
        log(f"  Default student: student001 / 123456")
        log(f"")
        log(f"  View logs:      tail -f {DEPLOY_DIR}/app.log")
        log(f"")
        log(f"  Restart app:")
        log(f"    pkill -f 'uvicorn.*{APP_PORT}'")
        log(f"    cd {DEPLOY_DIR}/backend && nohup {PY} -m uvicorn main:app --host 0.0.0.0 --port {APP_PORT} > {DEPLOY_DIR}/app.log 2>&1 &")

    except Exception as e:
        log(f"ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
