"""测试单个商品 - 查看调试输出。"""
import asyncio
import sys
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

    async with async_session() as db:
        result = await db.execute(
            select(XianyuAccountAuth).where(
                XianyuAccountAuth.account_id == account_id,
                XianyuAccountAuth.tenant_id == tenant_id,
                XianyuAccountAuth.deleted == 0,
            )
        )
        auth = result.scalar_one_or_none()
        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)

        r = await db.execute(text("""
            SELECT goods_id FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
            ORDER BY last_message_time DESC LIMIT 1
        """))
        goods_id = str(r.scalar())

    print(f"测试商品 ID: {goods_id}")
    internal_token = "dev-only-internal-api-token-change-me-32-chars"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
        "X-Internal-Tenant-Id": "1",
    }

    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        resp = await client.post(
            "http://localhost:3001/api/goofish/item-detail",
            headers=headers,
            json={"itemId": goods_id, "cookie": cookie_str},
        )
        print(f"HTTP 状态: {resp.status_code}")
        data = resp.json()
        print(f"ok: {data.get('ok')}")
        detail = data.get("detail") or {}
        print(f"itemId: {detail.get('itemId')}")
        print(f"title: {detail.get('title')}")
        print(f"picUrl: {detail.get('picUrl')}")
        print(f"price: {detail.get('price')}")


if __name__ == "__main__":
    asyncio.run(main())
