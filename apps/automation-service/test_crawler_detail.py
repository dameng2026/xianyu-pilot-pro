"""测试 crawler-service 的 /api/goofish/item-detail 端点。"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from app.core.database import async_session
from sqlalchemy import select, text
from app.models.entities import XianyuAccountAuth
from app.core.cookie_crypto import decrypt_cookie_if_needed


async def main():
    account_id = 1
    tenant_id = 1

    # 获取 Cookie
    async with async_session() as db:
        result = await db.execute(
            select(XianyuAccountAuth).where(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.deleted == 0,
            )
        )
        auth = result.scalar_one_or_none()
        if not auth or not auth.encrypted_cookie:
            print("账号未登录或无 Cookie")
            return

        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)
        print(f"Cookie 长度: {len(cookie_str) if cookie_str else 0}")

        # 获取 3 个商品的 goods_id
        r = await db.execute(text("""
            SELECT id, goods_id
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
            ORDER BY last_message_time DESC
            LIMIT 3
        """))
        goods_list = r.fetchall()

    # 内部 API 令牌（开发模式默认值）
    internal_token = "dev-only-internal-api-token-change-me-32-chars"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
        "X-Internal-Tenant-Id": "1",
    }

    print(f"\n测试 {len(goods_list)} 个商品:")
    for row in goods_list:
        goods_id = str(row[1])
        print(f"\n--- 商品 ID: {goods_id} ---")
        try:
            async with httpx.AsyncClient(timeout=45.0, trust_env=False) as client:
                resp = await client.post(
                    "http://localhost:3001/api/goofish/item-detail",
                    headers=headers,
                    json={"itemId": goods_id, "cookie": cookie_str},
                )
                print(f"  HTTP 状态: {resp.status_code}")
                data = resp.json()
                print(f"  ok: {data.get('ok')}")
                detail = data.get("detail") or {}
                print(f"  itemId: {detail.get('itemId')}")
                print(f"  title: {detail.get('title')}")
                print(f"  picUrl: {detail.get('picUrl')}")
                print(f"  price: {detail.get('price')}")
                if data.get("error"):
                    print(f"  error: {data.get('error')}")
        except Exception as exc:
            print(f"  调用失败: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
