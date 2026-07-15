"""调试 fetch_item_detail 函数 - 直接调用并打印返回结果。"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import async_session
from sqlalchemy import select, text
from app.models.entities import XianyuAccountAuth
from app.core.cookie_crypto import decrypt_cookie_if_needed
from app.services.xianyu_goods_sync import fetch_item_detail


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
        if not cookie_str:
            print("Cookie 解密失败")
            return

        # 获取前 5 个商品的 goods_id
        r = await db.execute(text("""
            SELECT id, peer_key, goods_id
            FROM xianyu_conversation
            WHERE deleted=0 AND goods_id IS NOT NULL AND goods_id != 0
            ORDER BY last_message_time DESC
            LIMIT 5
        """))
        goods_list = r.fetchall()

    print(f"\n测试 {len(goods_list)} 个商品:")
    for row in goods_list:
        conv_id = row[0]
        peer_key = row[1]
        goods_id = str(row[2])
        print(f"\n--- 商品 ID: {goods_id} (conv_id={conv_id} peer_key={peer_key}) ---")

        try:
            detail_data = await asyncio.to_thread(fetch_item_detail, cookie_str, goods_id)
            if not detail_data:
                print("  返回空")
                continue

            print(f"  顶层 keys: {list(detail_data.keys())[:20]}")

            # 检查各种可能的封面图字段
            item_do = detail_data.get("itemDO") or {}
            item = detail_data.get("item") or {}
            print(f"  itemDO keys: {list(item_do.keys())[:20] if isinstance(item_do, dict) else 'N/A'}")
            print(f"  item keys: {list(item.keys())[:20] if isinstance(item, dict) else 'N/A'}")

            # 尝试提取各种封面图字段
            cover_candidates = [
                ("itemDO.picUrl", item_do.get("picUrl") if isinstance(item_do, dict) else None),
                ("itemDO.coverPic", item_do.get("coverPic") if isinstance(item_do, dict) else None),
                ("itemDO.imageUrl", item_do.get("imageUrl") if isinstance(item_do, dict) else None),
                ("item.picUrl", item.get("picUrl") if isinstance(item, dict) else None),
                ("item.coverPic", item.get("coverPic") if isinstance(item, dict) else None),
                ("top.picUrl", detail_data.get("picUrl")),
                ("top.coverPic", detail_data.get("coverPic")),
                ("top.imageUrl", detail_data.get("imageUrl")),
            ]
            image_urls = item_do.get("imageUrls") if isinstance(item_do, dict) else None
            if image_urls:
                cover_candidates.append(("itemDO.imageUrls[0]", image_urls[0] if isinstance(image_urls, list) and image_urls else None))

            print("  封面图候选字段:")
            for name, val in cover_candidates:
                if val:
                    print(f"    {name}: {str(val)[:100]}")

            # 打印完整数据结构的前 500 字符
            try:
                full_str = json.dumps(detail_data, ensure_ascii=False, default=str)
                print(f"  完整数据前 500 字符:\n{full_str[:500]}")
            except Exception as e:
                print(f"  序列化失败: {e}")

        except Exception as exc:
            print(f"  调用失败: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
