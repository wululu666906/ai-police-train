"""Verify that scene roles API returns avatar data."""
import json, paramiko, re

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('82.156.126.212', port=22, username='panglihao', password='Panglihao@123',
               look_for_keys=False, allow_agent=False, timeout=30)


def run(cmd):
    i, o, e = client.exec_command(cmd, timeout=15, get_pty=True)
    ec = o.channel.recv_exit_status()
    return o.read().decode('utf-8', 'replace').strip()


# 1. Login
resp = run("curl -s -X POST http://127.0.0.1:5175/auth/token -d 'username=admin&password=123456'")
m = re.search(r'"access_token":\s*"([^"]+)"', resp)
if not m:
    print("Login failed")
    client.close()
    exit(1)
token = m.group(1)
print(f"Token: {token[:20]}...")

# 2. Get cases
cases_raw = run(f"curl -s -H 'Authorization: Bearer {token}' http://127.0.0.1:5175/api/cases/ 2>/dev/null")
print(f"Cases: {cases_raw[:100]}")

# 3. Check a training session if one exists
# First list sessions
sessions_raw = run(f"curl -s -H 'Authorization: Bearer {token}' http://127.0.0.1:5175/api/student/history 2>/dev/null")
print(f"Sessions: {sessions_raw[:100]}")

# Try to find a session with scene roles
sessions = json.loads(sessions_raw) if sessions_raw.startswith('[') else []
if sessions:
    session_id = sessions[0].get('id') if isinstance(sessions[0], dict) else None
    if session_id:
        detail = run(
            f"curl -s -H 'Authorization: Bearer {token}' "
            f"http://127.0.0.1:5175/api/training/session/{session_id} 2>/dev/null"
        )
        try:
            data = json.loads(detail)
            roles = data.get('scene_roles', [])
            print(f"\nScene roles ({len(roles)}):")
            for role in roles:
                print(f"  {role.get('name'):10s} | avatar_id={role.get('avatar_id'):2s} | avatar_url={role.get('avatar_url', 'N/A')}")
        except:
            print(f"Could not parse session detail: {detail[:200]}")

# 4. Check avatar static file serving
for i in [1, 5, 10, 15, 20]:
    code = run(f"curl -so /dev/null -w '%{{http_code}}' http://127.0.0.1:5175/avatars/avatar_{i:02d}.svg 2>/dev/null")
    print(f"Avatar {i:02d}: HTTP {code}")

client.close()
