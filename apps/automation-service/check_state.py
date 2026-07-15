"""检查数据库和服务状态。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import async_session
from sqlalchemy import text


async def main():
    async with async_session() as db:
        # 查看表结构
        r = await db.execute(text("DESCRIBE xianyu_conversation"))
        print("xianyu_conversation 表结构:")
        for row in r.fetchall():
            print(f"  {row[0]} ({row[1]})")

        print()
        r = await db.execute(text("DESCRIBE xianyu_chat_message"))
        print("xianyu_chat_message 表结构:")
        for row in r.fetchall():
            print(f"  {row[0]} ({row[1]})")


if __name__ == "__main__":
    asyncio.run(main())
