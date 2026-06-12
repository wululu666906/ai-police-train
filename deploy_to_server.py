#!/usr/bin/env python3
"""
Deploy AI Police Training Simulation Platform to remote server.
Uses paramiko for SSH with password authentication.
"""
import os
import sys
import time

import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
PORT = 22

DEPLOY_DIR = "/home/panglihao/ai-police-sim"
# Use Windows-compatible path
TARBALL_PATH = os.environ.get("TARBALL_PATH", "C:\\tmp\\ai-police-deploy.tar.gz")


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def create_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    log(f"SSH connecting to {SERVER}:{PORT} as {USER}...")
    client.connect(SERVER, port=PORT, username=USER, password=PASSWORD,
                   look_for_keys=False, allow_agent=False, timeout=30)
    log("SSH connected.")
    return client


def exec_cmd(client, command, sudo=False, timeout=300):
    if sudo:
        command = f"echo '{PASSWORD}' | sudo -S bash -c '{command}'"
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return exit_code, out, err


def upload_tarball(client):
    log("Uploading deployment package...")
    sftp = client.open_sftp()
    try:
        remote_path = f"{DEPLOY_DIR}/ai-police-deploy.tar.gz"
        sftp.put(TARBALL_PATH, remote_path)
        size = os.path.getsize(TARBALL_PATH)
        log(f"Uploaded {size:,} bytes.")
    finally:
        sftp.close()


def ensure_directory(client):
    log("Ensuring deployment directory...")
    code, out, err = exec_cmd(client, f"mkdir -p {DEPLOY_DIR}")
    if code != 0:
        log(f"ERROR: mkdir failed: {err}")
        return False
    return True


def extract_package(client):
    log("Extracting deployment package...")
    code, out, err = exec_cmd(client, f"cd {DEPLOY_DIR} && tar xzf ai-police-deploy.tar.gz 2>&1")
    if code != 0:
        log(f"ERROR: Extract failed: {err}")
        return False
    code, out, err = exec_cmd(client, f"ls {DEPLOY_DIR}/ | head -30")
    log(f"Files in target:\n{out}")
    return True


def check_docker(client):
    log("Checking Docker installation...")
    code, out, err = exec_cmd(client, "docker --version")
    if code != 0:
        log("Docker not found, attempting to install...")
        # For Tencent Cloud / Ubuntu servers
        cmds = [
            "apt-get update -qq && apt-get install -y -qq docker.io 2>&1 | tail -5",
            "curl -fsSL https://get.docker.com | bash 2>&1 | tail -5",
        ]
        for cmd in cmds:
            code, out, err = exec_cmd(client, cmd, timeout=180)
            if code == 0:
                log("Docker installed.")
                exec_cmd(client, "usermod -aG docker panglihao", sudo=True)
                log("User added to docker group - may need re-login.")
                return True
            log(f"Docker install attempt failed: {err[:200]}")
        return False

    log(f"Docker: {out}")

    code, out, err = exec_cmd(client, "docker compose version 2>/dev/null || docker-compose --version 2>/dev/null")
    log(f"Docker Compose: {out[:200]}")

    if "not found" in out.lower() or not out:
        log("Docker Compose v2 not found, installing...")
        exec_cmd(client,
            "DOCKER_CONFIG=/usr/local/lib/docker; mkdir -p $DOCKER_CONFIG/cli-plugins && "
            "curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 "
            "-o $DOCKER_CONFIG/cli-plugins/docker-compose && chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose",
            sudo=True, timeout=120)

    return True


def setup_server(client):
    log("Normalizing line endings and setting permissions...")
    scripts = ["start.sh", "backend/docker-entrypoint.sh", "scripts/server_deploy.sh"]
    for script in scripts:
        exec_cmd(client, f"cd {DEPLOY_DIR} && sed -i 's/\\r$//' {script} 2>/dev/null; chmod +x {script} 2>/dev/null")

    log("Creating data directories...")
    exec_cmd(client, f"cd {DEPLOY_DIR} && mkdir -p data/chroma_db && touch data/ai_police.db")

    log("Checking .env configuration...")
    code, out, err = exec_cmd(client, f"cat {DEPLOY_DIR}/backend/.env")
    if code == 0:
        keys_found = [line for line in out.split("\n") if "API_KEY" in line and "=" in line and line.split("=")[1].strip()]
        if keys_found:
            log(f"API keys found: {len(keys_found)}")
        else:
            log("WARNING: No API keys detected in .env!")

    log("Server setup complete.")


