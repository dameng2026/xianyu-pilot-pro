"""
Phase 2: Generic transformations applied to all route files.
- Remove tenant_id/user_id references (except message fields like sender_user_id/receiver_user_id)
- Remove disallowed imports (automation_runtime, opportunity, workflow, ai_transaction, opportunity_draft_service)
- Make update_ws_heartbeat import optional (no-op fallback) since automation_runtime is not copied
"""
import os
import re

TARGET_ROUTES_DIR = r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\api\v1\routes"

# Files to apply generic transformations to (all route files except __init__.py)
ROUTE_FILES = [
    "captcha.py", "feishu.py", "internal.py", "login.py", "restful.py", "sse.py",
    "account.py", "items.py", "order.py", "dashboard.py", "messages.py",
    "auto_delivery.py", "auto_reply.py", "kami.py", "quick_reply.py",
    "auto_reply_scope.py", "auto_category.py", "content_manage.py", "system.py", "misc.py",
]


def transform_content(content: str, filename: str) -> str:
    """Apply generic transformations to file content."""

    # ============================================================
    # 1. Remove disallowed imports
    # ============================================================
    # Remove automation_runtime import lines (we'll handle update_ws_heartbeat specially)
    # Replace the automation_runtime import with a no-op fallback for update_ws_heartbeat
    content = re.sub(
        r'from \.+services\.automation_runtime import \(?\s*[^)]*\)?\s*\n',
        _automation_runtime_replacement,
        content,
    )
    # Single-line variant
    content = re.sub(
        r'from \.+services\.automation_runtime import [^\n]+\n',
        _automation_runtime_replacement,
        content,
    )

    # Remove opportunity_draft_service imports
    content = re.sub(r'from \.+services\.opportunity_draft_service import [^\n]+\n', '', content)

    # Remove relative route imports for non-copied modules
    content = re.sub(r'from \.opportunity import [^\n]+\n', '', content)
    content = re.sub(r'from \.workflow import [^\n]+\n', '', content)
    content = re.sub(r'from \.ai_transaction import [^\n]+\n', '', content)
    content = re.sub(r'from \.ai_transaction_engine import [^\n]+\n', '', content)

    # ============================================================
    # 2. Remove tenant_id/user_id from current_user context
    # ============================================================
    # Remove lines like: tenant_id = current_user.get("tenant_id")
    content = re.sub(r'\s*tenant_id\s*=\s*current_user\.get\(\s*["\']tenant_id["\']\s*\)\s*\n', '\n', content)
    content = re.sub(r'\s*tenant_id\s*=\s*current_user\[\s*["\']tenant_id["\']\s*\]\s*\n', '\n', content)
    # Remove lines like: user_id = current_user.get("user_id")  (but NOT message fields)
    content = re.sub(r'\s*user_id\s*=\s*current_user\.get\(\s*["\']user_id["\']\s*\)\s*\n', '\n', content)
    content = re.sub(r'\s*user_id\s*=\s*current_user\[\s*["\']user_id["\']\s*\]\s*\n', '\n', content)

    # ============================================================
    # 3. Remove tenant_id from SQLAlchemy ORM queries
    # ============================================================
    # Patterns like: XianyuAccount.tenant_id == tenant_id  (with optional trailing comma)
    # These appear inside .where() calls, often as one of multiple conditions
    content = _remove_tenant_id_orm_conditions(content)

    # Remove tenant_id from raw SQL queries: "AND tenant_id = :tenant_id" or "WHERE tenant_id = :tenant_id"
    content = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tenant_id', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tid', '', content, flags=re.IGNORECASE)
    # "WHERE tenant_id = :tenant_id AND ..." -> "WHERE ..."
    content = re.sub(r'WHERE\s+tenant_id\s*=\s*:tenant_id\s+AND\s+', 'WHERE ', content, flags=re.IGNORECASE)
    content = re.sub(r'WHERE\s+tenant_id\s*=\s*:tid\s+AND\s+', 'WHERE ', content, flags=re.IGNORECASE)
    # "WHERE tenant_id = :tenant_id" at end -> remove WHERE clause entirely (tricky; leave for manual)
    # "WHERE tenant_id = :tenant_id\n" -> "\n" (removes the WHERE)
    content = re.sub(r'WHERE\s+tenant_id\s*=\s*:tenant_id\s*\n', '\n', content, flags=re.IGNORECASE)
    content = re.sub(r'WHERE\s+tenant_id\s*=\s*:tid\s*\n', '\n', content, flags=re.IGNORECASE)

    # ============================================================
    # 4. Remove tenant_id from params dicts
    # ============================================================
    # "tenant_id": tenant_id  (in dict literals)
    content = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', content)
    content = re.sub(r"\s*'tenant_id':\s*tenant_id,?\s*\n", '\n', content)
    # "tid": tenant_id
    content = re.sub(r'\s*"tid":\s*tenant_id,?\s*\n', '\n', content)
    # "tenant_id": tenant_id (with trailing comma on same line, in single-line dicts)
    content = re.sub(r',\s*"tenant_id":\s*tenant_id', '', content)
    content = re.sub(r'"tenant_id":\s*tenant_id,\s*', '', content)

    # ============================================================
    # 5. Remove tenant_id=tenant_id from constructor calls / function args
    # ============================================================
    # XianyuAccount(tenant_id=tenant_id, ...) -> XianyuAccount(...)
    content = re.sub(r'tenant_id\s*=\s*tenant_id,\s*', '', content)
    content = re.sub(r',\s*tenant_id\s*=\s*tenant_id', '', content)
    content = re.sub(r'tenant_id\s*=\s*tenant_id', '', content)
    # tenant_id=tenant_id in function calls
    content = re.sub(r',\s*tenant_id\s*=\s*tenant_id\b', '', content)

    # ============================================================
    # 6. Remove user_id from current_user context in constructors
    # ============================================================
    # XianyuAccount(..., user_id=current_user.get("user_id"), ...) -> remove user_id arg
    content = re.sub(r'\s*user_id\s*=\s*current_user\.get\(\s*["\']user_id["\']\s*\),?\s*\n', '\n', content)
    content = re.sub(r',\s*user_id\s*=\s*current_user\.get\(\s*["\']user_id["\']\s*\)', '', content)
    content = re.sub(r'user_id\s*=\s*current_user\.get\(\s*["\']user_id["\']\s*\),\s*', '', content)
    # user_id=current_user["user_id"]
    content = re.sub(r'\s*user_id\s*=\s*current_user\[\s*["\']user_id["\']\s*\],?\s*\n', '\n', content)
    content = re.sub(r',\s*user_id\s*=\s*current_user\[\s*["\']user_id["\']\s*\]', '', content)

    # ============================================================
    # 7. Remove user_id WHERE conditions on models (NOT message fields)
    # ============================================================
    # XianyuAccount.user_id == user_id  (but NOT sender_user_id, receiver_user_id, from_user_id, to_user_id)
    # Only match Model.user_id where Model is not a message model
    content = _remove_user_id_orm_conditions(content)

    # ============================================================
    # 8. Remove the user_id filter block (the or_ block in account.py)
    # ============================================================
    # Pattern:
    #   if user_id:
    #       from sqlalchemy import or_
    #       query = query.where(
    #           or_(
    #               XianyuAccount.user_id == user_id,
    #               XianyuAccount.user_id.is_(None),
    #           )
    #       )
    content = re.sub(
        r'\s*if user_id:\s*\n\s*from sqlalchemy import or_\s*\n\s*query\s*=\s*query\.where\(\s*\n?\s*or_\(\s*\n\s*XianyuAccount\.user_id\s*==\s*user_id,\s*\n\s*XianyuAccount\.user_id\.is_\(None\),\s*\n\s*\)\s*\n?\s*\)\s*\n',
        '\n',
        content,
    )

    # ============================================================
    # 9. Clean up empty try blocks / leftover blank lines
    # ============================================================
    # Remove "tenant_id = int(body.get("tenantId"))" type lines (internal API passthrough)
    # These are in internal.py - we'll handle internal.py specially

    return content


