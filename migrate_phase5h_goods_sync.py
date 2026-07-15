"""
Phase 5h: Fix remaining tenant_id in xianyu_goods_sync.py - broken replacements and dict keys.
"""
import os
import re

p = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\services\xianyu_goods_sync.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Fix broken "tenant_id=account_id=account_id" patterns
# Original was: tenant_id=tenant_id, account_id=account_id
# My regex removed "tenant_id=tenant_id," leaving "tenant_id=account_id=account_id"
c = c.replace('tenant_id=account_id=account_id,', 'account_id=account_id,')
c = c.replace('tenant_id=account_id=account_id', 'account_id=account_id')

# 2. Remove "tenant_id" from the set check: if key in {"tenant_id", "account_id"}:
c = re.sub(r'if key in \{"tenant_id",\s*"account_id"\}:', 'if key in {"account_id"}:', c)
c = re.sub(r'if key in \{"account_id",\s*"tenant_id"\}:', 'if key in {"account_id"}:', c)

# 3. Remove "values["tenant_id"] = goods_dict.get("tenant_id")"
c = re.sub(r'\s*values\["tenant_id"\]\s*=\s*goods_dict\.get\("tenant_id"\)\s*\n', '\n', c)

# 4. Remove any remaining "tenant_id" keys from goods dict literals
c = re.sub(r'"tenant_id":\s*\w+\.get\("tenant_id"\),?\s*\n', '\n', c)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)

remaining = len(re.findall(r'tenant_id', c))
print(f'xianyu_goods_sync.py: {remaining} remaining refs')
if remaining > 0:
    for line in c.split('\n'):
        if 'tenant_id' in line:
            print(f'  {line.strip()[:120]}')
