"""Check if venv module is available and try to set up Python environment."""
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
    print(f"[exit={exit_code}] $ {cmd[:100]}")
    lines = (out + "\n" + err).strip().split("\n")
    for l in lines[:15]:
        print(f"  {l}")
    return exit_code, out.strip(), err.strip()


# Check venv availability
run("python3 -m venv --help 2>&1 | head -3")

# Check if we can create a venv
run(f"cd {DEPLOY_DIR} && python3 -m venv test_venv 2>&1 && echo 'VENV OK' || echo 'VENV FAILED'", timeout=15)

# Check available python packages for user
run("apt list --installed 2>/dev/null | grep python3 | head -20 || true")

# Check if conda is available
run("conda --version 2>&1 || which conda 2>/dev/null || echo 'no conda'")

# Check pipx
run("pipx --version 2>&1 || which pipx 2>/dev/null || echo 'no pipx'")

# Check if we can download a portable python
run("which curl && curl --version | head -1")

client.close()
