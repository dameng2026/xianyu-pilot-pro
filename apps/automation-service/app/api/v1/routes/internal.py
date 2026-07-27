import asyncio as _asyncio
import json
import logging
import hmac
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select as _sel, update as _upd, text as _text_sql

from ....core.config import settings
from ....core.database import get_db, async_session as _async_session
from ....core.image_security import MAX_IMAGE_BYTES, validate_image_bytes
from ....core.response import ResultObject
from ....models.entities import WorkflowExecution, WorkflowDefinition
from ....services.automation_runtime import (
    execute_scheduled_task,
    list_due_tasks,
    local_business_search,
    execute_workflow,
    continue_workflow_execution,
    process_incoming_message,
    process_pending_deliveries,
    sync_delivery_status_for_account,
    sync_sold_orders_for_account,
    update_ws_heartbeat,
    list_workflow_timeline,
    list_workflow_state_variables,
    claim_scheduled_task_lease,
    _run_scheduled_task_in_background,
)
from ....services.upload_governance import (
    ALLOWED_PUBLIC_UPLOAD_PURPOSES,
    UploadGovernanceError,
    cleanup_expired_assets,
    store_governed_image,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal")

_WORKFLOW_FAILURE_MESSAGE = "工作流执行失败，请查看失败节点并重试"
_WORKFLOW_CONTINUE_FAILURE_MESSAGE = "工作流继续执行失败，请查看失败节点并重试"
_REDACTED_VALUE = "[REDACTED]"


def _normalize_payload_key(value: object) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


def _is_secret_payload_key(key: str) -> bool:
    return key in {
        "authorization", "headers", "apikey", "accesskey", "accesskeyid",
        "privatekey", "secretkey", "encryptkey", "clientsecret", "appsecret",
        "credential", "smtppass",
    } or key.endswith(
        ("password", "secret", "token", "cookie", "apikey", "credential")
    )


def _is_error_payload_key(key: str) -> bool:
    return key in {
        "error", "err", "errormessage", "lasterror", "exception", "traceback",
        "stack", "stacktrace", "responsebody", "rawresponse", "providerresponse",
        "rawpayload", "circuitreason", "aireason",
    }


def _sanitize_workflow_payload(value, *, failure_context: bool = False):
    """Remove provider diagnostics and credentials from persisted workflow summaries."""

    if isinstance(value, dict):
        local_failure = (
            failure_context
            or str(value.get("status") or "").lower() in {"failed", "error", "cancelled"}
            or str(value.get("event_level") or value.get("eventLevel") or "").upper() == "ERROR"
            or value.get("ok") is False
        )
        sanitized = {}
        for raw_key, raw_value in value.items():
            key = _normalize_payload_key(raw_key)
            if _is_secret_payload_key(key):
                sanitized[raw_key] = _REDACTED_VALUE if raw_value not in (None, "") else raw_value
            elif _is_error_payload_key(key):
                sanitized[raw_key] = _WORKFLOW_FAILURE_MESSAGE if raw_value not in (None, "") else raw_value
            elif local_failure and key in {
                "message", "reason", "detail", "details", "body", "response", "request",
                "debug", "raw", "content",
            }:
                sanitized[raw_key] = _WORKFLOW_FAILURE_MESSAGE if raw_value not in (None, "") else raw_value
            else:
                sanitized[raw_key] = _sanitize_workflow_payload(raw_value, failure_context=local_failure)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_workflow_payload(item, failure_context=failure_context) for item in value]
    return value


def _safe_workflow_status(value: object) -> str:
    status = str(value or "failed").strip().lower()
    return status if status in {"success", "partial_success", "failed", "cancelled"} else "failed"


def _safe_workflow_error(status: str, *, continuing: bool = False) -> str:
    if status in {"success", "partial_success"}:
        return ""
    return _WORKFLOW_CONTINUE_FAILURE_MESSAGE if continuing else _WORKFLOW_FAILURE_MESSAGE


def _required_tenant_id(value) -> Optional[int]:
    try:
        tenant_id = int(value)
    except (TypeError, ValueError):
        return None
    return tenant_id if tenant_id > 0 else None


