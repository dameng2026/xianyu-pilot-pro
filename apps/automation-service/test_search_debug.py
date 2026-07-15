"""Test the crawler-service search with a real Cookie from the database."""
import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from core.database import async_session
from sqlalchemy import text
from core.cookie_crypto import decrypt_cookie_if_needed


async def get_cookie_and_test():
    async with async_session() as db:
        # Get the first account with a valid cookie
        result = await db.execute(
            text("""
                SELECT a.id AS account_id, a.external_uid AS unb,
                       auth.encrypted_cookie AS encrypted_cookie
                FROM xianyu_account a
                JOIN xianyu_account_auth auth
                  ON auth.account_id = a.id AND auth.tenant_id = a.tenant_id
                WHERE a.deleted = 0
                  AND COALESCE(auth.deleted, 0) = 0
                  AND auth.encrypted_cookie IS NOT NULL
                  AND auth.encrypted_cookie != ''
                ORDER BY auth.updated_time DESC
                LIMIT 1
            """)
        )
        row = result.mappings().first()
        if not row:
            print("No account with cookie found in database")
            return

        account_id = row["account_id"]
        unb = row["unb"]
        encrypted_cookie = row["encrypted_cookie"]

        print(f"Found account: id={account_id}, unb={unb}")
        print(f"Encrypted cookie prefix: {encrypted_cookie[:20]}...")

        cookie_str = decrypt_cookie_if_needed(encrypted_cookie)
        print(f"Decrypted cookie length: {len(cookie_str)}")
        print(f"Cookie preview: {cookie_str[:80]}...")

        # Check if _m_h5_tk is present
        has_m_h5_tk = "_m_h5_tk=" in cookie_str
        print(f"Has _m_h5_tk: {has_m_h5_tk}")

        if not has_m_h5_tk:
            print("WARNING: Cookie is missing _m_h5_tk, search may fail")

        # Test the crawler-service directly
        import requests
        crawler_url = "http://localhost:3001/api/goofish/search"
        headers = {
            "X-Internal-Token": "dev-only-internal-api-token-change-me-32-chars",
            "X-Internal-Tenant-Id": "1",
        }
        params = {
            "q": "ddr4",
            "page": 1,
            "pageSize": 5,
            "cookie": cookie_str,
        }
        print(f"\nCalling crawler-service: {crawler_url}")
        print(f"Keyword: ddr4, page: 1, pageSize: 5")
        try:
            resp = requests.get(crawler_url, headers=headers, params=params, timeout=90)
            print(f"HTTP status: {resp.status_code}")
            data = resp.json()
            print(f"ok: {data.get('ok')}")
            print(f"total: {data.get('total')}")
            print(f"page: {data.get('page')}")
            print(f"pageSize: {data.get('pageSize')}")
            print(f"hasMore: {data.get('hasMore')}")
            items = data.get("items", [])
            print(f"items count: {len(items)}")
            for i, item in enumerate(items[:3]):
                print(f"\n--- Item {i+1} ---")
                print(f"  itemId: {item.get('itemId')}")
                print(f"  title: {(item.get('title') or '')[:60]}")
                print(f"  price: {item.get('price')}")
                print(f"  imageUrl: {(item.get('imageUrl') or '')[:60]}")
                print(f"  itemUrl: {(item.get('itemUrl') or '')[:60]}")
            if data.get("error"):
                print(f"\nError: {data.get('error')}")
        except Exception as e:
            print(f"Request failed: {e}")


if __name__ == "__main__":
    asyncio.run(get_cookie_and_test())
