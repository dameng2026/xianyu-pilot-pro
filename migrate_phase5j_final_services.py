"""
Phase 5j: Fix remaining tenant_id patterns in cookie_token_refresher.py,
feishu_bot.py, feishu_chat.py, notify_dispatcher.py.
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


def fix_cookie_token_refresher():
    """Fix remaining tenant_id in cookie_token_refresher.py."""
    p = os.path.join(SERVICES_DIR, 'cookie_token_refresher.py')
    c = read(p)
    # Remove "tenant_id=int(acc["tenant_id"])," 
    c = re.sub(r'\s*tenant_id=int\(acc\["tenant_id"\]\),?\s*\n', '\n', c)
    # Remove comment "# 更新 tenant_id（可能变化）"
    c = re.sub(r'\s*# 更新 tenant_id.*\n', '\n', c)
    # Remove "_states[aid].tenant_id = int(acc["tenant_id"])"
    c = re.sub(r'\s*_states\[aid\]\.tenant_id\s*=\s*int\(acc\["tenant_id"\]\)\s*\n', '\n', c)
    # Remove "state.tenant_id" from function calls and params
    c = re.sub(r'_call_has_login\(state\.account_id,\s*state\.tenant_id\)',
               '_call_has_login(state.account_id)', c)
    c = re.sub(r'\{"aid":\s*state\.account_id,\s*"tid":\s*state\.tenant_id\}',
               '{"aid": state.account_id}', c)
    # Remove "tenant_id=int(row["tenant_id"])"
    c = re.sub(r'\s*tenant_id=int\(row\["tenant_id"\]\)\s*\n', '\n', c)
    # Remove "state.tenant_id" attribute references
    c = re.sub(r',\s*state\.tenant_id', '', c)
    c = re.sub(r'state\.tenant_id,\s*', '', c)
    write(p, c)
    remaining = len(re.findall(r'tenant_id', c))
    print(f'  cookie_token_refresher.py: {remaining} remaining refs')


def fix_feishu_bot():
    """Fix remaining tenant_id in feishu_bot.py.
    
    Note: feishu_bot uses tenant_id for Feishu's own multi-tenant API (tenant_access_token).
    In single-tenant mode, tenant_id=1 is used. We keep the function signatures but
    remove SQL tenant_id column references.
    """
    p = os.path.join(SERVICES_DIR, 'feishu_bot.py')
    c = read(p)
    # Remove "tenant_id" from SQL params dicts
    c = re.sub(r'\{"tid":\s*tenant_id\}', '{}', c)
    c = re.sub(r'\{"tid":\s*tenant_id,\s*', '{', c)
    # Remove "AND tenant_id = :tid" from SQL
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tid', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tid\s*\n', '\n', c, flags=re.IGNORECASE)
    c = re.sub(r'WHERE\s+tenant_id\s*=\s*:tid\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    # Remove tenant_id from SELECT
    c = re.sub(r'SELECT\s+tenant_id,\s*', 'SELECT ', c, flags=re.IGNORECASE)
    write(p, c)
    remaining = len(re.findall(r'tenant_id', c))
    print(f'  feishu_bot.py: {remaining} remaining refs (Feishu API tenant_id - legitimate)')


def fix_feishu_chat():
    """Fix remaining tenant_id in feishu_chat.py."""
    p = os.path.join(SERVICES_DIR, 'feishu_chat.py')
    c = read(p)
    # Fix broken "tenant_id=account_id=target_account_id" pattern
    c = c.replace('tenant_id=account_id=target_account_id,', 'account_id=target_account_id,')
    c = c.replace('tenant_id=account_id=target_account_id', 'account_id=target_account_id')
    # Remove "tid": tenant_id from params dicts
    c = re.sub(r'\{"tid":\s*tenant_id,\s*', '{', c)
    c = re.sub(r'\{"tid":\s*tenant_id\}', '{}', c)
    c = re.sub(r',\s*"tid":\s*tenant_id\}', '}', c)
    # Remove "X-Internal-Tenant-Id" header
    c = re.sub(r'\s*"X-Internal-Tenant-Id":\s*str\(tenant_id\),?\s*\n', '\n', c)
    # Remove "AND tenant_id = :tid" from SQL
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tid', '', c, flags=re.IGNORECASE)
    c = re.sub(r'WHERE\s+tenant_id\s*=\s*:tid\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    # Remove "unb": ..., "aid": ..., "tid": tenant_id -> keep unb and aid
    c = re.sub(r'\{"unb":\s*new_unb,\s*"aid":\s*account_id,\s*"tid":\s*tenant_id\}',
               '{"unb": new_unb, "aid": account_id}', c)
    write(p, c)
    remaining = len(re.findall(r'tenant_id', c))
    print(f'  feishu_chat.py: {remaining} remaining refs')


def fix_notify_dispatcher():
    """Fix remaining tenant_id in notify_dispatcher.py."""
    p = os.path.join(SERVICES_DIR, 'notify_dispatcher.py')
    c = read(p)
    # Remove {"tid": tenant_id} params
    c = re.sub(r'\{"tid":\s*tenant_id\}', '{}', c)
    c = re.sub(r'\{"tid":\s*tenant_id,\s*', '{', c)
    # Remove "if not tenant_id:" check
    c = re.sub(r'\s*if not tenant_id:\s*\n\s*return\s*\n', '\n', c)
    c = re.sub(r'\s*if not tenant_id:\s*\n\s*return\s+None\s*\n', '\n', c)
    write(p, c)
    remaining = len(re.findall(r'tenant_id', c))
    print(f'  notify_dispatcher.py: {remaining} remaining refs')


def main():
    print('=== Phase 5j: Fix remaining service patterns ===')
    fix_cookie_token_refresher()
    fix_feishu_bot()
    fix_feishu_chat()
    fix_notify_dispatcher()
    print('\n=== Phase 5j complete ===')


if __name__ == '__main__':
    main()