def _required_qr_owner(body: Optional[dict]) -> tuple[Optional[int], Optional[int]]:
    payload = body or {}
    user_id = _required_tenant_id(payload.get("userId"))
    tenant_id = _required_tenant_id(payload.get("tenantId"))
    return user_id, tenant_id


def _qr_context_matches(ctx: dict, user_id: int, tenant_id: int) -> bool:
    try:
        return int(ctx.get("user_id")) == user_id and int(ctx.get("tenant_id")) == tenant_id
    except (TypeError, ValueError):
        return False


def verify_internal_token(x_internal_token: Optional[str] = Header(None)) -> None:
    """内部接口保护。Phase 1 起 fail-closed：令牌为空或不匹配均拒绝。"""
    if not x_internal_token:
        raise HTTPException(status_code=401, detail="暂未登录或token已经过期")

    expected = (getattr(settings, "effective_internal_api_token", "") or "").strip()
    if not expected:
        logger.error("INTERNAL_API_TOKEN 未配置，拒绝内部接口调用")
        raise HTTPException(status_code=503, detail="INTERNAL_API_TOKEN is not configured")
    if not hmac.compare_digest(str(x_internal_token), expected):
        raise HTTPException(status_code=403, detail="invalid internal token")


@router.get("/health")
async def internal_health(_: None = Depends(verify_internal_token)):
    return ResultObject.success({
        "service": "automation-service",
        "status": "ok",
        "boundary": "python-execution-only",
    })


@router.post("/uploads/cleanup")
async def internal_upload_cleanup(
    body: Optional[dict] = None,
    x_internal_tenant_id: Optional[str] = Header(None, alias="X-Internal-Tenant-Id"),
    _: None = Depends(verify_internal_token),
):
    payload = body or {}
    tenant_id = _required_tenant_id(payload.get("tenantId"))
    if tenant_id is None:
        return ResultObject.validate_failed("tenantId 必须为正整数")
    if str(tenant_id) != str(x_internal_tenant_id or "").strip():
        return ResultObject.failed("X-Internal-Tenant-Id 与清理租户不一致", code=403)
    dry_run = payload.get("dryRun", True) is not False
    if not dry_run and payload.get("confirm") != "DELETE_EXPIRED_UPLOADS":
        return ResultObject.validate_failed("执行清理必须提供确认口令")
    try:
        older_than_days = int(payload.get("olderThanDays") or settings.resolved_upload_retention_days)
        upload_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "../../../../uploads/images")
        )
        result = await cleanup_expired_assets(
            tenant_id=tenant_id,
            older_than_days=older_than_days,
            dry_run=dry_run,
            actor=str(payload.get("actor") or "internal-operator"),
            reason=str(payload.get("reason") or ""),
            reviewed_by=str(payload.get("reviewedBy") or ""),
            approved_by=str(payload.get("approvedBy") or ""),
            base_dir=upload_dir,
            asset_ids=payload.get("assetIds") if isinstance(payload.get("assetIds"), list) else None,
            limit=int(payload.get("limit") or 200),
        )
        return ResultObject.success(result)
    except (TypeError, ValueError):
        return ResultObject.validate_failed("清理参数格式无效")
    except UploadGovernanceError as exc:
        return ResultObject.failed(exc.public_message, code=exc.status_code)


