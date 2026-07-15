"""测试通过搜索 API 查找商品（搜索 API 不受 Baxia 限制）。"""
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
            ORDER BY last_message_time DESC LIMIT 3
        """))
        goods_ids = [str(row[0]) for row in r.fetchall()]

    internal_token = "dev-only-internal-api-token-change-me-32-chars"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
        "X-Internal-Tenant-Id": "1",
    }

    for goods_id in goods_ids:
        print(f"\n=== 搜索商品 ID: {goods_id} ===")
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            resp = await client.post(
                "http://localhost:3001/api/goofish/search",
                headers=headers,
                json={"q": goods_id, "page": 1, "pageSize": 5, "cookie": cookie_str},
            )
            print(f"  HTTP 状态: {resp.status_code}")
            data = resp.json()
            print(f"  ok: {data.get('ok')}")
            items = data.get("items", [])
            print(f"  搜索结果数: {len(items)}")
            for i, item in enumerate(items[:3]):
                print(f"  [{i}] itemId={item.get('itemId')} title={item.get('title', '')[:30]} imageUrl={item.get('imageUrl', '')[:60]}")
                if str(item.get("itemId")) == goods_id:
                    print(f"  >>> 匹配成功！imageUrl={item.get('imageUrl')}")


if __name__ == "__main__":
    asyncio.run(main())
