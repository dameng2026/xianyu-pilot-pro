"""退款关单（退款订单注销）服务

功能：
- 按账号读取退款关单配置（开关/URL/超时）
- 收到退款订单同步后，将订单发货内容按 \n---\n 拆块，每块携带首个链接
  POST 到外部注销接口（仅允许 https 公网，防 SSRF）
- 全部成功才标记 is_unregistered=1，否则记录失败原因
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

import httpx
from sqlalchemy import text

from ..core.database import async_session
from ..core.outbound_network import public_https_outbound_policy, require_expected_httpx_peer

logger = logging.getLogger(__name__)


def split_delivery_blocks(content: Optional[str]) -> list[str]:
    """将发货内容按 \n---\n 拆块。"""
    if not content:
        return []
    return [block.strip() for block in str(content).split("\n---\n") if block.strip()]


def extract_first_link(block: str) -> str:
    match = re.search(r"https?://\S+", str(block or ""))
    return match.group(0) if match else ""


async def _call_unregister_url(
    cancel_url: str,
    timeout_seconds: int,
    block: str,
    link_url: str,
) -> tuple[bool, str]:
    """调用外部注销接口，返回 (success, error_message)。"""
    try:
        target = await public_https_outbound_policy.pin_public_https(cancel_url)
    except Exception as exc:
        return False, f"URL 校验失败: {type(exc).__name__}"

    timeout = httpx.Timeout(connect=5.0, read=timeout_seconds, write=5.0, pool=5.0)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            headers={"Host": target.host_header},
        ) as client:
            response = await client.post(
                target.request_url,
                data={"delivery_content": block, "link_url": link_url},
                extensions={"sni_hostname": target.sni_hostname},
            )
            require_expected_httpx_peer(response, target.peer_ip)
            if response.status_code == 200:
                return True, ""
            return False, f"HTTP {response.status_code}: {response.text[:100]}"
    except httpx.HTTPError as exc:
        return False, f"网络异常: {type(exc).__name__}"
    except Exception as exc:
        return False, f"调用异常: {type(exc).__name__}"


async def process_order_unregister(tenant_id: int, account_id: int, order_no: str) -> None:
    """处理单个退款订单的注销回调（幂等：已注销跳过）。"""
    normalized_order_no = str(order_no or "").strip()
    if not normalized_order_no:
        return
    try:
        async with async_session() as db:
            account = (await db.execute(text("""
                SELECT refund_cancel_enabled, refund_cancel_url, refund_cancel_timeout
                FROM xianyu_account
                WHERE id = :account_id AND tenant_id = :tenant_id AND deleted = 0
                LIMIT 1
            """), {
                "account_id": account_id,
                "tenant_id": tenant_id,
            })).mappings().first()
            if not account or not account.get("refund_cancel_enabled"):
                return
            cancel_url = str(account.get("refund_cancel_url") or "").strip()
            if not cancel_url:
                return
            try:
                timeout_seconds = int(account.get("refund_cancel_timeout") or 60)
            except (TypeError, ValueError):
                timeout_seconds = 60

            order = (await db.execute(text("""
                SELECT id, is_unregistered FROM xianyu_trade_order
                WHERE tenant_id = :tenant_id AND account_id = :account_id
                  AND external_order_id = :order_no AND deleted = 0
                LIMIT 1
            """), {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "order_no": normalized_order_no,
            })).mappings().first()
            if not order or order.get("is_unregistered"):
                return
            order_db_id = order["id"]

            record = (await db.execute(text("""
                SELECT delivery_content FROM delivery_record
                WHERE tenant_id = :tenant_id AND account_id = :account_id
                  AND order_id = :order_no AND deleted = 0
                  AND delivery_content IS NOT NULL AND delivery_content <> ''
                ORDER BY id DESC LIMIT 1
            """), {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "order_no": normalized_order_no,
            })).mappings().first()
            content = record["delivery_content"] if record else ""
            blocks = split_delivery_blocks(content)

            if not blocks:
                await db.execute(text("""
                    UPDATE xianyu_trade_order
                    SET is_unregistered = 1, unregister_error_reason = '发货内容为空', updated_time = NOW()
                    WHERE id = :order_db_id
                """), {"order_db_id": order_db_id})
                await db.commit()
                logger.info(
                    "退款关单：订单 %s 发货内容为空，标记已请求 tenant=%s account=%s",
                    normalized_order_no, tenant_id, account_id,
                )
                return

            all_success = True
            fail_detail = ""
            for idx, block in enumerate(blocks, 1):
                link_url = extract_first_link(block)
                ok, err = await _call_unregister_url(
                    cancel_url, timeout_seconds, block, link_url,
                )
                if not ok:
                    all_success = False
                    fail_detail = f"第{idx}块 {err}"
                    logger.warning(
                        "退款关单接口失败 order=%s account=%s %s",
                        normalized_order_no, account_id, fail_detail,
                    )
                    break

            await db.execute(text("""
                UPDATE xianyu_trade_order
                SET is_unregistered = :flag,
                    unregister_error_reason = :reason,
                    updated_time = NOW()
                WHERE id = :order_db_id
            """), {
                "order_db_id": order_db_id,
                "flag": 1 if all_success else 0,
                "reason": "" if all_success else fail_detail,
            })
            await db.commit()
            logger.info(
                "退款关单完成 order=%s account=%s success=%s",
                normalized_order_no, account_id, all_success,
            )
    except Exception as exc:
        logger.warning(
            "退款关单处理异常 tenant=%s account=%s order=%s errorType=%s",
            tenant_id, account_id, normalized_order_no, type(exc).__name__,
        )


def schedule_refund_unregister(tenant_id: int, account_id: int, order_no: str) -> None:
    """后台触发退款关单（fire-and-forget，不阻塞订单同步）。"""
    try:
        asyncio.create_task(
            process_order_unregister(tenant_id, account_id, order_no),
            name=f"refund_unregister_{account_id}_{order_no}",
        )
    except Exception as exc:
        logger.warning(
            "退款关单任务创建失败 tenant=%s account=%s order=%s errorType=%s",
            tenant_id, account_id, order_no, type(exc).__name__,
        )
