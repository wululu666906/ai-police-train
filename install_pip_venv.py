"""Try alternative methods to install pip into venv."""
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
    for l in (out + err).strip().split("\n")[:12]:
        if l.strip():
            print(f"  {l}")
    return exit_code, out.strip(), err.strip()


VENV_PYTHON = f"{DEPLOY_DIR}/venv/bin/python3"

# Test: Can venv python reach PyPI?
print("\n--- Test: PyPI access ---")
run(f"{VENV_PYTHON} -c 'import urllib.request; r=urllib.request.urlopen(\"https://pypi.org\",timeout=10); print(r.status)' 2>&1")

# Option 1: Try get-pip.py with Tsinghua mirror
print("\n--- Option 1: get-pip with mirror ---")
run(f"{VENV_PYTHON} /tmp/get-pip.py --index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>&1", timeout=60)

# Check if pip installed now
ec, o, e = run(f"{VENV_PYTHON} -m pip --version 2>&1")
if ec == 0 and "pip" in o:
    print("pip IS INSTALLED NOW!")
    client.close()
    exit(0)

# Option 2: Download pip wheel and install manually
print("\n--- Option 2: Manual pip wheel ---")
run("curl -sL -o /tmp/pip-py3-none-any.whl https://pypi.tuna.tsinghua.edu.cn/packages/pip/pip-25.0.1-py3-none-any.whl 2>&1 | head -5", timeout=30)
run(f"ls -la /tmp/pip-py3-none-any.whl 2>&1")

# Option 3: Use pip's source
print("\n--- Option 3: Try downloading latest pip ---")
run("curl -sL https://pypi.tuna.tsinghua.edu.cn/simple/pip/ | grep -o 'pip-[0-9.]*-py3-none-any.whl' | head -5", timeout=30)

client.close()
