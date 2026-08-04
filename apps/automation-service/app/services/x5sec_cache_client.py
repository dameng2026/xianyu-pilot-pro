"""x5sec Redis 缓存客户端（Python 版）—— 方案 I x5sec 持久化强化

与 crawler-service 的 x5secCache.ts 完全对齐，供 automation-service 在 WS Token
获取时直接从 Redis 读取缓存的 x5sec 并注入 cookie，跳过滑块求解流程。

缓存策略（与 crawler-service 一致）：
- Key: x5sec:{unb}            （从 cookie 的 unb 字段提取用户 ID）
- Fallback Key: x5sec:tk:{md5(_m_h5_tk_token)[:16]}
- TTL: 24 小时（方案 I 优化：从 6 小时延长到 24 小时，x5sec 实际有效期可能更长）

2026-08-03 方案 I x5sec 持久化强化：
- Redis TTL 从 6 小时延长到 24 小时（减少重复求解频率）
- 新增本地文件兜底（Redis 失效时从本地文件读取，避免完全失效）
- 新增 x5sec 主动刷新机制（缓存接近过期时主动刷新，避免过期后触发滑块）

连接失败时静默降级（返回 None），不影响主流程。
"""
import hashlib
import json
import logging
import os
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

X5SEC_KEY_PREFIX = "x5sec:"
X5SEC_TK_KEY_PREFIX = "x5sec:tk:"

# 2026-08-03 方案 I：缓存写入 TTL 从 6 小时延长到 24 小时
# 原因：x5sec 实际有效期可能远超 6 小时（待研究方向 7.4 验证），延长 TTL 可：
# 1. 减少重复求解频率（从每 6 小时一次降到每 24 小时一次）
# 2. 在代理配额耗尽期间，已缓存的 x5sec 仍可复用，避免触发滑块
# 3. crawler-service 端 x5secCache.ts 也需同步延长到 24 小时
X5SEC_CACHE_TTL = 24 * 60 * 60  # 24 小时（秒）

# 方案 I：本地文件兜底路径（Redis 失效时从文件读取）
# 文件格式：{"unb": "x5sec_value", "tk_key": "x5sec_value", "updated_at": timestamp}
X5SEC_LOCAL_CACHE_DIR = os.environ.get("X5SEC_LOCAL_CACHE_DIR", "/tmp/x5sec_cache")
X5SEC_LOCAL_CACHE_TTL = 48 * 60 * 60  # 本地文件兜底 TTL：48 小时（比 Redis 长 2 倍）

# 方案 I：x5sec 主动刷新阈值（缓存剩余时间 < 此值时主动刷新）
# 默认 1 小时：缓存剩余 1 小时时，下次使用后主动触发刷新
X5SEC_REFRESH_THRESHOLD_SEC = 60 * 60  # 1 小时

# 模块级 Redis 连接（懒加载，同步连接）
_redis_client = None
_redis_connecting = False


def _get_redis_client():
    """获取 Redis 连接（懒加载，同步）。失败返回 None。

    2026-08-02 修复：移除 _redis_connect_attempted 永久标记，允许连接失败后重试。
    原因：与 x5secCache.ts 同样的问题，连接失败后永不重试，x5sec 缓存永久失效。
    """
    global _redis_client, _redis_connecting
    if _redis_client is not None:
        return _redis_client
    if _redis_connecting:
        return None  # 避免并发创建多个连接
    _redis_connecting = True

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
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            decode_responses=True,
        )
        _redis_client.ping()
        logger.info("x5sec Redis 连接成功 host=%s port=%d", host, port)
        return _redis_client
    except Exception as e:
        logger.warning("x5sec Redis 连接失败（降级为无缓存）: %s", e)
        _redis_client = None
        return None
    finally:
        _redis_connecting = False


# ============================================================
# 11.5.1-2：x5sec 缓存命中率监控（2026-08-04 实施）
# ============================================================
# 统计 key 前缀：x5sec:stat:*（Redis INCR 累计，永不过期，运维可通过
# GET /admin-api/x5sec-cache/stats 或 Redis 直接读取）
X5SEC_STAT_PREFIX = "x5sec:stat:"


def _incr_cache_stat(key: str) -> None:
    """累计缓存统计（Redis INCR）。失败静默忽略，不影响主流程。"""
    try:
        redis_client = _get_redis_client()
        if redis_client is not None:
            redis_client.incr(f"{X5SEC_STAT_PREFIX}{key}")
    except Exception:
        pass


def get_cache_stats() -> dict:
    """读取缓存命中率统计快照（供管理端/监控接口使用）。

    Returns:
        {request_total, hit_redis, hit_local, miss, hit_rate, write_total}
        任一指标缺失时为 0。
    """
    redis_client = _get_redis_client()
    stats = {
        "request_total": 0,
        "hit_redis": 0,
        "hit_local": 0,
        "miss": 0,
        "write_total": 0,
        "hit_rate": 0.0,
    }
    if redis_client is None:
        return stats
    try:
        for name in ("request_total", "hit_redis", "hit_local", "miss", "write_total"):
            val = redis_client.get(f"{X5SEC_STAT_PREFIX}{name}")
            if val:
                stats[name] = int(val)
        total_hits = stats["hit_redis"] + stats["hit_local"]
        total = stats["request_total"]
        stats["hit_rate"] = round(total_hits / total, 4) if total > 0 else 0.0
    except Exception as e:
        logger.warning("get_cache_stats: 统计读取失败: %s", e)
    return stats


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


