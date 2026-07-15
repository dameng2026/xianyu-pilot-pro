"""测试 crawler-service 带Cookie搜索"""
import asyncio
import requests
from app.core.database import async_session
from sqlalchemy import select
from app.models.entities import XianyuAccountAuth
from app.core.cookie_crypto import decrypt_cookie_if_needed


async def get_cookie():
    async with async_session() as db:
        result = await db.execute(select(XianyuAccountAuth).where(XianyuAccountAuth.account_id == 1))
        auth = result.scalar_one_or_none()
        if auth:
            return decrypt_cookie_if_needed(auth.encrypted_cookie)
    return None


async def test():
    cookie = await get_cookie()
    if not cookie:
        print("No cookie found")
        return

    print(f"Cookie length: {len(cookie)}")

    resp = requests.get(
        "http://localhost:3001/api/goofish/search",
        headers={
            "X-Internal-Token": "dev-only-internal-api-token-change-me-32-chars",
            "X-Internal-Tenant-Id": "1",
        },
        params={
            "q": "ddr4",
            "page": 1,
            "pageSize": 5,
            "cookie": cookie,
        },
        timeout=90,
    )
    data = resp.json()
    ok = data.get("ok")
    items = data.get("items", [])
    total = data.get("total")
    error = data.get("error")

    print(f"ok: {ok}")
    print(f"items count: {len(items)}")
    print(f"total: {total}")
    if items:
        first = items[0]
        title = first.get("title", "")
        price = first.get("price", "")
        item_id = first.get("itemId", "")
        print(f"first item: title={title[:50]}, price={price}, itemId={item_id}")
    else:
        print(f"error: {error}")


asyncio.run(test())
