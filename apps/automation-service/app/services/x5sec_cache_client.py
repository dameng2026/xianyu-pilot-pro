"""x5sec Redis 缓存客户端（Python 版）

与 crawler-service 的 x5secCache.ts 完全对齐，供 automation-service 在 WS Token
获取时直接从 Redis 读取缓存的 x5sec 并注入 cookie，跳过滑块求解流程。

缓存策略（与 crawler-service 一致）：
- Key: x5sec:{unb}            （从 cookie 的 unb 字段提取用户 ID）
- Fallback Key: x5sec:tk:{md5(_m_h5_tk_token)[:16]}
- TTL: 6 小时（由 crawler-service 写入时设置）

连接失败时静默降级（返回 None），不影响主流程。
"""
import hashlib
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

X5SEC_KEY_PREFIX = "x5sec:"
X5SEC_TK_KEY_PREFIX = "x5sec:tk:"

# 模块级 Redis 连接（懒加载，同步连接）
_redis_client = None
_redis_connect_attempted = False


def _get_redis_client():
    """获取 Redis 连接（懒加载，同步）。失败返回 None。"""
    global _redis_client, _redis_connect_attempted
    if _redis_client is not None:
        return _redis_client
    if _redis_connect_attempted:
        return None
    _redis_connect_attempted = True

    try:
        import redis as _redis_module

        host = (
            os.environ.get("X5SEC_REDIS_HOST")
            or os.environ.get("REDIS_HOST")
            or "xianyu-crawler-redis"
        )
        port = int(os.environ.get("X5SEC_REDIS_PORT") or os.environ.get("REDIS_PORT") or "6379")
        password = (
            os.environ.get("X5SEC_REDIS_PASSWORD")
            or os.environ.get("REDIS_PASSWORD")
        )

        _redis_client = _redis_module.Redis(
            host=host,
            port=port,
            password=password,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=False,
            decode_responses=True,
        )
        _redis_client.ping()
        logger.info("x5sec Redis 连接成功 host=%s port=%d", host, port)
        return _redis_client
    except Exception as e:
        logger.warning("x5sec Redis 连接失败（降级为无缓存）: %s", e)
        _redis_client = None
        return None


def _extract_cache_keys(cookie_str: str) -> dict:
    """从 cookie 字符串提取缓存 key。与 x5secCache.ts 的 extractCacheKeys 对齐。"""
    if not cookie_str:
        return {}

    result: dict = {}

    # 提取 unb（用户 ID）
    unb_match = re.search(r"(?:^|;\s*)unb=([^;]+)", cookie_str)
    if unb_match and unb_match.group(1):
        result["user_id"] = unb_match.group(1).strip()

    # 提取 _m_h5_tk（MTOP token），取 token 部分做 md5 hash 前 16 位
    tk_match = re.search(r"(?:^|;\s*)_m_h5_tk=([^;]+)", cookie_str)
    if tk_match and tk_match.group(1):
        tk = tk_match.group(1).strip()
        # _m_h5_tk 格式: {timestamp}_{token}，取 token 部分（与 TS 版一致）
        tk_part = "_".join(tk.split("_")[1:]) if "_" in tk else tk
        result["tk_key"] = hashlib.md5(tk_part.encode("utf-8")).hexdigest()[:16]

    return result


def get_cached_x5sec(cookie_str: str) -> Optional[str]:
    """从 Redis 读取缓存的 x5sec。与 x5secCache.ts 的 getCachedX5sec 对齐。"""
    if not cookie_str:
        return None

    redis_client = _get_redis_client()
    if redis_client is None:
        return None

    keys = _extract_cache_keys(cookie_str)
    cache_keys: list = []
    if keys.get("user_id"):
        cache_keys.append(f"{X5SEC_KEY_PREFIX}{keys['user_id']}")
    if keys.get("tk_key"):
        cache_keys.append(f"{X5SEC_TK_KEY_PREFIX}{keys['tk_key']}")

    if not cache_keys:
        return None

    try:
        for key in cache_keys:
            value = redis_client.get(key)
            if value:
                logger.info(
                    "x5sec 缓存命中 key=%s... length=%d",
                    key[:20],
                    len(value),
                )
                return value
        return None
    except Exception as e:
        logger.warning("x5sec 缓存读取失败: %s", e)
        return None


def cookie_has_x5sec(cookie_str: str) -> bool:
    """检查 cookie 中是否已包含 x5sec。与 x5secCache.ts 的 cookieHasX5sec 对齐。"""
    if not cookie_str:
        return False
    match = re.search(r"(?:^|;\s*)x5sec=([^;\s]+)", cookie_str)
    return bool(match and match.group(1) and len(match.group(1)) > 5)


def inject_x5sec_into_cookie(cookie_str: str, x5sec: str) -> str:
    """将 x5sec 注入到 cookie 字符串中。与 x5secCache.ts 的 injectX5secIntoCookie 对齐。"""
    if not x5sec or not cookie_str:
        return cookie_str

    result = cookie_str

    # 替换或追加 x5sec
    if re.search(r"(?:^|;\s*)x5sec=[^;]+", result, re.IGNORECASE):
        result = re.sub(
            r"(?:^|;\s*)x5sec=[^;]+",
            f"; x5sec={x5sec}",
            result,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        result = f"{result}; x5sec={x5sec}"

    # 清除 x5secdata（punish 数据，有 x5sec 后不再需要）
    result = re.sub(r"(?:^|;\s*)x5secdata=[^;]*", "", result, flags=re.IGNORECASE)

    # 清理多余空格和分号
    result = re.sub(r";\s*;\s*", "; ", result)
    result = re.sub(r"^;\s*", "", result).strip()

    return result


def evict_cached_x5sec(cookie_str: str) -> None:
    """删除缓存的 x5sec（x5sec 失效后清除旧缓存）。与 x5secCache.ts 的 evictCachedX5sec 对齐。"""
    if not cookie_str:
        return

    redis_client = _get_redis_client()
    if redis_client is None:
        return

    keys = _extract_cache_keys(cookie_str)
    cache_keys: list = []
    if keys.get("user_id"):
        cache_keys.append(f"{X5SEC_KEY_PREFIX}{keys['user_id']}")
    if keys.get("tk_key"):
        cache_keys.append(f"{X5SEC_TK_KEY_PREFIX}{keys['tk_key']}")

    if not cache_keys:
        return

    try:
        for key in cache_keys:
            redis_client.delete(key)
        logger.info("x5sec 缓存已清除 keys=%d", len(cache_keys))
    except Exception as e:
        logger.warning("x5sec 缓存清除失败: %s", e)
