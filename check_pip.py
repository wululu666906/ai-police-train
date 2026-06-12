"""Native deployment - check pip availability and set up environment."""
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
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(f"$ {cmd}")
    if out:
        for line in out.split("\n")[:10]:
            print(f"  {line}")
    if err:
        for line in err.split("\n")[:5]:
            print(f"  ERR: {line}")
    return exit_code, out, err


# Check pip
run("python3 -m pip --version 2>&1")

# Check ensurepip
run("python3 -m ensurepip --version 2>&1")

# Check existing site-packages in user space
run("python3 -m site --user-site 2>&1")

# Try installing a small package to verify
run("python3 -m pip install --user requests 2>&1 | tail -5", timeout=60)

# Check if we can access port 5175
run("ss -tlnp | grep -E '5175|8000' 2>/dev/null || netstat -tlnp 2>/dev/null | grep -E '5175|8000' || echo 'Ports free'")

# Check uvicorn
run("python3 -m uvicorn --version 2>&1 || echo 'uvicorn not installed'")

client.close()
