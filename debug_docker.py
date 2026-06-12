"""Check Docker permissions and available commands."""
import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(f"[exit={exit_code}] $ {cmd}")
    if out:
        print(f"  {out[:500]}")
    if err:
        print(f"  ERR: {err[:300]}")
    print()


# Check docker group access
run("docker ps 2>&1")
run("sudo docker ps 2>&1")

# Check if docker compose plugin is in another location
run("find / -name 'docker-compose*' -type f 2>/dev/null | head -5")

# Check if pip3 can install docker-compose
run("pip3 install --user docker-compose 2>&1 | tail -5", timeout=60)

# Check groups and docker access
run("groups")
run("ls -la /var/run/docker.sock 2>&1")

# Check available compose
run("dpkg -l | grep docker-compose 2>/dev/null || true")

# Try docker-compose (v1) if available
run("which docker-compose 2>/dev/null || echo 'not found'")

client.close()
