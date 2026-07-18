from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import settings

DATABASE_URL = settings.mysql_url

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    # MySQL 默认 wait_timeout=28800（8h），长连接被服务端静默断开后下次请求会拿到失效连接。
    # 注：pool_pre_ping 在 SQLAlchemy 2.0.x + aiomysql 0.3.0 组合下会触发
    # pymysql 方言的 do_ping 调用 AsyncAdapt_aiomysql_connection.ping()，
    # 但 aiomysql 0.3.0 的 ping() 要求 reconnect 参数，导致 TypeError。
    # 因此关闭 pool_pre_ping，改用 pool_recycle=3600（1h）主动回收连接，
    # 远小于 MySQL wait_timeout，足以避免失效连接。
    pool_pre_ping=False,
    pool_recycle=3600,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()