@router.post("/content/public-images/upload")
async def internal_public_content_image_upload(
    file: UploadFile = File(...),
    purpose: str = Form(...),
    x_internal_tenant_id: Optional[str] = Header(None, alias="X-Internal-Tenant-Id"),
    _: None = Depends(verify_internal_token),
):
    """Store an allowlisted public content image; metadata remains owned by Java/MySQL."""

    tenant_id = _required_tenant_id(x_internal_tenant_id)
    if tenant_id is None:
        return ResultObject.validate_failed("X-Internal-Tenant-Id 必须为正整数")
    normalized_purpose = str(purpose or "").strip().lower()
    if normalized_purpose not in ALLOWED_PUBLIC_UPLOAD_PURPOSES:
        return ResultObject.validate_failed("公开图片用途无效")
    try:
        content = await file.read(MAX_IMAGE_BYTES + 1)
        image = validate_image_bytes(content, declared_media_type=file.content_type)
        upload_dir = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "../../../../uploads/images")
        )
        stored = await store_governed_image(
            image,
            tenant_id=tenant_id,
            user_id=0,
            prefix=("carousel" if normalized_purpose == "carousel" else "open-content"),
            source_type=normalized_purpose,
            base_dir=upload_dir,
            visibility="public",
            purpose=normalized_purpose,
            owner_type="service",
        )
        logger.info(
            "public content image stored tenantId=%d purpose=%s bytes=%d",
            tenant_id,
            normalized_purpose,
            len(content),
        )
        return ResultObject.success({"url": stored.public_url, "assetId": stored.asset_id})
    except ValueError:
        return ResultObject.validate_failed(
            "图片文件无效；仅支持 JPEG、PNG、GIF、WebP，且大小不能超过 5MB"
        )
    except UploadGovernanceError as exc:
        return ResultObject.failed(exc.public_message, code=exc.status_code)
    except Exception as exc:
        logger.error("public content image upload failed errorType=%s", type(exc).__name__)
        return ResultObject.failed("上传公开内容图片失败，请稍后重试", code=503)


