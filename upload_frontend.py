"""Upload frontend dist to server and extract."""
import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"
TARBALL_PATH = "C:\\tmp\\frontend-dist.tar.gz"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"[exit={ec}] {cmd[:120]}")
    for l in (out + "\n" + err).strip().split("\n")[:10]:
        if l.strip():
            print(f"  {l}")
    return ec, out.strip(), err.strip()


# Upload dist
print("Uploading frontend dist...")
sftp = client.open_sftp()
try:
    sftp.put(TARBALL_PATH, f"{DEPLOY_DIR}/frontend-dist.tar.gz")
    print("Upload complete.")
finally:
    sftp.close()

# Extract into frontend/
print("Extracting...")
run(f"cd {DEPLOY_DIR}/frontend && rm -rf dist && tar xzf {DEPLOY_DIR}/frontend-dist.tar.gz")

# Verify
print("Verifying...")
run(f"ls -la {DEPLOY_DIR}/frontend/dist/")

# Restart app
print("Restarting app to pick up frontend...")
PY = f"{DEPLOY_DIR}/venv/bin/python3"
APP_PORT = 5175
run(f"pkill -f 'uvicorn.*{APP_PORT}' 2>/dev/null; sleep 1")
run(f"cd {DEPLOY_DIR}/backend && nohup {PY} -m uvicorn main:app --host 0.0.0.0 --port {APP_PORT} --log-level info >{DEPLOY_DIR}/app.log 2>&1 & sleep 3 && echo 'APP RESTARTED'")

# Test
print("Testing health...")
run(f"curl -s http://127.0.0.1:{APP_PORT}/healthz")
run(f"curl -so /dev/null -w 'HTTP %{{http_code}}' http://127.0.0.1:{APP_PORT}/ 2>/dev/null")
run(f"curl -so /dev/null -w 'Docs HTTP %{{http_code}}' http://127.0.0.1:{APP_PORT}/docs 2>/dev/null")

# Token test
print("Testing login...")
run(f"curl -s -X POST http://127.0.0.1:{APP_PORT}/auth/token -d 'username=admin&password=123456' 2>/dev/null | head -c 200")

client.close()
