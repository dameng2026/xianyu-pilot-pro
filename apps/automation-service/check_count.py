"""Quick check of message and conversation counts."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.core.database import async_session


async def main():
    async with async_session() as db:
        r = await db.execute(text("SELECT COUNT(*) FROM xianyu_chat_message WHERE account_id=1 AND deleted=0"))
        print(f"Messages: {r.scalar()}")
        r = await db.execute(text("SELECT COUNT(*) FROM xianyu_conversation WHERE account_id=1 AND deleted=0"))
        print(f"Conversations: {r.scalar()}")


asyncio.run(main())
