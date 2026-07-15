"""测试用商品标题搜索，看是否能匹配到 itemId。"""
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

        # 获取 5 个商品及其标题
        r = await db.execute(text("""
            SELECT goods_id, LEFT(goods_title, 50) AS title
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
              AND goods_title IS NOT NULL AND goods_title != ''
            ORDER BY last_message_time DESC
            LIMIT 5
        """))
        items = r.fetchall()

    internal_token = "dev-only-internal-api-token-change-me-32-chars"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
        "X-Internal-Tenant-Id": "1",
    }

    for goods_id, title in items:
        goods_id = str(goods_id)
        keyword = title[:20].strip()
        print(f"\n=== goods_id={goods_id} keyword='{keyword}' ===")
        try:
            async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                resp = await client.post(
                    "http://localhost:3001/api/goofish/search",
                    headers=headers,
                    json={"q": keyword, "page": 1, "pageSize": 10, "cookie": cookie_str},
                )
                data = resp.json()
            items = data.get("items", [])
            print(f"  搜索结果数: {len(items)}")
            for i, item in enumerate(items[:5]):
                item_id = str(item.get("itemId") or "")
                match = " <<< MATCH!" if item_id == goods_id else ""
                print(f"  [{i}] itemId={item_id} title={item.get('title', '')[:30]} imageUrl={item.get('imageUrl', '')[:50]}{match}")
        except Exception as exc:
            print(f"  搜索失败: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