def cache_x5sec(cookie_str: str, x5sec: str, ttl_seconds: int = X5SEC_CACHE_TTL) -> bool:
    """将 x5sec 缓存到 Redis。与 x5secCache.ts 的 cacheX5sec 对齐。

    2026-08-03 新增：此前 Python 端只有 get_cached_x5sec（读取）和 evict_cached_x5sec（清除），
    缺少缓存写入函数。导致 _try_silent_extract / _try_http_x5sec_extract 获取的 x5sec 无法缓存，
    每次 WS 掉线都需要重新获取，免滑块能力不足。

    同时写入 user-key 和 tk-key，提高命中率。
    任一 key 命中即可返回 x5sec，避免因 _m_h5_tk 刷新导致 tk-key 变化后缓存失效。

    2026-08-03 方案 I：同时写入本地文件兜底（Redis 失效时从文件读取）

    Args:
        cookie_str: Cookie 字符串（用于提取 user_id 和 tk_key）
        x5sec: x5sec 值
        ttl_seconds: 缓存 TTL（秒），默认 24 小时（方案 I）

    Returns:
        True 表示写入成功，False 表示失败（Redis 不可用或无有效 key）
    """
    if not x5sec or not cookie_str:
        return False

    keys = _extract_cache_keys(cookie_str)
    cache_keys: list = []
    if keys.get("user_id"):
        cache_keys.append(f"{X5SEC_KEY_PREFIX}{keys['user_id']}")
    if keys.get("tk_key"):
        cache_keys.append(f"{X5SEC_TK_KEY_PREFIX}{keys['tk_key']}")

    if not cache_keys:
        logger.warning("cache_x5sec: 无法从 cookie 提取用户标识，跳过缓存")
        return False

    redis_ok = False
    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            # 同时写入所有 key，确保任一 key 都能命中
            pipe = redis_client.pipeline()
            for key in cache_keys:
                pipe.set(key, x5sec, ex=ttl_seconds)
            pipe.execute()
            redis_ok = True
            logger.info(
                "cache_x5sec: 已缓存 x5sec 到 Redis (keys=%d, length=%d, TTL=%ds)",
                len(cache_keys), len(x5sec), ttl_seconds,
            )
        except Exception as e:
            logger.warning("cache_x5sec: Redis 缓存写入失败: %s", e)

    # 方案 I：同时写入本地文件兜底
    local_ok = _write_local_cache(keys, x5sec)
    if not redis_ok and not local_ok:
        return False
    # 2026-08-04 11.5.1-2：统计写入次数
    _incr_cache_stat("write_total")
    return True


def _write_local_cache(keys: dict, x5sec: str) -> bool:
    """方案 I：写入本地文件兜底缓存。

    Redis 失效时从本地文件读取，避免 x5sec 缓存完全失效。
    文件路径：{X5SEC_LOCAL_CACHE_DIR}/x5sec_{user_id}.json
    文件格式：{"user_id": "...", "tk_key": "...", "x5sec": "...", "updated_at": timestamp}

    Args:
        keys: _extract_cache_keys 返回的 keys dict
        x5sec: x5sec 值

    Returns:
        True 表示写入成功
    """
    if not x5sec or not keys.get("user_id"):
        return False

    try:
        os.makedirs(X5SEC_LOCAL_CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(X5SEC_LOCAL_CACHE_DIR, f"x5sec_{keys['user_id']}.json")
        cache_data = {
            "user_id": keys.get("user_id"),
            "tk_key": keys.get("tk_key"),
            "x5sec": x5sec,
            "updated_at": time.time(),
        }
        # 原子写入（先写临时文件再重命名）
        tmp_file = f"{cache_file}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)
        os.replace(tmp_file, cache_file)
        logger.info(
            "_write_local_cache: 已写入本地兜底缓存 user_id=%s length=%d",
            keys.get("user_id"), len(x5sec),
        )
        return True
    except Exception as e:
        logger.warning("_write_local_cache: 本地缓存写入失败: %s", e)
        return False


def _read_local_cache(cookie_str: str) -> Optional[str]:
    """方案 I：从本地文件读取兜底缓存。

    Redis 缓存未命中时，尝试从本地文件读取 x5sec。
    本地文件 TTL 比 Redis 长（48 小时 vs 24 小时），作为最后兜底。

    Args:
        cookie_str: Cookie 字符串（用于提取 user_id）

    Returns:
        x5sec 值，或 None（文件不存在/已过期/读取失败）
    """
    if not cookie_str:
        return None

    keys = _extract_cache_keys(cookie_str)
    user_id = keys.get("user_id")
    if not user_id:
        return None

    try:
        cache_file = os.path.join(X5SEC_LOCAL_CACHE_DIR, f"x5sec_{user_id}.json")
        if not os.path.exists(cache_file):
            return None

        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)

        # 检查 TTL
        updated_at = cache_data.get("updated_at", 0)
        age = time.time() - updated_at
        if age > X5SEC_LOCAL_CACHE_TTL:
            logger.info(
                "_read_local_cache: 本地缓存已过期 user_id=%s age=%.1fh TTL=%dh",
                user_id, age / 3600, X5SEC_LOCAL_CACHE_TTL / 3600,
            )
            return None

        x5sec = cache_data.get("x5sec")
        if x5sec and len(x5sec) > 5:
            logger.info(
                "_read_local_cache: 本地兜底缓存命中 user_id=%s length=%d age=%.1fh",
                user_id, len(x5sec), age / 3600,
            )
            return x5sec
        return None
    except Exception as e:
        logger.warning("_read_local_cache: 本地缓存读取失败: %s", e)
        return None


