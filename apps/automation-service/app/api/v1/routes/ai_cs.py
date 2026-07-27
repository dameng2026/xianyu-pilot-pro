"""AI 客服"小梦"前台 API（Python 端）。

对接 Java AiCsController：
- Java 接收前端请求，校验会话归属、余额、闲聊计数、消息计数后，
  通过 AutomationClient.streamSse 代理到本路由的 /chat 端点。
- Python 负责实际 AI 推理（调用通用模型）、工具调用解析与执行、
  SSE 流式回传、Java 回调（持久化 + 扣费）。

三层鉴权：
- 本路由仅接受 Java core-api 的内部调用（X-Internal-Token）
- Java 在转发前已完成 session 归属校验（session_id + user_id + tenant_id）
- 工具执行时再次以 tenant_id 限定所有数据库查询

路由清单：
- GET  /api/ai-cs/chat         SSE 流式聊天（Java streamSse 透传）
- POST /api/ai-cs/compress      上下文压缩（Java postInternalForData）
- POST /api/ai-cs/tool/execute  执行已确认的工具调用（Java postInternalForData）
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.config import settings
from ....core.database import get_db
from ....core.response import ResultObject
from .internal import verify_internal_token
from ....services.ai_cs_runtime import (
    compress_context,
    execute_confirmed_tool,
    stream_chat,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-cs")


def _require_positive_int(value: Any, *, name: str) -> int:
    """解析正整数参数，失败时抛 400。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{name} 必须为正整数")
    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{name} 必须为正整数")
    return parsed


def _sse_response(generator) -> StreamingResponse:
    """返回标准 SSE StreamingResponse，与 sse.py 保持一致。"""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# SSE 流式聊天
# ============================================================