def _automation_runtime_replacement(match: str) -> str:
    """Replace automation_runtime import with a no-op fallback for update_ws_heartbeat."""
    return (
        '\n# automation_runtime 模块未移植（工作流执行器）；update_ws_heartbeat 降级为 no-op\n'
        'async def update_ws_heartbeat(*args, **kwargs):\n'
        '    """No-op stub: 原本由 automation_runtime 提供，单租户精简版未移植该模块。"""\n'
        '    return None\n'
    )


def _remove_tenant_id_orm_conditions(content: str) -> str:
    """Remove XianyuAccount.tenant_id == tenant_id style conditions from .where() calls."""
    lines = content.split('\n')
    out = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are pure tenant_id ORM conditions (with optional trailing comma)
        # Match: XianyuAccount.tenant_id == tenant_id,
        # Match: XianyuAccountAuth.tenant_id == tenant_id,
        # etc.
        if re.match(r'^\w+\.tenant_id\s*==\s*tenant_id,?\s*$', stripped):
            # Skip this line entirely
            continue
        # Handle inline conditions like: .where(XianyuAccount.tenant_id == tenant_id)
        # -> .where()  (we'll clean up empty where later)
        line = re.sub(r'\.where\(\s*\w+\.tenant_id\s*==\s*tenant_id\s*\)', '', line)
        # Handle: .where(Model.id == x, Model.tenant_id == tenant_id, Model.deleted == 0)
        # -> .where(Model.id == x, Model.deleted == 0)
        line = re.sub(r'\.where\((.*?),\s*\w+\.tenant_id\s*==\s*tenant_id(.*?)\)',
                      lambda m: f'.where({m.group(1)}{m.group(2)})' if m.group(1).strip() else '.where()',
                      line)
        line = re.sub(r'\.where\(\w+\.tenant_id\s*==\s*tenant_id,\s*(.*?)\)',
                      lambda m: f'.where({m.group(1)})' if m.group(1).strip() else '.where()',
                      line)
        # Handle: (XianyuAccountAuth.tenant_id == XianyuAccount.tenant_id) - JOIN conditions
        # These reference model.tenant_id (column) not the variable; we need to remove the JOIN ON tenant_id
        # But this is complex - leave for manual handling
        out.append(line)
    # Clean up empty .where() calls
    result = '\n'.join(out)
    result = re.sub(r'\.where\(\s*\)', '', result)
    return result


