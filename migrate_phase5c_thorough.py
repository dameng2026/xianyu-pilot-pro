"""
Phase 5c: Thorough tenant_id removal from ws_storage.py, ws_client.py, ws_startup.py.
Handles function signatures, calls, SQL queries, params, and attributes.
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

    # 1. Remove tenant_id from function signatures (multi-line aware)
    # Pattern: "tenant_id: int," on its own line
    c = re.sub(r'^\s*tenant_id:\s*int\s*=\s*\d+,?\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id:\s*int,?\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id:\s*Optional\[int\]\s*=\s*None,?\s*\n', '', c, flags=re.MULTILINE)
    # Pattern: ", tenant_id: int" inline
    c = re.sub(r',\s*tenant_id:\s*int\s*=\s*\d+', '', c)
    c = re.sub(r',\s*tenant_id:\s*int', '', c)
    c = re.sub(r',\s*tenant_id:\s*Optional\[int\]\s*=\s*None', '', c)

    # 2. Remove tenant_id from function calls
    # Pattern: "func(tenant_id, " -> "func("
    c = re.sub(r'\(\s*tenant_id,\s*', '(', c)
    # Pattern: ", tenant_id," -> ","
    c = re.sub(r',\s*tenant_id,\s*', ', ', c)
    # Pattern: ", tenant_id)" -> ")"
    c = re.sub(r',\s*tenant_id\)', ')', c)
    # Pattern: ", tenant_id" at end of line -> ""
    c = re.sub(r',\s*tenant_id(?=\s*[\n)])', '', c)
    # Pattern: "tenant_id, " at start of call args
    c = re.sub(r'\btenant_id,\s*account_id', 'account_id', c)
    c = re.sub(r'\btenant_id,\s*int\(account_id\)', 'int(account_id)', c)

    # 3. Remove tenant_id from SQL queries
    # "AND tenant_id = :tenant_id"
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tenant_id', '', c, flags=re.IGNORECASE)
    # "AND X.tenant_id = :tenant_id"
    c = re.sub(r'\s*AND\s+\w+\.tenant_id\s*=\s*:\w+', '', c, flags=re.IGNORECASE)
    # "AND X.tenant_id = Y.tenant_id"
    c = re.sub(r'\s*AND\s+\w+\.tenant_id\s*=\s*\w+\.tenant_id', '', c, flags=re.IGNORECASE)
    # "WHERE tenant_id = :tenant_id AND" -> "WHERE"
    c = re.sub(r'WHERE\s+tenant_id\s*=\s*:\w+\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    c = re.sub(r'WHERE\s+\w+\.tenant_id\s*=\s*:\w+\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    # "WHERE tenant_id = :tenant_id\n" -> "\n"
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:\w+\s*\n', '\n', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+\w+\.tenant_id\s*=\s*:\w+\s*\n', '\n', c, flags=re.IGNORECASE)
    # "ON X.tenant_id = Y.tenant_id" in JOINs
    c = re.sub(r'\s*ON\s+\w+\.tenant_id\s*=\s*\w+\.tenant_id', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*AND\s+\w+\.tenant_id\s*=\s*\w+\.tenant_id', '', c, flags=re.IGNORECASE)

    # 4. Remove tenant_id from SELECT column lists
    # "SELECT a.tenant_id, " -> "SELECT "
    c = re.sub(r'SELECT\s+\w+\.tenant_id,\s*', 'SELECT ', c, flags=re.IGNORECASE)
    # "SELECT tenant_id, " -> "SELECT "
    c = re.sub(r'SELECT\s+tenant_id,\s*', 'SELECT ', c, flags=re.IGNORECASE)
    # ", a.tenant_id" at end of SELECT list
    c = re.sub(r',\s*\w+\.tenant_id(?=\s+(?:FROM|AS))', '', c, flags=re.IGNORECASE)
    # "a.tenant_id, " in SELECT
    c = re.sub(r'\w+\.tenant_id,\s*', '', c)

    # 5. Remove tenant_id from params dicts
    # "tenant_id": tenant_id,
    c = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
    # "tenant_id": int(...),
    c = re.sub(r'\s*"tenant_id":\s*int\([^)]*\),?\s*\n', '\n', c)
    # "tid": tenant_id,
    c = re.sub(r'\s*"tid":\s*tenant_id,?\s*\n', '\n', c)
    # {"tenant_id": tenant_id, "account_id": account_id} -> {"account_id": account_id}
    c = re.sub(r'\{"tenant_id":\s*tenant_id,\s*', '{', c)
    c = re.sub(r',\s*"tenant_id":\s*tenant_id\}', '}', c)

    # 6. Remove self.tenant_id attributes and references
    c = re.sub(r'^\s*self\.tenant_id\s*=\s*tenant_id\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*self\.tenant_id\s*=\s*\d+\s*\n', '', c, flags=re.MULTILINE)
    # ", tid": self.tenant_id" in params
    c = re.sub(r',?\s*"tid":\s*self\.tenant_id', '', c)
    # "self.tenant_id" in calls
    c = re.sub(r',\s*self\.tenant_id\)', ')', c)
    c = re.sub(r',\s*self\.tenant_id(?=\s*[,)])', '', c)

    # 7. Remove tenant_id = ... assignments
    c = re.sub(r'^\s*tenant_id\s*=\s*int\([^)]*\)\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id\s*=\s*\d+\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id\s*=\s*\w+\["tenant_id"\]\s*\n', '', c, flags=re.MULTILINE)
    c = re.sub(r'^\s*tenant_id\s*=\s*acct\["tenant_id"\]\s*\n', '', c, flags=re.MULTILINE)

    # 8. Remove tenant_id from logging statements
    # "tenant_id=%s" in format strings
    c = re.sub(r'tenant_id=%s,\s*', '', c)
    c = re.sub(r',\s*tenant_id=%s', '', c)
    c = re.sub(r'tenant_id=%s', '', c)
    # "tenant_id=%d" in format strings
    c = re.sub(r'tenant_id=%d,\s*', '', c)
    c = re.sub(r',\s*tenant_id=%d', '', c)
    c = re.sub(r'tenant_id=%d', '', c)
    # ", tenant_id," in logging args
    c = re.sub(r'",\s*tenant_id,\s*', '", ', c)
    c = re.sub(r'",\s*tenant_id\)', '")', c)
    # ", tenant_id)" in logging args
    c = re.sub(r',\s*tenant_id\)', ')', c)

    # 9. Remove "tenantId": tenant_id from dicts
    c = re.sub(r'\s*"tenantId":\s*tenant_id,?\s*\n', '\n', c)

    # 10. Remove tenant_id=tenant_id from function calls
    c = re.sub(r',\s*tenant_id=tenant_id', '', c)
    c = re.sub(r',\s*tenant_id=\d+', '', c)

    # 11. Clean up empty params dicts
    c = re.sub(r'\{\s*\}', '{}', c)

    # 12. Remove "tenant_id" from docstring parameter descriptions
    c = re.sub(r'^\s*tenant_id:\s*[^\n]*\n', '', c, flags=re.MULTILINE)

    write(file_path, c)

    # Count remaining
    remaining = len(re.findall(r'tenant_id', c))
    print(f'  {label}: {remaining} remaining refs')
    if remaining > 0:
        for line in c.split('\n'):
            if 'tenant_id' in line:
                print(f'    {line.strip()[:120]}')
                if remaining > 30:
                    break


def main():
    print('=== Phase 5c: Thorough services cleanup ===')
    thorough_cleanup(os.path.join(SERVICES_DIR, 'ws_storage.py'), 'ws_storage.py')
    print()
    thorough_cleanup(os.path.join(SERVICES_DIR, 'ws_client.py'), 'ws_client.py')
    print()
    thorough_cleanup(os.path.join(SERVICES_DIR, 'ws_startup.py'), 'ws_startup.py')
    print('\n=== Phase 5c complete ===')


if __name__ == '__main__':
    main()
