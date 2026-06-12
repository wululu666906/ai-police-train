"""Check app status after frontend update."""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('82.156.126.212', port=22, username='panglihao', password='Panglihao@123',
               look_for_keys=False, allow_agent=False, timeout=30)

def run(cmd):
    i,o,e = client.exec_command(cmd, timeout=15, get_pty=True)
    ec = o.channel.recv_exit_status()
    print(f"$ {cmd[:80]}")
    print(f"  {o.read().decode('utf-8','replace')[:300]}")
    err = e.read().decode('utf-8','replace')[:200]
    if err.strip(): print(f"  ERR: {err}")

run("ps aux | grep uvicorn | grep -v grep")
run("cat /home/panglihao/ai-police-sim/app.log | tail -20")
run("curl -s http://127.0.0.1:5175/healthz")
run("curl -so /dev/null -w '%{http_code}' http://127.0.0.1:5175/")
run("ls -la /home/panglihao/ai-police-sim/frontend/dist/")

client.close()
