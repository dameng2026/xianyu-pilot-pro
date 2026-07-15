"""带 Cookie 测试 crawler-service 搜索速度。"""
import asyncio
import sys
import os
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import async_session
from app.services.xianyu_goods_sync import _resolve_account_cookie


async def get_cookie():
    async with async_session() as db:
        cookie_str, err = await _resolve_account_cookie(db, tenant_id=1, account_id=1, current_user={})
        if err:
            print(f"[FAIL] {err}")
            return None
        return cookie_str


def call_crawler(keyword, cookie, page=1, page_size=5):
    params = urllib.parse.urlencode({
        "q": keyword,
        "page": page,
        "pageSize": page_size,
        "cookie": cookie,
    })
    url = f"http://localhost:3001/api/goofish/search?{params}"
    req = urllib.request.Request(url, headers={
        "X-Internal-Token": "dev-only-internal-api-token-change-me-32-chars",
        "X-Internal-Tenant-Id": "1",
    })
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    elapsed = time.time() - t0
    return body, elapsed


async def main():
    cookie = await get_cookie()
    if not cookie:
        return
    print(f"[OK] Cookie len={len(cookie)}")

    for i in range(3):
        body, elapsed = call_crawler("ddr4", cookie)
        import json
        data = json.loads(body)
        items = data.get("items", [])
        print(f"  第{i+1}次: 耗时 {elapsed:.2f}s, 商品数={len(items)}, ok={data.get('ok')}")
        if items:
            it = items[0]
            print(f"    首个: title={it.get('title','')[:30]} price={it.get('price')} itemId={it.get('itemId')}")


if __name__ == "__main__":
    asyncio.run(main())
