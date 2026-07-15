"""
Phase 5i: Thorough tenant_id cleanup for remaining service files:
cookie_token_refresher.py, feishu_bot.py, feishu_chat.py, notify_dispatcher.py,
ws_delivery_handler.py, xianyu_api_service.py
"""
import os
import re

SERVICES_DIR = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\services'


def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def thorough_cleanup(file_path, label):
    """Apply thorough tenant_id cleanup patterns to a file."""
    c = read(file_path)

    # 1. Remove tenant_id from function signatures
    c = re.sub(r'^\s*tenant_id:\s*int\s*=\s*\d+,?\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id:\s*int,?\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id:\s*Optional\[int\]\s*=\s*None,?\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r',\s*tenant_id:\s*int\s*=\s*\d+', '', c)
    c = re.sub(r',\s*tenant_id:\s*int', '', c)
    c = re.sub(r',\s*tenant_id:\s*Optional\[int\]\s*=\s*None', '', c)
    # Single-line signatures
    c = re.sub(r'def\s+(\w+)\(tenant_id:\s*int,\s*account_id:\s*int', r'def \1(account_id: int', c)
    c = re.sub(r'async def\s+(\w+)\(tenant_id:\s*int,\s*account_id:\s*int', r'async def \1(account_id: int', c)
    c = re.sub(r'def\s+(\w+)\(tenant_id:\s*int,\s*', r'def \1(', c)
    c = re.sub(r'async def\s+(\w+)\(tenant_id:\s*int,\s*', r'async def \1(', c)

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
    c = re.sub(r'\s*JOIN\s+\w+\s+\w+\s+ON\s+\w+\.tenant_id\s*=\s*\w+\.tenant_id', '', c, flags=re.IGNORECASE)

    # 4. Remove .where(Model.tenant_id == tenant_id) clauses
    c = re.sub(r'\.where\(\s*\w+\.tenant_id\s*==\s*tenant_id,\s*', '.where(', c)
    c = re.sub(r'\w+\.tenant_id\s*==\s*tenant_id,\s*', '', c)

    # 5. Remove tenant_id from SELECT column lists
    c = re.sub(r'SELECT\s+\w+\.tenant_id,\s*', 'SELECT ', c, flags=re.IGNORECASE)
    c = re.sub(r'\w+\.tenant_id,\s*', '', c)

    # 6. Remove tenant_id from params dicts
    c = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
    c = re.sub(r'\s*"tenant_id":\s*int\([^)]*\),?\s*\n', '\n', c)
    c = re.sub(r'\{"tenant_id":\s*tenant_id,\s*', '{', c)
    c = re.sub(r',\s*"tenant_id":\s*tenant_id\}', '}', c)
    c = re.sub(r'"tid":\s*tenant_id,?\s*\n', '\n', c)
    c = re.sub(r'\{"aid":\s*account_id,\s*"tid":\s*tenant_id\}', '{"aid": account_id}', c)

    # 7. Remove tenant_id from INSERT statements
    c = re.sub(r'INSERT INTO (\w+)\s*\(\s*tenant_id,\s*', r'INSERT INTO \1 (', c)
    c = re.sub(r'\(tenant_id,\s*', '(', c)
    c = re.sub(r',\s*tenant_id,\s*', ', ', c)
    c = re.sub(r',\s*tenant_id\)', ')', c)

    # 8. Remove :tenant_id from VALUES
    c = re.sub(r':tenant_id,\s*', '', c)

    # 9. Remove tenant_id from dict literals
    c = re.sub(r'"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
    c = re.sub(r'"tenant_id":\s*tenant_id,\s*', '', c)
    c = re.sub(r'"tenant_id":\s*\d+,?\s*\n', '\n', c)

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

    # 12. Fix broken "tenant_id=account_id=account_id" patterns
    c = c.replace('tenant_id=account_id=account_id,', 'account_id=account_id,')
    c = c.replace('tenant_id=account_id=account_id', 'account_id=account_id')

    # 13. Remove "tenant_id" from set/dict checks
    c = re.sub(r'if key in \{"tenant_id",\s*"account_id"\}:', 'if key in {"account_id"}:', c)
    c = re.sub(r'if key in \{"account_id",\s*"tenant_id"\}:', 'if key in {"account_id"}:', c)

    # 14. Remove tenant_id = ... assignments
    c = re.sub(r'^\s*tenant_id\s*=\s*int\([^)]*\)\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id\s*=\s*\d+\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id\s*=\s*\w+\["tenant_id"\]\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id\s*=\s*\w+\.get\("tenant_id"\)\s*\n', '', c, flags=re.MULTILINE)

    # 15. Remove self.tenant_id
    c = re.sub(r'^\s*self\.tenant_id\s*=\s*tenant_id\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*self\.tenant_id\s*=\s*\d+\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r',\s*self\.tenant_id\)', ')', c)
    c = re.sub(r',\s*self\.tenant_id(?=\s*[,)])', '', c)

    # 16. Remove tenant_id from docstring
    c = re.sub(r'^\s*tenant_id:\s*[^\n]*\n', '', c, flags=re.MULTILINE)

    # 17. Remove "tenantId": tenant_id
    c = re.sub(r'\s*"tenantId":\s*tenant_id,?\s*\n', '\n', c)

    # 18. Clean up empty params
    c = re.sub(r'\{\s*\}', '{}', c)

    write(file_path, c)

    remaining = len(re.findall(r'tenant_id', c))
    print(f'  {label}: {remaining} remaining refs')
    if remaining > 0:
        for line in c.split('\n'):
            if 'tenant_id' in line:
                print(f'    {line.strip()[:120]}')


def main():
    print('=== Phase 5i: Remaining services cleanup ===')
    files = [
        ('cookie_token_refresher.py', 'cookie_token_refresher.py'),
        ('feishu_bot.py', 'feishu_bot.py'),
        ('feishu_chat.py', 'feishu_chat.py'),
        ('notify_dispatcher.py', 'notify_dispatcher.py'),
        ('ws_delivery_handler.py', 'ws_delivery_handler.py'),
        ('xianyu_api_service.py', 'xianyu_api_service.py'),
    ]
    for fname, label in files:
        thorough_cleanup(os.path.join(SERVICES_DIR, fname), label)
        print()
    print('=== Phase 5i complete ===')


if __name__ == '__main__':
    main()
