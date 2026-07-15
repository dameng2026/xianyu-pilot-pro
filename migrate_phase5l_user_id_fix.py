"""
Phase 5l: 修复 user_id 提取行丢失问题
=====================================
迁移过程中 user_id = current_user.get("user_id") 行被误删，
但函数体内仍引用 user_id 变量，导致 NameError。

修复：
1. messages.py message_context: 添加 user_id = current_user.get("user_id")
2. messages.py online_conversations: 添加 user_id = current_user.get("user_id")
3. misc.py qrlogin_generate: 添加 user_id = current_user.get("user_id")
"""
from pathlib import Path

TARGET = Path(r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\api\v1\routes")


def fix_messages_py() -> None:
    """修复 messages.py 中两个函数的 user_id 提取行丢失"""
    p = TARGET / "messages.py"
    c = p.read_text(encoding="utf-8")

    before = c.count("user_id = current_user.get")

    # 修复 1: message_context 函数
    # 在 logger.info("message_context: ...") 之前添加 user_id 提取行
    old1 = '''        offset = req.get("offset", 0)
        logger.info("message_context: account_id=%s s_id=%s user_id=%s peer_user_id=%s",
                     account_id, s_id, user_id, peer_user_id)'''
    new1 = '''        offset = req.get("offset", 0)
        user_id = current_user.get("user_id")
        logger.info("message_context: account_id=%s s_id=%s user_id=%s peer_user_id=%s",
                     account_id, s_id, user_id, peer_user_id)'''
    if old1 in c:
        c = c.replace(old1, new1)
        print("  [FIX] message_context: 添加 user_id = current_user.get('user_id')")
    else:
        print("  [WARN] message_context: 未找到目标代码块，可能已修复或代码已变化")

    # 修复 2: online_conversations 函数
    # 在 'if user_id == 0:' 之前添加 user_id 提取行
    # 注意：该函数签名后紧跟着 docstring，然后是 'if user_id == 0:'
    old2 = '''    """
    if user_id == 0:
        user_id = None
    logger.info(
        "online_conversations: xianyuAccountId=%s cursor=%s pageSize=%s limit=%s",
                     xianyu_account_id, cursor, page_size, limit,
    )'''
    new2 = '''    """
    user_id = current_user.get("user_id")
    if user_id == 0:
        user_id = None
    logger.info(
        "online_conversations: xianyuAccountId=%s cursor=%s pageSize=%s limit=%s",
                     xianyu_account_id, cursor, page_size, limit,
    )'''
    if old2 in c:
        c = c.replace(old2, new2)
        print("  [FIX] online_conversations: 添加 user_id = current_user.get('user_id')")
    else:
        print("  [WARN] online_conversations: 未找到目标代码块，可能已修复或代码已变化")

    after = c.count("user_id = current_user.get")
    p.write_text(c, encoding="utf-8")
    print(f"  [INFO] user_id 提取行数量: {before} -> {after}")


def fix_misc_py() -> None:
    """修复 misc.py qrlogin_generate 函数的 user_id 提取行丢失"""
    p = TARGET / "misc.py"
    c = p.read_text(encoding="utf-8")

    before = c.count("user_id = current_user.get")

    # 在 'result = generate_qrcode(user_id=user_id)' 之前添加 user_id 提取行
    old = '''    try:
        result = generate_qrcode(user_id=user_id)'''
    new = '''    try:
        user_id = current_user.get("user_id")
        result = generate_qrcode(user_id=user_id)'''
    if old in c:
        c = c.replace(old, new)
        print("  [FIX] qrlogin_generate: 添加 user_id = current_user.get('user_id')")
    else:
        print("  [WARN] qrlogin_generate: 未找到目标代码块，可能已修复或代码已变化")

    after = c.count("user_id = current_user.get")
    p.write_text(c, encoding="utf-8")
    print(f"  [INFO] user_id 提取行数量: {before} -> {after}")


def main() -> None:
    print("=" * 70)
    print("Phase 5l: 修复 user_id 提取行丢失问题")
    print("=" * 70)
    print("[messages.py]")
    fix_messages_py()
    print()
    print("[misc.py]")
    fix_misc_py()
    print()
    print("=" * 70)
    print("完成。所有 user_id 引用现在都有对应的提取行。")
    print("=" * 70)


if __name__ == "__main__":
    main()
