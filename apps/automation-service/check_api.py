"""Check content_type=8 messages and test the online conversations API."""
import asyncio
import sys
import os
import json
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.core.database import async_session


async def check_db():
    async with async_session() as db:
        # Check content_type=8 messages
        print("=== content_type=8 (product card) messages ===")
        rows = await db.execute(text("""
            SELECT id, s_id, content_type, msg_content, xy_goods_id, message_time
            FROM xianyu_chat_message
            WHERE account_id = 1 AND deleted = 0 AND content_type = 8
            ORDER BY message_time DESC LIMIT 10
        """))
        ct8_rows = rows.mappings().all()
        print(f"Total content_type=8 messages: {len(ct8_rows)}")
        for r in ct8_rows[:5]:
            content_preview = str(r['msg_content'] or '')[:200]
            print(f"  id={r['id']} s_id={r['s_id']} goods={r['xy_goods_id']} content={content_preview}")

        # Check all content_types
        print("\n=== Content type distribution ===")
        rows = await db.execute(text("""
            SELECT content_type, COUNT(*) as cnt
            FROM xianyu_chat_message
            WHERE account_id = 1 AND deleted = 0
            GROUP BY content_type
            ORDER BY cnt DESC
        """))
        for r in rows.mappings().all():
            print(f"  content_type={r['content_type']}: {r['cnt']} messages")

        # Check full content of a content_type=8 message for image data
        print("\n=== Full content_type=8 message (checking for image URLs) ===")
        rows = await db.execute(text("""
            SELECT id, s_id, msg_content, xy_goods_id, reminder_url, reminder_content
            FROM xianyu_chat_message
            WHERE account_id = 1 AND deleted = 0 AND content_type = 8
            ORDER BY message_time DESC LIMIT 3
        """))
        for r in rows.mappings().all():
            print(f"  id={r['id']} s_id={r['s_id']} goods={r['xy_goods_id']}")
            print(f"    msg_content: {str(r['msg_content'] or '')[:300]}")
            print(f"    reminder_url: {r['reminder_url']}")
            print(f"    reminder_content: {str(r['reminder_content'] or '')[:200]}")

        # Check reminder_content for goods title extraction
        print("\n=== reminder_content samples (for goods title) ===")
        rows = await db.execute(text("""
            SELECT DISTINCT s_id, xy_goods_id, reminder_content
            FROM xianyu_chat_message
            WHERE account_id = 1 AND deleted = 0
              AND xy_goods_id IS NOT NULL AND xy_goods_id != ''
              AND reminder_content IS NOT NULL AND reminder_content != ''
            ORDER BY message_time DESC LIMIT 10
        """))
        for r in rows:
            print(f"  s_id={r['s_id']} goods={r['xy_goods_id']} reminder={str(r['reminder_content'] or '')[:80]}")


def test_api():
    """Test the online conversations API endpoint."""
    print("\n=== Testing API: /api/v1/messages/online-conversations ===")
    try:
        url = "http://localhost:12401/api/v1/messages/online-conversations?account_id=1&limit=5"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"Response code: {data.get('code')}")
            conversations = data.get('data', {}).get('conversations', [])
            print(f"Conversations returned: {len(conversations)}")
            for c in conversations[:5]:
                print(f"  sid={c.get('sid')} name={c.get('peerUserName')} "
                      f"avatar={'YES' if c.get('buyerAvatar') else 'NO'} "
                      f"goodsId={c.get('goodsId')} "
                      f"title={c.get('goodsTitle', '')[:30]} "
                      f"cover={'YES' if c.get('goodsCoverPic') else 'NO'}")
    except Exception as e:
        print(f"API test failed: {e}")


async def main():
    await check_db()
    test_api()


asyncio.run(main())
