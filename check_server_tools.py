"""Check available tools for native deployment."""
import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
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
    print()
    return exit_code, out, err


# System check
run("uname -a")
run("cat /etc/os-release 2>/dev/null | head -3")
run("groups")

# Python check
run("python3 --version 2>&1")
run("pip3 --version 2>&1")
run("which python3")

# Node check
run("node --version 2>&1")
run("npm --version 2>&1")

# Check if there is a root-like account
run("cat /etc/group | grep docker")

# Check storage
run("df -h /home 2>/dev/null || df -h")

# Check available memory
run("free -h")

# Can we use docker without sudo via other groups?
run("ls -la /var/run/docker.sock 2>/dev/null")

client.close()