def get_x5sec_cache_ttl_remaining(cookie_str: str) -> int:
    """方案 I：获取 x5sec 缓存剩余 TTL（秒）。

    用于判断是否需要主动刷新：剩余 TTL < X5SEC_REFRESH_THRESHOLD_SEC 时触发刷新。

    Args:
        cookie_str: Cookie 字符串

    Returns:
        剩余 TTL 秒数，-1 表示无缓存或读取失败
    """
    if not cookie_str:
        return -1

    redis_client = _get_redis_client()
    if redis_client is None:
        return -1

    keys = _extract_cache_keys(cookie_str)
    cache_keys: list = []
    if keys.get("user_id"):
        cache_keys.append(f"{X5SEC_KEY_PREFIX}{keys['user_id']}")
    if keys.get("tk_key"):
        cache_keys.append(f"{X5SEC_TK_KEY_PREFIX}{keys['tk_key']}")

    if not cache_keys:
        return -1

    try:
        for key in cache_keys:
            ttl = redis_client.ttl(key)
            if ttl and ttl > 0:
                return int(ttl)
        return -1
    except Exception as e:
        logger.warning("get_x5sec_cache_ttl_remaining: TTL 读取失败: %s", e)
        return -1


def should_refresh_x5sec(cookie_str: str) -> bool:
    """方案 I：判断是否应该主动刷新 x5sec。

    当 x5sec 缓存剩余 TTL < X5SEC_REFRESH_THRESHOLD_SEC（默认 1 小时）时，
    下次使用后应主动触发刷新，避免过期后触发滑块。

    Args:
        cookie_str: Cookie 字符串

    Returns:
        True 表示应该刷新，False 表示无需刷新或无缓存
    """
    ttl = get_x5sec_cache_ttl_remaining(cookie_str)
    if ttl < 0:
        return False
    return ttl < X5SEC_REFRESH_THRESHOLD_SEC


def get_cached_x5sec(cookie_str: str) -> Optional[str]:
    """从 Redis 读取缓存的 x5sec。与 x5secCache.ts 的 getCachedX5sec 对齐。

    2026-08-03 方案 I：Redis 未命中时尝试本地文件兜底读取。
    2026-08-04 11.5.1-2：接入缓存命中率统计埋点。
    """
    if not cookie_str:
        return None

    keys = _extract_cache_keys(cookie_str)
    cache_keys: list = []
    if keys.get("user_id"):
        cache_keys.append(f"{X5SEC_KEY_PREFIX}{keys['user_id']}")
    if keys.get("tk_key"):
        cache_keys.append(f"{X5SEC_TK_KEY_PREFIX}{keys['tk_key']}")

    if not cache_keys:
        return None

    # 统计：请求总数
    _incr_cache_stat("request_total")

    # 优先从 Redis 读取
    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            for key in cache_keys:
                value = redis_client.get(key)
                if value:
                    _incr_cache_stat("hit_redis")
                    logger.info(
                        "x5sec 缓存命中(Redis) key=%s... length=%d",
                        key[:20],
                        len(value),
                    )
                    return value
        except Exception as e:
            logger.warning("x5sec 缓存读取失败(Redis): %s", e)

    # 方案 I：Redis 未命中或失败，尝试本地文件兜底
    local_x5sec = _read_local_cache(cookie_str)
    if local_x5sec:
        _incr_cache_stat("hit_local")
        logger.info("x5sec 缓存命中(本地兜底) length=%d", len(local_x5sec))
        # 异步回填 Redis（下次可直接命中 Redis）
        try:
            if redis_client is not None:
                for key in cache_keys:
                    redis_client.set(key, local_x5sec, ex=X5SEC_CACHE_TTL)
                logger.info("x5sec 本地兜底缓存已回填 Redis")
        except Exception as e:
            logger.warning("x5sec 本地兜底缓存回填 Redis 失败: %s", e)
        return local_x5sec

    _incr_cache_stat("miss")
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
