import json, re, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('backend/services/workflow_service.py', 'r', encoding='utf-8') as f:
    content = f.read()
# Test file reads correctly
print('File read OK, length:', len(content))
