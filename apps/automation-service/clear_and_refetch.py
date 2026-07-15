"""Clear old messages and conversations for account 1, then trigger IM re-fetch."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.core.database import async_session


async def main():
    async with async_session() as db:
        # Soft-delete all messages for account 1
        result = await db.execute(text("""
            UPDATE xianyu_chat_message
            SET deleted = 1
            WHERE account_id = 1 AND deleted = 0
        """))
        print(f"Soft-deleted {result.rowcount} messages")

        # Soft-delete all conversations for account 1
        result = await db.execute(text("""
            UPDATE xianyu_conversation
            SET deleted = 1
            WHERE account_id = 1 AND deleted = 0
        """))
        print(f"Soft-deleted {result.rowcount} conversations")

        await db.commit()
        print("Done! Messages and conversations cleared.")

        # Verify
        rows = await db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM xianyu_chat_message WHERE account_id = 1 AND deleted = 0) AS active_msgs,
                (SELECT COUNT(*) FROM xianyu_conversation WHERE account_id = 1 AND deleted = 0) AS active_convs
        """))
        r = rows.first()
        print(f"Remaining active: messages={r[0]}, conversations={r[1]}")


asyncio.run(main())