def _remove_user_id_orm_conditions(content: str) -> str:
    """Remove XianyuAccount.user_id == user_id style conditions (NOT message fields)."""
    lines = content.split('\n')
    out = []
    for line in lines:
        stripped = line.strip()
        # Match: XianyuAccount.user_id == user_id,  (NOT sender_user_id etc.)
        # Only match when the attribute is exactly "user_id" (not sender_user_id)
        if re.match(r'^\w+\.user_id\s*==\s*user_id,?\s*$', stripped):
            continue
        # Handle: .where(XianyuAccount.user_id == user_id)
        line = re.sub(r'\.where\(\s*\w+\.user_id\s*==\s*user_id\s*\)', '', line)
        out.append(line)
    result = '\n'.join(out)
    result = re.sub(r'\.where\(\s*\)', '', result)
    return result


def main():
    print("=== Phase 2: Generic transformations ===")
    for fname in ROUTE_FILES:
        fpath = os.path.join(TARGET_ROUTES_DIR, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP (not found): {fname}")
            continue
        with open(fpath, 'r', encoding='utf-8') as f:
            original = f.read()
        transformed = transform_content(original, fname)
        if transformed != original:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(transformed)
            # Count remaining tenant_id references for reporting
            remaining = transformed.count('tenant_id')
            print(f"  OK: {fname} (remaining tenant_id refs: {remaining})")
        else:
            print(f"  NO CHANGE: {fname}")
    print("\n=== Phase 2 complete ===")


if __name__ == "__main__":
    main()
