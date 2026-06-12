"""Debug: check app status, fix frontend build, fix app startup."""
import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"[exit={ec}] $ {cmd[:100]}")
    for l in (out + "\n" + err).strip().split("\n")[:20]:
        if l.strip():
            print(f"  {l}")
    return ec, out.strip(), err.strip()


# === Debug 1: Check if uvicorn process is running ===
print("=== Checking processes ===")
run("ps aux | grep uvicorn | grep -v grep")

# === Debug 2: Check if there's any log file ===
print("\n=== Checking log files ===")
run(f"ls -la {DEPLOY_DIR}/*.log 2>&1 || true")
run(f"cat {DEPLOY_DIR}/nohup.out 2>&1 || true")

# === Debug 3: Try starting app directly with stderr captured ===
print("\n=== Try starting app directly ===")
PY = f"{DEPLOY_DIR}/venv/bin/python3"
APP_PORT = 5175

# Kill old processes
run(f"pkill -f 'uvicorn.*{APP_PORT}' 2>/dev/null || true")

# Start with explicit log path
ec, o, e = run(
    f"cd {DEPLOY_DIR}/backend && nohup {PY} -m uvicorn main:app --host 0.0.0.0 --port {APP_PORT} --log-level info >{DEPLOY_DIR}/app.log 2>&1 & sleep 3 && echo 'STARTED' && curl -s http://127.0.0.1:{APP_PORT}/healthz 2>&1 || echo 'FAILED'",
    timeout=30)
print(f"Start and health: {o[:300]}")

# Check logs
print("\n=== App log ===")
run(f"cat {DEPLOY_DIR}/app.log 2>&1 | head -30")

# Check main.py imports
print("\n=== Test app import ===")
run(f"cd {DEPLOY_DIR}/backend && {PY} -c \"from main import app; print('OK')\" 2>&1")

client.close()
