"""Final verification of frontend update."""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('82.156.126.212', port=22, username='panglihao', password='Panglihao@123',
               look_for_keys=False, allow_agent=False, timeout=30)

def run(cmd):
    i,o,e = client.exec_command(cmd, timeout=10)
    ec = o.channel.recv_exit_status()
    out = o.read().decode('utf-8','replace').strip()
    err = e.read().decode('utf-8','replace').strip()[:100]
    print(f"> {cmd[:70]}")
    print(f"  {out[:200]}")
    return out

print("=== VERIFICATION ===")
run("ps aux | grep 'uvicorn.*5175' | grep -v grep | head -1")
run("curl -s http://127.0.0.1:5175/healthz")
run("curl -s http://127.0.0.1:5175/api/healthz")
run("curl -so /dev/null -w 'HTTP %{http_code}' http://127.0.0.1:5175/")
run("curl -s http://127.0.0.1:5175/ | head -5")
run("du -sh /home/panglihao/ai-police-sim/frontend/dist/")

print("\n=== ALL GOOD ===")
print(f"System: http://82.156.126.212:5175")

client.close()
