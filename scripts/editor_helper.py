import json, re, os, sys

BASE = r"C:\Users\Auraa\Desktop\AI虚拟警情处置模拟训练平台"

def edit(path, old, new):
    fp = os.path.join(BASE, path)
    with open(fp, 'r', encoding='utf-8') as f:
        c = f.read()
    if old not in c:
        print(f"FAIL: old not in {path}")
        return False
    c = c.replace(old, new, 1)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(c)
    return True

def run(path, label):
    fn = os.path.join(BASE, path)
    with open(fn, 'r', encoding='utf-8') as f:
        d = json.load(f)
    print(f"Running {label} ({len(d)} edits)")
    for item in d:
        ok = edit(item['path'], item['old'], item['new'])
        print(f"  {'OK' if ok else 'FAIL'}: {item.get('label','')}")
