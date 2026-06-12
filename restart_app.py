"""Restart the application properly."""
import time, paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('82.156.126.212', port=22, username='panglihao', password='Panglihao@123',
               look_for_keys=False, allow_agent=False, timeout=30)

DEPLOY_DIR = "/home/panglihao/ai-police-sim"
PY = f"{DEPLOY_DIR}/venv/bin/python3"
APP_PORT = 5175

def run(cmd, timeout=15, pty=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=pty)
    ec = stdout.channel.recv_exit_status()
    return ec, stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")

# Kill old process
print("Killing old uvicorn...")
run(f"pkill -f 'uvicorn.*{APP_PORT}' 2>/dev/null || true", pty=False)
time.sleep(1)

# Start in background - use a nohup with double-fork approach
print("Starting uvicorn...")
cmd = (
    f"cd {DEPLOY_DIR}/backend && "
    f"nohup {PY} -m uvicorn main:app "
    f"--host 0.0.0.0 --port {APP_PORT} "
    f"--log-level info > {DEPLOY_DIR}/app.log 2>&1 &"
)
run(cmd, pty=False)
time.sleep(4)

# Check process
ec, o, e = run("ps aux | grep 'uvicorn' | grep -v grep", pty=False)
print(f"Process: '{o.strip()}'")

# Check health
ec, o, e = run("curl -s http://127.0.0.1:5175/healthz", pty=False)
print(f"Health: {o.strip()}")

if not o.strip():
    print("Checking logs...")
    ec, o, e = run(f"tail -20 {DEPLOY_DIR}/app.log", pty=False)
    print(f"Logs:\n{o}")

    # Try again with more explicit startup
    print("\nRetrying startup...")
    run(f"cd {DEPLOY_DIR}/backend && {PY} -m uvicorn main:app --host 0.0.0.0 --port {APP_PORT} --log-level info > {DEPLOY_DIR}/app2.log 2>&1 &", pty=False)
    time.sleep(5)
    ec, o, e = run("curl -s http://127.0.0.1:5175/healthz", pty=False)
    print(f"Health: {o.strip()}")
    ec, o, e = run(f"tail -20 {DEPLOY_DIR}/app2.log", pty=False)
    print(f"Logs2:\n{o}")

client.close()
