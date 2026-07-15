# -*- coding: utf-8 -*-
"""修改 app/core/security.py - 添加 jti、黑名单函数"""
import io

TARGET = r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\core\security.py"

with io.open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

NEW_CONTENT = '''import asyncio
import logging
import time
import uuid
from typing import Optional

import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.core.redis_client import redis_exists, redis_set

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    payload = {
        "sub": "admin",
        "username": username,
        "role": "admin",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(milliseconds=settings.jwt_expiration_ms),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ============================================================
# Token 黑名单（登出后吊销 jti）
# ============================================================
_BLACKLIST_PREFIX = "jwt_blacklist:"
# 内存回退：jti -> expiry(epoch seconds)
_mem_blacklist: dict = {}
_mem_blacklist_lock = asyncio.Lock()


def _cleanup_mem_blacklist() -> None:
    """清理内存中过期的黑名单项。"""
    now = time.time()
    expired = [j for j, exp in _mem_blacklist.items() if exp <= now]
    for j in expired:
        _mem_blacklist.pop(j, None)


async def is_token_blacklisted(jti: str) -> bool:
    """检查 jti 是否在黑名单中。"""
    if not jti:
        return False
    try:
        if await redis_exists(_BLACKLIST_PREFIX + jti):
            return True
    except Exception as e:
        logger.debug("redis_exists 黑名单失败，回退内存: %s", e)
    async with _mem_blacklist_lock:
        _cleanup_mem_blacklist()
        if jti in _mem_blacklist:
            # 命中内存黑名单
            return True
    return False


async def blacklist_token(jti: str, exp: int) -> None:
    """将 jti 加入黑名单，TTL 到 token 过期时间（exp 为 epoch seconds）。"""
    if not jti or not exp:
        return
    now = time.time()
    ttl = max(int(exp - now), 1)
    try:
        await redis_set(_BLACKLIST_PREFIX + jti, "1", ex=ttl)
    except Exception as e:
        logger.debug("redis_set 黑名单失败，回退内存: %s", e)
    async with _mem_blacklist_lock:
        _cleanup_mem_blacklist()
        _mem_blacklist[jti] = float(exp)
'''

with io.open(TARGET, "w", encoding="utf-8") as f:
    f.write(NEW_CONTENT)

print("security.py updated OK")
