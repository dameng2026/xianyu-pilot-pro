"""
Phase 5f: Fix user_id references that interact with XianyuAccount entity
(which doesn't have a user_id column in single-tenant mode).
"""
import os
import re

ROUTES_DIR = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\api\v1\routes'


def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def fix_account_py():
    """Remove user_id filtering in account.py (XianyuAccount has no user_id column)."""
    p = os.path.join(ROUTES_DIR, 'account.py')
    c = read(p)
    # Remove the entire "if user_id:" block that filters by user_id
    c = re.sub(
        r'\s*# 按 user_id 过滤，确保用户只能看到自己所属的账号\s*\n\s*if user_id:\s*\n\s*from sqlalchemy import or_\s*\n\s*query = query\.where\(\s*\n\s*or_\(\s*\n\s*XianyuAccount\.user_id\.is_\(None\),\s*\n\s*\)\s*\n\s*\)\s*\n',
        '\n',
        c,
    )
    write(p, c)
    print('  account.py: fixed')


def fix_restful_py():
    """Remove user_id=user_id from XianyuAccount constructor in restful.py."""
    p = os.path.join(ROUTES_DIR, 'restful.py')
    c = read(p)
    # Remove user_id=user_id from XianyuAccount constructor
    c = re.sub(r'\s*user_id=user_id,\s*\n', '\n', c)
    # Also remove the user_id filtering block if it exists
    c = re.sub(
        r'\s*# 按 user_id 过滤，确保用户只能看到自己所属的账号\s*\n\s*if user_id:\s*\n\s*from sqlalchemy import or_\s*\n\s*query = query\.where\(\s*\n\s*or_\(\s*\n\s*XianyuAccount\.user_id\.is_\(None\),\s*\n\s*\)\s*\n\s*\)\s*\n',
        '\n',
        c,
    )
    write(p, c)
    print('  restful.py: fixed')


def fix_misc_py():
    """Remove user_id from XianyuAccount interactions in misc.py."""
    p = os.path.join(ROUTES_DIR, 'misc.py')
    c = read(p)
    # Remove "existing_account.user_id = user_id" (XianyuAccount has no user_id)
    c = re.sub(r'\s*existing_account\.user_id\s*=\s*user_id\s*\n', '\n', c)
    # Remove "user_id=user_id" from XianyuAccount constructor
    c = re.sub(r'\s*user_id=user_id,\s*\n', '\n', c)
    write(p, c)
    print('  misc.py: fixed')


def main():
    print('=== Phase 5f: Fix user_id with XianyuAccount ===')
    fix_account_py()
    fix_restful_py()
    fix_misc_py()
    print('\n=== Phase 5f complete ===')


if __name__ == '__main__':
    main()
