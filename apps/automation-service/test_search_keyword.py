"""测试搜索 API 是否正常工作（用真实关键词）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx
from app.core.database import async_session
from sqlalchemy import select
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

    internal_token = "dev-only-internal-api-token-change-me-32-chars"
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": internal_token,
        "X-Internal-Tenant-Id": "1",
    }

    # 用真实关键词搜索
    keyword = "iPhone"
    print(f"搜索关键词: {keyword}")
    async with httpx.AsyncClient(timeout=180.0, trust_env=False) as client:
        resp = await client.post(
            "http://localhost:3001/api/goofish/search",
            headers=headers,
            json={"q": keyword, "page": 1, "pageSize": 5, "cookie": cookie_str},
        )
        print(f"HTTP 状态: {resp.status_code}")
        print(f"原始响应: {resp.text[:2000]}")
        data = resp.json()
        print(f"ok: {data.get('ok')}")
        items = data.get("items", [])
        print(f"搜索结果数: {len(items)}")
        if data.get("error"):
            print(f"error: {data.get('error')}")
        if data.get("errorType"):
            print(f"errorType: {data.get('errorType')}")
        for i, item in enumerate(items[:5]):
            print(f"  [{i}] itemId={item.get('itemId')} title={item.get('title', '')[:40]} imageUrl={item.get('imageUrl', '')[:60]}")


if __name__ == "__main__":
    asyncio.run(main())
