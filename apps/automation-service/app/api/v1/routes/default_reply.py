"""默认回复路由

账号级兜底回复：未命中关键词规则且 AI 客服关闭时生效。
支持文本（可附带图片）与外部 API 两种回复类型。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.http_failures import safe_route_failure
from ....core.response import ResultObject
from ....core.camel import CamelModel
from ....services.default_reply_api import normalize_api_timeout
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/defaultReply", tags=["defaultReply"])


class DefaultReplySaveRequest(CamelModel):
    enabled: bool = False
    reply_type: str = "text"  # text / api
    reply_content: str = ""
    reply_image: str = ""
    api_url: str = ""
    api_timeout: Optional[int] = None
    reply_once: bool = False


async def _assert_account_visible(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> bool:
    row = (await db.execute(
        text("""
            SELECT id FROM xianyu_account
            WHERE id = :account_id AND tenant_id = :tenant_id AND deleted = 0
            LIMIT 1
        """),
        {"account_id": account_id, "tenant_id": tenant_id},
    )).mappings().first()
    return row is not None


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "accountId": row.get("account_id"),
        "accountName": row.get("account_name") or "",
        "enabled": bool(row.get("enabled")),
        "replyType": row.get("reply_type") or "text",
        "replyContent": row.get("reply_content") or "",
        "replyImage": row.get("reply_image") or "",
        "apiUrl": row.get("api_url") or "",
        "apiTimeout": row.get("api_timeout") if row.get("api_timeout") is not None else 30,
        "replyOnce": bool(row.get("reply_once")),
        "createdAt": str(row.get("created_time")) if row.get("created_time") else None,
        "updatedAt": str(row.get("updated_time")) if row.get("updated_time") else None,
    }


@router.get("/list")
async def list_default_replies(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询当前租户所有账号的默认回复配置。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        rows = (await db.execute(text("""
            SELECT d.*, a.nickname AS account_name
            FROM default_reply d
            LEFT JOIN xianyu_account a ON a.id = d.account_id AND a.tenant_id = d.tenant_id
            WHERE d.tenant_id = :tenant_id AND d.deleted = 0
            ORDER BY d.updated_time DESC, d.id DESC
        """), {"tenant_id": tenant_id})).mappings().all()
        data = [_row_to_dict(dict(r)) for r in rows]
        return ResultObject.success({"records": data, "total": len(data)})
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="list default replies",
            user_message="获取默认回复配置失败，请稍后重试",
        )


@router.get("/{accountId}")
async def get_default_reply(
    accountId: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """查询指定账号的默认回复配置。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        if not await _assert_account_visible(db, tenant_id, accountId):
            return ResultObject.failed("账号不存在或无权操作", 404)
        row = (await db.execute(text("""
            SELECT d.*, a.nickname AS account_name
            FROM default_reply d
            LEFT JOIN xianyu_account a ON a.id = d.account_id AND a.tenant_id = d.tenant_id
            WHERE d.tenant_id = :tenant_id AND d.account_id = :account_id AND d.deleted = 0
            LIMIT 1
        """), {"tenant_id": tenant_id, "account_id": accountId})).mappings().first()
        if not row:
            return ResultObject.success({
                "accountId": accountId,
                "enabled": False,
                "replyType": "text",
                "replyContent": "",
                "replyImage": "",
                "apiUrl": "",
                "apiTimeout": 30,
                "replyOnce": False,
            })
        return ResultObject.success(_row_to_dict(dict(row)))
    except Exception as exc:
        return safe_route_failure(
            logger, exc, operation="get default reply",
            user_message="获取默认回复配置失败，请稍后重试",
        )


