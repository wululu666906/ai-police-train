#!/usr/bin/env python3
"""
Deploy AI Police Training Simulation Platform to remote server.
Phase 2: Fix Docker Compose and build containers.
"""
import os
import sys
import time

import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"


def log(msg: str):
    # Avoid emoji for Windows terminal compatibility
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def create_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    log(f"Connecting {SERVER} as {USER}...")
    client.connect(SERVER, port=22, username=USER, password=PASSWORD,
                   look_for_keys=False, allow_agent=False, timeout=30)
    log("Connected.")
    return client


def exec_cmd(client, command, sudo=False, timeout=300):
    if sudo:
        command = f"echo '{PASSWORD}' | sudo -S bash -c '{command}'"
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    return exit_code, out, err


def fix_docker_compose(client):
    """Install docker compose v2 plugin."""
    log("Checking docker compose availability...")

    # Check both v1 and v2
    code, out, _ = exec_cmd(client, "docker compose version 2>/dev/null")
    if code == 0 and out:
        log(f"docker compose v2 available: {out}")
        return

    code, out, _ = exec_cmd(client, "docker-compose --version 2>/dev/null")
    if code == 0 and out:
        log(f"docker-compose v1 available: {out}")
        # We'll use 'docker-compose' instead
        return "v1"

    log("Installing docker compose v2 plugin...")
    cmds = [
        # Method 1: apt install docker-compose-v2
        "apt-get update -qq && apt-get install -y -qq docker-compose-v2 2>&1 | tail -5",
        # Method 2: download plugin binary
        "mkdir -p /usr/local/lib/docker/cli-plugins && "
        "curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 "
        "-o /usr/local/lib/docker/cli-plugins/docker-compose && "
        "chmod +x /usr/local/lib/docker/cli-plugins/docker-compose",
    ]

    for i, cmd in enumerate(cmds, 1):
        log(f"Trying install method {i}...")
        code, out, err = exec_cmd(client, cmd, sudo=True, timeout=120)
        if code == 0:
            log(f"Method {i} succeeded.")
            # Verify
            code, out, _ = exec_cmd(client, "docker compose version 2>/dev/null")
            if code == 0:
                log(f"docker compose plugin ready: {out[:100]}")
                return
        log(f"Method {i} result: {err[:150]}")

    # Fall back to docker-compose v1
    log("Trying docker-compose v1...")
    code, out, _ = exec_cmd(client, "apt-get install -y -qq docker-compose 2>&1 | tail -3", sudo=True, timeout=120)
    if code == 0:
        return "v1"

    return None


def build_container(client, compose_cmd):
    log(f"Using compose command: {compose_cmd}")

    # First make sure old containers are gone
    exec_cmd(client, f"cd {DEPLOY_DIR} && {compose_cmd} down 2>/dev/null || true")

    # Normalize scripts
    for script in ["start.sh", "backend/docker-entrypoint.sh"]:
        exec_cmd(client, f"cd {DEPLOY_DIR} && sed -i 's/\\r$//' {script} && chmod +x {script}")

    # Build and start the app service
    log("Building Docker image (this may take 5-10 minutes)...")
    code, out, err = exec_cmd(client,
        f"cd {DEPLOY_DIR} && {compose_cmd} up -d --build app 2>&1", timeout=600)

    log(f"Build exit code: {code}")
    if out:
        log(f"Output: {out[:500]}")
    if err:
        log(f"Errors: {err[:500]}")

    if code != 0:
        log("Build failed, checking logs...")
        exec_cmd(client, f"cd {DEPLOY_DIR} && {compose_cmd} logs --tail 50 app 2>&1")
        return False

    # Health check
    log("Waiting for health check...")
    for i in range(30):
        c, o, _ = exec_cmd(client,
            "curl -fsSo /dev/null -w '%{http_code}' http://127.0.0.1:5175/healthz 2>/dev/null || "
            "curl -fsSo /dev/null -w '%{http_code}' http://127.0.0.1:8000/healthz 2>/dev/null || echo 000")
        if o == "200":
            log(f"Health check OK! ({i*2}s)")
            return True
        time.sleep(2)

    log("Health check timed out. Checking logs...")
    exec_cmd(client, f"cd {DEPLOY_DIR} && {compose_cmd} logs --tail 50 app 2>&1")
    return False


def show_status(client, compose_cmd):
    log("=" * 60)
    log("DEPLOYMENT STATUS")
    log("=" * 60)

    for label, cmd in [
        ("Container Status", f"cd {DEPLOY_DIR} && {compose_cmd} ps"),
        ("Health Check", "curl -s http://127.0.0.1:5175/healthz"),
        ("API Health", "curl -s http://127.0.0.1:5175/api/healthz"),
    ]:
        c, o, e = exec_cmd(client, cmd)
        log(f"{label}: {o[:200]}")
        if e:
            log(f"  stderr: {e[:200]}")


def main():
    client = create_client()
    try:
        compose_result = fix_docker_compose(client)
        compose_cmd = "docker-compose" if compose_result == "v1" else "docker compose"
        log(f"Using: {compose_cmd}")

        if not compose_result and compose_cmd == "docker compose":
            log("ERROR: Docker Compose is not available")
            return

        build_container(client, compose_cmd)
        show_status(client, compose_cmd)

        log("")
        log("=" * 60)
        log("DEPLOYMENT COMPLETE")
        log("=" * 60)
        log(f"System URL:    http://{SERVER}:5175")
        log(f"Health:        http://{SERVER}:5175/healthz")
        log(f"API Docs:      http://{SERVER}:5175/docs")
        log(f"Admin login:   admin / 123456")
        log(f"Student login: student001 / 123456")
        log("")
        log(f"View logs: cd {DEPLOY_DIR} && {compose_cmd} logs -f app")

    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()
