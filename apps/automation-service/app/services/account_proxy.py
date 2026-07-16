"""账号绑定代理读取（全自动滑块按账号固定出口）。"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import quote

from sqlalchemy import text

from ..core.cookie_crypto import decrypt_cookie_if_needed
from ..core.database import async_session
from ..core.failure_logging import log_service_failure

logger = logging.getLogger(__name__)

_HAS_PROXY_COLS: Optional[bool] = None


async def _detect_proxy_columns() -> bool:
    global _HAS_PROXY_COLS
    if _HAS_PROXY_COLS is not None:
        return _HAS_PROXY_COLS
    try:
        async with async_session() as db:
            row = (
                await db.execute(
                    text(
                        """
                        SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = 'xianyu_account'
                          AND COLUMN_NAME = 'proxy_host'
                        """
                    )
                )
            ).mappings().first()
            _HAS_PROXY_COLS = bool(row and int(row["cnt"] or 0) > 0)
    except Exception as e:
        log_service_failure(
            logger, e, operation="detect_account_proxy_columns", level=logging.DEBUG,
        )
        _HAS_PROXY_COLS = False
    return bool(_HAS_PROXY_COLS)


async def ensure_proxy_columns() -> None:
    """尝试补齐代理列（开发/本地容错；生产应走迁移）。"""
    if await _detect_proxy_columns():
        return
    try:
        async with async_session() as db:
            for stmt in (
                "ALTER TABLE xianyu_account ADD COLUMN proxy_type VARCHAR(16) DEFAULT ''",
                "ALTER TABLE xianyu_account ADD COLUMN proxy_host VARCHAR(255) DEFAULT ''",
                "ALTER TABLE xianyu_account ADD COLUMN proxy_port INT NULL",
                "ALTER TABLE xianyu_account ADD COLUMN proxy_username VARCHAR(128) DEFAULT ''",
                "ALTER TABLE xianyu_account ADD COLUMN encrypted_proxy_password TEXT NULL",
            ):
                try:
                    await db.execute(text(stmt))
                except Exception:
                    # 列可能已存在
                    pass
            await db.commit()
        global _HAS_PROXY_COLS
        _HAS_PROXY_COLS = True
        logger.info("已尝试补齐 xianyu_account 代理字段")
    except Exception as e:
        log_service_failure(
            logger, e, operation="ensure_account_proxy_columns", level=logging.WARNING,
        )


async def load_account_proxy(account_id: int, tenant_id: int) -> Optional[dict[str, Any]]:
    """读取账号绑定代理。无配置返回 None。

    Returns:
      {
        "server": "http://host:port" | "socks5://host:port",
        "username": str | None,
        "password": str | None,
        "type": "http"|"https"|"socks5",
      }
    """
    await ensure_proxy_columns()
    if not await _detect_proxy_columns():
        return None
    try:
        async with async_session() as db:
            row = (
                await db.execute(
                    text(
                        """
                        SELECT proxy_type, proxy_host, proxy_port, proxy_username, encrypted_proxy_password
                        FROM xianyu_account
                        WHERE id = :aid AND tenant_id = :tid AND COALESCE(deleted, 0) = 0
                        LIMIT 1
                        """
                    ),
                    {"aid": account_id, "tid": tenant_id},
                )
            ).mappings().first()
        if not row:
            return None
        host = str(row.get("proxy_host") or "").strip()
        port = row.get("proxy_port")
        if not host or not port:
            return None
        ptype = str(row.get("proxy_type") or "http").strip().lower() or "http"
        if ptype not in ("http", "https", "socks5", "socks4"):
            ptype = "http"
        user = str(row.get("proxy_username") or "").strip() or None
        pwd_enc = row.get("encrypted_proxy_password")
        pwd = decrypt_cookie_if_needed(pwd_enc) if pwd_enc else None
        if pwd is not None:
            pwd = str(pwd).strip() or None
        server = f"{ptype}://{host}:{int(port)}"
        return {
            "server": server,
            "username": user,
            "password": pwd,
            "type": ptype,
            "host": host,
            "port": int(port),
        }
    except Exception as e:
        log_service_failure(
            logger, e, operation="load_account_proxy",
            tenant_id=tenant_id, account_id=account_id, level=logging.WARNING,
        )
        return None


def proxy_to_playwright(proxy: Optional[dict[str, Any]]) -> Optional[dict[str, str]]:
    """转为 Playwright / sliderSolve 可消费结构。"""
    if not proxy or not proxy.get("server"):
        return None
    out: dict[str, str] = {"server": str(proxy["server"])}
    if proxy.get("username"):
        out["username"] = str(proxy["username"])
    if proxy.get("password"):
        out["password"] = str(proxy["password"])
    return out


def proxy_public_label(proxy: Optional[dict[str, Any]]) -> str:
    if not proxy:
        return ""
    host = proxy.get("host") or ""
    port = proxy.get("port") or ""
    ptype = proxy.get("type") or "http"
    if not host:
        return str(proxy.get("server") or "")
    return f"{ptype}://{host}:{port}"
