"""Deploy avatar update to server: backend changes, SVGs, frontend dist, seed & restart."""
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


def run(cmd, timeout=30):
    i,o,e = client.exec_command(cmd, timeout=timeout)
    ec = o.channel.recv_exit_status()
    return ec

def result(cmd, timeout=15):
    i,o,e = client.exec_command(cmd, timeout=timeout)
    ec = o.channel.recv_exit_status()
    return ec, o.read().decode("utf-8","replace").strip(), e.read().decode("utf-8","replace").strip()


sftp = client.open_sftp()

# Step 1: Upload backend changes + avatar SVGs
print("[1/5] Uploading backend changes + avatar SVGs...")
sftp.put("C:\\tmp\\ai-police-avatar-update.tar.gz", f"{DEPLOY_DIR}/avatar-update.tar.gz")

print("Extracting backend changes...")
run(f"cd {DEPLOY_DIR} && tar xzf avatar-update.tar.gz")
print("Done.")

# Step 2: Upload frontend dist
print("[2/5] Uploading frontend dist...")
sftp.put("C:\\tmp\\frontend-avatar-dist.tar.gz", f"{DEPLOY_DIR}/frontend-avatar-dist.tar.gz")

print("Extracting frontend dist...")
run(f"cd {DEPLOY_DIR}/frontend && rm -rf dist && tar xzf {DEPLOY_DIR}/frontend-avatar-dist.tar.gz")

sftp.close()

# Step 3: Seed avatar images
print("[3/5] Seeding avatar images into database...")
ec, o, e = result(f"cd {DEPLOY_DIR}/backend && {PY} seed_avatars.py 2>&1")
print(f"Seed: {o[:200]}")

# Step 4: Verify avatars were seeded
print("[4/5] Verifying avatar metadata...")
ec, o, e = result(f"cd {DEPLOY_DIR}/backend && {PY} -c 'from database import SessionLocal; from models import AvatarImage; db=SessionLocal(); print(\"Avatar count:\", db.query(AvatarImage).count()); db.close()' 2>&1")
print(f"Verify: {o[:200]}")

# Step 5: Restart app
print("[5/5] Restarting app...")
run(
    f"pkill -f 'uvicorn.*{APP_PORT}' 2>/dev/null; sleep 1; "
    f"cd {DEPLOY_DIR}/backend && nohup {PY} -m uvicorn main:app "
    f"--host 0.0.0.0 --port {APP_PORT} --log-level info >{DEPLOY_DIR}/app.log 2>&1 &"
)

# Health check
ec, o, e = result("curl -s http://127.0.0.1:5175/healthz")
print(f"Health: {o}")

ec, o, e = result("curl -s http://127.0.0.1:5175/api/healthz")
print(f"API health: {o}")

ec, o, e = result("curl -so /dev/null -w '%{http_code}' http://127.0.0.1:5175/")
print(f"Frontend: HTTP {o}")

# Verify avatars are accessible
ec, o, e = result("curl -so /dev/null -w '%{http_code}' http://127.0.0.1:5175/avatars/avatar_01.svg 2>/dev/null")
print(f"Avatar file (01): HTTP {o}")

ec, o, e = result("curl -so /dev/null -w '%{http_code}' http://127.0.0.1:5175/avatars/avatar_20.svg 2>/dev/null")
print(f"Avatar file (20): HTTP {o}")

print("\n=== DEPLOYMENT COMPLETE ===")
print(f"System: http://{SERVER}:{APP_PORT}")

client.close()
