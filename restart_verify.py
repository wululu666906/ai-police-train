"""Restart app and verify avatars work."""
import paramiko, time

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"
APP_PORT = 5175
PY = f"{DEPLOY_DIR}/venv/bin/python3"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)

def result(cmd, timeout=15):
    i,o,e = client.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = o.channel.recv_exit_status()
    return ec, o.read().decode("utf-8","replace").strip(), e.read().decode("utf-8","replace").strip()

# Kill old
print("Killing old process...")
result("pkill -f 'uvicorn.*5175' 2>/dev/null || true")
time.sleep(1)

# Start via raw transport channel
print("Starting uvicorn...")
transport = client.get_transport()
chan = transport.open_session()
chan.exec_command(
    f"cd {DEPLOY_DIR}/backend && nohup {PY} -m uvicorn main:app "
    f"--host 0.0.0.0 --port {APP_PORT} --log-level info >{DEPLOY_DIR}/app.log 2>&1 & echo DONE"
)
time.sleep(4)

# Check
ec, o, e = result("ps aux | grep 'uvicorn.*5175' | grep -v grep | head -1")
print(f"Process: {o[:80] or 'NOT FOUND'}")

ec, o, e = result("curl -s http://127.0.0.1:5175/healthz")
print(f"Health: {o}")

ec, o, e = result("curl -s http://127.0.0.1:5175/api/healthz")
print(f"API: {o}")

ec, o, e = result("curl -so /dev/null -w '%{http_code}' http://127.0.0.1:5175/ 2>/dev/null")
print(f"Frontend: HTTP {o}")

# Avatar files
for i in [1, 10, 20]:
    ec, o, e = result(f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:5175/avatars/avatar_{i:02d}.svg 2>/dev/null")
    print(f"Avatar {i:02d}: HTTP {o}")

print("\n=== STATUS ===")
print(f"http://{SERVER}:{APP_PORT}")

client.close()
