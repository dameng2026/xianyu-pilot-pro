"""AI 计费客户端。

Python 自动化端只执行自动回复、商机、工作流等动作；用户余额、价格、扣费和流水均由 Java core-api 负责。
该模块把真实 usage 回传给 Java。没有配置 CORE_API_BASE_URL 时仍可本地开发，但生产环境必须配置。
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import uuid
from typing import Any, Optional

import httpx

from ..core.config import settings


MAX_BILLING_RESPONSE_BYTES = 1024 * 1024


class AiBillingError(RuntimeError):
    """Safe, user-facing failure raised when an AI usage cannot be billed."""

    status_code = 503
    user_message = "AI 计费服务暂不可用，请稍后重试"


class AiBillingPaymentRequired(AiBillingError):
    status_code = 402
    user_message = "AI Token 余额不足，请先充值后重试"


class AiBillingUnavailable(AiBillingError):
    pass


def _require_billing_identity(payload: dict[str, Any]) -> tuple[int, int]:
    try:
        tenant_id = int(payload.get("tenantId") or payload.get("tenant_id") or 0)
        user_id = int(payload.get("userId") or payload.get("user_id") or 0)
    except (TypeError, ValueError) as exc:
        raise AiBillingUnavailable("AI billing identity is invalid") from exc
    if tenant_id <= 0 or user_id <= 0:
        raise AiBillingUnavailable("AI billing identity is missing")
    return tenant_id, user_id


def _non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return max(0, int(fallback or 0))


def estimate_text_tokens(text: str | None) -> int:
    """粗略估算 token，用于没有真实模型 usage 的本地闭环。真实模型调用后必须使用供应商返回的 usage。"""
    if not text:
        return 0
    stripped = str(text).strip()
    if not stripped:
        return 0
    # 中文文本近似 1 字 1 token，英文按 4 字符 1 token 估算，取较大值防止低估。
    return max(1, math.ceil(len(stripped) / 2))


def build_request_id(prefix: str = "ai") -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def build_stable_request_id(prefix: str, *identity_parts: Any) -> str:
    """Build a retry-stable request id from durable execution identity parts."""
    normalized = "\x1f".join(str(part or "").strip() for part in identity_parts)
    if not normalized.replace("\x1f", ""):
        return build_request_id(prefix)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
    safe_prefix = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in prefix)[:40] or "ai"
    return f"{safe_prefix}_{digest}"


def extract_cached_tokens(usage: dict[str, Any] | None) -> int:
    """从供应商返回的 usage 中提取缓存命中的输入 token 数。

    DeepSeek/OpenAI 兼容协议返回字段（按优先级匹配）：
    1. usage.prompt_tokens_details.cached_tokens  (OpenAI/DeepSeek-V4 标准字段)
    2. usage.prompt_cache_hit_tokens              (DeepSeek 早期字段)
    3. usage.cached_tokens / usage.cache_tokens   (顶层简写)
    """
    if not usage:
        return 0
    # 嵌套字段：prompt_tokens_details.cached_tokens（标准）
    details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        for key in ("cached_tokens", "cache_tokens"):
            v = details.get(key)
            if v is not None:
                try:
                    return max(0, int(v))
                except (TypeError, ValueError):
                    pass
    # 顶层简写
    for key in ("cached_tokens", "cache_tokens", "prompt_cache_hit_tokens", "cache_read_input_tokens"):
        v = usage.get(key)
        if v is not None:
            try:
                return max(0, int(v))
            except (TypeError, ValueError):
                pass
    return 0


async def precheck_ai_usage(payload: dict[str, Any]) -> dict[str, Any]:
    _require_billing_identity(payload)
    result = await _post_java("/open-api/internal/ai-billing/precheck", payload)
    if not isinstance(result, dict):
        raise AiBillingUnavailable("AI billing precheck returned an invalid response")
    if result.get("enough") is False:
        raise AiBillingPaymentRequired("AI token balance is insufficient")
    if result.get("enough") is not True:
        raise AiBillingUnavailable("AI billing precheck did not confirm capacity")
    return result


async def charge_ai_usage(payload: dict[str, Any]) -> dict[str, Any]:
    _require_billing_identity(payload)
    result = await _post_java("/open-api/internal/ai-billing/charge", payload)
    return require_charge_confirmation(result, str(payload.get("requestId") or ""))


def require_charge_confirmation(result: Any, request_id: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise AiBillingUnavailable("AI billing charge returned an invalid response")
    if result.get("deducted") is not True and result.get("duplicate") is not True:
        raise AiBillingUnavailable("AI billing charge was not confirmed")
    confirmed_request_id = str(result.get("requestId") or "")
    if not request_id or confirmed_request_id != request_id:
        raise AiBillingUnavailable("AI billing charge request id did not match")
    return result


async def charge_text_usage(
    *,
    tenant_id: int,
    user_id: int,
    scene: str,
    provider_name: str = "default",
    model_name: str = "default",
    model_type: str = "chat",
    prompt: str = "",
    completion: str = "",
    request_id: Optional[str] = None,
    raw_usage: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    usage = raw_usage or {}
    prompt_tokens = _non_negative_int(
        usage.get("prompt_tokens") or usage.get("promptTokens"),
        estimate_text_tokens(prompt),
    )
    completion_tokens = _non_negative_int(
        usage.get("completion_tokens") or usage.get("completionTokens"),
        estimate_text_tokens(completion),
    )
    cached_tokens = extract_cached_tokens(usage)
    # 缓存命中数不能超过输入 token 总数
    if cached_tokens > prompt_tokens:
        cached_tokens = prompt_tokens
    return await charge_ai_usage({
        "tenantId": tenant_id,
        "userId": user_id,
        "scene": scene,
        "providerName": provider_name,
        "modelName": model_name,
        "modelType": model_type,
        "billingMode": "token",
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "cachedTokens": cached_tokens,
        "totalTokens": _non_negative_int(
            usage.get("total_tokens") or usage.get("totalTokens"),
            prompt_tokens + completion_tokens,
        ),
        "requestId": request_id or build_request_id(scene),
        "rawUsage": usage,
    })


async def charge_image_usage(
    *,
    tenant_id: int,
    user_id: int,
    scene: str,
    provider_name: str = "default",
    model_name: str = "default",
    image_count: int = 1,
    spec_key: str = "",
    request_id: Optional[str] = None,
    raw_usage: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return await charge_ai_usage({
        "tenantId": tenant_id,
        "userId": user_id,
        "scene": scene,
        "providerName": provider_name,
        "modelName": model_name,
        "modelType": "image",
        "billingMode": "spec" if spec_key else "per_call",
        "imageCount": max(1, _non_negative_int(image_count, 1)),
        "specKey": spec_key,
        "requestId": request_id or build_request_id(scene),
        "rawUsage": raw_usage or {},
    })


async def _post_java(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    base = (settings.core_api_base_url or "").rstrip("/")
    if not base:
        raise AiBillingUnavailable("AI billing service is not configured")
    headers = {"Content-Type": "application/json"}
    if settings.effective_internal_api_token:
        headers["X-Internal-Token"] = settings.effective_internal_api_token
    # The payload (and especially requestId) is immutable across transport
    # retries, so Java's charge idempotency key remains effective.
    last_error: BaseException | None = None
    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for attempt in range(3):
            try:
                response_bytes = bytearray()
                async with client.stream(
                    "POST",
                    f"{base}{path}",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.status_code == 402:
                        raise AiBillingPaymentRequired("AI token balance is insufficient")
                    if resp.status_code == 429 or resp.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            "AI billing upstream unavailable",
                            request=resp.request,
                            response=resp,
                        )
                    if resp.status_code >= 400:
                        raise AiBillingUnavailable("AI billing request was rejected")
                    chunks = resp.aiter_bytes()
                    async for chunk in chunks:
                        if len(response_bytes) + len(chunk) > MAX_BILLING_RESPONSE_BYTES:
                            await chunks.aclose()
                            raise AiBillingUnavailable("AI billing returned an oversized response")
                        response_bytes.extend(chunk)
                try:
                    data = __import__("json").loads(bytes(response_bytes))
                except (UnicodeDecodeError, TypeError, ValueError) as exc:
                    raise AiBillingUnavailable("AI billing returned invalid JSON") from exc
                if isinstance(data, dict) and str(data.get("code")) in {"0", "200"}:
                    result = data.get("data")
                    if not isinstance(result, dict):
                        raise AiBillingUnavailable("AI billing returned invalid data")
                    return result
                if isinstance(data, dict) and str(data.get("code")) == "402":
                    raise AiBillingPaymentRequired("AI token balance is insufficient")
                if isinstance(data, dict):
                    try:
                        result_code = int(data.get("code"))
                    except (TypeError, ValueError):
                        result_code = 0
                    if result_code == 429 or result_code >= 500:
                        raise httpx.HTTPStatusError(
                            "AI billing upstream unavailable",
                            request=resp.request,
                            response=resp,
                        )
                raise AiBillingUnavailable("AI billing did not confirm the request")
            except AiBillingError:
                raise
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                break
    raise AiBillingUnavailable("AI billing upstream unavailable") from last_error