# ---- Java 网关转发扫码登录：Python 执行扫码流程并保存 Cookie ----
@router.post("/qrlogin/generate")
async def internal_qrlogin_generate(
    body: Optional[dict] = None,
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import generate_qrcode
        user_id, tenant_id = _required_qr_owner(body)
        if user_id is None or tenant_id is None:
            return ResultObject.validate_failed("userId 和 tenantId 必须为正整数")
        result = await _asyncio.to_thread(generate_qrcode, user_id=user_id, tenant_id=tenant_id)
        if "qrImage" in result and "qrCodeBase64" not in result:
            result["qrCodeBase64"] = result["qrImage"]
        result.setdefault("status", "pending")
        result.setdefault("message", "请使用闲鱼 App 扫码登录")
        return ResultObject.success(result)
    except Exception as e:
        logger.error("internal qr generate failed", exc_info=True)
        return ResultObject.failed("生成闲鱼登录二维码失败，请稍后重试", code=503)


@router.post("/qrlogin/status/{session_id}")
async def internal_qrlogin_status(
    session_id: str,
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import get_session_context, get_session_status, cleanup_session
        from .misc import _save_scan_login_result

        user_id, tenant_id = _required_qr_owner(body)
        if user_id is None or tenant_id is None:
            return ResultObject.validate_failed("userId 和 tenantId 必须为正整数")
        ctx = get_session_context(session_id)
        if ctx is None:
            return ResultObject.success({"status": "expired", "message": "会话不存在或已过期"})
        if not _qr_context_matches(ctx, user_id, tenant_id):
            return ResultObject.failed("无权访问此会话", code=403)

        result = get_session_status(session_id)
        if result.get("status") == "confirmed":
            account_id = _required_tenant_id((body or {}).get("accountId"))
            if (body or {}).get("accountId") is not None and account_id is None:
                return ResultObject.validate_failed("accountId 必须为正整数")
            if account_id is not None:
                result["accountId"] = account_id
                result["message"] = "扫码登录成功，等待更新账号 Cookie"
                return ResultObject.success(result)
            save_result = await _save_scan_login_result(session_id, db)
            if not save_result:
                result["status"] = "error"
                result["message"] = "账号保存失败，请重试"
            elif save_result.get("_error"):
                result["status"] = "error"
                result["message"] = save_result.get("message", "账号保存失败，请重试")
                result["errorCode"] = save_result.get("_error")
            else:
                result["accountId"] = save_result.get("account_id")
                result["cookieStatus"] = save_result.get("cookie_status")
                result["expireTime"] = save_result.get("expire_time")
                result["message"] = "扫码登录成功，账号已保存"
                cleanup_session(session_id)
        return ResultObject.success(result)
    except Exception as e:
        logger.error("internal qr status failed", exc_info=True)
        return ResultObject.failed("登录状态查询失败，请稍后重试", code=503)


@router.post("/qrlogin/cookies/{session_id}")
async def internal_qrlogin_cookies(
    session_id: str,
    body: Optional[dict] = None,
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import get_session_context, get_session_cookies

        user_id, tenant_id = _required_qr_owner(body)
        if user_id is None or tenant_id is None:
            return ResultObject.validate_failed("userId 和 tenantId 必须为正整数")
        ctx = get_session_context(session_id)
        if ctx is None:
            return ResultObject.success({"status": "expired", "message": "会话不存在或已过期"})
        if not _qr_context_matches(ctx, user_id, tenant_id):
            return ResultObject.failed("无权访问此会话", code=403)

        result = get_session_cookies(session_id)
        if not result:
            return ResultObject.success({"status": "expired", "message": "会话不存在或已过期"})
        return ResultObject.success(result)
    except Exception as e:
        logger.error("internal qr cookies failed", exc_info=True)
        return ResultObject.failed("扫码凭证读取失败，请稍后重试", code=503)


@router.post("/qrlogin/cleanup")
async def internal_qrlogin_cleanup(
    body: Optional[dict] = None,
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import cleanup_sessions_for_owner

        user_id, tenant_id = _required_qr_owner(body)
        if user_id is None or tenant_id is None:
            return ResultObject.validate_failed("userId 和 tenantId 必须为正整数")
        removed = cleanup_sessions_for_owner(user_id, tenant_id)
        return ResultObject.success({"status": "ok", "removed": removed})
    except Exception as e:
        logger.error("internal qr cleanup failed", exc_info=True)
        return ResultObject.failed("扫码会话清理失败，请稍后重试", code=503)


@router.post("/qrlogin/cleanup/{session_id}")
async def internal_qrlogin_cleanup_session(
    session_id: str,
    body: Optional[dict] = None,
    _: None = Depends(verify_internal_token),
):
    try:
        from ....core.xianyu_qr_login import cleanup_session_for_owner

        user_id, tenant_id = _required_qr_owner(body)
        if user_id is None or tenant_id is None:
            return ResultObject.validate_failed("userId 和 tenantId 必须为正整数")
        removed = cleanup_session_for_owner(session_id, user_id, tenant_id)
        return ResultObject.success({"status": "ok", "removed": 1 if removed else 0})
    except Exception as e:
        logger.error("internal qr session cleanup failed", exc_info=True)
        return ResultObject.failed("扫码会话清理失败，请稍后重试", code=503)


# ---- 定时任务执行器 ----
@router.get("/tasks/due")
async def internal_due_tasks(
    tenantId: Optional[int] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    tenant_id = _required_tenant_id(tenantId)
    if tenant_id is None:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    return ResultObject.success(await list_due_tasks(db, tenant_id, limit))


@router.post("/tasks/{task_id}/run")
async def internal_run_task(
    task_id: int,
    body: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    payload = body or {}
    tenant_id = _required_tenant_id(payload.get("tenantId"))
    if tenant_id is None:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")

    # 同步执行 lease claim，立即判断任务是否可执行（毫秒级完成）
    # 避免直接 await execute_scheduled_task 同步等待长耗时任务（如 auto_redelivery
    # 多账号同步订单+批量发货）导致 Java 端 HTTP 超时和前端 axios 超时。
    task, lease_token, claim_error = await claim_scheduled_task_lease(
        db, task_id, tenant_id, manual=True
    )

    if task is None:
        # claim 失败，返回对应错误
        error_code = claim_error.get("error") or claim_error.get("errorCode")
        if error_code in {"TASK_ALREADY_RUNNING", "TASK_LEASE_LOST"}:
            return ResultObject.failed(
                "定时任务正在执行或执行归属已变更，请稍后刷新状态",
                409,
            )
        if error_code == "TASK_SCOPE_INVALID":
            return ResultObject.validate_failed(claim_error.get("message", "任务参数无效"))
        # 500 兜底：claim_error.message 可能包含运行时异常详情（含 provider 响应体、
        # API key、token 等敏感信息），不得直接回传给前端。仅记录日志，返回通用提示。
        logger.warning(
            "定时任务 claim 失败 taskId=%d tenantId=%d errorCode=%s",
            task_id, tenant_id, error_code,
        )
        return ResultObject.failed("定时任务暂时无法执行，请稍后重试", 500)

    # claim 成功，启动后台异步执行剩余部分（执行 + lease 释放 + 通知）
    # 使用独立 db session，不依赖请求 scoped session
    _asyncio.create_task(_run_scheduled_task_in_background(task, tenant_id, lease_token))

    # 立即返回响应，前端通过任务列表轮询 lastStatus 查看最终执行结果
    return ResultObject.success({
        "ok": True,
        "running": True,
        "message": "任务已开始执行，请稍后在任务列表查看运行结果",
        "taskId": task_id,
        "taskType": str(task.get("task_type") or "").lower(),
    })


@router.post("/orders/sync-sold")
async def internal_sync_sold_orders(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    tenant_id = int(body.get("tenantId"))
    result = await sync_sold_orders_for_account(
        db,
        tenant_id,
        body.get("accountId"),
        body.get("externalOrderId"),
    )
    await db.commit()
    return ResultObject.success(result)


@router.post("/orders/confirm-shipment")
async def internal_confirm_shipment(
    body: dict = {},
    _: None = Depends(verify_internal_token),
):
    """内部确认发货端点：调用闲鱼 MTOP API 确认发货（虚拟发货/免拼发货）。

    供 Java 端 DeliveryExecutionService 在 WS 发货消息发送成功后调用，
    只有本接口返回 success=true 时，Java 端才应将本地 order_status 标记为 3。

    请求体:
        tenantId: 租户ID
        accountId: 闲鱼账号ID
        externalOrderId: 闲鱼订单ID
        isBargain: 是否小刀订单（bool，可选，默认 false）
        itemId: 商品ID（小刀订单必填）
        buyerId: 买家ID（小刀订单必填）
    """
    from ....services.xianyu_api_service import confirm_order_shipment

    account_id = body.get("accountId")
    external_order_id = body.get("externalOrderId")
    if not account_id or not external_order_id:
        return ResultObject.failed("缺少 accountId 或 externalOrderId", 422)

    is_bargain = bool(body.get("isBargain", False))
    item_id = body.get("itemId")
    buyer_id = body.get("buyerId")

    try:
        result = await _asyncio.to_thread(
            confirm_order_shipment,
            int(account_id),
            str(external_order_id),
            is_bargain=is_bargain,
            item_id=item_id,
            buyer_id=buyer_id,
        )
    except Exception as exc:
        logger.error(
            "内部确认发货异常: accountId=%s orderId=%s error=%s",
            account_id, external_order_id, exc,
        )
        return ResultObject.success({
            "success": False,
            "error": "CONFIRM_SHIPMENT_EXCEPTION",
            "message": f"确认发货异常: {exc}",
        })

    if result and result.get("success"):
        return ResultObject.success(result)
    return ResultObject.success(result or {
        "success": False,
        "error": "CONFIRM_SHIPMENT_FAILED",
        "message": "确认发货失败",
    })


@router.post("/orders/sync-delivery-status")
async def internal_sync_delivery_status(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    tenant_id = int(body.get("tenantId"))
    result = await sync_delivery_status_for_account(
        db,
        tenant_id,
        body.get("accountId"),
        body.get("externalOrderId"),
    )
    await db.commit()
    return ResultObject.success(result)


# ---- 自动发货闭环 ----
@router.post("/delivery/process-pending")
async def internal_process_pending_delivery(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    result = await process_pending_deliveries(
        db,
        tenant_id=int(body.get("tenantId")),
        account_id=body.get("accountId"),
        limit=int(body.get("limit", 20)),
    )
    return ResultObject.success(result)


# ---- 自动回复闭环：消息监听器提交入站消息，Python 负责匹配规则和写回日志 ----
@router.post("/messages/incoming")
async def internal_incoming_message(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.success(await process_incoming_message(db, body))


# ---- WebSocket 心跳 ----
@router.post("/ws/heartbeat")
async def internal_ws_heartbeat(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    return ResultObject.success(await update_ws_heartbeat(db, body))


# ---- 本地商机检索：生产环境由 Java 网关代理到此接口 ----
@router.get("/business-opportunity/search")
async def internal_business_search(
    q: str = Query(default=""),
    tenantId: Optional[int] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    tenant_id = _required_tenant_id(tenantId)
    if tenant_id is None:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    return ResultObject.success(await local_business_search(db, tenant_id, q, limit))


# ---- Phase12 工作流执行器 ----
@router.post("/workflows/{workflow_id}/execute")
async def internal_execute_workflow(
    workflow_id: int,
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    body["workflowId"] = workflow_id
    tenant_id = _required_tenant_id(body.get("tenantId"))
    if tenant_id is None:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    if _required_tenant_id(workflow_id) is None:
        return ResultObject.validate_failed("workflowId 必须为正整数")
    execution_id = _required_tenant_id(body.get("executionId"))
    if execution_id is None:
        return ResultObject.validate_failed("executionId 不能为空且必须为正整数")
    execution = (await db.execute(
        _sel(WorkflowExecution.id).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if execution is None:
        return ResultObject.failed("工作流执行记录不存在", code=404)
    workflow_name = (body.get("workflow") or {}).get("name") or f"工作流#{workflow_id}"

    # ★ 异步化：与 public 端点一致，fire-and-forget 后台执行，立即返回避免 Java/前端 HTTP 超时
    _asyncio.create_task(_internal_run_workflow_bg(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        execution_id=execution_id,
        wf_name=str(workflow_name),
        execute_payload=body,
    ))
    logger.info("[INTERNAL-WORKFLOW] 已提交后台执行 execution=%s workflow=%s", execution_id, workflow_name)

    return ResultObject.success({
        "status": "running",
        "executionId": execution_id,
        "message": "工作流已提交后台执行，请通过执行详情查看进度",
    })


@router.post("/workflows/executions/{execution_id}/continue")
async def internal_continue_workflow(
    execution_id: int,
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """继续执行已失败的工作流：复用原 execution_id，跳过已成功节点，从失败节点继续执行。"""
    tenant_id = _required_tenant_id(body.get("tenantId"))
    if tenant_id is None:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    if _required_tenant_id(execution_id) is None:
        return ResultObject.validate_failed("executionId 必须为正整数")
    execution = (await db.execute(
        _sel(WorkflowExecution.id).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.tenant_id == tenant_id,
        )
    )).scalar_one_or_none()
    if execution is None:
        return ResultObject.failed("工作流执行记录不存在", code=404)

    # 异步化：fire-and-forget 后台执行，立即返回
    _asyncio.create_task(_internal_continue_workflow_bg(
        tenant_id=tenant_id,
        execution_id=execution_id,
    ))
    logger.info("[INTERNAL-WORKFLOW-CONTINUE] 已提交后台继续执行 execution=%s", execution_id)

    return ResultObject.success({
        "status": "running",
        "executionId": execution_id,
        "message": "工作流继续执行已提交后台，请通过执行详情查看进度",
    })


async def _internal_continue_workflow_bg(
    tenant_id: int,
    execution_id: int,
):
    """后台继续执行工作流（复用 _internal_run_workflow_bg 的逻辑）。"""
    from datetime import datetime as _dt
    import json as _json
    async with _async_session() as bg_db:
        try:
            exec_result = await continue_workflow_execution(bg_db, execution_id)
            status = _safe_workflow_status(exec_result.get("status"))
            node_results = _sanitize_workflow_payload(
                exec_result.get("nodeResults", []),
                failure_context=status not in {"success", "partial_success"},
            )
            now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
            def _json_default(o):
                if hasattr(o, "isoformat"):
                    return o.isoformat()
                return f"<{type(o).__name__}>"
            output_str = _json.dumps(_sanitize_workflow_payload({
                "nodeResults": node_results,
                "artifacts": exec_result.get("artifacts", []),
                "timeline": exec_result.get("timeline", []),
            }, failure_context=status not in {"success", "partial_success"}), ensure_ascii=False, default=_json_default)
            err_msg = _safe_workflow_error(status, continuing=True)
            await bg_db.execute(_text_sql("""
                UPDATE workflow_execution
                SET status=:s, progress=100, finished_time=:ft,
                    error_message=:err, output_json=:o, updated_time=:ft
                WHERE id=:eid AND tenant_id=:tid
            """), {
                "s": status, "ft": now_str, "err": err_msg, "o": output_str,
                "eid": execution_id, "tid": tenant_id,
            })
            await bg_db.commit()
            logger.info("[INT-CONT-BG] 工作流继续执行完成 execution=%s status=%s", execution_id, status)
        except _asyncio.CancelledError:
            try:
                await bg_db.rollback()
            except Exception as rb_err:
                logger.debug("[INT-CONT-BG] 取消时回滚失败 execution=%s errorType=%s", execution_id, type(rb_err).__name__)
            try:
                now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                await bg_db.execute(_text_sql("""
                    UPDATE workflow_execution SET status='failed', progress=100, finished_time=:ft,
                        error_message='继续执行被取消，已发布商品已保留', updated_time=:ft
                    WHERE id=:eid AND tenant_id=:tid AND status='running'
                """), {"ft": now_str, "eid": execution_id, "tid": tenant_id})
                await bg_db.commit()
            except Exception as db_err:
                logger.error(
                    "[INT-CONT-BG] 取消时更新状态失败 execution=%s errorType=%s",
                    execution_id,
                    type(db_err).__name__,
                )
        except Exception as e:
            logger.error("[INT-CONT-BG] 工作流继续执行异常 execution=%s", execution_id, exc_info=True)
            try:
                await bg_db.rollback()
            except Exception as rb_err:
                logger.debug("[INT-CONT-BG] 异常时回滚失败 execution=%s errorType=%s", execution_id, type(rb_err).__name__)
            try:
                now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                await bg_db.execute(_text_sql("""
                    UPDATE workflow_execution SET status='failed', progress=100, finished_time=:ft,
                        error_message=:err, updated_time=:ft
                    WHERE id=:eid AND tenant_id=:tid
                """), {
                    "ft": now_str,
                    "err": _WORKFLOW_CONTINUE_FAILURE_MESSAGE,
                    "eid": execution_id,
                    "tid": tenant_id,
                })
                await bg_db.commit()
            except Exception as db_err:
                logger.error(
                    "[INT-CONT-BG] 异常时更新状态失败 execution=%s errorType=%s",
                    execution_id,
                    type(db_err).__name__,
                )


async def _internal_run_workflow_bg(
    tenant_id: int,
    workflow_id: int,
    execution_id: int,
    wf_name: str,
    execute_payload: dict,
):
    from datetime import datetime as _dt
    import json as _json
    async with _async_session() as bg_db:
        try:
            exec_result = await execute_workflow(bg_db, execute_payload)
            status = _safe_workflow_status(exec_result.get("status"))
            node_results = _sanitize_workflow_payload(
                exec_result.get("nodeResults", []),
                failure_context=status not in {"success", "partial_success"},
            )
            now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
            # ★ 使用 default=str 兜底，避免 timeline/nodeResults 内含 datetime 对象导致序列化失败
            def _json_default(o):
                if hasattr(o, "isoformat"):
                    return o.isoformat()
                return f"<{type(o).__name__}>"
            output_str = _json.dumps(_sanitize_workflow_payload({
                "nodeResults": node_results,
                "artifacts": exec_result.get("artifacts", []),
                "timeline": exec_result.get("timeline", []),
            }, failure_context=status not in {"success", "partial_success"}), ensure_ascii=False, default=_json_default)
            err_msg = _safe_workflow_error(status)
            # 用 raw SQL 更新（与 execute_workflow 保持一致，避免 ORM 模型映射问题）
            await bg_db.execute(_text_sql("""
                UPDATE workflow_execution
                SET status=:s, progress=100, finished_time=:ft,
                    error_message=:err, output_json=:o, updated_time=:ft
                WHERE id=:eid AND tenant_id=:tid
            """), {
                "s": status, "ft": now_str, "err": err_msg, "o": output_str,
                "eid": execution_id, "tid": tenant_id,
            })
            await bg_db.execute(_text_sql("""
                UPDATE workflow_definition
                SET execution_count = COALESCE(execution_count, 0) + 1, updated_time = :ft
                WHERE id = :wid AND tenant_id = :tid
            """), {"ft": now_str, "wid": workflow_id, "tid": tenant_id})
            await bg_db.commit()
            logger.info("[INT-BG] 工作流后台执行完成 execution=%s status=%s", execution_id, status)
        except _asyncio.CancelledError:
            try:
                await bg_db.rollback()
            except Exception as rb_err:
                logger.debug("[INT-BG] 取消时回滚失败 execution=%s errorType=%s", execution_id, type(rb_err).__name__)
            try:
                now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                await bg_db.execute(_text_sql("""
                    UPDATE workflow_execution SET status='failed', progress=100, finished_time=:ft,
                        error_message='工作流执行被取消，已发布商品已保留', updated_time=:ft
                    WHERE id=:eid AND tenant_id=:tid AND status='running'
                """), {"ft": now_str, "eid": execution_id, "tid": tenant_id})
                await bg_db.commit()
            except Exception as db_err:
                logger.error(
                    "[INT-BG] 取消时更新状态失败 execution=%s errorType=%s",
                    execution_id,
                    type(db_err).__name__,
                )
        except Exception as e:
            logger.error("[INT-BG] 工作流后台执行异常 execution=%s", execution_id, exc_info=True)
            try:
                await bg_db.rollback()
            except Exception as rb_err:
                logger.debug("[INT-BG] 异常时回滚失败 execution=%s errorType=%s", execution_id, type(rb_err).__name__)
            try:
                now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                await bg_db.execute(_text_sql("""
                    UPDATE workflow_execution SET status='failed', progress=100, finished_time=:ft,
                        error_message=:err, updated_time=:ft
                    WHERE id=:eid AND tenant_id=:tid
                """), {
                    "ft": now_str,
                    "err": _WORKFLOW_FAILURE_MESSAGE,
                    "eid": execution_id,
                    "tid": tenant_id,
                })
                await bg_db.commit()
            except Exception as db_err:
                logger.error(
                    "[INT-BG] 异常时更新状态失败 execution=%s errorType=%s",
                    execution_id,
                    type(db_err).__name__,
                )


@router.get("/workflows/executions/{execution_id}/timeline")
async def internal_workflow_timeline(
    execution_id: int,
    tenantId: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """查询工作流执行时间线"""
    tid = _required_tenant_id(tenantId)
    if tid is None:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    timeline = await list_workflow_timeline(db, tid, execution_id)
    return ResultObject.success(_sanitize_workflow_payload(timeline))


@router.get("/workflows/executions/{execution_id}/state-variables")
async def internal_workflow_state_variables(
    execution_id: int,
    tenantId: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """查询工作流状态变量"""
    tid = _required_tenant_id(tenantId)
    if tid is None:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    variables = await list_workflow_state_variables(db, tid, execution_id)
    safe_variables = []
    for variable in variables:
        safe_variable = dict(variable)
        if "var_value_parsed" in safe_variable:
            sanitized_value = _sanitize_workflow_payload(safe_variable["var_value_parsed"])
            safe_variable["var_value_parsed"] = sanitized_value
            if not isinstance(sanitized_value, str):
                safe_variable["var_value"] = json.dumps(sanitized_value, ensure_ascii=False)
        safe_variables.append(safe_variable)
    return ResultObject.success(safe_variables)


@router.get("/workflows/item-timing-stats")
async def internal_item_timing_stats(
    tenantId: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """查询最近100个商品的单商品平均耗时（用于预估完成时间）"""
    tid = _required_tenant_id(tenantId)
    if tid is None:
        return ResultObject.validate_failed("tenantId 不能为空且必须为正整数")
    try:
        from sqlalchemy import text as _tx
        rows = (await db.execute(_tx("""
            SELECT total_ms FROM workflow_item_timing
            WHERE tenant_id=:t AND deleted=0 AND total_ms > 0
            ORDER BY created_time DESC LIMIT 100
        """), {"t": tid})).all()
        if rows:
            total = sum(r[0] for r in rows)
            avg_ms = int(total / len(rows))
            return ResultObject.success({
                "sampleCount": len(rows),
                "avgMs": avg_ms,
                "avgSeconds": round(avg_ms / 1000, 1),
                "avgMinutes": round(avg_ms / 60000, 2),
            })
        return ResultObject.success({"sampleCount": 0, "avgMs": 0, "avgSeconds": 0, "avgMinutes": 0})
    except Exception as e:
        logger.warning("查询商品耗时统计失败", exc_info=True)
        return ResultObject.failed("商品耗时统计暂不可用，请稍后重试", 503)
