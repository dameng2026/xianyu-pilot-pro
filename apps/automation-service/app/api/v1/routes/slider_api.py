"""API 对接滑块求解路由（仅 Java 网关内部调用）。

端点：POST /api/slider/solve
鉴权：X-Internal-Token（Java 网关转发，使用 get_internal_service_identity 强制内部调用）
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ....core.response import ResultObject
from ....api.v1.deps import get_internal_service_identity
from ....services.captcha_api_solver import solve_for_external

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slider", tags=["slider-api"])


class SliderSolveRequest(BaseModel):
    requestId: str
    tenantId: int
    apiKeyPrefix: str
    clientIp: Optional[str] = None
    cookie: str
    targetUrl: str = "https://www.goofish.com"
    timeoutMs: int = 90000


@router.post("/solve")
async def solve(
    body: SliderSolveRequest,
    identity: dict = Depends(get_internal_service_identity),
) -> ResultObject:
    """
    对外滑块求解入口（仅 Java 网关内部调用）。
    Java 网关在调用前已完成：apiKey 鉴权 + 准入检查 + pending_count += 1。
    本端点仅负责求解编排 + 记录持久化，扣费由 Java 网关在收到响应后处理。
    """
    try:
        result = await solve_for_external(
            cookie=body.cookie,
            target_url=body.targetUrl,
            timeout_ms=body.timeoutMs,
            request_id=body.requestId,
            tenant_id=body.tenantId,
            api_key_prefix=body.apiKeyPrefix,
            client_ip=body.clientIp,
        )
        return ResultObject.success(data=result)
    except Exception as e:
        logger.error("slider_api solve failed req=%s errorType=%s", body.requestId, type(e).__name__)
        return ResultObject.failed(
            message="求解服务异常，请稍后重试",
            code=500,
            data={
                "status": "service_unavailable",
                "solved": False,
                "captchaDetected": False,
                "attempts": 0,
                "durationMs": 0,
                "cookies": None,
                "error": "求解服务异常，请稍后重试",
            },
        )
