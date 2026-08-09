from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from .config import settings

DATABASE_URL = settings.mysql_url

# 修复 SQLAlchemy 2.0.36 + aiomysql 0.3.0 的 pool_pre_ping 兼容问题：
# MySQLDialect_aiomysql.do_ping 在 _send_false_to_ping=False 时无参调用
# AsyncAdapt_aiomysql_connection.ping()，但该方法没有默认参数，抛 TypeError。
# 通过同步 patch 为 ping 补充 reconnect 默认参数，使 pre_ping 可用，
# 从而在 MySQL 静默断开空闲连接后 checkout 时自动检测并重建连接。
from sqlalchemy.dialects.mysql import aiomysql as _sa_aiomysql

_orig_aiomysql_ping = _sa_aiomysql.AsyncAdapt_aiomysql_connection.ping


def _patched_aiomysql_ping(self, reconnect=True):
    return _orig_aiomysql_ping(self, reconnect)


_sa_aiomysql.AsyncAdapt_aiomysql_connection.ping = _patched_aiomysql_ping

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    # MySQL 默认 wait_timeout=28800（8h），长连接被服务端静默断开后下次请求会拿到失效连接。
    # pool_pre_ping 在每次 checkout 时检测连接有效性，失效则自动重建（已通过
    # 上方 patch 修复 aiomysql 0.3.0 的兼容问题）。pool_recycle=3600 作为兜底。
    pool_pre_ping=True,
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