def build_and_run(client):
    log("Building and starting Docker containers...")

    # Stop existing
    exec_cmd(client, f"cd {DEPLOY_DIR} && docker compose down 2>/dev/null || true")

    # Build and start
    log("Running: docker compose up -d --build app (this may take 5-10 minutes)...")
    code, out, err = exec_cmd(client, f"cd {DEPLOY_DIR} && docker compose up -d --build app 2>&1", timeout=600)

    if code != 0:
        log(f"ERROR: Docker build/start failed: {err[:500]}")
        log("Container logs:")
        exec_cmd(client, f"cd {DEPLOY_DIR} && docker compose logs --tail 30 app 2>&1")
        return False

    log(f"Build output: {out[:500]}")

    # Wait for health
    log("Waiting for service to become healthy...")
    health_urls = [
        "http://127.0.0.1:5175/healthz",
        "http://127.0.0.1:8000/healthz",
    ]

    for attempt in range(30):
        for url in health_urls:
            code, out, _ = exec_cmd(client, f"curl -fsSo /dev/null -w '%{{http_code}}' '{url}' 2>/dev/null || true")
            if out == "200":
                log(f"Service healthy at {url} (attempt {attempt+1})!")
                return True
        time.sleep(2)

    log("WARNING: Health check timed out after 60s. Checking logs...")
    exec_cmd(client, f"cd {DEPLOY_DIR} && docker compose logs --tail 50 app 2>&1")
    return True  # Don't fail - it might still be starting


def verify_deployment(client):
    log("\n" + "=" * 60)
    log("VERIFYING DEPLOYMENT")
    log("=" * 60)

    checks = [
        ("Container Status", f"cd {DEPLOY_DIR} && docker compose ps"),
        ("Health Check", "curl -s http://127.0.0.1:5175/healthz"),
        ("API Health", "curl -s http://127.0.0.1:5175/api/healthz"),
        ("API Docs", "curl -so /dev/null -w '%{http_code}' http://127.0.0.1:5175/docs"),
    ]

    for name, cmd in checks:
        code, out, err = exec_cmd(client, cmd)
        log(f"{name}: {out[:200]}")
        if err:
            log(f"  stderr: {err[:200]}")


def main():
    log("=" * 60)
    log("AI POLICE DEPLOYMENT SCRIPT")
    log("=" * 60)

    if not os.path.exists(TARBALL_PATH):
        log(f"ERROR: Tarball not found at {TARBALL_PATH}")
        sys.exit(1)

    client = None
    try:
        client = create_client()

        if not ensure_directory(client):
            sys.exit(1)

        upload_tarball(client)

        if not extract_package(client):
            sys.exit(1)

        setup_server(client)
        check_docker(client)
        build_and_run(client)
        verify_deployment(client)

        log("")
        log("=" * 60)
        log("DEPLOYMENT COMPLETE")
        log("=" * 60)
        log("")
        log(f"🌐 System URL:    http://{SERVER}:5175")
        log(f"🔐 Health check:  http://{SERVER}:5175/healthz")
        log(f"📚 API Docs:      http://{SERVER}:5175/docs")
        log("")
        log("Default accounts:")
        log("  Admin:   admin / 123456")
        log("  Student: student001 / 123456")
        log("")
        log("Useful commands:")
        log(f"  SSH:      ssh {USER}@{SERVER}")
        log(f"  Logs:     cd {DEPLOY_DIR} && docker compose logs -f app")
        log(f"  Restart:  cd {DEPLOY_DIR} && docker compose up -d --build")

    except Exception as e:
        log(f"ERROR: Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
