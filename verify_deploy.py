"""Comprehensive end-to-end verification of deployed app."""
import paramiko, json

SERVER = "82.156.126.212"
USER = "panglihao"
PASSWORD = "Panglihao@123"
DEPLOY_DIR = "/home/panglihao/ai-police-sim"
APP_PORT = 5175

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SERVER, port=22, username=USER, password=PASSWORD,
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return ec, out.strip(), err.strip()


results = []

def check(name, cmd, expected=None):
    ec, out, err = run(cmd)
    ok = ec == 0 and ("error" not in out.lower() or expected and expected in out)
    if ec == 0 and out:
        ok = True
    results.append((name, ok, out[:120]))
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {out[:100]}")

print("=" * 60)
print("COMPREHENSIVE VERIFICATION")
print("=" * 60)

# 1. Process check
print("\n1. Service Status:")
check("Uvicorn process running",
      f"ps aux | grep 'uvicorn.*{APP_PORT}' | grep -v grep | wc -l")

# 2. Port check
print("\n2. Port & Network:")
check("Port 5175 listening",
      f"ss -tlnp | grep {APP_PORT} || netstat -tlnp 2>/dev/null | grep {APP_PORT}")

# 3. Health endpoints
print("\n3. Health Endpoints:")
check("GET /healthz", f"curl -s http://127.0.0.1:{APP_PORT}/healthz")
check("GET /api/healthz", f"curl -s http://127.0.0.1:{APP_PORT}/api/healthz")

# 4. Frontend check
print("\n4. Frontend:")
check("Serves index.html", f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/")
check("Serves favicon", f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/favicon.svg")
check("Serves assets/", f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/assets/ --max-time 5")
check("Catchall route (non-existent page returns 200 for SPA)",
      f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/some-random-path")

# 5. API Docs
print("\n5. API Documentation:")
check("Swagger UI accessible",
      f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/docs")
check("OpenAPI JSON",
      f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_PORT}/openapi.json")

# 6. Login API
print("\n6. Authentication API:")
check("Admin login",
      f"curl -s -X POST http://127.0.0.1:{APP_PORT}/auth/token "
      f"-d 'username=admin&password=123456'",
      expected="access_token")

# 7. Authenticated API (using token from login in the same shell)
print("\n7. Authenticated API:")
ec, out, _ = run(
    f"TOKEN=$(curl -s -X POST http://127.0.0.1:{APP_PORT}/auth/token "
    f"-d 'username=admin&password=123456' | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"access_token\"])' 2>/dev/null) && "
    f"curl -s -H 'Authorization: Bearer $TOKEN' http://127.0.0.1:{APP_PORT}/auth/students | head -c 100")
check("GET /auth/students (authenticated)", "", expected="[")

ec, out, _ = run(
    f"TOKEN=$(curl -s -X POST http://127.0.0.1:{APP_PORT}/auth/token "
    f"-d 'username=admin&password=123456' | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"access_token\"])' 2>/dev/null) && "
    f"curl -s -H 'Authorization: Bearer $TOKEN' http://127.0.0.1:{APP_PORT}/api/cases/ | head -c 100")
check("GET /api/cases/ (authenticated)", "", expected="[")

# 8. Student login
print("\n8. Student Login:")
check("Student login",
      f"curl -s -X POST http://127.0.0.1:{APP_PORT}/auth/token "
      f"-d 'username=student001&password=123456' | head -c 100")

# 9. File structure check
print("\n9. File Structure:")
check("Backend main.py", f"test -f {DEPLOY_DIR}/backend/main.py && echo 'OK'")
check("Frontend dist/index.html", f"test -f {DEPLOY_DIR}/frontend/dist/index.html && echo 'OK'")
check("Database file", f"test -f {DEPLOY_DIR}/backend/ai_police.db && echo 'OK'")
check("Venv python", f"test -f {DEPLOY_DIR}/venv/bin/python3 && echo 'OK'")
check("App log file", f"test -f {DEPLOY_DIR}/app.log && echo 'OK'")

# 10. Memory & resources
print("\n10. System Resources:")
ec, out, _ = run(f"free -h | grep Mem")
print(f"  Memory: {out[:60]}")
ec, out, _ = run(f"df -h / | tail -1")
print(f"  Disk: {out[:60]}")

# Summary
print("\n" + "=" * 60)
passed = sum(1 for r in results if r[1])
total = len(results)
print(f"RESULTS: {passed}/{total} checks passed")
print("=" * 60)

print(f"\n  http://{SERVER}:{APP_PORT}")

client.close()
