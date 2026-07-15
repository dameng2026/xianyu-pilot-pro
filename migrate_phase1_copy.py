"""
Phase 1: Copy all route/schema/service/data files from source to target.
Uses shutil.copy2 to preserve metadata and overwrite existing files.
"""
import shutil
import os

SOURCE_BASE = r"g:\源码\xianyu-assistant-package-temp\apps\automation-service\app"
TARGET_BASE = r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app"

# All route files to copy (direct copy + need modification - we'll modify in place after)
ROUTE_FILES = [
    "captcha.py", "feishu.py", "internal.py", "login.py", "restful.py", "sse.py",  # direct copy
    "account.py", "items.py", "order.py", "dashboard.py", "messages.py",
    "auto_delivery.py", "auto_reply.py", "kami.py", "quick_reply.py",
    "auto_reply_scope.py", "auto_category.py", "content_manage.py", "system.py", "misc.py",
]

# Schema files to copy
SCHEMA_FILES = ["account.py", "auth.py", "common.py", "dashboard.py", "order.py"]

# Service files to copy (direct + need modification)
SERVICE_FILES = [
    # direct copy
    "ws_protocol.py", "ws_token.py", "category_data.py", "ai_provider.py",
    "xianyu_qr_login.py", "feishu_bot.py", "feishu_chat.py",
    # need modification
    "ws_client.py", "ws_sse.py", "ws_startup.py", "ws_storage.py",
    "captcha_solver.py", "auto_category.py", "rag_service.py",
    # xianyu_goods_sync.py - special handling (remove search functions)
    "xianyu_goods_sync.py",
    # also copy these helper services that may be referenced
    "cookie_token_refresher.py", "ws_delivery_handler.py",
    "notify_dispatcher.py", "xianyu_api_service.py",
]

# Data files
DATA_FILES = ["categories.json"]


def copy_file(src_rel_path, dst_rel_path):
    src = os.path.join(SOURCE_BASE, src_rel_path.replace("/", os.sep))
    dst = os.path.join(TARGET_BASE, dst_rel_path.replace("/", os.sep))
    if not os.path.exists(src):
        print(f"  SKIP (not found): {src}")
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  OK: {src_rel_path} -> {dst_rel_path}")
    return True


def main():
    print("=== Phase 1: Copying files ===")

    print("\n--- Routes ---")
    for f in ROUTE_FILES:
        copy_file(f"api/v1/routes/{f}", f"api/v1/routes/{f}")

    print("\n--- Schemas ---")
    for f in SCHEMA_FILES:
        copy_file(f"schemas/{f}", f"schemas/{f}")

    print("\n--- Services ---")
    for f in SERVICE_FILES:
        copy_file(f"services/{f}", f"services/{f}")

    print("\n--- Data ---")
    for f in DATA_FILES:
        copy_file(f"data/{f}", f"data/{f}")

    print("\n=== Phase 1 complete ===")


if __name__ == "__main__":
    main()