@router.get("/chat")
async def ai_cs_chat(
    sessionId: int = Query(..., description="AI 客服会话ID"),
    userId: int = Query(..., description="用户ID"),
    tenantId: int = Query(..., description="租户ID"),
    message: str = Query(..., description="用户消息"),
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式聊天端点。

    Java AiCsController.chat 通过 AutomationClient.streamSse 调用本端点，
    携带 query: sessionId/userId/tenantId/message，并附加 X-Internal-Token。

    本端点：
    1. 校验内部令牌（三层鉴权第一层：服务间令牌）
    2. 校验参数完整性
    3. 调用 ai_cs_runtime.stream_chat 流式生成回复
    4. SSE 事件由 stream_chat 内部生成，本端点仅做透传
    """
    # 内部令牌校验（fail-closed）
    expected = (settings.effective_internal_api_token or "").strip()
    if not expected:
        logger.error("INTERNAL_API_TOKEN 未配置，拒绝 AI 客服 SSE 调用")
        raise HTTPException(status_code=503, detail="INTERNAL_API_TOKEN is not configured")
    import hmac as _hmac
    if not x_internal_token or not _hmac.compare_digest(str(x_internal_token), expected):
        raise HTTPException(status_code=403, detail="invalid internal token")

    # 参数校验
    session_id = _require_positive_int(sessionId, name="sessionId")
    user_id = _require_positive_int(userId, name="userId")
    tenant_id = _require_positive_int(tenantId, name="tenantId")
    if not message or not message.strip():
        # SSE 错误也走 StreamingResponse，便于前端统一处理
        async def _empty_message_stream():
            yield 'event: error\ndata: {"type":"error","message":"消息不能为空"}\n\n'
        return _sse_response(_empty_message_stream())

    logger.info(
        "ai_cs_chat start sessionId=%d userId=%d tenantId=%d msgLen=%d",
        session_id, user_id, tenant_id, len(message),
    )

    async def event_generator():
        try:
            async for chunk in stream_chat(
                db,
                session_id=session_id,
                user_id=user_id,
                tenant_id=tenant_id,
                message=message,
            ):
                yield chunk
        except Exception as exc:
            logger.warning(
                "ai_cs_chat stream exception sessionId=%d errorType=%s",
                session_id, type(exc).__name__,
            )
            yield (
                'event: error\ndata: '
                '{"type":"error","message":"AI 客服暂时不可用，请稍后重试"}\n\n'
            )

    return _sse_response(event_generator())


# ============================================================
# 上下文压缩
# ============================================================

@router.post("/compress")
async def ai_cs_compress(
    body: Optional[dict] = None,
    x_internal_tenant_id: Optional[str] = Header(None, alias="X-Internal-Tenant-Id"),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """上下文压缩端点。

    Java AiCsController.compress 通过 postInternalForData 调用本端点，
    body: {sessionId, userId, tenantId, messages?}
    - 若 body.messages 为空，Python 端无法获取历史消息（消息持久化在 Java 侧），
      返回空摘要，由 Java 端处理。
    - 若 body.messages 非空，Python 调用通用模型生成摘要并返回。

    本端点不扣费（与 Java 注释一致）。
    """
    payload = body or {}
    tenant_id_raw = payload.get("tenantId") or x_internal_tenant_id
    try:
        tenant_id = int(tenant_id_raw) if tenant_id_raw is not None else 0
    except (TypeError, ValueError):
        tenant_id = 0
    if tenant_id <= 0:
        return ResultObject.validate_failed("tenantId 必须为正整数")

    try:
        user_id = int(payload.get("userId") or 0)
    except (TypeError, ValueError):
        user_id = 0
    if user_id <= 0:
        return ResultObject.validate_failed("userId 必须为正整数")

    try:
        session_id = int(payload.get("sessionId") or 0)
    except (TypeError, ValueError):
        session_id = 0
    if session_id <= 0:
        return ResultObject.validate_failed("sessionId 必须为正整数")

    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        return ResultObject.validate_failed("messages 必须为数组")

    if not messages:
        # Java 端未传递历史消息，返回空摘要
        return ResultObject.success({
            "sessionId": session_id,
            "summary": "",
            "message": "无历史消息可压缩",
        })

    try:
        summary = await compress_context(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            messages=messages,
        )
        if not summary:
            return ResultObject.success({
                "sessionId": session_id,
                "summary": "",
                "message": "压缩失败，请稍后重试",
            })
        return ResultObject.success({
            "sessionId": session_id,
            "summary": summary,
        })
    except Exception as exc:
        logger.warning(
            "ai_cs_compress failed sessionId=%d errorType=%s",
            session_id, type(exc).__name__,
        )
        return ResultObject.failed("上下文压缩服务暂时不可用", code=503)


# ============================================================
# 工具执行
# ============================================================

@router.post("/tool/execute")
async def ai_cs_tool_execute(
    body: Optional[dict] = None,
    x_internal_tenant_id: Optional[str] = Header(None, alias="X-Internal-Tenant-Id"),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """执行已确认/拒绝的工具调用。

    Java AiCsController.confirmTool 通过 postInternalForData 调用本端点，
    body: {sessionId, userId, tenantId, toolCallId, accept, tool?, arguments?}
    - accept=true: 执行工具
    - accept=false: 标记为拒绝

    返回结构（与 ai_cs_runtime.execute_confirmed_tool 一致）：
    {
        "toolCallId": int,
        "tool": str,
        "status": "executed" | "rejected" | "failed",
        "result": dict,
        "message": str,
    }

    注意：本端点需要 tool_name 和 arguments 才能执行工具。
    Java 端目前仅传 toolCallId 和 accept，未传 tool_name/arguments。
    实际部署时，Java 端需补充传递，或 Python 端从 ai_cs_tool_call 表查询。
    本实现兼容两种方式：优先从 body 读取，缺失时尝试数据库查询。
    """
    payload = body or {}
    tenant_id_raw = payload.get("tenantId") or x_internal_tenant_id
    try:
        tenant_id = int(tenant_id_raw) if tenant_id_raw is not None else 0
    except (TypeError, ValueError):
        tenant_id = 0
    if tenant_id <= 0:
        return ResultObject.validate_failed("tenantId 必须为正整数")

    try:
        user_id = int(payload.get("userId") or 0)
    except (TypeError, ValueError):
        user_id = 0
    if user_id <= 0:
        return ResultObject.validate_failed("userId 必须为正整数")

    try:
        session_id = int(payload.get("sessionId") or 0)
    except (TypeError, ValueError):
        session_id = 0
    if session_id <= 0:
        return ResultObject.validate_failed("sessionId 必须为正整数")

    try:
        tool_call_id = int(payload.get("toolCallId") or 0)
    except (TypeError, ValueError):
        tool_call_id = 0
    if tool_call_id <= 0:
        return ResultObject.validate_failed("toolCallId 必须为正整数")

    accept = bool(payload.get("accept"))

    # 从 body 读取工具名与参数；缺失时尝试从数据库查询
    tool_name = str(payload.get("tool") or "").strip()
    arguments = payload.get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}

    if not tool_name and accept:
        # 尝试从 ai_cs_tool_call 表查询（表由 Java 管理，可能不存在）
        try:
            from sqlalchemy import text as _text
            row = (await db.execute(_text("""
                SELECT tool_name, arguments_json FROM ai_cs_tool_call
                WHERE id = :id AND tenant_id = :tenant_id
                LIMIT 1
            """), {"id": tool_call_id, "tenant_id": tenant_id})).mappings().first()
            if row:
                tool_name = str(row.get("tool_name") or "").strip()
                raw_args = row.get("arguments_json")
                if raw_args:
                    try:
                        import json as _json
                        parsed_args = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        if isinstance(parsed_args, dict):
                            arguments = parsed_args
                    except Exception:
                        arguments = {}
        except Exception as exc:
            logger.debug(
                "ai_cs_tool_execute load tool_call failed toolCallId=%d errorType=%s",
                tool_call_id, type(exc).__name__,
            )

    try:
        result = await execute_confirmed_tool(
            db,
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            tool_call_id=tool_call_id,
            accept=accept,
            tool_name=tool_name,
            arguments=arguments,
        )
        return ResultObject.success(result)
    except Exception as exc:
        logger.warning(
            "ai_cs_tool_execute failed toolCallId=%d errorType=%s",
            tool_call_id, type(exc).__name__,
        )
        return ResultObject.failed("工具执行失败，请稍后重试", code=503)


# ============================================================
# 知识库索引重建（内部，由 Java AdminAiCsController 调用）
# ============================================================

@router.post("/knowledge/rebuild")
async def ai_cs_knowledge_rebuild(
    _: None = Depends(verify_internal_token),
):
    """重建 AI 客服知识库向量索引。

    Java 端 AdminAiCsController 收到管理员触发后调用本端点。
    本端点扫描 ai_cs_knowledge 表中 enabled=1 的条目，
    重新生成向量并写入 SimpleVectorStore，供 RAG 检索使用。
    """
    try:
        from app.services.rag_service import rebuild_ai_cs_knowledge_index
        count = await rebuild_ai_cs_knowledge_index()
        return ResultObject.success({
            "rebuilt": True,
            "count": count,
            "message": f"知识库索引重建完成，共 {count} 条",
        })
    except ImportError:
        # rag_service 未实现 rebuild_ai_cs_knowledge_index 时降级为占位
        return ResultObject.success({
            "rebuilt": False,
            "count": 0,
            "message": "知识库索引重建暂未启用（rag_service 未提供实现）",
        })
    except Exception as exc:
        logger.exception("ai_cs_knowledge_rebuild failed: %s", exc)
        return ResultObject.failed("知识库索引重建失败", code=503)


# ============================================================
# 健康检查（内部）
# ============================================================

@router.get("/health")
async def ai_cs_health(
    _: None = Depends(verify_internal_token),
):
    """AI 客服模块健康检查。"""
    return ResultObject.success({
        "status": "ok",
        "module": "ai_cs",
        "capabilities": [
            "chat",
            "compress",
            "tool_execute",
            "knowledge_rebuild",
        ],
    })
