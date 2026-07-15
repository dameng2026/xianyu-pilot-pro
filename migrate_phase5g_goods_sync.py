"""
Phase 5g: Remove tenant_id from xianyu_goods_sync.py sync functions.
The XianyuAccountAuth/XianyuGoods entities don't have tenant_id columns.
"""
import os
import re

p = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\services\xianyu_goods_sync.py'
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Remove tenant_id from function signatures
# "tenant_id: int," on its own line
c = re.sub(r'^\s*tenant_id:\s*int\s*=\s*\d+,?\s*\n', '', c, flags=re.MULTILINE)
c = re.sub(r'^\s*tenant_id:\s*int,?\s*\n', '', c, flags=re.MULTILINE)
# ", tenant_id: int" inline
c = re.sub(r',\s*tenant_id:\s*int\s*=\s*\d+', '', c)
c = re.sub(r',\s*tenant_id:\s*int', '', c)
# "def func(tenant_id: int, account_id: int" -> "def func(account_id: int"
c = re.sub(r'def\s+(\w+)\(tenant_id:\s*int,\s*account_id:\s*int', r'def \1(account_id: int', c)
c = re.sub(r'async def\s+(\w+)\(tenant_id:\s*int,\s*account_id:\s*int', r'async def \1(account_id: int', c)
c = re.sub(r'def\s+(\w+)\(card_data:\s*dict,\s*account_id:\s*int,\s*tenant_id:\s*int\)',
           r'def \1(card_data: dict, account_id: int)', c)

# 2. Remove tenant_id from function calls
c = re.sub(r'\(\s*tenant_id,\s*', '(', c)
c = re.sub(r',\s*tenant_id,\s*', ', ', c)
c = re.sub(r',\s*tenant_id\)', ')', c)
c = re.sub(r',\s*tenant_id(?=\s*[\n)])', '', c)
c = re.sub(r'\btenant_id,\s*account_id', 'account_id', c)
c = re.sub(r'\btenant_id,\s*int\(account_id\)', 'int(account_id)', c)

# 3. Remove tenant_id from SQL queries
c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:\w+', '', c, flags=re.IGNORECASE)
c = re.sub(r'\s*AND\s+\w+\.tenant_id\s*=\s*:\w+', '', c, flags=re.IGNORECASE)
c = re.sub(r'\s*AND\s+\w+\.tenant_id\s*=\s*\w+\.tenant_id', '', c, flags=re.IGNORECASE)
c = re.sub(r'WHERE\s+tenant_id\s*=\s*:\w+\s+AND', 'WHERE', c, flags=re.IGNORECASE)
c = re.sub(r'WHERE\s+\w+\.tenant_id\s*=\s*:\w+\s+AND', 'WHERE', c, flags=re.IGNORECASE)
c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:\w+\s*\n', '\n', c, flags=re.IGNORECASE)
c = re.sub(r'\s*WHERE\s+\w+\.tenant_id\s*=\s*:\w+\s*\n', '\n', c, flags=re.IGNORECASE)
c = re.sub(r'\s*ON\s+\w+\.tenant_id\s*=\s*\w+\.tenant_id', '', c, flags=re.IGNORECASE)

# 4. Remove .where(Model.tenant_id == tenant_id) clauses
c = re.sub(r'\.where\(\s*XianyuAccountAuth\.tenant_id\s*==\s*tenant_id,\s*', '.where(', c)
c = re.sub(r'XianyuAccountAuth\.tenant_id\s*==\s*tenant_id,\s*', '', c)
c = re.sub(r'XianyuGoods\.tenant_id\s*==\s*tenant_id,\s*', '', c)

# 5. Remove tenant_id from SELECT column lists
c = re.sub(r'SELECT\s+\w+\.tenant_id,\s*', 'SELECT ', c, flags=re.IGNORECASE)
c = re.sub(r'\w+\.tenant_id,\s*', '', c)

# 6. Remove tenant_id from params dicts
c = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
c = re.sub(r'\s*"tenant_id":\s*int\([^)]*\),?\s*\n', '\n', c)
c = re.sub(r'\{"tenant_id":\s*tenant_id,\s*', '{', c)
c = re.sub(r',\s*"tenant_id":\s*tenant_id\}', '}', c)

# 7. Remove tenant_id from INSERT statements
c = re.sub(r'INSERT INTO (\w+)\s*\(\s*tenant_id,\s*', r'INSERT INTO \1 (', c)
c = re.sub(r'\(tenant_id,\s*', '(', c)
c = re.sub(r',\s*tenant_id,\s*', ', ', c)
c = re.sub(r',\s*tenant_id\)', ')', c)

# 8. Remove :tenant_id from VALUES
c = re.sub(r':tenant_id,\s*', '', c)

# 9. Remove tenant_id from dict literals (e.g., "tenant_id": tenant_id in goods dict)
c = re.sub(r'"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
c = re.sub(r'"tenant_id":\s*tenant_id,\s*', '', c)

# 10. Remove tenant_id from logging
c = re.sub(r'tenant_id=%s,\s*', '', c)
c = re.sub(r',\s*tenant_id=%s', '', c)
c = re.sub(r'tenant_id=%s', '', c)
c = re.sub(r'tenant_id=%d,\s*', '', c)
c = re.sub(r',\s*tenant_id=%d', '', c)
c = re.sub(r'tenant_id=%d', '', c)
c = re.sub(r'",\s*tenant_id,\s*', '", ', c)
c = re.sub(r'",\s*tenant_id\)', '")', c)
c = re.sub(r',\s*tenant_id\)', ')', c)
c = re.sub(r',\s*tenant_id,\s*', ', ', c)

# 11. Remove tenant_id=tenant_id from calls
c = re.sub(r',\s*tenant_id=tenant_id', '', c)
c = re.sub(r'tenant_id=tenant_id,\s*', '', c)

# 12. Remove "tenant_id=int(fields.get("tenant_id") or 0)," 
c = re.sub(r'\s*tenant_id=int\(fields\.get\("tenant_id"\)\s*or\s*0\),?\s*\n', '\n', c)

# 13. Remove "tenant_id: int," from docstring/Args sections
c = re.sub(r'^\s*tenant_id:\s*[^\n]*\n', '', c, flags=re.MULTILINE)

# 14. Clean up empty params
c = re.sub(r'\{\s*\}', '{}', c)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)

remaining = len(re.findall(r'tenant_id', c))
print(f'xianyu_goods_sync.py: {remaining} remaining refs')
if remaining > 0:
    for line in c.split('\n'):
        if 'tenant_id' in line:
            print(f'  {line.strip()[:120]}')
