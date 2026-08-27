"""
Python 自动化运行时。

边界约定：
- Java/core-api 保存用户、账号、商品、订单、会员、套餐等主数据。
- Python/automation-service 只负责执行类动作：扫码登录、消息监听闭环、自动回复、自动发货、定时任务执行、商机/爬虫调度。
- 本模块直接读写业务库中的执行结果表，避免重新实现 Java 侧 CRUD。
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import math
import os
import random
import re
import sys
import time
import traceback
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import sqlalchemy
from sqlalchemy import text

from .ai_billing import (
    AiBillingError,
    AiBillingPaymentRequired,
    AiBillingUnavailable,
    build_request_id,
    build_stable_request_id,
    build_text_charge_payload,
    charge_image_usage,
    charge_text_usage,
    estimate_text_tokens,
    precheck_ai_usage,
)
from .pending_billing import enqueue_pending_billing, ensure_pending_billing_table
from .ai_provider import generate_text, get_polish_keywords_restriction, get_polish_forbidden_keywords, enforce_polish_restriction, validate_polish_output
from .ws_storage import save_chat_message
from .xianyu_goods_sync import (
    _make_api_request as _mtop_search_request,
    _normalize_mtop_search_item,
    _resolve_account_cookie,
    SEARCH_MTOP_API,
    TOKEN_EXPIRED as _XIANYU_TOKEN_EXPIRED,
    TOKEN_EXPIRED_ALIAS as _XIANYU_TOKEN_EXPIRED_ALIAS,
    RGV587 as _XIANYU_RGV587,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import async_session
from app.core.failure_logging import log_service_failure
from app.core.http_failures import get_request_id
from app.core.image_security import MAX_IMAGE_BYTES, download_public_image, validate_image_bytes
from app.core.outbound_network import public_https_outbound_policy
from app.services.upload_governance import store_governed_image

logger = logging.getLogger(__name__)

# 生图模型配置缓存（60s TTL，避免每个生图节点都查库）
# 缓存中间结果（general_cfg + img_cfgs 列表），node_model_key 排序仍每次执行
_image_model_cache: dict = {}
_IMAGE_MODEL_TTL = 60

_SCHEDULED_TASK_LEASE_SECONDS = 5 * 60
_SCHEDULED_TASK_EXECUTOR_ID = f"{settings.app_name}:{uuid.uuid4().hex}"[:120]


class PublicRuntimeError(RuntimeError):
    """Explicitly authored runtime failure that is safe to persist and return."""

    def __init__(self, error_code: str, public_message: str):
        self.error_code = error_code
        self.public_message = public_message
        super().__init__(public_message)


def _exc_type_name(exc: BaseException) -> str:
    """Return the exception type name without serialising the exception value."""
    return type(exc).__name__


def _log_runtime_failure(operation: str, exc: BaseException) -> None:
    """Log diagnostic metadata without serialising the exception value.

    对 NameError/AttributeError/TypeError 等编程错误，额外记录异常发生位置（文件/行号，
    不含异常值），便于定位 send_auto_reply 等操作中的代码级 bug。
    """
    log_service_failure(logger, exc, operation=operation)
    # 编程错误（NameError 等）属于代码 bug，不应在生产环境出现，记录栈帧位置便于定位
    if isinstance(exc, (NameError, AttributeError, TypeError, ImportError, SyntaxError, KeyError)):
        tb_frames = "".join(traceback.format_list(traceback.extract_tb(exc.__traceback__) or []))
        trace_error_kind = _exc_type_name(exc)
        logger.error(
            "traceback operation=%s exc_type=%s tb=%s",
            operation, trace_error_kind, tb_frames,
        )


async def _post_provider_json_bounded(
    url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: float,
    max_response_bytes: int,
) -> tuple[int, dict[str, Any]]:
    """POST to a model provider without buffering an unbounded response."""
    import httpx

    try:
        target = await public_https_outbound_policy.pin_public_https(url)
    except ValueError as exc:
        raise PublicRuntimeError(
            "AI_PROVIDER_UNSAFE_ENDPOINT",
            "AI 服务端点未通过安全校验，请联系管理员检查配置",
        ) from exc
    request_headers = dict(headers)
    request_headers["Host"] = target.host_header
    response_bytes = bytearray()
    async with httpx.AsyncClient(
        timeout=timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        async with client.stream(
            "POST",
            target.request_url,
            json=payload,
            headers=request_headers,
            extensions={"sni_hostname": target.sni_hostname},
        ) as response:
            status_code = response.status_code
            if 200 <= status_code < 300:
                chunks = response.aiter_bytes()
                async for chunk in chunks:
                    if len(response_bytes) + len(chunk) > max_response_bytes:
                        await chunks.aclose()
                        raise PublicRuntimeError(
                            "AI_PROVIDER_RESPONSE_TOO_LARGE",
                            "AI 服务返回内容过大，本次结果未采用",
                        )
                    response_bytes.extend(chunk)
    if not 200 <= status_code < 300:
        return status_code, {}
    try:
        data = json.loads(bytes(response_bytes))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise PublicRuntimeError(
            "AI_PROVIDER_INVALID_RESPONSE",
            "AI 服务返回了无效结果，请稍后重试",
        ) from exc
    if not isinstance(data, dict):
        raise PublicRuntimeError(
            "AI_PROVIDER_INVALID_RESPONSE",
            "AI 服务返回了无效结果，请稍后重试",
        )
    return status_code, data


def _runtime_failure_details(
    exc: BaseException,
    *,
    operation: str,
    default_code: str,
    default_message: str,
) -> tuple[str, str]:
    """Return a stable public failure while retaining explicit business errors."""

    _log_runtime_failure(operation, exc)
    if isinstance(exc, PublicRuntimeError):
        return exc.error_code, exc.public_message
    if isinstance(exc, asyncio.CancelledError):
        return "WORKFLOW_CANCELLED", "任务已取消，请重新执行"
    return default_code, default_message


_PUBLIC_RUNTIME_ERRORS: dict[str, str] = {
    "RUNTIME_OPERATION_FAILED": "操作失败，请稍后重试",
    "WORKFLOW_CANCELLED": "任务已取消，请重新执行",
    "WORKFLOW_NODE_FAILED": "节点执行失败，请检查配置后重试",
    "WORKFLOW_NODE_RUNTIME_ERROR": "节点执行异常，请稍后重试",
    "SHOP_URL_REQUIRED": "请先配置店铺链接",
    "ACCOUNT_AUTH_UNAVAILABLE": "账号登录状态不可用，请重新登录",
    "SHOP_CRAWL_TRIGGER_FAILED": "店铺抓取任务启动失败，请稍后重试",
    "SHOP_CRAWL_REJECTED": "店铺抓取服务暂时不可用，请稍后重试",
    "SHOP_USER_ID_INVALID": "店铺链接无法识别，请检查后重试",
    "SHOP_CRAWL_FAILED": "店铺抓取失败，请稍后重试",
    "SHOP_CRAWL_TIMEOUT": "店铺抓取超时，请稍后重试",
    "SHOP_ITEMS_UNAVAILABLE": "店铺商品暂时无法获取，请稍后重试",
    "SHOP_EMPTY": "店铺暂无可提取商品",
    "SHOP_EXHAUSTED": "该店铺商品已全部提取",
    "PRODUCT_SEARCH_RATE_LIMITED": "商品搜索触发平台验证，请稍后重试",
    "PRODUCT_SEARCH_UNAVAILABLE": "商品搜索服务暂时不可用，请稍后重试",
    "PRODUCT_SEARCH_EMPTY": "未获取到商品，请调整关键词后重试",
    "ORDER_ACCOUNT_REQUIRED": "请先选择要同步的账号",
    "ORDER_ACCOUNT_NOT_FOUND": "账号不存在或已停用",
    "ORDER_SYNC_PARTIAL": "部分订单同步失败，请稍后重试",
    "SCHEDULED_TASK_FAILED": "定时任务执行失败，请检查配置后重试",
    "EVENT_DRIVEN_TASK": "自动回复是事件驱动能力，不能作为定时任务执行",
    "UNSUPPORTED_TASK_TYPE": "该定时任务类型暂不支持执行",
    "TASK_LEASE_LOST": "定时任务执行归属已丢失，本执行器已停止处理",
    "POLISH_TASK_ACCOUNT_REQUIRED": "商品擦亮任务缺少账号",
    "POLISH_TASK_FAILED": "商品擦亮任务提交失败，请稍后重试",
    "REDELIVERY_RECORD_REQUIRED": "补发货任务缺少记录编号",
    "REDELIVERY_RECORD_NOT_FOUND": "补发货记录不存在",
    "REDELIVERY_DATA_INCOMPLETE": "补发货记录缺少买家或发货内容",
    "REDELIVERY_SEND_FAILED": "补发货消息发送失败，请稍后重试",
    "DELIVERY_BATCH_PARTIAL": "部分订单发货失败，请查看记录后重试",
    "DELIVERY_RULE_MISSING": "该订单未匹配自动发货规则",
    "DELIVERY_CARD_STOCK_EMPTY": "卡密库存不足，请补充后重试",
    "DELIVERY_CARD_READ_FAILED": "卡密读取失败，请稍后重试",
    "DELIVERY_SEND_FAILED": "发货消息发送失败，请稍后重试",
    "AUTO_REPLY_INVALID_REQUEST": "自动回复请求缺少必要信息",
    "AUTO_REPLY_USER_UNRESOLVED": "AI 回复无法确定用户归属",
    "AI_MODEL_UNAVAILABLE": "AI 对话模型暂不可用，请先完成配置",
    "AI_BALANCE_INSUFFICIENT": "AI Token 余额不足，请充值后重试",
    "AI_BILLING_FAILED": "AI Token 扣费失败，本次回复已停止",
    "AI_BILLING_UNAVAILABLE": "AI 计费服务暂不可用，生图与发布已停止，请稍后重试",
    "AI_USER_UNRESOLVED": "AI 生图无法确定计费用户，请检查工作流账号归属",
    "AI_FILTER_FAILED": "AI 商品筛选异常，筛选已停止，请稍后重试",
    "AUTO_REPLY_SEND_FAILED": "自动回复发送失败，请检查账号连接后重试",
    "AUTO_REPLY_SEND_WS_DISCONNECTED": "WebSocket 未连接，自动回复未发送，请检查账号登录状态",
    "AUTO_REPLY_SEND_REJECTED": "自动回复被闲鱼拒绝，请稍后重试",
    "AUTO_REPLY_SEND_EXCEPTION": "自动回复发送异常，请稍后重试",
    "AUTO_REPLY_SEND_NO_SID": "消息缺少会话 ID，自动回复未发送",
    "AUTO_REPLY_SEND_SKIPPED": "自动回复发送被跳过，请稍后重试",
    "PUBLISH_AI_IMAGE_REQUIRED": "商品未生成 AI 封面图，已阻止发布",
    "PUBLISH_CONTENT_INVALID": "商品标题或描述不完整，已阻止发布",
    "PUBLISH_ACCOUNT_UNAVAILABLE": "发布账号登录状态不可用，请重新登录",
    "PUBLISH_DUPLICATE": "该商品已发布过，已跳过重复发布",
    "PUBLISH_PROVIDER_REJECTED": "商品发布被平台拒绝，请根据具体原因修改后重试",
    "PUBLISH_RUNTIME_ERROR": "商品发布异常，请稍后重试",
    "IMAGE_ADDRESS_REQUIRED": "请先选择完整的商品发布地址",
    "IMAGE_PROVIDER_FAILED": "AI 封面图生成失败，请稍后重试",
    "PUBLISH_CIRCUIT_OPEN": "连续发布失败已触发保护，请检查账号与商品配置后重试",
    "IMAGE_PUBLISH_NO_SUCCESS": "本次未成功发布商品，请检查生图和发布配置",
    "PUBLISH_NO_SUCCESS": "本次未成功发布商品，请检查账号与商品配置",
    "WORKFLOW_EXECUTION_NOT_FOUND": "工作流执行记录不存在",
    "WORKFLOW_TENANT_INVALID": "执行记录缺少有效的租户上下文",
    "WORKFLOW_ALREADY_RUNNING": "工作流正在运行，无需重复继续",
    "WORKFLOW_INPUT_INVALID": "工作流执行参数已损坏，无法继续",
    "WORKFLOW_DEFINITION_NOT_FOUND": "工作流定义不存在",
    "WORKFLOW_EMPTY": "工作流未配置可执行节点",
    "WORKFLOW_GRAPH_INVALID": "工作流连线或依赖配置无效",
    "WORKFLOW_RETRY_SOURCE_MISSING": "重试失败：未找到上游商品获取节点",
    "PRODUCT_TARGET_UNMET": "商品数量未达到目标，请调整关键词或筛选条件",
}
_RUNTIME_FAILURE_STATUSES = {"failed", "failure", "error", "rejected", "cancelled", "canceled"}
_RUNTIME_ERROR_KEYS = {
    "error",
    "errormessage",
    "failreason",
    "failedreason",
    "last_error",
    "lasterror",
    "aireason",
    "exception",
    "exceptionmessage",
}
_RUNTIME_RESPONSE_KEYS = {
    "response",
    "responsebody",
    "rawresponse",
    "rawbody",
    "requestbody",
    "rawrequest",
    "headers",
    "requestheaders",
    "responseheaders",
}
_RUNTIME_SECRET_KEY_SUFFIXES = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "passwd",
    "secret",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "verificationtoken",
    "apikey",
    "privatekey",
    "signature",
)
_RUNTIME_UNSAFE_FAILURE_TEXT = re.compile(
    r"https?://|(?:authorization|cookie|password|secret|token|api[-_]?key)\s*[:=]",
    re.IGNORECASE,
)


def _runtime_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]", "", _text(value).strip().lower())


def _is_runtime_failure_mapping(value: dict[Any, Any]) -> bool:
    if value.get("ok") is False or value.get("success") is False:
        return True
    if value.get("aiOk") is False:
        return True
    if _text(value.get("status")).strip().lower() in _RUNTIME_FAILURE_STATUSES:
        return True
    for key, item in value.items():
        normalized_key = _runtime_key(key)
        if normalized_key == "aireason" and value.get("aiOk") is not False:
            continue
        if normalized_key in _RUNTIME_ERROR_KEYS and item not in (None, "", [], {}):
            return True
    return False


def _sanitize_runtime_value(
    value: Any,
    *,
    failure_context: bool = False,
    default_code: str = "RUNTIME_OPERATION_FAILED",
) -> Any:
    """Remove untrusted failure details before a value crosses a persistence boundary.

    Only codes registered in ``_PUBLIC_RUNTIME_ERRORS`` may select a public message.
    This makes public business failures explicit and prevents upstream payloads from
    declaring arbitrary text safe by setting a boolean flag.
    """

    if isinstance(value, BaseException):
        return {
            "errorCode": default_code,
            "errorMessage": _PUBLIC_RUNTIME_ERRORS[default_code],
        }
    if isinstance(value, list):
        return [
            _sanitize_runtime_value(item, failure_context=failure_context, default_code=default_code)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _sanitize_runtime_value(item, failure_context=failure_context, default_code=default_code)
            for item in value
        ]
    if not isinstance(value, dict):
        if failure_context and isinstance(value, str) and _RUNTIME_UNSAFE_FAILURE_TEXT.search(value):
            return _PUBLIC_RUNTIME_ERRORS[default_code]
        return value

    is_failure = failure_context or _is_runtime_failure_mapping(value)
    requested_code = _text(value.get("errorCode") or value.get("error_code")).strip().upper()
    error_code = requested_code if requested_code in _PUBLIC_RUNTIME_ERRORS else default_code
    public_message = _PUBLIC_RUNTIME_ERRORS[error_code]
    sanitized: dict[Any, Any] = {}

    for key, item in value.items():
        normalized_key = _runtime_key(key)
        compact_key = normalized_key.replace("_", "")
        if compact_key == "token" or compact_key.endswith(_RUNTIME_SECRET_KEY_SUFFIXES):
            continue
        if is_failure and (
            normalized_key in _RUNTIME_ERROR_KEYS
            or compact_key in {item.replace("_", "") for item in _RUNTIME_ERROR_KEYS}
            or normalized_key in _RUNTIME_RESPONSE_KEYS
            or compact_key in {item.replace("_", "") for item in _RUNTIME_RESPONSE_KEYS}
            or compact_key.endswith("url")
            or compact_key.endswith("uri")
            or normalized_key in {"message", "publicerror", "errorcode", "error_code"}
        ):
            continue
        sanitized[key] = _sanitize_runtime_value(
            item,
            failure_context=is_failure,
            default_code=default_code,
        )

    if is_failure:
        sanitized["errorCode"] = error_code
        sanitized["errorMessage"] = public_message
        if "message" in value:
            sanitized["message"] = public_message
    return sanitized


def _normalize_workflow_node_output(output: Any) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {
            "ok": False,
            "errorCode": "WORKFLOW_NODE_FAILED",
            "errorMessage": _PUBLIC_RUNTIME_ERRORS["WORKFLOW_NODE_FAILED"],
            "message": _PUBLIC_RUNTIME_ERRORS["WORKFLOW_NODE_FAILED"],
        }
    return _sanitize_runtime_value(
        output,
        failure_context=output.get("ok") is False,
        default_code="WORKFLOW_NODE_FAILED",
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _find_first_key(d: dict, keys: list[str]) -> str:
    """按优先级查找字典中第一个存在的键"""
    for k in keys:
        if k in d:
            return k
    return "none"


def _text(value: Any) -> str:
    return "" if value is None else str(value)


_REPLY_SPLIT_SEPARATOR = "######"


def _split_reply_messages(content: str) -> list[str]:
    """将回复内容按 ###### 拆分为多条消息，逐条发送（与同类项目体验一致）。"""
    text_content = _text(content or "").strip()
    if not text_content:
        return []
    parts = [part.strip() for part in text_content.split(_REPLY_SPLIT_SEPARATOR)]
    return [part for part in parts if part]


async def _send_reply_content_via_client(
    client: Any,
    ws_sid: str,
    to_id: str,
    content: str,
) -> dict[str, Any]:
    """通过 WS 客户端逐条发送回复内容（支持 ###### 多消息拆分）。"""
    parts = _split_reply_messages(content)
    if not parts:
        return {"code": 400, "error": "回复内容为空"}
    for part in parts:
        result = await client.send_text_message(ws_sid, to_id, part, persist=False)
        if not isinstance(result, dict) or result.get("code") != 200:
            return result if isinstance(result, dict) else {"code": 500, "error": "发送失败"}
    return {"code": 200}


# ============================================================
# ★ 敏感词过滤：商品获取节点提取完成后，调用 Java core-api 的敏感词策略
#   过滤命中敏感词的商品，避免发布含敏感词的文案导致闲鱼账号封禁。
#   scene=product 的敏感词由后台「敏感词策略」模块维护。
# ============================================================

async def _fetch_product_sensitive_words() -> list[str]:
    """从 Java core-api 拉取 scene=product 的敏感词列表。

    失败时返回空列表并记录警告（不阻塞主流程，但调用方需意识到过滤未生效）。
    """
    import httpx as _httpx
    base = (settings.core_api_base_url or "").rstrip("/")
    if not base:
        logger.warning("[SENSITIVE] core_api_base_url 未配置，敏感词过滤跳过")
        return []
    headers = {"Accept": "application/json"}
    if settings.effective_internal_api_token:
        headers["X-Internal-Token"] = settings.effective_internal_api_token
    try:
        async with _httpx.AsyncClient(timeout=8.0, follow_redirects=False, trust_env=False) as client:
            resp = await client.get(
                f"{base}/open-api/internal/sensitive-words",
                headers=headers,
                params={"scene": "product"},
            )
            if resp.status_code != 200:
                logger.warning("[SENSITIVE] 拉取敏感词失败 status=%s", resp.status_code)
                return []
            data = resp.json()
    except Exception as e:
        _log_runtime_failure("fetch_sensitive_words", e)
        return []
    # Result 包装：{code, msg, data:{scene,count,words,records}}
    payload = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
    if not isinstance(payload, dict):
        return []
    words = payload.get("words") or []
    if not isinstance(words, list):
        return []
    # 规范化：去空白、去重（小写）、仅保留非空字符串
    normalized: list[str] = []
    seen: set[str] = set()
    for w in words:
        ws = _text(w).strip()
        if ws and ws.lower() not in seen:
            seen.add(ws.lower())
            normalized.append(ws)
    logger.info("[SENSITIVE] 拉取敏感词成功 count=%d", len(normalized))
    return normalized


async def _fetch_ai_cs_sensitive_words() -> list[str]:
    """从 Java core-api 拉取 AI 客服自动回复使用的敏感词列表。

    复用 scene=polish 场景（含 scene=all）：polish 语义为「AI 生成文本时不可携带的词」，
    与 AI 客服自动回复场景一致。失败时返回空列表（不阻塞自动回复，但敏感词限制不生效）。
    """
    import httpx as _httpx
    base = (settings.core_api_base_url or "").rstrip("/")
    if not base:
        logger.warning("[AI_CS_SENSITIVE] core_api_base_url 未配置，敏感词注入跳过")
        return []
    headers = {"Accept": "application/json"}
    if settings.effective_internal_api_token:
        headers["X-Internal-Token"] = settings.effective_internal_api_token
    try:
        async with _httpx.AsyncClient(timeout=8.0, follow_redirects=False, trust_env=False) as client:
            resp = await client.get(
                f"{base}/open-api/internal/sensitive-words",
                headers=headers,
                params={"scene": "polish"},
            )
            if resp.status_code != 200:
                logger.warning("[AI_CS_SENSITIVE] 拉取敏感词失败 status=%s", resp.status_code)
                return []
            data = resp.json()
    except Exception as e:
        _log_runtime_failure("fetch_ai_cs_sensitive_words", e)
        return []
    payload = data.get("data") if isinstance(data, dict) and isinstance(data.get("data"), dict) else data
    if not isinstance(payload, dict):
        return []
    words = payload.get("words") or []
    if not isinstance(words, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for w in words:
        ws = _text(w).strip()
        if ws and ws.lower() not in seen:
            seen.add(ws.lower())
            normalized.append(ws)
    logger.info("[AI_CS_SENSITIVE] 拉取敏感词成功 count=%d", len(normalized))
    return normalized


async def _record_workflow_image_history(
    *,
    tenant_id: int,
    user_id: int,
    request_id: str,
    model: str,
    prompt: str,
    size: str,
    image_url: str,
    method: str,
    workflow_id: Optional[int],
    workflow_execution_id: Optional[int],
    workflow_node_key: str,
    status: str,
    error_message: str,
) -> None:
    """工作流生图结果回传到 Java core-api 落库（fire-and-forget）。

    Java 端 ImageGenerationService.recordExternalGenerationHistory 会写入
    opportunity_image_history 表，source='workflow'，供前台「工作流 → 图片生成记录」页面查询。

    失败时仅记录警告，不抛出异常（不阻塞工作流主流程）。
    """
    import httpx as _httpx
    base = (settings.core_api_base_url or "").rstrip("/")
    if not base:
        logger.debug("[WORKFLOW_IMG_HISTORY] core_api_base_url 未配置，跳过回传")
        return
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.effective_internal_api_token:
        headers["X-Internal-Token"] = settings.effective_internal_api_token
    payload = {
        "tenantId": tenant_id,
        "userId": user_id,
        "requestId": request_id,
        "model": model,
        "prompt": prompt,
        "size": size,
        "imageUrl": image_url,
        "method": method,
        "source": "workflow",
        "workflowId": workflow_id,
        "workflowExecutionId": workflow_execution_id,
        "workflowNodeKey": workflow_node_key,
        "status": status,
        "errorMessage": error_message,
    }
    try:
        async with _httpx.AsyncClient(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            resp = await client.post(
                f"{base}/open-api/internal/workflow/image-history/record",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning(
                    "[WORKFLOW_IMG_HISTORY] 回传失败 status=%s model=%s",
                    resp.status_code, model,
                )
    except Exception as e:
        _log_runtime_failure("record_workflow_image_history", e)


async def _save_publish_draft(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: Optional[int],
    workflow_id: Optional[int],
    execution_id: Optional[int],
    workflow_name: str,
    node_key: str,
    account_id: Optional[int],
    title: str,
    price: str,
    description: str,
    cover_pic: str,
    image_urls: list,
    category: str,
    stock: int,
    location: Optional[dict],
    raw_payload: Optional[dict],
    source_item_id: str,
    source_title_hash: str,
    initial_status: str = "publishing",
    error_message: str = "",
) -> Optional[int]:
    """保存发布草稿到 workflow_goods_draft 表，返回草稿ID（fire-and-forget）。

    用于"发布前先存草稿"：无论后续发布成功或失败，草稿记录都保留，
    便于用户在前台「工作流 → 商品草稿箱」页面查看与重试发布。
    """
    try:
        result = await db.execute(
            text("""
                INSERT INTO workflow_goods_draft(
                    tenant_id, user_id, workflow_id, workflow_execution_id, workflow_name,
                    node_key, account_id, title, price, description, cover_pic, image_urls,
                    category, stock, location, raw_payload, source_item_id, source_title_hash,
                    publish_status, publish_error_message, publish_attempt_count,
                    created_time, updated_time, deleted
                ) VALUES (
                    :t, :u, :wid, :eid, :wn, :nk, :aid, :title, :price, :desc, :cover, :imgs,
                    :cat, :stock, :loc, :raw, :si, :sh, :ps, :err, 1,
                    NOW(), NOW(), 0
                )
            """),
            {
                "t": tenant_id, "u": user_id, "wid": workflow_id, "eid": execution_id,
                "wn": workflow_name or None, "nk": node_key or None,
                "aid": account_id, "title": (title or "")[:500], "price": price,
                "desc": description, "cover": cover_pic,
                "imgs": json.dumps(image_urls or [], ensure_ascii=False),
                "cat": category, "stock": stock,
                "loc": json.dumps(location, ensure_ascii=False) if location else None,
                "raw": json.dumps(raw_payload, ensure_ascii=False) if raw_payload else None,
                "si": source_item_id, "sh": source_title_hash,
                "ps": initial_status,
                "err": error_message[:2000] if error_message else None,
            },
        )
        await db.commit()
        return result.lastrowid
    except Exception as exc:
        await db.rollback()
        _log_runtime_failure("save_publish_draft", exc)
        return None


async def _update_publish_draft_status(
    db: AsyncSession,
    *,
    draft_id: Optional[int],
    status: str,
    xianyu_goods_id: str = "",
    error_message: str = "",
) -> None:
    """更新草稿发布状态（fire-and-forget，失败仅警告）。

    状态机：publishing → published / failed
    """
    if not draft_id:
        return
    try:
        await db.execute(
            text("""
                UPDATE workflow_goods_draft
                SET publish_status=:ps,
                    xianyu_goods_id=CASE WHEN :gid != '' THEN :gid ELSE xianyu_goods_id END,
                    publish_error_message=:err,
                    publish_time=CASE WHEN :ps IN ('published','failed') THEN NOW() ELSE publish_time END,
                    updated_time=NOW()
                WHERE id=:id
            """),
            {
                "ps": status,
                "gid": xianyu_goods_id or "",
                "err": error_message[:2000] if error_message else None,
                "id": draft_id,
            },
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        _log_runtime_failure("update_publish_draft_status", exc)


async def _finalize_publish_draft_from_result(
    db: AsyncSession,
    *,
    draft_id: Optional[int],
    publish_result: dict,
) -> None:
    """根据 publish_result 更新草稿最终状态（fire-and-forget）。

    映射规则：
    - status=published → draft status=published，记录 xianyu_goods_id
    - status=failed/skipped_no_ai_image/skipped_duplicate/skipped → draft status=failed，记录 error_message
    """
    if not draft_id:
        return
    status = _text(publish_result.get("status"))
    if status == "published":
        await _update_publish_draft_status(
            db, draft_id=draft_id, status="published",
            xianyu_goods_id=_text(publish_result.get("goods_id", "")),
        )
    elif status in ("failed", "skipped_no_ai_image", "skipped_duplicate", "skipped"):
        await _update_publish_draft_status(
            db, draft_id=draft_id, status="failed",
            error_message=_text(publish_result.get("error", "")),
        )


async def _save_legacy_publish_draft(
    db: AsyncSession,
    *,
    context: dict,
    tenant_id: int,
    account_id: Optional[int],
    is_fish_shop: bool,
    category: str,
    address,
    p: dict,
    img_url: str,
    image_urls: list,
    publish_result: dict,
    node_key: str = "PUBLISH",
) -> None:
    """fire-and-forget: 为 legacy PUBLISH 节点单条发布结果保存草稿（含最终状态）。

    与 _publish_single_item 的两阶段（publishing → published/failed）不同，
    legacy PUBLISH 节点在结果已知后批量保存草稿，直接写入最终状态。
    自动从 p 推导 source_item_id / source_title_hash，避免在每个调用点重复计算。

    用于「无论发布成功或失败都存入草稿箱」的约束：在 legacy PUBLISH 节点的
    每个 publish_results.append({...}) 后调用，确保所有发布结果都有对应草稿记录。
    """
    import hashlib as _hashlib
    try:
        _status = _text(publish_result.get("status"))
        # 映射到草稿状态：published 保留，其余（failed/skipped_*/dry_run）统一为 failed
        _draft_status = "published" if _status == "published" else "failed"
        _err_msg = ""
        if _draft_status == "failed":
            _err_msg = _text(publish_result.get("error", "")) or _status

        _source_item_id = _text(p.get("itemId", ""))
        _source_title_raw = _text(p.get("title", ""))
        _source_title_hash = (
            _hashlib.md5(_source_title_raw.strip().lower().encode("utf-8")).hexdigest()
            if _source_title_raw else ""
        )

        _draft_id = await _save_publish_draft(
            db=db, tenant_id=tenant_id,
            user_id=_safe_int(context.get("__user_id__"), 0) or None,
            workflow_id=context.get("__workflow_id__"),
            execution_id=context.get("__execution_id__"),
            workflow_name=_text(context.get("__workflow_name__")),
            node_key=node_key,
            account_id=account_id,
            title=_text(p.get("title", "")),
            price=_text(p.get("price", "1")) or "1",
            description=_text(p.get("description", "")),
            cover_pic=img_url or "",
            image_urls=image_urls or [],
            category=category,
            stock=999 if is_fish_shop else 1,
            location=address if isinstance(address, dict) else None,
            raw_payload=p,
            source_item_id=_source_item_id,
            source_title_hash=_source_title_hash,
            initial_status=_draft_status,
            error_message=_err_msg,
        )
        # published 状态需要回写 xianyu_goods_id（_save_publish_draft 未填该字段）
        if _draft_id and _draft_status == "published":
            await _update_publish_draft_status(
                db, draft_id=_draft_id, status="published",
                xianyu_goods_id=_text(publish_result.get("goods_id", "")),
            )
    except Exception as _draft_err:
        _log_runtime_failure("legacy_publish_draft", _draft_err)


def _item_hits_sensitive_word(item: dict, words: list[str]) -> str | None:
    """检查商品标题/描述/卖家是否命中敏感词。命中返回敏感词原文，否则返回 None。

    大小写不敏感，子串包含即命中（与 Java SensitiveWordService.findHits 行为一致）。
    """
    if not words:
        return None
    title = _text(item.get("title", "")).lower()
    desc = _text(item.get("description", "")).lower()
    seller = _text(item.get("seller", "")).lower()
    for w in words:
        wl = w.lower()
        if not wl:
            continue
        if wl in title or wl in desc or wl in seller:
            return w
    return None


def _filter_items_by_sensitive_words(
    items: list[dict], words: list[str], *, tag: str = "PRODUCT_FETCH",
) -> tuple[list[dict], list[dict]]:
    """从商品列表中过滤掉命中敏感词的商品。返回 (kept, removed)。

    words 为空时直接返回原列表（不变更），不记录日志。
    """
    if not words:
        return list(items), []
    kept: list[dict] = []
    removed: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        hit = _item_hits_sensitive_word(item, words)
        if hit:
            removed.append(item)
            logger.warning(
                "[%s/SENSITIVE] 移除命中敏感词的商品 title=%r hitWord=%s itemId=%s",
                tag,
                _text(item.get("title", ""))[:80],
                hit,
                _text(item.get("itemId", "")),
            )
        else:
            kept.append(item)
    if removed:
        logger.info("[%s/SENSITIVE] 敏感词过滤完成 输入=%d 保留=%d 移除=%d",
                    tag, len(items), len(kept), len(removed))
    return kept, removed


def _normalize_external_uid(value: Any) -> str:
    raw = _text(value).strip()
    return raw[:-8] if raw.endswith("@goofish") else raw


def _resolve_effective_buyer_id(payload: dict[str, Any]) -> str:
    candidates = [
        _text(payload.get("buyerId") or payload.get("buyer_id") or payload.get("fromUserId")).strip(),
        _text(payload.get("peerUserId") or payload.get("peer_user_id") or payload.get("externalBuyerId")).strip(),
        _text(payload.get("receiverUserId") or payload.get("receiver_user_id")).strip(),
    ]
    seller_uid = _normalize_external_uid(
        payload.get("sellerExternalUid")
        or payload.get("ownerUserId")
        or payload.get("sellerUserId")
        or payload.get("accountExternalUid")
    )

    for candidate in candidates:
        if not candidate:
            continue
        if seller_uid and _normalize_external_uid(candidate) == seller_uid:
            continue
        return candidate

    return ""


async def _resolve_effective_buyer_id_from_sid(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    payload: dict[str, Any],
) -> str:
    buyer_id = _resolve_effective_buyer_id(payload).strip()
    if buyer_id:
        return buyer_id

    sid = _text(payload.get("sId") or payload.get("sid") or payload.get("sessionId") or payload.get("session_id")).strip()
    if sid.startswith("sid:"):
        sid = sid[4:]
    if sid.endswith("@goofish"):
        sid = sid[:-8]
    if not sid:
        return ""

    seller_uid = _normalize_external_uid(
        payload.get("sellerExternalUid")
        or payload.get("ownerUserId")
        or payload.get("sellerUserId")
        or payload.get("accountExternalUid")
    )

    message_row = (await db.execute(text("""
        SELECT sender_user_id, peer_external_uid, receiver_user_id
        FROM xianyu_chat_message
        WHERE tenant_id = :tenant_id
          AND account_id = :account_id
          AND deleted = 0
          AND s_id COLLATE utf8mb4_unicode_ci IN (:sid, :sid_goofish)
          AND (
              (sender_user_id IS NOT NULL AND sender_user_id != '')
              OR (peer_external_uid IS NOT NULL AND peer_external_uid != '')
              OR (receiver_user_id IS NOT NULL AND receiver_user_id != '')
          )
        ORDER BY id DESC
        LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "sid": sid,
        "sid_goofish": f"{sid}@goofish",
    })).mappings().first()
    if message_row:
        for key in ("sender_user_id", "peer_external_uid", "receiver_user_id"):
            candidate = _text(message_row.get(key)).strip()
            if candidate and (not seller_uid or _normalize_external_uid(candidate) != seller_uid):
                return candidate

    conv_row = (await db.execute(text("""
        SELECT external_buyer_id, peer_external_uid
        FROM xianyu_conversation
        WHERE tenant_id = :tenant_id
          AND account_id = :account_id
          AND deleted = 0
          AND (
              peer_key COLLATE utf8mb4_unicode_ci IN (:sid_key, :sid_key_goofish)
              OR external_buyer_id COLLATE utf8mb4_unicode_ci IN (:sid, :sid_goofish, :sid_key, :sid_key_goofish)
          )
        ORDER BY id DESC
        LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "sid": sid,
        "sid_goofish": f"{sid}@goofish",
        "sid_key": f"sid:{sid}",
        "sid_key_goofish": f"sid:{sid}@goofish",
    })).mappings().first()
    if conv_row:
        for key in ("external_buyer_id", "peer_external_uid"):
            candidate = _text(conv_row.get(key)).strip()
            if candidate and not candidate.startswith("sid:") and (not seller_uid or _normalize_external_uid(candidate) != seller_uid):
                return candidate

    return ""


def _collect_normalized_party_ids(*values: Any) -> set[str]:
    identifiers: set[str] = set()
    for value in values:
        normalized = _normalize_external_uid(value)
        if normalized:
            identifiers.add(normalized)
    return identifiers


def _normalize_sid_value(value: Any) -> str:
    sid = _text(value).strip()
    if sid.startswith("sid:"):
        sid = sid[4:]
    if sid.endswith("@goofish"):
        sid = sid[:-8]
    return sid


def _parse_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _extract_live_conversation_role_hints(item: dict[str, Any]) -> dict[str, Any]:
    conversation = _parse_mapping(item.get("singleChatUserConversation") or item)
    single_conversation = _parse_mapping(conversation.get("singleChatConversation"))
    extension = _parse_mapping(single_conversation.get("extension"))

    owner_user_id = _text(extension.get("ownerUserId")).strip()
    item_seller_id = _text(extension.get("itemSellerId")).strip()
    group_owner_id = _text(extension.get("groupOwnerId")).strip()

    return {
        "sid": _normalize_sid_value(
            single_conversation.get("cid")
            or conversation.get("cid")
            or item.get("cid")
        ),
        "goodsId": _text(
            extension.get("itemId")
            or extension.get("goodsId")
            or extension.get("item_id")
        ).strip(),
        "ownerUserId": owner_user_id,
        "itemSellerId": item_seller_id,
        "groupOwnerId": group_owner_id,
        "sellerIds": _collect_normalized_party_ids(
            owner_user_id,
            item_seller_id,
            group_owner_id,
        ),
    }


async def _resolve_account_chat_role_from_live_conversations(
    account_id: int,
    payload: dict[str, Any],
    account_external_uid: str,
) -> str:
    sid = _normalize_sid_value(
        payload.get("sId")
        or payload.get("sid")
        or payload.get("sessionId")
        or payload.get("session_id")
    )
    goods_id = _text(payload.get("goodsId") or payload.get("itemId") or payload.get("xyGoodsId")).strip()
    if not sid and not goods_id:
        return ""

    try:
        from .ws_client import ws_manager

        client = ws_manager.get_client(account_id)
        if not client or not getattr(client, "is_connected", False):
            return ""

        body = await asyncio.wait_for(
            client.list_conversations(start_timestamp=None, limit=20),
            timeout=3.0,
        )
    except Exception as exc:
        _log_runtime_failure("resolve_live_conversation_role", exc)
        return ""

    items = body.get("userConvs", []) if isinstance(body, dict) else []
    for item in items:
        hints = _extract_live_conversation_role_hints(item)
        seller_ids = hints.get("sellerIds") or set()
        if not seller_ids:
            continue
        if sid and hints.get("sid") == sid:
            return "seller" if account_external_uid in seller_ids else "buyer"
        if goods_id and hints.get("goodsId") == goods_id:
            return "seller" if account_external_uid in seller_ids else "buyer"

    return ""


async def _resolve_account_chat_role(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    payload: dict[str, Any],
) -> str:
    account_external_uid = _normalize_external_uid(
        payload.get("sellerExternalUid")
        or payload.get("accountExternalUid")
        or payload.get("currentAccountExternalUid")
        or payload.get("currentUserId")
    )
    if not account_external_uid:
        return ""

    seller_ids = _collect_normalized_party_ids(
        payload.get("ownerUserId"),
        payload.get("sellerUserId"),
        payload.get("itemSellerId"),
        payload.get("groupOwnerId"),
        payload.get("itemOwnerId"),
        payload.get("goodsOwnerId"),
    )
    if seller_ids:
        return "seller" if account_external_uid in seller_ids else "buyer"

    goods_id = _text(payload.get("goodsId") or payload.get("itemId") or payload.get("xyGoodsId")).strip()
    if goods_id:
        goods_row = (await db.execute(text("""
            SELECT account_id
            FROM xianyu_goods
            WHERE tenant_id = :tenant_id
              AND deleted = 0
              AND (external_goods_id = :goods_id OR goods_id = :goods_id)
            ORDER BY CASE WHEN account_id = :account_id THEN 0 ELSE 1 END, id DESC
            LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "goods_id": goods_id,
        })).mappings().first()
        if goods_row:
            goods_account_id = _safe_int(goods_row.get("account_id"))
            if goods_account_id == account_id:
                return "seller"
            if goods_account_id:
                return "buyer"

    live_conversation_role = await _resolve_account_chat_role_from_live_conversations(
        account_id=account_id,
        payload=payload,
        account_external_uid=account_external_uid,
    )
    if live_conversation_role:
        return live_conversation_role

    return ""


def _strip_shop_watermark(title: str, body: str) -> tuple[str, str]:
    """兜底清洗：去除润色后标题/正文中可能残留的其他店铺标识。

    覆盖：
    - 店铺名后缀（XX电玩社/XX工作室/XX数码/XX小店/XX专营店/XX官方店/XX旗舰店 等）
    - 关注引导（关注店铺/点我头像/进店/收藏店铺）
    - 联系方式（QQ:123/微信:xxx/微信号/加微信/联系QQ）
    - 网址链接（http/https/url.cn）
    - 店铺历史数据（XX人想要/XX人收藏/XX人付款/XX人已购）
    - 价格符号残留（¥/￥/RMB）
    """
    # 店铺名后缀模式（两字以上后缀）
    shop_suffix_patterns = [
        r'[\s,，]*[\w\u4e00-\u9fa5]{2,10}?(电玩社|工作室|数码店|小店|专营店|官方店|旗舰店|店铺|代购店|商城)',
        r'[\s,，]*[\w\u4e00-\u9fa5]{2,10}?(小铺|铺子|数码|小店|商店)',
    ]
    # 关注引导
    follow_patterns = [
        r'[，,。\s]*关注[我们我]?[的店铺]+[，,。.]?\s*',
        r'[，,。\s]*点[击我]?头像[进点]店[，,。.]?\s*',
        r'[，,。\s]*进店[查看了解选购]\S{0,15}[，,。.]?\s*',
        r'[，,。\s]*收藏[本该店]?店铺?[，,。.]?\s*',
        r'[，,。\s]*欢迎?光临[本我]?[的店]?[，,。.]?\s*',
    ]
    # 联系方式
    contact_patterns = [
        r'[，,。\s]*(?:QQ|微信|wechat|vx|wx|V信)[：:=\-]?\s*\w{4,30}',
        r'[，,。\s]*(?:联系|加)\s*(?:QQ|微信|wechat|vx|wx)\s*\w{0,30}',
        r'[，,。\s]*微信号[：:=]?\s*\w{4,30}',
    ]
    # 店铺历史数据
    stats_patterns = [
        r'[\s,，]*\d+\s*(?:人|个)?(?:想要|收藏|付款|已购|人购买|人想要)',
        r'[\s,，]*\d+\s*人\s*(?:想要|收藏|已付款|购买)',
        r'[\s,，]*\d+\s*人小刀价',
        r'[\s,，]*小刀价',
    ]
    # ★ 英文店铺水印（如 LateSunday、LateSunda 等）
    shop_english_watermark = [
        r'[\s,，]*LateSunda(?:y|a)?',
        r'[\s,，]*RainyNightGaming',
    ]
    # ★ "口语化：" 前缀（爬取残留）
    colloquial_prefix = [
        r'口语化[：:]\s*',
    ]
    # 网址链接
    url_patterns = [
        r'https?://\S+',
        r'url\.cn/\S+',
        r'短链\.com/\S+',
    ]

    def _clean(text: str) -> str:
        if not text:
            return text
        all_patterns = (
            shop_suffix_patterns + follow_patterns + contact_patterns
            + stats_patterns + shop_english_watermark + colloquial_prefix + url_patterns
        )
        for pat in all_patterns:
            text = re.sub(pat, '', text, flags=re.IGNORECASE)
        # 去除货币符号残留
        text = re.sub(r'[¥￥]\s*', '', text)
        # 去除多余空格和标点
        text = re.sub(r'[\s,，]{2,}', ' ', text).strip(' ，,。.')
        return text.strip()

    return _clean(title), _clean(body)


def _parse_keywords(raw: Any) -> list[str]:
    if raw is None:
        return []
    value = str(raw).strip()
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in re.split(r"[,，\n\r\t]+", value) if x.strip()]


def _match_image_prompt_category(title: str, description: str, category_prompts: list[dict[str, Any]]) -> dict[str, Any] | None:
    category_prompts = _prepare_image_prompt_category_configs(category_prompts)
    combined = f"{_text(title)} {_text(description)}".lower()
    best_match: dict[str, Any] | None = None
    best_score = 0
    for item in category_prompts or []:
        keywords = _text(item.get("matchKeywords") or item.get("keywords") or item.get("matchs"))
        if not keywords.strip():
            continue
        score = 0
        for keyword in re.split(r"[,，\n\r\s]+", keywords):
            kw = keyword.strip().lower()
            if not kw:
                continue
            if kw in combined:
                score += max(2, len(kw))
        if score > best_score:
            best_score = score
            best_match = item
    return best_match if best_score > 0 else None


def _render_image_prompt_template(template: str, title: str, description: str) -> str:
    raw = _text(template)
    if not raw.strip():
        return ""
    return raw.replace("{{TITLE}}", _text(title).strip()).replace("{{CONTENT}}", _text(description).strip()[:3000]).strip()


FINAL_IMAGE_PROMPT_SUFFIX = (
    "补充要求：直接输出可上架的最终商品主图成品，不要只生成背景底图，不要依赖后期统一叠字模板。"
    "允许画面中出现少量清晰中文，但只保留主标题和2到3个短卖点。"
    "不要大面积留白，不要中下部灰白渐变留空，不要顶部整条灰色标题栏，不要右上角红色角标，不要底部红黄横条，不要固定套版感。"
    "不要店铺名、平台UI、头像、导航栏、二维码、水印、联系方式。"
)


def _compose_final_image_prompt(template: str, title: str, description: str) -> str:
    prompt = _render_image_prompt_template(template, title, description)
    if not prompt:
        return ""

    template_text = _text(template)
    if "{{TITLE}}" not in template_text and _text(title).strip():
        prompt = f"{prompt}\n\n商品标题：{_text(title).strip()}"
    if "{{CONTENT}}" not in template_text and _text(description).strip():
        prompt = f"{prompt}\n商品正文：{_text(description).strip()[:1200]}"

    return f"{prompt}\n\n{FINAL_IMAGE_PROMPT_SUFFIX}".strip()


def _image_prompt_sort_number(value: Any, fallback: int) -> int:
    text = _text(value).strip()
    if not text:
        return fallback
    try:
        return int(re.sub(r"[^\d-]", "", text) or fallback)
    except Exception:
        return fallback


def _prepare_image_prompt_category_configs(category_prompts: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for item in category_prompts or []:
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        enabled = payload.get("enabled")
        status = _text(payload.get("status") or "正常").strip().lower()
        if enabled in (False, 0, "0", "false") or status in {"禁用", "停用", "disabled", "false", "0"}:
            continue
        prepared.append(payload)
    prepared.sort(key=lambda item: (
        _image_prompt_sort_number(item.get("sortOrder") or item.get("sort"), 999999),
        _image_prompt_sort_number(item.get("id"), 999999999),
    ))
    return prepared


DEFAULT_IMAGE_PROMPT_FALLBACK = (
    "生成1张适合闲鱼/淘宝风格的中国电商商品主图（1:1正方形）。"
    "要求：不是平台截图，不要店铺名、头像、导航栏、二维码、水印、联系方式。"
    "画面必须只有一个明确主视觉，主体大、居中、易识别，整体高对比、强吸睛、适合手机缩略图点击。"
    "采用中文电商广告封面风格，可包含简短有力的大标题和2到3个短卖点标签，但不要堆满小字。"
    "背景简洁有层次，可用深色或亮色渐变搭配高饱和点缀，突出商品价值与成交感。"
    "不要复杂场景，不要3D渲染感，不要赛博霓虹，不要艺术海报感，要像高点击率商品主图。"
)


def _extract_image_prompt_category_key(ai_content: str, category_prompts: list[dict[str, Any]]) -> str:
    raw = _text(ai_content).strip()
    if not raw:
        return ""
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    candidates: dict[str, str] = {}
    for item in category_prompts:
        key = _text(item.get("categoryKey") or item.get("name")).strip()
        if key:
            candidates[key.lower()] = key
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            for field in ("categoryKey", "key", "category", "category_key"):
                value = _text(parsed.get(field)).strip().lower()
                if value in candidates:
                    return candidates[value]
    except Exception:
        pass
    lowered = cleaned.lower()
    if lowered in candidates:
        return candidates[lowered]
    for key in sorted(candidates.keys(), key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9_]){re.escape(key)}(?![a-z0-9_])", lowered):
            return candidates[key]
    return ""


async def _match_image_prompt_category_with_ai(
    title: str,
    description: str,
    category_prompts: list[dict[str, Any]],
    *,
    tenant_id: int,
    user_id: int,
    request_identity: str = "",
    generate_text_func=generate_text,
    scene: str = "workflow_image_prompt_select",
) -> dict[str, Any] | None:
    category_prompts = _prepare_image_prompt_category_configs(category_prompts)
    options: list[dict[str, str]] = []
    for item in category_prompts:
        key = _text(item.get("categoryKey") or item.get("name")).strip()
        if not key:
            continue
        options.append({
            "categoryKey": key,
            "name": _text(item.get("name") or key).strip(),
            "matchKeywords": _text(item.get("matchKeywords") or item.get("keywords") or "").strip(),
        })
    if not options:
        return None
    options_text = "\n".join(
        f"- categoryKey={item['categoryKey']} | name={item['name']} | keywords={item['matchKeywords'][:120]}"
        for item in options
    )
    system_prompt = (
        "你是闲鱼商品主图类目提示词选择器。"
        "你的任务是根据商品标题和正文，从给定候选类目中选择最适合用于商品封面设计提示词的 categoryKey。"
        "必须只从候选列表中选择，不要自造类目。"
        "请严格返回 JSON，例如 {\"categoryKey\":\"game_cdk\"}。"
        "如果实在无法判断，就返回 {\"categoryKey\":\"\"}。"
    )
    user_prompt = (
        f"商品标题：{_text(title).strip()}\n"
        f"商品正文：{_text(description).strip()[:1200]}\n\n"
        f"候选类目：\n{options_text}"
    )
    if int(tenant_id or 0) <= 0 or int(user_id or 0) <= 0:
        raise AiBillingError("image prompt selector billing identity is missing")
    billing_request_id = build_stable_request_id(
        scene,
        tenant_id,
        user_id,
        request_identity or f"{title}\n{description}",
        options_text,
    )
    try:
        await precheck_ai_usage({
            "tenantId": tenant_id,
            "userId": user_id,
            "scene": scene,
            "providerName": "default",
            "modelName": "default",
            "modelType": "chat",
            "promptTokens": estimate_text_tokens(user_prompt),
            "completionTokens": 0,
            "requestId": billing_request_id,
        })
        ai_result = await generate_text_func(
            scene,
            system_prompt,
            user_prompt,
            0.1,
            request_id=billing_request_id,
        )
    except AiBillingError as exc:
        # ★ 计费预检查/调用失败时降级到关键词匹配，避免终止整个生图流程。
        #   提示词选择是生图的增强环节，计费不可用时回退到非 AI 的关键词匹配
        #   比直接失败整个工作流（导致 30 张图全部不生成）更合理。
        _log_runtime_failure("select_image_prompt_category_billing", exc)
        return None
    except Exception as exc:
        _log_runtime_failure("select_image_prompt_category", exc)
        return None
    if not ai_result or not ai_result.get("ok"):
        return None
    ai_content = _text(ai_result.get("content"))
    try:
        await charge_text_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            scene=scene,
            provider_name=_text(ai_result.get("provider")) or "default",
            model_name=_text(ai_result.get("model")) or "default",
            prompt=user_prompt,
            completion=ai_content,
            request_id=billing_request_id,
            raw_usage=ai_result.get("usage") or {},
        )
    except AiBillingError as exc:
        # 扣费失败时也降级：AI 已调用但扣费失败，记录失败但继续工作流
        _log_runtime_failure("charge_image_prompt_category", exc)
        return None
    selected_key = _extract_image_prompt_category_key(ai_content, category_prompts)
    if not selected_key:
        return None
    for item in category_prompts:
        if _text(item.get("categoryKey") or item.get("name")).strip().lower() == selected_key.lower():
            return item
    return None


def _resolve_image_prompt_for_item(
    prompt_mode: str,
    custom_prompt: str,
    fallback_prompt: str,
    title: str,
    description: str,
    category_prompts: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    mode = _text(prompt_mode).strip().lower() or "default"
    if mode == "custom" and _text(custom_prompt).strip():
        return _render_image_prompt_template(custom_prompt, title, description), None
    matched = _match_image_prompt_category(title, description, category_prompts)
    if matched:
        template = _text(matched.get("promptTemplate") or matched.get("template") or matched.get("prompt"))
        if template.strip():
            return _render_image_prompt_template(template, title, description), matched
    return _render_image_prompt_template(fallback_prompt, title, description), None


async def _resolve_image_prompt_for_item_with_ai(
    prompt_mode: str,
    custom_prompt: str,
    fallback_prompt: str,
    title: str,
    description: str,
    category_prompts: list[dict[str, Any]],
    *,
    tenant_id: int,
    user_id: int,
    request_identity: str = "",
    generate_text_func=generate_text,
    scene: str = "workflow_image_prompt_select",
) -> tuple[str, dict[str, Any] | None]:
    mode = _text(prompt_mode).strip().lower() or "default"
    if mode == "custom" and _text(custom_prompt).strip():
        return _render_image_prompt_template(custom_prompt, title, description), None
    ai_matched = await _match_image_prompt_category_with_ai(
        title,
        description,
        category_prompts,
        tenant_id=tenant_id,
        user_id=user_id,
        request_identity=request_identity,
        generate_text_func=generate_text_func,
        scene=scene,
    )
    if ai_matched:
        template = _text(ai_matched.get("promptTemplate") or ai_matched.get("template") or ai_matched.get("prompt"))
        if template.strip():
            return _render_image_prompt_template(template, title, description), ai_matched
    return _resolve_image_prompt_for_item(
        prompt_mode=prompt_mode,
        custom_prompt=custom_prompt,
        fallback_prompt=fallback_prompt,
        title=title,
        description=description,
        category_prompts=category_prompts,
    )


def _workflow_search_fast(keyword: str, page: int, page_size: int, cookie_str: str) -> list[dict]:
    """工作流快速搜索：直调 MTOP API（用原始 Cookie，不刷新 _m_h5_tk）。

    遵守项目硬约束：商品搜索接口不得刷新 _m_h5_tk，刷新会触发 Baxia 风控。
    成功返回标准化 items 列表，触发风控抛异常由上层降级到慢速搜索。
    """
    search_data = {
        "keyword": keyword,
        "pageNumber": page,
        "rowsPerPage": page_size,
        "fromFilter": False,
        "sortValue": "",
        "sortField": "",
        "searchReqFromPage": "pcSearch",
        "customDistance": "",
        "gps": "",
        "customGps": "",
        "propValueStr": {},
        "extraFilterValue": "{}",
        "userPositionJson": "{}",
    }
    response = _mtop_search_request(
        cookie_str, SEARCH_MTOP_API, search_data,
        extra_form={"sessionOption": "AutoLoginOnly", "accountSite": "xianyu"},
    )
    ret = response.get("ret", [])
    ret_msg = str(ret[0]) if isinstance(ret, list) and ret else str(ret)
    # 检测风控/Token失效，抛异常让上层降级到慢速搜索
    if _XIANYU_RGV587 in ret_msg:
        raise PublicRuntimeError("PRODUCT_SEARCH_RATE_LIMITED", "商品搜索触发平台验证，请稍后重试")
    if _XIANYU_TOKEN_EXPIRED in ret_msg or _XIANYU_TOKEN_EXPIRED_ALIAS in ret_msg:
        raise PublicRuntimeError("ACCOUNT_AUTH_UNAVAILABLE", "账号登录状态不可用，请重新登录")
    if "FAIL_SYS_USER_VALIDATE" in ret_msg:
        raise PublicRuntimeError("PRODUCT_SEARCH_RATE_LIMITED", "商品搜索触发平台验证，请稍后重试")
    if "SUCCESS" not in ret_msg:
        raise PublicRuntimeError("PRODUCT_SEARCH_UNAVAILABLE", "商品搜索服务暂时不可用，请稍后重试")

    result_data = response.get("data", {})
    if not isinstance(result_data, dict):
        result_data = {}
    raw_items = (
        result_data.get("resultList")
        or result_data.get("items")
        or result_data.get("itemList")
        or result_data.get("cardList")
        or []
    )
    normalized = []
    for raw_item in raw_items:
        if isinstance(raw_item, dict):
            item = _normalize_mtop_search_item(raw_item)
            if item.get("title") or item.get("itemId"):
                normalized.append(item)
    return normalized


def _workflow_search_slow(keyword: str, page: int, page_size: int, tenant_id: int, cookie_str: str) -> list[dict]:
    """工作流慢速搜索：调用 crawler-service (Playwright 浏览器) 搜索闲鱼商品。

    浏览器方式自动处理 Baxia 反爬令牌，避免 MTOP API 直调被风控拦截。
    """
    import requests as _requests

    crawler_url = f"{(os.getenv('CRAWLER_SERVICE_URL') or 'http://localhost:3001').rstrip('/')}/api/goofish/search"
    headers = {
        "X-Internal-Token": settings.effective_internal_api_token,
        "X-Internal-Tenant-Id": str(tenant_id),
    }
    payload = {
        "q": keyword,
        "page": page,
        "pageSize": page_size,
    }
    if cookie_str:
        payload["cookie"] = cookie_str
    resp = _requests.post(crawler_url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise PublicRuntimeError("PRODUCT_SEARCH_UNAVAILABLE", "商品搜索服务暂时不可用，请稍后重试")

    items = data.get("items", [])
    normalized = []
    for item in items:
        item_id = item.get("itemId", "")
        normalized.append({
            "title": item.get("title", ""),
            "price": item.get("price", ""),
            "imageUrl": item.get("imageUrl", ""),
            "link": f"https://www.goofish.com/item?itemId={item_id}" if item_id else (item.get("itemUrl") or ""),
            "itemId": item_id,
            "seller": item.get("userNickName", ""),
            "area": item.get("area", ""),
            "soldCount": 0,
            "wantCount": 0,
            "description": item.get("title", ""),
        })
    return normalized


def _workflow_search_with_fallback(
    keyword: str, page: int, page_size: int, tenant_id: int, cookie_str: str, mode: str = "auto",
) -> tuple[list[dict], str]:
    """工作流搜索降级：fast 直调 MTOP → slow 浏览器。

    复用商机发掘已验证的搜索降级机制（auto 智能模式先快后慢自动降级），
    遵守硬约束：不刷新 _m_h5_tk，直接使用原始 Cookie。
    返回 (items, searchMode)。

    ★ 当 auto 模式下 fast 触发 Baxia 风控（PRODUCT_SEARCH_RATE_LIMITED）且 slow 也失败时，
      抛出 PublicRuntimeError(PRODUCT_SEARCH_RATE_LIMITED)，让上层 PRODUCT_FETCH 能检测到
      风控信号并切换后续关键词为 slow 模式，避免继续撞 MTOP 风控墙。
    """
    mode = (mode or "auto").lower().strip()
    if mode not in ("fast", "slow", "auto"):
        mode = "auto"

    fast_rate_limited = False
    if mode in ("fast", "auto"):
        try:
            items = _workflow_search_fast(keyword, page, page_size, cookie_str)
            if items:
                logger.info("[PRODUCT_FETCH] 快速搜索成功 keyword=%s count=%d", keyword, len(items))
                return items, "fast"
            logger.info("[PRODUCT_FETCH] 快速搜索无结果 keyword=%s，尝试慢速搜索", keyword)
        except PublicRuntimeError as e:
            _log_runtime_failure("workflow_search_fast", e)
            if mode == "fast":
                raise
            # auto 模式：记录是否为 Baxia 风控，用于后续策略切换
            if e.error_code == "PRODUCT_SEARCH_RATE_LIMITED":
                fast_rate_limited = True
        except Exception as e:
            _log_runtime_failure("workflow_search_fast", e)
            if mode == "fast":
                raise

    # 慢速搜索（Playwright 浏览器）
    try:
        items = _workflow_search_slow(keyword, page, page_size, tenant_id, cookie_str)
        logger.info("[PRODUCT_FETCH] 慢速搜索成功 keyword=%s count=%d", keyword, len(items))
        return items, "slow"
    except Exception as slow_err:
        # ★ 如果 fast 触发了 Baxia 风控，且 slow 也失败，
        #   抛出风控异常让上层 PRODUCT_FETCH 切换后续关键词为 slow 模式
        if fast_rate_limited:
            logger.warning("[PRODUCT_FETCH] keyword=%s fast 触发风控且 slow 也失败，向上抛出风控信号", keyword)
            raise PublicRuntimeError(
                "PRODUCT_SEARCH_RATE_LIMITED",
                "快速搜索触发平台验证，慢速搜索也失败",
            )
        raise


# ---- crawler-service HTTP 内部调用头 ----
_CRAWLER_BASE = (os.getenv("CRAWLER_SERVICE_URL") or "http://localhost:3001").rstrip("/")
_CRAWLER_HEADERS = {
    "X-Internal-Token": settings.effective_internal_api_token,
}


def _crawler_headers(tenant_id: int) -> dict:
    h = dict(_CRAWLER_HEADERS)
    h["X-Internal-Tenant-Id"] = str(tenant_id)
    return h


# ========== AI封面图Pillow文字叠加 ==========

_FONT_CANDIDATES_BOLD = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\Dengb.ttf",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
]

_FONT_CANDIDATES_REGULAR = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\Deng.ttf",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
]


def _load_font(size: int, bold: bool = True):
    """加载中文字体，优先粗体。验证字体确实能渲染中文后才返回。"""
    from PIL import ImageFont, ImageDraw, Image as PILImage
    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    import os
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                # 验证：渲染中文"测试"到小图片，确认像素被实际绘制
                test_img = PILImage.new("RGB", (60, 40), (255, 255, 255))
                test_draw = ImageDraw.Draw(test_img)
                test_draw.text((5, 5), "测试", font=font, fill=(0, 0, 0))
                # 检查是否有黑色像素（文字确实被画出来了）
                has_black = False
                for y in range(5, 35):
                    for x in range(5, 55):
                        if test_img.getpixel((x, y))[0] < 128:
                            has_black = True
                            break
                    if has_black:
                        break
                if has_black:
                    return font
            except Exception:
                continue
    # 终极回退：尝试所有已知字体（含粗体和常规）
    for path in _FONT_CANDIDATES_BOLD + _FONT_CANDIDATES_REGULAR:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                test_img = PILImage.new("RGB", (60, 40), (255, 255, 255))
                test_draw = ImageDraw.Draw(test_img)
                test_draw.text((5, 5), "测试", font=font, fill=(0, 0, 0))
                for y in range(5, 35):
                    for x in range(5, 55):
                        if test_img.getpixel((x, y))[0] < 128:
                            return font
            except Exception:
                continue
    return ImageFont.load_default()


_SELLING_TAG_POOL = [
    "永久使用", "一键安装", "远程安装", "自动发货",
    "正版激活", "终身授权", "永久激活", "包安装",
    "支持重装", "官方正版", "秒发货", "全版本",
    "稳定可用", "即买即用", "24h发货", "安全无毒",
    "Win/Mac", "全套教程", "持续更新", "售后无忧",
]


def _extract_cover_keywords(title: str, desc: str = "") -> dict:
    """从商品标题/描述中提取封面图所需的关键词：主标题、角标、卖点。

    分类优先级：强特征词（具体产品名）> 弱特征词（通用描述词）。
    例如"微软Visio2024...送海量素材模板"应识别为软件而非素材，因为Visio是强特征词。
    """
    text = f"{title} {desc}"

    # 强特征词：具体产品/品牌名，出现即确定类型（优先级最高）
    has_strong_software = bool(re.search(
        r"(?:Visio|visio|Office|office|Windows|windows|Word|word|Excel|excel|PowerPoint|PPT(?!模板)|"
        r"Photoshop|PS(?!素材)|Premiere|PR(?!模板)|AutoCAD|CAD(?!素材)|After\s*Effects|AE|"
        r"Illustrator|AI(?!素材)|InDesign|ID|WPS|3ds\s*Max|Maya|CorelDRAW|CDR|Matlab|SPSS)",
        text
    ))
    has_strong_game = bool(re.search(
        r"(?:Steam\s*(?:正版|游戏|激活|离线|国区|CDK|dlc|DLC)?|CDK|cdkey|"
        r"全DLC|豪华版|终极版|离线(?:可玩|模式|游戏)|游戏账号|PC游戏|主机游戏|电玩)",
        text, re.IGNORECASE
    )) and not bool(re.search(r"小游戏|课堂游戏|互动游戏|团建游戏|年会游戏|晨会游戏", text))
    has_strong_material = bool(re.search(
        r"(?:PPT模板|简历模板|海报模板|视频素材|图片素材|设计素材|源文件|预设|笔刷|文案模板|文档模板)",
        text, re.IGNORECASE
    ))
    has_strong_course = bool(re.search(
        r"(?:视频教程|视频课|网课|培训课程|全套教程)",
        text
    ))

    # 弱特征词：通用描述词，仅在无强特征词时使用
    has_weak_material = bool(re.search(r"素材|模板", text))
    has_weak_course = bool(re.search(r"教程|课程|教学|学习|培训", text))
    has_weak_software = bool(re.search(r"安装|软件|激活|密钥|系统", text, re.IGNORECASE))

    # 按强→弱优先级确定类型
    is_software = has_strong_software
    is_game = has_strong_game and not is_software
    is_material = has_strong_material and not is_software and not is_game
    is_course = has_strong_course and not is_software and not is_game and not is_material

    # 如果没有强特征词匹配，按弱特征词判断（注意顺序：素材/教程优先于安装类弱词）
    if not (is_software or is_game or is_material or is_course):
        if has_strong_material or (has_weak_material and not has_weak_software):
            is_material = True
        elif has_strong_course or has_weak_course:
            is_course = True
        elif has_weak_software:
            is_software = True

    # 角标关键词（右上角红色角标）
    badge = ""
    if is_software:
        badge_patterns = [
            (r"(永久|终身|不限期|一直可用|永久授权|终身使用)", "永久激活"),
            (r"(远程|协助|帮装|代装|在线安装|一对一)", "远程安装"),
            (r"(一键|秒装|快速安装|自动安装|点击即装)", "一键安装"),
            (r"(激活码|序列号|密钥|cdk|CDK|正版码)", "正版激活"),
        ]
    elif is_game:
        badge_patterns = [
            (r"(全DLC|豪华版|终极版|完整版)", "全DLC"),
            (r"(激活码|CDK|cdkey|序列号|正版码)", "正版激活"),
            (r"(国区|全区|全球)", "国区可用"),
            (r"(Steam|steam|PC|离线)", "Steam"),
        ]
    elif is_material:
        badge_patterns = [
            (r"(限时|特价|特惠|优惠|低价)", "限时特惠"),
            (r"(全套|合集|大礼包|打包)", "全套合集"),
            (r"(高清|4K|无损|源文件)", "高清素材"),
            (r"(更新|升级|持续更新)", "持续更新"),
        ]
    elif is_course:
        badge_patterns = [
            (r"(全套|全集|完整|系统)", "全套课程"),
            (r"(一对一|答疑|指导|售后)", "一对一指导"),
            (r"(限时|特价|优惠)", "限时特惠"),
            (r"(永久|终身|反复看)", "永久有效"),
        ]
    else:
        badge_patterns = [
            (r"(永久|终身|不限期)", "永久使用"),
            (r"(自动发货|24小时发货|秒发)", "自动发货"),
            (r"(热卖|爆款|热销|畅销)", "爆款热销"),
            (r"(特价|优惠|低价|特惠)", "限时特惠"),
        ]
    for pattern, label in badge_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            badge = label
            break
    if not badge:
        if is_software:
            badge = "一键安装"
        elif is_game:
            badge = "正版激活"
        elif is_material:
            badge = "高清素材"
        elif is_course:
            badge = "全套教程"
        else:
            badge = "自动发货"

    # 主标题：从标题中提取核心产品名
    # 先提取产品核心名称——按类别识别
    main_title = ""
    if is_software:
        # 软件类：提取软件名+版本
        sw_match = re.search(r"(Office|office|Visio|visio|Windows|windows|Word|word|Excel|excel|PPT|PowerPoint|PS|Photoshop|PR|Premiere|CAD|AutoCAD|AE|After\s*Effects|AI|Illustrator|ID|InDesign|WPS|3ds\s*Max|Maya|CDR|CorelDRAW|Matlab|SPSS|Python)[^0-9a-zA-Z]*(\d{4})?", text, re.IGNORECASE)
        if sw_match:
            sw_name = sw_match.group(1)
            sw_ver = sw_match.group(2) or ""
            main_title = sw_name + (sw_ver if sw_ver else "")
        if not main_title:
            # 尝试提取"XXX安装"前的产品名
            m = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{2,10})\s*(安装|激活|软件)", title)
            if m:
                main_title = m.group(1)
    elif is_game:
        # 游戏类：提取游戏名（中文优先，在Steam/激活码等关键词之前）
        m = re.search(r"([\u4e00-\u9fa5][\u4e00-\u9fa5A-Za-z0-9\s]{1,12}?)\s*(?:Steam|steam|激活码|CDK|全DLC|豪华版|PC版|PC|游戏|正版)", title)
        if m:
            main_title = m.group(1).strip()
        if not main_title:
            # 尝试匹配中文游戏名（至少2个汉字）
            m2 = re.search(r"([\u4e00-\u9fa5]{2,8})", title)
            if m2:
                main_title = m2.group(1)
        if not main_title:
            main_title = title[:8]
    elif is_material:
        # 素材类：提取素材类型
        m = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{2,10}(?:模板|素材|海报|简历|视频|图片|预设|笔刷|文案))", title, re.IGNORECASE)
        if m:
            main_title = m.group(1)
        if not main_title:
            # PPT/Word/Excel 等英文关键词+中文后缀
            m2 = re.search(r"(PPT|Word|Excel|PS|PR|AE|AI|CAD|Visio)\s*[\u4e00-\u9fa5]{0,4}", title, re.IGNORECASE)
            if m2:
                main_title = m2.group(0)
        if not main_title:
            m3 = re.match(r"([\u4e00-\u9fa5A-Za-z0-9]{2,10})", title)
            if m3:
                main_title = m3.group(1)
    elif is_course:
        # 教程类
        m = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{2,8}(?:教程|课程|教学|网课))", title)
        if m:
            main_title = m.group(1)
        if not main_title:
            m2 = re.match(r"([\u4e00-\u9fa5A-Za-z0-9]{2,8})", title)
            if m2:
                main_title = m2.group(1)
    else:
        # 通用：取标题最前面的核心词（2-8字）
        m = re.match(r"([\u4e00-\u9fa5A-Za-z0-9]{2,8})", title)
        if m:
            main_title = m.group(1)

    if not main_title or len(main_title) < 2:
        main_title = title[:8]

    # 清理主标题中的无关词
    main_title = re.sub(r"(远程安装|一键安装|自动发货|永久激活|永久使用|正版|激活码|秘钥|密钥|特价|热卖|爆款|促销|优惠|包邮|秒发|\d+元|￥|¥)", "", main_title).strip()
    if not main_title:
        main_title = title[:8]
    # 限制长度
    main_title = main_title[:10]

    # 版本标签：优先匹配标题中最先出现的年份（通常是最新版本）
    version = ""
    ver_match = re.search(r"(20\d{2})\s*(?:版|年|版本)?", title)
    if ver_match:
        version = ver_match.group(1) + "版"
    else:
        ver_match2 = re.search(r"(全DLC|豪华版|专业版|增强版|完整版|企业版|旗舰版|家庭版|专业增强版)", text)
        if ver_match2:
            version = ver_match2.group(1)

    # 底部卖点：3个标签（根据商品类型选择）
    sell_tags = []
    if is_software:
        tag_candidates = [
            ("永久使用", r"永久|终身|不限期|一直用"),
            ("一键安装", r"一键|秒装|快速安装|自动安装"),
            ("远程安装", r"远程|协助|帮装|代装"),
            ("支持重装", r"支持重装|可重装|反复安装"),
            ("正版激活", r"正版|激活码|密钥|授权"),
            ("自动发货", r"自动发货|24小时|秒发"),
            ("Win/Mac", r"win.*mac|windows.*mac|支持win|支持mac"),
            ("全套教程", r"教程|指导|教学"),
            ("安全稳定", r"安全|稳定|无毒"),
        ]
    elif is_game:
        tag_candidates = [
            ("国区可用", r"国区|全区|全球|中文"),
            ("正版激活", r"正版|激活码|CDK|密钥"),
            ("全DLC", r"DLC|dlc|豪华|终极|完整版"),
            ("Steam", r"Steam|steam|PC"),
            ("即买即发", r"自动发货|秒发|即发"),
            ("诚信交易", r"诚信|安全|靠谱"),
            ("永久质保", r"永久|终身|质保|售后"),
            ("在线指导", r"指导|教程|帮助"),
        ]
    elif is_material:
        tag_candidates = [
            ("高清质量", r"高清|4K|无损|源文件|质量"),
            ("持续更新", r"更新|升级|持续"),
            ("自动发货", r"自动发货|秒发|即发"),
            ("海量资源", r"全套|合集|大礼包|海量|全套"),
            ("多种格式", r"格式|多种|兼容|通用"),
            ("售后无忧", r"售后|指导|答疑"),
            ("即下即用", r"即用|直接用|简单|方便"),
        ]
    elif is_course:
        tag_candidates = [
            ("高清视频", r"高清|视频|画质"),
            ("持续更新", r"更新|升级|持续|新增"),
            ("自动发货", r"自动发货|秒发|即发"),
            ("一对一指导", r"一对一|答疑|指导|售后"),
            ("永久有效", r"永久|终身|反复|不限期"),
            ("零基础学", r"零基础|入门|新手"),
            ("全套课程", r"全套|全集|完整|系统"),
        ]
    else:
        tag_candidates = [
            ("自动发货", r"自动发货|24小时|秒发"),
            ("永久使用", r"永久|终身|长期"),
            ("售后无忧", r"售后|质保|指导"),
            ("优质商品", r"优质|精品|高端"),
            ("即买即用", r"即买|秒发|即用"),
        ]
    for tag_name, pattern in tag_candidates:
        if re.search(pattern, text, re.IGNORECASE) and tag_name not in sell_tags:
            # 不要与版本标签重复
            if tag_name == version:
                continue
            sell_tags.append(tag_name)
        if len(sell_tags) >= 3:
            break
    # 不足3个时按类型补齐默认标签
    default_tags_by_type = {
        "software": ["自动发货", "永久使用", "安全稳定"],
        "game": ["诚信交易", "即买即发", "售后无忧"],
        "material": ["自动发货", "持续更新", "售后无忧"],
        "course": ["自动发货", "永久有效", "零基础学"],
        "other": ["自动发货", "售后无忧", "即买即用"],
    }
    tag_type = "software" if is_software else "game" if is_game else "material" if is_material else "course" if is_course else "other"
    for tag in default_tags_by_type[tag_type]:
        if len(sell_tags) >= 3:
            break
        if tag not in sell_tags and tag != version and tag != badge:
            sell_tags.append(tag)

    return {
        "main_title": main_title[:10],
        "badge": badge,
        "version": version,
        "sell_tags": sell_tags[:3],
        "category": "software" if is_software else "game" if is_game else "material" if is_material else "course" if is_course else "other",
    }


def _generate_software_cover(title: str, desc: str = "") -> bytes:
    """生成软件安装类商品封面图（蓝白模板风格，仿照参考图）。

    布局：蓝色边框(上下10%) + 白色中框(80%) + 产品Logo首字母 + 卖点文字。
    完全使用Pillow绘制，无需AI生图，中文文字完美渲染。
    """
    from PIL import Image, ImageDraw
    import io

    S = 800
    BLUE = (26, 93, 221)
    DARK_BLUE = (15, 55, 160)
    WHITE = (255, 255, 255)
    RED = (220, 30, 30)
    ORANGE = (230, 80, 20)
    GOLD = (250, 200, 0)
    BLACK = (30, 30, 30)
    DARK = (20, 20, 50)
    LOGO_BG = (20, 30, 60)

    kw = _extract_cover_keywords(title, desc)
    main_title = kw["main_title"]
    badge = kw["badge"]
    version = kw["version"]
    sell_tags = kw["sell_tags"]
    cat = kw.get("category", "other")

    img = Image.new("RGB", (S, S), BLUE)
    draw = ImageDraw.Draw(img, "RGBA")

    # ========== 顶部蓝色区域 ==========
    top_h = int(S * 0.12)
    draw.rectangle([0, 0, S, top_h], fill=BLUE)
    # 顶栏大字（白+黄配色）
    top_font_big = _load_font(int(S * 0.095), bold=True)
    top_font_small = _load_font(int(S * 0.065), bold=True)
    top_text = badge if badge else "永久激活"
    # 分两部分：白色前缀 + 黄色后缀
    if "激活" in top_text:
        prefix = top_text.replace("激活", "")
        suffix = "激活"
    elif "安装" in top_text:
        prefix = top_text.replace("安装", "")
        suffix = "安装"
    else:
        prefix = top_text[:2]
        suffix = top_text[2:]

    # 顶部居中文字
    all_top = prefix + suffix
    tbbox = draw.textbbox((0, 0), all_top, font=top_font_big)
    tw = tbbox[2] - tbbox[0]
    tx = (S - tw) / 2 - tbbox[0]
    ty = (top_h - (tbbox[3] - tbbox[1])) / 2 - tbbox[1]
    # 先画prefix白色
    if prefix:
        draw.text((tx, ty), prefix, font=top_font_big, fill=WHITE)
        pbbox = draw.textbbox((0, 0), prefix, font=top_font_big)
        pw = pbbox[2] - pbbox[0]
        # 再画suffix黄色
        draw.text((tx + pw, ty), suffix, font=top_font_big, fill=GOLD)
    else:
        draw.text((tx, ty), all_top, font=top_font_big, fill=WHITE)

    # ========== 白色中框区域 ==========
    pad = int(S * 0.02)
    white_top = top_h + pad
    white_bottom = S - top_h - pad
    white_left = pad
    white_right = S - pad
    draw.rectangle([white_left, white_top, white_right, white_bottom], fill=WHITE)
    draw.rectangle([white_left, white_top, white_right, white_bottom], outline=BLUE, width=3)

    # ---- "亲测推荐"椭圆标签（左上角白色区域内）----
    rec_x, rec_y = int(S * 0.05), white_top + int(S * 0.03)
    rec_font = _load_font(int(S * 0.045), bold=True)
    rec_text = "亲测推荐"
    rbbox = draw.textbbox((0, 0), rec_text, font=rec_font)
    rw, rh = rbbox[2] - rbbox[0], rbbox[3] - rbbox[1]
    rec_pad_x, rec_pad_y = int(S * 0.035), int(S * 0.018)
    rec_w, rec_h = rw + rec_pad_x * 2, rh + rec_pad_y * 2
    # 渐变椭圆底（蓝粉渐变效果用两个椭圆近似）
    draw.ellipse([rec_x - rec_pad_x, rec_y - rec_pad_y, rec_x + rw + rec_pad_x, rec_y + rh + rec_pad_y],
                 fill=(200, 220, 255))
    draw.ellipse([rec_x - rec_pad_x + 3, rec_y - rec_pad_y + 3, rec_x + rw + rec_pad_x - 3, rec_y + rh + rec_pad_y - 3],
                 fill=(255, 220, 240))
    draw.text((rec_x - rbbox[0], rec_y - rbbox[1]), rec_text, font=rec_font, fill=(80, 40, 160))
    # 英文小字
    en_font = _load_font(int(S * 0.018), bold=False)
    en_text = "PERSONAL RECOMMENDATION"
    ebbox = draw.textbbox((0, 0), en_text, font=en_font)
    ex = rec_x + (rw - (ebbox[2] - ebbox[0])) / 2 - ebbox[0]
    draw.text((ex, rec_y + rh + int(S * 0.005)), en_text, font=en_font, fill=(100, 60, 160))

    # ---- 右上角说明文字 ----
    rt_font = _load_font(int(S * 0.048), bold=True)
    rt_text = "解决各种疑难杂症"
    rtbbox = draw.textbbox((0, 0), rt_text, font=rt_font)
    rtw = rtbbox[2] - rtbbox[0]
    draw.text((white_right - rtw - int(S * 0.05) - rtbbox[0], white_top + int(S * 0.04) - rtbbox[1]),
              rt_text, font=rt_font, fill=ORANGE)

    # ---- 工程师一对一标签（右上角第二行）----
    eng_font = _load_font(int(S * 0.05), bold=True)
    eng_text = "工程师一对一远程"
    ebbox2 = draw.textbbox((0, 0), eng_text, font=eng_font)
    ew = ebbox2[2] - ebbox2[0]
    eh = ebbox2[3] - ebbox2[1]
    eng_x = white_right - ew - int(S * 0.04) - ebbox2[0]
    eng_y = white_top + int(S * 0.10) - ebbox2[1]
    # 黑色边框白底
    draw.rectangle([eng_x - int(S * 0.015), eng_y - int(S * 0.008),
                    eng_x + ew + int(S * 0.015), eng_y + eh + int(S * 0.008)],
                   outline=BLACK, width=3)
    draw.text((eng_x, eng_y), eng_text, font=eng_font, fill=BLACK)

    # ---- 产品Logo（左侧深色圆角方块+首字母）----
    logo_size = int(S * 0.28)
    logo_x = int(S * 0.08)
    logo_y = white_top + int(S * 0.16)
    draw.rounded_rectangle([logo_x, logo_y, logo_x + logo_size, logo_y + logo_size],
                           radius=int(S * 0.04), fill=LOGO_BG)
    # Logo文字（取产品名首字母或前两个字符）
    logo_text = ""
    # 提取软件缩写
    logo_map = {
        "ps": "Ps", "photoshop": "Ps", "pr": "Pr", "premiere": "Pr",
        "ai": "Ai", "illustrator": "Ai", "ae": "Ae", "id": "Id",
        "office": "Off", "word": "W", "excel": "X", "ppt": "Pp", "powerpoint": "Pp",
        "visio": "V", "windows": "Win", "cad": "CAD", "autocad": "CAD",
        "wps": "WPS", "3dsmax": "3D", "maya": "My", "cdr": "CD",
        "coreldraw": "CD", "matlab": "M", "spss": "S",
    }
    t_lower = (title + " " + desc).lower()
    for key, val in logo_map.items():
        if key in t_lower:
            logo_text = val
            break
    if not logo_text:
        # 取主标题前2个字符
        clean = re.sub(r"[0-9\s安装激活永久远程包版教程送素材]+", "", main_title)
        logo_text = clean[:2].upper() if clean else main_title[:2]

    logo_font_size = int(logo_size * 0.55)
    logo_font = _load_font(logo_font_size, bold=True)
    lbbox = draw.textbbox((0, 0), logo_text, font=logo_font)
    lw, lh = lbbox[2] - lbbox[0], lbbox[3] - lbbox[1]
    lx = logo_x + (logo_size - lw) / 2 - lbbox[0]
    ly = logo_y + (logo_size - lh) / 2 - lbbox[1]
    # Logo渐变色（蓝色→青色）
    draw.text((lx, ly), logo_text, font=logo_font, fill=(40, 140, 255))

    # ---- 右侧卖点文字列表 ----
    sell_start_y = logo_y + int(S * 0.02)
    sell_x_start = logo_x + logo_size + int(S * 0.06)

    # 卖点1：红色带下划线（浏览器高速下载风格）
    sell_font = _load_font(int(S * 0.052), bold=True)
    sell_texts = [
        ("浏览器高速下载", RED, True),
        ("可免费加急安装", BLACK, True),
        ("保证好用", RED, True),
    ]
    # 根据实际sell_tags动态替换
    if len(sell_tags) >= 1:
        sell_texts = []
        colors = [RED, BLACK, RED]
        underlines = [True, True, True]
        for i, tag in enumerate(sell_tags[:3]):
            sell_texts.append((tag, colors[i], underlines[i]))

    cur_y = sell_start_y
    for i, (stext, scolor, suline) in enumerate(sell_texts):
        sbbox = draw.textbbox((0, 0), stext, font=sell_font)
        stw = sbbox[2] - sbbox[0]
        sth = sbbox[3] - sbbox[1]
        sxx = sell_x_start - sbbox[0]
        syy = cur_y - sbbox[1]
        draw.text((sxx, syy), stext, font=sell_font, fill=scolor)
        if suline:
            # 下划线
            line_y = syy + sth + int(S * 0.005)
            draw.line([(sxx + sbbox[0], line_y), (sxx + stw + sbbox[0], line_y)],
                      fill=scolor, width=max(2, int(S * 0.005)))
        cur_y += sth + int(S * 0.035)

    # ---- 白色区域底部产品英文/全称号 ----
    bottom_prod_font = _load_font(int(S * 0.075), bold=True)
    # 产品全名
    full_name = main_title
    if version and version not in full_name:
        full_name = full_name + " " + version
    fbbox = draw.textbbox((0, 0), full_name, font=bottom_prod_font)
    fw = fbbox[2] - fbbox[0]
    fx = (S - fw) / 2 - fbbox[0]
    fy = white_bottom - int(S * 0.10) - fbbox[1]
    # 黑色描边白色字
    for ddx, ddy in [(-2,0),(2,0),(0,-2),(0,2),(-2,-2),(2,2),(-2,2),(2,-2)]:
        draw.text((fx+ddx, fy+ddy), full_name, font=bottom_prod_font, fill=(0,0,0,200))
    draw.text((fx, fy), full_name, font=bottom_prod_font, fill=WHITE if False else BLACK)

    # ========== 底部蓝色区域 ==========
    draw.rectangle([0, S - top_h, S, S], fill=BLUE)
    bot_text = "安装失败 全额退款"
    bot_font = _load_font(int(S * 0.09), bold=True)
    bbbox = draw.textbbox((0, 0), bot_text, font=bot_font)
    bw2 = bbbox[2] - bbbox[0]
    bx = (S - bw2) / 2 - bbbox[0]
    by = (S - top_h / 2) - (bbbox[3] - bbbox[1]) / 2 - bbbox[1]
    draw.text((bx, by), bot_text, font=bot_font, fill=WHITE)

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=92)
    return output.getvalue()


def _add_cover_text_overlay(image_bytes: bytes, title: str, desc: str = "") -> bytes:
    """在AI生成的电商海报背景上叠加中文文字，生成高质量闲鱼商品主图。

    参考闲鱼爆款主图的设计规范：
    - 1:1 正方形（闲鱼标准尺寸）
    - 深色背景 + 高饱和色块（参考图通用模式：深蓝/深紫/黑底 + 白/黄/红字）
    - 顶部大标题（粗体白字，占画面上半部分的核心位置）
    - 右上角红色角标（徽章式，带白边）
    - 底部红黄横幅（3个卖点标签）
    - 整体风格扁平电商海报，强烈促销感
    """
    from PIL import Image, ImageDraw, ImageFilter
    import io

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    except Exception:
        return image_bytes

    # 确保1:1正方形（闲鱼标准）
    w, h = img.size
    if w != h:
        size = max(w, h)
        new_img = Image.new("RGBA", (size, size), (20, 25, 60, 255))
        offset = ((size - w) // 2, (size - h) // 2)
        new_img.paste(img, offset, img if img.mode == "RGBA" else None)
        img = new_img

    # 统一缩放到 800x800（闲鱼正方形主图标准尺寸）
    TARGET_SIZE = 800
    if img.size[0] != TARGET_SIZE:
        img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)

    S = TARGET_SIZE
    draw = ImageDraw.Draw(img, "RGBA")

    # 提取关键词
    kw = _extract_cover_keywords(title, desc)
    main_title = kw["main_title"]
    badge = kw["badge"]
    version = kw["version"]
    sell_tags = kw["sell_tags"]

    # ---- 1. 底部渐变遮罩（确保文字可读性）----
    overlay_h = int(S * 0.45)
    for y in range(S - overlay_h, S):
        alpha = int(180 * (y - (S - overlay_h)) / overlay_h)
        draw.line([(0, y), (S, y)], fill=(10, 15, 40, alpha))

    # ---- 2. 顶部半透明条（主标题背景）----
    title_bar_h = int(S * 0.22)
    draw.rectangle([0, 0, S, title_bar_h], fill=(10, 15, 50, 160))

    # ---- 3. 右上角红色角标（徽章）----
    badge_size = int(S * 0.22)
    badge_x = S - badge_size - int(S * 0.02)
    badge_y = int(S * 0.02)
    badge_font_size = int(badge_size * 0.38)
    badge_font = _load_font(badge_font_size, bold=True)
    # 角标背景（红色圆角矩形）
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
        radius=int(S * 0.025), fill=(230, 30, 30, 240),
    )
    # 角标白边
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
        radius=int(S * 0.025), outline=(255, 255, 255, 200), width=max(2, int(S * 0.005)),
    )
    # 角标文字居中
    bbox = draw.textbbox((0, 0), badge, font=badge_font)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    bt_x = badge_x + (badge_size - bw) / 2 - bbox[0]
    bt_y = badge_y + (badge_size - bh) / 2 - bbox[1]
    # 文字阴影
    draw.text((bt_x + 2, bt_y + 2), badge, font=badge_font, fill=(0, 0, 0, 100))
    draw.text((bt_x, bt_y), badge, font=badge_font, fill=(255, 255, 255, 255))

    # ---- 4. 版本标签（左上角蓝色椭圆）----
    if version:
        ver_font_size = int(S * 0.055)
        ver_font = _load_font(ver_font_size, bold=True)
        vbbox = draw.textbbox((0, 0), version, font=ver_font)
        vw, vh = vbbox[2] - vbbox[0], vbbox[3] - vbbox[1]
        ver_pad_x, ver_pad_y = int(S * 0.03), int(S * 0.012)
        ver_x, ver_y = int(S * 0.03), int(S * 0.02)
        ver_w = vw + ver_pad_x * 2
        ver_h = vh + ver_pad_y * 2
        draw.rounded_rectangle(
            [ver_x, ver_y, ver_x + ver_w, ver_y + ver_h],
            radius=int(ver_h * 0.3), fill=(250, 200, 0, 230),
        )
        draw.text(
            (ver_x + ver_pad_x - vbbox[0], ver_y + ver_pad_y - vbbox[1]),
            version, font=ver_font, fill=(50, 30, 0, 255),
        )

    # ---- 5. 主标题（顶部大字）----
    # 根据标题字数动态调整字号
    title_len = len(main_title)
    if title_len <= 4:
        title_font_size = int(S * 0.15)
    elif title_len <= 6:
        title_font_size = int(S * 0.12)
    elif title_len <= 8:
        title_font_size = int(S * 0.10)
    else:
        title_font_size = int(S * 0.085)
    title_font = _load_font(title_font_size, bold=True)

    # 标题分两行（如果太长）
    title_lines = []
    if title_len <= 6:
        title_lines = [main_title]
    elif title_len <= 10:
        mid = title_len // 2
        title_lines = [main_title[:mid], main_title[mid:]]
    else:
        title_lines = [main_title[:5], main_title[5:10]]

    title_y_start = int(S * 0.06)
    if version:
        title_y_start += int(S * 0.05)
    line_height = int(title_font_size * 1.2)
    for i, line in enumerate(title_lines):
        lbbox = draw.textbbox((0, 0), line, font=title_font)
        lw = lbbox[2] - lbbox[0]
        lx = (S - lw) / 2 - lbbox[0]
        ly = title_y_start + i * line_height - lbbox[1]
        # 文字描边/阴影
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2)]:
            draw.text((lx + dx, ly + dy), line, font=title_font, fill=(0, 0, 0, 120))
        draw.text((lx, ly), line, font=title_font, fill=(255, 255, 255, 255))

    # ---- 6. 底部红黄横幅（卖点标签）----
    banner_h = int(S * 0.12)
    banner_y = S - banner_h
    # 左半黄底
    draw.rectangle([0, banner_y, int(S * 0.5), S], fill=(250, 200, 0, 240))
    # 右半红底
    draw.rectangle([int(S * 0.5), banner_y, S, S], fill=(220, 30, 30, 240))

    tag_font_size = int(S * 0.055)
    tag_font = _load_font(tag_font_size, bold=True)

    # 3个标签：第1个在黄底左，第2个在黄底右/中缝，第3个在红底
    tag_positions = [
        (int(S * 0.17), int(S * 0.96)),
        (int(S * 0.50), int(S * 0.96)),
        (int(S * 0.83), int(S * 0.96)),
    ]
    tag_colors = [(50, 30, 0, 255), (255, 255, 255, 255), (255, 255, 255, 255)]

    # 如果只有3个标签，调整为左中右布局横跨横幅
    if len(sell_tags) >= 3:
        # 3个标签等分横幅
        section_w = S / 3
        for i in range(3):
            tag = sell_tags[i]
            tbbox = draw.textbbox((0, 0), tag, font=tag_font)
            tw = tbbox[2] - tbbox[0]
            tx = section_w * i + (section_w - tw) / 2 - tbbox[0]
            ty = banner_y + (banner_h - (tbbox[3] - tbbox[1])) / 2 - tbbox[1]
            # 交替颜色
            if i == 0:
                tc = (50, 30, 0, 255)
            elif i == 1:
                tc = (255, 255, 255, 255)
            else:
                tc = (255, 255, 255, 255)
            draw.text((tx, ty), tag, font=tag_font, fill=tc)

    # ---- 7. 装饰元素：白色边框线（参考图的边框风格）----
    border_w = max(3, int(S * 0.008))
    draw.rectangle(
        [border_w // 2, border_w // 2, S - border_w // 2 - 1, S - border_w // 2 - 1],
        outline=(255, 255, 255, 60), width=border_w,
    )

    # 转回RGB（合成到白色背景）并保存
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[3])

    output = io.BytesIO()
    bg.save(output, format="JPEG", quality=92)
    return output.getvalue()


async def _download_and_overlay_image(
    img_url: str, title: str, desc: str, tenant_id: int, user_id: int | None = None
) -> str:
    """下载AI生成的图片，叠加中文文字后保存到本地uploads，返回本地访问URL。"""
    import os

    try:
        downloaded = await download_public_image(img_url)
        raw_bytes = downloaded.content

        # 叠加文字
        processed_bytes = _add_cover_text_overlay(raw_bytes, title, desc)

        uploads_dir = os.path.join(os.path.dirname(__file__), "../../uploads/images")
        image = validate_image_bytes(processed_bytes)
        stored = await store_governed_image(
            image,
            tenant_id=tenant_id,
            user_id=user_id,
            prefix="cover-overlay",
            source_type="workflow-cover",
            base_dir=uploads_dir,
        )
        logger.info("[COVER-OVERLAY] 封面图文字叠加完成 assetId=%d", stored.asset_id)
        return stored.public_url
    except Exception as e:
        _log_runtime_failure("download_and_overlay_image", e)
        return ""


async def _save_image_bytes_direct(
    img_bytes: bytes, title: str, tenant_id: int, user_id: int | None = None
) -> str:
    """直接保存AI生成的图片字节到本地uploads，不做Pillow文字叠加。
    用于AI已生成完整封面图（含文字）的场景，如 chat/completions 模式。"""
    import os

    try:
        uploads_dir = os.path.join(os.path.dirname(__file__), "../../uploads/images")
        image = validate_image_bytes(img_bytes)
        stored = await store_governed_image(
            image,
            tenant_id=tenant_id,
            user_id=user_id,
            prefix="cover",
            source_type="workflow-cover",
            base_dir=uploads_dir,
        )
        logger.info("[COVER-DIRECT] 封面图直接保存完成 assetId=%d bytes=%d", stored.asset_id, len(img_bytes))
        return stored.public_url
    except Exception as e:
        _log_runtime_failure("save_image_bytes_direct", e)
        return ""


def _normalize_shop_item(raw: dict) -> dict:
    """将 crawler-service 返回的店铺商品标准化为工作流统一格式（与关键词搜索产物一致）。"""
    item_id = _text(raw.get("itemId"))
    # ★ 修复：使用 crawler-service 新增的 description 字段（真实商品文案）
    #   之前误把 raw.get("title") 同时作为 title 和 description，导致润色节点拿不到真实文案
    desc = _text(raw.get("description")) or ""
    title = _text(raw.get("title"))
    # 兜底：如果 description 为空，再用 title 作为描述（避免空内容导致润色失败）
    if not desc:
        desc = title
    return {
        "title": title,
        "price": _text(raw.get("price")),
        "imageUrl": _text(raw.get("imageUrl")),
        "link": f"https://www.goofish.com/item?id={item_id}" if item_id else (_text(raw.get("itemUrl")) or ""),
        "itemId": item_id,
        "seller": "",
        "area": "",
        "soldCount": 0,
        "wantCount": 0,
        "description": desc,
    }


# ============================================================
# ★ 文案质量评分：检测润色结果是否合格
#   评分维度：
#     1. 是否包含源商品元数据标识（"XX人想要"、"小刀价"、"LateSunday"、"口语化："等）
#     2. 标题长度是否合理（5-30 字）
#     3. 文案长度是否合理（≥30 字）
#     4. 是否与源标题/源文案完全相同（未改写）
#   返回 (score, reasons) 其中 score ∈ [0, 100]
# ============================================================
_SHOP_META_PATTERNS = [
    re.compile(r"\d+\s*人想要"),
    re.compile(r"\d+\s*人收藏"),
    re.compile(r"\d+\s*人付款"),
    re.compile(r"\d+\s*人小刀价"),
    re.compile(r"小刀价"),
    re.compile(r"LateSunday", re.IGNORECASE),
    re.compile(r"口语化[：:]"),
    re.compile(r"雨夜电玩社"),
    re.compile(r"店铺\s*[QQ微信]\s*[：:]"),
    re.compile(r"关注店铺"),
    re.compile(r"点我头像"),
]


def _evaluate_polish_quality(
    polished_title: str,
    polished_body: str,
    source_title: str,
    source_body: str,
    forbidden_keywords: list[str] | None = None,
) -> tuple[int, list[str]]:
    """评估润色后文案的质量分数。
    返回 (score, reasons)。score ≥ 60 视为合格；< 60 需要重试。

    若传入 forbidden_keywords，命中禁止词直接判 0 分（强制重试）。
    """
    reasons: list[str] = []
    score = 100
    full_text = f"{polished_title}\n{polished_body}"

    # 0. ★ 禁止词硬校验（命中直接判 0 分，强制重试）
    if forbidden_keywords:
        title_hits, body_hits = validate_polish_output(polished_title, polished_body, forbidden_keywords)
        if title_hits or body_hits:
            all_hits = []
            for kw in title_hits + body_hits:
                if kw not in all_hits:
                    all_hits.append(kw)
            score = 0
            reasons.append(f"命中润色禁止词: {'、'.join(all_hits)}（必须重新生成）")

    # 1. 检测源商品元数据标识（每个 -15 分）
    for pat in _SHOP_META_PATTERNS:
        if pat.search(full_text):
            score -= 15
            reasons.append(f"包含源商品元数据: {pat.pattern}")

    # 2. 标题长度（5-30 字）
    title_len = len(polished_title.strip())
    if title_len < 5:
        score -= 20
        reasons.append(f"标题过短 ({title_len} 字)")
    elif title_len > 30:
        score -= 10
        reasons.append(f"标题过长 ({title_len} 字，应 ≤30)")

    # 3. 文案长度（≥30 字）
    body_len = len(polished_body.strip())
    if body_len < 30:
        score -= 20
        reasons.append(f"文案过短 ({body_len} 字)")

    # 4. 与源标题完全相同（未改写）
    if polished_title.strip() and polished_title.strip() == source_title.strip():
        score -= 25
        reasons.append("标题与源标题完全相同（未改写）")

    # 5. 与源文案完全相同（未改写）
    if polished_body.strip() and polished_body.strip() == source_body.strip():
        score -= 25
        reasons.append("文案与源文案完全相同（未改写）")

    # 6. 标题或文案为空
    if not polished_title.strip():
        score -= 30
        reasons.append("标题为空")
    if not polished_body.strip():
        score -= 30
        reasons.append("文案为空")

    return max(0, min(100, score)), reasons


async def _workflow_shop_fetch(
    db: AsyncSession, tenant_id: int, config: dict, context: dict, state: dict,
) -> dict:
    """店铺搜索模式：通过 crawler-service 爬取店铺商品，按账号+店铺去重后取前 N 个。

    流程：
    1. POST /api/import/goofish 触发店铺爬取（含 6 小时缓存）
    2. 轮询 GET /api/crawl-jobs/:jobId 直到完成
    3. GET /api/goofish/stores/:userId/items 获取全部商品
    4. 查询 workflow_shop_fetched_goods 去重表，过滤已提取商品（按账号+店铺）
    5. 取前 N 个（N = config.targetCount，默认 5），写入去重表
    6. 返回标准化商品列表

    遵守硬约束：店铺商品爬取必须通过浏览器（crawler-service Playwright），不可使用 API 接口。
    """
    import httpx as _httpx

    shop_url = _text(config.get("shopUrl") or config.get("shop_url") or config.get("url") or "").strip()
    if not shop_url:
        return {
            "ok": False, "errorCode": "SHOP_URL_REQUIRED", "message": "请先配置店铺链接",
            "count": 0, "items": [], "keyword": "",
            "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
            "artifact": {"count": 0, "items": [], "keyword": ""},
            "steps": [{"step": "校验", "status": "error", "detail": "缺少店铺链接"}],
        }

    # ★ 目标数量：从节点配置读取（用户在前端可自定义），默认 5
    #   范围限制 1-100，避免过大值导致爬取过久
    try:
        shop_target_count = int(config.get("targetCount") or config.get("target_count") or 5)
    except (ValueError, TypeError):
        shop_target_count = 5
    shop_target_count = max(1, min(100, shop_target_count))

    # 1) 账号解析（与关键词搜索相同的逻辑）
    account_id = (config.get("accountId")
                  or state.get("selectedAccountId")
                  or state.get("selected_account_id")
                  or context.get("input", {}).get("accountId")
                  or context.get("input", {}).get("selectedAccountId")
                  or context.get("input", {}).get("selected_account_id"))
    if not account_id:
        for ctx_key, ctx_val in context.items():
            if isinstance(ctx_val, dict) and ctx_val.get("selectedAccountId"):
                account_id = ctx_val["selectedAccountId"]
                break
    if not account_id:
        account_id = 1

    acct_id = int(account_id)
    state["target_count"] = shop_target_count

    # 2) 解析账号 Cookie
    cookie_str, cookie_err, _resolved_acct_id = await _resolve_account_cookie(db, tenant_id, acct_id, {})
    if cookie_err:
        logger.warning("runtimeFailure operation=resolve_shop_account_cookie errorType=AccountAuthUnavailable requestId=%s", get_request_id() or "-")
        return {
            "ok": False, "errorCode": "ACCOUNT_AUTH_UNAVAILABLE", "message": "账号登录状态不可用，请重新登录",
            "count": 0, "items": [], "keyword": shop_url,
            "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
            "artifact": {"count": 0, "items": [], "keyword": shop_url},
            "steps": [{"step": "账号校验", "status": "error", "detail": "账号登录状态不可用"}],
        }

    steps: list[dict] = []
    headers = _crawler_headers(tenant_id)

    # 3) 触发店铺爬取（crawler-service 处理 URL 解析 + 6小时缓存 + BullMQ 任务）
    try:
        async with _httpx.AsyncClient(timeout=30) as _client:
            resp = await _client.post(
                f"{_CRAWLER_BASE}/api/import/goofish",
                headers=headers, json={"url": shop_url, "cookie": cookie_str},
            )
        resp.raise_for_status()
        import_data = resp.json()
    except Exception as e:
        _log_runtime_failure("trigger_shop_crawl", e)
        return {
            "ok": False, "errorCode": "SHOP_CRAWL_TRIGGER_FAILED", "message": "店铺抓取任务启动失败，请稍后重试",
            "count": 0, "items": [], "keyword": shop_url,
            "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
            "artifact": {"count": 0, "items": [], "keyword": shop_url},
            "steps": [{"step": "启动抓取", "status": "error", "detail": "抓取任务启动失败"}],
        }

    if not import_data.get("ok"):
        return {
            "ok": False, "errorCode": "SHOP_CRAWL_REJECTED", "message": "店铺抓取服务暂时不可用，请稍后重试",
            "count": 0, "items": [], "keyword": shop_url,
            "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
            "artifact": {"count": 0, "items": [], "keyword": shop_url},
            "steps": [{"step": "启动抓取", "status": "error", "detail": "抓取服务拒绝任务"}],
        }

    job_id = import_data.get("jobId", "")
    store_user_id = _text(import_data.get("userId", ""))
    job_status = import_data.get("status", "")

    if not store_user_id:
        return {
            "ok": False, "errorCode": "SHOP_USER_ID_INVALID", "message": "店铺链接无法识别，请检查后重试",
            "count": 0, "items": [], "keyword": shop_url,
            "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
            "artifact": {"count": 0, "items": [], "keyword": shop_url},
            "steps": [{"step": "解析userId", "status": "error", "detail": "无法解析店铺 userId"}],
        }

    logger.info("[PRODUCT_FETCH/SHOP] 店铺爬取任务 jobId=%s userId=%s status=%s cached=%s",
                job_id, store_user_id, job_status, import_data.get("cached", False))

    # 4) 如果任务未完成，轮询等待（最多 3 分钟）
    if job_status not in ("completed",):
        max_polls = 60  # 60次 × 3秒 = 180秒
        poll_interval = 3
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            try:
                async with _httpx.AsyncClient(timeout=15) as _client:
                    poll_resp = await _client.get(
                        f"{_CRAWLER_BASE}/api/crawl-jobs/{job_id}",
                        headers=headers,
                    )
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
            except Exception as e:
                _log_runtime_failure("poll_shop_crawl", e)
                continue

            job_status = poll_data.get("status", "")
            if job_status == "completed":
                break
            if job_status in ("failed", "unknown"):
                return {
                    "ok": False, "errorCode": "SHOP_CRAWL_FAILED", "message": "店铺抓取失败，请稍后重试",
                    "count": 0, "items": [], "keyword": shop_url,
                    "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
                    "artifact": {"count": 0, "items": [], "keyword": shop_url},
                    "steps": [{"step": "等待抓取", "status": "error", "detail": "抓取任务执行失败"}],
                }
            logger.info("[PRODUCT_FETCH/SHOP] 轮询中 attempt=%d status=%s", i + 1, job_status)
        else:
            return {
                "ok": False, "errorCode": "SHOP_CRAWL_TIMEOUT", "message": "店铺抓取超时，请稍后重试",
                "count": 0, "items": [], "keyword": shop_url,
                "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
                "artifact": {"count": 0, "items": [], "keyword": shop_url},
                "steps": [{"step": "等待爬取", "status": "error", "detail": "爬取超时"}],
            }

    steps.append({"step": "店铺爬取", "status": "success", "detail": f"userId={store_user_id} 爬取完成"})

    # 5) 获取店铺全部商品
    try:
        raw_items: list[dict[str, Any]] = []
        items_page = 1
        expected_total: int | None = None
        async with _httpx.AsyncClient(timeout=30) as _client:
            while items_page <= 20:
                items_resp = await _client.get(
                    f"{_CRAWLER_BASE}/api/goofish/stores/{store_user_id}/items",
                    headers=headers,
                    params={"page": items_page, "pageSize": 500},
                )
                items_resp.raise_for_status()
                items_data = items_resp.json()
                page_items = items_data.get("items")
                total_value = items_data.get("total")
                if not isinstance(page_items, list) or not isinstance(total_value, int) or total_value < 0:
                    raise RuntimeError("crawler store-items response is invalid")
                if expected_total is None:
                    expected_total = total_value
                elif expected_total != total_value:
                    raise RuntimeError("crawler store-items total changed during pagination")
                raw_items.extend(item for item in page_items if isinstance(item, dict))
                if not items_data.get("hasMore"):
                    break
                items_page += 1
            else:
                raise RuntimeError("crawler store-items pagination exceeded 10000 items")
        if expected_total is None or len(raw_items) != expected_total:
            raise RuntimeError("crawler store-items response was incomplete")
    except Exception as e:
        _log_runtime_failure("fetch_shop_items", e)
        return {
            "ok": False, "errorCode": "SHOP_ITEMS_UNAVAILABLE", "message": "店铺商品暂时无法获取，请稍后重试",
            "count": 0, "items": [], "keyword": shop_url,
            "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
            "artifact": {"count": 0, "items": [], "keyword": shop_url},
            "steps": steps + [{"step": "获取商品", "status": "error", "detail": "店铺商品分页结果不可用"}],
        }

    if not raw_items:
        steps.append({"step": "获取商品", "status": "warn", "detail": "店铺无商品"})
        state["all_fetched_items"] = []
        state["product_fetch_page"] = 1
        return {
            "ok": False, "errorCode": "SHOP_EMPTY", "message": "店铺暂无可提取商品",
            "count": 0, "items": [], "keyword": shop_url,
            "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
            "artifact": {"count": 0, "items": [], "keyword": shop_url},
            "steps": steps,
        }

    logger.info("[PRODUCT_FETCH/SHOP] 店铺商品总数=%d", len(raw_items))

    # 按 firstSeenAt 升序排序（保证跨次运行顺序稳定）
    raw_items.sort(key=lambda x: (x.get("firstSeenAt") or "", x.get("id") or 0))

    # 6) 查询去重表：该账号+该店铺已提取过的商品 ID
    dedup_rows = (await db.execute(text("""
        SELECT item_id FROM workflow_shop_fetched_goods
        WHERE tenant_id=:t AND account_id=:a AND store_user_id=:s AND deleted=0
    """), {"t": tenant_id, "a": acct_id, "s": store_user_id})).fetchall()
    already_fetched_ids = {row[0] for row in dedup_rows}

    logger.info(
        "[PRODUCT_FETCH/SHOP] 账号=%d storeRefPresent=%s 已提取=%d个",
        acct_id,
        bool(store_user_id),
        len(already_fetched_ids),
    )

    # 7) 过滤已提取商品 + 敏感词过滤，取前 shop_target_count 个合规商品
    #    ★ 敏感词过滤：命中后台 scene=product 敏感词的商品直接移除，并写入去重表避免下次重复考察。
    #      若首批候选全部命中敏感词，会继续向后取更多候选，直到凑够目标数或耗尽店铺商品池。
    sensitive_words = await _fetch_product_sensitive_words()
    new_items: list[dict] = []              # 保留的合规商品（标准化后）
    considered_items: list[dict] = []       # 本次考察过的所有商品（含命中敏感词的），统一写入去重表
    considered_ids: set[str] = set()        # 本次已考察的 itemId（避免同批内重复）
    sensitive_removed = 0

    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        item_id = _text(raw_item.get("itemId"))
        if item_id and item_id in already_fetched_ids:
            continue
        if item_id and item_id in considered_ids:
            continue
        if item_id:
            considered_ids.add(item_id)
        normalized = _normalize_shop_item(raw_item)
        considered_items.append(normalized)
        # 敏感词检查（与 Java SensitiveWordService.findHits 行为一致：大小写不敏感、子串包含即命中）
        if sensitive_words:
            hit = _item_hits_sensitive_word(normalized, sensitive_words)
            if hit:
                sensitive_removed += 1
                logger.warning(
                    "[PRODUCT_FETCH/SHOP/SENSITIVE] 移除命中敏感词的商品 title=%r hitWord=%s itemId=%s",
                    _text(normalized.get("title", ""))[:80], hit, item_id,
                )
                continue
        new_items.append(normalized)
        if len(new_items) >= shop_target_count:
            break

    # 8) 将本次考察过的所有商品（含命中敏感词的）写入去重表，避免下次重复考察
    workflow_id = context.get("__workflow_id__")
    execution_id = context.get("__execution_id__")
    for item in considered_items:
        item_id = item.get("itemId", "")
        if not item_id:
            continue
        try:
            await db.execute(text("""
                INSERT INTO workflow_shop_fetched_goods(tenant_id, account_id, store_user_id, item_id, workflow_id, execution_id, created_time, deleted)
                VALUES(:t, :a, :s, :i, :wid, :eid, NOW(), 0)
            """), {
                "t": tenant_id, "a": acct_id, "s": store_user_id,
                "i": item_id, "wid": workflow_id, "eid": execution_id,
            })
        except Exception as e:
            _log_runtime_failure("record_shop_item_dedup", e)
    await db.commit()

    if sensitive_removed > 0:
        steps.append({
            "step": "敏感词过滤",
            "status": "warn" if new_items else "error",
            "detail": f"命中敏感词移除 {sensitive_removed} 个商品",
        })

    if not new_items:
        # 所有候选均已被提取或命中敏感词
        if considered_items:
            # 本轮有候选但全部命中敏感词，已写入去重表，下次会取不同候选
            steps.append({"step": "去重过滤", "status": "warn", "detail": f"本次候选 {len(considered_items)} 个全部命中敏感词"})
            state["all_fetched_items"] = []
            state["product_fetch_page"] = 1
            return {
                "ok": False, "errorCode": "SHOP_SENSITIVE_FILTERED", "message": "本次候选商品全部命中敏感词，请重新执行工作流以提取下一批",
                "count": 0, "items": [], "keyword": shop_url,
                "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
                "artifact": {"count": 0, "items": [], "keyword": shop_url},
                "steps": steps,
            }
        steps.append({"step": "去重过滤", "status": "warn", "detail": "所有商品已提取过，无新商品可取"})
        state["all_fetched_items"] = []
        state["product_fetch_page"] = 1
        return {
            "ok": False, "errorCode": "SHOP_EXHAUSTED", "message": "该店铺商品已全部提取",
            "count": 0, "items": [], "keyword": shop_url,
            "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
            "artifact": {"count": 0, "items": [], "keyword": shop_url},
            "steps": steps,
        }

    logger.info(
        "[PRODUCT_FETCH/SHOP] 完成 storeRefPresent=%s 本次提取=%d 累计已提取=%d sensitiveRemoved=%d",
        bool(store_user_id),
        len(new_items),
        len(already_fetched_ids) + len(considered_items),
        sensitive_removed,
    )

    # 10) 更新状态（与关键词搜索保持一致的状态变量）
    state["all_fetched_items"] = new_items
    state["product_fetch_page"] = 1
    state["selected_keywords"] = [shop_url]

    extra_msg = f"，命中敏感词移除 {sensitive_removed} 个" if sensitive_removed > 0 else ""
    steps.append({
        "step": "提取商品",
        "status": "success",
        "detail": f"店铺共 {len(raw_items)} 个商品，已提取 {len(already_fetched_ids)} 个，本次取 {len(new_items)} 个{extra_msg}",
    })

    return {
        "ok": len(new_items) > 0,
        "message": f"成功从店铺提取 {len(new_items)} 个商品（店铺共 {len(raw_items)} 个，已提取过 {len(already_fetched_ids)} 个{extra_msg}）",
        "items": new_items, "count": len(new_items),
        "keyword": shop_url,
        "artifactType": "goods", "artifactTitle": "商品获取(店铺)",
        "artifact": {"count": len(new_items), "items": new_items, "keyword": shop_url},
        "steps": steps,
    }


def _match_category_from_tree(tree: list, title: str) -> dict | None:
    """从分类树中按标题关键词匹配最合适的分类。"""
    if not tree or not title:
        return None
    title_lower = title.lower()
    best_match = None
    best_score = 0

    def _walk(nodes: list, depth: int = 0):
        nonlocal best_match, best_score
        for node in nodes:
            name = (node.get("label") or node.get("title") or "").strip()
            children = node.get("children", [])
            if name:
                # 计算匹配分数：标题中包含分类名的关键词越多越好
                name_parts = [p for p in re.split(r"[/,，\s]", name) if len(p) >= 2]
                score = 0
                for part in name_parts:
                    if part.lower() in title_lower:
                        score += len(part)
                # 叶子节点加分（更具体）
                if not children and score > 0:
                    score += 10
                if score > best_score:
                    best_score = score
                    best_match = {"name": name, "id": node.get("id"), "score": score}
            if children:
                _walk(children, depth + 1)

    _walk(tree)
    if best_match and best_score > 2:
        return best_match
    return None


def _flatten_category_tree(tree: list) -> list[dict]:
    """将分类树平铺为叶子节点列表。"""
    result = []

    def _walk(nodes: list, parents: list[str] | None = None):
        if parents is None:
            parents = []
        for node in nodes:
            name = (node.get("label") or node.get("title") or "").strip()
            children = node.get("children", [])
            current_path = parents + [name]
            if not children:
                result.append({
                    "id": node.get("id"),
                    "name": name,
                    "path": " ＞ ".join(current_path),
                })
            else:
                _walk(children, current_path)

    _walk(tree)
    return result


async def _suggest_category_by_title(
    db: AsyncSession,
    tenant_id: int,
    title: str,
    flat_options: list[dict],
    user_id: Optional[int] = None,
) -> str | None:
    """根据商品标题，从平铺分类列表中智能匹配分类。

    user_id 是 AI 调用的计费归属；无法绑定用户时不会调用 AI。
    """
    if not title or not flat_options:
        return None
    title_lower = title.lower()
    # 1) 精确匹配：标题中包含完整分类名
    for opt in flat_options:
        name = opt.get("name", "").lower()
        if name and name in title_lower:
            return opt["name"]
    # 2) 关键词分段匹配
    best_match = None
    best_score = 0
    for opt in flat_options:
        name = opt.get("name", "")
        name_parts = [p for p in re.split(r"[/,，\s]", name) if len(p) >= 2]
        score = 0
        for part in name_parts:
            if part.lower() in title_lower:
                score += len(part)
        if score > best_score:
            best_score = score
            best_match = opt["name"]
    if best_match and best_score > 3:
        return best_match
    # 3) 使用 AI 建议（需要 AI provider 配置）
    if not user_id or int(user_id) <= 0:
        return None
    try:
        prompt = f"""
根据商品标题，从以下分类列表中选出一个最合适的分类。只返回分类名称，不要任何其他文字。

商品标题：{title}

可选分类：
{chr(10).join(f"- {o['name']} ({o['path']})" for o in flat_options[:200])}
"""
        billing_request_id = build_request_id("workflow_category_suggest")
        await precheck_ai_usage({
            "tenantId": tenant_id,
            "userId": int(user_id),
            "scene": "workflow_category_suggest",
            "providerName": "default",
            "modelName": "default",
            "modelType": "chat",
            "promptTokens": estimate_text_tokens(prompt),
            "completionTokens": 0,
            "requestId": billing_request_id,
        })
        ai_result = await generate_text(
            "workflow_category_suggest",
            "你是闲鱼商品分类专家。根据商品标题从给定分类中选择最合适的分类。只输出分类名称。",
            prompt,
            0.3,
            request_id=billing_request_id,
        )
        if not ai_result.get("ok"):
            return None
        content = _text(ai_result.get("content", "")).strip()
        if content:
            await charge_text_usage(
                tenant_id=tenant_id, user_id=int(user_id), scene="workflow_category_suggest",
                provider_name=_text(ai_result.get("provider")) or "default",
                model_name=_text(ai_result.get("model")) or "default",
                prompt=prompt, completion=content,
                request_id=billing_request_id,
                raw_usage=ai_result.get("usage") or {},
            )
            # 从 AI 返回结果中查找匹配的分类
            for opt in flat_options:
                if opt["name"] == content or content in opt["path"]:
                    return opt["name"]
    except AiBillingError:
        raise
    except Exception as exc:
        _log_runtime_failure("suggest_product_category", exc)
    return None


async def insert_notification(
    db: AsyncSession,
    tenant_id: int,
    user_id: Optional[int],
    title: str,
    content: str,
    notice_type: str = "automation",
    level: str = "info",
) -> None:
    # level 字符串映射为 priority 数字（数据库实际列名为 priority，非 level）
    priority_map = {"info": 0, "warning": 1, "warn": 1, "error": 2}
    priority = priority_map.get(str(level).lower(), 0)
    try:
        await db.execute(text(
            """
            INSERT INTO notification(tenant_id, user_id, notification_type, title, content, priority, is_read, created_time)
            VALUES(:tenant_id, :user_id, :notice_type, :title, :content, :priority, 0, NOW())
            """
        ), {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "notice_type": notice_type,
            "title": title,
            "content": content,
            "priority": priority,
        })
    except Exception as exc:
        _log_runtime_failure("insert_runtime_notification", exc)


async def list_due_tasks(db: AsyncSession, tenant_id: Optional[int] = None, limit: int = 20) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": min(max(limit, 1), 100)}
    tenant_sql = ""
    if tenant_id is not None:
        tenant_sql = " AND tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id
    rows = (await db.execute(text(f"""
        SELECT * FROM scheduled_task
        WHERE deleted = 0
          AND enabled = 1
          {tenant_sql}
          AND (next_run_time IS NULL OR next_run_time <= NOW(6))
          AND (lease_token IS NULL OR lease_expires_at IS NULL OR lease_expires_at <= NOW(6))
        ORDER BY COALESCE(next_run_time, created_time) ASC
        LIMIT :limit
    """), params)).mappings().all()
    return [dict(r) for r in rows]


async def _renew_scheduled_task_lease(
    task_id: int,
    tenant_id: int,
    lease_token: str,
) -> bool:
    """Keep a claimed task exclusive; return False if ownership is lost."""

    renewal_interval = max(1, _SCHEDULED_TASK_LEASE_SECONDS // 3)
    while True:
        await asyncio.sleep(renewal_interval)
        try:
            async with async_session() as lease_db:
                renewed = await lease_db.execute(text("""
                    UPDATE scheduled_task
                    SET lease_expires_at = TIMESTAMPADD(SECOND, :lease_seconds, NOW(6)),
                        updated_time = NOW()
                    WHERE id = :id
                      AND tenant_id = :tenant_id
                      AND lease_token = :lease_token
                      AND enabled = 1
                      AND deleted = 0
                      AND lease_expires_at > NOW(6)
                """), {
                    "id": task_id,
                    "tenant_id": tenant_id,
                    "lease_token": lease_token,
                    "lease_seconds": _SCHEDULED_TASK_LEASE_SECONDS,
                })
                await lease_db.commit()
            if getattr(renewed, "rowcount", 0) != 1:
                return False
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log_runtime_failure("renew_scheduled_task_lease", exc)
            return False


async def _dispatch_scheduled_task(
    db: AsyncSession,
    task: dict[str, Any],
    tenant_id: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    account_id = task.get("account_id")
    task_type = _text(task.get("task_type")).lower()
    if task_type in {"auto_delivery", "delivery", "auto-delivery"}:
        return await process_pending_deliveries(
            db,
            tenant_id=tenant_id,
            account_id=_safe_int(account_id) if account_id is not None else None,
            limit=min(max(_safe_int(config.get("limit"), 20), 1), 100),
        )
    if task_type == "redelivery":
        return await _run_redelivery_task(db, tenant_id, task)
    if task_type == "polish_goods":
        return await _run_polish_goods_task(db, tenant_id, task)
    if task_type == "sync_orders":
        return await _run_sync_orders_task(db, tenant_id, task)
    if task_type == "sync_delivery_status":
        return await _run_sync_delivery_status_task(db, tenant_id, task)
    if task_type == "sync_goods":
        return await _run_sync_goods_task(db, tenant_id, task)
    if task_type == "auto_redelivery":
        return await _run_auto_redelivery_task(db, tenant_id, task)
    if task_type == "one_click_polish":
        return await _run_one_click_polish_task(db, tenant_id, task)
    if task_type == "workflow":
        return await _run_workflow_scheduled_task(db, tenant_id, task)
    if task_type in {"sync_account", "account_sync", "refresh_account"}:
        return await mark_account_synced(
            db,
            tenant_id,
            _safe_int(account_id) if account_id is not None else None,
        )
    if task_type in {"auto_reply", "reply", "auto-reply"}:
        return {
            "ok": False,
            "errorCode": "EVENT_DRIVEN_TASK",
            "message": "自动回复是事件驱动能力，不能作为定时任务执行",
            "terminal": True,
        }
    return {
        "ok": False,
        "errorCode": "UNSUPPORTED_TASK_TYPE",
        "message": f"不支持的定时任务类型: {task_type or '-'}",
        "terminal": True,
    }


async def _run_task_under_lease(
    db: AsyncSession,
    task: dict[str, Any],
    tenant_id: int,
    config: dict[str, Any],
    lease_token: str,
) -> tuple[dict[str, Any], bool]:
    """Cancel task work immediately when the independent lease heartbeat fails."""

    async def run_body() -> dict[str, Any]:
        try:
            return await _dispatch_scheduled_task(db, task, tenant_id, config)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log_runtime_failure("execute_scheduled_task_body", exc)
            return {
                "ok": False,
                "errorCode": "SCHEDULED_TASK_FAILED",
                "message": "定时任务执行失败，请稍后重试",
            }

    body_task = asyncio.create_task(run_body())
    renewal_task = asyncio.create_task(
        _renew_scheduled_task_lease(int(task["id"]), tenant_id, lease_token)
    )
    try:
        done, _ = await asyncio.wait(
            {body_task, renewal_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if renewal_task in done:
            lease_owned = await renewal_task
            if not lease_owned:
                body_task.cancel()
                try:
                    await body_task
                except asyncio.CancelledError:
                    pass
                return {
                    "ok": False,
                    "errorCode": "TASK_LEASE_LOST",
                    "message": "定时任务执行归属已丢失，本执行器已停止处理",
                }, False
        result = await body_task
        return result, True
    finally:
        for running in (body_task, renewal_task):
            if not running.done():
                running.cancel()
        await asyncio.gather(body_task, renewal_task, return_exceptions=True)


async def _complete_scheduled_task_lease(
    db: AsyncSession,
    *,
    task: dict[str, Any],
    tenant_id: int,
    lease_token: str,
    result: dict[str, Any],
    config: dict[str, Any],
) -> tuple[bool, bool]:
    succeeded = result.get("ok") is True
    terminal = result.get("terminal") is True
    interval = min(max(_safe_int(config.get("intervalMinutes"), 5), 1), 10_080)
    max_failures = 1 if terminal else min(
        max(_safe_int(config.get("maxConsecutiveFailures"), 5), 1),
        20,
    )
    prior_failures = max(_safe_int(task.get("consecutive_failure_count"), 0), 0)
    disable_after_failure = not succeeded and prior_failures + 1 >= max_failures
    last_status = (
        "success" if succeeded
        else "disabled_after_failures" if disable_after_failure
        else "failed"
    )
    completed = await db.execute(text("""
        UPDATE scheduled_task
        SET last_run_time = NOW(6),
            next_run_time = TIMESTAMPADD(MINUTE, :interval, NOW(6)),
            last_status = :last_status,
            last_result = :last_result,
            last_finished_time = NOW(6),
            consecutive_failure_count = CASE
                WHEN :succeeded = 1 THEN 0
                ELSE COALESCE(consecutive_failure_count, 0) + 1
            END,
            enabled = CASE WHEN :disable_after_failure = 1 THEN 0 ELSE enabled END,
            lease_token = NULL,
            lease_owner = NULL,
            lease_expires_at = NULL,
            updated_time = NOW()
        WHERE id = :id
          AND tenant_id = :tenant_id
          AND lease_token = :lease_token
          AND lease_expires_at > NOW(6)
          AND deleted = 0
    """), {
        "id": int(task["id"]),
        "tenant_id": tenant_id,
        "lease_token": lease_token,
        "interval": interval,
        "last_status": last_status,
        "last_result": json.dumps(result, ensure_ascii=False)[:4000],
        "succeeded": 1 if succeeded else 0,
        "disable_after_failure": 1 if disable_after_failure else 0,
    })
    if getattr(completed, "rowcount", 0) != 1:
        rollback = getattr(db, "rollback", None)
        if rollback is not None:
            await rollback()
        return False, disable_after_failure
    await db.commit()
    return True, disable_after_failure


async def claim_scheduled_task_lease(
    db: AsyncSession,
    task_id: int,
    tenant_id: int,
    *,
    manual: bool = False,
) -> tuple[Optional[dict[str, Any]], Optional[str], dict[str, Any]]:
    """仅做 lease claim + reload task，不执行任务体。

    返回 (task_dict, lease_token, error_dict)：
    - 成功：(task, lease_token, {})
    - 失败：(None, None, {"ok": False, "error": "...", ...})

    拆分自 execute_scheduled_task，用于支持「立即返回，后台异步执行」模式：
    内部调度器通过 execute_scheduled_task 调用本函数后同步执行剩余部分；
    外部 HTTP 手动触发通过 internal_run_task 调用本函数后启动后台任务。
    """
    task_id = _safe_int(task_id)
    scoped_tenant_id = _safe_int(tenant_id)
    if task_id <= 0 or scoped_tenant_id <= 0:
        return None, None, {
            "ok": False,
            "claimed": False,
            "error": "TASK_SCOPE_INVALID",
            "message": "定时任务或租户范围无效",
            "taskId": task_id,
        }

    lease_token = uuid.uuid4().hex
    due_condition = "" if manual else "AND (next_run_time IS NULL OR next_run_time <= NOW(6))"
    claim = await db.execute(text(f"""
        UPDATE scheduled_task
        SET lease_token = :lease_token,
            lease_owner = :lease_owner,
            lease_expires_at = TIMESTAMPADD(SECOND, :lease_seconds, NOW(6)),
            last_status = 'running',
            last_started_time = NOW(6),
            run_attempt_count = COALESCE(run_attempt_count, 0) + 1,
            updated_time = NOW()
        WHERE id = :id
          AND tenant_id = :tenant_id
          AND enabled = 1
          AND deleted = 0
          {due_condition}
          AND (lease_token IS NULL OR lease_expires_at IS NULL OR lease_expires_at <= NOW(6))
    """), {
        "id": task_id,
        "tenant_id": scoped_tenant_id,
        "lease_token": lease_token,
        "lease_owner": _SCHEDULED_TASK_EXECUTOR_ID,
        "lease_seconds": _SCHEDULED_TASK_LEASE_SECONDS,
    })
    await db.commit()
    if getattr(claim, "rowcount", 0) != 1:
        return None, None, {
            "ok": False,
            "claimed": False,
            "error": "TASK_ALREADY_RUNNING",
            "message": "定时任务正在其他执行器中运行或已不可用",
            "taskId": task_id,
        }

    params: dict[str, Any] = {
        "id": task_id,
        "tenant_id": scoped_tenant_id,
        "lease_token": lease_token,
    }
    task = (await db.execute(text("""
        SELECT * FROM scheduled_task
        WHERE id = :id AND tenant_id = :tenant_id AND deleted = 0
          AND lease_token = :lease_token
        LIMIT 1
    """), params)).mappings().first()
    if not task:
        return None, None, {
            "ok": False,
            "claimed": True,
            "error": "TASK_LEASE_LOST",
            "message": "定时任务执行归属已丢失",
            "taskId": task_id,
        }

    return dict(task), lease_token, {}


async def execute_scheduled_task(
    db: AsyncSession,
    task_id: int,
    tenant_id: Optional[int] = None,
    *,
    manual: bool = False,
) -> dict[str, Any]:
    """同步执行定时任务（用于内部 cron 调度器）。

    外部 HTTP 手动触发请使用 claim_scheduled_task_lease + _run_scheduled_task_in_background 组合，
    避免长耗时任务（如 auto_redelivery 多账号同步订单+批量发货）阻塞 HTTP 请求导致前端超时。
    """
    scoped_tenant_id = _safe_int(tenant_id)
    task, lease_token, claim_error = await claim_scheduled_task_lease(
        db, task_id, scoped_tenant_id, manual=manual
    )
    if task is None:
        return claim_error

    task_id = _safe_int(task.get("id", task_id))
    t_id = _safe_int(task.get("tenant_id"), scoped_tenant_id)
    task_type = _text(task.get("task_type")).lower()
    config = _task_config(task)

    result, lease_owned = await _run_task_under_lease(
        db,
        task,
        t_id,
        config,
        lease_token,
    )
    if not lease_owned:
        if result.get("errorCode"):
            result["error"] = result["errorCode"]
        result.update({"claimed": True, "taskId": task_id, "taskType": task_type})
        return result

    result = _sanitize_runtime_value(
        result,
        failure_context=result.get("ok") is False,
        default_code="SCHEDULED_TASK_FAILED",
    )
    if result.get("ok") is False and result.get("errorCode"):
        result["error"] = result["errorCode"]
    result.update({"claimed": True, "taskId": task_id, "taskType": task_type})
    completed, disabled = await _complete_scheduled_task_lease(
        db,
        task=task,
        tenant_id=t_id,
        lease_token=lease_token,
        result=result,
        config=config,
    )
    if not completed:
        return {
            "ok": False,
            "claimed": True,
            "error": "TASK_LEASE_LOST",
            "message": "定时任务结果未能由当前执行器确认",
            "taskId": task_id,
            "taskType": task_type,
        }
    if disabled:
        result["disabledAfterFailures"] = True
    try:
        await insert_notification(
            db,
            t_id,
            None,
            "定时任务已执行",
            f"任务 {task.get('task_name') or task_id} 执行结果：{result.get('message') or result}",
            "scheduled_task",
            "info" if result.get("ok") is True else "warning",
        )
        await db.commit()
    except Exception as exc:
        rollback = getattr(db, "rollback", None)
        if rollback is not None:
            await rollback()
        _log_runtime_failure("notify_scheduled_task_completion", exc)
    return result


async def _run_scheduled_task_in_background(
    task: dict[str, Any],
    tenant_id: int,
    lease_token: str,
) -> None:
    """后台执行定时任务（claim 后剩余部分：执行 + lease 释放 + 通知）。

    使用独立 db session，避免依赖请求 scoped session。
    失败时记录日志并强制释放 lease，避免任务永久卡在 running 状态。
    """
    task_id = _safe_int(task.get("id"))
    task_type = _text(task.get("task_type")).lower()
    task_name = task.get("task_name") or task_id
    t_id = _safe_int(task.get("tenant_id"), tenant_id)
    config = _task_config(task)

    try:
        async with async_session() as bg_db:
            result, lease_owned = await _run_task_under_lease(
                bg_db, task, t_id, config, lease_token,
            )
            if not lease_owned:
                logger.warning(
                    "后台定时任务 lease 丢失 taskId=%d taskType=%s",
                    task_id, task_type,
                )
                return

            result = _sanitize_runtime_value(
                result,
                failure_context=result.get("ok") is False,
                default_code="SCHEDULED_TASK_FAILED",
            )
            if result.get("ok") is False and result.get("errorCode"):
                result["error"] = result["errorCode"]
            result.update({"claimed": True, "taskId": task_id, "taskType": task_type})
            completed, disabled = await _complete_scheduled_task_lease(
                bg_db,
                task=task,
                tenant_id=t_id,
                lease_token=lease_token,
                result=result,
                config=config,
            )
            if not completed:
                logger.warning(
                    "后台定时任务 lease 完成失败 taskId=%d taskType=%s",
                    task_id, task_type,
                )
                return
            if disabled:
                result["disabledAfterFailures"] = True
            try:
                await insert_notification(
                    bg_db, t_id, None,
                    "定时任务已执行",
                    f"任务 {task_name} 执行结果：{result.get('message') or result}",
                    "scheduled_task",
                    "info" if result.get("ok") is True else "warning",
                )
                await bg_db.commit()
            except Exception as exc:
                rollback = getattr(bg_db, "rollback", None)
                if rollback is not None:
                    await rollback()
                _log_runtime_failure("notify_scheduled_task_completion", exc)

            logger.info(
                "后台定时任务执行完成 taskId=%d taskType=%s ok=%s",
                task_id, task_type, result.get("ok"),
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _log_runtime_failure("run_scheduled_task_in_background", exc)
        # 即使执行失败也要释放 lease，避免任务永久卡在 running 状态
        try:
            async with async_session() as cleanup_db:
                await cleanup_db.execute(text("""
                    UPDATE scheduled_task
                    SET last_status = 'failed',
                        last_finished_time = NOW(6),
                        last_result = :last_result,
                        lease_token = NULL,
                        lease_owner = NULL,
                        lease_expires_at = NULL,
                        next_run_time = TIMESTAMPADD(MINUTE, 5, NOW(6)),
                        consecutive_failure_count = COALESCE(consecutive_failure_count, 0) + 1,
                        updated_time = NOW()
                    WHERE id = :id AND tenant_id = :tenant_id AND lease_token = :lease_token
                """), {
                    "id": task_id,
                    "tenant_id": t_id,
                    "lease_token": lease_token,
                    "last_result": json.dumps({"ok": False, "message": f"后台执行异常: {type(exc).__name__}"}, ensure_ascii=False)[:4000],
                })
                await cleanup_db.commit()
        except Exception:
            pass


def _task_config(task: dict[str, Any]) -> dict[str, Any]:
    config_json = task.get("config_json")
    if not config_json:
        return {}
    try:
        return json.loads(config_json)
    except Exception:
        return {}


async def _run_polish_goods_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    config = _task_config(task)
    account_id = _safe_int(task.get("account_id") or config.get("accountId") or config.get("account_id"))
    if not account_id:
        return {"ok": False, "errorCode": "POLISH_TASK_ACCOUNT_REQUIRED", "message": "商品擦亮任务缺少账号", "processed": 0}

    from app.api.v1.routes.items import _submit_polish_task

    response = await _submit_polish_task(
        db=db,
        account_id=account_id,
        tenant_id=tenant_id,
    )
    payload = response.data if isinstance(response.data, dict) else {}
    result = dict(payload)
    result["ok"] = response.code == 200
    if response.code == 200:
        result["message"] = response.msg or result.get("message") or "商品擦亮任务已提交"
    else:
        result["errorCode"] = "POLISH_TASK_FAILED"
        result["message"] = "商品擦亮任务提交失败，请稍后重试"
    result["processed"] = _safe_int(result.get("processed"), _safe_int(result.get("total"), 0))
    result["taskType"] = task.get("task_type")
    result["accountId"] = account_id
    return result


async def _run_redelivery_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    config = _task_config(task)
    record_id = _safe_int(config.get("recordId") or config.get("record_id"))
    if not record_id:
        return {"ok": False, "errorCode": "REDELIVERY_RECORD_REQUIRED", "message": "补发货任务缺少记录编号", "processed": 0}

    row = (await db.execute(text("""
        SELECT dr.id, dr.account_id, dr.order_id, dr.status,
               COALESCE(dr.delivery_content, dr.content) AS delivery_content,
               o.buyer_id, o.external_order_id, o.item_id, o.is_bargain
        FROM delivery_record dr
        JOIN xianyu_trade_order o
          ON o.tenant_id = dr.tenant_id
          AND (o.id = dr.order_id OR o.external_order_id = dr.order_id)
        WHERE dr.id = :record_id AND dr.tenant_id = :tenant_id AND dr.deleted = 0
        LIMIT 1
    """), {"record_id": record_id, "tenant_id": tenant_id})).mappings().first()
    if not row:
        return {"ok": False, "errorCode": "REDELIVERY_RECORD_NOT_FOUND", "message": "补发货记录不存在", "processed": 0, "recordId": record_id}

    # 门控：若该记录已处于成功状态（status IN (1,2)），拒绝重发，避免对同一买家重复发送货源信息
    # 历史问题：用户看到"订单待发货"会误以为没发货，反复点补发 → 反复发送货源信息
    existing_status = _safe_int(row.get("status"))
    if existing_status in (1, 2):
        return {
            "ok": True,
            "errorCode": "REDELIVERY_ALREADY_SUCCESS",
            "message": "该发货记录已成功发送，无需重复补发",
            "processed": 0,
            "recordId": record_id,
            "deliveryStatus": "success" if existing_status == 2 else "pending",
        }

    row = dict(row)
    account_id = _safe_int(row.get("account_id"))
    buyer_id = _text(row.get("buyer_id"))
    content = _text(row.get("delivery_content"))
    if not account_id or not buyer_id or not content:
        error_message = "补发货缺少买家或发货内容"
        await db.execute(text("""
            UPDATE delivery_record
            SET status = 3,
                delivery_status = 'failed',
                error_message = :error_message,
                fail_reason = :error_message,
                retry_count = COALESCE(retry_count, 0) + 1,
                updated_time = NOW()
            WHERE id = :record_id AND tenant_id = :tenant_id
        """), {"record_id": record_id, "tenant_id": tenant_id, "error_message": error_message})
        return {"ok": False, "errorCode": "REDELIVERY_DATA_INCOMPLETE", "message": error_message, "processed": 0, "recordId": record_id}

    send_ok = await _send_delivery_message_via_ws(db, tenant_id, account_id, buyer_id, content)
    if send_ok:
        # 先调用闲鱼确认发货 API，只有平台真正标记为已发货后才更新本地 order_status=3
        # 补发货场景下订单可能已标记为已发货（order_status=3），此时保持原状态
        # 若订单尚未标记为已发货，则只有确认发货成功才标记
        confirm_success = False
        confirm_error_msg = "确认发货能力不可用"
        external_order_id_for_confirm = _text(row.get("external_order_id"))
        is_bargain_for_confirm = _safe_int(row.get("is_bargain")) == 1
        try:
            from .xianyu_api_service import confirm_order_shipment
            confirm_result = await asyncio.to_thread(
                confirm_order_shipment,
                account_id,
                external_order_id_for_confirm,
                is_bargain=is_bargain_for_confirm,
                item_id=_text(row.get("item_id")),
                buyer_id=buyer_id,
            )
            if confirm_result and confirm_result.get("success"):
                confirm_success = True
                logger.info(
                    "补发货确认发货成功: accountId=%d orderId=%s",
                    account_id, external_order_id_for_confirm,
                )
            else:
                confirm_error_msg = (confirm_result.get("message") if confirm_result else "确认发货失败") or "确认发货失败"
                logger.warning(
                    "补发货确认发货失败: accountId=%d orderId=%s error=%s",
                    account_id, external_order_id_for_confirm, confirm_error_msg,
                )
        except Exception as e:
            confirm_error_msg = f"确认发货异常: {type(e).__name__}"
            _log_runtime_failure("redelivery_confirm", e)

        await db.execute(text("""
            UPDATE delivery_record
            SET status = 2,
                delivery_status = 'success',
                error_message = NULL,
                fail_reason = NULL,
                retry_count = COALESCE(retry_count, 0) + 1,
                delivery_time = NOW(),
                completed_time = NOW(),
                updated_time = NOW()
            WHERE id = :record_id AND tenant_id = :tenant_id
        """), {"record_id": record_id, "tenant_id": tenant_id})

        if confirm_success:
            await db.execute(text("""
                UPDATE xianyu_trade_order
                SET order_status = 3,
                    ship_time = COALESCE(ship_time, NOW()),
                    updated_time = NOW()
                WHERE id = :order_id AND tenant_id = :tenant_id
            """), {"order_id": row.get("order_id"), "tenant_id": tenant_id})
            return {"ok": True, "message": "补发货成功", "processed": 1, "recordId": record_id}
        else:
            # 确认发货失败：发货消息已补发，但闲鱼平台未标记为已发货
            # 不更新 order_status，等待下次同步或重试
            return {"ok": True, "message": f"补发货消息已发送，但确认发货失败：{confirm_error_msg}", "processed": 1, "recordId": record_id, "confirmFailed": True}

    error_message = "WS发送失败"
    await db.execute(text("""
        UPDATE delivery_record
        SET status = 3,
            delivery_status = 'failed',
            error_message = :error_message,
            fail_reason = :error_message,
            retry_count = COALESCE(retry_count, 0) + 1,
            updated_time = NOW()
        WHERE id = :record_id AND tenant_id = :tenant_id
    """), {"record_id": record_id, "tenant_id": tenant_id, "error_message": error_message})
    return {"ok": False, "errorCode": "REDELIVERY_SEND_FAILED", "message": "补发货消息发送失败，请稍后重试", "processed": 0, "recordId": record_id}


def _parse_remote_order_time(value: Any) -> Optional[datetime.datetime]:
    text_value = _text(value).strip()
    if not text_value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text_value, fmt)
        except ValueError:
            continue
    return None


def _parse_remote_order_amount(total_price: Any, unit_price: Any, quantity: int) -> str:
    raw_total = _text(total_price).strip()
    if raw_total:
        try:
            return f"{Decimal(raw_total):.2f}"
        except (InvalidOperation, ValueError):
            pass
    raw_unit = _text(unit_price).strip()
    if raw_unit:
        try:
            return f"{(Decimal(raw_unit) * max(quantity, 1)):.2f}"
        except (InvalidOperation, ValueError):
            pass
    return "0.00"


def _map_remote_order_status(raw_status: Any, in_refund: bool = False) -> int:
    if in_refund:
        return 2
    status_text = _text(raw_status).strip()
    status_map = {
        "待付款": 0,
        "已付款": 1,
        "待发货": 2,
        "已发货": 3,
        "交易成功": 4,
        "交易关闭": 5,
        "退款中": 2,
        "退款成功": 5,
        "已退款": 5,
        "退款关闭": 5,
    }
    return status_map.get(status_text, 1)


def _parse_remote_sold_order_item(item: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    common = item.get("commonData") if isinstance(item.get("commonData"), dict) else {}
    buyer_info = item.get("buyerInfoVO") if isinstance(item.get("buyerInfoVO"), dict) else {}
    price_vo = item.get("priceVO") if isinstance(item.get("priceVO"), dict) else {}
    item_info = item.get("itemInfoVO") if isinstance(item.get("itemInfoVO"), dict) else {}
    item_buy_info = common.get("itemBuyInfo") if isinstance(common.get("itemBuyInfo"), dict) else {}

    external_order_id = _text(common.get("orderId") or "").strip()
    if not external_order_id:
        return None

    quantity = _safe_int(price_vo.get("buyNum"), 1)
    if quantity <= 0:
        quantity = 1

    goods_id = _text(common.get("itemId") or item_info.get("itemId") or item_buy_info.get("itemId") or "").strip()
    goods_title = (
        _text(item.get("itemTitle") or "")
        or _text(common.get("itemTitle") or "")
        or _text(item_info.get("title") or "")
        or _text(item_buy_info.get("title") or "")
        or (f"商品 {goods_id}" if goods_id else "订单商品")
    )
    goods_image = (
        _text(item.get("itemMainPic") or "")
        or _text(common.get("itemMainPic") or "")
        or _text(item_info.get("itemPic") or "")
        or _text(item_buy_info.get("itemPic") or "")
    )
    goods_price = _text(price_vo.get("auctionPrice") or price_vo.get("unitPrice") or "").strip()
    total_amount = _parse_remote_order_amount(price_vo.get("totalPrice"), goods_price, quantity)

    return {
        "externalOrderId": external_order_id,
        "buyerName": _text(buyer_info.get("userNick") or buyer_info.get("name") or "").strip(),
        "buyerId": _text(buyer_info.get("buyerId") or "").strip(),
        "orderStatus": _map_remote_order_status(common.get("orderStatus"), _text(common.get("inRefund")).lower() == "true"),
        "totalAmount": total_amount,
        "createTime": _parse_remote_order_time(common.get("createTime")),
        "payTime": _parse_remote_order_time(common.get("payTime") or common.get("paymentTime")),
        "shipTime": _parse_remote_order_time(common.get("deliveryTime") or common.get("consignTime") or common.get("shipTime")),
        "confirmTime": _parse_remote_order_time(common.get("endTime") or common.get("confirmTime")),
        "buyerMessage": _text(common.get("buyerMessage") or common.get("leaveMessage") or "").strip(),
        "itemId": goods_id,
        "isBargain": 0,
        "isRated": 0,
        "isRedFlower": 0,
        "items": [
            {
                "goodsId": goods_id,
                "goodsTitle": goods_title.strip(),
                "goodsImage": goods_image.strip(),
                "goodsPrice": goods_price or total_amount,
                "goodsCount": quantity,
                "quantity": quantity,
            }
        ],
    }


async def _load_order_sync_account(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> Optional[dict[str, Any]]:
    row = (await db.execute(text("""
        SELECT id AS accountId, external_uid AS externalUid
        FROM xianyu_account
        WHERE tenant_id = :tenant_id AND id = :account_id AND deleted = 0
        LIMIT 1
    """), {"tenant_id": tenant_id, "account_id": account_id})).mappings().first()
    return dict(row) if row else None


async def _fetch_remote_sold_orders_page(
    account_id: int,
    page_number: int,
    query_code: str = "ALL",
) -> dict[str, Any]:
    from .xianyu_api_service import fetch_sold_orders_page

    result = await asyncio.to_thread(
        fetch_sold_orders_page,
        account_id,
        page_number,
        30,
        query_code,
    )
    if not result or not result.get("success"):
        raise PublicRuntimeError("ORDER_SYNC_PARTIAL", "部分订单同步失败，请稍后重试")
    payload = result.get("data") or {}
    return {
        "items": payload.get("items") or [],
        "nextPage": bool(payload.get("nextPage")),
        "totalCount": _safe_int(payload.get("totalCount")),
    }


async def _fetch_remote_sold_orders(
    account_id: int,
    query_code: str = "ALL",
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen_order_ids: set[str] = set()
    page_number = 1
    page = await _fetch_remote_sold_orders_page(account_id, page_number, query_code=query_code)
    total_count = _safe_int(page.get("totalCount"))
    total_pages = max(1, math.ceil(total_count / 30)) if total_count > 0 else None
    if max_pages is not None and max_pages > 0:
        total_pages = min(total_pages, max_pages) if total_pages is not None else max_pages

    while True:
        for item in page.get("items") or []:
            parsed = _parse_remote_sold_order_item(item)
            if not parsed:
                continue
            order_id = _text(parsed.get("externalOrderId") or "")
            if order_id in seen_order_ids:
                continue
            seen_order_ids.add(order_id)
            collected.append(parsed)

        reached_total_pages = total_pages is not None and page_number >= total_pages
        if reached_total_pages:
            break
        if max_pages is not None and max_pages > 0 and page_number >= max_pages:
            break
        if not page.get("nextPage") and (total_pages is None or page_number >= total_pages):
            break
        page_number += 1
        # 翻页失败时返回已收集的部分订单，而非全部丢失
        # （令牌过期等错误已在 fetch_sold_orders_page 内部处理重试，此处多为不可恢复错误）
        try:
            page = await _fetch_remote_sold_orders_page(account_id, page_number, query_code=query_code)
        except Exception as exc:
            _log_runtime_failure("fetch_remote_sold_orders_page", exc)
            break
    return collected


# 退款订单 disputeStatus → 本地订单状态映射
# 1/2/3 = 退款中 → 2（与 _map_remote_order_status 中"退款中"映射一致）
# 5 = 退款成功 → 5（与"退款成功/已退款"映射一致）
_REFUND_DISPUTE_STATUS_MAP = (("1", 2), ("2", 2), ("3", 2), ("5", 5))


async def _fetch_remote_refund_orders_page(
    account_id: int,
    dispute_status: str,
) -> list[dict[str, Any]]:
    from .xianyu_api_service import fetch_refund_orders_page

    result = await asyncio.to_thread(fetch_refund_orders_page, account_id, dispute_status)
    if not result or not result.get("success"):
        logger.warning(
            "runtimeFailure operation=fetch_remote_refund_orders errorType=ProviderRejected requestId=%s",
            get_request_id() or "-",
        )
        return []
    payload = result.get("data") or {}
    return payload.get("items") or []


async def _fetch_remote_refund_orders(account_id: int) -> list[dict[str, Any]]:
    """拉取闲鱼退款订单（4 种 disputeStatus 各取首页），解析为订单字典列表。

    退款订单与卖家已售订单结构相同（commonData/buyerInfoVO/priceVO），
    复用 _parse_remote_sold_order_item 解析后覆盖 orderStatus 为退款状态。
    已存在的订单会被 upsert 更新状态，缺失的订单会被补充入库。
    """
    collected: list[dict[str, Any]] = []
    seen_order_ids: set[str] = set()
    for dispute_status, refund_status in _REFUND_DISPUTE_STATUS_MAP:
        try:
            raw_items = await _fetch_remote_refund_orders_page(account_id, dispute_status)
        except Exception as exc:
            _log_runtime_failure("fetch_remote_refund_orders", exc)
            continue
        for item in raw_items:
            parsed = _parse_remote_sold_order_item(item)
            if not parsed:
                continue
            order_id = _text(parsed.get("externalOrderId") or "")
            if not order_id or order_id in seen_order_ids:
                continue
            # 覆盖为退款状态，确保已售订单列表中的退款订单状态被更新
            parsed["orderStatus"] = refund_status
            seen_order_ids.add(order_id)
            collected.append(parsed)
    return collected


async def _replace_remote_order_items(
    db: AsyncSession,
    tenant_id: int,
    order_id: int,
    items: list[dict[str, Any]],
) -> None:
    await db.execute(text("""
        UPDATE xianyu_trade_order_item
        SET deleted = 1, updated_time = NOW()
        WHERE tenant_id = :tenant_id AND order_id = :order_id AND deleted = 0
    """), {"tenant_id": tenant_id, "order_id": order_id})

    for item in items:
        # 闲鱼 MTOP 返回的 goodsId 是 external_goods_id（如 1065651182579），
        # 需同时填入 external_goods_id 字段，并尝试映射到 xianyu_goods.id 内部 ID。
        ext_goods_id = _text(item.get("goodsId") or "").strip()
        internal_goods_id = None
        if ext_goods_id:
            g_row = (await db.execute(
                text("SELECT id FROM xianyu_goods WHERE tenant_id=:tid AND external_goods_id=:ext AND deleted=0 ORDER BY id DESC LIMIT 1"),
                {"tid": tenant_id, "ext": ext_goods_id},
            )).mappings().first()
            if g_row:
                internal_goods_id = _safe_int(g_row.get("id")) or None

        await db.execute(text("""
            INSERT INTO xianyu_trade_order_item(
                order_id, tenant_id, goods_id, external_goods_id, goods_title, goods_image,
                goods_price, goods_count, quantity, deleted, created_time, updated_time
            ) VALUES (
                :order_id, :tenant_id, :goods_id, :external_goods_id, :goods_title, :goods_image,
                :goods_price, :goods_count, :quantity, 0, NOW(), NOW()
            )
        """), {
            "order_id": order_id,
            "tenant_id": tenant_id,
            "goods_id": internal_goods_id,
            "external_goods_id": ext_goods_id or None,
            "goods_title": _text(item.get("goodsTitle") or "").strip() or None,
            "goods_image": _text(item.get("goodsImage") or "").strip() or None,
            "goods_price": _text(item.get("goodsPrice") or "0").strip() or "0",
            "goods_count": max(_safe_int(item.get("goodsCount"), 1), 1),
            "quantity": max(_safe_int(item.get("quantity"), _safe_int(item.get("goodsCount"), 1)), 1),
        })


async def _backfill_missing_goods_from_orders(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    orders: list[dict[str, Any]],
) -> int:
    """订单同步后补全缺失的商品记录。

    订单中的 item_id 是闲鱼外部商品 ID。如果 xianyu_goods 表中不存在该商品，
    则用订单中已有的商品信息（itemId/title/image/price）创建最小商品记录。
    这确保后续发货配置（delivery_goods_config）能通过 external_goods_id → xianyu_goods.id 链路命中。

    不调用闲鱼详情 API，避免触发风控；商品信息会在下次商品同步时补全。
    """
    if not orders:
        return 0

    # 收集所有订单中的商品信息（去重）
    goods_map: dict[str, dict[str, Any]] = {}
    for order in orders:
        item_id = _text(order.get("itemId") or "").strip()
        if not item_id:
            continue
        if item_id in goods_map:
            continue
        items = order.get("items") or []
        first_item = items[0] if items else {}
        goods_map[item_id] = {
            "external_goods_id": item_id,
            "title": _text(first_item.get("goodsTitle") or order.get("itemTitle") or f"商品 {item_id}"),
            "image_url": _text(first_item.get("goodsImage") or ""),
            "price": _text(first_item.get("goodsPrice") or order.get("totalAmount") or ""),
        }

    if not goods_map:
        return 0

    # 批量查询哪些商品已存在
    item_ids = list(goods_map.keys())
    placeholders = ", ".join(f":id_{i}" for i in range(len(item_ids)))
    params = {f"id_{i}": item_ids[i] for i in range(len(item_ids))}
    params["tenant_id"] = tenant_id
    params["account_id"] = account_id
    # 注意：查询不再过滤 deleted=0。
    # 如果只查未删除记录，被软删除（deleted=1）的商品会被误判为"不存在"，
    # 然后下方 INSERT 会创建一条新的 deleted=0 重复记录，导致幽灵商品反复出现：
    #   - 商品同步把远程不存在的商品标记 deleted=1
    #   - 订单同步查 deleted=0 找不到 → INSERT 新的 deleted=0 记录
    #   - 下次同步又把这条新记录标记 deleted=1，无限循环
    # 修复后查询覆盖所有 deleted 状态，已存在记录（无论是否软删除）都跳过。
    existing_rows = (await db.execute(text(f"""
        SELECT external_goods_id FROM xianyu_goods
        WHERE tenant_id = :tenant_id AND account_id = :account_id
          AND external_goods_id IN ({placeholders})
    """), params)).mappings().all()
    existing_ids = {row.get("external_goods_id") for row in existing_rows}

    # 对缺失的商品创建最小记录
    backfilled = 0
    for item_id, info in goods_map.items():
        if item_id in existing_ids:
            continue
        try:
            await db.execute(text("""
                INSERT INTO xianyu_goods (
                    tenant_id, account_id, external_goods_id, goods_id, title,
                    price, sold_price, cover_pic, image_url, status,
                    deleted, created_time, updated_time
                ) VALUES (
                    :tenant_id, :account_id, :external_goods_id, :goods_id, :title,
                    :price, :price, :image_url, :image_url, 1,
                    0, NOW(), NOW()
                )
            """), {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "external_goods_id": item_id,
                "goods_id": item_id,
                "title": info["title"][:255] if info["title"] else f"商品 {item_id}",
                "price": info["price"][:32] if info["price"] else "0",
                "image_url": info["image_url"][:500] if info["image_url"] else None,
            })
            backfilled += 1
        except Exception:
            # 唯一约束冲突等异常跳过，不影响其他商品
            continue

    if backfilled > 0:
        logger.info(
            "订单同步自动补全商品记录 tenantId=%d accountId=%d backfilled=%d/%d",
            tenant_id, account_id, backfilled, len(goods_map)
        )
    return backfilled


async def _upsert_remote_sold_order(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    order: dict[str, Any],
) -> str:
    external_order_id = _text(order.get("externalOrderId") or "").strip()
    if not external_order_id:
        return "skipped"

    existing = (await db.execute(text("""
        SELECT id
        FROM xianyu_trade_order
        WHERE tenant_id = :tenant_id
          AND account_id = :account_id
          AND external_order_id = :external_order_id
          AND deleted = 0
        LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "external_order_id": external_order_id,
    })).mappings().first()

    params = {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "external_order_id": external_order_id,
        "order_status": _safe_int(order.get("orderStatus"), 1),
        "total_amount": _text(order.get("totalAmount") or "0.00"),
        "buyer_name": _text(order.get("buyerName") or "").strip() or None,
        "buyer_id": _text(order.get("buyerId") or "").strip() or None,
        "create_time": order.get("createTime"),
        "pay_time": order.get("payTime"),
        "ship_time": order.get("shipTime"),
        "confirm_time": order.get("confirmTime"),
        "buyer_message": _text(order.get("buyerMessage") or "").strip() or None,
        "item_id": _text(order.get("itemId") or "").strip() or None,
        "is_bargain": _safe_int(order.get("isBargain"), 0),
        "is_rated": _safe_int(order.get("isRated"), 0),
        "is_red_flower": _safe_int(order.get("isRedFlower"), 0),
    }

    if existing:
        await db.execute(text("""
            UPDATE xianyu_trade_order
            SET order_status = CASE
                    WHEN order_status = 3 AND :order_status IN (1, 2)
                             AND ship_time IS NOT NULL
                             AND ship_time > DATE_SUB(NOW(), INTERVAL 30 MINUTE)
                        THEN order_status
                    ELSE :order_status
                END,
                total_amount = :total_amount,
                buyer_name = :buyer_name,
                buyer_id = :buyer_id,
                create_time = COALESCE(:create_time, create_time),
                pay_time = COALESCE(:pay_time, pay_time),
                ship_time = COALESCE(:ship_time, ship_time),
                confirm_time = COALESCE(:confirm_time, confirm_time),
                buyer_message = COALESCE(:buyer_message, buyer_message),
                item_id = COALESCE(:item_id, item_id),
                is_bargain = :is_bargain,
                is_rated = :is_rated,
                is_red_flower = :is_red_flower,
                updated_time = NOW()
            WHERE id = :id AND tenant_id = :tenant_id
        """), {**params, "id": existing.get("id")})
        order_db_id = _safe_int(existing.get("id"))
        action = "updated"
    else:
        insert_result = await db.execute(text("""
            INSERT INTO xianyu_trade_order(
                tenant_id, account_id, external_order_id, order_status, total_amount,
                buyer_name, buyer_id, create_time, pay_time, ship_time, confirm_time,
                buyer_message, item_id, is_bargain, is_rated, is_red_flower,
                deleted, created_time, updated_time
            ) VALUES (
                :tenant_id, :account_id, :external_order_id, :order_status, :total_amount,
                :buyer_name, :buyer_id, :create_time, :pay_time, :ship_time, :confirm_time,
                :buyer_message, :item_id, :is_bargain, :is_rated, :is_red_flower,
                0, NOW(), NOW()
            )
        """), params)
        order_db_id = _safe_int(getattr(insert_result, "lastrowid", 0))
        action = "inserted"
    if order_db_id:
        await _replace_remote_order_items(db, tenant_id, order_db_id, order.get("items") or [])
    return action


async def _run_sync_orders_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    config = _task_config(task)
    external_order_id = _text(config.get("externalOrderId") or "")
    account_ids = _extract_task_account_ids(task, config)
    # 兼容旧任务：未配置 accountIds 时回退到单账号字段
    if not account_ids:
        single_id = _safe_int(config.get("accountId") or task.get("account_id"))
        if single_id:
            account_ids = [single_id]
    if not account_ids:
        return {
            "ok": False,
            "errorCode": "ORDER_ACCOUNT_REQUIRED",
            "message": "请先选择要同步的账号",
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "taskType": task.get("task_type"),
        }

    # 多账号场景：循环同步并汇总结果
    if len(account_ids) == 1:
        return await _run_sync_orders_for_single_account(
            db, tenant_id, task, account_ids[0], external_order_id
        )

    aggregated = {
        "ok": True,
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "failed": 0,
        "taskType": task.get("task_type"),
        "details": [],
        "autoDeliveryTriggered": False,
    }
    for aid in account_ids:
        try:
            single = await _run_sync_orders_for_single_account(
                db, tenant_id, task, aid, external_order_id
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log_runtime_failure("sync_orders_scheduled_multi", exc)
            aggregated["ok"] = False
            aggregated["failed"] += 1
            aggregated["details"].append({"accountId": aid, "ok": False, "message": f"同步失败: {type(exc).__name__}"})
            continue
        aggregated["processed"] += _safe_int(single.get("processed"))
        aggregated["inserted"] += _safe_int(single.get("inserted"))
        aggregated["updated"] += _safe_int(single.get("updated"))
        aggregated["failed"] += _safe_int(single.get("failed"))
        if single.get("autoDeliveryTriggered"):
            aggregated["autoDeliveryTriggered"] = True
        aggregated["details"].append({"accountId": aid, "ok": bool(single.get("ok")), "summary": {
            "processed": single.get("processed"),
            "inserted": single.get("inserted"),
            "updated": single.get("updated"),
            "failed": single.get("failed"),
        }})
    aggregated["message"] = (
        f"同步订单任务执行完成：账号 {len(account_ids)} 个，"
        f"新增 {aggregated['inserted']} 个，更新 {aggregated['updated']} 个，失败 {aggregated['failed']} 个"
    )
    return aggregated


async def _run_sync_orders_for_single_account(
    db: AsyncSession,
    tenant_id: int,
    task: dict[str, Any],
    account_id: int,
    external_order_id: str,
) -> dict[str, Any]:
    """单账号订单同步 + 同步后立即触发自动发货（保持原 _run_sync_orders_task 行为）。"""
    result = await sync_sold_orders_for_account(db, tenant_id, account_id, external_order_id or None)
    result["taskType"] = task.get("task_type")

    # 订单同步后，如果新增了待发货订单，立即触发自动发货（不等待 auto_delivery 定时任务）。
    # 根因：闲鱼"已付款"通知不通过 WS 聊天消息推送，WS 实时路径无法触发；
    # 仅靠 auto_delivery 定时兜底会有 1-5 分钟延迟。同步后立即发货可将延迟降到几乎为 0。
    inserted = _safe_int(result.get("inserted"))
    if inserted > 0:
        try:
            delivery_result = await process_pending_deliveries(
                db, tenant_id, account_id=account_id, limit=20
            )
            result["autoDeliveryTriggered"] = True
            result["autoDeliveryResult"] = {
                "success": delivery_result.get("success", 0),
                "skipped": delivery_result.get("skipped", 0),
                "failed": delivery_result.get("failed", 0),
            }
            logger.info(
                "订单同步后立即触发自动发货 tenantId=%d accountId=%d inserted=%d deliverySuccess=%s deliverySkipped=%s deliveryFailed=%s",
                tenant_id, account_id, inserted,
                delivery_result.get("success", 0),
                delivery_result.get("skipped", 0),
                delivery_result.get("failed", 0),
            )
        except Exception as exc:
            _log_runtime_failure("sync_auto_delivery_after_orders", exc)
            result["autoDeliveryTriggered"] = False
            result["autoDeliveryError"] = f"自动发货失败: {type(exc).__name__}"

    return result


async def _run_sync_delivery_status_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    config = _task_config(task)
    account_id = _safe_int(config.get("accountId") or task.get("account_id"))
    external_order_id = _text(config.get("externalOrderId") or "")
    result = await sync_delivery_status_for_account(db, tenant_id, account_id, external_order_id or None)
    result["taskType"] = task.get("task_type")
    return result


def _extract_task_account_ids(task: dict[str, Any], config: dict[str, Any]) -> list[int]:
    """从 task.config_json.accountIds 提取多账号列表。

    新版多账号任务通过 configJson.accountIds 数组存储；旧版单账号字段保留为兼容字段。
    """
    raw = config.get("accountIds")
    if isinstance(raw, list):
        ids: list[int] = []
        seen: set[int] = set()
        for item in raw:
            value = _safe_int(item)
            if value > 0 and value not in seen:
                seen.add(value)
                ids.append(value)
        if ids:
            return ids
    # 兼容旧字段：accountId / account_id
    single = _safe_int(config.get("accountId") or task.get("account_id"))
    if single > 0:
        return [single]
    return []


async def _load_tenant_account_ids(db: AsyncSession, tenant_id: int) -> list[int]:
    """加载租户下所有启用状态的账号 ID（用于未指定账号的兜底场景，如默认自动补发任务）。"""
    rows = (await db.execute(text("""
        SELECT a.id
        FROM xianyu_account a
        LEFT JOIN xianyu_account_runtime r ON r.tenant_id = a.tenant_id AND r.account_id = a.id AND r.deleted = 0
        WHERE a.tenant_id = :tenant_id
          AND a.deleted = 0
          AND a.status = 1
        ORDER BY a.id ASC
    """), {"tenant_id": tenant_id})).mappings().all()
    return [_safe_int(row.get("id")) for row in rows if _safe_int(row.get("id")) > 0]


async def _run_sync_goods_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    """同步商品任务（多账号）：循环调用 sync_goods_for_account 拉取每个账号的最新商品列表。

    定时任务模式下不调用详情接口（async_fetch_detail=False），避免高频调用触发风控。
    """
    config = _task_config(task)
    account_ids = _extract_task_account_ids(task, config)
    if not account_ids:
        account_ids = await _load_tenant_account_ids(db, tenant_id)
    if not account_ids:
        return {
            "ok": False,
            "errorCode": "SYNC_GOODS_ACCOUNT_REQUIRED",
            "message": "同步商品任务缺少账号",
            "processed": 0,
            "taskType": task.get("task_type"),
        }

    from .xianyu_goods_sync import sync_goods_for_account

    success = 0
    failed = 0
    details: list[dict[str, Any]] = []
    for account_id in account_ids:
        try:
            cookie_str, cookie_err, _ = await _resolve_account_cookie(db, tenant_id, account_id, {})
            if cookie_err or not cookie_str:
                failed += 1
                details.append({"accountId": account_id, "ok": False, "message": cookie_err or "Cookie 不可用"})
                continue
            sync_id = f"sched_{tenant_id}_{account_id}_{int(time.time())}"
            result = await sync_goods_for_account(
                account_id=account_id,
                tenant_id=tenant_id,
                cookie_str=cookie_str,
                sync_id=sync_id,
                db_session_factory=None,
                async_fetch_detail=False,
            )
            success += 1
            details.append({
                "accountId": account_id,
                "ok": True,
                "total": _safe_int(result.get("total")),
                "new": _safe_int(result.get("new")),
                "updated": _safe_int(result.get("updated")),
                "offShelf": _safe_int(result.get("off_shelf")),
            })
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failed += 1
            _log_runtime_failure("sync_goods_scheduled", exc)
            details.append({"accountId": account_id, "ok": False, "message": f"同步失败: {type(exc).__name__}"})

    return {
        "ok": failed == 0,
        "errorCode": "" if failed == 0 else "SYNC_GOODS_PARTIAL",
        "message": f"同步商品任务执行完成：账号 {len(account_ids)} 个，成功 {success} 个，失败 {failed} 个",
        "processed": len(account_ids),
        "success": success,
        "failed": failed,
        "details": details,
        "taskType": task.get("task_type"),
    }


async def _run_auto_redelivery_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    """自动补发订单任务（间隔模式）：到达设定时间后，先同步订单，再筛选待发货订单批量补发。

    筛选条件（与 process_pending_deliveries 一致）：
    - order_status IN (1, 2)：已付款或待发货（已退款/退款关闭已映射为 5，自动排除）
    - 不存在 status=1 的 delivery_record：未发货或上次发货未成功
    - 命中 delivery_goods_config 或 delivery_rule：已配置货源库并开启自动发货

    若 accountIds 为空（默认 10 分钟任务），按租户整体处理：先同步所有账号订单，再批量补发。
    """
    config = _task_config(task)
    account_ids = _extract_task_account_ids(task, config)
    if not account_ids:
        account_ids = await _load_tenant_account_ids(db, tenant_id)

    # 1) 同步订单：确保新订单入库后才能被补发流程识别
    synced = 0
    sync_failed = 0
    for account_id in account_ids:
        try:
            await sync_sold_orders_for_account(db, tenant_id, account_id, None)
            synced += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            sync_failed += 1
            _log_runtime_failure("auto_redelivery_sync_orders", exc)

    # 2) 批量处理待发货订单：process_pending_deliveries 内部按订单维度筛选并执行
    try:
        delivery_result = await process_pending_deliveries(
            db, tenant_id=tenant_id, account_id=None, limit=100
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _log_runtime_failure("auto_redelivery_process", exc)
        return {
            "ok": False,
            "errorCode": "AUTO_REDELIVERY_PROCESS_FAILED",
            "message": f"自动补发任务处理失败：{type(exc).__name__}",
            "processed": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "syncSummary": {"synced": synced, "syncFailed": sync_failed},
            "taskType": task.get("task_type"),
        }

    return {
        "ok": bool(delivery_result.get("ok", True)),
        "message": (
            f"自动补发任务执行完成：同步账号 {synced} 个，"
            f"处理订单 {delivery_result.get('processed', 0)} 个，"
            f"成功 {delivery_result.get('success', 0)} 个，"
            f"跳过 {delivery_result.get('skipped', 0)} 个，"
            f"失败 {delivery_result.get('failed', 0)} 个"
        ),
        "processed": _safe_int(delivery_result.get("processed")),
        "success": _safe_int(delivery_result.get("success")),
        "skipped": _safe_int(delivery_result.get("skipped")),
        "failed": _safe_int(delivery_result.get("failed")),
        "syncSummary": {"synced": synced, "syncFailed": sync_failed},
        "taskType": task.get("task_type"),
    }


async def _run_one_click_polish_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    """一键擦亮商品任务（多账号）：循环调用 _submit_polish_task 为每个账号擦亮所有在售商品。"""
    config = _task_config(task)
    account_ids = _extract_task_account_ids(task, config)
    if not account_ids:
        return {
            "ok": False,
            "errorCode": "POLISH_TASK_ACCOUNT_REQUIRED",
            "message": "一键擦亮任务缺少账号",
            "processed": 0,
            "taskType": task.get("task_type"),
        }

    from app.api.v1.routes.items import _submit_polish_task

    success = 0
    failed = 0
    details: list[dict[str, Any]] = []
    for account_id in account_ids:
        try:
            response = await _submit_polish_task(
                db=db,
                account_id=account_id,
                tenant_id=tenant_id,
            )
            payload = response.data if isinstance(response.data, dict) else {}
            if response.code == 200:
                success += 1
                details.append({
                    "accountId": account_id,
                    "ok": True,
                    "taskId": payload.get("taskId"),
                    "total": payload.get("total"),
                    "message": payload.get("message") or response.msg,
                })
            else:
                failed += 1
                details.append({
                    "accountId": account_id,
                    "ok": False,
                    "message": response.msg or payload.get("message") or "擦亮任务提交失败",
                })
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failed += 1
            _log_runtime_failure("one_click_polish_scheduled", exc)
            details.append({"accountId": account_id, "ok": False, "message": f"擦亮失败: {type(exc).__name__}"})

    return {
        "ok": failed == 0,
        "errorCode": "" if failed == 0 else "POLISH_TASK_PARTIAL",
        "message": f"一键擦亮任务执行完成：账号 {len(account_ids)} 个，成功 {success} 个，失败 {failed} 个",
        "processed": len(account_ids),
        "success": success,
        "failed": failed,
        "details": details,
        "taskType": task.get("task_type"),
    }


async def _run_workflow_scheduled_task(db: AsyncSession, tenant_id: int, task: dict[str, Any]) -> dict[str, Any]:
    """工作流定时任务：通过 Java 内部接口触发工作流执行（无用户登录态依赖）。

    工作流任务不绑定具体账号（使用工作流自带账号），仅依赖 config.workflowId 选择已配置的工作流定义。
    """
    import httpx

    config = _task_config(task)
    workflow_id = _safe_int(config.get("workflowId") or config.get("workflow_id"))
    if not workflow_id:
        return {
            "ok": False,
            "errorCode": "WORKFLOW_ID_REQUIRED",
            "message": "工作流任务缺少工作流定义",
            "processed": 0,
            "taskType": task.get("task_type"),
        }

    base = (settings.core_api_base_url or "").rstrip("/")
    if not base:
        return {
            "ok": False,
            "errorCode": "WORKFLOW_TRIGGER_UNCONFIGURED",
            "message": "core-api 地址未配置",
            "processed": 0,
            "taskType": task.get("task_type"),
        }

    url = f"{base}/open-api/internal/workflow/definitions/{workflow_id}/trigger?tenantId={tenant_id}"
    headers = {"Content-Type": "application/json"}
    if settings.effective_internal_api_token:
        headers["X-Internal-Token"] = settings.effective_internal_api_token

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            resp = await client.post(url, json={}, headers=headers)
        if resp.status_code != 200:
            return {
                "ok": False,
                "errorCode": "WORKFLOW_TRIGGER_HTTP_ERROR",
                "message": f"触发工作流失败：HTTP {resp.status_code}",
                "processed": 0,
                "workflowId": workflow_id,
                "taskType": task.get("task_type"),
            }
        body = resp.json() if resp.text else {}
        if body.get("code") != 200:
            return {
                "ok": False,
                "errorCode": "WORKFLOW_TRIGGER_FAILED",
                "message": body.get("msg") or "触发工作流失败",
                "processed": 0,
                "workflowId": workflow_id,
                "taskType": task.get("task_type"),
            }
        data = body.get("data") or {}
        return {
            "ok": True,
            "message": "工作流已触发",
            "processed": 1,
            "executionId": data.get("executionId") or data.get("id"),
            "workflowId": workflow_id,
            "taskType": task.get("task_type"),
        }
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _log_runtime_failure("workflow_scheduled_trigger", exc)
        return {
            "ok": False,
            "errorCode": "WORKFLOW_TRIGGER_EXCEPTION",
            "message": f"触发工作流异常：{type(exc).__name__}",
            "processed": 0,
            "workflowId": workflow_id,
            "taskType": task.get("task_type"),
        }


async def sync_sold_orders_for_account(
    db: AsyncSession,
    tenant_id: int,
    account_id: Optional[int],
    external_order_id: Optional[str] = None,
) -> dict[str, Any]:
    if not account_id:
        return {
            "ok": False,
            "errorCode": "ORDER_ACCOUNT_REQUIRED",
            "message": "请先选择要同步的账号",
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "accountId": account_id,
            "externalOrderId": external_order_id,
        }

    account = await _load_order_sync_account(db, tenant_id, account_id)
    if not account:
        return {
            "ok": False,
            "errorCode": "ORDER_ACCOUNT_NOT_FOUND",
            "message": "账号不存在或已停用",
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "accountId": account_id,
            "externalOrderId": external_order_id,
        }

    remote_orders = await _fetch_remote_sold_orders(account_id)
    if external_order_id:
        remote_orders = [
            order for order in remote_orders
            if _text(order.get("externalOrderId") or "") == _text(external_order_id)
        ]

    inserted = 0
    updated = 0
    failed = 0
    sold_item_ids_to_relist: list[str] = []  # 新售订单对应的商品 ID，用于触发售整自动上架
    for order in remote_orders:
        try:
            result = await _upsert_remote_sold_order(db, tenant_id, account_id, order)
        except Exception as exc:
            failed += 1
            _log_runtime_failure("upsert_remote_sold_order", exc)
            continue
        if result == "inserted":
            inserted += 1
            # 新订单插入成功，记录商品 ID 用于触发售整自动上架钩子
            sold_item_id = _text(order.get("itemId") or "").strip()
            if sold_item_id:
                sold_item_ids_to_relist.append(sold_item_id)
        elif result == "updated":
            updated += 1

    # 售整自动上架钩子：新售订单触发后立即异步重发
    # 失败不影响订单同步主流程；relist_scheduler 也会每 3 分钟兜底扫描
    if sold_item_ids_to_relist:
        try:
            from .relist_service import relist_sold_item
            for sold_item_id in sold_item_ids_to_relist:
                # 异步触发，不等待结果（fire-and-forget）
                asyncio.create_task(
                    relist_sold_item(account_id, tenant_id, sold_item_id),
                    name=f"relist_hook_{account_id}_{sold_item_id}",
                )
        except Exception as exc:
            _log_runtime_failure("trigger_relist_hook", exc)

    # 同步退款订单：补充缺失的退款订单 + 更新已售订单的退款状态
    # （除非按 externalOrderId 单订单同步，此时不需要拉全部退款订单）
    refund_inserted = 0
    refund_updated = 0
    refund_failed = 0
    refund_processed = 0
    refund_error = False
    refund_order_nos: list[str] = []
    if not external_order_id:
        try:
            refund_orders = await _fetch_remote_refund_orders(account_id)
            refund_processed = len(refund_orders)
            for order in refund_orders:
                try:
                    result = await _upsert_remote_sold_order(db, tenant_id, account_id, order)
                except Exception as exc:
                    refund_failed += 1
                    _log_runtime_failure("upsert_remote_refund_order", exc)
                    continue
                if result == "inserted":
                    refund_inserted += 1
                elif result == "updated":
                    refund_updated += 1
                refund_no = _text(order.get("orderNo") or order.get("external_order_id") or "").strip()
                if refund_no:
                    refund_order_nos.append(refund_no)
        except Exception as exc:
            refund_error = True
            _log_runtime_failure("sync_remote_refund_orders", exc)

    await mark_account_synced(db, tenant_id, account_id)
    await db.commit()

    # 退款关单：同步到退款订单后，按账号配置调用外部注销接口（fire-and-forget）
    if refund_order_nos:
        try:
            from .refund_cancel_service import schedule_refund_unregister
            for refund_order_no in refund_order_nos:
                schedule_refund_unregister(tenant_id, account_id, refund_order_no)
        except Exception as exc:
            _log_runtime_failure("schedule_refund_unregister", exc)

    # 订单同步后自动补全缺失的商品记录，确保发货配置（delivery_goods_config）可命中。
    # 仅用订单中已有的商品信息（itemId/title/image/price）创建最小商品记录，不调用详情 API，避免风控。
    goods_backfilled = 0
    try:
        goods_backfilled = await _backfill_missing_goods_from_orders(
            db, tenant_id, account_id, remote_orders
        )
        if goods_backfilled > 0:
            await db.commit()
    except Exception as exc:
        await db.rollback()
        _log_runtime_failure("backfill_missing_goods_from_orders", exc)

    total_processed = len(remote_orders) + refund_processed
    total_inserted = inserted + refund_inserted
    total_updated = updated + refund_updated
    total_failed = failed + refund_failed
    message_parts = [f"订单同步完成，共处理 {total_processed} 条（已售 {len(remote_orders)} + 退款 {refund_processed}）"]
    if goods_backfilled > 0:
        message_parts.append(f"自动补全 {goods_backfilled} 个缺失商品")
    if refund_error:
        message_parts.append("退款订单暂未完成同步")
    return {
        "ok": total_failed == 0 and not refund_error,
        "errorCode": "" if total_failed == 0 and not refund_error else "ORDER_SYNC_PARTIAL",
        "message": "；".join(message_parts),
        "processed": total_processed,
        "inserted": total_inserted,
        "updated": total_updated,
        "failed": total_failed,
        "accountId": account_id,
        "externalOrderId": external_order_id,
        "refundProcessed": refund_processed,
        "refundInserted": refund_inserted,
        "refundUpdated": refund_updated,
        "goodsBackfilled": goods_backfilled,
        "refundFailed": refund_failed,
    }


async def sync_delivery_status_for_account(
    db: AsyncSession,
    tenant_id: int,
    account_id: Optional[int],
    external_order_id: Optional[str] = None,
) -> dict[str, Any]:
    params = {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "external_order_id": external_order_id or "",
    }
    await db.execute(text("""
        UPDATE delivery_record dr
        LEFT JOIN xianyu_trade_order o ON o.id = dr.order_id AND o.tenant_id = dr.tenant_id
        SET dr.delivery_status = CASE
                WHEN dr.delivery_status IS NOT NULL AND dr.delivery_status <> '' THEN dr.delivery_status
                WHEN o.order_status IN (3, 4) THEN 'success'
                WHEN o.order_status = 5 THEN 'failed'
                ELSE 'pending'
            END,
            dr.updated_time = NOW()
        WHERE dr.tenant_id = :tenant_id
          AND dr.deleted = 0
          AND (:account_id IS NULL OR dr.account_id = :account_id)
          AND (:external_order_id = '' OR o.external_order_id = :external_order_id)
    """), params)
    return {
        "ok": True,
        "message": "发货状态同步任务已执行",
        "processed": 1 if account_id is not None or external_order_id else 0,
        "accountId": account_id,
        "externalOrderId": external_order_id,
    }


async def mark_account_synced(db: AsyncSession, tenant_id: int, account_id: Optional[int]) -> dict[str, Any]:
    if account_id:
        await db.execute(text("""
            UPDATE xianyu_account_runtime
            SET last_sync_time = NOW(), updated_time = NOW()
            WHERE tenant_id = :tenant_id AND account_id = :account_id AND deleted = 0
        """), {"tenant_id": tenant_id, "account_id": account_id})
        return {"ok": True, "message": "账号同步时间已更新", "processed": 1}
    await db.execute(text("""
        UPDATE xianyu_account_runtime
        SET last_sync_time = NOW(), updated_time = NOW()
        WHERE tenant_id = :tenant_id AND deleted = 0
    """), {"tenant_id": tenant_id})
    return {"ok": True, "message": "租户账号同步时间已更新", "processed": 1}


async def process_pending_deliveries(
    db: AsyncSession,
    tenant_id: int,
    account_id: Optional[int] = None,
    limit: int = 20,
) -> dict[str, Any]:
    params: dict[str, Any] = {"tenant_id": tenant_id, "limit": min(max(limit, 1), 100)}
    account_sql = ""
    if account_id is not None:
        account_sql = " AND o.account_id = :account_id"
        params["account_id"] = account_id
    rows = (await db.execute(text(f"""
        SELECT o.*
        FROM xianyu_trade_order o
        WHERE o.tenant_id = :tenant_id
          AND o.deleted = 0
          AND o.order_status IN (1, 2)
          {account_sql}
          AND NOT EXISTS (
            SELECT 1 FROM delivery_record d
            WHERE d.tenant_id = o.tenant_id
              AND d.deleted = 0
              AND d.status IN (1, 2)
              AND (
                  d.order_id = o.id
                  OR d.order_id = o.external_order_id
              )
          )
        ORDER BY COALESCE(o.pay_time, o.created_time) ASC
        LIMIT :limit
    """), params)).mappings().all()

    success = 0
    failed = 0
    skipped = 0
    details = []
    for row in rows:
        result = await execute_delivery_for_order(db, dict(row))
        details.append(result)
        if result.get("ok"):
            success += 1
        elif result.get("errorCode") in ("DELIVERY_RULE_MISSING", "DELIVERY_RETRY_THROTTLED"):
            # 未匹配发货规则或重试节流中的订单不算发货失败，避免连续失败导致定时任务被禁用
            skipped += 1
        else:
            failed += 1
    await db.commit()
    return {
        "ok": failed == 0,
        "errorCode": "" if failed == 0 else "DELIVERY_BATCH_PARTIAL",
        "message": f"处理待发货订单 {len(rows)} 个，成功 {success} 个，跳过 {skipped} 个，失败 {failed} 个",
        "processed": len(rows),
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "details": details,
    }


async def _ensure_goods_placeholder_from_order_items(
    db: AsyncSession,
    tenant_id: int,
    external_goods_id: str,
) -> bool:
    """发货时发现商品不存在，从 xianyu_trade_order_item 表补全最小商品记录。

    场景：订单已入库（sync_sold_orders）但商品未同步（sync_goods_for_account），
    用户在前端配置发货规则时商品列表为空。此函数用订单项中的商品信息创建占位记录，
    让 delivery_goods_config 的 external_goods_id → xianyu_goods.id 映射能命中。
    """
    if not external_goods_id:
        return False

    # 从订单项表获取商品信息
    item_row = (await db.execute(text("""
        SELECT oi.goods_id, oi.goods_title, oi.goods_image, oi.goods_price,
               o.account_id
        FROM xianyu_trade_order_item oi
        JOIN xianyu_trade_order o ON o.id = oi.order_id AND o.tenant_id = oi.tenant_id
        WHERE oi.tenant_id = :tenant_id
          AND oi.deleted = 0
          AND oi.goods_id = :goods_id
        ORDER BY oi.id DESC LIMIT 1
    """), {"tenant_id": tenant_id, "goods_id": int(external_goods_id) if external_goods_id.isdigit() else 0})).mappings().first()

    if not item_row:
        return False

    account_id = item_row.get("account_id") or 0
    if not account_id:
        return False

    # 防御性查重：INSERT 前确认该商品在任意 deleted 状态下都不存在，
    # 避免对已被软删除（deleted=1）的商品创建 deleted=0 重复记录（幽灵商品根因之一）。
    existing_row = (await db.execute(text("""
        SELECT id FROM xianyu_goods
        WHERE tenant_id = :tenant_id AND account_id = :account_id
          AND external_goods_id = :external_goods_id
        LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "external_goods_id": external_goods_id,
    })).mappings().first()
    if existing_row:
        return False

    try:
        await db.execute(text("""
            INSERT INTO xianyu_goods (
                tenant_id, account_id, external_goods_id, goods_id, title,
                price, sold_price, cover_pic, image_url, status,
                deleted, created_time, updated_time
            ) VALUES (
                :tenant_id, :account_id, :external_goods_id, :goods_id, :title,
                :price, :price, :image_url, :image_url, 1,
                0, NOW(), NOW()
            )
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "external_goods_id": external_goods_id,
            "goods_id": external_goods_id,
            "title": (_text(item_row.get("goods_title")) or f"商品 {external_goods_id}")[:255],
            "price": (_text(item_row.get("goods_price")) or "0")[:32],
            "image_url": (_text(item_row.get("goods_image")) or None),
        })
        logger.info(
            "发货时自动补全商品占位记录 tenantId=%d accountId=%d externalGoodsId=%s",
            tenant_id, account_id, external_goods_id
        )
        return True
    except Exception:
        return False


async def _resolve_goods_level_rule(
    db: AsyncSession,
    tenant_id: int,
    external_goods_id: str,
) -> Optional[dict[str, Any]]:
    """查商品级自动发货配置（delivery_goods_config）。

    与实时路径 ws_delivery_handler._load_goods_delivery_rule 逻辑一致，
    确保定时批量路径也能命中商品详情页配置的自动发货规则。
    通过订单 item_id（闲鱼商品ID）映射到 xianyu_goods.id 再查配置。
    """
    if not external_goods_id:
        return None

    # 1. external_goods_id → xianyu_goods.id
    # 注意：查询不再过滤 deleted=0。
    # 若只查未删除记录，被软删除（deleted=1）的商品会被误判为"不存在"，
    # 进而调用 _ensure_goods_placeholder_from_order_items 创建 deleted=0 重复记录，
    # 导致幽灵商品反复出现（与 _backfill_missing_goods_from_orders 同类 bug）。
    # 修复后覆盖所有 deleted 状态：软删除商品若有 delivery_goods_config 仍可命中发货配置。
    goods_row = (await db.execute(text("""
        SELECT id FROM xianyu_goods
        WHERE tenant_id = :tenant_id AND external_goods_id = :xy_goods_id
        ORDER BY id DESC LIMIT 1
    """), {"tenant_id": tenant_id, "xy_goods_id": external_goods_id})).mappings().first()
    if not goods_row:
        # 商品不存在时，尝试从订单项表补全最小商品记录，确保发货配置可命中。
        # 场景：订单同步入库但商品尚未同步（如新上架商品被购买），用户已在前端配置发货规则。
        await _ensure_goods_placeholder_from_order_items(db, tenant_id, external_goods_id)
        goods_row = (await db.execute(text("""
            SELECT id FROM xianyu_goods
            WHERE tenant_id = :tenant_id AND external_goods_id = :xy_goods_id
            ORDER BY id DESC LIMIT 1
        """), {"tenant_id": tenant_id, "xy_goods_id": external_goods_id})).mappings().first()
        if not goods_row:
            return None
    internal_goods_id = goods_row.get("id")

    # 2. 查 delivery_goods_config
    cfg_row = (await db.execute(text("""
        SELECT id, goods_id, config_json FROM delivery_goods_config
        WHERE tenant_id = :tenant_id AND goods_id = :goods_id AND deleted = 0
        LIMIT 1
    """), {"tenant_id": tenant_id, "goods_id": internal_goods_id})).mappings().first()
    if not cfg_row:
        return None

    config_json = cfg_row.get("config_json")
    if isinstance(config_json, str):
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError:
            return None
    elif isinstance(config_json, dict):
        config = config_json
    else:
        return None

    timing_config = config.get("payDelivery")
    if not isinstance(timing_config, dict):
        return None

    if timing_config.get("enabled") in (0, "0", False, "false", "False", None):
        return None

    mode = str(timing_config.get("mode") or "text").lower()
    header = str(timing_config.get("header") or "")
    content = str(timing_config.get("content") or "")
    footer = str(timing_config.get("footer") or "")
    source_id = timing_config.get("sourceId")

    # 文本模式：尝试从货源库补全 content
    if mode == "text" and source_id:
        src = (await db.execute(text("""
            SELECT content FROM delivery_text_source
            WHERE tenant_id = :tenant_id AND id = :source_id AND deleted = 0
            LIMIT 1
        """), {"tenant_id": tenant_id, "source_id": source_id})).mappings().first()
        if src and not content:
            content = str(src.get("content") or "")

    if mode == "text" and not any([header.strip(), content.strip(), footer.strip()]):
        return None

    delivery_content = "\n".join(
        part for part in [header.strip(), content.strip(), footer.strip()] if part
    )

    return {
        "id": cfg_row.get("id"),
        "goods_id": internal_goods_id,
        "delivery_mode": mode,
        "delivery_content": delivery_content,
        "content": delivery_content,
        "card_group_id": timing_config.get("cardGroupId"),
        "auto_confirm_shipment": timing_config.get("autoConfirmShipment")
        or timing_config.get("auto_confirm_shipment")
        or 0,
        "confirm_before_send": timing_config.get("confirmBeforeSend")
        or timing_config.get("confirm_before_send")
        or 0,
        "closed_order_still_send": timing_config.get("closedOrderStillSend")
        or timing_config.get("closed_order_still_send")
        or 0,
    }


async def execute_delivery_for_order(db: AsyncSession, order: dict[str, Any]) -> dict[str, Any]:
    tenant_id = _safe_int(order.get("tenant_id"))
    account_id = order.get("account_id")
    order_id = _safe_int(order.get("id"))
    buyer_id = _text(order.get("buyer_id") or "")
    external_order_id = _text(order.get("external_order_id") or "")
    buyer_name = _text(order.get("buyer_name") or "买家")
    # 提取商品ID（闲鱼 external_goods_id），用于按商品精确匹配会话 s_id，
    # 避免发到该买家其他订单的旧会话（用户反馈过发货信息发错会话的问题）
    xy_goods_id = _text(order.get("item_id") or "")

    existing_delivery = (await db.execute(text("""
        SELECT id, card_item_id FROM delivery_record
        WHERE tenant_id = :tenant_id AND deleted = 0
          AND status IN (1, 2)
          AND (order_id = :order_id
               OR (:external_order_id <> '' AND order_id = :external_order_id))
        ORDER BY id DESC LIMIT 1
    """), {"tenant_id": tenant_id, "order_id": order_id, "external_order_id": external_order_id})).mappings().first()
    if existing_delivery:
        return {"ok": True, "orderId": order_id, "deliveryRecordId": existing_delivery.get("id"), "cardItemId": existing_delivery.get("card_item_id"), "message": "订单已发货，跳过重复处理"}

    # === 交叉维度去重：按 买家ID + 商品ID 检查实时路径是否已发货 ===
    # 背景：实时路径（ws_delivery_handler）在付款消息 reminder_url 不含 orderId 时，
    # delivery_record.order_id 为 NULL，上面的 order_id 维度检查无法命中。
    # 此时通过 receiver_info 中的 buyerUserId + xyGoodsId 交叉匹配，防止批量路径重复发货。
    # 归一化 @goofish 后缀，与实时路径 _has_existing_realtime_delivery 保持一致。
    if buyer_id and xy_goods_id:
        cross_existing = (await db.execute(text("""
            SELECT id FROM delivery_record
            WHERE tenant_id = :tenant_id AND account_id = :account_id AND deleted = 0
              AND status IN (1, 2)
              AND delivery_timing = 'after_payment'
              AND REPLACE(JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.buyerUserId')), '@goofish', '') = REPLACE(:buyer_id, '@goofish', '')
              AND JSON_UNQUOTE(JSON_EXTRACT(receiver_info, '$.xyGoodsId')) = :xy_goods_id
            ORDER BY id DESC LIMIT 1
        """), {
            "tenant_id": tenant_id, "account_id": account_id,
            "buyer_id": buyer_id, "xy_goods_id": xy_goods_id,
        })).mappings().first()
        if cross_existing:
            logger.info(
                "批量路径交叉去重命中：订单 %s 买家 %s 商品 %s 已被实时路径发货，跳过（deliveryRecordId=%s）",
                order_id, buyer_id, xy_goods_id, cross_existing.get("id"),
            )
            return {"ok": True, "orderId": order_id, "deliveryRecordId": cross_existing.get("id"), "message": "订单已被实时路径发货，跳过重复处理"}

    # === 重试节流：检查最近一条失败记录的时间，避免每分钟都重试 ===
    # 距离上次失败不足 RETRY_INTERVAL_SECONDS 秒的订单跳过重试，等待下一周期
    RETRY_INTERVAL_SECONDS = 120  # 失败后至少等 2 分钟再重试
    last_fail = (await db.execute(text("""
        SELECT id, status, fail_reason, retry_count,
               TIMESTAMPDIFF(SECOND, updated_time, NOW()) AS secs_since_update
        FROM delivery_record
        WHERE tenant_id = :tenant_id AND order_id = :order_id AND deleted = 0 AND status IN (0, 3)
        ORDER BY id DESC LIMIT 1
    """), {"tenant_id": tenant_id, "order_id": order_id})).mappings().first()
    if last_fail:
        secs = _safe_int(last_fail.get("secs_since_update"))
        retry_count = _safe_int(last_fail.get("retry_count"))
        if secs < RETRY_INTERVAL_SECONDS and retry_count >= 3:
            # 重试次数已达上限且未到重试间隔，跳过
            return {"ok": False, "errorCode": "DELIVERY_RETRY_THROTTLED", "orderId": order_id,
                    "message": f"发货重试节流：距上次失败 {secs}s，重试 {retry_count} 次，等待 {RETRY_INTERVAL_SECONDS}s 后重试"}

    # 优先查商品级自动发货配置（delivery_goods_config），与实时路径 ws_delivery_handler 保持一致。
    # 订单的 item_id 是闲鱼商品ID（external_goods_id），需先映射到 xianyu_goods.id 再查配置。
    rule = await _resolve_goods_level_rule(db, tenant_id, _text(order.get("item_id") or ""))

    # 商品级配置未命中时，回退到账号级/通用规则（delivery_rule）
    if not rule:
        rule = (await db.execute(text("""
            SELECT * FROM delivery_rule
            WHERE tenant_id = :tenant_id
              AND deleted = 0
              AND status = 1
              AND (account_id IS NULL OR account_id = :account_id)
              AND (goods_id IS NULL OR goods_id = 0)
            ORDER BY CASE WHEN account_id = :account_id THEN 0 ELSE 1 END, id DESC
            LIMIT 1
        """), {"tenant_id": tenant_id, "account_id": account_id})).mappings().first()

    if not rule:
        await _insert_delivery_record(db, tenant_id, account_id, order_id, None, "none", None, 0, "未配置自动发货规则")
        return {"ok": False, "errorCode": "DELIVERY_RULE_MISSING", "orderId": order_id, "message": "该订单未匹配自动发货规则"}

    rule = dict(rule)
    # 使用 delivery_mode 作为主字段，兼容旧 delivery_type
    delivery_mode = (_text(rule.get("delivery_mode") or rule.get("delivery_type") or "card")).lower()
    delivery_content = _text(rule.get("delivery_content") or rule.get("content") or "")
    card_item_id = None
    content = ""          # 实际发送的内容
    send_ok = False       # WS 发送是否成功

    if delivery_mode in {"card", "kami", "auto_kami"}:
        preferred_group_id = rule.get("card_group_id")
        # MySQL 支持 UPDATE ... ORDER BY ... LIMIT 1；状态条件写在 UPDATE 中，确保原子认领。
        update_result = await db.execute(text("""
            UPDATE card_item
            SET status = 1, used_order_id = :order_id, used_time = NOW(), updated_time = NOW()
            WHERE tenant_id = :tenant_id
              AND deleted = 0
              AND COALESCE(status, 0) = 0
              AND (:group_id IS NULL OR group_id = :group_id)
            ORDER BY id ASC
            LIMIT 1
        """), {"tenant_id": tenant_id, "group_id": preferred_group_id, "order_id": order_id})
        if (update_result.rowcount or 0) <= 0:
            await _insert_delivery_record(db, tenant_id, account_id, order_id, rule.get("id"), delivery_mode, None, 0, "卡密库存不足")
            await insert_notification(db, tenant_id, None, "自动发货失败", f"订单 {external_order_id or order_id} 卡密库存不足", "auto_delivery", "warning")
            return {"ok": False, "errorCode": "DELIVERY_CARD_STOCK_EMPTY", "orderId": order_id, "ruleId": rule.get("id"), "message": "卡密库存不足，请补充后重试"}

        card = (await db.execute(text("""
            SELECT * FROM card_item
            WHERE tenant_id = :tenant_id AND used_order_id = :order_id AND deleted = 0
            ORDER BY used_time DESC, id DESC LIMIT 1
        """), {"tenant_id": tenant_id, "order_id": order_id})).mappings().first()
        if not card:
            await _insert_delivery_record(db, tenant_id, account_id, order_id, rule.get("id"), delivery_mode, None, 0, "卡密认领后读取失败")
            return {"ok": False, "errorCode": "DELIVERY_CARD_READ_FAILED", "orderId": order_id, "ruleId": rule.get("id"), "message": "卡密读取失败，请稍后重试"}
        card = dict(card)
        card_item_id = card.get("id")
        content = _text(card.get("card_content") or card.get("card_key") or card.get("card_value"))

        # 通过 WebSocket 将卡密内容发送给买家
        send_ok = await _send_delivery_message_via_ws(db, tenant_id, account_id, buyer_id, content, xy_goods_id)

        if send_ok:
            # 发送成功 → 标记为已使用（status=2）
            await db.execute(text("""
                UPDATE card_item SET status = 2, updated_time = NOW()
                WHERE id = :id AND tenant_id = :tenant_id
            """), {"id": card_item_id, "tenant_id": tenant_id})
        else:
            # 发送失败 → 回滚卡密状态（status=0, 清除订单关联）
            await db.execute(text("""
                UPDATE card_item SET status = 0, used_order_id = NULL, used_time = NULL, updated_time = NOW()
                WHERE id = :id AND tenant_id = :tenant_id
            """), {"id": card_item_id, "tenant_id": tenant_id})

        # 更新卡密组计数
        await db.execute(text("""
            UPDATE card_group g SET
              total_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0),
              used_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 2),
              remain_count = (SELECT COUNT(*) FROM card_item i WHERE i.group_id = g.id AND i.tenant_id = g.tenant_id AND i.deleted = 0 AND i.status = 0),
              updated_time = NOW()
            WHERE g.id = :group_id AND g.tenant_id = :tenant_id
        """), {"group_id": card.get("group_id"), "tenant_id": tenant_id})

    elif delivery_mode == "text":
        # 文本模式：变量替换后通过 WS 发送
        content = delivery_content
        content = content.replace("{buyerUserName}", buyer_name)
        content = content.replace("{buyerName}", buyer_name)
        content = content.replace("{orderId}", external_order_id)
        content = content.replace("{goodsTitle}", "")
        content = content.replace("{deliveryTime}", time.strftime("%Y-%m-%d %H:%M:%S"))
        send_ok = await _send_delivery_message_via_ws(db, tenant_id, account_id, buyer_id, content, xy_goods_id)

    else:
        # 未知模式，尝试作为文本发送
        content = delivery_content
        send_ok = await _send_delivery_message_via_ws(db, tenant_id, account_id, buyer_id, content, xy_goods_id)

    # ---- 记录发货结果 ----
    record_status = 1 if send_ok else 0
    fail_reason = None
    if not send_ok:
        if delivery_mode in {"card", "kami", "auto_kami"}:
            fail_reason = "卡密已回滚：WS发送失败"
        else:
            fail_reason = "WS发送失败"

    await _insert_delivery_record(db, tenant_id, account_id, order_id, rule.get("id"), delivery_mode, content, record_status, fail_reason, card_item_id)

    if send_ok:
        # 先调用闲鱼确认发货 API，只有平台真正标记为已发货后才更新本地 order_status=3
        # 避免本地标记 3 但闲鱼平台实际未发货的状态不一致问题
        # 小刀订单走免拼发货接口（freeshipping），普通订单走虚拟发货接口（consign.dummy）
        confirm_success = False
        confirm_error_msg = "确认发货能力不可用"
        try:
            from .xianyu_api_service import confirm_order_shipment
            is_bargain = _safe_int(order.get("is_bargain")) == 1
            confirm_result = await asyncio.to_thread(
                confirm_order_shipment,
                account_id,
                external_order_id,
                is_bargain=is_bargain,
                item_id=xy_goods_id,
                buyer_id=buyer_id,
            )
            if confirm_result and confirm_result.get("success"):
                confirm_success = True
                ship_method = confirm_result.get("ship_method", "freeshipping" if is_bargain else "consign")
                logger.info(
                    "确认发货成功: accountId=%d orderId=%s isBargain=%s method=%s",
                    account_id, external_order_id, is_bargain, ship_method,
                )
            else:
                confirm_error_msg = (confirm_result.get("message") if confirm_result else "确认发货失败") or "确认发货失败"
                logger.warning(
                    "runtimeFailure operation=confirm_delivery errorType=ProviderRejected requestId=%s msg=%s",
                    get_request_id() or "-", confirm_error_msg,
                )
        except Exception as e:
            confirm_error_msg = f"确认发货异常: {type(e).__name__}"
            _log_runtime_failure("confirm_delivery", e)

        if confirm_success:
            # 确认发货成功，更新订单状态为已发货
            await db.execute(text("""
                UPDATE xianyu_trade_order
                SET order_status = 3, ship_time = NOW(), updated_time = NOW()
                WHERE id = :order_id AND tenant_id = :tenant_id
            """), {"order_id": order_id, "tenant_id": tenant_id})

            await insert_notification(db, tenant_id, None, "自动发货成功",
                                      f"订单 {external_order_id or order_id} 已通过WS发送发货内容",
                                      "auto_delivery", "info")
            try:
                from .notify_dispatcher import notify_auto_delivery
                await notify_auto_delivery(tenant_id, account_id, True, external_order_id or order_id, "已通过WS发送发货内容")
            except Exception as exc:
                _log_runtime_failure("notify_delivery_success", exc)
            return {"ok": True, "orderId": order_id, "ruleId": rule.get("id"), "cardItemId": card_item_id, "message": "已通过WS发送发货内容"}
        else:
            # 确认发货失败：发货消息已发送，但闲鱼平台未标记为已发货
            # 保持本地 order_status 不变（仍为待发货），等待下次同步或重试
            await insert_notification(db, tenant_id, None, "自动发货确认失败",
                                      f"订单 {external_order_id or order_id} 发货消息已发送，但确认发货失败：{confirm_error_msg}",
                                      "auto_delivery", "warning")
            try:
                from .notify_dispatcher import notify_auto_delivery
                await notify_auto_delivery(tenant_id, account_id, False, external_order_id or order_id, f"发货消息已发送，但确认发货失败：{confirm_error_msg}")
            except Exception as exc:
                _log_runtime_failure("notify_delivery_failure", exc)
            return {"ok": False, "errorCode": "CONFIRM_SHIPMENT_FAILED", "orderId": order_id, "ruleId": rule.get("id"), "cardItemId": card_item_id, "message": f"发货消息已发送，但确认发货失败：{confirm_error_msg}"}
    else:
        await insert_notification(db, tenant_id, None, "自动发货WS发送失败",
                                  f"订单 {external_order_id or order_id} {fail_reason or 'WS发送失败'}",
                                  "auto_delivery", "warning")
        try:
            from .notify_dispatcher import notify_auto_delivery
            await notify_auto_delivery(tenant_id, account_id, False, external_order_id or order_id, fail_reason or "WS发送失败")
        except Exception as exc:
            _log_runtime_failure("notify_delivery_failure", exc)
        return {"ok": False, "errorCode": "DELIVERY_SEND_FAILED", "orderId": order_id, "ruleId": rule.get("id"), "cardItemId": card_item_id, "message": "发货消息发送失败，请稍后重试"}


async def _insert_delivery_record(
    db: AsyncSession,
    tenant_id: int,
    account_id: Optional[int],
    order_id: int,
    rule_id: Optional[int],
    delivery_type: str,
    content: Optional[str],
    status: int,
    fail_reason: Optional[str],
    card_item_id: Optional[int] = None,
) -> None:
    delivery_status = "success" if status == 1 else "failed"

    # 重试时复用已有失败记录：避免 delivery_record 表无限膨胀
    # 查找该订单最近一条失败记录（status=0 或 3），若存在则更新而非插入新记录
    existing = (await db.execute(text("""
        SELECT id, retry_count FROM delivery_record
        WHERE tenant_id = :tenant_id AND order_id = :order_id AND deleted = 0
          AND status IN (0, 3)
        ORDER BY id DESC LIMIT 1
    """), {"tenant_id": tenant_id, "order_id": order_id})).mappings().first()

    if existing:
        # 更新已有失败记录：递增 retry_count，更新状态和内容
        new_retry = _safe_int(existing.get("retry_count")) + 1
        await db.execute(text("""
            UPDATE delivery_record
            SET account_id = :account_id, rule_id = :rule_id, delivery_type = :delivery_type,
                content = :content, status = :status, fail_reason = :fail_reason,
                delivery_status = :delivery_status, error_message = :error_message,
                delivery_time = IF(:status = 1, NOW(), NULL),
                card_item_id = :card_item_id, updated_time = NOW(),
                retry_count = :retry_count
            WHERE id = :id AND tenant_id = :tenant_id
        """), {
            "id": existing.get("id"),
            "tenant_id": tenant_id,
            "account_id": account_id,
            "rule_id": rule_id,
            "delivery_type": delivery_type,
            "content": content,
            "status": status,
            "fail_reason": fail_reason,
            "delivery_status": delivery_status,
            "error_message": fail_reason,
            "card_item_id": card_item_id,
            "retry_count": new_retry,
        })
        return

    # 无已有失败记录，插入新记录
    await db.execute(text("""
        INSERT INTO delivery_record(
            tenant_id, account_id, order_id, rule_id, delivery_type, content,
            status, retry_count, fail_reason, delivery_status, error_message,
            delivery_time, card_item_id, deleted, created_time, updated_time
        ) VALUES(
            :tenant_id, :account_id, :order_id, :rule_id, :delivery_type, :content,
            :status, 0, :fail_reason, :delivery_status, :error_message,
            IF(:status = 1, NOW(), NULL), :card_item_id, 0, NOW(), NOW()
        )
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "order_id": order_id,
        "rule_id": rule_id,
        "delivery_type": delivery_type,
        "content": content,
        "status": status,
        "fail_reason": fail_reason,
        "delivery_status": delivery_status,
        "error_message": fail_reason,
        "card_item_id": card_item_id,
    })


async def _send_delivery_message_via_ws(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    buyer_id: str,
    content: str,
    xy_goods_id: Optional[str] = None,
) -> bool:
    """通过 WebSocket 发送发货消息给买家。

    从 xianyu_chat_message 表中查找会话 s_id，然后通过 WebSocket 发送。
    如果 WS 未连接或找不到会话，静默失败（不走异常，只返回 False）。

    会话查找策略（严格按商品维度匹配，避免发到该买家的其他订单旧会话）：
    1. 优先按 buyer_id + xy_goods_id 精确匹配（同一买家在同一商品上的会话）
    2. 若 xy_goods_id 缺失或未命中，回退到仅按 buyer_id 匹配最新会话

    Returns:
        True 表示发送成功
    """
    if not buyer_id or not content:
        return False

    buyer_id_with_suffix = f"{buyer_id}@goofish" if not buyer_id.endswith("@goofish") else buyer_id
    buyer_id_no_suffix = buyer_id.split("@", 1)[0] if "@" in buyer_id else buyer_id

    # 优先按 buyer_id + xy_goods_id 精确匹配（防止发到该买家的其他订单会话）
    row = None
    match_strategy = ""
    if xy_goods_id:
        row = (await db.execute(
            text("""
                SELECT s_id, sender_user_id, xy_goods_id FROM xianyu_chat_message
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND (sender_user_id = :buyer_id
                       OR sender_user_id = :buyer_id_with_suffix
                       OR sender_user_id = :buyer_id_no_suffix)
                  AND xy_goods_id = :xy_goods_id
                  AND s_id IS NOT NULL AND s_id != ''
                  AND deleted = 0
                ORDER BY id DESC
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "buyer_id": buyer_id,
                "buyer_id_with_suffix": buyer_id_with_suffix,
                "buyer_id_no_suffix": buyer_id_no_suffix,
                "xy_goods_id": xy_goods_id,
            }
        )).mappings().first()
        match_strategy = "buyer+goods"

    # 回退：仅按 buyer_id 匹配最新会话
    if not row:
        row = (await db.execute(
            text("""
                SELECT s_id, sender_user_id, xy_goods_id FROM xianyu_chat_message
                WHERE tenant_id = :tenant_id
                  AND account_id = :account_id
                  AND (sender_user_id = :buyer_id
                       OR sender_user_id = :buyer_id_with_suffix
                       OR sender_user_id = :buyer_id_no_suffix)
                  AND s_id IS NOT NULL AND s_id != ''
                  AND deleted = 0
                ORDER BY id DESC
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "buyer_id": buyer_id,
                "buyer_id_with_suffix": buyer_id_with_suffix,
                "buyer_id_no_suffix": buyer_id_no_suffix,
            }
        )).mappings().first()
        match_strategy = "buyer-only"

    if not row:
        logger.warning(
            "未找到会话 s_id: accountId=%d buyerId=%s xyGoodsId=%s",
            account_id, buyer_id, xy_goods_id or "-",
        )
        return False

    s_id = str(row["s_id"])
    sender_user_id = str(row["sender_user_id"] or "")
    msg_xy_goods_id = str(row.get("xy_goods_id") or "")

    # 安全检查：若指定了 xy_goods_id 但回退到 buyer-only 匹配的会话，
    # 该会话的 xy_goods_id 与当前订单商品不一致 → 视为发到错误会话，拒绝发送。
    # 这样可以避免把发货内容发到买家历史任意订单的旧会话（用户反馈过该问题）。
    if xy_goods_id and match_strategy == "buyer-only" and msg_xy_goods_id and msg_xy_goods_id != xy_goods_id:
        logger.warning(
            "拒绝发送到错误会话: accountId=%d buyerId=%s orderGoodsId=%s sessionGoodsId=%s "
            "(定时路径找不到当前商品的会话，需等待WS实时消息入库后再发送)",
            account_id, buyer_id, xy_goods_id, msg_xy_goods_id,
        )
        return False

    logger.info(
        "发货会话匹配: accountId=%d buyerId=%s xyGoodsId=%s strategy=%s sId=%s",
        account_id, buyer_id, xy_goods_id or "-", match_strategy, s_id,
    )

    # 获取 WebSocket 客户端
    try:
        from .ws_client import ws_manager
    except ImportError:
        logger.error("无法导入 ws_manager")
        return False

    client = ws_manager.get_client(account_id)
    if not client or not client.is_connected:
        logger.warning("WebSocket 未连接，无法发送发货消息: accountId=%d", account_id)
        return False

    # 构造会话 ID 和接收者 ID
    cid = s_id if s_id.endswith("@goofish") else f"{s_id}@goofish"
    to_id = sender_user_id if sender_user_id.endswith("@goofish") else f"{sender_user_id}@goofish"

    logger.info(
        "发送发货消息: accountId=%d cid=%s to_id=%s contentLen=%d",
        account_id, cid, to_id, len(content)
    )

    try:
        result = await client.send_text_message(cid=cid, to_id=to_id, text=content)
        code = result.get("code", 500)
        if code == 200:
            logger.info("发货消息发送成功: accountId=%d", account_id)
            return True
        else:
            logger.warning(
                "runtimeFailure operation=send_delivery_message errorType=ProviderRejected requestId=%s",
                get_request_id() or "-",
            )
            return False
    except Exception as e:
        _log_runtime_failure("send_delivery_message", e)
        return False


async def process_incoming_message(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id = _safe_int(payload.get("tenantId") or payload.get("tenant_id"), 1)
    account_id = _safe_int(payload.get("accountId") or payload.get("account_id"))
    if not account_id:
        return {"ok": False, "errorCode": "AUTO_REPLY_INVALID_REQUEST", "message": "自动回复请求缺少账号信息"}

    if not await _is_account_active_for_auto_reply(db, tenant_id, account_id):
        logger.info(
            "[AUTO_REPLY] 跳过已删除/停用账号 tenantId=%d accountId=%d",
            tenant_id,
            account_id,
        )
        return {
            "ok": True,
            "matched": False,
            "autoSent": False,
            "message": "账号已删除或停用，跳过自动回复",
        }

    # 提前解析 seller_uid，用于自问自答防护（必须在 buyer_id 解析之前）
    seller_uid = _text(
        payload.get("sellerExternalUid")
        or payload.get("ownerUserId")
        or payload.get("sellerUserId")
        or payload.get("accountExternalUid")
    )

    # === 自问自答防护（强制闸门）===
    # 显式校验 payload 的原始 senderUserId（即 buyerId 字段）是否等于卖家自己。
    # 即使 IM 回环消息 direction 被误判为 IN、_resolve_effective_buyer_id_from_sid
    # 从历史消息反查出买家 ID，这里也能直接拦截，避免自问自答。
    # 注意：该检查必须在 _resolve_effective_buyer_id_from_sid 之前，因为后者
    # 会跳过等于卖家的候选，导致原始 sender 信息丢失。
    raw_sender_uid = _text(payload.get("buyerId") or payload.get("senderUserId"))
    if raw_sender_uid and seller_uid:
        if _normalize_external_uid(raw_sender_uid) == _normalize_external_uid(seller_uid):
            logger.info(
                "[AUTO_REPLY] 跳过自动回复（原始 senderUserId 命中卖家自己）tenantId=%d accountId=%d sId=%s senderUserId=%s",
                tenant_id, account_id, _text(payload.get("sId") or payload.get("sid")), raw_sender_uid
            )
            return {"ok": True, "matched": False, "message": "senderUserId 指向卖家自己，跳过自动回复（防止自问自答）"}

    buyer_id = (await _resolve_effective_buyer_id_from_sid(db, tenant_id, account_id, payload)).strip() or "unknown"
    buyer_name = _text(payload.get("buyerName") or payload.get("buyer_name") or buyer_id)
    content = _text(payload.get("content"))
    if not content:
        return {"ok": False, "errorCode": "AUTO_REPLY_INVALID_REQUEST", "message": "自动回复请求缺少消息内容"}
    # 防御：buyer_id 为空/unknown 时无法通过 WS 发送回复，提前拦截避免无效的 AI 调用与发送超时
    # 系统消息（如 PIC_DEAL_ERROR 业务通知）senderUserId 为空，会进入此分支被跳过
    if not buyer_id or buyer_id == "unknown":
        logger.info(
            "[AUTO_REPLY] 跳过自动回复（buyer_id 为空/unknown）tenantId=%d accountId=%d sId=%s contentLen=%d",
            tenant_id, account_id, _text(payload.get("sId") or payload.get("sid")), len(content)
        )
        return {"ok": True, "matched": False, "message": "buyer_id 为空，跳过自动回复（系统消息）"}

    message_type = _text(payload.get("messageType") or payload.get("message_type") or "text").lower()
    if message_type not in {"text", "system", "image", "card"}:
        message_type = "text"

    conversation_id = _text(payload.get("conversationId") or payload.get("conversation_id") or payload.get("sessionId") or payload.get("session_id") or buyer_id)
    if not conversation_id:
        conversation_id = buyer_id or "unknown"

    # 闲鱼会话 ID（sId，格式 xxx@goofish），用于通过 WebSocket 发送回复
    ws_sid = _text(payload.get("sId") or payload.get("sid"))

    platform_message_id = _text(payload.get("platformMessageId") or payload.get("pnmId") or payload.get("pnm_id"))
    goods_id = _text(payload.get("goodsId") or payload.get("itemId") or payload.get("xyGoodsId"))
    item_title = _text(payload.get("itemTitle") or payload.get("cardTitle"))
    if seller_uid and _normalize_external_uid(buyer_id) == _normalize_external_uid(seller_uid):
        logger.info(
            "[AUTO_REPLY] 跳过自动回复（buyer_id 命中卖家自己）tenantId=%d accountId=%d sId=%s buyerId=%s",
            tenant_id, account_id, ws_sid, buyer_id
        )
        return {"ok": True, "matched": False, "message": "buyer_id 指向卖家自己，跳过自动回复"}

    account_chat_role = await _resolve_account_chat_role(db, tenant_id, account_id, payload)
    if account_chat_role == "buyer":
        logger.info(
            "[AUTO_REPLY] 跳过自动回复（当前账号处于买家角色）tenantId=%d accountId=%d sId=%s buyerId=%s",
            tenant_id,
            account_id,
            ws_sid,
            buyer_id,
        )
        return {
            "ok": True,
            "matched": False,
            "autoSent": False,
            "message": "当前账号处于买家角色，跳过自动回复",
        }

    runtime = (await db.execute(text("""
        SELECT id FROM xianyu_account_runtime
        WHERE tenant_id = :tenant_id AND account_id = :account_id AND deleted = 0
        LIMIT 1
    """), {"tenant_id": tenant_id, "account_id": account_id})).first()
    if not runtime:
        await db.execute(text("""
            INSERT INTO xianyu_account_runtime(tenant_id, account_id, ws_status, last_heartbeat_time, last_sync_time, deleted, created_time, updated_time)
            VALUES(:tenant_id, :account_id, 1, NOW(), NOW(), 0, NOW(), NOW())
        """), {"tenant_id": tenant_id, "account_id": account_id})

    conv_row = (await db.execute(text("""
        SELECT id FROM xianyu_conversation
        WHERE tenant_id = :tenant_id AND account_id = :account_id AND deleted = 0
          AND external_buyer_id = :buyer_id
        ORDER BY id DESC LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "buyer_id": buyer_id,
    })).mappings().first()

    if conv_row:
        conversation_db_id = int(conv_row["id"])
        await db.execute(text("""
            UPDATE xianyu_conversation
            SET buyer_name = :buyer_name,
                goods_id = CASE WHEN :goods_id <> '' THEN :goods_id ELSE goods_id END,
                goods_title = CASE WHEN :item_title <> '' THEN :item_title ELSE goods_title END,
                last_message_content = :content,
                last_message_time = NOW(),
                updated_time = NOW()
            WHERE id = :conversation_id
        """), {
            "conversation_id": conversation_db_id,
            "buyer_name": buyer_name,
            "goods_id": goods_id,
            "item_title": item_title,
            "content": content,
        })
    else:
        # peer_key 与 external_buyer_id 保持一致（buyer_id 已通过
        # _resolve_effective_buyer_id_from_sid 解析为真实 external_uid 或 'unknown'），
        # 避免新会话 peer_key 为 NULL 导致后续头像/封面图持久化失败。
        await db.execute(text("""
            INSERT INTO xianyu_conversation(
                tenant_id, account_id, peer_key, external_buyer_id, buyer_name, goods_id, goods_title,
                last_message_content, last_message_time, deleted, created_time, updated_time
            ) VALUES(
                :tenant_id, :account_id, :peer_key, :buyer_id, :buyer_name, :goods_id, :item_title,
                :content, NOW(), 0, NOW(), NOW()
            )
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "peer_key": buyer_id,
            "buyer_id": buyer_id,
            "buyer_name": buyer_name,
            # goods_id 是 bigint 列，空字符串会导致 DataError，需转为 NULL
            "goods_id": goods_id or None,
            "item_title": item_title,
            "content": content,
        })
        conversation_db_id = int((await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar() or 0)

    # === 会话级自动回复状态检查（人工干预自动暂停/恢复） ===
    # 业务规则：
    #   1. 检测到人工发送消息（OUT 且 is_auto_reply=0）后，会话自动暂停 AI 回复
    #   2. 买家发送"开启自动回复"指令 → 自动恢复（仅当未被用户手动关闭）
    #   3. 距上次人工回复 > 暂停时长（默认 60 秒，可配置），买家发新消息时自动恢复
    #   4. 用户在网站手动点击按钮关闭时，禁止自动恢复，仅允许用户手动开启
    #   5. 此检查在 AI 规则匹配之前生效，会话暂停时直接跳过 AI 回复
    # 暂停时长从 ai-customer-service 配置的 pauseDurationSeconds 读取（默认 60 秒）
    pause_duration_seconds = await _resolve_ai_cs_pause_duration_seconds(db, tenant_id, account_id)
    pause_duration_ms = pause_duration_seconds * 1000
    conv_state_row = (await db.execute(text("""
        SELECT auto_reply_paused, auto_reply_manual_disabled, last_manual_reply_at
        FROM xianyu_conversation
        WHERE id = :conversation_id
    """), {"conversation_id": conversation_db_id})).mappings().first()
    conv_paused = int((conv_state_row or {}).get("auto_reply_paused") or 0)
    conv_manual_disabled = int((conv_state_row or {}).get("auto_reply_manual_disabled") or 0)
    conv_last_manual_at = (conv_state_row or {}).get("last_manual_reply_at")

    # 指令检测：买家发送"开启自动回复"（精确匹配，避免误触发）
    RESUME_COMMAND = "开启自动回复"
    is_resume_command = content.strip() == RESUME_COMMAND

    if is_resume_command and conv_paused == 1:
        if conv_manual_disabled == 0:
            # 自动恢复（指令触发）
            await db.execute(text("""
                UPDATE xianyu_conversation
                SET auto_reply_paused = 0, last_manual_reply_at = NULL, updated_time = NOW()
                WHERE id = :conversation_id
            """), {"conversation_id": conversation_db_id})
            logger.info(
                "[AUTO_REPLY] 买家发送'开启自动回复'指令，自动恢复 AI 回复 tenantId=%d accountId=%d convId=%d",
                tenant_id, account_id, conversation_db_id
            )
            msg_text = "买家发送'开启自动回复'指令，已恢复 AI 自动回复"
        else:
            # 用户已手动关闭，指令无法自动恢复
            logger.info(
                "[AUTO_REPLY] 买家发送'开启自动回复'指令，但用户已手动关闭，保持暂停 tenantId=%d accountId=%d convId=%d",
                tenant_id, account_id, conversation_db_id
            )
            msg_text = "用户已手动关闭自动回复，需用户手动开启"
        # 此条指令消息本身不触发 AI 回复（避免回复"开启自动回复"这条指令）
        await db.commit()
        return {
            "ok": True,
            "matched": False,
            "autoSent": False,
            "conversationId": conversation_db_id,
            "message": msg_text,
        }

    if conv_paused == 1:
        if conv_manual_disabled == 1:
            # 用户手动关闭，跳过 AI 回复
            logger.info(
                "[AUTO_REPLY] 用户已手动关闭自动回复，跳过 AI 回复 tenantId=%d accountId=%d convId=%d",
                tenant_id, account_id, conversation_db_id
            )
            await db.commit()
            return {
                "ok": True,
                "matched": False,
                "autoSent": False,
                "conversationId": conversation_db_id,
                "message": "用户已手动关闭自动回复，AI 回复已暂停",
            }
        # 人工干预暂停中，检查是否超过 1 分钟自动恢复
        now_ms = int(time.time() * 1000)
        if conv_last_manual_at is None:
            # 异常状态：暂停但无 last_manual_reply_at，直接恢复
            await db.execute(text("""
                UPDATE xianyu_conversation
                SET auto_reply_paused = 0, last_manual_reply_at = NULL, updated_time = NOW()
                WHERE id = :conversation_id
            """), {"conversation_id": conversation_db_id})
            logger.warning(
                "[AUTO_REPLY] 暂停状态异常（无 last_manual_reply_at），自动恢复 tenantId=%d accountId=%d convId=%d",
                tenant_id, account_id, conversation_db_id
            )
        else:
            elapsed_ms = now_ms - int(conv_last_manual_at)
            if elapsed_ms >= pause_duration_ms:
                # 自动恢复（超过配置的暂停时长）
                await db.execute(text("""
                    UPDATE xianyu_conversation
                    SET auto_reply_paused = 0, last_manual_reply_at = NULL, updated_time = NOW()
                    WHERE id = :conversation_id
                """), {"conversation_id": conversation_db_id})
                logger.info(
                    "[AUTO_REPLY] 距上次人工回复 %dms >= %ds，自动恢复 AI 回复 tenantId=%d accountId=%d convId=%d",
                    elapsed_ms, pause_duration_seconds, tenant_id, account_id, conversation_db_id
                )
            else:
                # 暂停时长内，保持暂停
                logger.info(
                    "[AUTO_REPLY] 人工干预暂停中（%dms < %ds），跳过 AI 回复 tenantId=%d accountId=%d convId=%d",
                    elapsed_ms, pause_duration_seconds, tenant_id, account_id, conversation_db_id
                )
                await db.commit()
                return {
                    "ok": True,
                    "matched": False,
                    "autoSent": False,
                    "conversationId": conversation_db_id,
                    "message": "人工干预暂停中，AI 回复已临时挂起",
                }

    # === 人工干预兜底判定：上一条消息是否是卖家自己发送的（非 AI 自动回复） ===
    # 背景：auto_reply_paused 状态字段在以下场景会漏设置：
    #   1. 图片消息发送路径（/sendImageMessage）未调用暂停逻辑
    #   2. IM 回环异步任务可能丢失（asyncio.create_task）
    #   3. 会话匹配失败时静默跳过
    # 此处直接查询该会话最近一条 OUT 消息（非 AI 自动回复），若距当前 < 暂停时长（默认 60 秒），视为人工干预中，跳过 AI 回复。
    # 仅在 conv_paused == 0 时触发，作为状态字段机制的兜底；不替换现有暂停时长自动恢复逻辑。
    if conv_paused == 0 and conv_manual_disabled == 0:
        last_manual_msg = (await db.execute(text("""
            SELECT UNIX_TIMESTAMP(msg_time) * 1000 AS message_time
            FROM xianyu_message
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND conversation_id = :conversation_id
              AND deleted = 0
              AND direction = 1
              AND is_auto_reply = 0
            ORDER BY msg_time DESC, id DESC
            LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "conversation_id": conversation_db_id,
        })).mappings().first()
        if last_manual_msg and last_manual_msg.get("message_time"):
            try:
                last_manual_ms = int(last_manual_msg["message_time"])
                now_ms_val = int(time.time() * 1000)
                manual_elapsed_ms = now_ms_val - last_manual_ms
                if 0 <= manual_elapsed_ms < pause_duration_ms:
                    # 同步设置 auto_reply_paused 状态字段，让后续逻辑能正确感知并广播 SSE
                    await db.execute(text("""
                        UPDATE xianyu_conversation
                        SET auto_reply_paused = 1, last_manual_reply_at = :last_manual_at, updated_time = NOW()
                        WHERE id = :conversation_id AND auto_reply_paused = 0
                    """), {
                        "conversation_id": conversation_db_id,
                        "last_manual_at": last_manual_ms,
                    })
                    logger.info(
                        "[AUTO_REPLY] 兜底判定：上一条消息为卖家发送（%dms < %ds），暂停 AI 回复 tenantId=%d accountId=%d convId=%d",
                        manual_elapsed_ms, pause_duration_seconds, tenant_id, account_id, conversation_db_id
                    )
                    await db.commit()
                    return {
                        "ok": True,
                        "matched": False,
                        "autoSent": False,
                        "conversationId": conversation_db_id,
                        "message": "检测到卖家最近有人工回复，AI 回复已临时挂起",
                    }
            except (ValueError, TypeError) as exc:
                parse_error_kind = _exc_type_name(exc)
                logger.warning(
                    "[AUTO_REPLY] 兜底判定解析 message_time 失败 convId=%d value=%s errorType=%s",
                    conversation_db_id, last_manual_msg.get("message_time"), parse_error_kind
                )

    if platform_message_id:
        existing = (await db.execute(text("""
            SELECT id FROM xianyu_message
            WHERE tenant_id = :tenant_id AND account_id = :account_id AND conversation_id = :conversation_id
              AND deleted = 0 AND ext_message_id = :ext_message_id
            LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "conversation_id": conversation_db_id,
            "ext_message_id": platform_message_id,
        })).mappings().first()
        if existing:
            await db.commit()
            return {
                "ok": True,
                "matched": False,
                "conversationId": conversation_db_id,
                "messageId": int(existing["id"]),
                "platformMessageId": platform_message_id,
                "message": "消息已存在，跳过重复处理",
            }

    await db.execute(text("""
        INSERT INTO xianyu_message(
            tenant_id, account_id, conversation_id, from_user_id, to_user_id, content,
            message_type, direction, is_auto_reply, deleted, ext_message_id, created_time, updated_time
        ) VALUES(:tenant_id, :account_id, :conversation_id, :from_user_id, NULL, :content,
                 :message_type, 0, 0, 0, :ext_message_id, NOW(), NOW())
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "conversation_id": conversation_db_id,
        "from_user_id": buyer_id,
        "content": content,
        "message_type": message_type,
        "ext_message_id": platform_message_id or None,
    })
    trigger_message_id = (await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()

    # 消息过滤规则：命中 skip_reply 时跳过自动回复（仍保留消息入库与人工可见）
    filter_hits = await _check_message_filter(db, tenant_id, account_id, content)
    if "skip_reply" in filter_hits:
        await db.commit()
        return {
            "ok": True,
            "matched": False,
            "autoSent": False,
            "conversationId": conversation_db_id,
            "messageId": trigger_message_id,
            "platformMessageId": platform_message_id,
            "filtered": True,
            "filterTypes": filter_hits,
            "message": "消息过滤规则命中，已跳过自动回复",
        }

    rule = await _match_auto_reply_rule(db, tenant_id, account_id, content, goods_id=goods_id)
    if not rule:
        # 未命中显式规则，回退到 AI 客服配置（24小时智能客服）
        # 查询账号所属用户的 ai-customer-service 业务配置，若启用则构造虚拟 rule 走 AI 回复
        rule = await _build_ai_customer_service_rule(db, tenant_id, account_id, content, payload=payload)
        if not rule:
            default_reply_result = await _try_default_reply(
                db=db,
                tenant_id=tenant_id,
                account_id=account_id,
                conversation_db_id=conversation_db_id,
                content=content,
                buyer_id=buyer_id,
                buyer_name=buyer_name,
                ws_sid=ws_sid,
                goods_id=goods_id,
                trigger_message_id=trigger_message_id,
                platform_message_id=platform_message_id,
            )
            if default_reply_result:
                return default_reply_result
            await db.commit()
            return {
                "ok": True,
                "matched": False,
                "conversationId": conversation_db_id,
                "messageId": trigger_message_id,
                "platformMessageId": platform_message_id,
                "message": "未命中自动回复规则，且 AI 客服未启用",
            }

    # 幂等检查：该会话该规则对该消息是否已处理过自动回复（rule/trigger_message_id 此时均已赋值）
    # 注意：AI 客服 fallback 路径下 rule.id 为 None，SQL 中 `rule_id = NULL` 永远为 false 会导致去重失效
    # （历史 Bug：同一触发反复生成回复并发送）。此处使用 NULL-safe 匹配：rule_id 均为 NULL 时也视为相等。
    existing_reply = (await db.execute(text("""
        SELECT id FROM auto_reply_log
        WHERE tenant_id = :tenant_id AND account_id = :account_id AND conversation_id = :conversation_id
          AND (rule_id = :rule_id OR (rule_id IS NULL AND :rule_id IS NULL))
          AND trigger_message = :trigger_message AND deleted = 0
          AND action IN ('auto_send_allowed', 'suggest_only')
        ORDER BY id DESC LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "conversation_id": conversation_db_id,
        "rule_id": rule.get("id"),
        "trigger_message": content,
    })).mappings().first()
    if existing_reply:
        await db.commit()
        return {
            "ok": True,
            "matched": True,
            "autoSent": False,
            "conversationId": conversation_db_id,
            "messageId": trigger_message_id,
            "ruleId": rule.get("id"),
            "message": "该消息已处理过自动回复，跳过重复处理",
        }

    reply_content = _text(rule.get("reply_content"))
    reply_mode = _text(rule.get("reply_mode") or rule.get("reply_type") or "text").lower()
    reply_message_time = int(time.time() * 1000)

    safety_reasons = await _auto_reply_safety_reasons(db, tenant_id, rule, content)
    safe_mode = _safe_int(rule.get("safe_mode"), 1)
    if safety_reasons and safe_mode != 0:
        await _insert_auto_reply_blocked(db, tenant_id, account_id, conversation_db_id, rule, content, reply_content, safety_reasons)
        await db.commit()
        return {
            "ok": True,
            "matched": True,
            "autoSent": False,
            "action": "suggest_only",
            "conversationId": conversation_db_id,
            "messageId": trigger_message_id,
            "platformMessageId": platform_message_id,
            "ruleId": rule.get("id"),
            "replySuggestion": reply_content,
            "safetyReasons": safety_reasons,
            "message": "命中自动回复规则，但已按安全策略转为人工确认",
        }

    billing_result = None
    billing_pending: Optional[dict[str, Any]] = None
    if reply_mode in {"ai", "llm", "model"}:
        user_id = await _resolve_account_user_id(db, tenant_id, account_id, rule)
        if not user_id:
            await _insert_auto_reply_failure(db, tenant_id, account_id, conversation_db_id, rule, content, "AUTO_REPLY_USER_UNRESOLVED")
            await db.commit()
            return {"ok": False, "errorCode": "AUTO_REPLY_USER_UNRESOLVED", "matched": True, "conversationId": conversation_db_id, "messageId": trigger_message_id, "message": "AI 回复无法确定用户归属"}
        prompt_text = reply_content or "请根据买家消息生成当前商品的店铺客服回复"
        billing_request_id = build_stable_request_id(
            "auto_reply",
            tenant_id,
            account_id,
            conversation_db_id,
            platform_message_id or trigger_message_id,
            rule.get("id"),
        )

        # === 预检查：AI 模型是否已配置 ===
        from .ai_provider import _resolve_ai_config
        ai_cfg = await _resolve_ai_config()
        if not ai_cfg.get("enabled"):
            logger.warning("[AI_REPLY] AI 模型未配置，跳过自动回复 tenantId=%d accountId=%d source=%s",
                           tenant_id, account_id, ai_cfg.get("source"))
            await _insert_auto_reply_failure(db, tenant_id, account_id, conversation_db_id, rule, content,
                                              "AI_MODEL_UNAVAILABLE")
            await db.commit()
            return {"ok": False, "errorCode": "AI_MODEL_UNAVAILABLE", "matched": True, "conversationId": conversation_db_id,
                    "messageId": trigger_message_id, "message": "AI 对话模型暂不可用，请先完成配置"}

        # === 预检查：Token 余额是否充足 ===
        try:
            await precheck_ai_usage({
                "tenantId": tenant_id,
                "userId": user_id,
                "scene": "auto_reply",
                "providerName": "default",
                "modelName": "default",
                "modelType": "chat",
                "promptTokens": estimate_text_tokens(prompt_text + "\n买家消息：" + content),
                "completionTokens": 0,
                "requestId": billing_request_id,
            })
        except AiBillingPaymentRequired:
            await _insert_auto_reply_failure(db, tenant_id, account_id, conversation_db_id, rule, content,
                                              "AI_BALANCE_INSUFFICIENT")
            await db.commit()
            # Token 余额不足，发送"自动回复暂停"用户级通知（去重，每个用户只发一次）
            try:
                from .notify_dispatcher import notify_auto_reply_paused
                await notify_auto_reply_paused(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    account_id=account_id,
                    reason="AI Token 余额为 0，自动回复已暂停",
                )
            except Exception as notify_exc:
                _log_runtime_failure("notify_auto_reply_paused_on_precheck", notify_exc)
            return {"ok": False, "errorCode": "AI_BALANCE_INSUFFICIENT", "matched": True, "conversationId": conversation_db_id,
                    "messageId": trigger_message_id, "message": "AI Token 余额不足，请充值后重试"}
        except AiBillingUnavailable as exc:
            # 计费服务暂不可用（core-api 宕机/网络异常）时降级：不阻断自动回复，仅记录警告
            _log_runtime_failure("precheck_ai_balance_degraded", exc)
            logger.warning("[AI_REPLY] 计费服务暂不可用，降级跳过 precheck，继续执行自动回复 tenantId=%d accountId=%d",
                           tenant_id, account_id)
        except AiBillingError as exc:
            _log_runtime_failure("precheck_ai_balance", exc)
            await _insert_auto_reply_failure(db, tenant_id, account_id, conversation_db_id, rule, content,
                                              "AI_BILLING_UNAVAILABLE")
            await db.commit()
            return {"ok": False, "errorCode": "AI_BILLING_UNAVAILABLE", "matched": True, "conversationId": conversation_db_id,
                    "messageId": trigger_message_id, "message": "AI 计费服务暂不可用，请稍后重试"}

        # === 携带对话上下文（最近 8 条消息）===
        context_messages: list[dict] = []
        try:
            history_rows = (await db.execute(text("""
                SELECT direction, msg_content, content_type, message_time
                FROM xianyu_chat_message
                WHERE tenant_id = :tenant_id AND account_id = :account_id
                  AND s_id COLLATE utf8mb4_unicode_ci = :s_id COLLATE utf8mb4_unicode_ci
                  AND deleted = 0 AND content_type = 1
                  AND msg_content IS NOT NULL AND msg_content != ''
                ORDER BY message_time DESC, id DESC
                LIMIT 8
            """), {"tenant_id": tenant_id, "account_id": account_id,
                   "s_id": str(payload.get("sId") or "")})).mappings().all()
            # 倒序→正序
            for hr in reversed(history_rows):
                role = "assistant" if str(hr.get("direction") or "").upper() == "OUT" else "user"
                msg_text = _text(hr.get("msg_content") or "")
                if msg_text:
                    context_messages.append({"role": role, "content": msg_text})
        except Exception as ctx_err:
            _log_runtime_failure("load_auto_reply_context", ctx_err)
            context_messages = []

        # 追加当前买家消息作为最后一条
        context_messages.append({"role": "user", "content": content})

        ai_result = await generate_text(
            "auto_reply",
            prompt_text,
            "",
            0.3,
            messages=context_messages,
            request_id=billing_request_id,
            # 实时互动场景：收紧超时与重试，避免模型响应慢时买家长时间等待。
            # 20 秒未返回即放弃本次回复（最坏约 40s 两个重试窗口），
            # 与默认 60s×3 次（最坏 180s+）相比显著降低自动回复延迟。
            timeout=20,
            max_attempts=2,
        )
        raw_usage = None
        request_id = None
        provider_name = _text(rule.get("provider_name") or "default")
        model_name = _text(rule.get("model_name") or "default")
        if ai_result.get("ok"):
            reply_content = _text(ai_result.get("content"))
            raw_usage = ai_result.get("usage") or {}
            request_id = billing_request_id
            provider_name = _text(ai_result.get("provider") or provider_name)
            model_name = _text(ai_result.get("model") or model_name)
        else:
            await _insert_auto_reply_failure(db, tenant_id, account_id, conversation_db_id, rule, content, "AI_MODEL_UNAVAILABLE")
            await db.commit()
            return {"ok": False, "errorCode": "AI_MODEL_UNAVAILABLE", "matched": True, "conversationId": conversation_db_id,
                    "messageId": trigger_message_id, "message": "AI 对话模型暂不可用，请稍后重试"}

        # === AI 回复生成后、发送前二次检查人工干预暂停状态 ===
        # 背景：AI 模型生成回复需要数秒，期间卖家可能从其他客户端（移动 APP / PC 闲鱼）介入会话。
        # 若不二次检查，已生成的回复仍会被发出，与人工回复"撞车"形成自问自答。
        # 此处复用 rule.pause_duration_seconds（AI 客服场景）或回退查询配置（显式规则场景）。
        # 仅检查"人工干预暂停"（auto_reply_manual_disabled=0），用户手动关闭的会话不在此处拦截
        # （已在 5683 行状态检查中拦截，此处只兜底"AI 生成期间新增的人工干预"）。
        pause_secs_for_recheck = _safe_int(rule.get("pause_duration_seconds"), 0)
        if pause_secs_for_recheck <= 0:
            # 显式规则场景无 pause_duration_seconds 字段，回退查询配置
            pause_secs_for_recheck = await _resolve_ai_cs_pause_duration_seconds(db, tenant_id, account_id)
        pause_ms_for_recheck = pause_secs_for_recheck * 1000
        conv_state_recheck = (await db.execute(text("""
            SELECT auto_reply_paused, auto_reply_manual_disabled, last_manual_reply_at
            FROM xianyu_conversation
            WHERE id = :conversation_id
        """), {"conversation_id": conversation_db_id})).mappings().first()
        if conv_state_recheck:
            recheck_paused = int(conv_state_recheck.get("auto_reply_paused") or 0)
            recheck_manual_disabled = int(conv_state_recheck.get("auto_reply_manual_disabled") or 0)
            recheck_last_manual_at = conv_state_recheck.get("last_manual_reply_at")
            if recheck_paused == 1 and recheck_manual_disabled == 0 and recheck_last_manual_at:
                recheck_now_ms = int(time.time() * 1000)
                recheck_elapsed_ms = recheck_now_ms - int(recheck_last_manual_at)
                if 0 <= recheck_elapsed_ms < pause_ms_for_recheck:
                    # AI 生成期间卖家已介入，放弃发送已生成的回复（不计费、不入消息库）
                    logger.info(
                        "[AUTO_REPLY] AI 回复生成后二次检查：人工干预暂停中（%dms < %ds），放弃发送 tenantId=%d accountId=%d convId=%d",
                        recheck_elapsed_ms, pause_secs_for_recheck, tenant_id, account_id, conversation_db_id
                    )
                    await db.execute(text("""
                        INSERT INTO auto_reply_log(
                            tenant_id, account_id, conversation_id, rule_id, trigger_message, reply_content,
                            hit_type, status, fail_reason, action, safety_reasons, deleted, created_time, updated_time
                        ) VALUES(:tenant_id, :account_id, :conversation_id, :rule_id, :trigger_message, :reply_content,
                            :hit_type, 0, '人工干预暂停，AI 回复放弃发送', 'manual', '人工干预暂停', 0, NOW(), NOW())
                    """), {
                        "tenant_id": tenant_id,
                        "account_id": account_id,
                        "conversation_id": conversation_db_id,
                        "rule_id": rule.get("id"),
                        "trigger_message": content,
                        "reply_content": reply_content[:500] if reply_content else "",
                        "hit_type": rule.get("match_type") or "keyword",
                    })
                    await db.commit()
                    return {
                        "ok": True,
                        "matched": True,
                        "autoSent": False,
                        "conversationId": conversation_db_id,
                        "messageId": trigger_message_id,
                        "platformMessageId": platform_message_id,
                        "ruleId": rule.get("id"),
                        "replyContent": reply_content,
                        "message": "AI 回复生成后检测到人工干预，已放弃发送",
                    }

        # === 暂存计费上下文：发送成功后才扣费 ===
        # 关键约束：但凡存在发送失败的行为，都禁止进行 token 扣费。
        # 因此扣费不能在 AI 调用后立即执行，必须等到消息真正发送到闲鱼成功后再扣费。
        # 若扣费时计费服务暂不可用，走 pending_billing 补扣（消息已发送无法撤回）。
        billing_pending = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "scene": "auto_reply",
            "provider_name": provider_name,
            "model_name": model_name,
            "model_type": "chat",
            "prompt": prompt_text + "\n买家消息：" + content,
            "completion": reply_content,
            "request_id": billing_request_id,
            "raw_usage": raw_usage,
        }

    # === 先通过 WebSocket 发送回复，发送成功后才扣费与入库 ===
    # 旧实现先扣费再发送，发送失败时已扣 Token 但消息未发出，违反"发送失败禁止扣费"约束。
    # 改为先发送、成功后扣费与入库，失败时仅记录失败日志，不扣费。
    send_status = "skipped"
    send_error_code = ""
    send_error = ""
    send_result_detail: dict[str, Any] = {}
    if ws_sid:
        try:
            from .ws_client import ws_manager
            client = ws_manager.get_client(account_id)
            if not client or not client.is_connected:
                send_status = "ws_disconnected"
                send_error_code = "AUTO_REPLY_SEND_WS_DISCONNECTED"
                send_error = "WebSocket 未连接，自动回复未发送"
                logger.warning("[AUTO_REPLY] WS 未连接，回复未发送 accountId=%d cid=%s", account_id, ws_sid)
            else:
                to_id = buyer_id if "@" in buyer_id else f"{buyer_id}@goofish"
                reply_image = _text(rule.get("reply_image") or "") if isinstance(rule, dict) else ""
                image_send_ok = True
                if reply_image and reply_mode != "ai":
                    try:
                        from .ws_delivery_handler import _send_delivery_image
                        img_ok, _img_transient, img_err = await _send_delivery_image(
                            db, tenant_id, account_id, ws_sid, to_id, reply_image,
                        )
                        image_send_ok = bool(img_ok)
                        if not image_send_ok:
                            send_error = _text(img_err) or "图片回复发送失败"
                            logger.warning(
                                "runtimeFailure operation=send_auto_reply_image errorType=ProviderRejected requestId=%s upstreamError=%s",
                                get_request_id() or "-", send_error,
                            )
                    except Exception as img_exc:
                        image_send_ok = False
                        send_error = "图片回复发送异常，请稍后重试"
                        _log_runtime_failure("send_auto_reply_image", img_exc)
                if image_send_ok:
                    send_result = await _send_reply_content_via_client(
                        client, ws_sid, to_id, reply_content,
                    )
                else:
                    send_result = {"code": 400, "error": send_error}
                send_result_detail = send_result if isinstance(send_result, dict) else {}
                if send_result.get("code") == 200:
                    send_status = "sent"
                    logger.info("[AUTO_REPLY] 回复已发送 accountId=%d cid=%s toId=%s", account_id, ws_sid, to_id)
                else:
                    send_status = "send_failed"
                    send_error_code = "AUTO_REPLY_SEND_REJECTED"
                    # 优先使用 ws_client 返回的 errorCode/error，便于运维定位
                    upstream_error = _text(send_result.get("error"))
                    send_error = upstream_error or "自动回复发送失败，请检查账号连接后重试"
                    logger.warning(
                        "runtimeFailure operation=send_auto_reply errorType=ProviderRejected requestId=%s upstreamError=%s",
                        get_request_id() or "-", upstream_error,
                    )
        except Exception as send_exc:
            send_status = "exception"
            send_error_code = "AUTO_REPLY_SEND_EXCEPTION"
            send_error = "自动回复发送异常，请稍后重试"
            _log_runtime_failure("send_auto_reply", send_exc)
    else:
        send_status = "no_sid"
        send_error_code = "AUTO_REPLY_SEND_NO_SID"
        send_error = "payload 未携带 sId，无法通过 WS 发送"
        logger.warning("[AUTO_REPLY] 缺少 sId，回复未发送 accountId=%d", account_id)

    # 发送失败（含未连接/超时/无 sId/被拒绝/异常）：仅记录失败日志，不扣费、不写入消息表。
    # 关键约束：发送失败禁止 token 扣费，因此此处不走任何扣费/补扣逻辑。
    if send_status != "sent":
        if not send_error_code:
            # 兜底：未匹配到细化错误码时使用通用错误码
            send_error_code = "AUTO_REPLY_SEND_FAILED"
        await _insert_auto_reply_failure(db, tenant_id, account_id, conversation_db_id, rule, content, send_error_code)
        await db.commit()
        return {
            "ok": False,
            "errorCode": send_error_code,
            "matched": True,
            "conversationId": conversation_db_id,
            "messageId": trigger_message_id,
            "platformMessageId": platform_message_id,
            "ruleId": rule.get("id"),
            "replyContent": reply_content,
            "billing": _sanitize_runtime_value(billing_result),
            "sendStatus": send_status,
            "sendErrorCode": send_error_code,
            "sendError": send_error,
            "sendDetail": _sanitize_runtime_value(send_result_detail),
            "message": send_error or "自动回复发送失败",
        }

    # === 发送成功后才扣费 ===
    # 计费时若发生 503（计费服务暂不可用），消息已发送无法撤回，
    # 走 pending_billing 暂存待 Java 恢复后补扣；其余扣费失败也走 pending_billing 兜底补扣，
    # 最大限度避免"消息已发但未扣费"的情况。
    if billing_pending:
        try:
            billing_result = await charge_text_usage(**billing_pending)
        except AiBillingPaymentRequired as exc:
            # 兜底：precheck 通过但 charge 时余额被扣干（理论上不会发生，但兜底通知）
            # 消息已发送无法撤回，走 pending_billing 暂存补扣，待用户充值后自动补扣
            _log_runtime_failure("charge_auto_reply_payment_required", exc)
            await _enqueue_pending_auto_reply_billing(db, account_id, billing_pending, exc)
            try:
                from .notify_dispatcher import notify_auto_reply_paused
                await notify_auto_reply_paused(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    account_id=account_id,
                    reason="AI Token 余额为 0，自动回复已暂停",
                )
            except Exception as notify_exc:
                _log_runtime_failure("notify_auto_reply_paused_on_charge", notify_exc)
        except AiBillingUnavailable as exc:
            # 计费服务暂不可用：消息已发送，暂存计费请求待后续补扣
            _log_runtime_failure("charge_auto_reply_usage_degraded", exc)
            logger.warning("[AI_REPLY] 计费服务暂不可用，降级暂存计费请求待补扣（消息已发送）tenantId=%d accountId=%d",
                           tenant_id, account_id)
            await _enqueue_pending_auto_reply_billing(db, account_id, billing_pending, exc)
        except AiBillingError as exc:
            # 其他扣费失败：消息已发送，仍尝试暂存补扣，避免漏扣
            _log_runtime_failure("charge_auto_reply_usage", exc)
            logger.warning("[AI_REPLY] 扣费失败，暂存计费请求待补扣 tenantId=%d accountId=%d", tenant_id, account_id)
            await _enqueue_pending_auto_reply_billing(db, account_id, billing_pending, exc)

    # === 发送成功后才将回复写入数据库 ===
    await db.execute(text("""
        INSERT INTO xianyu_message(
            tenant_id, account_id, conversation_id, from_user_id, to_user_id, content,
            message_type, direction, is_auto_reply, deleted, created_time, updated_time
        ) VALUES(:tenant_id, :account_id, :conversation_id, NULL, :to_user_id, :content, 'text', 1, 1, 0, FROM_UNIXTIME(:created_time / 1000), NOW())
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "conversation_id": conversation_db_id,
        "to_user_id": buyer_id,
        "content": reply_content,
        "created_time": reply_message_time,
    })
    reply_message_id = (await db.execute(text("SELECT LAST_INSERT_ID()"))).scalar()

    if ws_sid and buyer_id:
        await save_chat_message(
            db,
            tenant_id,
            account_id,
            {
                "pnmId": "",
                "sId": ws_sid,
                "contentType": 1,
                "msgContent": reply_content,
                "senderUserId": seller_uid,
                "senderUserName": "我",
                "receiverUserId": buyer_id,
                "xyGoodsId": goods_id,
                "messageTime": reply_message_time,
                "direction": "OUT",
                "readStatus": 1,
            },
            seller_external_uid=seller_uid,
            sync_legacy_message=False,
            is_auto_reply=1,
        )

    await db.execute(text("""
        INSERT INTO auto_reply_log(
            tenant_id, account_id, conversation_id, rule_id, trigger_message, reply_content,
            hit_type, status, fail_reason, action, safety_reasons, deleted, created_time, updated_time
        ) VALUES(:tenant_id, :account_id, :conversation_id, :rule_id, :trigger_message, :reply_content,
            :hit_type, 1, NULL, 'auto_send_allowed', '', 0, NOW(), NOW())
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "conversation_id": conversation_db_id,
        "rule_id": rule.get("id"),
        "trigger_message": content,
        "reply_content": reply_content,
        "hit_type": rule.get("match_type") or "keyword",
    })
    # 更新会话最后消息 + 记录 AI 自动回复时间戳（用于人工干预检测与前端展示）
    await db.execute(text("""
        UPDATE xianyu_conversation
        SET last_message_time = NOW(),
            last_message_content = :reply_content,
            last_auto_reply_at = :last_auto_reply_at,
            updated_time = NOW()
        WHERE id = :conversation_id
    """), {
        "conversation_id": conversation_db_id,
        "reply_content": reply_content,
        "last_auto_reply_at": int(reply_message_time or (time.time() * 1000)),
    })
    await db.commit()

    return {
        "ok": True,
        "matched": True,
        "conversationId": conversation_db_id,
        "messageId": trigger_message_id,
        "platformMessageId": platform_message_id,
        "replyMessageId": reply_message_id,
        "ruleId": rule.get("id"),
        "replyContent": reply_content,
        "billing": _sanitize_runtime_value(billing_result),
        "sendStatus": send_status,
        "sendErrorCode": "",
        "sendError": "",
        "message": "已命中规则并生成自动回复记录",
    }


async def _auto_reply_safety_reasons(db: AsyncSession, tenant_id: int, rule: dict[str, Any], content: str) -> list[str]:
    reasons: list[str] = []
    text_content = _text(content)
    for keyword in _parse_keywords(rule.get("handoff_keywords") or ""):
        if keyword and keyword in text_content:
            reasons.append(f"命中人工接管关键词：{keyword}")
    # 仅对脱离平台交易/索要敏感信息等真正高风险行为禁止自动回复；
    # 常规售后（退款/退货/投诉/赔偿等）交由 AI 依据商品信息正常回答，不再默认拦截转人工
    if re.search(r"(线下交易|加微信|加我微信|私下付款|绕过平台|脱离平台|验证码|银行卡密码|身份证号(码)?|银行卡号|支付密码|先(交|付|转)(款|钱|押金)|输入账号密码|扫(码|脸)|登录我的账号)", text_content):
        reasons.append("涉及脱离平台交易或索要敏感信息等高风险场景")
    if rule.get("price_floor") is not None and re.search(r"(便宜|最低|少点|砍价|刀|包邮)", text_content):
        reasons.append(f"涉及议价，需人工确认最低价底线 {rule.get('price_floor')}")
    max_daily = _safe_int(rule.get("max_daily_replies"), 0)
    if max_daily > 0 and rule.get("id"):
        today_count = (await db.execute(text("""
            SELECT COUNT(*) FROM auto_reply_log
            WHERE tenant_id=:tenant_id AND rule_id=:rule_id AND deleted=0
              AND action='auto_send_allowed' AND DATE(created_time)=CURRENT_DATE()
        """), {"tenant_id": tenant_id, "rule_id": rule.get("id")})).scalar() or 0
        if int(today_count) >= max_daily:
            reasons.append(f"已达到该规则每日自动回复上限：{max_daily}")
    return reasons


async def _insert_auto_reply_blocked(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    conversation_id: int,
    rule: dict[str, Any],
    trigger_message: str,
    reply_content: str,
    safety_reasons: list[str],
) -> None:
    await db.execute(text("""
        INSERT INTO auto_reply_log(
            tenant_id, account_id, conversation_id, rule_id, trigger_message, reply_content,
            hit_type, status, fail_reason, action, safety_reasons, deleted, created_time, updated_time
        ) VALUES(:tenant_id, :account_id, :conversation_id, :rule_id, :trigger_message, :reply_content,
            :hit_type, 2, NULL, 'suggest_only', :safety_reasons, 0, NOW(), NOW())
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "conversation_id": conversation_id,
        "rule_id": rule.get("id"),
        "trigger_message": trigger_message,
        "reply_content": reply_content,
        "hit_type": rule.get("match_type") or "keyword",
        "safety_reasons": "；".join(safety_reasons),
    })


async def _resolve_account_user_id(db: AsyncSession, tenant_id: int, account_id: int, rule: dict[str, Any]) -> Optional[int]:
    user_id = _safe_int(rule.get("user_id") or rule.get("userId"))
    if user_id:
        return user_id
    try:
        row = (await db.execute(text("""
            SELECT user_id FROM xianyu_account
            WHERE tenant_id = :tenant_id AND id = :account_id AND deleted = 0
            LIMIT 1
        """), {"tenant_id": tenant_id, "account_id": account_id})).mappings().first()
    except Exception as exc:
        # ★ DB 异常：通过 _log_runtime_failure 记录错误类型（不泄露异常详情），再 re-raise
        _log_runtime_failure("resolve_account_user_id_db_query", exc)
        raise
    # ★ 临时调试日志：DB 查询结果（确认后删除）
    logger.warning(
        "[IMAGE_GENERATE-DEBUG] _resolve_account_user_id tenant_id=%r account_id=%r row=%r user_id=%r",
        tenant_id, account_id, (dict(row) if row else None), (row.get("user_id") if row else None),
    )
    return _safe_int(row.get("user_id")) if row else None


async def _is_account_active_for_auto_reply(db: AsyncSession, tenant_id: int, account_id: int) -> bool:
    row = (await db.execute(text("""
        SELECT status
        FROM xianyu_account
        WHERE tenant_id = :tenant_id
          AND id = :account_id
          AND deleted = 0
        LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
    })).mappings().first()
    if not row:
        return False
    status = row.get("status")
    return status is None or _safe_int(status, 0) == 1


def _build_ai_fallback_reply(content: str, prompt_text: str) -> str:
    content = _text(content)
    prompt_text = _text(prompt_text)
    if prompt_text and len(prompt_text) <= 180 and "{" not in prompt_text:
        return f"您好，关于“{content[:80]}”，{prompt_text}"
    return f"您好，已收到您的消息：{content[:120]}。我这边马上为您处理，请稍等。"


def _normalize_ai_cs_entries(raw: Any, *, fallback_text: str = "", prefix: str = "内容", source: str = "user") -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            normalized = _normalize_ai_cs_entry(item, prefix=prefix, index=index, source=source)
            if normalized:
                items.append(normalized)
    elif isinstance(raw, str) and raw.strip():
        items.append({
            "name": f"{prefix} 1",
            "content": raw.strip(),
            "source": source,
        })

    fallback_text = _text(fallback_text).strip()
    if not items and fallback_text:
        items.append({
            "name": f"{prefix} 1",
            "content": fallback_text,
            "source": source,
        })
    return items


def _normalize_ai_cs_entry(raw: Any, *, prefix: str, index: int, source: str) -> Optional[dict[str, str]]:
    if raw is None:
        return None
    if isinstance(raw, str):
        content = raw.strip()
        if not content:
            return None
        return {"name": f"{prefix} {index}", "content": content, "source": source}
    if isinstance(raw, dict):
        content = _text(raw.get("content")).strip()
        if not content:
            return None
        name = _text(raw.get("name") or raw.get("title") or f"{prefix} {index}").strip() or f"{prefix} {index}"
        return {
            "name": name,
            "content": content,
            "source": _text(raw.get("source") or source) or source,
        }
    return None


def _join_ai_cs_entry_contents(entries: list[dict[str, str]]) -> str:
    return "\n\n".join(
        _text(item.get("content")).strip()
        for item in entries
        if isinstance(item, dict) and _text(item.get("content")).strip()
    )


def _bool_to_smallint(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    text_value = _text(value).strip().lower()
    if text_value in {"1", "true", "yes", "on"}:
        return 1
    if text_value in {"0", "false", "no", "off"}:
        return 0
    return None


def _compute_ai_cs_effective_enabled(
    *,
    global_enabled: bool,
    account_id: int,
    account_scopes: dict[str, Any],
    product_enabled: Optional[int],
) -> bool:
    if not global_enabled:
        return False
    if product_enabled is not None:
        return int(product_enabled) == 1
    accounts = (account_scopes or {}).get("accounts", {}) or {}
    account_key = str(account_id)
    if account_key in accounts:
        return bool(accounts.get(account_key))
    return True


async def _load_ai_cs_account_scopes(db: AsyncSession, tenant_id: int) -> dict[str, Any]:
    row = (await db.execute(text("""
        SELECT config_json FROM user_business_setting
        WHERE tenant_id = :tenant_id
          AND setting_key = 'auto-reply-account-scopes'
          AND deleted = 0
        LIMIT 1
    """), {"tenant_id": tenant_id})).mappings().first()
    if not row:
        return {"accounts": {}}
    try:
        config = json.loads(row["config_json"]) if row["config_json"] else {}
        return config if isinstance(config, dict) else {"accounts": {}}
    except Exception:
        return {"accounts": {}}


async def _load_goods_context(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    goods_id: str,
    sid: str = "",
    buyer_id: str = "",
) -> Optional[dict[str, Any]]:
    normalized_goods_id = _text(goods_id).strip()
    if not normalized_goods_id and buyer_id:
        conv_row = (await db.execute(text("""
            SELECT goods_id
            FROM xianyu_conversation
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND deleted = 0
              AND external_buyer_id = :buyer_id
              AND goods_id IS NOT NULL
              AND goods_id != ''
            ORDER BY updated_time DESC, id DESC
            LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "buyer_id": buyer_id,
        })).mappings().first()
        if conv_row:
            normalized_goods_id = _text(conv_row.get("goods_id")).strip()

    if not normalized_goods_id and sid:
        msg_row = (await db.execute(text("""
            SELECT xy_goods_id
            FROM xianyu_chat_message
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND s_id COLLATE utf8mb4_unicode_ci = :sid COLLATE utf8mb4_unicode_ci
              AND deleted = 0
              AND xy_goods_id IS NOT NULL
              AND xy_goods_id != ''
            ORDER BY message_time DESC, id DESC
            LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "sid": sid,
        })).mappings().first()
        if msg_row:
            normalized_goods_id = _text(msg_row.get("xy_goods_id")).strip()

    if not normalized_goods_id:
        return None

    row = (await db.execute(text("""
        SELECT id, goods_id, external_goods_id, title, price, sold_price, cover_pic, image_url,
               image_urls, detail_info, description, detail_url, quantity, stock, status,
               category, raw_payload, auto_reply_enabled
        FROM xianyu_goods
        WHERE tenant_id = :tenant_id
          AND account_id = :account_id
          AND deleted = 0
          AND (external_goods_id = :goods_id OR goods_id = :goods_id)
        ORDER BY updated_time DESC, id DESC
        LIMIT 1
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "goods_id": normalized_goods_id,
    })).mappings().first()
    if not row:
        return None

    data = dict(row)
    image_urls = data.get("image_urls")
    if isinstance(image_urls, str):
        try:
            image_urls = json.loads(image_urls)
        except Exception:
            image_urls = []
    data["image_urls"] = image_urls if isinstance(image_urls, list) else []
    raw_payload = data.get("raw_payload")
    if isinstance(raw_payload, str):
        try:
            raw_payload = json.loads(raw_payload)
        except Exception:
            raw_payload = raw_payload
    data["raw_payload"] = raw_payload
    return data


def _build_goods_context_text(goods: Optional[dict[str, Any]]) -> str:
    if not goods:
        return "当前还没有查到这条会话对应商品的本地资料。买家如果追问具体配置、成色、库存或价格细节，就自然说明这个细节我这边暂时确认不了，请买家查看商品页或等人工再帮他确认。"

    # 库存显示：当本地库存为 0 或缺失时，显示"未知"而非"0"
    # 原因：闲鱼列表 API 不返回库存字段，详情同步可能延迟或失败，
    # 此时本地 stock=0 不代表真实库存为 0，避免 AI 据此告知买家"没库存"导致订单流失
    quantity_val = _text(goods.get('quantity') or goods.get('stock'))
    try:
        stock_display = '未知' if (not quantity_val or int(quantity_val) <= 0) else quantity_val
    except (ValueError, TypeError):
        stock_display = '未知'

    lines = [
        f"商品ID：{_text(goods.get('external_goods_id') or goods.get('goods_id')) or '未知'}",
        f"商品标题：{_text(goods.get('title')) or '未知'}",
        f"商品价格：{_text(goods.get('price')) or '未知'}",
        f"商品售价：{_text(goods.get('sold_price')) or _text(goods.get('price')) or '未知'}",
        f"库存：{stock_display}",
        f"商品分类：{_text(goods.get('category')) or '未知'}",
        f"商品状态：{_text(goods.get('status')) or '未知'}",
        f"商品文案：{_text(goods.get('description') or goods.get('detail_info')) or '暂无'}",
        f"详情链接：{_text(goods.get('detail_url')) or '暂无'}",
    ]
    if goods.get("image_urls"):
        lines.append(f"商品图片数量：{len(goods.get('image_urls') or [])}")
    return "\n".join(lines)


async def _fallback_db_search_learned_kb(
    db: AsyncSession,
    kb_ids: list[int],
    query: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """DB 关键词兜底检索学习知识库。

    当 RAG 向量检索不可用（embedding 服务未配置或失败）时使用。
    策略：
    1. 优先按 question 字段 LIKE 全词匹配（最相关）
    2. 命中不足 top_k 时，补充按 question 分词 LIKE 匹配
    3. 仍不足时，按 score 降序返回前 top_k 条（兜底保证有内容注入）

    Args:
        db: 数据库会话
        kb_ids: 用户启用的 learned KB id 列表
        query: 买家消息内容
        top_k: 返回前 K 条

    Returns:
        [{question, answer, category, score, kb_id, similarity, weighted}, ...]
    """
    if not kb_ids or not query or not query.strip():
        return []
    try:
        # 1. 优先 question LIKE 全词匹配
        # 注意：kb_ids 已经在调用前确认非空，使用 IN 子句查询
        kb_ids_set = [int(kb) for kb in kb_ids]
        rows = (await db.execute(text(
            "SELECT id, question, answer, tags, score FROM ai_cs_learned_kb "
            "WHERE id IN :ids AND deleted=0 AND review_status='approved' "
            "AND enabled=1 AND sensitive_filtered=1 "
            "AND (question LIKE :q OR tags LIKE :q) "
            "ORDER BY score DESC LIMIT :limit"
        ).bindparams(
            sqlalchemy.bindparam("ids", expanding=True),
        ), {"ids": kb_ids_set, "q": f"%{query.strip()[:200]}%", "limit": top_k})).mappings().all()

        # 2. 命中不足时，按 score 降序兜底返回
        if len(rows) < top_k:
            existing_ids = {r["id"] for r in rows}
            extra_rows = (await db.execute(text(
                "SELECT id, question, answer, tags, score FROM ai_cs_learned_kb "
                "WHERE id IN :ids AND deleted=0 AND review_status='approved' "
                "AND enabled=1 AND sensitive_filtered=1 "
                "ORDER BY score DESC LIMIT :limit"
            ).bindparams(
                sqlalchemy.bindparam("ids", expanding=True),
            ), {"ids": kb_ids_set, "limit": top_k})).mappings().all()
            for r in extra_rows:
                if r["id"] not in existing_ids:
                    rows.append(r)
                    if len(rows) >= top_k:
                        break

        return [
            {
                "question": r["question"] or "",
                "answer": r["answer"] or "",
                "category": "",
                "score": float(r["score"] or 50),
                "kb_id": r["id"],
                "similarity": 0.5,  # DB 检索无相似度，给固定中位值
                "weighted": 0.5,    # 与 similarity 一致，避免影响排序
            }
            for r in rows[:top_k]
        ]
    except Exception as exc:
        search_error_kind = _exc_type_name(exc)
        logger.warning("[AI_CS] db fallback search failed errorType=%s", search_error_kind)
        return []


def _build_ai_cs_system_prompt(
    cfg: dict[str, Any],
    goods: Optional[dict[str, Any]],
    user_knowledge_bases: list[dict[str, str]],
    user_chat_rules: list[dict[str, str]],
    default_knowledge_bases: list[dict[str, str]],
    default_chat_rules: list[dict[str, str]],
    sensitive_words: Optional[list[str]] = None,
    learned_kb_hits: Optional[list[dict[str, Any]]] = None,
    user_private_kb_hits: Optional[list[dict[str, Any]]] = None,
) -> str:
    """构造 AI 客服系统提示词。

    V1.49 调整 prompt 注入顺序（用户要求）：
    回复优先级：系统提示 → 回复规则 → 知识库 → 敏感词限制。
    1. 用户自定义系统提示（systemPrompt）：角色定位、语气、品牌风格
    2. 当前商品信息：上下文必备
    3. 回复规则（chat_rules）：用户优先 + 默认补充，定义"该说什么、不该说什么"
    4. 知识库（按优先级）：用户私有知识库 > 用户启用知识库 > 学习知识库 > 默认知识库
    5. 敏感词限制：最后兜底，禁止出现违规内容

    不再预设角色、语气、库存红线等硬编码提示词，避免覆盖用户自定义语气。
    """
    parts: list[Any] = []

    # 1) 用户自定义系统提示词（最优先，严格遵守）
    custom_prompt = _text(cfg.get("systemPrompt")).strip()
    if custom_prompt:
        parts.append(custom_prompt)
        parts.append("")

    # 2) 当前商品信息（上下文，必须提供）
    parts.append("【当前商品信息】")
    parts.append(_build_goods_context_text(goods))

    # 3) 回复规则（用户优先 → 默认补充）
    # 注入顺序调整：先规则后知识库，AI 回复时优先按规则约束
    has_user_rules = bool(user_chat_rules)
    has_default_rules = bool(default_chat_rules)
    if has_user_rules or has_default_rules:
        parts.extend(["", "【回复规则（必须严格遵守，优先级高于知识库）】"])
        parts.append("当买家提问时，请按以下规则约束回复口径。规则中的内容必须严格遵守，")
        parts.append("若规则与知识库内容冲突，以规则为准。")
        if has_user_rules:
            parts.append("")
            parts.append("--- 用户回复规则（优先） ---")
            parts.append(_join_ai_cs_entry_contents(user_chat_rules))
        if has_default_rules:
            parts.append("")
            parts.append("--- 默认回复规则（补充） ---")
            parts.append(_join_ai_cs_entry_contents(default_chat_rules))

    # 4) 知识库（按优先级：用户私有 → 用户启用 → 学习 → 默认）
    MAX_KB_PER_ITEM_CHARS = 800
    MAX_KB_TOTAL_CHARS = 4000
    has_any_kb = (
        user_private_kb_hits
        or user_knowledge_bases
        or learned_kb_hits
        or default_knowledge_bases
    )
    if has_any_kb:
        parts.extend(["", "【知识库（参考素材，用于辅助回复）】"])
        parts.append("以下知识库条目作为回复参考素材。若与上方回复规则冲突，以规则为准。")

    # 4.1 用户的私有知识库（最高优先级）
    if user_private_kb_hits:
        parts.append("")
        parts.append("--- 我的私有知识库（最高优先级） ---")
        total_user_kb_chars = 0
        for hit in user_private_kb_hits:
            title = str(hit.get('title', ''))[:100]
            content = str(hit.get('content', ''))[:MAX_KB_PER_ITEM_CHARS]
            snippet = f"{'### ' + title + chr(10) if title else ''}{content}"
            if total_user_kb_chars + len(snippet) > MAX_KB_TOTAL_CHARS:
                parts.append("（更多知识库条目已截断）")
                break
            parts.append(snippet)
            parts.append("")
            total_user_kb_chars += len(snippet)

    # 4.2 用户主动配置的知识库
    if user_knowledge_bases:
        parts.append("")
        parts.append("--- 用户启用知识库（高优先级） ---")
        parts.append(_join_ai_cs_entry_contents(user_knowledge_bases))

    # 4.3 学习知识库（RAG 检索结果，按买家问题匹配）
    # 注：answer 字段是 MEDIUMTEXT，可能极长。这里限制单条 800 字、总 4000 字，避免 prompt 爆炸。
    if learned_kb_hits:
        parts.append("")
        parts.append("--- 学习知识库（按问题匹配，含分类标签） ---")
        total_kb_chars = 0
        for hit in learned_kb_hits:
            q = str(hit.get('question', ''))[:200]
            a = str(hit.get('answer', ''))[:MAX_KB_PER_ITEM_CHARS]
            snippet = f"Q: {q}\nA: {a}"
            if total_kb_chars + len(snippet) > MAX_KB_TOTAL_CHARS:
                parts.append("（更多知识库条目已截断）")
                break
            parts.append(snippet)
            cat = hit.get('category', '')
            score = hit.get('score', 0)
            if cat or score:
                parts.append(f"（分类: {cat} | 评分: {score}）")
            parts.append("")
            total_kb_chars += len(snippet)

    # 4.4 默认知识库（兜底补充）
    if default_knowledge_bases:
        parts.append("")
        parts.append("--- 默认知识库（补充） ---")
        parts.append(_join_ai_cs_entry_contents(default_knowledge_bases))

    # 5) 后台配置的敏感词限制（最后兜底）
    if sensitive_words:
        parts.extend(["", "【回复禁用词】以下词汇不得出现在你的回复中：", "、".join(sensitive_words)])

    return "\n".join(part for part in parts if part is not None).strip()


async def _insert_auto_reply_failure(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    conversation_id: int,
    rule: dict[str, Any],
    trigger_message: str,
    error_code: str,
) -> None:
    fail_reason = _PUBLIC_RUNTIME_ERRORS.get(error_code, _PUBLIC_RUNTIME_ERRORS["RUNTIME_OPERATION_FAILED"])
    await db.execute(text("""
        INSERT INTO auto_reply_log(
            tenant_id, account_id, conversation_id, rule_id, trigger_message, reply_content,
            hit_type, status, fail_reason, action, safety_reasons, deleted, created_time, updated_time
        ) VALUES(:tenant_id, :account_id, :conversation_id, :rule_id, :trigger_message, '',
            :hit_type, 0, :fail_reason, 'manual', :fail_reason, 0, NOW(), NOW())
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "conversation_id": conversation_id,
        "rule_id": rule.get("id"),
        "trigger_message": trigger_message,
        "hit_type": rule.get("match_type") or "keyword",
        "fail_reason": fail_reason,
    })


async def _enqueue_pending_auto_reply_billing(
    db: AsyncSession,
    account_id: int,
    billing_pending: dict[str, Any],
    exc: BaseException,
) -> None:
    """将自动回复计费请求暂存到 pending_billing 表，待 Java core-api 恢复后由定时任务补扣。

    使用场景：自动回复消息已通过 WebSocket 发送到闲鱼，但 Java 计费服务暂不可用
    或扣费异常。此时消息已发出无法撤回，只能暂存计费请求等待补扣，避免漏扣 Token。
    """
    try:
        await ensure_pending_billing_table()
        pending_payload = build_text_charge_payload(
            tenant_id=billing_pending["tenant_id"],
            user_id=billing_pending["user_id"],
            scene=billing_pending["scene"],
            provider_name=billing_pending["provider_name"],
            model_name=billing_pending["model_name"],
            model_type=billing_pending["model_type"],
            prompt=billing_pending["prompt"],
            completion=billing_pending["completion"],
            request_id=billing_pending["request_id"],
            raw_usage=billing_pending["raw_usage"],
        )
        await enqueue_pending_billing(
            db,
            tenant_id=billing_pending["tenant_id"],
            user_id=billing_pending["user_id"],
            account_id=account_id,
            scene=billing_pending["scene"],
            request_id=billing_pending["request_id"],
            payload=pending_payload,
            error=f"计费暂存失败: {type(exc).__name__}",
        )
    except Exception as enqueue_exc:
        _log_runtime_failure("enqueue_pending_auto_reply_billing", enqueue_exc)


async def _resolve_ai_cs_pause_duration_seconds(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
) -> int:
    """读取 ai-customer-service 配置中的人工干预暂停时长（秒）。

    用于会话级自动回复状态检查（process_incoming_message 5683 行附近的 60_000 硬编码替换）。
    该检查在 rule 匹配之前生效，无法从 rule 读取，故独立查询。

    Returns:
        int: 暂停时长（秒）。
             - pauseOnHumanIntervene=false → 返回 0（表示不暂停，调用方据此跳过暂停逻辑）
             - pauseOnHumanIntervene=true（默认）→ 返回 pauseDurationSeconds（默认 60，0 或负数视为 60）
             - 配置缺失/异常 → 返回 60（保守默认，避免暂停失效导致 AI 与人工"撞车"）
    """
    default_seconds = 60
    try:
        user_id = _safe_int((await db.execute(text("""
            SELECT user_id FROM xianyu_account
            WHERE tenant_id = :tenant_id AND id = :account_id AND deleted = 0
            LIMIT 1
        """), {"tenant_id": tenant_id, "account_id": account_id})).scalar())
        if not user_id:
            return default_seconds
        cfg_row = (await db.execute(text("""
            SELECT config_json FROM user_business_setting
            WHERE tenant_id = :tenant_id AND user_id = :user_id
              AND setting_key = 'ai-customer-service' AND deleted = 0
            LIMIT 1
        """), {"tenant_id": tenant_id, "user_id": user_id})).mappings().first()
        if not cfg_row:
            # fallback 到租户级任意用户配置
            cfg_row = (await db.execute(text("""
                SELECT config_json FROM user_business_setting
                WHERE tenant_id = :tenant_id
                  AND setting_key = 'ai-customer-service' AND deleted = 0
                ORDER BY updated_time DESC, id DESC
                LIMIT 1
            """), {"tenant_id": tenant_id})).mappings().first()
        if not cfg_row or not cfg_row["config_json"]:
            return default_seconds
        cfg = json.loads(cfg_row["config_json"])
        # pauseOnHumanIntervene 开关：默认 true；显式 false 时返回 0（不暂停）
        if cfg.get("pauseOnHumanIntervene") in (False, "false", "False", 0, "0"):
            return 0
        val = _safe_int(cfg.get("pauseDurationSeconds"), default_seconds)
        # 0 或负数视为默认 60（避免暂停逻辑失效导致 AI 与人工"撞车"）
        if val <= 0:
            return default_seconds
        return val
    except Exception as exc:
        pause_cfg_kind = _exc_type_name(exc)
        logger.warning(
            "[AUTO_REPLY] 读取 pauseDurationSeconds 失败，回退默认 60s tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, pause_cfg_kind,
        )
        return default_seconds


async def _try_default_reply(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    conversation_db_id: int,
    content: str,
    buyer_id: str,
    buyer_name: str,
    ws_sid: str,
    goods_id: str,
    trigger_message_id: Optional[int],
    platform_message_id: str,
) -> Optional[dict[str, Any]]:
    """未命中关键词规则且 AI 客服关闭时的兜底回复。

    支持 text（可附带图片）与 api（外部接口）两种类型；reply_once 时对同一买家只回复一次。
    任何失败均静默降级（返回 None），不阻塞消息入库。
    """
    try:
        row = (await db.execute(text("""
            SELECT * FROM default_reply
            WHERE tenant_id = :tenant_id AND account_id = :account_id
              AND deleted = 0 AND enabled = 1
            LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
        })).mappings().first()
        if not row:
            return None

        buyer_key = _text(buyer_id or "").strip()
        reply_once = _safe_int(row.get("reply_once"), 0)
        if reply_once == 1 and buyer_key:
            existing = (await db.execute(text("""
                SELECT id FROM default_reply_record
                WHERE tenant_id = :tenant_id AND account_id = :account_id
                  AND buyer_user_id = :buyer_user_id
                LIMIT 1
            """), {
                "tenant_id": tenant_id,
                "account_id": account_id,
                "buyer_user_id": buyer_key,
            })).mappings().first()
            if existing:
                return None

        reply_type = _text(row.get("reply_type") or "text").lower()
        reply_content = _text(row.get("reply_content") or "")
        reply_image = _text(row.get("reply_image") or "")
        api_url = _text(row.get("api_url") or "")
        api_timeout = _safe_int(row.get("api_timeout"), 30)

        if reply_type == "api":
            from .default_reply_api import call_reply_api
            reply_content = await call_reply_api(
                account_id=account_id,
                message=content,
                api_url=api_url,
                timeout=api_timeout,
                chat_id=str(conversation_db_id or ""),
                item_id=goods_id or None,
                send_user_id=buyer_key or None,
                send_user_name=buyer_name or None,
            ) or ""
            if not reply_content:
                return None

        # 变量替换，与关键词规则体验保持一致
        reply_content = reply_content.replace("{send_user_name}", buyer_name or "买家")
        reply_content = reply_content.replace("{send_user_id}", buyer_key or "")
        reply_content = reply_content.replace("{send_message}", content)

        sent = False
        fail_reason = ""
        if reply_image and reply_type == "text":
            from .ws_delivery_handler import _send_delivery_image
            try:
                ok, _is_transient, err = await _send_delivery_image(
                    db, tenant_id, account_id, ws_sid or "", buyer_key, reply_image,
                )
                sent = bool(ok)
                if not sent:
                    fail_reason = _text(err) or "图片默认回复发送失败"
            except Exception as exc:
                image_send_kind = _exc_type_name(exc)
                logger.warning(
                    "[DEFAULT_REPLY] 图片默认回复发送异常 tenantId=%d accountId=%d errorType=%s",
                    tenant_id, account_id, image_send_kind,
                )
                fail_reason = "图片默认回复发送异常"
        elif reply_content:
            if ws_sid:
                from .ws_client import ws_manager
                client = ws_manager.get_client(account_id)
                if client and client.is_connected:
                    to_id = buyer_key if "@" in buyer_key else f"{buyer_key}@goofish"
                    send_result = await _send_reply_content_via_client(
                        client, ws_sid, to_id, reply_content,
                    )
                    sent = bool(send_result and send_result.get("code") == 200)
                    if not sent:
                        fail_reason = _text(send_result.get("error")) or "默认回复发送失败"
                else:
                    fail_reason = "WebSocket 未连接，默认回复未发送"
            else:
                fail_reason = "缺少会话ID，默认回复未发送"
        else:
            fail_reason = "默认回复内容为空"

        # 记录自动回复日志（source=default_reply），便于用户在日志页追踪
        await db.execute(text("""
            INSERT INTO auto_reply_log(
                tenant_id, account_id, conversation_id, rule_id, trigger_message, reply_content,
                hit_type, status, fail_reason, action, safety_reasons, deleted, created_time, updated_time
            ) VALUES(:tenant_id, :account_id, :conversation_id, NULL, :trigger_message, :reply_content,
                'default_reply', :status, :fail_reason, 'auto_send_allowed', '', 0, NOW(), NOW())
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
            "conversation_id": conversation_db_id,
            "trigger_message": content,
            "reply_content": reply_content[:500] if reply_content else "",
            "status": 1 if sent else 0,
            "fail_reason": fail_reason or "",
        })

        if reply_once == 1 and sent and buyer_key:
            try:
                await db.execute(text("""
                    INSERT IGNORE INTO default_reply_record(tenant_id, account_id, buyer_user_id, created_time)
                    VALUES(:tenant_id, :account_id, :buyer_user_id, NOW())
                """), {
                    "tenant_id": tenant_id,
                    "account_id": account_id,
                    "buyer_user_id": buyer_key,
                })
            except Exception as exc:
                def_reply_record_err = _exc_type_name(exc)
                logger.warning(
                    "[DEFAULT_REPLY] 写入默认回复记录失败 tenantId=%d accountId=%d errorType=%s",
                    tenant_id, account_id, def_reply_record_err,
                )

        await db.commit()
        return {
            "ok": True,
            "matched": True,
            "autoSent": sent,
            "conversationId": conversation_db_id,
            "messageId": trigger_message_id,
            "platformMessageId": platform_message_id,
            "ruleId": None,
            "replyContent": reply_content,
            "source": "default_reply",
            "message": "默认回复已发送" if sent else f"默认回复未发送：{fail_reason}",
        }
    except Exception as exc:
        def_reply_run_err = _exc_type_name(exc)
        logger.warning(
            "[DEFAULT_REPLY] 默认回复执行异常 tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, def_reply_run_err,
        )
        try:
            await db.rollback()
        except Exception:
            pass
        return None


async def _build_ai_customer_service_rule(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    content: str,
    payload: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """根据 user_business_setting 中的 ai-customer-service 配置构造虚拟自动回复规则。

    实现「24小时智能客服」：用户在系统设置中开启 AI 客服后，
    即便没有显式 auto_reply_rule，买家消息也会由 AI 自动回复。

    Returns:
        dict: 虚拟 rule（reply_mode='ai'），或 None 表示 AI 客服未启用/不在工作时段
    """
    # 1) 解析账号所属用户 ID（与 _resolve_account_user_id 同逻辑，但同步内联以避免循环依赖）
    user_id = _safe_int((await db.execute(text("""
        SELECT user_id FROM xianyu_account
        WHERE tenant_id = :tenant_id AND id = :account_id AND deleted = 0
        LIMIT 1
    """), {"tenant_id": tenant_id, "account_id": account_id})).scalar())
    if not user_id:
        logger.debug("[AI_CS] 账号未关联用户，跳过 AI 客服 tenantId=%d accountId=%d", tenant_id, account_id)
        return None

    # 2) 读取 ai-customer-service 配置
    #    按账号归属 user_id 查询；查不到时 fallback 到 tenant_id 下任意 user_id 的同 key 配置，
    #    适配单租户多用户场景（用户可能用某个子账号登录并配置，但闲鱼账号归属另一个用户）。
    cfg_row = (await db.execute(text("""
        SELECT config_json FROM user_business_setting
        WHERE tenant_id = :tenant_id AND user_id = :user_id
          AND setting_key = 'ai-customer-service' AND deleted = 0
        LIMIT 1
    """), {"tenant_id": tenant_id, "user_id": user_id})).mappings().first()
    if cfg_row:
        logger.debug("[AI_CS] 命中账号归属用户配置 tenantId=%d userId=%d", tenant_id, user_id)
    else:
        cfg_row = (await db.execute(text("""
            SELECT config_json FROM user_business_setting
            WHERE tenant_id = :tenant_id
              AND setting_key = 'ai-customer-service' AND deleted = 0
            ORDER BY updated_time DESC, id DESC
            LIMIT 1
        """), {"tenant_id": tenant_id})).mappings().first()
        if cfg_row:
            logger.info(
                "[AI_CS] 账号归属用户未配置 AI 客服，已 fallback 到租户级配置 tenantId=%d accountId=%d userId=%d",
                tenant_id, account_id, user_id,
            )
    if not cfg_row:
        logger.debug("[AI_CS] 未配置 AI 客服 tenantId=%d userId=%d", tenant_id, user_id)
        return None

    try:
        cfg = json.loads(cfg_row["config_json"]) if cfg_row["config_json"] else {}
    except Exception:
        logger.warning("[AI_CS] ai-customer-service 配置 JSON 解析失败 tenantId=%d userId=%d", tenant_id, user_id)
        return None

    # 3) 校验启用状态
    enabled = bool(cfg.get("enabled"))
    if not enabled:
        logger.debug("[AI_CS] AI 客服未启用 tenantId=%d userId=%d", tenant_id, user_id)
        return None

    payload = payload or {}
    goods_id = _text(payload.get("goodsId") or payload.get("itemId") or payload.get("xyGoodsId")).strip()
    sid = _text(payload.get("sId") or payload.get("sid") or payload.get("sessionId")).strip()
    buyer_id = _text(payload.get("buyerId") or payload.get("peerUserId") or payload.get("externalBuyerId")).strip()
    goods = await _load_goods_context(db, tenant_id, account_id, goods_id, sid=sid, buyer_id=buyer_id)
    account_scopes = await _load_ai_cs_account_scopes(db, tenant_id)
    product_enabled = _bool_to_smallint(goods.get("auto_reply_enabled")) if goods else None
    if not _compute_ai_cs_effective_enabled(
        global_enabled=enabled,
        account_id=account_id,
        account_scopes=account_scopes,
        product_enabled=product_enabled,
    ):
        logger.debug("[AI_CS] 当前账号/商品作用域未启用 tenantId=%d accountId=%d goodsId=%s", tenant_id, account_id, goods_id)
        return None

    # 4) 校验工作时段
    work_hours_24 = bool(cfg.get("workHours24", True))
    if not work_hours_24:
        work_start = _text(cfg.get("workStart") or "09:00")
        work_end = _text(cfg.get("workEnd") or "22:00")
        now = time.localtime()
        now_minutes = now.tm_hour * 60 + now.tm_min
        def _parse_hhmm(s: str) -> int:
            try:
                h, m = s.split(":")[:2]
                return int(h) * 60 + int(m)
            except Exception:
                return -1
        start_min = _parse_hhmm(work_start)
        end_min = _parse_hhmm(work_end)
        if start_min >= 0 and end_min >= 0 and start_min < end_min:
            if not (start_min <= now_minutes < end_min):
                logger.debug(
                    "[AI_CS] 当前不在工作时段 %s-%s tenantId=%d",
                    work_start, work_end, tenant_id
                )
                return None

    # 5) 拉黑关键词检测：命中则不回复
    block_keywords = _parse_keywords(cfg.get("blacklistKeywords"))
    lowered = content.lower()
    for kw in block_keywords:
        if kw and kw.lower() in lowered:
            logger.info(
                "[AI_CS] 命中黑名单关键词，跳过 AI 回复 tenantId=%d keywordLen=%d",
                tenant_id,
                len(kw),
            )
            return None

    # 6) 每日上限检测
    max_daily = _safe_int(cfg.get("maxDailyReplies"), 0)
    if max_daily > 0:
        today_count = (await db.execute(text("""
            SELECT COUNT(*) FROM auto_reply_log
            WHERE tenant_id=:tenant_id AND account_id=:account_id AND deleted=0
              AND action='auto_send_allowed' AND hit_type='ai_customer_service'
              AND DATE(created_time)=CURRENT_DATE()
        """), {"tenant_id": tenant_id, "account_id": account_id})).scalar() or 0
        if int(today_count) >= max_daily:
            logger.info("[AI_CS] 已达每日上限 %d，跳过 tenantId=%d accountId=%d", max_daily, tenant_id, account_id)
            return None

    # 7) 构造虚拟 rule（走 AI 回复模式）
    user_knowledge_bases = _normalize_ai_cs_entries(
        cfg.get("knowledgeBases"),
        fallback_text=_text(cfg.get("knowledgeBase")),
        prefix="知识库",
        source="user",
    )
    user_chat_rules = _normalize_ai_cs_entries(
        cfg.get("chatRules"),
        prefix="聊天规则",
        source="user",
    )
    default_knowledge_bases = _normalize_ai_cs_entries(
        cfg.get("defaultKnowledgeBases"),
        prefix="默认知识库",
        source="default",
    )
    default_chat_rules = _normalize_ai_cs_entries(
        cfg.get("defaultChatRules"),
        prefix="默认聊天规则",
        source="default",
    )
    # 拉取后台配置的敏感词（复用 polish 场景），用于限制 AI 回复不要出现违规内容
    sensitive_words = await _fetch_ai_cs_sensitive_words()

    # 查询用户启用的 KB 并做 RAG 检索
    learned_kb_hits: list[dict[str, Any]] = []
    user_private_kb_hits: list[dict[str, Any]] = []
    try:
        if content and tenant_id and account_id and user_id:
            # 注意：AsyncResult.mappings() 返回的迭代器只能消费一次，
            # 必须先 .all() 物化为列表再分区，否则第二次迭代会拿到空游标。
            all_bindings = (await db.execute(text(
                "SELECT kb_type, kb_id, enabled FROM ai_cs_user_kb_binding "
                "WHERE tenant_id=:t AND user_id=:u AND deleted=0"
            ), {"t": tenant_id, "u": user_id})).mappings().all()
            learned_ids = [r["kb_id"] for r in all_bindings
                           if r["kb_type"] == "learned" and r["enabled"]]
            user_kb_ids = [r["kb_id"] for r in all_bindings
                           if r["kb_type"] == "user" and r["enabled"]]

            from app.services.rag_service import search_with_filter
            if learned_ids:
                try:
                    learned_kb_hits = await search_with_filter(
                        query=content, kb_ids=learned_ids, top_k=3
                    )
                except Exception as exc:
                    vector_search_kind = _exc_type_name(exc)
                    logger.warning("[AI_CS] vector search failed, fallback to DB search errorType=%s", vector_search_kind)
                    learned_kb_hits = []
                # 向量检索失败或返回空时，回退到 DB 关键词 LIKE 检索
                # 兜底场景：线上未配置 embedding 模型，所有条目 vector_indexed=0
                if not learned_kb_hits:
                    learned_kb_hits = await _fallback_db_search_learned_kb(
                        db, learned_ids, content, top_k=3
                    )
            if user_kb_ids:
                user_kb_rows = await db.execute(text(
                    "SELECT title, content FROM ai_cs_user_kb "
                    "WHERE id IN :ids AND tenant_id=:t AND user_id=:u "
                    "AND deleted=0 AND enabled=1"
                ).bindparams(sqlalchemy.bindparam("ids", expanding=True)),
                {"ids": user_kb_ids, "t": tenant_id, "u": user_id})
                user_private_kb_hits = [
                    {"title": r["title"], "content": r["content"]}
                    for r in user_kb_rows.mappings()
                ]
    except Exception as exc:
        kb_lookup_err = _exc_type_name(exc)
        logger.warning("[AI_CS] kb binding/rag lookup failed errorType=%s", kb_lookup_err)

    system_prompt = _build_ai_cs_system_prompt(
        cfg,
        goods,
        user_knowledge_bases,
        user_chat_rules,
        default_knowledge_bases,
        default_chat_rules,
        sensitive_words=sensitive_words,
        learned_kb_hits=learned_kb_hits,
        user_private_kb_hits=user_private_kb_hits,
    )
    welcome_message = _text(cfg.get("welcomeMessage"))
    handoff_keywords = _text(cfg.get("handoffKeywords"))
    safe_mode_raw = cfg.get("safeMode")
    safe_mode = 1 if safe_mode_raw in (True, "true", "True", 1, "1") else 0
    # 人工干预暂停时长（秒）：pauseOnHumanIntervene=false 时为 0（不暂停），
    # 否则取 pauseDurationSeconds（默认 60，0 或负数视为 60）
    _pause_enabled = cfg.get("pauseOnHumanIntervene") not in (False, "false", "False", 0, "0")
    _pause_secs_cfg = _safe_int(cfg.get("pauseDurationSeconds"), 60)
    pause_duration_seconds_val = (_pause_secs_cfg if _pause_secs_cfg > 0 else 60) if _pause_enabled else 0

    return {
        "id": None,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "account_id": account_id,
        "reply_mode": "ai",
        "reply_content": system_prompt or welcome_message or "您好，我来帮您确认这件商品的信息。",
        "match_type": "ai_customer_service",
        "match_keywords": "",
        "handoff_keywords": handoff_keywords,
        "safe_mode": safe_mode,
        "provider_name": "default",
        "model_name": "default",
        "max_daily_replies": max_daily,
        "price_floor": None,
        "goods_context": goods,
        "knowledge_bases": user_knowledge_bases,
        "default_knowledge_bases": default_knowledge_bases,
        "chat_rules": user_chat_rules,
        "default_chat_rules": default_chat_rules,
        # 人工干预自动暂停时长（秒），用于 AI 回复生成后的二次检查
        # 0 表示不暂停（pauseOnHumanIntervene=false）；正数表示暂停时长
        "pause_duration_seconds": pause_duration_seconds_val,
    }


async def _check_message_filter(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    content: str,
) -> list[str]:
    """检查消息过滤规则，返回命中的过滤类型列表（skip_reply / skip_notify）。

    查询失败时按“不过滤”处理（fail-open 只影响过滤，不影响主链路收发消息），
    避免过滤规则表异常导致买家消息无法接收或自动回复停摆。
    """
    try:
        text_content = _text(content or "")
        if not text_content:
            return []
        rows = (await db.execute(text("""
            SELECT keyword, filter_type
            FROM message_filter
            WHERE tenant_id = :tenant_id
              AND account_id = :account_id
              AND deleted = 0
              AND enabled = 1
            ORDER BY id ASC
        """), {
            "tenant_id": tenant_id,
            "account_id": account_id,
        })).mappings().all()
        lowered = text_content.lower()
        hits: list[str] = []
        for row in rows:
            keyword = _text(row.get("keyword") or "").strip().lower()
            if not keyword:
                continue
            if keyword in lowered:
                filter_type = _text(row.get("filter_type") or "").strip()
                if filter_type and filter_type not in hits:
                    hits.append(filter_type)
        return hits
    except Exception as exc:
        msg_filter_err = _exc_type_name(exc)
        logger.warning(
            "[MESSAGE_FILTER] 查询消息过滤规则失败 tenantId=%d accountId=%d errorType=%s",
            tenant_id, account_id, msg_filter_err,
        )
        return []


async def _match_auto_reply_rule(
    db: AsyncSession,
    tenant_id: int,
    account_id: int,
    content: str,
    goods_id: str = "",
) -> Optional[dict[str, Any]]:
    rows = (await db.execute(text("""
        SELECT * FROM auto_reply_rule
        WHERE tenant_id = :tenant_id
          AND deleted = 0
          AND status = 1
          AND (account_id IS NULL OR account_id = :account_id)
          AND (xy_goods_id IS NULL OR xy_goods_id = '' OR xy_goods_id = :goods_id)
        ORDER BY CASE WHEN account_id = :account_id THEN 0 ELSE 1 END,
                 CASE WHEN xy_goods_id IS NULL OR xy_goods_id = '' THEN 1 ELSE 0 END,
                 COALESCE(priority, 0) DESC, id DESC
    """), {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "goods_id": goods_id or "",
    })).mappings().all()
    lowered = content.lower()
    for r in rows:
        rule = dict(r)
        match_type = (_text(rule.get("match_type")) or "any").lower()
        keywords = _parse_keywords(rule.get("match_keywords") or rule.get("trigger_keywords"))
        # AI 意图模式：直接命中（由 reply_mode 决定走 AI 回复）
        if match_type == "ai":
            return rule
        # 正则模式：每个关键词作为正则，任一匹配即命中
        if match_type == "regex":
            for k in keywords:
                try:
                    if re.search(k, content):
                        return rule
                except re.error:
                    continue
            continue
        # 关键词为空时跳过（避免 any/all 模式误命中所有消息）
        if not keywords:
            continue
        # 全部关键词模式：所有关键词都必须命中
        if match_type == "all":
            if all(k.lower() in lowered for k in keywords):
                return rule
            continue
        # 任意关键词模式（默认）：任一关键词命中即生效
        if match_type in {"any", "keyword", "contains"}:
            if any(k.lower() in lowered for k in keywords):
                return rule
            continue
        # 精确匹配模式
        if match_type == "exact" and any(k == content for k in keywords):
            return rule
    return None


async def update_ws_heartbeat(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    tenant_id = _safe_int(payload.get("tenantId") or payload.get("tenant_id"))
    account_id = _safe_int(payload.get("accountId") or payload.get("account_id"))
    if not tenant_id or not account_id:
        return {"ok": False, "message": "tenantId/accountId 不能为空"}
    latency = _safe_int(payload.get("latency") or payload.get("wsLatencyMs"), 0)
    online = _safe_int(payload.get("onlineStatus"), 1)
    ws_status = _safe_int(payload.get("wsStatus"), 1)
    count = (await db.execute(text("""
        SELECT COUNT(*) FROM xianyu_account_runtime
        WHERE tenant_id = :tenant_id AND account_id = :account_id AND deleted = 0
    """), {"tenant_id": tenant_id, "account_id": account_id})).scalar() or 0
    if count:
        await db.execute(text("""
            UPDATE xianyu_account_runtime
            SET online_status = :online, ws_status = :ws_status, ws_latency_ms = :latency,
                last_heartbeat_time = NOW(), last_online_time = IF(:online = 1, NOW(), last_online_time), updated_time = NOW()
            WHERE tenant_id = :tenant_id AND account_id = :account_id AND deleted = 0
        """), {"tenant_id": tenant_id, "account_id": account_id, "online": online, "ws_status": ws_status, "latency": latency})
    else:
        await db.execute(text("""
            INSERT INTO xianyu_account_runtime(
                tenant_id, account_id, online_status, ws_status, ws_latency_ms,
                cookie_status, last_heartbeat_time, last_online_time, last_sync_time, deleted, created_time, updated_time
            ) VALUES(:tenant_id, :account_id, :online, :ws_status, :latency, 1, NOW(), NOW(), NOW(), 0, NOW(), NOW())
        """), {"tenant_id": tenant_id, "account_id": account_id, "online": online, "ws_status": ws_status, "latency": latency})
    await db.commit()
    return {"ok": True, "message": "心跳已更新", "accountId": account_id, "wsStatus": ws_status}


async def local_business_search(db: AsyncSession, tenant_id: Optional[int], keyword: str, limit: int = 20) -> list[dict[str, Any]]:
    q = f"%{keyword.strip()}%"
    if not keyword.strip():
        return []
    params: dict[str, Any] = {"q": q, "limit": min(max(limit, 1), 50)}
    tenant_sql = ""
    if tenant_id is not None:
        tenant_sql = " AND g.tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id
    rows = (await db.execute(text(f"""
        SELECT g.id, g.external_goods_id, g.title, g.price, g.stock, g.image_url, g.status, g.created_time,
               a.nickname AS account_name
        FROM xianyu_goods g
        LEFT JOIN xianyu_account a ON a.id = g.account_id
        WHERE g.deleted = 0 {tenant_sql}
          AND (g.title LIKE :q OR g.description LIKE :q OR g.category LIKE :q)
        ORDER BY g.updated_time DESC, g.id DESC
        LIMIT :limit
    """), params)).mappings().all()
    return [{
        "id": r.get("id"),
        "goodsId": r.get("external_goods_id"),
        "title": r.get("title"),
        "price": r.get("price"),
        "stock": r.get("stock"),
        "imageUrl": r.get("image_url"),
        "status": r.get("status"),
        "accountName": r.get("account_name"),
        "source": "local_goods",
        "createdTime": str(r.get("created_time")) if r.get("created_time") else None,
    } for r in rows]

# ---- Phase12 工作流执行器 ----

async def insert_timeline(
    db: AsyncSession,
    tenant_id: int,
    execution_id: Optional[int],
    workflow_id: Optional[int],
    node_key: str,
    event_level: str,
    event_type: str,
    title: str,
    content: str = "",
    payload: Optional[dict] = None,
) -> None:
    """插入工作流时间线事件"""
    try:
        is_failure = _text(event_level).strip().upper() == "ERROR"
        safe_content = _sanitize_runtime_value(content, failure_context=is_failure)
        safe_payload = _sanitize_runtime_value(payload, failure_context=is_failure) if payload else None
        await db.execute(text("""
            INSERT INTO workflow_timeline(tenant_id, execution_id, workflow_id, node_key,
                event_level, event_type, title, content, payload_json, created_time, deleted)
            VALUES(:tenant_id, :execution_id, :workflow_id, :node_key,
                :event_level, :event_type, :title, :content, :payload_json, NOW(), 0)
        """), {
            "tenant_id": tenant_id,
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "node_key": node_key,
            "event_level": event_level,
            "event_type": event_type,
            "title": title,
            "content": safe_content,
            "payload_json": json.dumps(safe_payload, ensure_ascii=False) if safe_payload else None,
        })
    except Exception as exc:
        _log_runtime_failure("persist_workflow_timeline", exc)


async def update_execution_progress(
    db: AsyncSession,
    tenant_id: int,
    execution_id: Optional[int],
    node_key: str = "",
    progress: int = -1,
    node_total: Optional[int] = None,
    node_success: Optional[int] = None,
) -> None:
    """
    更新 workflow_execution 的进度字段，让前端列表/详情能看到实时进度。
    - progress: 0-100，-1 表示不更新
    - node_total/node_success: 节点完成度，None 表示不更新
    - node_key: 当前执行节点 key
    只更新 status='running' 的记录，避免覆盖终态。
    """
    if not execution_id:
        return
    try:
        sets = []
        params: dict = {"eid": execution_id, "tid": tenant_id}
        if node_key:
            sets.append("current_node_key=:nk")
            params["nk"] = node_key
        if progress >= 0:
            sets.append("progress=:p")
            params["p"] = max(0, min(99, progress))
        if node_total is not None:
            sets.append("node_total=:nt")
            params["nt"] = node_total
        if node_success is not None:
            sets.append("node_success=:ns")
            params["ns"] = node_success
        if not sets:
            return
        sets.append("updated_time=NOW()")
        await db.execute(text(
            f"UPDATE workflow_execution SET {', '.join(sets)} WHERE id=:eid AND tenant_id=:tid AND status='running'"
        ), params)
    except Exception as exc:
        _log_runtime_failure("update_workflow_progress", exc)


async def save_state_variable(
    db: AsyncSession,
    tenant_id: int,
    execution_id: Optional[int],
    node_key: str,
    var_name: str,
    var_value: Any,
    var_type: str = "string",
) -> None:
    """保存工作流状态变量"""
    try:
        safe_value = _sanitize_runtime_value(
            var_value,
            failure_context=_runtime_key(var_name) in _RUNTIME_ERROR_KEYS,
        )
        # 先删除同名旧变量
        await db.execute(text("""
            UPDATE workflow_state_variable SET deleted=1, updated_time=NOW()
            WHERE tenant_id=:tenant_id AND execution_id=:execution_id
              AND var_name=:var_name AND deleted=0
        """), {
            "tenant_id": tenant_id,
            "execution_id": execution_id,
            "var_name": var_name,
        })
        # 插入新变量
        await db.execute(text("""
            INSERT INTO workflow_state_variable(tenant_id, execution_id, node_key, var_name, var_value, var_type, created_time, updated_time, deleted)
            VALUES(:tenant_id, :execution_id, :node_key, :var_name, :var_value, :var_type, NOW(), NOW(), 0)
        """), {
            "tenant_id": tenant_id,
            "execution_id": execution_id,
            "node_key": node_key,
            "var_name": var_name,
            "var_value": json.dumps(safe_value, ensure_ascii=False) if not isinstance(safe_value, str) else safe_value,
            "var_type": var_type,
        })
    except Exception as exc:
        _log_runtime_failure("persist_workflow_state_variable", exc)


async def _record_item_timing(
    db: AsyncSession,
    tenant_id: int,
    execution_id: Optional[int],
    workflow_id: Optional[int],
    item_index: int,
    source_item_id: str,
    source_title: str,
    polish_ms: int = 0,
    image_generate_ms: int = 0,
    publish_ms: int = 0,
    total_ms: int = 0,
) -> None:
    try:
        await db.execute(text("""
            INSERT INTO workflow_item_timing(tenant_id, execution_id, workflow_id, item_index,
                source_item_id, source_title, polish_ms, image_generate_ms, publish_ms, total_ms, created_time, deleted)
            VALUES(:t, :e, :w, :idx, :si, :st, :pm, :im, :pm2, :tm, NOW(), 0)
        """), {
            "t": tenant_id, "e": execution_id, "w": workflow_id, "idx": item_index,
            "si": source_item_id or "", "st": source_title[:200] if source_title else "",
            "pm": polish_ms, "im": image_generate_ms, "pm2": publish_ms, "tm": total_ms,
        })
        await db.commit()
    except Exception as exc:
        _log_runtime_failure("persist_workflow_item_timing", exc)


async def save_checkpoint(
    db: AsyncSession,
    tenant_id: int,
    execution_id: Optional[int],
    workflow_id: Optional[int],
    node_key: str,
    state_snapshot: dict,
    context_json: Optional[dict] = None,
    retry_count: int = 0,
    max_retries: int = 3,
) -> None:
    """保存工作流检查点"""
    try:
        safe_state_snapshot = _sanitize_runtime_value(state_snapshot)
        safe_context_json = _sanitize_runtime_value(context_json) if context_json else None
        # 标记旧检查点为历史
        await db.execute(text("""
            UPDATE workflow_checkpoint SET status='history', updated_time=NOW()
            WHERE tenant_id=:tenant_id AND execution_id=:execution_id
              AND node_key=:node_key AND status='active' AND deleted=0
        """), {
            "tenant_id": tenant_id,
            "execution_id": execution_id,
            "node_key": node_key,
        })
        await db.execute(text("""
            INSERT INTO workflow_checkpoint(tenant_id, execution_id, workflow_id, node_key,
                checkpoint_type, state_snapshot, context_json, retry_count, max_retries, status, created_time, updated_time, deleted)
            VALUES(:tenant_id, :execution_id, :workflow_id, :node_key,
                'snapshot', :state_snapshot, :context_json, :retry_count, :max_retries, 'active', NOW(), NOW(), 0)
        """), {
            "tenant_id": tenant_id,
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "node_key": node_key,
            "state_snapshot": json.dumps(safe_state_snapshot, ensure_ascii=False),
            "context_json": json.dumps(safe_context_json, ensure_ascii=False) if safe_context_json else None,
            "retry_count": retry_count,
            "max_retries": max_retries,
        })
    except Exception as exc:
        _log_runtime_failure("persist_workflow_checkpoint", exc)


def _node_key(node: dict[str, Any]) -> str:
    return _text(node.get("nodeKey") or node.get("id") or node.get("key"))


def _node_type(node: dict[str, Any]) -> str:
    return _text(node.get("nodeType") or node.get("type") or "action").lower()


def _node_config(node: dict[str, Any]) -> dict[str, Any]:
    raw = node.get("config") or node.get("params") or {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            return {"invalidConfig": True}
    return {}


def _topological_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Optional[str]]:
    by_key = {_node_key(n): n for n in nodes if _node_key(n)}
    indegree = {k: 0 for k in by_key}
    graph: dict[str, list[str]] = {k: [] for k in by_key}
    for e in edges:
        s = _text(e.get("sourceNodeKey") or e.get("source"))
        t = _text(e.get("targetNodeKey") or e.get("target"))
        if s not in by_key or t not in by_key:
            return [], "连线引用了不存在的节点"
        graph[s].append(t)
        indegree[t] += 1
    queue = [k for k, v in indegree.items() if v == 0]
    ordered = []
    while queue:
        k = queue.pop(0)
        ordered.append(by_key[k])
        for nxt in graph.get(k, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if len(ordered) != len(by_key):
        return [], "工作流存在循环依赖"
    return ordered, None


def _build_workflow_state(context: dict[str, Any]) -> dict[str, Any]:
    """从上下文中提取结构化的工作流状态（匹配 test script 的 state 结构）"""
    input_data = context.get("input", {})
    state = {
        "keywords": input_data.get("keywords", []),
        "target_count": _safe_int(input_data.get("target_count") or input_data.get("targetCount"), 5),
        "current_count": 0,
        "selected_products": [],
        "polished_products": [],
        "generated_images": [],
        "publish_result": [],
        "logs": [],
        "retry_count": 0,
        # 商品分页增量获取相关状态
        "all_fetched_items": [],
        "product_fetch_page": 1,
        "selected_keywords": [],
    }
    # 从已有节点输出中恢复状态
    for key, val in context.items():
        if isinstance(val, dict):
            if val.get("items") and key not in ("input",):
                state["selected_products"] = val.get("items", [])
                state["current_count"] = len(state["selected_products"])
            if val.get("polished"):
                state["polished_products"] = val.get("polished", [])
            if val.get("images"):
                state["generated_images"] = val.get("images", [])
            if val.get("publishResults"):
                state["publish_result"] = val.get("publishResults", [])
    return state


async def continue_workflow_execution(db: AsyncSession, execution_id: int) -> dict[str, Any]:
    """
    继续执行已失败的工作流。复用原 execution_id，跳过已成功的节点，从失败节点开始继续执行。
    - 读取 workflow_execution 的 input_json（含 workflow 定义）
    - 从 workflow_state_variable 表加载已保存的 state
    - 从 workflow_timeline 找到已成功的节点（node_success 事件）
    - 找到失败节点（最后一条 node_failed 事件）
    - 调用 execute_workflow，传入 continueExecutionId + skipNodeKeys + initialState
    """
    # 1) 读取 workflow_execution 主记录
    rows = (await db.execute(text("""
        SELECT id, tenant_id, workflow_id, status, current_node_key, input_json, output_json
        FROM workflow_execution WHERE id=:eid LIMIT 1
    """), {"eid": execution_id})).mappings().all()
    if not rows:
        return {"status": "failed", "errorCode": "WORKFLOW_EXECUTION_NOT_FOUND", "errorMessage": "工作流执行记录不存在"}
    row = dict(rows[0])
    try:
        tenant_id = int(row.get("tenant_id"))
    except (TypeError, ValueError):
        return {"status": "failed", "errorCode": "WORKFLOW_TENANT_INVALID", "errorMessage": "执行记录缺少有效的租户上下文"}
    if tenant_id <= 0:
        return {"status": "failed", "errorCode": "WORKFLOW_TENANT_INVALID", "errorMessage": "执行记录缺少有效的租户上下文"}
    workflow_id = row.get("workflow_id")
    cur_status = _text(row.get("status") or "")
    if cur_status == "running":
        return {"status": "failed", "errorCode": "WORKFLOW_ALREADY_RUNNING", "errorMessage": "工作流正在运行，无需重复继续"}

    # 2) 解析 input_json 拿到 workflow 定义
    input_json_str = _text(row.get("input_json") or "")
    try:
        input_payload = json.loads(input_json_str) if input_json_str else {}
    except Exception:
        return {"status": "failed", "errorCode": "WORKFLOW_INPUT_INVALID", "errorMessage": "工作流执行参数已损坏，无法继续"}

    workflow = input_payload.get("workflow") or {}
    nodes = workflow.get("nodes") or []
    if not nodes:
        # input_json 里没有 workflow 定义，需要从 workflow_node + workflow_edge 表加载
        # （workflow_definition 表只有 config_json/canvas_json，nodes/edges 存在单独的表里）
        wf_rows = (await db.execute(text("""
            SELECT id, name, description, trigger_type, status, config_json, canvas_json
            FROM workflow_definition WHERE id=:wid LIMIT 1
        """), {"wid": workflow_id})).mappings().all()
        if not wf_rows:
            return {"status": "failed", "errorCode": "WORKFLOW_DEFINITION_NOT_FOUND", "errorMessage": "工作流定义不存在"}
        wf_row = dict(wf_rows[0])
        # 读 workflow_node 表（按 sort_order 排序）
        node_rows = (await db.execute(text("""
            SELECT node_key, node_name, node_type, position_x, position_y, config_json, sort_order
            FROM workflow_node
            WHERE workflow_id=:wid AND deleted=0
            ORDER BY sort_order ASC, id ASC
        """), {"wid": workflow_id})).mappings().all()
        # 读 workflow_edge 表（实际字段名是 condition_expr，不是 condition）
        edge_rows = (await db.execute(text("""
            SELECT source_node_key, target_node_key, condition_expr
            FROM workflow_edge
            WHERE workflow_id=:wid AND deleted=0
            ORDER BY id ASC
        """), {"wid": workflow_id})).mappings().all()
        nodes = []
        for nr in node_rows:
            nr = dict(nr)
            nk = _text(nr.get("node_key") or "")
            if not nk:
                continue
            try:
                cfg = json.loads(_text(nr.get("config_json") or "{}"))
            except Exception:
                cfg = {}
            nodes.append({
                "id": nk,
                "nodeKey": nk,
                "name": _text(nr.get("node_name") or ""),
                "nodeName": _text(nr.get("node_name") or ""),
                "type": _text(nr.get("node_type") or ""),
                "nodeType": _text(nr.get("node_type") or ""),
                "x": float(nr.get("position_x") or 0),
                "y": float(nr.get("position_y") or 0),
                "config": cfg,
            })
        edges = []
        for er in edge_rows:
            er = dict(er)
            edges.append({
                "source": _text(er.get("source_node_key") or ""),
                "target": _text(er.get("target_node_key") or ""),
                "sourceNodeKey": _text(er.get("source_node_key") or ""),
                "targetNodeKey": _text(er.get("target_node_key") or ""),
                "condition": _text(er.get("condition_expr") or ""),
            })
        # 尝试从 canvas_json 读 zoom 等元数据
        try:
            canvas = json.loads(_text(wf_row.get("canvas_json") or "{}"))
        except Exception:
            canvas = {}
        try:
            config = json.loads(_text(wf_row.get("config_json") or "{}"))
        except Exception:
            config = {}
        workflow = {
            "id": workflow_id,
            "name": _text(wf_row.get("name") or f"工作流#{workflow_id}"),
            "description": _text(wf_row.get("description") or ""),
            "triggerType": _text(wf_row.get("trigger_type") or "manual"),
            "status": _text(wf_row.get("status") or "draft"),
            "config": config,
            "canvas": canvas,
            "nodes": nodes,
            "edges": edges,
        }
        if not nodes:
            return {"status": "failed", "errorCode": "WORKFLOW_EMPTY", "errorMessage": "工作流未配置可执行节点"}

    # 3) 从 workflow_timeline 找到已成功的节点
    tl_rows = (await db.execute(text("""
        SELECT node_key, event_type FROM workflow_timeline
        WHERE execution_id=:eid AND tenant_id=:tid AND deleted=0
        AND event_type IN ('node_success', 'node_failed', 'node_partial')
        ORDER BY id ASC
    """), {"eid": execution_id, "tid": tenant_id})).mappings().all()

    success_keys: set[str] = set()
    failed_key = ""
    for r in tl_rows:
        r = dict(r)
        nk = _text(r.get("node_key") or "")
        et = _text(r.get("event_type") or "")
        if not nk or nk == "system":
            continue
        if et == "node_success":
            success_keys.add(nk)
        elif et == "node_failed":
            # 失败节点：从该节点开始重新执行（不加入 skip）
            failed_key = nk
        elif et == "node_partial":
            # partial_success 节点：继续模式下需要重新执行（发布节点等）
            pass

    # 4) 从 workflow_state_variable 表加载 state
    sv_rows = (await db.execute(text("""
        SELECT var_name, var_value, var_type FROM workflow_state_variable
        WHERE execution_id=:eid AND tenant_id=:tid AND deleted=0
        ORDER BY id DESC
    """), {"eid": execution_id, "tid": tenant_id})).mappings().all()
    initial_state: dict[str, Any] = {}
    seen_names: set[str] = set()
    for r in sv_rows:
        r = dict(r)
        vn = _text(r.get("var_name") or "")
        if not vn or vn in seen_names:
            continue
        seen_names.add(vn)
        vv = _text(r.get("var_value") or "")
        vt = _text(r.get("var_type") or "string")
        if vt == "json":
            try:
                initial_state[vn] = json.loads(vv) if vv else None
            except Exception:
                initial_state[vn] = vv
        elif vt == "number":
            try:
                initial_state[vn] = float(vv) if vv else 0
            except Exception:
                initial_state[vn] = 0
        else:
            initial_state[vn] = vv

    # 兼容 publish_results 字段（同时保存了 publish_result 和 publish_results）
    if "publish_results" not in initial_state and "publish_result" in initial_state:
        initial_state["publish_results"] = initial_state["publish_result"]
    initial_state = _sanitize_runtime_value(initial_state)

    # 5) 更新 execution 状态为 running，准备继续执行
    await db.execute(text("""
        UPDATE workflow_execution SET status='running', progress=0,
            error_message='', finished_time=NULL, updated_time=NOW()
        WHERE id=:eid AND tenant_id=:tid
    """), {"eid": execution_id, "tid": tenant_id})
    await db.commit()

    # 6) 构造继续执行的 payload
    continue_payload = dict(input_payload)  # 保留原 payload（含 addressPayload 等）
    # ★ 关键修复：原 input_json 通常不含 tenantId，必须显式注入，否则 execute_workflow
    #   内 `_safe_int(payload.get("tenantId"))` 会得到 0，导致 _resolve_account_cookie
    #   查询 xianyu_account_auth WHERE tenant_id=0 返回空，所有发布都会报"账号Cookie已失效"。
    continue_payload["tenantId"] = tenant_id
    continue_payload["executionId"] = execution_id
    continue_payload["workflowId"] = workflow_id
    continue_payload["workflow"] = workflow
    continue_payload["continueExecutionId"] = execution_id
    continue_payload["skipNodeKeys"] = list(success_keys)
    continue_payload["initialState"] = initial_state
    continue_payload["input"] = input_payload.get("input") or {}

    logger.info("[CONTINUE] 继续执行 execution=%s skip=%s failed_node=%s state_keys=%s",
                execution_id, list(success_keys), failed_key, list(initial_state.keys()))

    # 7) 调用 execute_workflow
    return await execute_workflow(db, continue_payload)


async def execute_workflow(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """
    执行工作流节点。Java 负责保存定义和执行记录；Python 负责执行节点逻辑并返回结果。
    
    改进（匹配 workflow_test_script.md）：
    1. 时间线记录 - 每个节点执行前后写入 workflow_timeline
    2. 状态管理 - 结构化状态字典在节点间传递
    3. 重试路由 - ProductFilter 支持数量不足时 RETRY → ProductFetch
    4. 产物持久化 - 写入 workflow_artifact 表
    5. 检查点 - 每个节点执行后保存 checkpoint
    """
    tenant_id = _safe_int(payload.get("tenantId"))
    workflow = payload.get("workflow") or {}
    nodes = workflow.get("nodes") or []
    edges = workflow.get("edges") or []
    execution_id = payload.get("executionId")
    workflow_id = payload.get("workflowId") or workflow.get("id")
    workflow_name = _text(workflow.get("name") or f"工作流#{workflow_id}")

    # ★ 继续执行模式：复用原 execution_id，跳过已成功节点，使用 initialState
    continue_mode = bool(payload.get("continueExecutionId"))
    skip_node_keys: set[str] = set(payload.get("skipNodeKeys") or [])
    initial_state: Optional[dict] = payload.get("initialState")

    ordered, err = _topological_nodes(nodes, edges)
    if err:
        await insert_timeline(db, tenant_id, execution_id, workflow_id, "system", "ERROR", "system", "拓扑排序失败", err)
        await db.commit()
        return {"status": "failed", "progress": 100, "errorCode": "WORKFLOW_GRAPH_INVALID", "errorMessage": "工作流连线或依赖配置无效", "nodeResults": []}

    # 初始化上下文
    context: dict[str, Any] = {"input": payload.get("input") or {}, "artifacts": []}
    # 将 workflow_id/execution_id/workflow_name 注入 context，供 PUBLISH 等节点写去重表与草稿箱使用
    context["__workflow_id__"] = workflow_id
    context["__execution_id__"] = execution_id
    context["__workflow_name__"] = workflow_name
    # ★ 注入发布模式：publish（默认，生图后直接发布） | draft_only（生图后仅存草稿不发布）
    #   _publish_single_item 检测 draft_only 时跳过实际发布，仅将草稿以 status=draft 写入 workflow_goods_draft 表
    _publish_mode_raw = _text(payload.get("publishMode") or "publish").lower()
    context["__publish_mode__"] = "draft_only" if _publish_mode_raw == "draft_only" else "publish"
    # ★ 注入前端预检传入的 addressPayload，供 IMAGE_GENERATE 节点直接使用
    # 注意：Java WorkflowService.execute 把前端整个 input 作为 payload.input 传递，
    # 因此 addressPayload 实际位于 payload.input.addressPayload；同时兼容历史路径
    # payload.addressPayload（继续执行场景或旧版前端直接平铺）。
    _input_obj = payload.get("input") if isinstance(payload.get("input"), dict) else {}
    _addr_payload = payload.get("addressPayload") or _input_obj.get("addressPayload")
    if _addr_payload:
        context["__address_payload__"] = _addr_payload
    # ★ 注入继续执行模式标记，供 IMAGE_GENERATE 节点检测以复用已生成的图
    if continue_mode:
        context["__continue_mode__"] = True
    node_results: list[dict[str, Any]] = []

    # ★ 继续执行模式：在 timeline 记录一条"恢复执行"事件
    if continue_mode:
        skipped_list = list(skip_node_keys)
        await insert_timeline(db, tenant_id, execution_id, workflow_id, "system", "INFO", "workflow_resumed",
                              f"工作流恢复执行: {workflow_name}",
                              f"从失败节点继续，跳过已成功的 {len(skipped_list)} 个节点",
                              {"skippedNodeKeys": skipped_list, "continueMode": True})
    else:
        # 记录工作流开始
        await insert_timeline(db, tenant_id, execution_id, workflow_id, "system", "INFO", "workflow_start",
                              f"工作流触发: {workflow_name}",
                              f"共 {len(ordered)} 个节点", {"nodeCount": len(ordered), "workflowName": workflow_name})

    # 构建初始状态
    if initial_state and isinstance(initial_state, dict):
        # ★ 继续执行：使用上一次保存的 state
        state = initial_state
    else:
        state = _build_workflow_state(context)
    # 仅在非继续模式下重新保存初始 state（继续模式下 state 已存在于 state_variable 表）
    if not continue_mode:
        await save_state_variable(db, tenant_id, execution_id, "system", "workflow_state", state, "json")
        await save_state_variable(db, tenant_id, execution_id, "system", "keywords", state["keywords"], "json")
        await save_state_variable(db, tenant_id, execution_id, "system", "target_count", state["target_count"], "number")

    # 执行节点 - 支持重试路由
    max_global_retries = 5
    global_retry = 0

    idx = 0
    while idx < len(ordered):
        node = ordered[idx]
        key = _node_key(node)
        name = _text(node.get("nodeName") or node.get("name") or key)
        typ = _node_type(node)
        config = _node_config(node)

        # ★ 继续执行模式：跳过已成功的节点
        if key in skip_node_keys:
            await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "INFO", "node_skipped",
                                  f"跳过已成功节点: {name}",
                                  f"继续执行模式：复用上次的执行结果", {"skipped": True})
            idx += 1
            continue

        started = __import__('time').perf_counter()
        status = "success"
        output: dict[str, Any] = {}
        error_message = ""
        error_code = ""

        # 保存检查点
        await save_checkpoint(db, tenant_id, execution_id, workflow_id, key, state, context, global_retry, max_global_retries)

        # 记录节点开始
        await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "INFO", "node_start",
                              f"开始执行节点: {name}", f"类型: {typ}", {"config": config})
        # ★ 更新执行进度：当前节点 + 进度（按节点序号等分摊，留 1% 给节点内部细化）
        await update_execution_progress(
            db, tenant_id, execution_id, node_key=key,
            progress=int(idx * 100 / max(len(ordered), 1)),
            node_total=len(ordered), node_success=idx,
        )

        try:
            output = _normalize_workflow_node_output(
                await _execute_workflow_node(db, tenant_id, typ, config, context, state)
            )
            context[key] = output

            # 更新状态：如果节点返回了结构化数据，合并到 state
            if output.get("items") is not None:
                state["selected_products"] = output["items"]
                state["current_count"] = len(output["items"])
                await save_state_variable(db, tenant_id, execution_id, key, "selected_products", output["items"], "json")
                await save_state_variable(db, tenant_id, execution_id, key, "current_count", state["current_count"], "number")
                # 商品获取节点使用的分页增量状态
                if "all_fetched_items" in state:
                    await save_state_variable(db, tenant_id, execution_id, key, "all_fetched_items", state["all_fetched_items"], "json")
                if "product_fetch_page" in state:
                    await save_state_variable(db, tenant_id, execution_id, key, "product_fetch_page", state["product_fetch_page"], "number")
                if "selected_keywords" in state:
                    await save_state_variable(db, tenant_id, execution_id, key, "selected_keywords", state["selected_keywords"], "json")
                if "target_count" in state:
                    await save_state_variable(db, tenant_id, execution_id, key, "target_count", state["target_count"], "number")

            if output.get("polished") is not None:
                state["polished_products"] = output["polished"]
                await save_state_variable(db, tenant_id, execution_id, key, "polished_products", output["polished"], "json")

            if output.get("images") is not None:
                state["generated_images"] = output["images"]
                await save_state_variable(db, tenant_id, execution_id, key, "generated_images", output["images"], "json")

            if output.get("publishResults") is not None:
                state["publish_result"] = output["publishResults"]
                state["publish_results"] = output["publishResults"]
                await save_state_variable(db, tenant_id, execution_id, key, "publish_result", output["publishResults"], "json")
                await save_state_variable(db, tenant_id, execution_id, key, "publish_results", output["publishResults"], "json")

            # 触发器节点：保存 selectedAccountId 和 executeCount 到工作流状态
            if output.get("selectedAccountId") is not None:
                state["selected_account_id"] = output["selectedAccountId"]
                await save_state_variable(db, tenant_id, execution_id, key, "selected_account_id", output["selectedAccountId"], "number")
            if output.get("selectedAccountIds") is not None:
                state["selected_account_ids"] = output["selectedAccountIds"]
                await save_state_variable(db, tenant_id, execution_id, key, "selected_account_ids", output["selectedAccountIds"], "json")
            if output.get("executeCount") is not None:
                state["execute_count"] = output["executeCount"]
                await save_state_variable(db, tenant_id, execution_id, key, "execute_count", output["executeCount"], "number")

            # 记录产物
            if output.get("artifact"):
                artifact_entry = _sanitize_runtime_value({
                    "nodeKey": key,
                    "artifactType": output.get("artifactType", "json"),
                    "title": output.get("artifactTitle") or name,
                    "content": output.get("artifact"),
                    "fileUrl": output.get("fileUrl"),
                }, failure_context=output.get("ok") is False, default_code="WORKFLOW_NODE_FAILED")
                context.setdefault("artifacts", []).append(artifact_entry)
                # 持久化产物到 DB
                try:
                    await db.execute(text("""
                        INSERT INTO workflow_artifact(tenant_id, execution_id, node_key, artifact_type, title, content_json, file_url, created_time, deleted)
                        VALUES(:tenant_id, :execution_id, :node_key, :artifact_type, :title, :content_json, :file_url, NOW(), 0)
                    """), {
                        "tenant_id": tenant_id,
                        "execution_id": execution_id,
                        "node_key": key,
                        "artifact_type": artifact_entry["artifactType"],
                        "title": artifact_entry["title"],
                        "content_json": json.dumps(artifact_entry["content"], ensure_ascii=False),
                        "file_url": artifact_entry.get("fileUrl") or "",
                    })
                except Exception as exc:
                    _log_runtime_failure("persist_workflow_artifact", exc)

            # 处理重试路由（如 ProductFilter 返回 RETRY）
            route = _text(output.get("route") or "SUCCESS").upper()
            if route == "RETRY" and global_retry < max_global_retries:
                global_retry += 1
                state["retry_count"] = global_retry
                await save_state_variable(db, tenant_id, execution_id, key, "retry_count", global_retry, "number")
                # 记录重试事件
                await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "WARN", "node_retry",
                                      f"节点重试({global_retry}/{max_global_retries}): {name}",
                                      output.get("message") or "数量不足，重新获取商品",
                                      {"retryCount": global_retry, "maxRetries": max_global_retries})
                # 回退到上一个商品获取节点
                fallback_idx = idx - 1
                while fallback_idx >= 0:
                    prev_node = ordered[fallback_idx]
                    prev_type = _node_type(prev_node)
                    if prev_type in {"goods_search", "product_fetch", "商品获取", "PRODUCT_FETCH"}:
                        idx = fallback_idx  # 回到上一个 fetch 节点重新执行
                        break
                    fallback_idx -= 1
                if fallback_idx < 0:
                    # 没找到前面的 fetch 节点，终止工作流
                    status = "failed"
                    error_message = "重试失败：未找到上游商品获取节点"
                    await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "ERROR", "node_retry_failed",
                                          error_message, error_message, {})
                    await db.commit()
                    return {
                        "status": "failed", "progress": 100, "errorCode": "WORKFLOW_RETRY_SOURCE_MISSING", "errorMessage": error_message,
                        "nodeResults": node_results, "artifacts": context.get("artifacts", []), "timeline": [],
                    }
                continue  # 重新执行当前 idx（回退后的节点）

            # 重试次数用尽，终止工作流
            if route == "RETRY" and global_retry >= max_global_retries:
                status = "failed"
                error_message = "商品数量未达到目标，请调整关键词或筛选条件"
                await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "ERROR", "workflow_terminated",
                                      error_message, error_message, {"retryCount": global_retry})
                await db.commit()
                return {
                    "status": "failed", "progress": 100, "errorCode": "PRODUCT_TARGET_UNMET", "errorMessage": error_message,
                    "nodeResults": node_results, "artifacts": context.get("artifacts", []), "timeline": [],
                }

            # ★ 注意：node_success 事件和进度更新必须延后到 ok=False 检查之后，
            #   否则失败节点会被标记为成功，导致 continue_workflow_execution 跳过该节点。

        except BaseException as exc:
            # 捕获 BaseException（含 asyncio.CancelledError），避免外部连接取消导致已发布商品记录丢失
            is_cancelled = isinstance(exc, asyncio.CancelledError)
            status = "failed"
            error_code, error_message = _runtime_failure_details(
                exc,
                operation="execute_workflow_node",
                default_code="WORKFLOW_NODE_RUNTIME_ERROR",
                default_message="节点执行异常，请稍后重试",
            )
            await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "ERROR", "node_failed",
                                  f"节点执行失败: {name}", error_message,
                                  {"errorCode": error_code, "message": error_message, "cancelled": is_cancelled})

        # 节点返回 ok=False（如 IMAGE_GENERATE 全部生图失败、PUBLISH 全部发布失败）的处理
        if status == "success" and output and output.get("ok") is False:
            error_code = _text(output.get("errorCode") or "WORKFLOW_NODE_FAILED")
            node_err = _text(output.get("errorMessage") or output.get("message") or "节点返回失败")
            # ★ 任何节点：若已产出部分结果（partial=True，如已生成部分图片/已发布部分商品），
            #   标记为 partial_success，不终止工作流，重试时会重新执行该节点以复用已产出结果。
            if output.get("partial"):
                status = "partial_success"
                error_message = node_err
                await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "WARN", "node_partial",
                                      f"节点部分成功: {name}",
                                      f"{node_err}（已产出的结果已保存，重试时将复用）",
                                      {"successCount": output.get("successCount", 0), "failedCount": output.get("failedCount", 0),
                                       "errorCode": error_code})
                # partial_success 不进入 failed 终止分支，继续下一个节点
            else:
                # 其他节点 ok=False（如生图全失败）：终止工作流
                status = "failed"
                error_message = node_err
                await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "ERROR", "node_failed",
                                      f"节点执行失败(返回失败): {name}", error_message,
                                      {"errorCode": error_code, "message": error_message})

        # ★ 仅在节点真正成功时记录 node_success 事件并更新完成节点数。
        #   partial_success 节点不记录 node_success（只记录了 node_partial），
        #   这样 continue_workflow_execution 不会将其加入 skipNodeKeys，重试时会重新执行以复用已产出结果。
        if status == "success":
            await insert_timeline(db, tenant_id, execution_id, workflow_id, key, "INFO", "node_success",
                                  f"节点执行成功: {name}",
                                  f"耗时: {int((__import__('time').perf_counter() - started) * 1000)}ms",
                                  {"output": output})
            await update_execution_progress(
                db, tenant_id, execution_id,
                progress=int((idx + 1) * 100 / max(len(ordered), 1)),
                node_success=idx + 1,
            )
        elif status == "partial_success":
            # partial_success 仅更新进度条，不更新 node_success 计数（避免被 continue 跳过）
            await update_execution_progress(
                db, tenant_id, execution_id,
                progress=int((idx + 1) * 100 / max(len(ordered), 1)),
            )

        duration = int((__import__('time').perf_counter() - started) * 1000)
        node_results.append(_sanitize_runtime_value({
            "nodeKey": key,
            "nodeName": name,
            "nodeType": typ,
            "status": status,
            "input": config,
            "output": output,
            "errorCode": error_code,
            "errorMessage": error_message,
            "durationMs": duration,
        }, failure_context=status == "failed", default_code=error_code or "WORKFLOW_NODE_FAILED"))

        if status == "failed":
            await insert_timeline(db, tenant_id, execution_id, workflow_id, "system", "ERROR", "workflow_failed",
                                  f"工作流执行失败: {workflow_name}", error_message,
                                  {"nodeResults": node_results})
            await db.commit()
            return {
                "status": "failed",
                "progress": 100,
                "errorCode": error_code or "WORKFLOW_NODE_FAILED",
                "errorMessage": error_message,
                "nodeResults": node_results,
                "artifacts": context.get("artifacts", []),
                "timeline": [],
            }

        # ★ 每个节点成功后立即提交，让前端通过轮询能看到实时进度（timeline + state variables + artifacts）
        #   原先仅在失败/完成时 commit，导致执行中的节点进度对前端不可见（timeline 停在第一个节点）
        try:
            await db.commit()
        except Exception as exc:
            _log_runtime_failure("commit_workflow_node", exc)

        idx += 1

    # 工作流执行完成
    # 若任一节点为 partial_success，整体状态记为 partial_success（区别于全成功 success 与全失败 failed）
    has_partial = any(nr.get("status") == "partial_success" for nr in node_results)
    final_status = "partial_success" if has_partial else "success"
    final_msg = "工作流执行完成（部分成功）" if has_partial else "工作流执行完成"

    await insert_timeline(db, tenant_id, execution_id, workflow_id, "system", "INFO", "workflow_end",
                          f"{final_msg}: {workflow_name}",
                          f"共 {len(node_results)} 个节点，{global_retry} 次重试",
                          {"nodeCount": len(node_results), "retryCount": global_retry, "finalStatus": final_status})

    await insert_notification(db, tenant_id, None, final_msg,
                              f"工作流 {workflow_name} 已执行完成，共 {len(node_results)} 个节点",
                              "workflow", "info" if not has_partial else "warning")
    await db.commit()

    # 查询时间线
    timeline_rows = []
    try:
        rows = (await db.execute(text("""
            SELECT id, node_key, event_level, event_type, title, content, payload_json, created_time
            FROM workflow_timeline
            WHERE tenant_id=:tenant_id AND execution_id=:execution_id AND deleted=0
            ORDER BY id ASC
        """), {"tenant_id": tenant_id, "execution_id": execution_id})).mappings().all()
        timeline_rows = [dict(r) for r in rows]
    except Exception:
        pass

    return {
        "status": final_status,
        "progress": 100,
        "message": final_msg,
        "nodeResults": node_results,
        "artifacts": context.get("artifacts", []),
        "timeline": timeline_rows,
        "summary": {"nodeCount": len(node_results), "executionId": execution_id, "workflowId": workflow_id, "retryCount": global_retry, "hasPartial": has_partial},
    }


# ============================================================================
# 工作流「生图+发布」一体化辅助函数
#   背景：新流程要求每生成一张 AI 封面图后立即发布该商品，而不是全部生图后再批量发布。
#   下列函数用于支撑 IMAGE_GENERATE 节点的内联发布能力。
# ============================================================================


async def _resolve_publish_address(
    db: AsyncSession,
    tenant_id: int,
    address_payload: Optional[dict] = None,
) -> tuple[str, dict]:
    """
    解析发布地址。
    优先级：
      1) 前端预检传入的 addressPayload（用户在弹框中选择的地址）
      2) user_publish_address 表中按 use_count DESC 排序的常用地址
    返回 (address_text, address_dict)，address_text 为空字符串表示未找到地址。
    address_dict 包含 prov/city/area/divisionId/gps/poiId/poiName 字段，
    可直接传给 XianyuItemPublisher.publish 的 item_data["location"]。

    ★ 关键修复：前端传入的 addressPayload 通常只有 poiName/city/area/detail/lat/lng，
      缺少 prov/divisionId/gps/poiId 等闲鱼发布 API 必需的字段（会触发
      FAIL_BIZ_ITEM_EDIT_INVALID_MAP_LOCATION 错误）。
      因此当 addressPayload 缺少任一关键字段时，用数据库里同 tenant 的常用地址补全。
    """
    REQUIRED_KEYS = ("prov", "divisionId", "gps", "poiId")

    def _addr_from_payload(p: dict) -> dict:
        return {
            "poiName": _text(p.get("poiName") or ""),
            "prov": _text(p.get("prov") or ""),
            "city": _text(p.get("city") or ""),
            "area": _text(p.get("area") or ""),
            "divisionId": _text(p.get("divisionId") or ""),
            "gps": _text(p.get("gps") or ""),
            "poiId": _text(p.get("poiId") or ""),
            "detail": _text(p.get("detail") or ""),
        }

    # 辅助：从 address_payload 里 lat/lng 推导 gps（"经度,纬度" 格式）
    def _fill_gps_from_latlng(p: dict, addr: dict) -> None:
        if addr.get("gps"):
            return
        lat = _text(p.get("lat") or "")
        lng = _text(p.get("lng") or "")
        if lat and lng:
            # 闲鱼发布 API 的 gps 字段格式为 "经度,纬度"（lng,lat）
            addr["gps"] = f"{lng},{lat}"

    # 1) 优先使用前端预检传入的地址
    addr_from_payload: dict = {}
    if address_payload and isinstance(address_payload, dict):
        poi = _text(address_payload.get("poiName") or "")
        if poi:
            addr_from_payload = _addr_from_payload(address_payload)
            # 从 lat/lng 推导 gps（兜底）
            _fill_gps_from_latlng(address_payload, addr_from_payload)
            # 检查关键字段是否齐全
            missing = [k for k in REQUIRED_KEYS if not addr_from_payload.get(k)]
            if not missing:
                return poi, addr_from_payload
            # 关键字段缺失：去数据库查同一 tenant 的常用地址补全
            logger.info("[PUBLISH-ADDR] addressPayload 缺少关键字段 %s，从 user_publish_address 补全", missing)

    # 2) user_publish_address 表
    # ★ 关键修复：必须过滤掉关键字段（prov/divisionId/gps/poiId）为空的脏数据，
    #   否则按 use_count DESC 排序会优先选中历史遗留的不完整地址（如早期保存时
    #   未包含完整发布定位信息的记录），导致发布时触发
    #   FAIL_BIZ_ITEM_EDIT_INVALID_MAP_LOCATION 错误。
    try:
        rows = (await db.execute(text("""
            SELECT address_poi_name, address_city, address_area, address_prov,
                   address_division_id, address_gps, address_poi_id, address_detail
            FROM user_publish_address
            WHERE tenant_id=:tenant_id AND deleted=0
              AND address_poi_name IS NOT NULL AND address_poi_name <> ''
              AND address_prov IS NOT NULL AND address_prov <> ''
              AND address_division_id IS NOT NULL AND address_division_id <> ''
              AND address_gps IS NOT NULL AND address_gps <> ''
              AND address_poi_id IS NOT NULL AND address_poi_id <> ''
            ORDER BY use_count DESC, updated_time DESC
            LIMIT 1
        """), {"tenant_id": tenant_id})).mappings().all()
        if rows:
            row = dict(rows[0])
            poi = _text(row.get("address_poi_name", ""))
            if poi:
                db_addr = {
                    "poiName": poi,
                    "prov": _text(row.get("address_prov", "")),
                    "city": _text(row.get("address_city", "")),
                    "area": _text(row.get("address_area", "")),
                    "divisionId": _text(row.get("address_division_id", "")),
                    "gps": _text(row.get("address_gps", "")),
                    "poiId": _text(row.get("address_poi_id", "")),
                    "detail": _text(row.get("address_detail", "")),
                }
                # 如果有 address_payload 但关键字段缺失，用 db_addr 补全缺失字段
                if addr_from_payload:
                    for k, v in db_addr.items():
                        if not addr_from_payload.get(k) and v:
                            addr_from_payload[k] = v
                    return addr_from_payload.get("poiName") or poi, addr_from_payload
                return poi, db_addr
    except Exception as exc:
        _log_runtime_failure("resolve_publish_address", exc)

    # 如果数据库查询失败但 address_payload 有数据，返回它（即使关键字段缺失）
    if addr_from_payload:
        return addr_from_payload.get("poiName") or "", addr_from_payload

    return "", {}


async def _prepare_account_publishers(
    db: AsyncSession,
    tenant_id: int,
    account_ids: list,
    dry_run: bool,
) -> dict:
    """
    预解析所有账号的 Cookie + XianyuItemPublisher 实例，避免循环内重复解析。
    返回 {account_id: {"cookie_str", "token", "publisher", "is_fish_shop", "error"}}。
    若某账号 Cookie 解析失败，对应 entry 的 publisher 为 None，error 字段说明原因。
    """
    result: dict = {}
    if dry_run:
        for acct_id in account_ids:
            try:
                acct_id = int(acct_id)
            except (ValueError, TypeError):
                continue
            result[acct_id] = {"cookie_str": "", "token": "", "publisher": None, "is_fish_shop": False, "error": ""}
        return result

    from app.services.xianyu_goods_sync import XianyuItemPublisher, extract_token_from_cookie
    logger.info("[PREPARE-PUB] 开始预解析 publishers tenant_id=%s account_ids=%s dry_run=%s db_closed=%s",
                tenant_id, account_ids, dry_run, getattr(db, 'closed', 'unknown'))
    for acct_id_raw in account_ids:
        try:
            acct_id = int(acct_id_raw)
        except (ValueError, TypeError):
            continue
        try:
            cookie_str, cookie_err, _resolved_acct_id = await _resolve_account_cookie(db, tenant_id, acct_id, {})
            logger.info("[PREPARE-PUB] acct_id=%d auth_ok=%s", acct_id, not bool(cookie_err))
            if cookie_err:
                result[acct_id] = {"cookie_str": "", "token": "", "publisher": None, "is_fish_shop": False, "error": "账号登录状态不可用"}
                continue
            token = extract_token_from_cookie(cookie_str)
            if not token:
                result[acct_id] = {"cookie_str": cookie_str, "token": "", "publisher": None, "is_fish_shop": False, "error": "Cookie中缺少_m_h5_tk，请重新登录"}
                continue
            publisher = XianyuItemPublisher(cookie_str, tenant_id)
            # 查询账号是否鱼小铺：鱼小铺账号可自定义库存，普通账号库存固定为 1
            try:
                _fs_row = (await db.execute(text(
                    "SELECT fish_shop_user FROM xianyu_account WHERE id=:aid AND tenant_id=:tid AND deleted=0 LIMIT 1"
                ), {"aid": acct_id, "tid": tenant_id})).first()
                is_fish_shop = bool(_fs_row and _fs_row[0])
            except Exception as _fs_err:
                fs_flag_lookup_err = _exc_type_name(_fs_err)
                logger.warning("[PREPARE-PUB] acct_id=%d 查询鱼小铺标识失败，按普通账号处理 errorType=%s", acct_id, fs_flag_lookup_err)
                is_fish_shop = False
            result[acct_id] = {"cookie_str": cookie_str, "token": token, "publisher": publisher, "is_fish_shop": is_fish_shop, "error": ""}
        except Exception as e:
            _log_runtime_failure("prepare_account_publisher", e)
            result[acct_id] = {"cookie_str": "", "token": "", "publisher": None, "is_fish_shop": False, "error": "发布账号登录状态不可用"}
    logger.info("[PREPARE-PUB] 完成 预解析结果 keys=%s", list(result.keys()))
    return result


async def _resolve_category_by_image(
    db: AsyncSession,
    tenant_id: int,
    img_url: str,
    title: str,
    user_id: Optional[int] = None,
) -> str:
    """
    分类获取：
      1) 调用闲鱼 mtop.taobao.idle.kgraph.property.recommend API 用封面图获取推荐分类
      2) 失败 → AI 按标题从分类树推荐（复用 _suggest_category_by_title）
      3) 仍失败 → 返回空字符串（让闲鱼 API 自动分类）

    user_id 用于 AI 调用扣费（仅当传入时扣费，未传入则跳过扣费）。
    """
    # 1) 优先用封面图调闲鱼分类推荐 API
    if img_url:
        try:
            cat_name = await _fetch_category_from_image_api(db, tenant_id, img_url)
            if cat_name:
                logger.info("[CAT-BY-IMG] 封面图识别分类成功: %s", cat_name)
                return cat_name
        except Exception as exc:
            _log_runtime_failure("classify_product_image", exc)

    # 2) AI 按标题从分类树推荐
    if title:
        try:
            from .category_data import load_categories
            cat_data = load_categories()
            tree = cat_data.get("cation", cat_data.get("categories", []))
            flat_options = _flatten_category_tree(tree)
            if flat_options:
                ai_cat = await _suggest_category_by_title(db, tenant_id, title, flat_options, user_id=user_id)
                if ai_cat:
                    return ai_cat
        except Exception as exc:
            _log_runtime_failure("classify_product_with_ai", exc)

    return ""


async def _fetch_category_from_image_api(
    db: AsyncSession,
    tenant_id: int,
    img_url: str,
) -> str:
    """
    调用闲鱼分类推荐 API（mtop.taobao.idle.kgraph.property.recommend）获取图片对应的分类。
    复用工作流中任一账号的 Cookie 生成签名。
    返回 catName 字符串，失败返回空字符串。
    """
    # 找一个可用账号的 Cookie 来签名
    rows = (await db.execute(text("""
        SELECT a.id AS account_id, a.cookie
        FROM xianyu_account a
        WHERE a.tenant_id=:t AND a.deleted=0 AND a.cookie IS NOT NULL AND a.cookie != ''
        ORDER BY a.id ASC LIMIT 1
    """), {"t": tenant_id})).mappings().all()
    if not rows:
        return ""
    row = dict(rows[0])
    cookie_str = _text(row.get("cookie") or "")
    if not cookie_str:
        return ""

    # 提取 _m_h5_tk
    import re as _re
    m = _re.search(r"_m_h5_tk=([^;]+)", cookie_str)
    if not m:
        return ""
    tk = m.group(1)
    token_part = tk.split("_")[0] if "_" in tk else tk
    if not token_part:
        return ""

    import time as _time
    import hashlib as _hashlib
    import httpx

    timestamp = str(int(_time.time() * 1000))
    appkey = "12574478"
    data_str = f"{token_part}&{timestamp}&{appkey}&{{\"imageUrls\":[\"{img_url}\"]}}"
    sign = _hashlib.md5(data_str.encode("utf-8")).hexdigest()

    api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.kgraph.property.recommend/2.0/"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": cookie_str,
    }
    form_data = {
        "jsv": "1.0.0",
        "appKey": appkey,
        "t": timestamp,
        "sign": sign,
        "api": "mtop.taobao.idle.kgraph.property.recommend",
        "v": "2.0",
        "type": "originaljson",
        "dataType": "json",
        "data": json.dumps({"imageUrls": [img_url]}),
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(api_url, headers=headers, data=form_data)
    if resp.status_code != 200:
        return ""
    body = resp.json()
    if not isinstance(body, dict):
        return ""
    # 失败检查
    if body.get("ret") and isinstance(body["ret"], list):
        for r in body["ret"]:
            if "FAIL" in _text(r) or "ERROR" in _text(r):
                logger.debug(
                    "runtimeFailure operation=classify_product_image errorType=ProviderRejected requestId=%s",
                    get_request_id() or "-",
                )
                return ""
    data = body.get("data") or {}
    card_list = data.get("cardList") or []
    for card in card_list:
        card_data = card.get("cardData") or {}
        values_list = card_data.get("valuesList") or []
        for v in values_list:
            cat_name = _text(v.get("catName") or v.get("categoryName") or "")
            if cat_name:
                return cat_name
    return ""


async def _publish_single_item(
    db: AsyncSession,
    tenant_id: int,
    context: dict,
    state: dict,
    p: dict,
    img_url: str,
    img_ai_ok: bool,
    category: str,
    address_text: str,
    address: dict,
    account_pub: dict,
    acct_id: int,
    platform: str,
    idx: int,
) -> dict:
    """
    发布单个商品到闲鱼。封装发布逻辑（含去重、实际发布、落库去重表）。
    account_pub: _prepare_account_publishers 返回的 entry（含 publisher/token/cookie_str/error）。
    返回 publish_result 字典。
    """
    import hashlib as _hashlib
    title = _text(p.get("title", ""))
    desc = _text(p.get("description", ""))
    price = _text(p.get("price", "0"))
    # 价格兜底：搜索结果可能未携带 price 字段（如风控降级时 DOM 提取的残缺数据），使用默认价避免发布被拒绝
    try:
        _price_num = float(price)
    except (ValueError, TypeError):
        _price_num = 0.0
    if _price_num <= 0:
        logger.warning("[PUBLISH-INLINE] 商品价格缺失或无效，使用默认价 1 元 account=%d title=%s origPrice=%r", acct_id, title[:20], price)
        price = "1"
    source_item_id = _text(p.get("itemId", ""))
    source_title_raw = _text(p.get("title", ""))
    source_title_hash = _hashlib.md5(source_title_raw.strip().lower().encode("utf-8")).hexdigest() if source_title_raw else ""

    # ★ 发布前先存草稿：无论后续发布成功或失败都保留，便于用户在前台草稿箱查看与重试
    #   状态机：publishing（插入时） → published/failed（finalize 时）
    #   鱼小铺账号库存默认 999，普通账号库存固定 1（与实际发布逻辑一致）
    _draft_stock = 999 if account_pub.get("is_fish_shop") else 1

    # ★ 草稿模式（draft_only）：生图后只将封面图、标题、文案、价格、地址、分类、账号等
    #   存入 workflow_goods_draft 表（status=draft），不调用闲鱼发品 API。
    #   用户可在「商品草稿箱」页面单条/多选/一键全部发布。
    _publish_mode = _text(context.get("__publish_mode__") or "publish").lower()
    if _publish_mode == "draft_only":
        _draft_id = await _save_publish_draft(
            db=db, tenant_id=tenant_id,
            user_id=_safe_int(context.get("__user_id__"), 0) or None,
            workflow_id=context.get("__workflow_id__"),
            execution_id=context.get("__execution_id__"),
            workflow_name=_text(context.get("__workflow_name__")),
            node_key="IMAGE_GENERATE",
            account_id=acct_id,
            title=title, price=price, description=desc,
            cover_pic=img_url, image_urls=[img_url] if img_url else [],
            category=category, stock=_draft_stock,
            location=address if isinstance(address, dict) else None,
            raw_payload=p,
            source_item_id=source_item_id, source_title_hash=source_title_hash,
            initial_status="draft",
        )
        logger.info("[PUBLISH-DRAFT-ONLY] 已存入草稿箱 draft_id=%s account=%d title=%s",
                    _draft_id, acct_id, title[:30])
        return {
            "status": "saved_as_draft",
            "draft_id": _draft_id,
            "accountId": acct_id,
            "title": title,
            "price": price,
            "category": category,
            "publish_ms": 0,
            "error": "",
            "errorCode": "",
        }

    _draft_id = await _save_publish_draft(
        db=db, tenant_id=tenant_id,
        user_id=_safe_int(context.get("__user_id__"), 0) or None,
        workflow_id=context.get("__workflow_id__"),
        execution_id=context.get("__execution_id__"),
        workflow_name=_text(context.get("__workflow_name__")),
        node_key="IMAGE_GENERATE",
        account_id=acct_id,
        title=title, price=price, description=desc,
        cover_pic=img_url, image_urls=[img_url] if img_url else [],
        category=category, stock=_draft_stock,
        location=address if isinstance(address, dict) else None,
        raw_payload=p,
        source_item_id=source_item_id, source_title_hash=source_title_hash,
        initial_status="publishing",
    )
    try:
        _result = await _publish_single_item_impl(
            db, tenant_id, context, state, p, img_url, img_ai_ok,
            category, address_text, address, account_pub, acct_id, platform, idx,
            title=title, desc=desc, price=price,
            source_item_id=source_item_id, source_title_hash=source_title_hash,
        )
    finally:
        # ★ 无论成功/失败/跳过，都根据结果更新草稿状态（fire-and-forget）
        if _result and _draft_id:
            try:
                await _finalize_publish_draft_from_result(
                    db, draft_id=_draft_id, publish_result=_result,
                )
            except Exception as _fin_exc:
                _log_runtime_failure("finalize_publish_draft", _fin_exc)
    return _result


async def _publish_single_item_impl(
    db: AsyncSession,
    tenant_id: int,
    context: dict,
    state: dict,
    p: dict,
    img_url: str,
    img_ai_ok: bool,
    category: str,
    address_text: str,
    address: dict,
    account_pub: dict,
    acct_id: int,
    platform: str,
    idx: int,
    *,
    title: str,
    desc: str,
    price: str,
    source_item_id: str,
    source_title_hash: str,
) -> dict:
    """_publish_single_item 的内部实现（不含草稿逻辑）。

    草稿保存与状态更新由外层 _publish_single_item 统一处理。
    本函数仅负责校验、去重、实际发布与落库去重表。
    """
    # 约束1：未生成AI封面图的商品严禁发布
    if not img_ai_ok or not img_url:
        logger.warning("[PUBLISH-INLINE] 跳过发布(无AI封面图) account=%d title=%s", acct_id, title[:20])
        return {
            "goods_id": "",
            "title": title,
            "image_url": img_url,
            "platform": platform,
            "status": "skipped_no_ai_image",
            "errorCode": "PUBLISH_AI_IMAGE_REQUIRED",
            "error": "商品未生成 AI 封面图，已阻止发布",
            "account_id": acct_id,
            "category": category,
            "addressText": address_text,
            "address": address,
            "source_item_id": source_item_id,
            "idx": idx,
        }

    if not title or not desc:
        return {
            "goods_id": "",
            "title": title,
            "image_url": img_url,
            "platform": platform,
            "status": "skipped",
            "errorCode": "PUBLISH_CONTENT_INVALID",
            "error": "商品标题或描述不完整，已阻止发布",
            "account_id": acct_id,
            "category": category,
            "addressText": address_text,
            "address": address,
            "source_item_id": source_item_id,
            "idx": idx,
        }

    # ★ 价格校验：价格 <= 0 直接跳过发布，避免发送到闲鱼后被 FAIL_BIZ_SKU_PRICE_ILLEGAL 拒绝
    #   搜索结果可能未携带 price 字段，需在调用 publisher 前防御
    try:
        _price_num = float(price) if price not in ("", None) else 0.0
    except (ValueError, TypeError):
        _price_num = 0.0
    if _price_num <= 0:
        logger.warning("[PUBLISH-INLINE] 跳过发布(价格<=0) account=%d title=%s price=%r",
                       acct_id, title[:20], price)
        return {
            "goods_id": "",
            "title": title,
            "image_url": img_url,
            "platform": platform,
            "status": "skipped",
            "errorCode": "PUBLISH_PRICE_INVALID",
            "error": "商品价格未设置或为 0，已阻止发布",
            "account_id": acct_id,
            "category": category,
            "addressText": address_text,
            "address": address,
            "source_item_id": source_item_id,
            "idx": idx,
        }

    # 账号 Cookie 失败
    if not account_pub.get("publisher"):
        return {
            "goods_id": "",
            "title": title,
            "image_url": img_url,
            "platform": platform,
            "status": "failed",
            "errorCode": "PUBLISH_ACCOUNT_UNAVAILABLE",
            "error": "发布账号登录状态不可用，请重新登录",
            "account_id": acct_id,
            "category": category,
            "addressText": address_text,
            "address": address,
            "source_item_id": source_item_id,
            "idx": idx,
        }

    # 约束2：跨次运行去重检查
    try:
        dedup_hit = False
        if source_item_id:
            dr = (await db.execute(text("""
                SELECT id FROM workflow_published_goods
                WHERE tenant_id=:t AND account_id=:a AND source_item_id=:s AND deleted=0 LIMIT 1
            """), {"t": tenant_id, "a": acct_id, "s": source_item_id})).first()
            if dr:
                dedup_hit = True
        if not dedup_hit and source_title_hash:
            dr = (await db.execute(text("""
                SELECT id FROM workflow_published_goods
                WHERE tenant_id=:t AND account_id=:a AND source_title_hash=:h AND deleted=0 LIMIT 1
            """), {"t": tenant_id, "a": acct_id, "h": source_title_hash})).first()
            if dr:
                dedup_hit = True
        if dedup_hit:
            logger.info("[PUBLISH-INLINE] 跳过发布(重复) account=%d title=%s itemId=%s", acct_id, title[:20], source_item_id)
            return {
                "goods_id": "",
                "title": title,
                "image_url": img_url,
                "platform": platform,
                "status": "skipped_duplicate",
                "errorCode": "PUBLISH_DUPLICATE",
                "error": "该商品已发布过，已跳过重复发布",
                "account_id": acct_id,
                "category": category,
                "addressText": address_text,
                "address": address,
                "source_item_id": source_item_id,
                "idx": idx,
            }
    except Exception as exc:
        _log_runtime_failure("check_inline_publish_duplicate", exc)

    # 真实发布
    try:
        _t_pub_start = __import__('time').perf_counter()
        # 鱼小铺账号可自定义库存（默认 999），普通账号库存固定为 1
        _pub_quantity = 999 if account_pub.get("is_fish_shop") else 1
        item_data = {
            "title": title,
            "desc": desc,
            "imageUrls": [img_url],
            "price": price,
            "quantity": _pub_quantity,
        }
        if category:
            item_data["category"] = {"catName": category}
        # ★ 地址：直接复用 address dict 作为 location 字段
        #   XianyuItemPublisher.publish 会读取 location 的 prov/city/area/divisionId/gps/poiId/poiName 字段
        if isinstance(address, dict) and address.get("poiName"):
            item_data["location"] = {
                "poiName": address.get("poiName", ""),
                "prov": address.get("prov", ""),
                "city": address.get("city", ""),
                "area": address.get("area", ""),
                "divisionId": address.get("divisionId", ""),
                "gps": address.get("gps", ""),
                "poiId": address.get("poiId", ""),
            }

        publisher = account_pub["publisher"]
        result = await asyncio.to_thread(publisher.publish, item_data)
        _pub_ms = int((__import__('time').perf_counter() - _t_pub_start) * 1000)

        if result.get("success"):
            goods_id = _text(result.get("itemId", ""))
            logger.info("[PUBLISH-INLINE] 发布成功 account=%d title=%s goods_id=%s",
                        acct_id, title[:20], goods_id)
            # 落库去重表
            try:
                await db.execute(text("""
                    INSERT INTO workflow_published_goods(tenant_id, account_id, source_item_id, source_title_hash, source_image_url, goods_id, published_title, workflow_id, execution_id, created_time, deleted)
                    VALUES(:t, :a, :si, :sh, :img, :gid, :pt, :wid, :eid, NOW(), 0)
                """), {
                    "t": tenant_id, "a": acct_id, "si": source_item_id or "",
                    "sh": source_title_hash, "img": img_url[:500] if img_url else "",
                    "gid": goods_id, "pt": title[:200],
                    "wid": context.get("__workflow_id__"), "eid": context.get("__execution_id__"),
                })
                await db.commit()
            except Exception as exc:
                await db.rollback()
                _log_runtime_failure("persist_inline_publish_dedup", exc)
            # 记录耗时
            try:
                _timing = state.setdefault("item_timings", {}).get(idx, {})
                _polish = _timing.get("polish_ms", 0)
                _img = _timing.get("image_generate_ms", 0)
                _total = _polish + _img + _pub_ms
                await _record_item_timing(
                    db=db, tenant_id=tenant_id,
                    execution_id=context.get("__execution_id__"),
                    workflow_id=context.get("__workflow_id__"),
                    item_index=idx,
                    source_item_id=_timing.get("source_item_id", source_item_id),
                    source_title=_timing.get("source_title", title),
                    polish_ms=_polish, image_generate_ms=_img,
                    publish_ms=_pub_ms, total_ms=_total,
                )
            except Exception as exc:
                _log_runtime_failure("persist_inline_publish_timing", exc)
            return {
                "goods_id": goods_id,
                "title": title,
                "image_url": img_url,
                "platform": platform,
                "status": "published",
                "account_id": acct_id,
                "category": category,
                "addressText": address_text,
                "address": address,
                "source_item_id": source_item_id,
                "idx": idx,
                "publish_ms": _pub_ms,
            }
        else:
            logger.warning("runtimeFailure operation=publish_single_item errorType=ProviderRejected requestId=%s", get_request_id() or "-")
            # 透传 publisher 返回的真实原因（已包含 ret_msg 翻译），避免丢失排障信息
            reject_msg = result.get("message") or "平台暂未接受该商品，请检查内容后重试"
            return {
                "goods_id": "",
                "title": title,
                "image_url": img_url,
                "platform": platform,
                "status": "failed",
                "errorCode": "PUBLISH_PROVIDER_REJECTED",
                "error": reject_msg,
                "account_id": acct_id,
                "category": category,
                "source_item_id": source_item_id,
                "idx": idx,
            }
    except Exception as e:
        _log_runtime_failure("publish_single_item", e)
        # 仅保留异常类型便于排障，异常值不得写入结果（防泄露）
        err_type = type(e).__name__
        err_msg = err_type
        return {
            "goods_id": "",
            "title": title,
            "image_url": img_url,
            "platform": platform,
            "status": "failed",
            "errorCode": "PUBLISH_RUNTIME_ERROR",
            "error": f"商品发布异常：{err_msg}",
            "errorMessage": err_msg,
            "errorType": err_type,
            "account_id": acct_id,
            "category": category,
            "source_item_id": source_item_id,
            "idx": idx,
        }


async def _execute_workflow_node(
    db: AsyncSession,
    tenant_id: int,
    typ: str,
    config: dict[str, Any],
    context: dict[str, Any],
    state: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    执行单个工作流节点。
    匹配 workflow_test_script.md 中的节点语义：
    - trigger: 初始化触发器
    - goods_search/product_fetch: 按关键词搜索商品
    - goods_filter/product_filter: 筛选商品，支持数量不足时 RETRY
    - image_generate: 生成商品图片
    - text_rewrite: 润色文案
    - notification: 发送通知
    - publish_goods: 发布商品
    """
    if state is None:
        state = {}

    if typ in {"trigger", "manual", "start", "TRIGGER"}:
        # ★ 多账号支持：读取 selectedAccountIds 数组，兼容老工作流的 selectedAccountId 单值
        selected_account_ids = config.get("selectedAccountIds") or []
        if not isinstance(selected_account_ids, list):
            selected_account_ids = [selected_account_ids] if selected_account_ids else []
        selected_account_ids = [int(a) for a in selected_account_ids if a]
        # 兼容老工作流：若无 selectedAccountIds 但有 selectedAccountId
        if not selected_account_ids:
            single = config.get("selectedAccountId")
            if single:
                selected_account_ids = [int(single)]
        execute_count = config.get("executeCount", 1)
        # 单账号兼容：state["selected_account_id"] 仍保留第一个账号（供 PRODUCT_FETCH 搜索使用）
        first_account_id = selected_account_ids[0] if selected_account_ids else None
        return {
            "ok": True,
            "message": "触发器已就绪",
            "selectedAccountId": first_account_id,
            "selectedAccountIds": selected_account_ids,
            "executeCount": execute_count,
            "artifact": {"trigger": config}
        }

    if typ in {"goods_search", "product_fetch", "商品获取", "PRODUCT_FETCH"}:
        # ★ 店铺搜索模式：通过 crawler-service 爬取店铺商品，按账号+店铺去重后取前 5 个
        #   sourceType=keyword（默认）走下方现有关键词搜索逻辑，不受影响
        _source_type = _text(config.get("sourceType") or config.get("source_type") or "keyword").lower().strip()
        if _source_type == "shop":
            logger.info("[PRODUCT_FETCH] 店铺搜索模式 shopUrl=%s", config.get("shopUrl") or config.get("shop_url"))
            return await _workflow_shop_fetch(db, tenant_id, config, context, state)

        # ★ 直接调用 MTOP 搜索函数（与 browser 手动搜索走完全相同的代码路径）
        #   支持分页增量获取：在筛选不足触发 RETRY 后，使用 page+1 获取更多商品并追加到已有池
        logger.info("[PRODUCT_FETCH] 开始商品获取")

        # 1) 关键词获取
        raw_keywords = config.get("keywords") or state.get("keywords") or context.get("input", {}).get("keywords") or []
        if isinstance(raw_keywords, str):
            raw_keywords = _parse_keywords(raw_keywords)
        if not raw_keywords:
            single_kw = _text(config.get("keyword") or context.get("input", {}).get("keyword") or "")
            if single_kw:
                raw_keywords = [single_kw]
        if not raw_keywords:
            raw_keywords = ["蓝海商品"]

        target_count = _safe_int(config.get("targetCount") or config.get("limit"), 5)
        # 把 target_count 写入 state，供筛选节点使用
        state["target_count"] = target_count

        # 2) 账号解析
        account_id = (config.get("accountId")
                      or state.get("selectedAccountId")
                      or state.get("selected_account_id")
                      or context.get("input", {}).get("accountId")
                      or context.get("input", {}).get("selectedAccountId")
                      or context.get("input", {}).get("selected_account_id"))
        if not account_id:
            for ctx_key, ctx_val in context.items():
                if isinstance(ctx_val, dict) and ctx_val.get("selectedAccountId"):
                    account_id = ctx_val["selectedAccountId"]
                    break
        if not account_id:
            account_id = 1  # 默认使用第一个账号

        # 3) 解析账号 Cookie（与 /goofish-search 接口完全一致）
        cookie_str, cookie_err, _resolved_acct_id = await _resolve_account_cookie(db, tenant_id, int(account_id), {})
        if cookie_err:
            logger.warning("runtimeFailure operation=resolve_search_account_cookie errorType=AccountAuthUnavailable requestId=%s", get_request_id() or "-")
            return {
                "ok": False, "errorCode": "ACCOUNT_AUTH_UNAVAILABLE", "message": "账号登录状态不可用，请重新登录",
                "count": 0, "items": [], "keyword": ", ".join(raw_keywords[:3]) if raw_keywords else "",
                "artifactType": "goods", "artifactTitle": "商品获取",
                "artifact": {"count": 0, "items": [], "keyword": ", ".join(raw_keywords[:3]) if raw_keywords else ""},
            }

        # 遵守项目硬约束：商品搜索接口不得刷新 _m_h5_tk（刷新会触发 Baxia 风控）
        # 直接使用原始 Cookie，由 _workflow_search_with_fallback 实现 fast→slow 自动降级


        # 4) 关键词选取策略
        #    首轮执行：从所有关键词中随机抽取 target_count 个关键词
        #    重试执行：使用上一轮选中的关键词，page+1（增量追加补充商品池）
        previous_items = state.get("all_fetched_items", [])
        current_page = state.get("product_fetch_page", 1)

        # ★ 状态污染防护：检查旧商品池中的商品 keyword 字段是否属于当前关键词列表。
        #    如果不属于（说明用户修改了关键词配置，或来自不同执行上下文），
        #    必须清空旧商品池，从第一页重新搜索。
        if previous_items:
            current_kw_set = set(raw_keywords)
            # 从旧商品池的第一个商品的 keyword 字段判断来源
            stale_keywords_found = False
            for _pi in previous_items[:5]:
                _pi_kw = _text(_pi.get("keyword", "")) if isinstance(_pi, dict) else ""
                if _pi_kw and _pi_kw not in current_kw_set:
                    stale_keywords_found = True
                    break
            # 也检查 saved selected_keywords
            saved_keywords = state.get("selected_keywords", [])
            if not stale_keywords_found and saved_keywords:
                for _sk in saved_keywords:
                    if _sk not in current_kw_set:
                        stale_keywords_found = True
                        break
            if stale_keywords_found:
                logger.info("[PRODUCT_FETCH] 检测到旧商品池关键词与当前配置不匹配，清空旧商品池 %d 个",
                            len(previous_items))
                previous_items = []
                current_page = 1
                state["all_fetched_items"] = []
                state["product_fetch_page"] = 1
                state["selected_keywords"] = []

        existing_ids = {item.get("itemId", "") for item in previous_items}

        if previous_items:
            # 重试轮次：使用首轮选中的关键词，翻页补充更多商品
            selected_keywords = state.get("selected_keywords", raw_keywords[:1])
            logger.info("[PRODUCT_FETCH] 重试执行 关键词=%d个 page=%d", len(selected_keywords), current_page)
        else:
            # 首轮执行：从所有关键词中随机抽取 target_count 个
            sample_size = min(target_count, len(raw_keywords))
            sample_size = max(sample_size, 1)
            selected_keywords = random.sample(raw_keywords, sample_size)
            state["selected_keywords"] = selected_keywords
            logger.info(
                "[PRODUCT_FETCH] 首轮执行 从 %d 个关键词中随机选中 %d 个",
                len(raw_keywords),
                len(selected_keywords),
            )

        logger.info("[PRODUCT_FETCH] 当前页码=%d 已有商品=%d 目标=%d",
                     current_page, len(previous_items), target_count)

        # 5) 逐关键词搜索，收集所有商品到池中（不再每词只取1个）
        #    搜索完所有关键词后，从池中按关键词均衡选取 target_count 个
        #    遵守硬约束：不刷新 _m_h5_tk，直接使用原始 Cookie
        #    ★ 修复：连续 MTOP 调用会触发 Baxia 风控（第2次起即被拦截），
        #      需在关键词之间增加间隔；检测到风控后，后续关键词直接走 slow 模式；
        #      慢速搜索之间也增加间隔，避免 crawler-service 并发资源争用导致 500。
        new_items: list[dict] = []
        steps: list[dict] = []
        user_search_mode = _text(config.get("fetchMode") or config.get("searchMode") or "auto")
        # 运行期模式：检测到风控后切换为 slow，避免继续撞 MTOP 风控墙
        runtime_search_mode = user_search_mode
        baxia_triggered = False
        # 每个关键词搜索后的间隔（秒）：fast 成功后小间隔，slow/失败后大间隔
        FAST_OK_INTERVAL = 1.5
        SLOW_INTERVAL = 2.0

        for kw_idx, kw in enumerate(selected_keywords):
            # 关键词之间的间隔：从第2个关键词开始等待，降低 Baxia 风控触发概率
            if kw_idx > 0:
                _interval = SLOW_INTERVAL if baxia_triggered else FAST_OK_INTERVAL
                await asyncio.sleep(_interval)

            try:
                raw_items_list, used_mode = await asyncio.to_thread(
                    _workflow_search_with_fallback,
                    kw, current_page, 20, tenant_id, cookie_str, runtime_search_mode,
                )
            except PublicRuntimeError as e:
                _log_runtime_failure("search_workflow_products", e)
                # ★ 检测到 Baxia 风控：后续关键词直接走 slow 模式，不再撞 MTOP
                if e.error_code == "PRODUCT_SEARCH_RATE_LIMITED" and not baxia_triggered:
                    baxia_triggered = True
                    runtime_search_mode = "slow"
                    logger.warning("[PRODUCT_FETCH] keyword=%s 触发风控，后续关键词切换为 slow 模式", kw)
                    steps.append({
                        "step": f"搜索[{kw}]",
                        "status": "error",
                        "errorCode": "PRODUCT_SEARCH_RATE_LIMITED",
                        "detail": f"快速搜索触发平台验证，已切换后续关键词为慢速搜索",
                    })
                else:
                    steps.append({
                        "step": f"搜索[{kw}]",
                        "status": "error",
                        "errorCode": e.error_code,
                        "detail": f"搜索失败：{e.public_message}",
                    })
                continue
            except Exception as e:
                _log_runtime_failure("search_workflow_products", e)
                steps.append({"step": f"搜索[{kw}]", "status": "error", "errorCode": "PRODUCT_SEARCH_UNAVAILABLE", "detail": "商品搜索服务暂时不可用"})
                continue

            logger.info("[PRODUCT_FETCH] 搜索 keyword=%s page=%d mode=%s 原始商品数=%d",
                         kw, current_page, used_mode, len(raw_items_list))

            # 记录返回商品标题样本，便于排查搜索结果不相关问题
            if raw_items_list:
                _title_samples = []
                for _ri in raw_items_list[:3]:
                    if isinstance(_ri, dict):
                        _t = _ri.get("title", "") or _ri.get("description", "")
                        _title_samples.append(_t[:40] if _t else "(无标题)")
                logger.info("[PRODUCT_FETCH] 搜索结果样本 keyword=%s: %s", kw, _title_samples)

            # 收集该关键词所有去重商品到池中（不再只取1个）
            kw_taken = 0
            for raw_item in raw_items_list:
                if not isinstance(raw_item, dict):
                    continue
                item_id = raw_item.get("itemId", "")
                if item_id and item_id in existing_ids:
                    continue
                if item_id:
                    existing_ids.add(item_id)
                raw_item["keyword"] = kw
                new_items.append(raw_item)
                kw_taken += 1

            steps.append({
                "step": f"搜索[{kw}]",
                "status": "success" if kw_taken > 0 else "warn",
                "detail": f"搜索成功({used_mode}模式) page={current_page} 收集{kw_taken}个商品",
            })

        # ★ 逐商品进度事件
        _fetched_so_far = len(previous_items) + len(new_items)
        try:
            _exec_id = context.get("__execution_id__")
            _wf_id = context.get("__workflow_id__")
            await insert_timeline(db, tenant_id, _exec_id, _wf_id, key, "INFO", "fetch_progress",
                                  f"商品获取进度: 搜索到{_fetched_so_far}个商品（目标{target_count}）",
                                  f"本轮搜索{len(selected_keywords)}个关键词，共收集{len(new_items)}个新商品",
                                  {"progress": min(_fetched_so_far, target_count), "total": target_count, "poolSize": _fetched_so_far})
            await db.commit()
        except Exception as exc:
            _log_runtime_failure("persist_product_fetch_progress", exc)

        # 6) 汇总所有商品，随机打乱后选取 target_count 个
        combined_pool = previous_items + new_items

        # ★ 敏感词过滤：命中后台 scene=product 敏感词的商品直接移除。
        #   过滤后的池写回 state["all_fetched_items"]，确保重试时不会再次选中坏商品；
        #   若过滤后池大小 < target_count，PRODUCT_FILTER 节点会触发重试，自动从下一页补充新商品。
        sensitive_words = await _fetch_product_sensitive_words()
        if sensitive_words:
            combined_pool, _sensitive_removed = _filter_items_by_sensitive_words(
                combined_pool, sensitive_words, tag="PRODUCT_FETCH",
            )
            if _sensitive_removed:
                steps.append({
                    "step": "敏感词过滤",
                    "status": "warn",
                    "detail": f"命中敏感词移除 {len(_sensitive_removed)} 个商品，剩余 {len(combined_pool)} 个",
                })

        state["all_fetched_items"] = combined_pool  # 保留完整池供重试追加
        state["product_fetch_page"] = current_page + 1  # 下次获取下一页

        # ★ 按关键词均衡选取 target_count 个商品，避免全部商品来自单一关键词。
        #   策略：按 keyword 分组，每组内部随机打乱，然后 round-robin 轮询选取，
        #   确保每个成功关键词至少贡献 1 个商品（当 target_count >= 关键词数时）。
        #   仅当 combined_pool 数量 > target_count 时才需要选取；否则全部保留。
        if len(combined_pool) > target_count:
            # 按 keyword 分组（previous_items 中的商品可能没有 keyword 字段，归入 "历史" 组）
            kw_buckets: dict[str, list[dict]] = {}
            for _item in combined_pool:
                _kw = _text(_item.get("keyword", "")) if isinstance(_item, dict) else ""
                if not _kw:
                    _kw = "历史商品"
                kw_buckets.setdefault(_kw, []).append(_item)
            # 每组内部随机打乱，保证同关键词内商品多样性
            for _bucket in kw_buckets.values():
                random.shuffle(_bucket)
            # round-robin 轮询选取：从每个关键词组依次取1个，循环直到填满 target_count
            selected: list[dict] = []
            _bucket_keys = list(kw_buckets.keys())
            # 按组数量降序排列，优先从大组取，避免小组提前耗尽后轮空
            _bucket_keys.sort(key=lambda k: len(kw_buckets[k]), reverse=True)
            _exhausted: set[str] = set()
            while len(selected) < target_count and len(_exhausted) < len(_bucket_keys):
                for _bk in _bucket_keys:
                    if len(selected) >= target_count:
                        break
                    if _bk in _exhausted:
                        continue
                    _bucket = kw_buckets[_bk]
                    if not _bucket:
                        _exhausted.add(_bk)
                        continue
                    selected.append(_bucket.pop(0))
        else:
            selected = list(combined_pool)

        # 统计实际选中的关键词分布
        _selected_kw_dist: dict[str, int] = {}
        for _s in selected:
            _kw = _text(_s.get("keyword", "")) if isinstance(_s, dict) else ""
            _kw = _kw or "历史商品"
            _selected_kw_dist[_kw] = _selected_kw_dist.get(_kw, 0) + 1
        _kw_dist_str = ", ".join(f"{k}={v}" for k, v in _selected_kw_dist.items())

        logger.info("[PRODUCT_FETCH] 完成 池大小=%d 选取=%d 目标=%d page=%d 关键词分布=[%s]",
                     len(combined_pool), len(selected), target_count, current_page, _kw_dist_str)

        # 实际使用的关键词（用于前端展示，避免显示固定第一个关键词产生误导）
        used_keywords_display = ", ".join(selected_keywords) if selected_keywords else ""

        # ★ 当多个关键词搜索失败、结果集中来自单一关键词时，明确告知用户
        _success_kw_count = len([k for k, v in _selected_kw_dist.items() if v > 0 and k != "历史商品"])
        if _success_kw_count <= 1 and len(selected_keywords) > 1 and len(selected) > 0:
            _warning_msg = f"成功获取 {len(selected)} 个商品，但仅 {_success_kw_count} 个关键词搜索成功（共 {len(selected_keywords)} 个），建议稍后重试或检查账号风控状态"
        else:
            _warning_msg = f"成功获取 {len(selected)} 个商品（商品池 {len(combined_pool)} 个，按关键词均衡选取 {len(selected)} 个）"

        return {
            "ok": len(selected) > 0,
            "errorCode": "" if selected else "PRODUCT_SEARCH_EMPTY",
            "message": _warning_msg if selected else "未获取到商品",
            "items": selected, "count": len(selected),
            "keyword": used_keywords_display,
            "artifactType": "goods", "artifactTitle": "商品获取",
            "artifact": {
                "count": len(selected), "items": selected,
                "keyword": used_keywords_display,
                "poolSize": len(combined_pool),
                "keywordDistribution": _selected_kw_dist,
            },
            "steps": steps,
        }

    if typ in {"goods_filter", "product_filter", "商品筛选", "PRODUCT_FILTER"}:
        # 从 state 或 context 中获取上一节点产物
        previous_items = state.get("selected_products", [])
        if not previous_items:
            for v in context.values():
                if isinstance(v, dict) and isinstance(v.get("items"), list):
                    previous_items = v.get("items")
                    break

        # 目标数量来自商品获取节点的配置（筛选节点不再有独立 targetCount）
        target_count = state.get("target_count", 5)
        min_price = float(config.get("minPrice") or 0)
        user_prompt = _text(config.get("userPrompt") or "")

        logger.info("[PRODUCT_FILTER] 开始筛选 items=%d targetCount=%d hasPrompt=%s",
                     len(previous_items), target_count, bool(user_prompt))

        # 解析扣费用 user_id（取首个账号）
        _pf_account_ids = state.get("selected_account_ids") or ([state.get("selected_account_id")] if state.get("selected_account_id") else [])
        _pf_user_id = None
        if _pf_account_ids:
            try:
                _pf_user_id = await _resolve_account_user_id(db, tenant_id, int(_pf_account_ids[0]), {})
            except Exception as exc:
                _log_runtime_failure("resolve_product_filter_user", exc)
                _pf_user_id = None

        if user_prompt and not _pf_user_id:
            return {
                "ok": False,
                "errorCode": "AI_USER_UNRESOLVED",
                "message": "AI 筛选无法确定计费用户，请检查工作流账号归属",
                "items": [],
            }
        _pf_run_identity = context.get("__execution_id__") or build_request_id("product_filter_run")

        filtered = []
        for item_index, p in enumerate(previous_items):
            if min_price > 0 and float(p.get("price", 0)) < min_price:
                logger.info("[PRODUCT_FILTER] 移除(价格筛除): price=%s < minPrice=%s",
                            p.get("price"), min_price)
                continue

            # AI 规则筛选：用户填写了筛选规则时，用 AI 判断商品是否匹配
            if user_prompt:
                title = _text(p.get("title", ""))
                description = _text(p.get("description", "") or p.get("desc", ""))
                item_text = f"标题：{title}\n描述：{description}"
                ai_prompt = (
                    f"你是一个商品筛选助手。下面是用户定义的筛选规则：\n\n"
                    f"{user_prompt}\n\n"
                    f"下面是待筛选的商品信息：\n\n"
                    f"{item_text}\n\n"
                    f"请判断这个商品是否符合上述筛选规则。只回答\"符合\"或\"不符合\"，不要其他文字。"
                )
                billing_request_id = build_stable_request_id(
                    "product_filter",
                    tenant_id,
                    _pf_run_identity,
                    item_index,
                    p.get("itemId") or p.get("id") or title,
                    user_prompt,
                )
                try:
                    await precheck_ai_usage({
                        "tenantId": tenant_id,
                        "userId": _pf_user_id,
                        "scene": "product_filter",
                        "providerName": "default",
                        "modelName": "default",
                        "modelType": "chat",
                        "promptTokens": estimate_text_tokens(ai_prompt),
                        "completionTokens": 0,
                        "requestId": billing_request_id,
                    })
                    ai_result = await generate_text(
                        "product_filter",
                        "你是一个严格的商品筛选助手，根据规则判断商品是否通过筛选。",
                        ai_prompt,
                        0.1,
                        request_id=billing_request_id,
                    )
                    if not ai_result.get("ok"):
                        return {
                            "ok": False,
                            "errorCode": "AI_MODEL_UNAVAILABLE",
                            "message": "AI 商品筛选服务暂不可用，请稍后重试",
                            "items": filtered,
                        }
                    content = _text(ai_result.get("content", "")).strip()
                    await charge_text_usage(
                        tenant_id=tenant_id, user_id=_pf_user_id, scene="product_filter",
                        provider_name=_text(ai_result.get("provider", "default")),
                        model_name=_text(ai_result.get("model", "default")),
                        prompt=ai_prompt, completion=content,
                        request_id=billing_request_id,
                        raw_usage=ai_result.get("usage") or {},
                    )
                    decision = re.sub(r"[\s。.!！]", "", content).lower()
                    if decision in {"符合", "是", "通过", "true"}:
                        filtered.append(p)
                        logger.info("[PRODUCT_FILTER] AI判断通过 titleLen=%d", len(title))
                    else:
                        logger.info(
                            "[PRODUCT_FILTER] AI判断移除 titleLen=%d decisionLen=%d",
                            len(title),
                            len(content),
                        )
                except AiBillingPaymentRequired:
                    return {
                        "ok": False,
                        "errorCode": "AI_BALANCE_INSUFFICIENT",
                        "message": "AI Token 余额不足，请充值后重试",
                        "items": filtered,
                    }
                except AiBillingError as exc:
                    _log_runtime_failure("bill_product_filter", exc)
                    return {
                        "ok": False,
                        "errorCode": "AI_BILLING_UNAVAILABLE",
                        "message": "AI 计费服务暂不可用，筛选已停止，请稍后重试",
                        "items": filtered,
                    }
                except Exception as exc:
                    _log_runtime_failure("filter_product_with_ai", exc)
                    return {
                        "ok": False,
                        "errorCode": "AI_FILTER_FAILED",
                        "message": "AI 商品筛选异常，筛选已停止，请稍后重试",
                        "items": filtered,
                    }
            else:
                # 无筛选规则，全部通过
                filtered.append(p)

        removed = len(previous_items) - len(filtered)
        logger.info("[PRODUCT_FILTER] 筛选完成: 保留=%d 移除=%d 目标=%d",
                     len(filtered), removed, target_count)

        # 数量不足时 RETRY
        if len(filtered) < target_count:
            return {
                "ok": True, "items": filtered, "count": len(filtered), "removed": removed,
                "route": "RETRY",
                "message": f"筛选后仅 {len(filtered)} 个商品，不足目标 {target_count} 个，需要重试",
                "artifactType": "goods", "artifactTitle": "筛选后商品(不足)",
                "artifact": {"items": filtered, "targetCount": target_count, "removed": removed},
            }

        return {
            "ok": True, "items": filtered, "count": len(filtered), "removed": removed,
            "route": "SUCCESS",
            "artifactType": "goods", "artifactTitle": "筛选后商品",
            "artifact": {"items": filtered, "targetCount": target_count, "removed": removed},
        }

    if typ in {"image_generate", "generate_image", "生图", "ai_image", "IMAGE_GENERATE"}:
        first_prompt = _text(config.get("firstPrompt") or config.get("prompt") or config.get("style") or DEFAULT_IMAGE_PROMPT_FALLBACK)
        polished = state.get("polished_products", [])
        # ★ imageCount 语义修正：每个商品都需要独立封面图，生成数量应 >= 待发布商品数。
        #    若 config 未配置或配置值 < polished 数量，自动取 max(configValue, len(polished))。
        config_image_count = _safe_int(config.get("imageCount"), 0)
        image_count = max(config_image_count, len(polished)) if polished else (config_image_count or 5)
        if not polished:
            for v in context.values():
                if isinstance(v, dict) and isinstance(v.get("polished"), list):
                    polished = v.get("polished")
                    break

        logger.info("[IMAGE_GENERATE] 开始生图 polished=%d count=%d", len(polished), image_count)

        # 读取后台配置的全部启用生图模型（admin_module_record 表），逐个尝试直到成功。
        # 同时读取 general 配置继承其 baseUrl/apiKey。
        # ★ 与 Java ModelConfigService.getAllImageConfigs() + isEnabled() 保持完全一致：
        #   - SQL 不按 status 过滤（status 字段存的是 "正常"/"禁用" 等中文标签，不是数字）
        #   - 读完后检查 JSON 内的 status/enabled 字段判断是否可用
        # ★ 尊重节点配置的 modelKey：若指定则优先使用该模型，其余作为兜底
        node_model_key = _text(config.get("modelKey") or "").strip()
        image_configs: list[dict] = []
        try:
            # 缓存中间结果（general_cfg + img_cfgs）60s，避免每个生图节点都查库
            # node_model_key 排序每次都执行，因为不同节点可能指定不同 modelKey
            import time as _time
            now = _time.time()
            cached = _image_model_cache.get("data")
            cached_ts = _image_model_cache.get("ts", 0)
            if cached and (now - cached_ts) < _IMAGE_MODEL_TTL:
                general_cfg = cached.get("general_cfg", {})
                img_cfgs = cached.get("img_cfgs", [])
            else:
                rows = (await db.execute(text("""
                    SELECT module_key, status, json_text FROM admin_module_record
                    WHERE module_key IN ('model-config-general', 'model-config-image', 'model-config-image-2', 'model-config-image-3')
                      AND deleted=0
                    ORDER BY id ASC
                """))).mappings().all()
                general_cfg = {}
                img_cfgs = []
                for r in rows:
                    mk = _text(r.get("module_key"))
                    try:
                        cfg = json.loads(r.get("json_text") or "{}")
                    except Exception:
                        cfg = {}
                    # ★ 与 Java isEnabled() 一致：检查 JSON 内的 enabled/status 字段
                    cfg_enabled = _text(cfg.get("enabled", "")).strip()
                    cfg_status = _text(cfg.get("status", "")).strip()
                    if cfg_enabled in ("false", "0") or cfg_enabled.lower() == "false":
                        continue
                    if cfg_status in ("禁用", "0") or cfg_status.lower() == "false":
                        continue
                    if mk == "model-config-general":
                        general_cfg = cfg
                    else:
                        # 标记该配置的 module_key，用于后续按 modelKey 排序
                        cfg["__module_key__"] = mk
                        img_cfgs.append(cfg)
                _image_model_cache["data"] = {"general_cfg": general_cfg, "img_cfgs": img_cfgs}
                _image_model_cache["ts"] = now
            # 生图配置继承 general 的 baseUrl/apiKey（若自身未设置）
            for cfg in img_cfgs:
                merged = dict(general_cfg)
                merged.update(cfg)
                if merged.get("baseUrl") and merged.get("apiKey"):
                    image_configs.append(merged)
            # ★ 若节点指定了 modelKey，将其排到第一位（优先使用），其余作为兜底
            if node_model_key:
                image_configs.sort(key=lambda c: 0 if c.get("__module_key__") == node_model_key else 1)
        except Exception as exc:
            _log_runtime_failure("load_image_model_config", exc)

        if not image_configs:
            logger.error("[IMAGE_GENERATE] 未读取到任何启用的生图模型配置，生图必然失败")
        else:
            logger.info("[IMAGE_GENERATE] 可用生图模型 %d 个: %s",
                        len(image_configs),
                        ", ".join(_text(c.get("modelName")) or "(无名)" for c in image_configs))

        images: list[dict] = []
        gen_steps: list[dict] = []
        publish_results: list[dict] = []
        total_to_gen = min(image_count, len(polished)) if polished else 0

        # ★ 继续执行模式：复用 state 中已保存的 generated_images 和 publish_results
        #   - 已成功发布(published)的商品：跳过，不重新生图也不重新发布
        #   - 已生成图但发布失败(failed)的商品：复用 img_url，仅重新发布
        #   - 未生成图或缺失的商品：正常走生图+发布流程
        continue_mode = bool(context.get("__continue_mode__"))
        if continue_mode:
            prev_images = state.get("generated_images") or []
            prev_pub_results = state.get("publish_results") or state.get("publish_result") or []
            # 按 idx 建立索引
            prev_img_by_idx: dict[int, dict] = {}
            for img in prev_images:
                try:
                    prev_img_by_idx[int(img.get("index"))] = img
                except (ValueError, TypeError):
                    pass
            prev_pub_by_idx: dict[int, dict] = {}
            for pr in prev_pub_results:
                try:
                    prev_pub_by_idx[int(pr.get("idx"))] = pr
                except (ValueError, TypeError):
                    pass
            # 把已成功发布的 idx 收集起来，循环时跳过
            already_published_idxs: set[int] = set()
            for _idx, pr in prev_pub_by_idx.items():
                if pr.get("status") == "published":
                    already_published_idxs.add(_idx)
            logger.info("[IMAGE_GENERATE-CONTINUE] 继续执行模式：已保存图=%d 已发布结果=%d 已成功发布=%d",
                        len(prev_img_by_idx), len(prev_pub_by_idx), len(already_published_idxs))
        else:
            prev_img_by_idx = {}
            prev_pub_by_idx = {}
            already_published_idxs = set()
        # ★ 生图开始事件：让前端立即知道生图总数，显示"开始生图: 共 N 张"
        try:
            _exec_id = context.get("__execution_id__")
            _wf_id = context.get("__workflow_id__")
            _image_billing_run_identity = _exec_id or build_request_id("workflow_image_run")
            await insert_timeline(db, tenant_id, _exec_id, _wf_id, "IMAGE_GENERATE", "INFO", "live_image_start",
                                  f"开始生图: 共 {total_to_gen} 张",
                                  f"模型数={len(image_configs)} 每张约 50-90 秒，生完即发布",
                                  {"total": total_to_gen, "modelCount": len(image_configs)})
            await db.commit()
        except Exception as exc:
            _log_runtime_failure("persist_image_start", exc)

        # ★ 新流程：每生成一张图后立即发布该商品。
        #   循环前一次性预解析所有账号的 Cookie + publisher 实例（避免重复解析）
        #   循环前一次性解析发布地址（前端预检传入或 user_publish_address 表）
        account_ids = state.get("selected_account_ids") or []
        if not account_ids:
            node_account_ids = config.get("accountIds") or []
            if isinstance(node_account_ids, str):
                account_ids = [a.strip() for a in node_account_ids.split(",") if a.strip()]
            elif isinstance(node_account_ids, list):
                account_ids = node_account_ids
        account_publishers: dict = {}
        if account_ids and polished:
            try:
                account_publishers = await _prepare_account_publishers(db, tenant_id, account_ids, dry_run=False)
                logger.info("[IMAGE_GENERATE] 预解析账号 publishers 数=%d", len(account_publishers))
            except Exception as exc:
                _log_runtime_failure("prepare_image_publishers", exc)

        # 解析扣费用 user_id（取首个账号；IMAGE_GENERATE 节点内 AI 分类建议复用）
        _pub_user_id = None
        if account_ids:
            try:
                # ★ 临时调试日志：排查 AI_USER_UNRESOLVED 根因（确认后删除）
                _dbg_first = account_ids[0]
                logger.warning(
                    "[IMAGE_GENERATE-DEBUG] resolve_user tenant_id=%r account_ids=%r first=%r int(first)=%r polished=%d",
                    tenant_id, account_ids, _dbg_first, (int(_dbg_first) if _dbg_first is not None else None), len(polished),
                )
                _pub_user_id = await _resolve_account_user_id(db, tenant_id, int(account_ids[0]), {})
                logger.warning(
                    "[IMAGE_GENERATE-DEBUG] resolve_user result _pub_user_id=%r",
                    _pub_user_id,
                )
            except Exception as exc:
                # ★ resolve_user 异常：通过 _log_runtime_failure 记录错误类型（不泄露异常详情）
                _log_runtime_failure("resolve_user_for_image_generate", exc)
                _pub_user_id = None
        else:
            logger.warning("[IMAGE_GENERATE-DEBUG] account_ids 为空，无法解析 user_id")
        if polished and not _pub_user_id:
            return {
                "ok": False,
                "images": [],
                "count": 0,
                "errorCode": "AI_USER_UNRESOLVED",
                "errorMessage": "AI 生图无法确定计费用户，请检查工作流账号归属",
                "message": "AI 生图无法确定计费用户，请检查工作流账号归属",
                "artifactType": "image",
                "artifactTitle": "生成图片(计费用户缺失)",
                "artifact": {"prompt": first_prompt, "images": [], "steps": []},
                "steps": [],
            }

        # 解析发布地址
        address_payload = context.get("__address_payload__") or {}
        address_text, address = await _resolve_publish_address(db, tenant_id, address_payload)
        if not address_text:
            # 地址缺失：节点失败，提示用户先配置地址
            _err = "无法确定发布地址。请在工作流运行前的地址预检弹框中选择地址，或在地址管理中添加地址后重新执行。"
            logger.error("[IMAGE_GENERATE] %s", _err)
            return {
                "ok": False, "images": [], "imagePrompt": first_prompt, "count": 0,
                "errorCode": "IMAGE_ADDRESS_REQUIRED",
                "errorMessage": "请先选择完整的商品发布地址",
                "artifactType": "image", "artifactTitle": "生成图片(地址缺失)",
                "artifact": {"prompt": first_prompt, "images": [], "steps": [], "addressError": True},
                "steps": [],
            }
        logger.info("[IMAGE_GENERATE] 发布地址=%s", address_text[:60])

        item_timings = state.setdefault("item_timings", {})

        # ★ 并行执行配置：读取节点配置的并行度（默认3，范围1-5）
        #   parallel_count=1 时退化为顺序执行；>1 时多个商品的生图+发布并行进行
        parallel_count = _safe_int(config.get("parallelCount"), 3)
        parallel_count = max(1, min(5, parallel_count))

        # 预处理继续执行模式中已成功发布的商品（同步处理，不进并行）
        for idx in range(max(total_to_gen, 1)):
            if idx in already_published_idxs:
                prev_img = prev_img_by_idx.get(idx) or {}
                prev_pub = prev_pub_by_idx.get(idx) or {}
                images.append({
                    "index": idx,
                    "url": prev_img.get("url", ""),
                    "prompt": first_prompt,
                    "aiOk": True,
                    "aiReason": "继续执行:复用已成功发布的图",
                    "sourceItemId": prev_img.get("sourceItemId", ""),
                    "sourceTitle": prev_img.get("sourceTitle", ""),
                    "accountId": prev_pub.get("account_id"),
                })
                gen_steps.append({"index": idx, "title": (prev_img.get("sourceTitle") or "")[:40], "aiOk": True, "aiReason": "继续执行:已发布跳过", "imgUrl": (prev_img.get("url") or "")[:100]})
                publish_results.append(prev_pub)
                logger.info("[IMAGE_GENERATE-CONTINUE] idx=%d 已成功发布，跳过", idx)

        # 需要实际并行处理的商品 idx 列表
        pending_idxs = [idx for idx in range(total_to_gen) if idx not in already_published_idxs]
        prompt_mode = _text(config.get("promptMode") or "default").strip().lower() or "default"
        custom_image_prompt = _text(
            config.get("customImagePrompt")
            or config.get("imagePrompt")
            or config.get("firstPrompt")
            or config.get("prompt")
            or ""
        )
        category_prompt_configs: list[dict[str, Any]] = []
        try:
            prompt_rows = (await db.execute(text("""
                SELECT id,status,json_text
                FROM admin_module_record
                WHERE module_key = :module_key AND deleted = 0
                ORDER BY id ASC
            """), {"module_key": "model-config-image-prompts"})).mappings().all()
            raw_prompt_configs: list[dict[str, Any]] = []
            for row in prompt_rows:
                try:
                    raw_json = row.get("json_text")
                    payload = json.loads(raw_json) if raw_json else {}
                    payload["id"] = row.get("id")
                    payload.setdefault("status", row.get("status"))
                    raw_prompt_configs.append(payload)
                except Exception as exc:
                    _log_runtime_failure("parse_image_prompt_config", exc)
            category_prompt_configs = _prepare_image_prompt_category_configs(raw_prompt_configs)
        except Exception as exc:
            _log_runtime_failure("load_image_prompt_config", exc)

        # ★ 连续失败熔断状态变量（在外层初始化，让 if/else 两分支都能访问）
        #   连续 3 次发布失败时置 _circuit_broken=True，未开始的 worker 直接跳过。
        _MAX_CONSECUTIVE_FAIL = 3
        _consecutive_fail_count = 0
        _circuit_broken = False
        _circuit_reason = ""

        if not pending_idxs:
            logger.info("[IMAGE_GENERATE] 所有商品已在继续执行模式中跳过，无需生图")
        else:
            # 并行控制信号量：限制同时执行生图+发布的 worker 数量
            _gen_semaphore = asyncio.Semaphore(parallel_count)
            # 每账号发布锁 + 上次发布时间戳（确保同账号发布间隔 >= publish_interval，默认10秒）
            publish_interval = _safe_int(config.get("publishIntervalSeconds"), 10)
            _account_pub_locks: dict = {}
            _account_last_pub_ts: dict = {}
            for aid in account_ids:
                try:
                    _aid = int(aid)
                    _account_pub_locks[_aid] = asyncio.Semaphore(1)
                    _account_last_pub_ts[_aid] = 0.0
                except (ValueError, TypeError):
                    pass
            # 状态更新锁：保护 images/publish_results 列表追加和 state 写入
            _state_lock = asyncio.Lock()
            _img_done_count = 0
            _img_start_count = 0
            _pub_done_count = 0
            _exec_id = context.get("__execution_id__")
            _wf_id = context.get("__workflow_id__")

            logger.info("[IMAGE_GENERATE] 并行度=%d 待处理=%d 发布间隔=%ds",
                        parallel_count, len(pending_idxs), publish_interval)

            # ★ 单个商品的生图+发布 worker（并行执行）
            #   每个 worker 使用独立的 DB session（AsyncSession 非线程安全）
            #   生图 AI 调用（~50-90s）完全并行；发布通过每账号锁确保间隔
            async def _process_one_item(idx: int):
                nonlocal _img_done_count, _pub_done_count, _img_start_count
                nonlocal _consecutive_fail_count, _circuit_broken, _circuit_reason
                async with _gen_semaphore:
                    # ★ 熔断后未开始的 worker 直接跳过
                    if _circuit_broken:
                        logger.info("[IMAGE_GENERATE-CIRCUIT] idx=%d 因熔断跳过（连续%d次失败）", idx, _consecutive_fail_count)
                        return

                    _t_img_start = time.perf_counter()
                    p = polished[idx] if idx < len(polished) else {}
                    title = _text(p.get("title", f"商品{idx}"))
                    desc = _text(p.get("description", ""))

                    # ★ 发射"正在生图"事件：让前端在生图等待期间（60-130秒）能看到进度在动，避免卡在"开始生图"不动
                    async with _state_lock:
                        _img_start_count += 1
                        _cur_start_idx = _img_start_count
                    try:
                        async with async_session() as _ev_db:
                            await insert_timeline(_ev_db, tenant_id, _exec_id, _wf_id, "IMAGE_GENERATE", "INFO", "image_start",
                                                  f"正在生图: 第 {_cur_start_idx}/{total_to_gen}",
                                                  f"商品[{title[:20]}] 开始调用生图模型",
                                                  {"progress": _cur_start_idx, "total": total_to_gen})
                            await _ev_db.commit()
                    except Exception as exc:
                        _log_runtime_failure("persist_image_item_start", exc)

                    resolved_prompt_text, matched_prompt_category = await _resolve_image_prompt_for_item_with_ai(
                        prompt_mode=prompt_mode,
                        custom_prompt=custom_image_prompt,
                        fallback_prompt=first_prompt,
                        title=title,
                        description=desc,
                        category_prompts=category_prompt_configs,
                        tenant_id=tenant_id,
                        user_id=int(_pub_user_id),
                        request_identity=f"{_image_billing_run_identity}:{idx}:prompt-category",
                    )
                    matched_prompt_category_key = _text((matched_prompt_category or {}).get("categoryKey") or (matched_prompt_category or {}).get("name"))
                    applied_prompt_text = resolved_prompt_text or first_prompt

                    img_url = ""
                    ai_ok = False
                    ai_reason = ""

                    # ★ 继续执行模式：复用已生成的图
                    if continue_mode and idx in prev_img_by_idx:
                        prev_img = prev_img_by_idx[idx]
                        _prev_url = _text(prev_img.get("url"))
                        _prev_ok = bool(prev_img.get("aiOk"))
                        if _prev_url and _prev_ok:
                            img_url = _prev_url
                            ai_ok = True
                            ai_reason = "继续执行:复用已生成的AI封面图"
                        elif _prev_url:
                            img_url = _prev_url
                            ai_ok = False
                            ai_reason = _text(prev_img.get("aiReason")) or "继续执行:复用已失败的生图结果"

                    # 逐个尝试所有启用的生图模型，直到成功
                    # ★ 跟踪本次尝试的模型/尺寸/方法，供回传生图历史使用
                    _attempted_model = ""
                    _attempted_size = "1024x1024"
                    _attempted_method = ""
                    if img_url and ai_ok:
                        logger.info("[IMAGE_GENERATE-CONTINUE] idx=%d 跳过生图模型调用（复用 state）", idx)
                    else:
                        for cfg in image_configs:
                            model_name = _text(cfg.get("modelName") or cfg.get("model") or cfg.get("defaultModel"))
                            if not model_name:
                                continue
                            try:
                                import httpx
                                import base64 as _b64
                                base_url = _text(cfg["baseUrl"]).rstrip("/")
                                if not base_url.endswith("/v1"):
                                    base_url += "/v1"
                                provider_mode = _text(cfg.get("providerMode") or "openai-compatible")
                                cfg_default_prompt = _text(cfg.get("defaultSystemPrompt") or cfg.get("systemPrompt") or "")
                                effective_prompt = resolved_prompt_text or cfg_default_prompt or first_prompt
                                gen_prompt = _compose_final_image_prompt(effective_prompt, title, desc)
                                applied_prompt_text = gen_prompt or effective_prompt or applied_prompt_text
                                skip_pillow_overlay = True

                                raw_size = _text(cfg.get("imageSize") or "1024x1024")
                                img_size = raw_size.split(" ")[0] if " " in raw_size else raw_size
                                if not re.match(r"\d{3,4}x\d{3,4}", img_size):
                                    img_size = "1024x1024"

                                # ★ 跟踪本次尝试的模型/尺寸/方法（每次循环覆盖，最终保留最后尝试的值）
                                _attempted_model = model_name
                                _attempted_size = img_size
                                _attempted_method = provider_mode

                                image_billing_request_id = build_stable_request_id(
                                    "workflow_image",
                                    tenant_id,
                                    _image_billing_run_identity,
                                    idx,
                                    cfg.get("__module_key__") or cfg.get("providerName") or base_url,
                                    model_name,
                                    provider_mode,
                                )
                                await precheck_ai_usage({
                                    "tenantId": tenant_id,
                                    "userId": int(_pub_user_id),
                                    "scene": "workflow_image",
                                    "providerName": _text(cfg.get("providerName")) or "default",
                                    "modelName": model_name,
                                    "modelType": "image",
                                    "billingMode": "spec",
                                    "imageCount": 1,
                                    "specKey": img_size,
                                    "requestId": image_billing_request_id,
                                })

                                if provider_mode == "chat-completions-image":
                                    size_hint = "\n\n----------------------------\n\nIMAGE SIZE CONSTRAINT\nThe output image MUST be a perfect square (1:1 aspect ratio, e.g. 1024x1024).\nDo NOT generate portrait or landscape images.\nAspect ratio: 1:1 (width equals height).\n"
                                    if size_hint not in gen_prompt:
                                        gen_prompt = gen_prompt + size_hint
                                    chat_payload = {
                                        "model": model_name,
                                        "messages": [{"role": "user", "content": gen_prompt}],
                                        "modalities": ["text", "image"],
                                        "stream": False,
                                    }
                                    req_headers = {
                                        "Authorization": f"Bearer {cfg['apiKey']}",
                                        "Content-Type": "application/json",
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                        "Accept": "*/*",
                                    }
                                    status_code, data = await _post_provider_json_bounded(
                                        f"{base_url}/chat/completions",
                                        payload=chat_payload,
                                        headers=req_headers,
                                        timeout_seconds=180,
                                        max_response_bytes=8 * 1024 * 1024,
                                    )
                                    if 200 <= status_code < 300:
                                        await charge_image_usage(
                                            tenant_id=tenant_id,
                                            user_id=int(_pub_user_id),
                                            scene="workflow_image",
                                            provider_name=_text(cfg.get("providerName")) or "default",
                                            model_name=model_name,
                                            image_count=1,
                                            spec_key=img_size,
                                            request_id=image_billing_request_id,
                                            raw_usage=data.get("usage") if isinstance(data, dict) else {},
                                        )
                                        choices = data.get("choices") or []
                                        content_str = ""
                                        if choices:
                                            msg = choices[0].get("message") or {}
                                            content_str = _text(msg.get("content"))
                                        _b64_match = re.search(r"data:image/(\w+);base64,([A-Za-z0-9+/=]+)", content_str)
                                        if _b64_match:
                                            encoded_image = _b64_match.group(2)
                                            max_encoded_chars = ((MAX_IMAGE_BYTES + 2) // 3) * 4
                                            if len(encoded_image) > max_encoded_chars:
                                                raise ValueError("generated image exceeds the size limit")
                                            img_bytes = _b64.b64decode(encoded_image, validate=True)
                                            if img_bytes and len(img_bytes) > 100:
                                                if skip_pillow_overlay:
                                                    img_url = await _save_image_bytes_direct(
                                                        img_bytes, title, tenant_id,
                                                        _safe_int(context.get("__user_id__"), 0) or None,
                                                    )
                                                else:
                                                    processed = _add_cover_text_overlay(img_bytes, title, desc)
                                                    img_url = await _save_image_bytes_direct(
                                                        processed, title, tenant_id,
                                                        _safe_int(context.get("__user_id__"), 0) or None,
                                                    )
                                                if img_url:
                                                    ai_ok = True
                                                    ai_reason = f"生图模型({model_name})生成成功[chat]"
                                                    logger.info("[IMAGE_GENERATE] idx=%d 生图成功[chat] model=%s", idx, model_name)
                                                    break
                                            else:
                                                ai_reason = f"模型({model_name})返回空图片数据"
                                        else:
                                            ai_reason = f"模型({model_name})响应中未找到图片"
                                    else:
                                        ai_reason = "AI 封面图生成失败，请稍后重试"
                                else:
                                    payload = {
                                        "model": model_name,
                                        "prompt": gen_prompt,
                                        "n": 1,
                                        "size": img_size,
                                        "response_format": "url",
                                    }
                                    quality_cfg = _text(cfg.get("quality") or "")
                                    if quality_cfg and "标准" not in quality_cfg:
                                        payload["quality"] = "hd"
                                    status_code, data = await _post_provider_json_bounded(
                                        f"{base_url}/images/generations",
                                        payload=payload,
                                        headers={"Authorization": f"Bearer {cfg['apiKey']}"},
                                        timeout_seconds=180,
                                        max_response_bytes=8 * 1024 * 1024,
                                    )
                                    if 200 <= status_code < 300:
                                        await charge_image_usage(
                                            tenant_id=tenant_id,
                                            user_id=int(_pub_user_id),
                                            scene="workflow_image",
                                            provider_name=_text(cfg.get("providerName")) or "default",
                                            model_name=model_name,
                                            image_count=1,
                                            spec_key=img_size,
                                            request_id=image_billing_request_id,
                                            raw_usage=data.get("usage") if isinstance(data, dict) else {},
                                        )
                                        data_list = data.get("data") or []
                                        raw_img_url = _text(data_list[0].get("url", "")) if data_list else ""
                                        if raw_img_url:
                                            if skip_pillow_overlay:
                                                downloaded = await download_public_image(raw_img_url)
                                                img_url = await _save_image_bytes_direct(
                                                    downloaded.content, title, tenant_id,
                                                    _safe_int(context.get("__user_id__"), 0) or None,
                                                )
                                            else:
                                                img_url = await _download_and_overlay_image(
                                                    raw_img_url, title, desc, tenant_id,
                                                    _safe_int(context.get("__user_id__"), 0) or None,
                                                )
                                            if img_url:
                                                ai_ok = True
                                                ai_reason = f"生图模型({model_name})生成成功"
                                                logger.info("[IMAGE_GENERATE] idx=%d 生图成功 model=%s", idx, model_name)
                                                break
                                            ai_reason = f"生图模型({model_name})返回的图片未通过安全校验"
                                        else:
                                            ai_reason = f"模型({model_name})返回空URL"
                                    else:
                                        ai_reason = "AI 封面图生成失败，请稍后重试"
                            except AiBillingError:
                                raise
                            except PublicRuntimeError as exc:
                                await charge_image_usage(
                                    tenant_id=tenant_id,
                                    user_id=int(_pub_user_id),
                                    scene="workflow_image",
                                    provider_name=_text(cfg.get("providerName")) or "default",
                                    model_name=model_name,
                                    image_count=1,
                                    spec_key=img_size,
                                    request_id=image_billing_request_id,
                                    raw_usage={},
                                )
                                ai_reason = exc.public_message
                                _log_runtime_failure("generate_product_image_invalid_response", exc)
                            except Exception as e:
                                ai_reason = "AI 封面图生成失败，请稍后重试"
                                _log_runtime_failure("generate_product_image", e)
                        else:
                            if image_configs:
                                ai_reason = f"全部{len(image_configs)}个生图模型均失败: {ai_reason}"
                            else:
                                ai_reason = "未配置启用的生图模型"
                            logger.error(
                                "[IMAGE_GENERATE] idx=%d 生图失败 reasonLen=%d",
                                idx,
                                len(ai_reason),
                            )

                    # ★ 生图结果回传 Java core-api 落库（fire-and-forget，不阻塞工作流主流程）
                    #   即使失败也不影响生图+发布流程，仅记录警告
                    try:
                        await _record_workflow_image_history(
                            tenant_id=tenant_id,
                            user_id=int(_pub_user_id),
                            request_id=build_request_id("workflow_image_record"),
                            model=_attempted_model,
                            prompt=applied_prompt_text or "",
                            size=_attempted_size,
                            image_url=img_url,
                            method=_attempted_method,
                            workflow_id=_safe_int(_wf_id) if _wf_id else None,
                            workflow_execution_id=_safe_int(_exec_id) if _exec_id else None,
                            workflow_node_key="IMAGE_GENERATE",
                            status="success" if ai_ok else "failed",
                            error_message="" if ai_ok else ai_reason,
                        )
                    except Exception as _cb_exc:
                        _log_runtime_failure("record_workflow_image_history_call", _cb_exc)

                    _img_ms = int((time.perf_counter() - _t_img_start) * 1000)
                    _image_dict = {
                        "index": idx,
                        "url": img_url,
                        "prompt": applied_prompt_text,
                        "aiOk": ai_ok,
                        "errorCode": "" if ai_ok else "IMAGE_PROVIDER_FAILED",
                        "aiReason": ai_reason,
                        "sourceItemId": _text(p.get("itemId", "")),
                        "sourceTitle": title,
                        "accountId": p.get("accountId"),
                        "promptMode": prompt_mode,
                        "promptCategory": matched_prompt_category_key,
                    }
                    _gen_step_dict = {
                        "index": idx,
                        "title": title[:40],
                        "aiOk": ai_ok,
                        "errorCode": "" if ai_ok else "IMAGE_PROVIDER_FAILED",
                        "aiReason": ai_reason,
                        "imgUrl": img_url[:100],
                        "promptMode": prompt_mode,
                        "promptCategory": matched_prompt_category_key,
                    }

                    # ★ 线程安全地更新共享状态 + 发送生图进度事件
                    async with _state_lock:
                        _img_done_count += 1
                        images.append(_image_dict)
                        gen_steps.append(_gen_step_dict)
                        item_timings.setdefault(idx, {})["image_generate_ms"] = _img_ms
                        state["generated_images"] = images
                    # 用独立 session 写生图进度事件（AsyncSession 非线程安全）
                    try:
                        async with async_session() as _ev_db:
                            await save_state_variable(_ev_db, tenant_id, _exec_id, "IMAGE_GENERATE", "generated_images", images, "json")
                            await insert_timeline(_ev_db, tenant_id, _exec_id, _wf_id, "IMAGE_GENERATE", "INFO", "image_progress",
                                                  f"生图进度: {_img_done_count}/{total_to_gen}",
                                                  f"idx={idx} {'成功' if ai_ok else '失败'} 耗时={_img_ms}ms",
                                                  {"progress": _img_done_count, "total": total_to_gen, "aiOk": ai_ok})
                            await _ev_db.commit()
                    except Exception as exc:
                        _log_runtime_failure("persist_image_progress", exc)

                    # ★ 生图成功后立即发布（生图失败则跳过发布）
                    if polished and idx < len(polished):
                        p_pub = polished[idx]
                        acct_id_raw = p_pub.get("accountId")
                        try:
                            acct_id = int(acct_id_raw) if acct_id_raw is not None else (int(account_ids[0]) if account_ids else 1)
                        except (ValueError, TypeError):
                            acct_id = 1
                        account_pub = account_publishers.get(acct_id) or {}

                        # 用 AI 封面图识别分类（独立 session）
                        category = ""
                        try:
                            async with async_session() as _cat_db:
                                category = await _resolve_category_by_image(_cat_db, tenant_id, img_url, title, user_id=_pub_user_id)
                        except Exception:
                            category = ""

                        # ★ 发布：每账号锁确保同账号发布间隔 >= publish_interval
                        _acct_lock = _account_pub_locks.get(acct_id)
                        if _acct_lock:
                            async with _acct_lock:
                                _now = time.monotonic()
                                _last_ts = _account_last_pub_ts.get(acct_id, 0.0)
                                if _last_ts > 0 and (_now - _last_ts) < publish_interval:
                                    await asyncio.sleep(publish_interval - (_now - _last_ts))
                                async with async_session() as _pub_db:
                                    pub_result = await _publish_single_item(
                                        _pub_db, tenant_id, context, state, p_pub, img_url, ai_ok,
                                        category, address_text, address,
                                        account_pub, acct_id, _text(config.get("platform") or "xianyu"), idx,
                                    )
                                _account_last_pub_ts[acct_id] = time.monotonic()
                        else:
                            async with async_session() as _pub_db:
                                pub_result = await _publish_single_item(
                                    _pub_db, tenant_id, context, state, p_pub, img_url, ai_ok,
                                    category, address_text, address,
                                    account_pub, acct_id, _text(config.get("platform") or "xianyu"), idx,
                                )

                        _pub_status = pub_result.get("status", "")
                        _pub_ms = pub_result.get("publish_ms", 0)

                        # ★ 线程安全地更新发布结果 + 发送生图+发布进度事件
                        #   并同步更新连续失败熔断计数（失败 +1，成功清零，>=3 触发熔断）
                        _circuit_just_broken = False
                        _pub_err_msg = _text(pub_result.get("error"))
                        async with _state_lock:
                            _pub_done_count += 1
                            publish_results.append(pub_result)
                            state["publish_results"] = publish_results
                            _cur_img_done = _img_done_count
                            _cur_pub_done = _pub_done_count
                            # ★ 熔断计数：仅统计真正发布失败（不含 skipped_* / saved_as_draft）
                            #   draft_only 模式下 saved_as_draft 视为成功（清零失败计数）
                            if _pub_status == "failed":
                                _consecutive_fail_count += 1
                                if not _circuit_broken and _consecutive_fail_count >= _MAX_CONSECUTIVE_FAIL:
                                    _circuit_broken = True
                                    _circuit_reason = f"连续{_consecutive_fail_count}次发布失败，已熔断。最后错误: {_pub_err_msg[:200]}"
                                    _circuit_just_broken = True
                            elif _pub_status in ("published", "saved_as_draft"):
                                _consecutive_fail_count = 0
                            # skipped_* 不计入失败也不清零，保持中性
                        try:
                            async with async_session() as _ev_db:
                                await save_state_variable(_ev_db, tenant_id, _exec_id, "IMAGE_GENERATE", "publish_results", publish_results, "json")
                                # ★ 进度描述：区分 saved_as_draft（已存草稿）与其他状态
                                if _pub_status == "saved_as_draft":
                                    _pub_desc = "已存草稿"
                                elif _pub_status == "published":
                                    _pub_desc = "发布成功"
                                elif _pub_status == "failed":
                                    _pub_desc = "发布失败"
                                elif _pub_status.startswith("skipped"):
                                    _pub_desc = "跳过"
                                else:
                                    _pub_desc = _pub_status
                                await insert_timeline(_ev_db, tenant_id, _exec_id, _wf_id, "IMAGE_GENERATE", "INFO", "image_and_publish_progress",
                                      f"生图+发布进度: 生图 {_cur_img_done}/{total_to_gen}，发布 {_cur_pub_done}/{total_to_gen}",
                                      f"商品[{title[:20]}] 生图{'成功' if ai_ok else '失败'} {_pub_desc}",
                                      {
                                          "imageProgress": _cur_img_done, "imageTotal": total_to_gen,
                                          "publishProgress": _cur_pub_done, "publishTotal": total_to_gen,
                                          "aiOk": ai_ok, "publishStatus": _pub_status,
                                          "accountId": acct_id, "publishMs": _pub_ms,
                                          "parallelCount": parallel_count,
                                      })
                                # ★ 熔断事件单独发送 WARN 级别时间线，便于前端展示
                                if _circuit_just_broken:
                                    await insert_timeline(_ev_db, tenant_id, _exec_id, _wf_id, "IMAGE_GENERATE", "WARN", "publish_circuit_broken",
                                          f"连续{_MAX_CONSECUTIVE_FAIL}次发布失败，已熔断终止后续发布",
                                          _circuit_reason,
                                          {"consecutiveFailCount": _consecutive_fail_count, "maxAllowed": _MAX_CONSECUTIVE_FAIL,
                                           "lastError": _pub_err_msg[:300]})
                                await _ev_db.commit()
                        except Exception as exc:
                            _log_runtime_failure("persist_image_publish_progress", exc)
                        if _circuit_just_broken:
                            logger.error(
                                "[IMAGE_GENERATE-CIRCUIT] reasonLen=%d",
                                len(_circuit_reason),
                            )

            # 并行调度所有 pending 商品
            _tasks = [asyncio.create_task(_process_one_item(idx)) for idx in pending_idxs]
            _results = await asyncio.gather(*_tasks, return_exceptions=True)
            for _r in _results:
                if isinstance(_r, Exception):
                    _log_runtime_failure("image_generate_worker", _r)

            if any(isinstance(_r, AiBillingPaymentRequired) for _r in _results):
                # ★ 余额不足时，若已有部分图片生成或发布，标记 partial=True，
                #   使 execute_workflow 将节点标记为 partial_success 而非 failed，
                #   重试时会重新执行该节点以复用已产出的结果。
                _has_partial = bool(images) or bool(publish_results)
                _pub_ok = sum(1 for r in publish_results if r.get("status") == "published")
                # ★ 保存已产出结果到 state，确保重试时能复用
                state["generated_images"] = images
                state["publish_results"] = publish_results
                return {
                    "ok": False,
                    "errorCode": "AI_BALANCE_INSUFFICIENT",
                    "errorMessage": "AI Token 余额不足，请充值后重试",
                    "message": "AI Token 余额不足，请充值后重试",
                    "partial": _has_partial,
                    "images": images,
                    "count": len(images),
                    "publishResults": publish_results,
                    "successCount": _pub_ok,
                    "failedCount": len(pending_idxs) - _pub_ok,
                    "steps": gen_steps,
                }
            if any(isinstance(_r, AiBillingError) for _r in _results):
                _has_partial = bool(images) or bool(publish_results)
                _pub_ok = sum(1 for r in publish_results if r.get("status") == "published")
                state["generated_images"] = images
                state["publish_results"] = publish_results
                return {
                    "ok": False,
                    "errorCode": "AI_BILLING_UNAVAILABLE",
                    "errorMessage": "AI 计费服务暂不可用，生图与发布已停止，请稍后重试",
                    "message": "AI 计费服务暂不可用，生图与发布已停止，请稍后重试",
                    "partial": _has_partial,
                    "images": images,
                    "count": len(images),
                    "publishResults": publish_results,
                    "successCount": _pub_ok,
                    "failedCount": len(pending_idxs) - _pub_ok,
                    "steps": gen_steps,
                }

            # 按 idx 排序确保输出顺序一致
            images.sort(key=lambda x: x.get("index", 0))
            gen_steps.sort(key=lambda x: x.get("index", 0))
            publish_results.sort(key=lambda x: x.get("idx", 0))
            state["generated_images"] = images
            state["publish_results"] = publish_results

        ai_success_count = sum(1 for i in images if i.get("aiOk"))
        pub_success_count = sum(1 for r in publish_results if r.get("status") == "published")
        pub_failed_count = sum(1 for r in publish_results if r.get("status") == "failed")
        pub_skipped_ai = sum(1 for r in publish_results if r.get("status") == "skipped_no_ai_image")
        pub_skipped_dup = sum(1 for r in publish_results if r.get("status") == "skipped_duplicate")
        # ★ 草稿模式统计：saved_as_draft 是 draft_only 模式下生图后存入草稿箱的商品
        pub_saved_draft_count = sum(1 for r in publish_results if r.get("status") == "saved_as_draft")
        logger.info("[IMAGE_GENERATE] 生图+发布完成 生图成功=%d/%d 发布成功=%d 失败=%d 无AI图跳过=%d 重复跳过=%d 存草稿=%d 熔断=%s",
                    ai_success_count, len(images), pub_success_count, pub_failed_count, pub_skipped_ai, pub_skipped_dup,
                    pub_saved_draft_count, _circuit_broken)

        # 节点状态：有发布成功/已存草稿=ok；有部分失败=partial；全部失败=failed
        # ★ 熔断触发时强制判 failed（即使有部分成功也认为是异常终止）
        # ★ draft_only 模式下若全部为 saved_as_draft，节点判成功
        if _circuit_broken:
            node_ok = False
            partial = False
        elif pub_saved_draft_count > 0 and pub_success_count == 0 and pub_failed_count == 0:
            # 草稿模式：所有商品均已存入草稿箱
            node_ok = True
            partial = False
        elif pub_success_count > 0 and (pub_failed_count > 0 or pub_skipped_ai > 0 or pub_skipped_dup > 0):
            node_ok = True
            partial = True
        elif pub_success_count > 0:
            node_ok = True
            partial = False
        else:
            node_ok = False
            partial = False

        # 若所有生图失败，节点判失败
        if images and ai_success_count == 0:
            return {
                "ok": False, "images": images, "imagePrompt": first_prompt,
                "count": len(images),
                "publishResults": publish_results,
                "errorCode": "IMAGE_PROVIDER_FAILED",
                "errorMessage": "AI 封面图生成失败，请稍后重试",
                "artifactType": "image", "artifactTitle": "生成图片(全部失败)",
                "artifact": {"prompt": first_prompt, "images": images, "steps": gen_steps, "allFailed": True, "publishResults": publish_results},
                "steps": gen_steps,
            }

        # ★ 熔断终止：节点判失败，errorMessage 包含熔断原因
        #   注意：此时已生成的图片和成功的发布都正常返回，便于继续执行时复用
        if _circuit_broken:
            _circuit_msg = "连续发布失败已触发保护，请检查账号与商品配置后重试"
            return {
                "ok": False,
                "errorCode": "PUBLISH_CIRCUIT_OPEN",
                "partial": pub_success_count > 0,
                "images": images, "imagePrompt": first_prompt,
                "count": len(images),
                "publishResults": publish_results,
                "publishSuccessCount": pub_success_count,
                "publishFailedCount": pub_failed_count,
                "publishSkippedAiCount": pub_skipped_ai,
                "publishSkippedDuplicateCount": pub_skipped_dup,
                "circuitBroken": True,
                "consecutiveFailCount": _consecutive_fail_count,
                "errorMessage": _circuit_msg,
                "message": _circuit_msg,
                "artifactType": "image", "artifactTitle": "生图+发布结果(已熔断)",
                "artifact": {"prompt": first_prompt, "images": images, "steps": gen_steps, "publishResults": publish_results,
                             "publishSuccessCount": pub_success_count, "publishFailedCount": pub_failed_count,
                             "publishSkippedAiCount": pub_skipped_ai, "publishSkippedDuplicateCount": pub_skipped_dup,
                             "circuitBroken": True, "consecutiveFailCount": _consecutive_fail_count, "circuitReason": _circuit_reason},
                "steps": gen_steps,
            }

        # 构造汇总消息
        msg_parts = []
        if pub_saved_draft_count > 0:
            msg_parts.append(f"已生图 {ai_success_count} 张，存入草稿箱 {pub_saved_draft_count} 个")
        else:
            msg_parts.append(f"已生图 {ai_success_count} 张，发布成功 {pub_success_count} 个")
        if pub_failed_count:
            msg_parts.append(f"{pub_failed_count}个发布失败")
        if pub_skipped_ai:
            msg_parts.append(f"{pub_skipped_ai}个无AI封面图已阻止")
        if pub_skipped_dup:
            msg_parts.append(f"{pub_skipped_dup}个重复已跳过")

        return {
            "ok": node_ok,
            "errorCode": "" if node_ok else "IMAGE_PUBLISH_NO_SUCCESS",
            "partial": partial,
            "images": images, "imagePrompt": first_prompt,
            "count": len(images),
            "publishResults": publish_results,
            "publishSuccessCount": pub_success_count,
            "publishFailedCount": pub_failed_count,
            "publishSkippedAiCount": pub_skipped_ai,
            "publishSkippedDuplicateCount": pub_skipped_dup,
            "savedAsDraftCount": pub_saved_draft_count,
            "message": "，".join(msg_parts),
            "artifactType": "image",
            "artifactTitle": "生图+存草稿结果" if pub_saved_draft_count > 0 and pub_success_count == 0 else "生图+发布结果",
            "artifact": {"prompt": first_prompt, "images": images, "steps": gen_steps, "publishResults": publish_results,
                         "publishSuccessCount": pub_success_count, "publishFailedCount": pub_failed_count,
                         "publishSkippedAiCount": pub_skipped_ai, "publishSkippedDuplicateCount": pub_skipped_dup,
                         "savedAsDraftCount": pub_saved_draft_count},
            "steps": gen_steps,
        }

    if typ in {"text_rewrite", "rewrite", "润色", "ai_text", "product_polish", "PRODUCT_POLISH"}:
        # 润色节点：AI 逐商品润色文案
        #   优先级：用户自定义提示词 > 润色风格(tone)
        user_prompt = _text(config.get("userPrompt") or "")
        tone = _text(config.get("tone") or config.get("style") or config.get("text") or "闲鱼爆款")
        polish_style = user_prompt if user_prompt else tone

        # 获取待润色的商品列表
        items_to_polish = state.get("selected_products", [])
        if not items_to_polish:
            for v in context.values():
                if isinstance(v, dict) and isinstance(v.get("items"), list):
                    items_to_polish = v.get("items")
                    break

        # ★ 多账号支持：获取账号列表，每个商品为每个账号生成一个独立润色版本
        account_ids = state.get("selected_account_ids") or []
        if not account_ids:
            single_acct = state.get("selected_account_id")
            account_ids = [single_acct] if single_acct else []
        if not account_ids:
            account_ids = [1]  # 兜底

        logger.info("[PRODUCT_POLISH] 开始润色 items=%d accounts=%d (总版本=%d) style=%s",
                     len(items_to_polish), len(account_ids), len(items_to_polish) * len(account_ids), polish_style[:30])

        # ★ 读取润色强限制（来自后台「通用模型配置」的润色关键词/禁止关键词，前台不可见、不可改）
        #   默认禁止「盗版、破解版、毕设」；管理员可在后台追加更多禁止词或必含词。
        #   在循环外读取一次，供 _call_ai_and_parse 中的 system prompt 使用。
        _polish_restriction_str = ""
        try:
            _polish_restriction_str = await get_polish_keywords_restriction()
        except Exception as exc:
            _log_runtime_failure("load_polish_restrictions", exc)

        # ★ 读取禁止词列表（用于质量评分硬校验，命中则强制重试）
        #   与 _polish_restriction_str 同源，但返回纯列表供 validate_polish_output 使用。
        _polish_forbidden_list: list[str] = []
        try:
            _polish_forbidden_list = await get_polish_forbidden_keywords()
        except Exception as exc:
            _log_runtime_failure("load_polish_forbidden_keywords", exc)

        # 解析扣费用 user_id（取首个账号；润色节点内部 AI 调用复用，循环外解析一次）
        _pp_account_ids = account_ids
        _pp_user_id = None
        if _pp_account_ids:
            try:
                _pp_user_id = await _resolve_account_user_id(db, tenant_id, int(_pp_account_ids[0]), {})
            except Exception as exc:
                _log_runtime_failure("resolve_product_polish_user", exc)
                _pp_user_id = None
        if items_to_polish and not _pp_user_id:
            return {
                "ok": False,
                "errorCode": "AI_USER_UNRESOLVED",
                "message": "AI 润色无法确定计费用户，请检查工作流账号归属",
                "polished": [],
            }

        polished = []
        polish_steps = []
        item_timings = state.setdefault("item_timings", {})
        global_version_idx = 0  # 全局版本序号，用于 item_timings key
        _polish_run_identity = context.get("__execution_id__") or build_request_id("product_polish_run")

        # ★ 内部函数：构建润色提示词（支持重试时附加失败原因）
        def _build_polish_prompt(t_raw: str, d_raw: str, style: str, retry_reasons: list = None) -> str:
            prompt = (
                f"你是一名闲鱼爆款商品文案改写专家。下面给你一个**对方店铺**的商品信息（标题+文案），"
                f"请你参考对方的标题和文案，改写出一份**适合本账号发布**的新标题和新文案。\n\n"
                f"=== 对方商品信息（仅供参考，不得照抄）===\n"
                f"对方标题：{t_raw}\n"
                f"对方文案：\n{d_raw}\n\n"
                f"=== 改写要求（必须严格遵守）===\n"
                f"1. **标题改写**：基于对方标题改写，保留核心关键词（如软件名、版本号、适用系统等），"
                f"但必须重新组织语言，不得原样复制。新标题不超过 30 个字，要包含关键搜索词。\n"
                f"2. **文案改写**：参考对方文案的结构和卖点，改写出相似度 70% 以上的新文案（保留对方文案的核心结构、卖点顺序、"
                f"重点信息），但用词要重新组织，不要整段照搬。\n"
                f"3. **必须删除的元数据**：对方标题/文案中所有属于其他店铺的标识必须彻底清除：\n"
                f"   - 店铺名/作者署名/水印（如\"LateSunday\"、\"雨夜电玩社\"、\"XX工作室\"等）\n"
                f"   - 历史成交数据（如\"302人想要\"、\"249人收藏\"、\"XX人付款\"等）\n"
                f"   - 联系方式（QQ/微信/网址）\n"
                f"   - 关注引导（如\"关注店铺\"、\"点我头像\"）\n"
                f"   - 价格符号残留（¥/￥/RMB）\n"
                f"4. **文案结构**：参考下方合格示例，使用清晰的段落和换行，让买家一眼看清卖点。\n"
                f"5. **风格**：{style}\n"
                f"6. 严禁输出解释、分析、备注、代码块标记。\n\n"
                f"=== 合格示例（请模仿此结构和质量）===\n"
                f"标题：pr软件2026一键安装premiere视频剪辑中英文版mac原版\n"
                f"文案：\n"
                f"pr软件2026一键安装premiere视频剪辑中英文版mac原版2025M1-5\n\n"
                f"（拍下秒发）pr一键安装软件2026版本，2017-2026win一键安装 带教程\n\n"
                f"支持系统：win/mac(安装包)\n\n"
                f"【发货方式】24h自动发货\n"
                f"1、百度网盘下载\n"
                f"2、夸克网盘下载\n\n"
                f"虚拟物品售出不退不换\n\n"
                f"=== 不合格反例（绝对不能生成这种内容）===\n"
                f"❌ 标题中保留\"LateSunday\"等对方店铺名\n"
                f"❌ 标题或文案中保留\"302人想要\"\"249人收藏\"等对方店铺数据\n"
                f"❌ 标题与对方标题完全相同（未改写）\n"
                f"❌ 文案与对方文案完全相同（未改写）\n"
                f"❌ 文案中出现\"口语化：\"等明显是源商品爬取残留的内容\n"
                f"❌ 文案过短（少于 30 字）\n\n"
                f"请按 JSON 返回，格式必须是：\n"
                f'{{"title":"优化后的标题","body":"优化后的正文"}}\n'
            )
            # ★ 重试时附加失败原因，让 AI 知道上次哪里没做好
            if retry_reasons:
                prompt += (
                    f"\n=== 上次生成内容质量不合格，具体问题 ===\n"
                    f"{'; '.join(retry_reasons)}\n"
                    f"请务必避免上述问题，重新生成一份合格的内容。\n"
                )
            return prompt

        # ★ 内部函数：调用 AI 并解析响应，返回 (title, body, ok, source, reason, response_text)
        async def _call_ai_and_parse(prompt: str, request_identity: str) -> tuple[str, str, bool, str, str, str]:
            nonlocal _ai_provider
            ai_response_text: str = ""
            ai_source = "none"
            ai_reason = "未调用模型"
            # 润色 system prompt：基础指令 + 强限制（禁止词/必含词，来自后台通用模型配置）
            _base_sys = "你是一个闲鱼商品文案优化助手。根据原始商品信息和指定风格，生成优化后的标题和描述文案。返回格式：标题：[标题]\\n正文：[正文]"
            _polish_sys_prompt = _base_sys + ("\n" + _polish_restriction_str if _polish_restriction_str else "")

            # 1) 优先使用数据库配置的 AI Provider
            if _ai_provider and _ai_provider.base_url and _ai_provider.api_key:
                try:
                    import httpx
                    _base_url = _ai_provider.base_url.rstrip("/")
                    if not _base_url.endswith("/v1"):
                        _base_url += "/v1"
                    _db_billing_id = build_stable_request_id(
                        "product_polish_db",
                        tenant_id,
                        _pp_user_id,
                        request_identity,
                        _ai_provider.provider_name,
                        _ai_provider.model_name,
                    )
                    await precheck_ai_usage({
                        "tenantId": tenant_id,
                        "userId": int(_pp_user_id),
                        "scene": "product_polish",
                        "providerName": _text(_ai_provider.provider_name) or "default",
                        "modelName": _text(_ai_provider.model_name) or "default",
                        "modelType": "chat",
                        "promptTokens": estimate_text_tokens(prompt),
                        "completionTokens": 0,
                        "requestId": _db_billing_id,
                    })
                    _payload = {
                        "model": _ai_provider.model_name,
                        "temperature": 0.3,
                        "messages": [
                            {"role": "system", "content": _polish_sys_prompt},
                            {"role": "user", "content": prompt},
                        ],
                    }
                    try:
                        _status_code, _data = await _post_provider_json_bounded(
                            f"{_base_url}/chat/completions",
                            payload=_payload,
                            headers={"Authorization": f"Bearer {_ai_provider.api_key}"},
                            timeout_seconds=60,
                            max_response_bytes=2 * 1024 * 1024,
                        )
                    except PublicRuntimeError as _provider_error:
                        if _provider_error.error_code == "AI_PROVIDER_RESPONSE_TOO_LARGE":
                            await charge_text_usage(
                                tenant_id=tenant_id, user_id=int(_pp_user_id), scene="product_polish",
                                provider_name=_text(_ai_provider.provider_name) or "default",
                                model_name=_text(_ai_provider.model_name) or "default",
                                prompt=prompt, completion="",
                                request_id=_db_billing_id,
                                raw_usage={},
                            )
                        raise
                    if 200 <= _status_code < 300:
                        _choices = _data.get("choices") or []
                        if _choices:
                            ai_response_text = _text(
                                (_choices[0].get("message") or {}).get("content")
                                or _choices[0].get("text")
                                or ""
                            ).strip()
                            ai_source = "db_provider"
                            ai_reason = "数据库模型配置调用成功" if ai_response_text else "数据库模型返回空内容"
                        await charge_text_usage(
                            tenant_id=tenant_id, user_id=int(_pp_user_id), scene="product_polish",
                            provider_name=_text(_ai_provider.provider_name) or "default",
                            model_name=_text(_ai_provider.model_name) or "default",
                            prompt=prompt, completion=ai_response_text,
                            request_id=_db_billing_id,
                            raw_usage=_data.get("usage") or {},
                        )
                        logger.info("[PRODUCT_POLISH] DB-AI响应 provider=%s model=%s len=%d",
                                     _ai_provider.provider_name, _ai_provider.model_name, len(ai_response_text))
                    else:
                        logger.warning(
                            "[PRODUCT_POLISH] DB-AI HTTP status=%d responseBytes=%d",
                            _status_code,
                            0,
                        )
                except AiBillingError:
                    raise
                except Exception as _e:
                    # Never reuse a provider result when any part of the call or
                    # its charge path failed unexpectedly.
                    ai_response_text = ""
                    ai_source = "db_provider"
                    ai_reason = "数据库模型调用失败"
                    _log_runtime_failure("polish_product_with_database_provider", _e)

            # 2) 回退到环境变量配置
            if not ai_response_text:
                try:
                    _fallback_billing_id = build_stable_request_id(
                        "product_polish_env",
                        tenant_id,
                        _pp_user_id,
                        request_identity,
                    )
                    await precheck_ai_usage({
                        "tenantId": tenant_id,
                        "userId": int(_pp_user_id),
                        "scene": "product_polish",
                        "providerName": "default",
                        "modelName": "default",
                        "modelType": "chat",
                        "promptTokens": estimate_text_tokens(prompt),
                        "completionTokens": 0,
                        "requestId": _fallback_billing_id,
                    })
                    _fallback = await generate_text(
                        "product_polish",
                        _polish_sys_prompt,
                        prompt,
                        0.3,
                        request_id=_fallback_billing_id,
                    )
                    if _fallback.get("ok") is not False:
                        ai_response_text = _text(_fallback.get("content", "")).strip()
                        ai_source = "env_provider"
                        ai_reason = "环境变量模型配置调用成功" if ai_response_text else "环境变量模型返回空内容"
                    else:
                        ai_source = "env_provider"
                        ai_reason = "AI 润色服务暂时不可用"
                    if ai_response_text:
                        logger.info("[PRODUCT_POLISH] 回退generate_text响应 len=%d", len(ai_response_text))
                        await charge_text_usage(
                            tenant_id=tenant_id, user_id=int(_pp_user_id), scene="product_polish",
                            provider_name=_text(_fallback.get("provider")) or "default",
                            model_name=_text(_fallback.get("model")) or "default",
                            prompt=prompt, completion=ai_response_text,
                            request_id=_fallback_billing_id,
                            raw_usage=_fallback.get("usage") or {},
                        )
                except AiBillingError:
                    raise
                except Exception as exc:
                    ai_response_text = ""
                    ai_reason = "AI 润色服务暂时不可用"
                    _log_runtime_failure("polish_product_with_environment_provider", exc)

            # 3) 解析 AI 响应
            p_title = ""
            p_body = ""
            p_ok = False
            if ai_response_text:
                content_text = ai_response_text.strip()

                # JSON: {"title":"...","body":"..."}
                try:
                    json_match = re.search(r"\{[\s\S]*\}", content_text)
                    json_text = json_match.group(0) if json_match else content_text
                    parsed_json = json.loads(json_text)
                    if isinstance(parsed_json, dict):
                        pt = _text(parsed_json.get("title") or parsed_json.get("标题") or "").strip()
                        pb = _text(parsed_json.get("body") or parsed_json.get("正文") or parsed_json.get("description") or "").strip()
                        if pt and pb:
                            p_title = pt[:30]
                            p_body = pb
                            p_ok = True
                            if "解析成功" not in ai_reason:
                                ai_reason = "JSON解析成功"
                except Exception:
                    pass

                # 标题/正文格式
                if not p_ok:
                    title_match = re.search(r"标题[：:]\s*(.+)", content_text)
                    body_match = re.search(r"正文[：:]\s*(.+)", content_text, re.DOTALL)
                    if title_match and body_match:
                        pt = title_match.group(1).strip().strip('[]【】"')
                        pb = body_match.group(1).strip()
                        if pt and pb:
                            p_title = pt[:30]
                            p_body = pb
                            p_ok = True
                            if "解析成功" not in ai_reason:
                                ai_reason = "标题/正文格式解析成功"

                # Markdown 格式
                if not p_ok:
                    title_match = re.search(r"(?:^|\n)(?:#+\s*)?(?:标题|Title)\s*[：:]?\s*(.+)", content_text)
                    body_match = re.search(r"(?:^|\n)(?:#+\s*)?(?:正文|描述|Body|Description)\s*[：:]?\s*([\s\S]+)$", content_text)
                    if title_match and body_match:
                        pt = title_match.group(1).strip().strip('[]【】"')
                        pb = body_match.group(1).strip()
                        if pt and pb:
                            p_title = pt[:30]
                            p_body = pb
                            p_ok = True
                            if "解析成功" not in ai_reason:
                                ai_reason = "Markdown格式解析成功"

                # 多行兜底
                if not p_ok:
                    lines = [line.strip() for line in content_text.splitlines() if line.strip()]
                    if len(lines) >= 2:
                        pt = re.sub(r"^(?:标题|Title)\s*[：:]?\s*", "", lines[0]).strip().strip('[]【】"')
                        pb = "\n".join(lines[1:]).strip()
                        pb = re.sub(r"^(?:正文|描述|Body|Description)\s*[：:]?\s*", "", pb)
                        if pt and pb:
                            p_title = pt[:30]
                            p_body = pb
                            p_ok = True
                            if "解析成功" not in ai_reason:
                                ai_reason = "多行文本兜底解析成功"

            if not p_ok and ai_response_text and "失败" not in ai_reason:
                ai_reason = "模型返回内容无法解析"

            return p_title, p_body, p_ok, ai_source, ai_reason, ai_response_text

        # ★ 从数据库读取 AI Provider 配置（用户在「后台 → 模型配置」中添加的）
        #   在循环外读取一次，避免每次重试都查询数据库
        try:
            from sqlalchemy import select as _sa_select
            from ..models.entities import XianyuAiProvider
            _result = await db.execute(
                _sa_select(XianyuAiProvider)
                .where(XianyuAiProvider.status == 1)
                .order_by(XianyuAiProvider.id.asc())
                .limit(1)
            )
            _ai_provider = _result.scalar_one_or_none()
        except Exception:
            _ai_provider = None

        for idx, p in enumerate(items_to_polish):
            for acct_id in account_ids:
                _t_polish_start = __import__('time').perf_counter()
                title_raw = _text(p.get("title", ""))[:500]
                desc_raw = _text(p.get("description", "") or p.get("desc", "") or p.get("itemDesc", ""))[:20000]
                price_raw = _text(p.get("price", ""))

                polished_title = title_raw      # 默认值
                polished_body = desc_raw        # 默认值
                ai_ok = False
                ai_source = "none"
                ai_reason = "未调用模型"
                ai_response_text = ""  # 仅用于当前请求内解析，不写入状态或产物
                quality_score = 0
                quality_reasons: list = []
                attempt_count = 0  # 重试计数

                # ★ 主润色循环：最多 4 次（1 次原始 + 3 次重试；多一次给禁止词重试）
                while attempt_count < 4:
                    retry_reasons = quality_reasons if attempt_count > 0 else None
                    ai_prompt = _build_polish_prompt(title_raw, desc_raw, polish_style, retry_reasons)
                    try:
                        _pt, _pb, _ok, _src, _reason, _resp_text = await _call_ai_and_parse(
                            ai_prompt,
                            f"{_polish_run_identity}:{idx}:{acct_id}:{attempt_count}",
                        )
                    except AiBillingPaymentRequired:
                        return {
                            "ok": False,
                            "errorCode": "AI_BALANCE_INSUFFICIENT",
                            "message": "AI Token 余额不足，请充值后重试",
                            "polished": polished,
                        }
                    except AiBillingError as exc:
                        _log_runtime_failure("bill_product_polish", exc)
                        return {
                            "ok": False,
                            "errorCode": "AI_BILLING_UNAVAILABLE",
                            "message": "AI 计费服务暂不可用，润色已停止，请稍后重试",
                            "polished": polished,
                        }

                    if _ok and _pt and _pb:
                        polished_title = _pt
                        polished_body = _pb
                        ai_ok = True
                        ai_source = _src
                        ai_reason = _reason
                        ai_response_text = _resp_text

                        # 兜底清洗：去除残留的店铺标识
                        polished_title, polished_body = _strip_shop_watermark(polished_title, polished_body)

                        # 评分（传入禁止词列表，命中直接判 0 分强制重试）
                        quality_score, quality_reasons = _evaluate_polish_quality(
                            polished_title, polished_body, title_raw, desc_raw,
                            forbidden_keywords=_polish_forbidden_list,
                        )
                        logger.info("[PRODUCT_POLISH] acct=%d attempt=%d score=%d reasons=%s title=%s",
                                     acct_id, attempt_count, quality_score, quality_reasons[:3],
                                     polished_title[:30])

                        if quality_score >= 60:
                            # 评分通过，跳出重试循环
                            break
                        # 评分未通过，继续重试
                        attempt_count += 1
                        continue
                    else:
                        # AI 调用失败或解析失败
                        ai_source = _src
                        ai_reason = _reason
                        ai_response_text = _resp_text
                        attempt_count += 1
                        if attempt_count >= 4:
                            logger.warning("[PRODUCT_POLISH] AI未返回有效结果（重试%d次后仍失败）title=%s",
                                           attempt_count, title_raw[:20])
                        break  # AI 调用本身失败，不重试

                if not ai_ok:
                    return {
                        "ok": False,
                        "errorCode": "AI_MODEL_UNAVAILABLE",
                        "message": "AI 润色服务暂不可用或未返回有效内容，请稍后重试",
                        "polished": polished,
                    }

                if ai_ok:
                    # 如果模型返回内容与原文完全一致，降级到本地规则改写
                    if polished_title.strip() == title_raw.strip() and polished_body.strip() == desc_raw.strip():
                        compact_title = re.sub(r"\s+", " ", title_raw).strip()
                        compact_title = re.sub(r"(.{1,12}?)\1+", r"\1", compact_title)
                        compact_title = compact_title[:30].strip(" ，,。.!！?？-_/\\") or title_raw[:30]

                        compact_body = re.sub(r"\s+", " ", desc_raw).strip()
                        compact_body = re.sub(r"([A-Za-z0-9一-龥]{2,20})\s+\1", r"\1", compact_body)
                        compact_body = compact_body.replace("标价就是售价，可以直接拍", "价格清晰，拍下即可发货")
                        compact_body = compact_body.replace("下单界面", "下单后")
                        compact_body = compact_body[:220].strip()
                        if compact_body and compact_body == desc_raw.strip():
                            compact_body = f"{polish_style}：{compact_body}"

                        polished_title = compact_title
                        polished_body = compact_body or desc_raw
                        ai_reason = "模型原样返回，已降级为本地规则改写"

                    # 评分信息加入 reason（如重试过）
                    if quality_reasons and "重试" not in ai_reason:
                        ai_reason = f"{ai_reason}（评分 {quality_score}）"

                    full_description = f"{polished_title}\n{polished_body}"
                    logger.info("[PRODUCT_POLISH] AI润色成功 account=%d 标题=%s 正文长度=%d score=%d",
                                 acct_id, polished_title[:20], len(full_description), quality_score)
                # 最终硬兜底：已成功计费的 AI 结果若仍与原文一致，再做本地改写。
                if polished_title.strip() == title_raw.strip() and full_description.strip() == desc_raw.strip():
                    forced_title = re.sub(r"\s+", " ", title_raw).strip()
                    forced_title = re.sub(r"(.{1,12}?)\1+", r"\1", forced_title)
                    forced_title = forced_title[:30].strip(" ，,。.!！?？-_/\\") or f"{polish_style}商品"

                    forced_body = re.sub(r"\s+", " ", desc_raw).strip()
                    forced_body = forced_body.replace("标价就是售价，可以直接拍", "价格清晰，拍下即可发货")
                    forced_body = forced_body.replace("下单界面", "下单后")
                    if forced_body == desc_raw.strip():
                        forced_body = f"{polish_style}：{forced_body}"

                    polished_title = forced_title
                    full_description = f"{forced_title}\n{forced_body}" if forced_body else forced_title
                    if not ai_reason or "原样返回" not in ai_reason:
                        ai_reason = "最终出参硬兜底改写"

                # ★ 禁止词最终硬过滤兜底：
                #   无论前面经历了多少次重试或本地改写，最终输出前对标题和正文做一次 mask 替换，
                #   确保返回前端/入库的内容绝不包含任何禁止词（含默认禁止词和后台配置的禁止词）。
                #   这是最后一道防线，即使模型完全不遵守 prompt 限制、即使重试耗尽也能保证。
                try:
                    _ft, _fd, _fhits = await enforce_polish_restriction(polished_title, full_description)
                    if _fhits:
                        polished_title = _ft
                        full_description = _fd
                        logger.warning("[PRODUCT_POLISH] 最终硬过滤命中禁止词 acct=%d hits=%s title=%s",
                                       acct_id, _fhits, polished_title[:30])
                        if "禁止词" not in (ai_reason or ""):
                            ai_reason = f"{ai_reason or ''}；已硬过滤禁止词: {'、'.join(_fhits)}".strip("；")
                except Exception as exc:
                    _log_runtime_failure("enforce_final_polish_restrictions", exc)

                # 输出：只保留处理后的标题、文案、价格、分类，并关联账号
                p_new = {
                    "title": polished_title,
                    "description": full_description,
                    "price": price_raw,
                    "category": p.get("category") or p.get("categoryName") or "",
                    "accountId": acct_id,  # ★ 关联此版本对应的发布账号
                }
                # 保留 itemId 等关键标识字段供后续节点使用
                for keep_key in ("itemId", "id", "link", "imageUrl", "images", "keyword", "soldCount", "wantCount"):
                    if keep_key in p:
                        p_new[keep_key] = p[keep_key]
                polished.append(p_new)
                # 记录润色耗时
                _polish_ms = int((__import__('time').perf_counter() - _t_polish_start) * 1000)
                item_timings.setdefault(global_version_idx, {})["polish_ms"] = _polish_ms
                item_timings.setdefault(global_version_idx, {})["source_item_id"] = _text(p.get("itemId", ""))
                item_timings.setdefault(global_version_idx, {})["source_title"] = title_raw[:200]
                item_timings.setdefault(global_version_idx, {})["account_id"] = acct_id
                polish_steps.append({
                    "itemId": p.get("itemId") or p.get("id") or "",
                    "accountId": acct_id,
                    "sourceTitle": title_raw[:120],
                    "sourceDescPreview": desc_raw[:160],
                    "aiSource": ai_source,
                    "aiOk": ai_ok,
                    "aiReason": ai_reason,
                    "resultTitle": polished_title[:120],
                    "resultDescPreview": full_description[:200],
                    "changed": (polished_title != title_raw) or (full_description != desc_raw),
                })
                global_version_idx += 1

                # ★ 逐商品进度事件：让前端展示"正在润色第 N 个商品"
                #   状态判定：AI 成功 → 润色成功；AI 失败但硬兜底改写了文案 → 润色成功(本地改写)；AI 失败且未改写 → 保留原文
                _polish_status_text = "润色成功" if ai_ok else (
                    "润色成功" if (polished_title != title_raw or full_description != desc_raw) else "保留原文"
                )
                _total_versions = len(items_to_polish) * len(account_ids)
                try:
                    _exec_id = context.get("__execution_id__")
                    _wf_id = context.get("__workflow_id__")
                    await insert_timeline(db, tenant_id, _exec_id, _wf_id, "PRODUCT_POLISH", "INFO", "polish_progress",
                                          f"润色进度: {global_version_idx}/{_total_versions}",
                                          f"商品[{title_raw[:20]}] 账号{acct_id} {_polish_status_text}",
                                          {"progress": global_version_idx, "total": _total_versions, "accountId": acct_id})
                    await db.commit()
                except Exception as exc:
                    _log_runtime_failure("persist_polish_progress", exc)

        logger.info("[PRODUCT_POLISH] 润色完成 成功=%d", len(polished))
        return {
            "ok": True, "polished": polished, "count": len(polished),
            "artifactType": "text", "artifactTitle": "润色文案[PRODUCT_POLISH]",
            "artifact": {"polished": polished, "style": polish_style, "steps": polish_steps, "marker": "PRODUCT_POLISH_V2"},
        }

    if typ in {"notification", "notify", "通知", "NOTIFICATION"}:
        message = _text(config.get("message") or "工作流节点已触发通知")
        await insert_notification(db, tenant_id, None, "工作流通知", message, "workflow", "info")
        return {"ok": True, "message": "通知已写入系统通知", "notified": True}

    if typ in {"publish_goods", "publish", "发布商品", "PUBLISH"}:
        # 默认真实发布（dry_run 默认关闭），支持节点配置覆盖
        dry_run = bool(config.get("dryRun", False))
        platform = _text(config.get("platform") or "xianyu")
        publish_interval = _safe_int(config.get("publishIntervalSeconds"), 10)
        # 从工作流状态中读取触发器配置的发布账号ID
        selected_account_id = state.get("selected_account_id") or config.get("selectedAccountId")
        polished = state.get("polished_products", [])
        images = state.get("generated_images", [])
        # 获取原始商品数据（含分类、地址等信息）
        selected_products = state.get("selected_products", [])

        # ★ 新流程：若上游 IMAGE_GENERATE 节点已完成内联发布（state 含 publish_results），
        #   PUBLISH 节点变成汇总节点，仅输出统计信息，不执行实际发布。
        #   兼容老工作流：若 state.publish_results 不存在（无生图节点改造的场景），仍走原批量发布逻辑。
        existing_publish_results = state.get("publish_results") or []
        if existing_publish_results:
            logger.info("[PUBLISH] 检测到上游已发布结果（%d 条），PUBLISH 节点转为汇总模式",
                        len(existing_publish_results))
            success_count = sum(1 for r in existing_publish_results if r.get("status") == "published")
            failed_count = sum(1 for r in existing_publish_results if r.get("status") == "failed")
            skipped_ai = sum(1 for r in existing_publish_results if r.get("status") == "skipped_no_ai_image")
            skipped_dup = sum(1 for r in existing_publish_results if r.get("status") == "skipped_duplicate")
            # ★ 草稿模式统计：saved_as_draft 是 draft_only 模式下生图后存入草稿箱的商品
            saved_draft_count = sum(1 for r in existing_publish_results if r.get("status") == "saved_as_draft")
            total_skipped = skipped_ai + skipped_dup

            # ★ 草稿模式下不计算发布成败：仅统计存入草稿箱的数量
            if saved_draft_count > 0 and success_count == 0 and failed_count == 0:
                node_ok = True
                partial = False
            elif success_count > 0 and (failed_count > 0 or total_skipped > 0):
                node_ok = True
                partial = True
            elif success_count > 0:
                node_ok = True
                partial = False
            else:
                node_ok = False
                partial = False

            msg_parts = []
            if saved_draft_count > 0:
                msg_parts.append(f"汇总：已存入草稿箱 {saved_draft_count} 个商品")
            else:
                msg_parts.append(f"汇总：已发布 {success_count} 个商品")
            if failed_count:
                msg_parts.append(f"{failed_count}个失败")
            if skipped_ai:
                msg_parts.append(f"{skipped_ai}个无AI封面图已阻止")
            if skipped_dup:
                msg_parts.append(f"{skipped_dup}个重复已跳过")

            # 写一条汇总 timeline 事件
            try:
                _exec_id = context.get("__execution_id__")
                _wf_id = context.get("__workflow_id__")
                await insert_timeline(db, tenant_id, _exec_id, _wf_id, "PUBLISH", "INFO", "publish_summary",
                                      f"发布汇总: 成功 {success_count}，失败 {failed_count}，跳过 {total_skipped}，存草稿 {saved_draft_count}",
                                      "，".join(msg_parts),
                                      {"successCount": success_count, "failedCount": failed_count,
                                       "skippedNoAiCount": skipped_ai, "skippedDuplicateCount": skipped_dup,
                                       "savedAsDraftCount": saved_draft_count,
                                       "totalCount": len(existing_publish_results), "summaryMode": True})
                await db.commit()
            except Exception as exc:
                _log_runtime_failure("persist_publish_summary", exc)

            return {
                "ok": node_ok,
                "errorCode": "" if node_ok else "PUBLISH_NO_SUCCESS",
                "partial": partial,
                "publishResults": existing_publish_results, "dryRun": dry_run,
                "count": len(existing_publish_results),
                "successCount": success_count,
                "failedCount": failed_count,
                "skippedNoAiCount": skipped_ai,
                "skippedDuplicateCount": skipped_dup,
                "savedAsDraftCount": saved_draft_count,
                "selectedAccountId": selected_account_id,
                "category": _text(config.get("category", "")),
                "addressText": _text(config.get("addressText", "")),
                "message": "，".join(msg_parts),
                "errorMessage": "" if node_ok else f"发布失败: {failed_count}个失败, {skipped_ai}个无AI封面图, {skipped_dup}个重复",
                "artifactType": "publish_plan", "artifactTitle": "发布计划(汇总)" if saved_draft_count == 0 else "草稿汇总",
                "artifact": {"dryRun": dry_run, "platform": platform, "publishResults": existing_publish_results,
                             "successCount": success_count, "failedCount": failed_count,
                             "skippedNoAiCount": skipped_ai, "skippedDuplicateCount": skipped_dup,
                             "savedAsDraftCount": saved_draft_count,
                             "summaryMode": True},
            }
        # ===== 兼容老工作流的批量发布逻辑（state 无 publish_results 时执行）=====


        # === 发布分类自动检测 ===
        # 1) 优先使用节点配置中用户手动输入的分类
        category = _text(config.get("category", ""))
        # 2) 如果节点未配置分类，从原始商品中获取分类
        if not category and selected_products:
            # 取第一个商品的原始分类
            first_product = selected_products[0] if selected_products else {}
            category = _text(first_product.get("category", first_product.get("catName", "")))
            if not category:
                # 尝试从商品的 detail_info/description 中匹配分类关键词
                desc = _text(first_product.get("description", first_product.get("desc", "")))
                title = _text(first_product.get("title", ""))
                combined = (title + " " + desc).lower()
                # 从本地分类数据库中按标题匹配
                try:
                    from .category_data import load_categories
                    cat_data = load_categories()
                    tree = cat_data.get("cation", cat_data.get("categories", []))
                    matched = _match_category_from_tree(tree, title)
                    if matched:
                        category = matched["name"]
                        logger.info("工作流发布节点：从分类树按标题匹配到分类: %s", category)
                except Exception as exc:
                    _log_runtime_failure("match_publish_category_tree", exc)
        # 3) 如果仍然没有分类，尝试 AI 建议
        if not category:
            title_for_cat = ""
            if polished:
                title_for_cat = _text(polished[0].get("title", ""))
            if not title_for_cat and selected_products:
                title_for_cat = _text(selected_products[0].get("title", ""))
            if title_for_cat:
                try:
                    from .category_data import load_categories
                    cat_data = load_categories()
                    tree = cat_data.get("cation", cat_data.get("categories", []))
                    flat_options = _flatten_category_tree(tree)
                    if flat_options:
                        ai_category = await _suggest_category_by_title(db, tenant_id, title_for_cat, flat_options, user_id=_pub_user_id)
                        if ai_category:
                            category = ai_category
                            logger.info("工作流发布节点：AI建议分类: %s", category)
                except Exception as exc:
                    _log_runtime_failure("suggest_publish_category", exc)

        # === 发布地址处理 ===
        # 1) 优先使用节点配置的地址
        address_text = _text(config.get("addressText", ""))
        address = config.get("address", {})
        # 2) 如果节点未配置地址，从原始商品中获取地址
        if not address_text and selected_products:
            first_product = selected_products[0] if selected_products else {}
            # 商品数据可能包含地址信息
            product_address = first_product.get("address", {}) or first_product.get("location", {})
            if product_address and isinstance(product_address, dict):
                address = product_address
                address_text = _text(product_address.get("poiName", product_address.get("address", "")))
            elif isinstance(product_address, str):
                address_text = product_address
        # 3) 如果仍然没有地址，从数据库中查找用户常用地址
        if not address_text:
            try:
                rows = (await db.execute(text("""
                    SELECT address_poi_name, address_city, address_area, address_detail
                    FROM user_publish_address
                    WHERE tenant_id=:tenant_id AND deleted=0
                    ORDER BY use_count DESC, updated_time DESC
                    LIMIT 1
                """), {"tenant_id": tenant_id})).mappings().all()
                if rows:
                    row = dict(rows[0])
                    address_text = _text(row.get("address_poi_name", ""))
                    address = {
                        "poiName": row.get("address_poi_name", ""),
                        "city": row.get("address_city", ""),
                        "area": row.get("address_area", ""),
                        "detail": row.get("address_detail", ""),
                    }
                    logger.info(
                        "工作流发布节点：使用数据库中的常用地址 addressLen=%d",
                        len(address_text),
                    )
            except Exception as exc:
                _log_runtime_failure("load_publish_address", exc)

        # === 执行发布（多账号：每个账号发布各自对应的润色版本） ===
        # ★ 多账号模式：account_ids 来自 state["selected_account_ids"]（触发器节点配置）
        #   polished 列表中每个版本已带 accountId 字段，发布时仅发布属于该账号的版本
        account_ids = state.get("selected_account_ids") or []
        if not account_ids:
            account_ids_raw = config.get("accountIds") or []
            if isinstance(account_ids_raw, str):
                account_ids = [a.strip() for a in account_ids_raw.split(",") if a.strip()]
            elif isinstance(account_ids_raw, list):
                account_ids = account_ids_raw
            if not account_ids and selected_account_id:
                account_ids = [selected_account_id]
            if not account_ids:
                account_ids = [1]

        logger.info("[PUBLISH] 开始发布 accounts=%s polished=%d dryRun=%s",
                     account_ids, len(polished), dry_run)

        publish_results = []
        if not dry_run:
            from app.services.xianyu_goods_sync import XianyuItemPublisher, extract_token_from_cookie

        # ★ 按 accountId 分组润色版本：每个账号只发布属于它的版本
        for acct_id in account_ids:
            try:
                acct_id = int(acct_id)
            except (ValueError, TypeError):
                continue

            # 筛选属于该账号的润色版本（无 accountId 字段时视为属于当前账号，兼容老数据）
            acct_polished = [p for p in polished if p.get("accountId") == acct_id or p.get("accountId") is None]
            if not acct_polished:
                logger.info("[PUBLISH] 账号%d 无对应润色版本，跳过", acct_id)
                continue

            # ★ 鱼小铺标识默认 False（dry_run 路径不查询，统一按普通账号处理库存=1）
            #   非 dry_run 路径在下方 cookie 解析后会覆盖为真实值
            acct_is_fish_shop = False

            # 解析账号 Cookie（复用 _resolve_account_cookie，已处理解密）
            if not dry_run:
                cookie_str, cookie_err, _resolved_acct_id = await _resolve_account_cookie(db, tenant_id, acct_id, {})
                if cookie_err:
                    logger.warning("runtimeFailure operation=resolve_publish_account_cookie errorType=AccountAuthUnavailable requestId=%s", get_request_id() or "-")
                    for p in acct_polished:
                        publish_results.append({
                            "title": _text(p.get("title", "")), "platform": platform,
                            "status": "failed", "errorCode": "PUBLISH_ACCOUNT_UNAVAILABLE",
                            "error": "发布账号登录状态不可用，请重新登录",
                            "account_id": acct_id, "category": category,
                        })
                        # ★ 草稿保存（fire-and-forget）：发布前账号失效也记入草稿箱
                        await _save_legacy_publish_draft(
                            db, context=context, tenant_id=tenant_id, account_id=acct_id,
                            is_fish_shop=acct_is_fish_shop, category=category, address=address,
                            p=p, img_url="", image_urls=[],
                            publish_result=publish_results[-1],
                        )
                    continue
                token = extract_token_from_cookie(cookie_str)
                if not token:
                    logger.error("[PUBLISH] 账号%d Cookie缺少_m_h5_tk", acct_id)
                    for p in acct_polished:
                        publish_results.append({
                            "title": _text(p.get("title", "")), "platform": platform,
                            "status": "failed", "errorCode": "PUBLISH_ACCOUNT_UNAVAILABLE",
                            "error": "发布账号登录状态不可用，请重新登录",
                            "account_id": acct_id, "category": category,
                        })
                        # ★ 草稿保存（fire-and-forget）：Cookie 缺 token 也记入草稿箱
                        await _save_legacy_publish_draft(
                            db, context=context, tenant_id=tenant_id, account_id=acct_id,
                            is_fish_shop=acct_is_fish_shop, category=category, address=address,
                            p=p, img_url="", image_urls=[],
                            publish_result=publish_results[-1],
                        )
                    continue
                publisher = XianyuItemPublisher(cookie_str, tenant_id)
                # 查询账号是否鱼小铺：鱼小铺账号可自定义库存，普通账号库存固定为 1
                try:
                    _fs_row = (await db.execute(text(
                        "SELECT fish_shop_user FROM xianyu_account WHERE id=:aid AND tenant_id=:tid AND deleted=0 LIMIT 1"
                    ), {"aid": acct_id, "tid": tenant_id})).first()
                    acct_is_fish_shop = bool(_fs_row and _fs_row[0])
                except Exception as _fs_err:
                    fs_flag_pub_err = _exc_type_name(_fs_err)
                    logger.warning("[PUBLISH] 账号%d 查询鱼小铺标识失败，按普通账号处理 errorType=%s", acct_id, fs_flag_pub_err)
                    acct_is_fish_shop = False

            for idx, p in enumerate(polished):
                # ★ 多账号：仅发布属于当前账号的版本
                p_acct = p.get("accountId")
                if p_acct is not None and int(p_acct) != acct_id:
                    continue

                img_ref = images[idx] if idx < len(images) else ""
                img_url = img_ref["url"] if isinstance(img_ref, dict) else str(img_ref)
                img_ai_ok = bool(img_ref.get("aiOk")) if isinstance(img_ref, dict) else False
                image_urls = [img_url] if img_url else []
                title = _text(p.get("title", ""))
                desc = _text(p.get("description", ""))
                price = _text(p.get("price", "0"))
                # 价格兜底：搜索结果可能未携带 price 字段（如风控降级时 DOM 提取的残缺数据），使用默认价避免发布被拒绝
                try:
                    _price_num = float(price)
                except (ValueError, TypeError):
                    _price_num = 0.0
                if _price_num <= 0:
                    logger.warning("[PUBLISH] 商品价格缺失或无效，使用默认价 1 元 account=%d title=%s origPrice=%r", acct_id, title[:20], price)
                    price = "1"
                # 源商品标识（用于跨次运行去重）
                source_item_id = _text(p.get("itemId", "") or (img_ref.get("sourceItemId", "") if isinstance(img_ref, dict) else ""))
                source_title_raw = _text(p.get("title", "")) or (img_ref.get("sourceTitle", "") if isinstance(img_ref, dict) else "")
                import hashlib as _hashlib
                source_title_hash = _hashlib.md5(source_title_raw.strip().lower().encode("utf-8")).hexdigest() if source_title_raw else ""

                # ★ 约束1：未使用AI生图模型生成封面图的商品严禁发布
                if not img_ai_ok or not img_url:
                    publish_results.append({
                        "goods_id": "",
                        "title": title,
                        "image_url": img_url,
                        "platform": platform,
                        "status": "skipped_no_ai_image",
                        "errorCode": "PUBLISH_AI_IMAGE_REQUIRED",
                        "error": "商品未生成 AI 封面图，已阻止发布",
                        "interval_seconds": publish_interval,
                        "account_id": acct_id, "category": category,
                        "addressText": address_text, "address": address,
                        "source_item_id": source_item_id,
                    })
                    # ★ 草稿保存（fire-and-forget）：无 AI 封面图也记入草稿箱
                    await _save_legacy_publish_draft(
                        db, context=context, tenant_id=tenant_id, account_id=acct_id,
                        is_fish_shop=acct_is_fish_shop, category=category, address=address,
                        p=p, img_url=img_url, image_urls=image_urls,
                        publish_result=publish_results[-1],
                    )
                    logger.warning("[PUBLISH] 跳过发布(无AI封面图) account=%d title=%s", acct_id, title[:20])
                    continue

                if dry_run or not title or not desc or not image_urls:
                    publish_results.append({
                        "goods_id": "",
                        "title": title,
                        "image_url": img_url,
                        "platform": platform,
                        "status": "dry_run" if dry_run else "skipped",
                        "interval_seconds": publish_interval,
                        "account_id": acct_id, "category": category,
                        "addressText": address_text, "address": address,
                    })
                    # ★ 草稿保存（fire-and-forget）：dry_run / 字段缺失也记入草稿箱
                    await _save_legacy_publish_draft(
                        db, context=context, tenant_id=tenant_id, account_id=acct_id,
                        is_fish_shop=acct_is_fish_shop, category=category, address=address,
                        p=p, img_url=img_url, image_urls=image_urls,
                        publish_result=publish_results[-1],
                    )
                    continue

                # ★ 价格校验：价格 <= 0 直接跳过发布，避免发送到闲鱼后被 FAIL_BIZ_SKU_PRICE_ILLEGAL 拒绝
                try:
                    _price_num = float(price) if price not in ("", None) else 0.0
                except (ValueError, TypeError):
                    _price_num = 0.0
                if _price_num <= 0:
                    publish_results.append({
                        "goods_id": "",
                        "title": title,
                        "image_url": img_url,
                        "platform": platform,
                        "status": "skipped",
                        "errorCode": "PUBLISH_PRICE_INVALID",
                        "error": "商品价格未设置或为 0，已阻止发布",
                        "interval_seconds": publish_interval,
                        "account_id": acct_id, "category": category,
                        "addressText": address_text, "address": address,
                        "source_item_id": source_item_id,
                    })
                    # ★ 草稿保存（fire-and-forget）：价格无效也记入草稿箱
                    await _save_legacy_publish_draft(
                        db, context=context, tenant_id=tenant_id, account_id=acct_id,
                        is_fish_shop=acct_is_fish_shop, category=category, address=address,
                        p=p, img_url=img_url, image_urls=image_urls,
                        publish_result=publish_results[-1],
                    )
                    logger.warning("[PUBLISH] 跳过发布(价格<=0) account=%d title=%s price=%r",
                                   acct_id, title[:20], price)
                    continue

                # ★ 约束2：跨次运行去重（按账号+itemId/标题），已发布过的商品跳过
                try:
                    dedup_hit = False
                    if source_item_id:
                        dr = (await db.execute(text("""
                            SELECT id FROM workflow_published_goods
                            WHERE tenant_id=:t AND account_id=:a AND source_item_id=:s AND deleted=0 LIMIT 1
                        """), {"t": tenant_id, "a": acct_id, "s": source_item_id})).first()
                        if dr:
                            dedup_hit = True
                    if not dedup_hit and source_title_hash:
                        dr = (await db.execute(text("""
                            SELECT id FROM workflow_published_goods
                            WHERE tenant_id=:t AND account_id=:a AND source_title_hash=:h AND deleted=0 LIMIT 1
                        """), {"t": tenant_id, "a": acct_id, "h": source_title_hash})).first()
                        if dr:
                            dedup_hit = True
                    if dedup_hit:
                        publish_results.append({
                            "goods_id": "",
                            "title": title,
                            "image_url": img_url,
                            "platform": platform,
                            "status": "skipped_duplicate",
                            "errorCode": "PUBLISH_DUPLICATE",
                            "error": "该商品已发布过，已跳过重复发布",
                            "interval_seconds": publish_interval,
                            "account_id": acct_id, "category": category,
                            "addressText": address_text, "address": address,
                            "source_item_id": source_item_id,
                        })
                        # ★ 草稿保存（fire-and-forget）：重复跳过也记入草稿箱
                        await _save_legacy_publish_draft(
                            db, context=context, tenant_id=tenant_id, account_id=acct_id,
                            is_fish_shop=acct_is_fish_shop, category=category, address=address,
                            p=p, img_url=img_url, image_urls=image_urls,
                            publish_result=publish_results[-1],
                        )
                        logger.info("[PUBLISH] 跳过发布(重复) account=%d title=%s itemId=%s", acct_id, title[:20], source_item_id)
                        continue
                except Exception as exc:
                    _log_runtime_failure("check_publish_duplicate", exc)

                # 真实发布到闲鱼
                try:
                    _t_pub_start = __import__('time').perf_counter()
                    # 鱼小铺账号可自定义库存（默认 999），普通账号库存固定为 1
                    _pub_quantity = 999 if acct_is_fish_shop else 1
                    item_data = {
                        "title": title,
                        "desc": desc,
                        "imageUrls": image_urls,
                        "price": price,
                        "quantity": _pub_quantity,
                    }
                    if category:
                        item_data["category"] = {"catName": category}
                    if isinstance(address, dict) and address.get("poiName"):
                        item_data["location"] = address

                    result = publisher.publish(item_data)
                    _pub_ms = int((__import__('time').perf_counter() - _t_pub_start) * 1000)
                    if result.get("success"):
                        goods_id = _text(result.get("itemId", ""))
                        publish_results.append({
                            "goods_id": goods_id,
                            "title": title,
                            "image_url": img_url,
                            "platform": platform,
                            "status": "published",
                            "interval_seconds": publish_interval,
                            "account_id": acct_id, "category": category,
                            "addressText": address_text, "address": address,
                            "source_item_id": source_item_id,
                        })
                        # ★ 草稿保存（fire-and-forget）：发布成功记入草稿箱 status=published
                        await _save_legacy_publish_draft(
                            db, context=context, tenant_id=tenant_id, account_id=acct_id,
                            is_fish_shop=acct_is_fish_shop, category=category, address=address,
                            p=p, img_url=img_url, image_urls=image_urls,
                            publish_result=publish_results[-1],
                        )
                        logger.info("[PUBLISH] 发布成功 account=%d title=%s goods_id=%s",
                                     acct_id, title[:20], goods_id)
                        # ★ 约束3：发布成功立即落库去重表，即使后续节点/连接取消也不丢已发布记录
                        try:
                            await db.execute(text("""
                                INSERT INTO workflow_published_goods(tenant_id, account_id, source_item_id, source_title_hash, source_image_url, goods_id, published_title, workflow_id, execution_id, created_time, deleted)
                                VALUES(:t, :a, :si, :sh, :img, :gid, :pt, :wid, :eid, NOW(), 0)
                            """), {
                                "t": tenant_id, "a": acct_id, "si": source_item_id or "",
                                "sh": source_title_hash, "img": img_url[:500] if img_url else "",
                                "gid": goods_id, "pt": title[:200],
                                "wid": context.get("__workflow_id__"), "eid": context.get("__execution_id__"),
                            })
                            await db.commit()
                        except Exception as exc:
                            # 去重表写入失败不应阻塞主流程（UNIQUE 冲突也算，说明并发已发布过）
                            await db.rollback()
                            _log_runtime_failure("persist_publish_dedup", exc)
                        # ★ 记录单商品耗时（包含润色+生图+发布），用于统计平均耗时
                        try:
                            _timing = state.setdefault("item_timings", {}).get(idx, {})
                            _polish = _timing.get("polish_ms", 0)
                            _img = _timing.get("image_generate_ms", 0)
                            _total = _polish + _img + _pub_ms
                            await _record_item_timing(
                                db=db, tenant_id=tenant_id,
                                execution_id=context.get("__execution_id__"),
                                workflow_id=context.get("__workflow_id__"),
                                item_index=idx,
                                source_item_id=_timing.get("source_item_id", source_item_id),
                                source_title=_timing.get("source_title", title),
                                polish_ms=_polish, image_generate_ms=_img,
                                publish_ms=_pub_ms, total_ms=_total,
                            )
                        except Exception as exc:
                            _log_runtime_failure("persist_publish_timing", exc)
                    else:
                        # 透传 publisher 返回的真实原因（已包含 ret_msg 翻译）
                        reject_msg = result.get("message") or "平台暂未接受该商品，请检查内容后重试"
                        publish_results.append({
                            "goods_id": "",
                            "title": title, "image_url": img_url,
                            "platform": platform,
                            "status": "failed", "errorCode": "PUBLISH_PROVIDER_REJECTED",
                            "error": reject_msg,
                            "account_id": acct_id, "category": category,
                            "source_item_id": source_item_id,
                        })
                        # ★ 草稿保存（fire-and-forget）：发布被拒也记入草稿箱 status=failed
                        await _save_legacy_publish_draft(
                            db, context=context, tenant_id=tenant_id, account_id=acct_id,
                            is_fish_shop=acct_is_fish_shop, category=category, address=address,
                            p=p, img_url=img_url, image_urls=image_urls,
                            publish_result=publish_results[-1],
                        )
                        logger.warning("runtimeFailure operation=publish_workflow_item errorType=ProviderRejected requestId=%s", get_request_id() or "-")
                except Exception as e:
                    publish_results.append({
                        "goods_id": "",
                        "title": title, "image_url": img_url,
                        "platform": platform,
                        "status": "failed", "errorCode": "PUBLISH_RUNTIME_ERROR",
                        "error": "商品发布异常，请稍后重试",
                        "account_id": acct_id, "category": category,
                        "source_item_id": source_item_id,
                    })
                    # ★ 草稿保存（fire-and-forget）：运行时异常也记入草稿箱 status=failed
                    await _save_legacy_publish_draft(
                        db, context=context, tenant_id=tenant_id, account_id=acct_id,
                        is_fish_shop=acct_is_fish_shop, category=category, address=address,
                        p=p, img_url=img_url, image_urls=image_urls,
                        publish_result=publish_results[-1],
                    )
                    _log_runtime_failure("publish_workflow_item", e)

                # ★ 逐商品发布进度事件：让前端展示"正在发布第 N 个商品"
                _pub_done = len(publish_results)
                _pub_total = len(polished)
                try:
                    _exec_id = context.get("__execution_id__")
                    _wf_id = context.get("__workflow_id__")
                    _last = publish_results[-1] if publish_results else {}
                    _last_status = _text(_last.get('status', ''))
                    _last_status_cn = '成功' if _last_status == 'published' else '失败' if _last_status == 'failed' else '跳过' if _last_status.startswith('skipped') else _last_status
                    await insert_timeline(db, tenant_id, _exec_id, _wf_id, "PUBLISH", "INFO", "publish_progress",
                                          f"发布进度: {_pub_done}/{_pub_total}",
                                          f"商品[{title[:20]}] 发布{_last_status_cn}",
                                          {"progress": _pub_done, "total": _pub_total, "accountId": acct_id,
                                           "interval": publish_interval})
                    await db.commit()
                except Exception as exc:
                    _log_runtime_failure("persist_publish_progress", exc)

                # 多商品发布间隔
                if idx < len(polished) - 1 and not dry_run:
                    await asyncio.sleep(publish_interval)

        # 记录用户常用地址（如果有地址信息）
        if address_text and not dry_run:
            try:
                await db.execute(text("""
                    INSERT INTO user_publish_address(tenant_id, address_poi_name, address_city, address_area, address_detail, use_count, deleted, created_time, updated_time)
                    VALUES(:tenant_id, :poi_name, :city, :area, :detail, 1, 0, NOW(), NOW())
                    ON DUPLICATE KEY UPDATE use_count=use_count+1, updated_time=NOW()
                """), {
                    "tenant_id": tenant_id,
                    "poi_name": address.get("poiName", address_text),
                    "city": _text(address.get("city", "")),
                    "area": _text(address.get("area", "")),
                    "detail": _text(address.get("detail", "")),
                })
                await db.commit()
            except Exception as exc:
                _log_runtime_failure("persist_publish_address", exc)

        # 统计发布结果
        success_count = sum(1 for r in publish_results if r.get("status") == "published")
        failed_count = sum(1 for r in publish_results if r.get("status") == "failed")
        skipped_ai = sum(1 for r in publish_results if r.get("status") == "skipped_no_ai_image")
        skipped_dup = sum(1 for r in publish_results if r.get("status") == "skipped_duplicate")
        total_skipped = skipped_ai + skipped_dup

        # 节点状态语义：有成功=ok；部分失败/跳过=partial；全失败=failed
        if success_count > 0 and (failed_count > 0 or total_skipped > 0):
            node_ok = True  # partial：仍算成功，不阻断后续节点
            partial = True
        elif success_count > 0:
            node_ok = True
            partial = False
        else:
            node_ok = False
            partial = False

        # 构造可读消息
        msg_parts = [f"已发布 {success_count} 个商品"]
        if failed_count:
            msg_parts.append(f"{failed_count}个失败")
        if skipped_ai:
            msg_parts.append(f"{skipped_ai}个无AI封面图已阻止")
        if skipped_dup:
            msg_parts.append(f"{skipped_dup}个重复已跳过")
        if dry_run:
            msg_parts.append("演练模式")

        return {
            "ok": node_ok,
            "errorCode": "" if node_ok else "PUBLISH_NO_SUCCESS",
            "partial": partial,
            "publishResults": publish_results, "dryRun": dry_run,
            "count": len(publish_results),
            "successCount": success_count,
            "failedCount": failed_count,
            "skippedNoAiCount": skipped_ai,
            "skippedDuplicateCount": skipped_dup,
            "selectedAccountId": selected_account_id,
            "category": category,
            "addressText": address_text,
            "message": "（" + "，".join(msg_parts[1:]) + "）" if len(msg_parts) > 1 else msg_parts[0],
            "errorMessage": "" if node_ok else f"发布失败: {failed_count}个失败, {skipped_ai}个无AI封面图, {skipped_dup}个重复",
            "artifactType": "publish_plan", "artifactTitle": "发布计划",
            "artifact": {"dryRun": dry_run, "platform": platform, "publishResults": publish_results, "account_id": selected_account_id, "category": category, "address": address, "successCount": success_count, "failedCount": failed_count, "skippedNoAiCount": skipped_ai, "skippedDuplicateCount": skipped_dup},
        }

    return {"ok": True, "message": f"节点类型 {typ} 已跳过执行", "config": config}


async def list_workflow_timeline(
    db: AsyncSession,
    tenant_id: int,
    execution_id: int,
) -> list[dict[str, Any]]:
    """查询工作流执行时间线"""
    try:
        rows = (await db.execute(text("""
            SELECT id, node_key, event_level, event_type, title, content, payload_json, created_time
            FROM workflow_timeline
            WHERE tenant_id=:tenant_id AND execution_id=:execution_id AND deleted=0
            ORDER BY id ASC
        """), {"tenant_id": tenant_id, "execution_id": execution_id})).mappings().all()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            payload_value = item.get("payload_json")
            if isinstance(payload_value, str) and payload_value.strip():
                try:
                    payload_value = json.loads(payload_value)
                except (TypeError, ValueError, json.JSONDecodeError):
                    payload_value = None
            is_failure = _text(item.get("event_level")).strip().upper() == "ERROR"
            safe_item = _sanitize_runtime_value(item, failure_context=is_failure)
            if payload_value is not None:
                safe_payload = _sanitize_runtime_value(payload_value, failure_context=is_failure)
                safe_item["payload_json"] = json.dumps(safe_payload, ensure_ascii=False)
            if is_failure:
                payload_code = ""
                if isinstance(payload_value, dict):
                    payload_code = _text(payload_value.get("errorCode") or payload_value.get("error_code")).strip().upper()
                error_code = payload_code if payload_code in _PUBLIC_RUNTIME_ERRORS else "RUNTIME_OPERATION_FAILED"
                safe_item["errorCode"] = error_code
                safe_item["content"] = _PUBLIC_RUNTIME_ERRORS[error_code]
            result.append(safe_item)
        return result
    except Exception as e:
        _log_runtime_failure("list_workflow_timeline", e)
        return []


async def list_workflow_state_variables(
    db: AsyncSession,
    tenant_id: int,
    execution_id: int,
) -> list[dict[str, Any]]:
    """查询工作流状态变量"""
    try:
        rows = (await db.execute(text("""
            SELECT id, node_key, var_name, var_value, var_type, created_time
            FROM workflow_state_variable
            WHERE tenant_id=:tenant_id AND execution_id=:execution_id AND deleted=0
            ORDER BY id ASC
        """), {"tenant_id": tenant_id, "execution_id": execution_id})).mappings().all()
        result = []
        for r in rows:
            d = dict(r)
            # 尝试解析 JSON 值
            if d.get("var_value"):
                try:
                    parsed_value = json.loads(d["var_value"])
                except Exception:
                    parsed_value = d["var_value"]
                safe_value = _sanitize_runtime_value(
                    parsed_value,
                    failure_context=_runtime_key(d.get("var_name")) in _RUNTIME_ERROR_KEYS,
                )
                d["var_value_parsed"] = safe_value
                d["var_value"] = (
                    json.dumps(safe_value, ensure_ascii=False)
                    if not isinstance(safe_value, str)
                    else safe_value
                )
            result.append(_sanitize_runtime_value(d))
        return result
    except Exception as e:
        _log_runtime_failure("list_workflow_state_variables", e)
        return []
