"""Restart uvicorn on server."""
import time, socket, paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('82.156.126.212', port=22, username='panglihao', password='Panglihao@123',
               look_for_keys=False, allow_agent=False, timeout=30)

DEPLOY_DIR = "/home/panglihao/ai-police-sim"
PY = f"{DEPLOY_DIR}/venv/bin/python3"
APP_PORT = 5175

def run(cmd, timeout=10):
    transport = client.get_transport()
    chan = transport.open_session(timeout=timeout)
    chan.exec_command(cmd)
    # For background commands, just exit after sending
    chan.shutdown_write()
    code = chan.recv_exit_status(timeout=timeout)
    return code

# Kill old
print("Killing old uvicorn...")
try:
    run(f"pkill -f 'uvicorn.*{APP_PORT}' 2>/dev/null || true")
except: pass
time.sleep(1)

# Start app with nohup - using raw channel to avoid pty issues
print("Starting uvicorn...")
transport = client.get_transport()
chan = transport.open_session()
cmd = (
    f"cd {DEPLOY_DIR}/backend && "
    f"nohup {PY} -m uvicorn main:app "
    f"--host 0.0.0.0 --port {APP_PORT} "
    f"--log-level info > {DEPLOY_DIR}/app.log 2>&1 &"
)
chan.exec_command(cmd)
chan.shutdown_write()
time.sleep(5)

# Check process
def check(cmd):
    i,o,e = client.exec_command(cmd, timeout=10)
    ec = o.channel.recv_exit_status()
    return o.read().decode('utf-8','replace').strip()

p = check("ps aux | grep 'uvicorn.*5175' | grep -v grep")
print(f"Process: {p[:100] or 'NOT RUNNING'}")

h = check("curl -s http://127.0.0.1:5175/healthz")
print(f"Health: {h or 'FAILED'}")

s = check("curl -so /dev/null -w '%{http_code}' http://127.0.0.1:5175/")
print(f"Frontend: {s}")

if not h:
    print("Logs:")
    print(check(f"tail -20 {DEPLOY_DIR}/app.log"))

client.close()
