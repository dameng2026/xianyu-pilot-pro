"""
Phase 5b: Fix remaining tenant_id references in captcha_solver.py and verify
ws_storage.py and ws_client.py.
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


def fix_captcha_solver():
    """Fix remaining tenant_id references in captcha_solver.py."""
    p = os.path.join(SERVICES_DIR, 'captcha_solver.py')
    c = read(p)
    # Remove "tenant_id = int(row["tenant_id"])" - row no longer has tenant_id column
    c = re.sub(r'\s*tenant_id\s*=\s*int\(row\["tenant_id"\]\)\s*\n', '\n', c)
    # Remove "X-Internal-Tenant-Id" header
    c = re.sub(r'\s*"X-Internal-Tenant-Id":\s*str\(tenant_id\),?\s*\n', '\n', c)
    # Remove tenant_id from docstring
    c = re.sub(r'\s*tenant_id:\s*租户 ID\s*\n', '\n', c)
    # Remove "AND tenant_id = :tid" from SQL queries
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tid', '', c, flags=re.IGNORECASE)
    # Remove "tid": tenant_id from params
    c = re.sub(r'\s*"tid":\s*tenant_id,?\s*\n', '\n', c)
    # Fix params dicts that now have trailing/leading commas
    c = re.sub(r'\{"aid":\s*account_id,\s*\}', '{"aid": account_id}', c)
    # Remove tenant_id from notify_captcha_required call
    c = re.sub(
        r'notify_captcha_required\(\s*tenant_id,\s*account_id,',
        'notify_captcha_required(\n                account_id,',
        c,
    )
    write(p, c)
    print('  captcha_solver.py: fixed')


def verify_ws_storage():
    """Verify ws_storage.py has no broken tenant_id references."""
    p = os.path.join(SERVICES_DIR, 'ws_storage.py')
    c = read(p)
    # Find any remaining tenant_id references
    matches = re.findall(r'.*tenant_id.*', c)
    if matches:
        print(f'  ws_storage.py: {len(matches)} remaining tenant_id refs:')
        for m in matches[:20]:
            print(f'    {m.strip()[:100]}')
    else:
        print('  ws_storage.py: clean')


def verify_ws_client():
    """Verify ws_client.py has no broken tenant_id references."""
    p = os.path.join(SERVICES_DIR, 'ws_client.py')
    c = read(p)
    matches = re.findall(r'.*tenant_id.*', c)
    if matches:
        print(f'  ws_client.py: {len(matches)} remaining tenant_id refs:')
        for m in matches[:20]:
            print(f'    {m.strip()[:100]}')
    else:
        print('  ws_client.py: clean')


def verify_ws_startup():
    """Verify ws_startup.py has no broken tenant_id references."""
    p = os.path.join(SERVICES_DIR, 'ws_startup.py')
    c = read(p)
    matches = re.findall(r'.*tenant_id.*', c)
    if matches:
        print(f'  ws_startup.py: {len(matches)} remaining tenant_id refs:')
        for m in matches[:20]:
            print(f'    {m.strip()[:100]}')
    else:
        print('  ws_startup.py: clean')


def main():
    print('=== Phase 5b: Fix captcha_solver and verify ===')
    fix_captcha_solver()
    verify_ws_storage()
    verify_ws_client()
    verify_ws_startup()
    print('\n=== Phase 5b complete ===')


if __name__ == '__main__':
    main()
