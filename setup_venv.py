"""Set up venv without ensurepip, then pip is installable inside."""
import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"[exit={exit_code}] $ {cmd[:120]}")
    for l in (out + err).strip().split("\n")[:15]:
        print(f"  {l}")
    return exit_code, out.strip(), err.strip()


# Step 1: Remove failed test venv
run(f"rm -rf {DEPLOY_DIR}/test_venv")

# Step 2: Create venv without pip
print("\n--- Creating venv without pip ---")
ec, o, e = run(f"cd {DEPLOY_DIR} && python3 -m venv --without-pip venv 2>&1")
if ec != 0:
    print("FAILED to create venv even without pip")
    client.close()
    exit(1)
print("venv created OK")

# Step 3: Download get-pip.py and install pip into the venv
print("\n--- Installing pip into venv ---")
run("curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py")
ec, o, e = run(f"{DEPLOY_DIR}/venv/bin/python /tmp/get-pip.py 2>&1")
print(f"get-pip result: {o[:200]}")
if ec != 0:
    print(f"FAILED: {e[:200]}")

# Step 4: Verify pip in venv
print("\n--- Verifying pip ---")
ec, o, e = run(f"{DEPLOY_DIR}/venv/bin/pip --version 2>&1")
print(f"pip: {o[:150]}")

# Step 5: Install deps
print("\n--- Installing Python deps (this may take a while) ---")
ec, o, e = run(f"{DEPLOY_DIR}/venv/bin/pip install -r {DEPLOY_DIR}/backend/requirements.txt 2>&1", timeout=300)
print(f"pip install: {o[:300]}")

# Step 6: Verify key packages
print("\n--- Verifying packages ---")
for pkg in ["fastapi", "uvicorn", "sqlalchemy", "openai", "passlib", "python-multipart"]:
    ec, o, e = run(f"{DEPLOY_DIR}/venv/bin/python -c 'import {pkg}; print({pkg}.__version__)' 2>&1 || echo FAILED")
    print(f"  {pkg}: {o[:60]}")

client.close()
