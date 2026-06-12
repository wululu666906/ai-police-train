import json, re, os, base64, sys

def edit(path, old, new):
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    if old not in c:
        print(f"OLD NOT FOUND in {path}")
        return False
    c = c.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    return True

# Decode the base64-encoded replacement data
data = json.loads(base64.b64decode(sys.argv[1]).decode('utf-8'))
base_dir = r"C:\Users\Auraa\Desktop\AI虚拟警情处置模拟训练平台"

for item in data:
    path = os.path.join(base_dir, item['path'])
    result = edit(path, item['old'], item['new'])
    print(f"{'OK' if result else 'FAIL'}: {item.get('label', path)}")
