# -*- coding: utf-8 -*-
"""创建 app/core/redis_client.py - Redis 客户端 + 内存回退"""
import io
import os

TARGET_DIR = r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\core"
TARGET = os.path.join(TARGET_DIR, "redis_client.py")

CONTENT = '''# -*- coding: utf-8 -*-
"""
Redis 客户端（带内存回退）
=========================
- 使用 redis.asyncio 提供 async 客户端
- Redis 不可用时回退到内存 dict，系统仍能运行（单实例场景）
- 提供：get_redis、is_redis_available、redis_get、redis_set、redis_incr、redis_expire、redis_delete、redis_exists
"""
import asyncio
import logging
import time
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

# 延迟导入 redis.asyncio，缺失时降级
try:
    import redis.asyncio as aioredis  # type: ignore
    _REDIS_PKG_AVAILABLE = True
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore
    _REDIS_PKG_AVAILABLE = False
    logger.warning("redis 包未安装，所有 Redis 操作将回退到内存")

_redis_client = None
_redis_init_failed = False

# 内存回退存储：key -> {"value": ..., "expire": float|None}
_mem_store: dict = {}
_mem_lock = asyncio.Lock()


async def get_redis():
    """获取 Redis 客户端单例。Redis 不可用时返回 None。"""
    global _redis_client, _redis_init_failed
    if not _REDIS_PKG_AVAILABLE:
        return None
    if _redis_init_failed:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=0,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # 测试连接
        await _redis_client.ping()
        logger.info("Redis 连接成功 %s:%s", settings.redis_host, settings.redis_port)
        return _redis_client
    except Exception as e:
        logger.warning("Redis 连接失败，回退内存模式: %s", e)
        _redis_init_failed = True
        _redis_client = None
        return None


async def is_redis_available() -> bool:
    """Redis 是否可用（已连接）。"""
    return await get_redis() is not None


def _mem_cleanup():
    """清理内存中过期的项。"""
    now = time.time()
    expired = [k for k, v in _mem_store.items() if v.get("expire") is not None and v["expire"] <= now]
    for k in expired:
        _mem_store.pop(k, None)


async def redis_get(key: str) -> Optional[str]:
    """GET，返回字符串或 None。"""
    client = await get_redis()
    if client is not None:
        try:
            return await client.get(key)
        except Exception as e:
            logger.debug("redis_get 失败，回退内存: %s", e)
    async with _mem_lock:
        _mem_cleanup()
        item = _mem_store.get(key)
        return item["value"] if item else None


async def redis_set(key: str, value: str, ex: Optional[int] = None) -> bool:
    """SET，ex 为秒。"""
    client = await get_redis()
    if client is not None:
        try:
            await client.set(key, value, ex=ex)
            return True
        except Exception as e:
            logger.debug("redis_set 失败，回退内存: %s", e)
    async with _mem_lock:
        _mem_cleanup()
        _mem_store[key] = {
            "value": value,
            "expire": (time.time() + ex) if ex else None,
        }
        return True


async def redis_incr(key: str, expire: Optional[int] = None) -> int:
    """INCR，可选设置过期。返回递增后的值。"""
    client = await get_redis()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.incr(key)
            if expire is not None:
                pipe.expire(key, expire)
            results = await pipe.execute()
            return int(results[0])
        except Exception as e:
            logger.debug("redis_incr 失败，回退内存: %s", e)
    async with _mem_lock:
        _mem_cleanup()
        item = _mem_store.get(key)
        cur = int(item["value"]) if item else 0
        cur += 1
        _mem_store[key] = {
            "value": str(cur),
            "expire": (time.time() + expire) if expire else (item["expire"] if item else None),
        }
        return cur


async def redis_expire(key: str, seconds: int) -> bool:
    """EXPIRE。"""
    client = await get_redis()
    if client is not None:
        try:
            return bool(await client.expire(key, seconds))
        except Exception as e:
            logger.debug("redis_expire 失败，回退内存: %s", e)
    async with _mem_lock:
        _mem_cleanup()
        item = _mem_store.get(key)
        if item is None:
            return False
        item["expire"] = time.time() + seconds
        return True


async def redis_delete(key: str) -> int:
    """DEL，返回删除数量。"""
    client = await get_redis()
    if client is not None:
        try:
            return int(await client.delete(key))
        except Exception as e:
            logger.debug("redis_delete 失败，回退内存: %s", e)
    async with _mem_lock:
        return 1 if _mem_store.pop(key, None) is not None else 0


async def redis_exists(key: str) -> bool:
    """EXISTS。"""
    client = await get_redis()
    if client is not None:
        try:
            return bool(await client.exists(key))
        except Exception as e:
            logger.debug("redis_exists 失败，回退内存: %s", e)
    async with _mem_lock:
        _mem_cleanup()
        return key in _mem_store
'''

os.makedirs(TARGET_DIR, exist_ok=True)
with io.open(TARGET, "w", encoding="utf-8") as f:
    f.write(CONTENT)
print("redis_client.py created OK")
