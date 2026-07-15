"""
Phase 5e: Fix remaining tenant_id in captcha_solver.py params dicts.
"""
import os
import re

SERVICES_DIR = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\services'

p = os.path.join(SERVICES_DIR, 'captcha_solver.py')
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# Remove "tid": tenant_id from params dicts (the SQL no longer uses :tid)
c = re.sub(r'\{"aid":\s*account_id,\s*"tid":\s*tenant_id\}', '{"aid": account_id}', c)
c = re.sub(r',\s*"tid":\s*tenant_id\}', '}', c)
c = re.sub(r'"tid":\s*tenant_id,?\s*\n', '\n', c)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)

remaining = len(re.findall(r'tenant_id', c))
print(f'captcha_solver.py: {remaining} remaining refs')
if remaining > 0:
    for line in c.split('\n'):
        if 'tenant_id' in line:
            print(f'  {line.strip()[:120]}')
