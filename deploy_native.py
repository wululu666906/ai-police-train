"""Native deployment: install pip, Python deps, build frontend, run app."""
import os
import sys
import time

import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"
APP_PORT = 5175  # User specified port


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def create_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    log(f"Connecting to {SERVER} as {USER}...")
    client.connect(SERVER, port=22, username=USER, password=PASSWORD,
                   look_for_keys=False, allow_agent=False, timeout=30)
    log("Connected.")
    return client


def run(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return exit_code, out.strip(), err.strip()


def install_pip(client):
    """Install pip in user space via get-pip.py."""
    log("Downloading get-pip.py...")
    exit_code, out, err = run(client,
        "curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py 2>&1", timeout=30)
    if exit_code != 0:
        log(f"Failed to download get-pip.py: {err}")
        return False

    log("Installing pip (user mode)...")
    exit_code, out, err = run(client,
        "python3 /tmp/get-pip.py --user 2>&1", timeout=120)
    log(f"pip install output: {out[:200]}")
    if exit_code != 0 or "error" in out.lower():
        log(f"pip install failed: {err[:200]}")
        return False

    # Verify pip works
    exit_code, out, err = run(client,
        "python3 -m pip --version 2>&1")
    log(f"pip: {out[:100]}")
    return exit_code == 0


def install_python_deps(client):
    """Install Python dependencies in user space."""
    log("Installing Python dependencies...")
    req_path = f"{DEPLOY_DIR}/backend/requirements.txt"
    exit_code, out, err = run(client,
        f"python3 -m pip install --user -r {req_path} 2>&1", timeout=300)
    log(f"Deps install output: {out[:300]}")
    if exit_code != 0 or "error" in out.lower():
        # Check for actual errors, not just warnings
        error_lines = [l for l in out.split("\n") if "ERROR" in l.upper()]
        if error_lines:
            log(f"Dependency installation errors:")
            for e_line in error_lines[:5]:
                log(f"  {e_line}")
            return False

    # Verify key packages
    log("Verifying key packages...")
    for pkg in ["fastapi", "uvicorn", "sqlalchemy", "openai"]:
        ec, o, _ = run(client, f"python3 -c 'import {pkg}; print({pkg}.__version__)' 2>&1 || echo NOT_FOUND")
        log(f"  {pkg}: {o[:50]}")

    return True


def build_frontend(client):
    """Install npm deps and build frontend."""
    log("Installing frontend dependencies...")
    exit_code, out, err = run(client,
        f"cd {DEPLOY_DIR}/frontend && npm install 2>&1 | tail -10", timeout=180)
    if exit_code != 0:
        log(f"npm install failed: {err[:200]}")
        return False

    log("Building frontend...")
    exit_code, out, err = run(client,
        f"cd {DEPLOY_DIR}/frontend && npm run build 2>&1", timeout=180)
    if exit_code != 0:
        log(f"Frontend build failed: {err[:300]}")
        return False
    log(f"Build output: {out[:200]}")
    return True


def deploy_frontend_env(client):
    """Copy .env.production to .env for build vars."""
    log("Setting up frontend environment...")
    # The .env.production already has VITE_API_URL=/api
    exit_code, out, err = run(client,
        f"cat {DEPLOY_DIR}/frontend/.env.production")
    log(f"Frontend env: {out[:100]}")


def set_up_venv(client):
    """Set up a Python virtual environment for isolation."""
    log("Setting up Python virtual environment...")
    exit_code, out, err = run(client,
        f"cd {DEPLOY_DIR} && python3 -m venv venv 2>&1", timeout=30)
    if exit_code != 0:
        log(f"venv creation failed: {err[:200]}")
        return False

    log("Installing deps in venv...")
    exit_code, out, err = run(client,
        f"cd {DEPLOY_DIR} && ./venv/bin/pip install -r backend/requirements.txt 2>&1", timeout=300)
    log(f"Venv deps: {out[:200]}")

    # Verify key packages in venv
    for pkg in ["fastapi", "uvicorn", "sqlalchemy", "openai"]:
        ec, o, _ = run(client,
            f"cd {DEPLOY_DIR} && ./venv/bin/python -c 'import {pkg}; print({pkg}.__version__)' 2>&1 || echo NOT_FOUND")
        log(f"  {pkg}: {o[:50]}")

    return exit_code == 0


def start_app(client):
    """Start the application."""
    log("Initializing database and starting app...")

    # First test if uvicorn works
    exit_code, out, err = run(client,
        f"cd {DEPLOY_DIR}/backend && python3 -c 'from main import app; print(\"FastAPI app loaded OK\")' 2>&1",
        timeout=15)
    log(f"App import: {out}")

    # Initialize DB
    log("Initializing database...")
    exit_code, out, err = run(client,
        f"cd {DEPLOY_DIR}/backend && python3 init_db.py 2>&1", timeout=15)
    log(f"DB init: {out}")

    # Check SQLite DB exists
    exit_code, out, err = run(client,
        f"ls -la {DEPLOY_DIR}/backend/ai_police.db 2>&1")
    log(f"DB file: {out}")

    # Kill any existing process on APP_PORT
    run(client, f"pkill -f 'uvicorn.*{APP_PORT}' 2>/dev/null || true")

    # Start uvicorn in background with nohup
    log(f"Starting uvicorn on port {APP_PORT}...")
    run(client,
        f"cd {DEPLOY_DIR}/backend && nohup python3 -m uvicorn main:app "
        f"--host 0.0.0.0 --port {APP_PORT} "
        f"--log-level info > {DEPLOY_DIR}/app.log 2>&1 &",
        timeout=10)
    log("App starting in background...")

    # Wait for it to start
    log("Waiting for app to become ready...")
    for i in range(30):
        ec, o, _ = run(client,
            f"curl -fsSo /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/healthz 2>/dev/null || echo 000",
            timeout=5)
        if o == "200":
            log(f"App is ready! (http://127.0.0.1:{APP_PORT}/healthz)")
            return True
        if i == 5:
            # After 10s, check if process is running
            ec, o, _ = run(client, f"ps aux | grep uvicorn | grep -v grep | head -3")
            log(f"Uvicorn process: {o[:200]}")
        time.sleep(2)

    log("App did not become ready. Checking logs...")
    exit_code, out, err = run(client, f"tail -30 {DEPLOY_DIR}/app.log")
    log(f"Logs:\n{out}")
    return False


def verify_deployment(client):
    log("=" * 60)
    log("VERIFYING DEPLOYMENT")
    log("=" * 60)

    checks = [
        ("Uvicorn Process", f"ps aux | grep 'uvicorn' | grep -v grep"),
        ("Health Check", f"curl -s http://127.0.0.1:{APP_PORT}/healthz"),
        ("API Health", f"curl -s http://127.0.0.1:{APP_PORT}/api/healthz"),
        ("API Docs", f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/docs 2>/dev/null"),
        ("DB File", f"ls -la {DEPLOY_DIR}/backend/ai_police.db"),
    ]

    for name, cmd in checks:
        ec, o, e = run(client, cmd)
        log(f"{name}: {o[:200]}")
        if e:
            log(f"  ERR: {e[:200]}")

    log("")
    log("=" * 60)
    log("DEPLOYMENT COMPLETE")
    log("=" * 60)
    log("")
    log(f"  System URL:    http://{SERVER}:{APP_PORT}")
    log(f"  Health check:  http://{SERVER}:{APP_PORT}/healthz")
    log(f"  API Docs:      http://{SERVER}:{APP_PORT}/docs")
    log("")
    log("Default accounts:")
    log("  Admin:   admin / 123456")
    log("  Student: student001 / 123456")
    log("")
    log(f"View logs: tail -f {DEPLOY_DIR}/app.log")
    log(f"Restart:   cd {DEPLOY_DIR}/backend && nohup python3 -m uvicorn main:app --host 0.0.0.0 --port {APP_PORT} > {DEPLOY_DIR}/app.log 2>&1 &")


def main():
    log("=" * 60)
    log("AI POLICE - NATIVE DEPLOYMENT")
    log("=" * 60)

    client = create_client()
    try:
        # Step 1: Install pip
        log("\n--- Step 1: Install pip ---")
        if not install_pip(client):
            log("ERROR: Could not install pip")
            return

        # Step 2: Install Python dependencies using venv
        log("\n--- Step 2: Install Python deps ---")
        set_up_venv(client)

        # Step 3: Build frontend
        log("\n--- Step 3: Build frontend ---")
        deploy_frontend_env(client)
        if not build_frontend(client):
            log("ERROR: Frontend build failed")

        # Step 4: Set up ChromaDB dir
        run(client, f"mkdir -p {DEPLOY_DIR}/data/chroma_db")

        # Step 5: Start app
        log("\n--- Step 4: Start application ---")
        start_app(client)

        # Step 6: Verify
        log("\n--- Step 5: Verification ---")
        verify_deployment(client)

    except Exception as e:
        log(f"ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
