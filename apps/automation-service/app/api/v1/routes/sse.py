import logging
import asyncio
import json
import uuid
import hmac
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from ....core.config import settings
from ....services.ws_sse import broadcaster

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sse")


def _sse_response(generator):
    """返回标准 SSE StreamingResponse，避免 EventSource 因 MIME type 不匹配而 abort"""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/subscribe")
async def subscribe_sse(
    request: Request,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    x_internal_tenant_id: str | None = Header(default=None, alias="X-Internal-Tenant-Id"),
):
    """SSE 订阅端点，用于实时推送事件。

    Phase 1 起仅允许 Java core-api 代理调用；前端先获取一次性 SSE ticket，
    再由 Java 携带内部令牌建立到 Python 的长连接，避免长期 JWT 出现在 URL 中。
    """

    expected = (settings.effective_internal_api_token or "").strip()
    if not expected:
        logger.error("INTERNAL_API_TOKEN 未配置，拒绝 SSE 内部订阅")
        raise HTTPException(status_code=503, detail="INTERNAL_API_TOKEN is not configured")
    if not x_internal_token or not hmac.compare_digest(str(x_internal_token), expected):
        raise HTTPException(status_code=403, detail="invalid internal token")
    if not x_internal_tenant_id:
        raise HTTPException(status_code=400, detail="missing X-Internal-Tenant-Id")
    try:
        tenant_id = int(x_internal_tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="invalid X-Internal-Tenant-Id")
    if tenant_id <= 0:
        raise HTTPException(status_code=400, detail="invalid X-Internal-Tenant-Id")

    # 生成唯一订阅ID
    subscriber_id = f"tenant_{tenant_id}_{uuid.uuid4().hex[:8]}"

    async def event_generator():
        queue = None
        try:
            # 订阅事件
            queue = await broadcaster.subscribe(tenant_id, subscriber_id)
            
            # 先发送一个连接成功事件
            yield f"data: {json.dumps({'type': 'connected', 'message': '连接成功', 'tenantId': tenant_id})}\n\n"
            
            while True:
                if await request.is_disconnected():
                    break
                
                try:
                    # 从队列获取事件（带超时，用于发送心跳）
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                    yield message
                except asyncio.TimeoutError:
                    # 发送心跳保活
                    yield f"data: {json.dumps({'type': 'heartbeat', 'message': 'connected'})}\n\n"
        except asyncio.CancelledError:
            logger.info("SSE 连接被客户端断开 subId=%s", subscriber_id)
        except Exception as e:
            logger.error("SSE 连接异常 subId=%s errorType=%s", subscriber_id, type(e).__name__)
        finally:
            if queue is not None:
                await broadcaster.unsubscribe(tenant_id, subscriber_id)

    return _sse_response(event_generator())
