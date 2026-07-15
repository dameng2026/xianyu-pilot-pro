"""详细测试 _fetch_goods_covers_async 函数，打印每个商品的处理结果。"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# 设置日志级别为 DEBUG
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from app.core.database import async_session
from sqlalchemy import select, text
from app.models.entities import XianyuAccountAuth
from app.core.cookie_crypto import decrypt_cookie_if_needed
from app.core.config import settings


async def main():
    account_id = 1
    tenant_id = 1

    async with async_session() as db:
        # 获取所有没有封面图但有 goods_id 和 goods_title 的商品
        r = await db.execute(text("""
            SELECT id, peer_key, goods_id, goods_title, buyer_avatar, goods_cover_pic
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
              AND (goods_cover_pic IS NULL OR goods_cover_pic = '')
              AND goods_title IS NOT NULL AND goods_title != ''
            ORDER BY last_message_time DESC
            LIMIT 10
        """))
        rows = r.fetchall()

    if not rows:
        print("没有需要拉取封面图的会话")
        return

    print(f"找到 {len(rows)} 个需要拉取封面图的会话")
    for row in rows:
        print(f"  id={row[0]} goods_id={row[2]} title={row[3][:30]}")

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
        cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)

    # 构造 conversations
    conversations = []
    for row in rows:
        peer_key = row[1] or ""
        sid = peer_key[4:] if peer_key.startswith("sid:") else peer_key
        conversations.append({
            "sid": sid,
            "goodsId": str(row[2]) if row[2] else "",
            "goodsCoverPic": row[5] or "",
        })

    # 直接调用搜索 API，模拟 _fetch_goods_covers_async 的逻辑
    crawler_base = (os.getenv("CRAWLER_SERVICE_URL") or "http://localhost:3001").rstrip("/")
    search_url = f"{crawler_base}/api/goofish/search"
    headers = {
        "X-Internal-Token": settings.effective_internal_api_token,
        "X-Internal-Tenant-Id": str(tenant_id),
    }

    semaphore = asyncio.Semaphore(2)
    cover_map = {}

    async def _search_one(goods_id: str, title: str) -> None:
        if not title:
            print(f"  [SKIP] goods_id={goods_id} 无标题")
            return
        keyword = title[:30].strip()
        if not keyword:
            print(f"  [SKIP] goods_id={goods_id} 关键词为空")
            return
        async with semaphore:
            try:
                async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
                    resp = await client.post(
                        search_url,
                        headers=headers,
                        json={"q": keyword, "page": 1, "pageSize": 10, "cookie": cookie_str},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                if not data.get("ok"):
                    print(f"  [FAIL] goods_id={goods_id} 搜索 API 返回失败: {data.get('error')}")
                    return
                items = data.get("items", [])
                print(f"  [SEARCH] goods_id={goods_id} keyword='{keyword}' results={len(items)}")
                # 优先精确匹配 itemId
                for item in items:
                    if str(item.get("itemId") or "") == goods_id:
                        image_url = item.get("imageUrl") or ""
                        if image_url:
                            print(f"  [MATCH-EXACT] goods_id={goods_id} imageUrl={image_url[:60]}")
                            cover_map[goods_id] = image_url
                            return
                # 兜底：title 包含匹配
                for item in items:
                    item_id = str(item.get("itemId") or "")
                    item_title = item.get("title") or ""
                    if not item_id or not item_title:
                        continue
                    if title and title in item_title:
                        image_url = item.get("imageUrl") or ""
                        if image_url:
                            print(f"  [MATCH-TITLE] goods_id={goods_id} itemId={item_id} title={item_title[:30]} imageUrl={image_url[:60]}")
                            cover_map[goods_id] = image_url
                            return
                print(f"  [NO-MATCH] goods_id={goods_id} 未找到匹配")
            except Exception as exc:
                print(f"  [ERROR] goods_id={goods_id} err={exc}")

    # 构造 goods_id -> title 映射
    goods_id_to_title = {str(row[2]): row[3] for row in rows}
    unique_goods_ids = list(goods_id_to_title.keys())[:10]

    print(f"\n开始搜索 {len(unique_goods_ids)} 个商品...")
    await asyncio.gather(*(_search_one(gid, goods_id_to_title.get(gid, "")) for gid in unique_goods_ids))

    print(f"\n搜索完成，匹配到 {len(cover_map)} 个封面图")
    for goods_id, cover_url in cover_map.items():
        print(f"  goods_id={goods_id} cover={cover_url[:80]}")


if __name__ == "__main__":
    asyncio.run(main())
