"""
Phase 5d: Final fix for remaining tenant_id patterns in ws_storage.py, ws_client.py, ws_startup.py.
Handles broken replacements, single-line signatures, VALUES placeholders, and multi-line params.
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


def fix_ws_storage():
    """Fix remaining tenant_id in ws_storage.py."""
    p = os.path.join(SERVICES_DIR, 'ws_storage.py')
    c = read(p)

    # 1. Remove "WHERE xm.tenant_id = c.tenant_id" JOIN conditions
    c = re.sub(r'\s*WHERE\s+\w+\.tenant_id\s*=\s*\w+\.tenant_id\s*\n', '\n', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*AND\s+\w+\.tenant_id\s*=\s*\w+\.tenant_id\s*\n', '\n', c, flags=re.IGNORECASE)

    # 2. Remove "tenant_id": tenant_id from multi-line params dicts
    # Pattern: "tenant_id": tenant_id, (on its own line or inline)
    c = re.sub(r'"tenant_id":\s*tenant_id,\s*\n', '', c)
    c = re.sub(r'"tenant_id":\s*tenant_id,\s*', '', c)
    # Pattern: , "tenant_id": tenant_id} at end of dict
    c = re.sub(r',\s*"tenant_id":\s*tenant_id\}', '}', c)

    # 3. Remove :tenant_id from VALUES placeholders
    # Pattern: ":tenant_id, :account_id, ..." -> ":account_id, ..."
    c = re.sub(r':tenant_id,\s*:account_id,', ':account_id,', c)
    c = re.sub(r':tenant_id,\s*', '', c)

    # 4. Remove "tenant_id" column from INSERT statements
    # Pattern: "INSERT INTO table (tenant_id, account_id, ..." -> "INSERT INTO table (account_id, ..."
    c = re.sub(r'INSERT INTO (\w+)\s*\(\s*tenant_id,\s*', r'INSERT INTO \1 (', c)
    # Pattern: ", tenant_id, " in column lists
    c = re.sub(r'\(tenant_id,\s*', '(', c)
    c = re.sub(r',\s*tenant_id,\s*', ', ', c)
    c = re.sub(r',\s*tenant_id\)', ')', c)

    # 5. Fix broken "db=db, tenant_id=account_id=account_id," pattern
    c = re.sub(r'db=db,\s*tenant_id=account_id=account_id,', 'db=db, account_id=account_id,', c)

    # 6. Remove remaining "tenant_id": tenant_id patterns in various forms
    c = re.sub(r'\{"tenant_id":\s*tenant_id,\s*', '{', c)

    write(p, c)
    remaining = len(re.findall(r'tenant_id', c))
    print(f'  ws_storage.py: {remaining} remaining refs')
    if remaining > 0:
        for line in c.split('\n'):
            if 'tenant_id' in line:
                print(f'    {line.strip()[:120]}')


def fix_ws_client():
    """Fix remaining tenant_id in ws_client.py."""
    p = os.path.join(SERVICES_DIR, 'ws_client.py')
    c = read(p)

    # 1. Fix single-line function signatures: "def func(tenant_id: int, account_id: int)"
    c = re.sub(r'def\s+(\w+)\(tenant_id:\s*int,\s*account_id:\s*int', r'def \1(account_id: int', c)
    c = re.sub(r'def\s+(\w+)\(tenant_id:\s*int,\s*', r'def \1(', c)
    # Also handle "async def"
    c = re.sub(r'async def\s+(\w+)\(tenant_id:\s*int,\s*account_id:\s*int', r'async def \1(account_id: int', c)
    c = re.sub(r'async def\s+(\w+)\(tenant_id:\s*int,\s*', r'async def \1(', c)

    # 2. Remove "AND tenant_id = :tid" from SQL queries
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tid', '', c, flags=re.IGNORECASE)

    # 3. Remove "tid": tenant_id from params dicts
    c = re.sub(r'\{"aid":\s*account_id,\s*"tid":\s*tenant_id\}', '{"aid": account_id}', c)
    c = re.sub(r'"tid":\s*tenant_id,?\s*\n', '\n', c)
    c = re.sub(r',\s*"tid":\s*tenant_id\}', '}', c)

    # 4. Fix broken "tenant_id=event_display_name=" pattern
    # Original was: tenant_id=self.tenant_id,\n                        event_display_name="Cookie 到期",
    c = c.replace(
        'tenant_id=event_display_name="Cookie 到期",',
        'event_display_name="Cookie 到期",'
    )

    # 5. Fix broken "tenant_id=account_id=self.account_id," pattern
    # Original was: tenant_id=self.tenant_id,\n                            account_id=self.account_id,
    c = c.replace(
        'tenant_id=account_id=self.account_id,',
        'account_id=self.account_id,'
    )

    # 6. Remove tenant_id from _lookup_account_name_safe calls
    # Pattern: _lookup_account_name_safe(self.tenant_id, self.account_id)
    c = re.sub(r'_lookup_account_name_safe\(self\.tenant_id,\s*self\.account_id\)',
               '_lookup_account_name_safe(self.account_id)', c)
    c = re.sub(r'_lookup_account_name_safe\(tenant_id,\s*account_id\)',
               '_lookup_account_name_safe(account_id)', c)
    c = re.sub(r'_lookup_account_name_safe\(tenant_id,\s*int\(account_id\)\)',
               '_lookup_account_name_safe(int(account_id))', c)

    write(p, c)
    remaining = len(re.findall(r'tenant_id', c))
    print(f'  ws_client.py: {remaining} remaining refs')
    if remaining > 0:
        for line in c.split('\n'):
            if 'tenant_id' in line:
                print(f'    {line.strip()[:120]}')


def fix_ws_startup():
    """Fix remaining tenant_id in ws_startup.py."""
    p = os.path.join(SERVICES_DIR, 'ws_startup.py')
    c = read(p)

    # 1. Fix single-line function signatures
    c = re.sub(r'async def\s+(\w+)\(tenant_id:\s*int,\s*account_id:\s*int([^)]*)\)',
               r'async def \1(account_id: int\2)', c)
    c = re.sub(r'def\s+(\w+)\(tenant_id:\s*int,\s*account_id:\s*int([^)]*)\)',
               r'def \1(account_id: int\2)', c)

    # 2. Remove "AND tenant_id = :tid" from SQL
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tid', '', c, flags=re.IGNORECASE)

    # 3. Remove "tid": tenant_id from params
    c = re.sub(r'\{"aid":\s*account_id,\s*"tid":\s*tenant_id\}', '{"aid": account_id}', c)
    c = re.sub(r'"tid":\s*tenant_id,?\s*\n', '\n', c)

    # 4. Remove "a.tenant_id" from SELECT and JOIN
    c = re.sub(r',\s*a\.tenant_id', '', c, flags=re.IGNORECASE)
    c = re.sub(r'a\.tenant_id,\s*', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*AND\s+auth\.tenant_id\s*=\s*a\.tenant_id', '', c, flags=re.IGNORECASE)

    # 5. Remove "tenant_id = acct["tenant_id"]" assignment
    c = re.sub(r'\s*tenant_id\s*=\s*acct\["tenant_id"\]\s*\n', '\n', c)

    # 6. Remove tenant_id from function calls
    c = re.sub(r'handle_incoming_message_for_delivery\(\s*tenant_id,\s*account_id,',
               'handle_incoming_message_for_delivery(\n        account_id,', c)
    c = re.sub(r'_run_delivery_after_message_saved\(\s*tenant_id,\s*account_id,',
               '_run_delivery_after_message_saved(\n        account_id,', c)
    c = re.sub(r'_run_ai_auto_reply_after_message_saved\(\s*tenant_id,\s*account_id,',
               '_run_ai_auto_reply_after_message_saved(\n        account_id,', c)
    c = re.sub(r'on_message_callback\(\s*tenant_id,\s*account_id,',
               'on_message_callback(\n        account_id,', c)

    write(p, c)
    remaining = len(re.findall(r'tenant_id', c))
    print(f'  ws_startup.py: {remaining} remaining refs')
    if remaining > 0:
        for line in c.split('\n'):
            if 'tenant_id' in line:
                print(f'    {line.strip()[:120]}')


def main():
    print('=== Phase 5d: Final services fix ===')
    fix_ws_storage()
    print()
    fix_ws_client()
    print()
    fix_ws_startup()
    print('\n=== Phase 5d complete ===')


if __name__ == '__main__':
    main()
