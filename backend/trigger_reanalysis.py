"""触发视频重新分析"""
import requests

BASE = "http://127.0.0.1:8000"

# 登录
resp = requests.post(f"{BASE}/auth/token", data={"username": "admin", "password": "123456"})
login_data = resp.json()
print(f"Login response keys: {list(login_data.keys())}")
token = login_data.get("access_token") or login_data.get("token") or ""
if not token:
    print(f"Login failed! {login_data}")
    exit(1)
headers = {"Authorization": f"Bearer {token}"}

# 触发所有视频重新分析（重建节点类型）
resp = requests.get(f"{BASE}/videos/admin/list?page_size=50", headers=headers)
videos = resp.json().get("items", [])
for v in videos:
    print(f"Triggering re-analysis for video {v['id']}: {v['title']} (status={v['status']}, nodes={v.get('node_count',0)})")
    r = requests.post(f"{BASE}/videos/retry-analysis/{v['id']}", headers=headers)
    print(f"  Result: {r.status_code} {r.json()}")

print("\nDone! Videos are being analyzed in the background.")
