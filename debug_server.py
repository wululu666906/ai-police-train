"""Debug Docker Compose installation on server."""
import paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd, sudo=False, timeout=30):
    if sudo:
        cmd = f"echo '{PASSWORD}' | sudo -S bash -c '{cmd}'"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"[exit={exit_code}] {cmd[:80]}")
    if out[:200]:
        print(f"  OUT: {out[:200]}")
    if err[:200]:
        print(f"  ERR: {err[:200]}")
    return exit_code, out, err


# Check docker and system
run("docker --version")
run("whoami")
run("id")
run("ls -la /usr/local/lib/docker/cli-plugins/ 2>/dev/null || echo 'No plugin dir'")
run("ls -la /usr/libexec/docker/cli-plugins/ 2>/dev/null || echo 'No exec dir'")

# Check available docker compose packages
run("apt-cache search docker-compose 2>/dev/null | head -10 || true")

# Try installing docker compose plugin properly
run("mkdir -p /usr/local/lib/docker/cli-plugins", sudo=True)
run("curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose 2>&1 | head -5", sudo=True, timeout=60)
run("chmod +x /usr/local/lib/docker/cli-plugins/docker-compose", sudo=True)
run("docker compose version")

client.close()
