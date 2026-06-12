"""Upload frontend dist and restart server app."""
import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
TARBALL = "C:\\tmp\\frontend-dist.tar.gz"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"
APP_PORT = 5175
PY = f"{DEPLOY_DIR}/venv/bin/python3"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    return ec, stdout.read().decode("utf-8", errors="replace")


print("Uploading frontend dist...")
sftp = client.open_sftp()
sftp.put(TARBALL, f"{DEPLOY_DIR}/frontend-dist.tar.gz")
sftp.close()
print("Uploaded.")

print("Extracting...")
ec, o = run(f"cd {DEPLOY_DIR}/frontend && rm -rf dist && tar xzf {DEPLOY_DIR}/frontend-dist.tar.gz && echo OK")
print(f"Extract: {o[:100]}")

print("Restarting app...")
ec, o = run(
    f"pkill -f 'uvicorn.*{APP_PORT}' 2>/dev/null; sleep 1; "
    f"cd {DEPLOY_DIR}/backend && nohup {PY} -m uvicorn main:app "
    f"--host 0.0.0.0 --port {APP_PORT} --log-level info >{DEPLOY_DIR}/app.log 2>&1 & sleep 4 && "
    f"curl -s http://127.0.0.1:{APP_PORT}/healthz")
print(f"Restart: {o[:100]}")

ec, o = run(f"curl -s http://127.0.0.1:{APP_PORT}/")
print(f"Frontend HTTP status: {o[:200]}")

client.close()
print("Done!")
