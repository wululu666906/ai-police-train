"""Test SSH connection to deployment server."""
import sys, traceback, paramiko

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print("Connecting...", flush=True)
    client.connect(SERVER, port=22, username=USER, password=PASSWORD,
                   look_for_keys=False, allow_agent=False, timeout=30)
    print("Connected!", flush=True)
    stdin, stdout, stderr = client.exec_command("whoami", timeout=10)
    print("Output:", stdout.read().decode(), flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
finally:
    try: client.close()
    except: pass
