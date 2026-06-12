#!/usr/bin/env python3
import json, re, os

BASE = r"C:\Users\Auraa\Desktop\AI虚拟警情处置模拟训练平台"

def read_file(path):
    with open(os.path.join(BASE, path), 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(os.path.join(BASE, path), 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Written: {path}")

def edit_file(path, old, new):
    content = read_file(path)
    if old not in content:
        print(f"ERROR: old string not found in {path}")
        print(f"Looking for: {repr(old[:80])}")
        return False
    content = content.replace(old, new, 1)
    write_file(path, content)
    return True

# ========== Fix TEST_MARKER in workflow_service.py ==========
print("=== Fixing TEST_MARKER ===")
content = read_file("backend/services/workflow_service.py")
old_marker = "TEST_MARKER\n\n    def _normalize_parsed_case"
new_marker = "        return persons\n\n    def _normalize_parsed_case"
if "TEST_MARKER" in content:
    content = content.replace(old_marker, new_marker, 1)
    write_file("backend/services/workflow_service.py", content)
    print("TEST_MARKER fixed")
else:
    content2 = read_file("backend/services/workflow_service.py")
    print("TEST_MARKER not found, checking file...")
    lines = content2.split('\n')
    for i, line in enumerate(lines):
        if 'return persons' in line or 'TEST' in line:
            print(f"  Line {i+1}: {repr(line)}")
