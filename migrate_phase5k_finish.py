"""
Phase 5k: 最终修复脚本
=====================
修复剩余的 tenant_id 引用问题：
1. cookie_token_refresher.py: 移除 AccountRefreshState 构造中无效的 tenant_id=int(row["tenant_id"])
   (SQL 不再查询 tenant_id 列，且 dataclass 无 tenant_id 字段)
2. notify_dispatcher.py: 移除 dispatch_notification 中无效的 'if not tenant_id:' 校验
   (函数签名无 tenant_id 参数)
3. feishu_bot.py: 将 _load_feishu_app_config / get_tenant_access_token 的 tenant_id 参数
   改为默认值 1；将 send_text_message / upload_image / send_image_message 中调用
   get_tenant_access_token(tenant_id) 改为 get_tenant_access_token() (使用默认值)
4. feishu_chat.py: 移除 _fetch_qr_image_from_crawler 的 tenant_id 参数(函数体未使用)；
   将 _fetch_qr_image_from_crawler(tenant_id) 调用改为 _fetch_qr_image_from_crawler()；
   将 _load_feishu_app_config(tenant_id) 调用改为 _load_feishu_app_config(1)
"""
import re
from pathlib import Path

TARGET = Path(r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\services")


def fix_cookie_token_refresher() -> None:
    """移除 AccountRefreshState 构造中无效的 tenant_id=int(row["tenant_id"]) 行"""
    p = TARGET / "cookie_token_refresher.py"
    c = p.read_text(encoding="utf-8")
    before = c.count("tenant_id")
    # 移除 'tenant_id=int(row["tenant_id"]),' 行（含前后空白和换行）
    c = re.sub(
        r'\n\s*tenant_id=int\(row\["tenant_id"\]\),\n',
        '\n',
        c,
    )
    after = c.count("tenant_id")
    p.write_text(c, encoding="utf-8")
    print(f"[cookie_token_refresher.py] tenant_id refs: {before} -> {after}")


def fix_notify_dispatcher() -> None:
    """移除 dispatch_notification 中无效的 'if not tenant_id:' 校验"""
    p = TARGET / "notify_dispatcher.py"
    c = p.read_text(encoding="utf-8")
    before = c.count("tenant_id")
    # 精确匹配 'if not tenant_id:\n        return False\n' 块
    c = re.sub(
        r'\n\s*if not tenant_id:\s*\n\s*return False\s*\n',
        '\n',
        c,
    )
    after = c.count("tenant_id")
    p.write_text(c, encoding="utf-8")
    print(f"[notify_dispatcher.py] tenant_id refs: {before} -> {after}")


def fix_feishu_bot() -> None:
    """feishu_bot.py:
    - _load_feishu_app_config(tenant_id: int) -> (tenant_id: int = 1)
    - get_tenant_access_token(tenant_id: int) -> (tenant_id: int = 1)
    - send_text_message/upload_image/send_image_message 中的
      get_tenant_access_token(tenant_id) -> get_tenant_access_token()
    """
    p = TARGET / "feishu_bot.py"
    c = p.read_text(encoding="utf-8")
    before = c.count("tenant_id")

    # 1. 函数签名加默认值
    c = c.replace(
        "async def _load_feishu_app_config(tenant_id: int) -> Optional[dict]:",
        "async def _load_feishu_app_config(tenant_id: int = 1) -> Optional[dict]:",
    )
    c = c.replace(
        "async def get_tenant_access_token(tenant_id: int) -> Optional[str]:",
        "async def get_tenant_access_token(tenant_id: int = 1) -> Optional[str]:",
    )
    # 2. 调用处改用默认值（send_text_message/upload_image/send_image_message 内）
    # 这些函数自身没有 tenant_id 参数，原代码 'get_tenant_access_token(tenant_id)' 引用了未定义变量
    c = c.replace(
        "token = await get_tenant_access_token(tenant_id)",
        "token = await get_tenant_access_token()",
    )

    after = c.count("tenant_id")
    p.write_text(c, encoding="utf-8")
    print(f"[feishu_bot.py] tenant_id refs: {before} -> {after}")


def fix_feishu_chat() -> None:
    """feishu_chat.py:
    - _fetch_qr_image_from_crawler 移除 tenant_id 参数(函数体未使用)
    - _fetch_qr_image_from_crawler(tenant_id) -> _fetch_qr_image_from_crawler()
    - _load_feishu_app_config(tenant_id) -> _load_feishu_app_config(1)
    """
    p = TARGET / "feishu_chat.py"
    c = p.read_text(encoding="utf-8")
    before = c.count("tenant_id")

    # 1. 函数签名移除 tenant_id 参数
    c = c.replace(
        "async def _fetch_qr_image_from_crawler(tenant_id: int) -> Optional[bytes]:",
        "async def _fetch_qr_image_from_crawler() -> Optional[bytes]:",
    )
    # 2. 调用处移除 tenant_id 实参
    c = c.replace(
        "qr_image_bytes = await _fetch_qr_image_from_crawler(tenant_id)",
        "qr_image_bytes = await _fetch_qr_image_from_crawler()",
    )
    # 3. _load_feishu_app_config(tenant_id) -> _load_feishu_app_config(1)
    #    (该函数在 feishu_bot.py 中已改为默认值 1，这里显式传 1 以保持清晰)
    c = c.replace(
        "config = await _load_feishu_app_config(tenant_id)",
        "config = await _load_feishu_app_config(1)",
    )

    after = c.count("tenant_id")
    p.write_text(c, encoding="utf-8")
    print(f"[feishu_chat.py] tenant_id refs: {before} -> {after}")


def main() -> None:
    print("=" * 70)
    print("Phase 5k: 最终修复剩余 tenant_id 引用")
    print("=" * 70)
    fix_cookie_token_refresher()
    fix_notify_dispatcher()
    fix_feishu_bot()
    fix_feishu_chat()
    print("=" * 70)
    print("完成。剩余 tenant_id 引用应为：")
    print("  - feishu_bot.py: 仅函数签名默认值与缓存 key（合法 Feishu API 用法）")
    print("  - 其他文件: 0")
    print("=" * 70)


if __name__ == "__main__":
    main()