@router.post("/{accountId}")
async def save_default_reply(
    accountId: int,
    req: DefaultReplySaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """保存指定账号的默认回复配置（upsert）。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        if not await _assert_account_visible(db, tenant_id, accountId):
            return ResultObject.failed("账号不存在或无权操作", 404)

        reply_type = (req.reply_type or "text").strip().lower()
        if reply_type not in ("text", "api"):
            return ResultObject.failed("回复类型仅支持 text 或 api", 400)
        api_timeout = normalize_api_timeout(req.api_timeout)
        api_url = (req.api_url or "").strip()
        if reply_type == "api" and not api_url:
            return ResultObject.failed("API 类型必须填写 API 地址", 400)

        existing = (await db.execute(
            text("""
                SELECT id FROM default_reply
                WHERE tenant_id = :tenant_id AND account_id = :account_id AND deleted = 0
                LIMIT 1
            """),
            {"tenant_id": tenant_id, "account_id": accountId},
        )).mappings().first()

        if existing:
            await db.execute(
                text("""
                    UPDATE default_reply
                    SET enabled = :enabled, reply_type = :reply_type,
                        reply_content = :reply_content, reply_image = :reply_image,
                        api_url = :api_url, api_timeout = :api_timeout,
                        reply_once = :reply_once, updated_time = NOW()
                    WHERE id = :id AND tenant_id = :tenant_id
                """),
                {
                    "id": existing["id"],
                    "tenant_id": tenant_id,
                    "enabled": 1 if req.enabled else 0,
                    "reply_type": reply_type,
                    "reply_content": (req.reply_content or "").strip(),
                    "reply_image": (req.reply_image or "").strip(),
                    "api_url": api_url,
                    "api_timeout": api_timeout,
                    "reply_once": 1 if req.reply_once else 0,
                },
            )
        else:
            result = await db.execute(
                text("""
                    INSERT INTO default_reply(
                        tenant_id, account_id, enabled, reply_type, reply_content,
                        reply_image, api_url, api_timeout, reply_once, deleted, created_time, updated_time
                    ) VALUES(
                        :tenant_id, :account_id, :enabled, :reply_type, :reply_content,
                        :reply_image, :api_url, :api_timeout, :reply_once, 0, NOW(), NOW()
                    )
                """),
                {
                    "tenant_id": tenant_id,
                    "account_id": accountId,
                    "enabled": 1 if req.enabled else 0,
                    "reply_type": reply_type,
                    "reply_content": (req.reply_content or "").strip(),
                    "reply_image": (req.reply_image or "").strip(),
                    "api_url": api_url,
                    "api_timeout": api_timeout,
                    "reply_once": 1 if req.reply_once else 0,
                },
            )
        await db.commit()
        return ResultObject.success({"accountId": accountId}, message="默认回复配置已保存")
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="save default reply",
            user_message="保存默认回复配置失败，请稍后重试",
        )


@router.delete("/{accountId}")
async def delete_default_reply(
    accountId: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """删除指定账号的默认回复配置（软删除）。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        result = await db.execute(
            text("""
                UPDATE default_reply
                SET deleted = 1, updated_time = NOW()
                WHERE tenant_id = :tenant_id AND account_id = :account_id AND deleted = 0
            """),
            {"tenant_id": tenant_id, "account_id": accountId},
        )
        await db.commit()
        return ResultObject.success(
            {"accountId": accountId, "deleted": (result.rowcount or 0) > 0},
            message="默认回复配置已删除",
        )
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="delete default reply",
            user_message="删除默认回复配置失败，请稍后重试",
        )


@router.post("/{accountId}/clearRecords")
async def clear_default_reply_records(
    accountId: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """清空指定账号的默认回复记录（reply_once 计数）。"""
    try:
        tenant_id = int(current_user.get("tenant_id") or 0)
        if tenant_id <= 0:
            return ResultObject.failed("缺少租户上下文", 400)
        await db.execute(
            text("""
                DELETE FROM default_reply_record
                WHERE tenant_id = :tenant_id AND account_id = :account_id
            """),
            {"tenant_id": tenant_id, "account_id": accountId},
        )
        await db.commit()
        return ResultObject.success({"accountId": accountId}, message="默认回复记录已清空")
    except Exception as exc:
        await db.rollback()
        return safe_route_failure(
            logger, exc, operation="clear default reply records",
            user_message="清空默认回复记录失败，请稍后重试",
        )
