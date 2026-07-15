"""检查未匹配商品的标题，分析为什么没匹配到。"""
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

        # 获取所有没有封面图但有 goods_id 的商品
        r = await db.execute(text("""
            SELECT goods_id, goods_title
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
              AND (goods_cover_pic IS NULL OR goods_cover_pic = '')
              AND goods_title IS NOT NULL AND goods_title != ''
            ORDER BY last_message_time DESC
            LIMIT 10
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
        # 使用完整标题作为关键词（最多 30 字符）
        keyword = (title or "")[:30].strip()
        print(f"\n=== goods_id={goods_id} ===")
        print(f"  title={title}")
        print(f"  keyword={keyword}")
        try:
            async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                resp = await client.post(
                    "http://localhost:3001/api/goofish/search",
                    headers=headers,
                    json={"q": keyword, "page": 1, "pageSize": 10, "cookie": cookie_str},
                )
                data = resp.json()
            results = data.get("items", [])
            print(f"  搜索结果数: {len(results)}")
            # 检查每个结果
            match_found = False
            for i, item in enumerate(results[:5]):
                item_id = str(item.get("itemId") or "")
                item_title = item.get("title", "")
                image_url = item.get("imageUrl", "")
                match = " <<< EXACT MATCH!" if item_id == goods_id else ""
                # 检查 title 是否包含 goods_id 对应的 title
                title_contains = ""
                if title and item_title and title in item_title:
                    title_contains = " [TITLE CONTAINS]"
                if not match_found and (match or title_contains):
                    match_found = True
                print(f"  [{i}] itemId={item_id} title={item_title[:40]}")
                print(f"      imageUrl={image_url[:60]}{match}{title_contains}")
        except Exception as exc:
            print(f"  搜索失败: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
