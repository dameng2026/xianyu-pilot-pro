"""
工作流 API 路由。

提供工作流定义管理、节点执行、AI 筛选/润色/生图、发布、任务记录和日志查看等完整 API。
"""
from __future__ import annotations

import json
import logging
import random
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select, text, update as sql_update, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.http_failures import log_route_failure, safe_route_failure
from ....core.response import ResultObject
from ....models.entities import (
    WorkflowDefinition, WorkflowNode, WorkflowEdge, WorkflowExecution,
    WorkflowNodeLog, WorkflowTimeline, WorkflowArtifact,
    WorkflowStateVariable, WorkflowCheckpoint, WorkflowPublishRecord,
)
from ....schemas.workflow import (
    WorkflowDefinitionDTO, WorkflowDefinitionListDTO, WorkflowOverviewDTO,
    WorkflowExecutionDTO, WorkflowExecutionListDTO, WorkflowNodeResultDTO,
    WorkflowExecuteReqDTO, RecentRunDTO, NodeLogDTO,
    AiScreenReqDTO, AiScreenResultDTO, AiRewriteReqDTO, AiRewriteResultDTO,
    AiGenerateImageReqDTO, AiGenerateImageResultDTO,
    WorkflowPublishReqDTO, WorkflowPublishResultDTO,
)
from ..deps import get_current_user
from ....services.ai_provider import generate_text, get_polish_keywords_restriction, enforce_polish_restriction
from ....services.ai_billing import (
    AiBillingError,
    AiBillingPaymentRequired,
    build_request_id,
    charge_text_usage,
    charge_image_usage,
    estimate_text_tokens,
    precheck_ai_usage,
)
from ....services.automation_runtime import (
    execute_workflow, insert_timeline, save_state_variable,
    save_checkpoint, _prepare_image_prompt_category_configs, _resolve_image_prompt_for_item_with_ai,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflow")

DEFAULT_IMAGE_PROMPT_FALLBACK = (
    "生成1张适合闲鱼/淘宝风格的中国电商商品主图（1:1正方形）。"
    "要求：不是平台截图，不要店铺名、头像、导航栏、二维码、水印、联系方式。"
    "画面必须只有一个明确主视觉，主体大、居中、易识别，整体高对比、强吸睛、适合手机缩略图点击。"
    "采用中文电商广告封面风格，可包含简短有力的大标题和2到3个短卖点标签，但不要堆满小字。"
    "背景简洁有层次，可用深色或亮色渐变搭配高饱和点缀，突出商品价值与成交感。"
    "不要复杂场景，不要3D渲染感，不要赛博霓虹，不要艺术海报感，要像高点击率商品主图。"
)

TENANT_CONTEXT_REQUIRED_MESSAGE = "缺少租户上下文"


def _require_tenant(current_user: dict) -> int:
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise ValueError("缺少租户上下文")
    return int(tenant_id)


def _require_billing_user(current_user: dict) -> int:
    try:
        user_id = int(current_user.get("user_id") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("缺少用户上下文") from exc
    if user_id <= 0:
        raise ValueError("缺少用户上下文")
    return user_id


async def _precheck_text_billing(
    *, tenant_id: int, user_id: int, scene: str, prompt: str
) -> str:
    request_id = build_request_id(scene)
    await precheck_ai_usage({
        "tenantId": tenant_id,
        "userId": user_id,
        "scene": scene,
        "providerName": "default",
        "modelName": "default",
        "modelType": "chat",
        "promptTokens": estimate_text_tokens(prompt),
        "completionTokens": 0,
        "requestId": request_id,
    })
    return request_id


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _generate_execution_no() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = random.randint(1000, 9999)
    return f"WF{ts}{rand}"


# ==================== 工作流定义管理 ====================


@router.get("/overview", response_model=ResultObject[WorkflowOverviewDTO])
async def workflow_overview(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        # 工作流总数
        total_res = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.deleted == 0,
            )
        )
        total = len(total_res.scalars().all())

        # 已发布数
        pub_res = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.deleted == 0,
                WorkflowDefinition.status == "published",
            )
        )
        enabled = len(pub_res.scalars().all())

        # 今日执行数
        today_count_res = await db.execute(text("""
            SELECT COUNT(*) FROM workflow_execution
            WHERE tenant_id=:tenant_id AND deleted=0
              AND DATE(created_time)=CURRENT_DATE()
        """), {"tenant_id": tenant_id})
        today_count = int(today_count_res.scalar() or 0)

        # 成功率
        success_res = await db.execute(text("""
            SELECT COUNT(*) FROM workflow_execution
            WHERE tenant_id=:tenant_id AND deleted=0 AND status='success'
        """), {"tenant_id": tenant_id})
        success_count = int(success_res.scalar() or 0)
        total_exec = await db.execute(text("""
            SELECT COUNT(*) FROM workflow_execution
            WHERE tenant_id=:tenant_id AND deleted=0
        """), {"tenant_id": tenant_id})
        total_exec_count = int(total_exec.scalar() or 0)
        rate = round(success_count / total_exec_count * 100, 1) if total_exec_count > 0 else 0.0

        return ResultObject.success(WorkflowOverviewDTO(
            workflow_count=total,
            enabled_count=enabled,
            today_execution_count=today_count,
            success_rate=rate,
        ))
    except Exception as e:
        return safe_route_failure(logger, e, operation="workflow overview", user_message="工作流概览暂不可用，请稍后重试", code=503)


@router.get("/definitions", response_model=ResultObject[WorkflowDefinitionListDTO])
async def list_workflows(
    keyword: str = Query(""),
    status: str = Query(""),
    current: int = Query(1),
    size: int = Query(20),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        current = max(current, 1)
        size = min(max(size, 1), 100)
        offset = (current - 1) * size

        conditions = [
            "tenant_id = :tenant_id",
            "deleted = 0",
        ]
        params: dict = {"tenant_id": tenant_id, "limit": size, "offset": offset}
        if keyword:
            conditions.append("name LIKE :kw")
            params["kw"] = f"%{keyword}%"
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions)

        total_res = await db.execute(text(f"""
            SELECT COUNT(*) FROM workflow_definition WHERE {where_clause}
        """), params)
        total = int(total_res.scalar() or 0)

        rows_res = await db.execute(text(f"""
            SELECT id, name, description, trigger_type, status, version,
                   execution_count, created_time, updated_time
            FROM workflow_definition
            WHERE {where_clause}
            ORDER BY updated_time DESC, id DESC
            LIMIT :limit OFFSET :offset
        """), params)
        rows = [dict(r) for r in rows_res.mappings().all()]

        return ResultObject.success(WorkflowDefinitionListDTO(
            records=rows, current=current, size=size, total=total,
        ))
    except Exception as e:
        return safe_route_failure(logger, e, operation="list workflow definitions", user_message="工作流列表暂不可用，请稍后重试", code=503)


@router.get("/definitions/{workflow_id}", response_model=ResultObject[WorkflowDefinitionDTO])
async def get_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.deleted == 0,
            )
        )
        wf = result.scalar_one_or_none()
        if not wf:
            return ResultObject.failed("工作流不存在")

        # 查询节点
        nodes_res = await db.execute(
            select(WorkflowNode).where(
                WorkflowNode.workflow_id == workflow_id,
                WorkflowNode.tenant_id == tenant_id,
                WorkflowNode.deleted == 0,
            ).order_by(WorkflowNode.sort_order)
        )
        nodes = nodes_res.scalars().all()

        # 查询连线
        edges_res = await db.execute(
            select(WorkflowEdge).where(
                WorkflowEdge.workflow_id == workflow_id,
                WorkflowEdge.tenant_id == tenant_id,
                WorkflowEdge.deleted == 0,
            ).order_by(WorkflowEdge.sort_order)
        )
        edges = edges_res.scalars().all()

        return ResultObject.success(WorkflowDefinitionDTO(
            id=wf.id,
            name=wf.name,
            description=wf.description or "",
            trigger_type=wf.trigger_type or "manual",
            config=wf.config_json or {},
            canvas={"zoom": (wf.canvas_json or {}).get("zoom", 100)} if wf.canvas_json else {"zoom": 100},
            status=wf.status or "draft",
            version=wf.version or 1,
            execution_count=wf.execution_count or 0,
            nodes=[{
                "id": n.node_key,
                "nodeKey": n.node_key,
                "name": n.node_name,
                "nodeName": n.node_name,
                "type": n.node_type,
                "nodeType": n.node_type,
                "x": n.position_x or 80,
                "y": n.position_y or 80,
                "positionX": n.position_x or 80,
                "positionY": n.position_y or 80,
                "config": n.config_json or {},
                "retry": bool(n.retry_enabled),
                "retryEnabled": bool(n.retry_enabled),
                "retryCount": n.retry_count or 0,
                "retryIntervalSeconds": n.retry_interval_seconds or 30,
            } for n in nodes],
            edges=[{
                "source": e.source_node_key,
                "sourceNodeKey": e.source_node_key,
                "target": e.target_node_key,
                "targetNodeKey": e.target_node_key,
                "condition": e.condition_expr or "",
                "conditionExpr": e.condition_expr or "",
            } for e in edges],
            created_time=str(wf.created_time) if wf.created_time else None,
            updated_time=str(wf.updated_time) if wf.updated_time else None,
        ))
    except Exception as e:
        return safe_route_failure(logger, e, operation="get workflow definition", user_message="查询工作流失败，请稍后重试")


@router.post("/definitions", response_model=ResultObject)
async def create_workflow(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
        user_id = current_user.get("user_id", 0)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        name = _text(body.get("name") or "未命名工作流")
        description = _text(body.get("description") or "")
        trigger_type = _text(body.get("triggerType") or "manual")
        config = body.get("config") or {}
        canvas = body.get("canvas") or {"zoom": 100}
        nodes = body.get("nodes") or []
        edges = body.get("edges") or []

        wf = WorkflowDefinition(
            tenant_id=tenant_id,
            user_id=_safe_int(user_id),
            name=name,
            description=description,
            trigger_type=trigger_type,
            config_json=config,
            canvas_json=canvas,
            status="draft",
            version=1,
        )
        db.add(wf)
        await db.commit()
        await db.refresh(wf)

        # 保存节点
        for idx, n in enumerate(nodes):
            node_key = _text(n.get("nodeKey") or n.get("id") or f"node_{idx}")
            node = WorkflowNode(
                tenant_id=tenant_id,
                workflow_id=wf.id,
                node_key=node_key,
                node_name=_text(n.get("nodeName") or n.get("name") or node_key),
                node_type=_text(n.get("nodeType") or n.get("type") or "action"),
                position_x=_safe_int(n.get("x") or n.get("positionX"), 80),
                position_y=_safe_int(n.get("y") or n.get("positionY"), 80),
                config_json=n.get("config") or n.get("params") or {},
                retry_enabled=1 if n.get("retry") or n.get("retryEnabled") else 0,
                retry_count=_safe_int(n.get("retryCount"), 0),
                retry_interval_seconds=_safe_int(n.get("retryIntervalSeconds"), 30),
                sort_order=idx,
            )
            db.add(node)

        # 保存连线
        for idx, e in enumerate(edges):
            edge = WorkflowEdge(
                tenant_id=tenant_id,
                workflow_id=wf.id,
                source_node_key=_text(e.get("sourceNodeKey") or e.get("source")),
                target_node_key=_text(e.get("targetNodeKey") or e.get("target")),
                condition_expr=_text(e.get("conditionExpr") or e.get("condition") or ""),
                sort_order=idx,
            )
            db.add(edge)

        await db.commit()
        return ResultObject.success({"id": wf.id, "name": wf.name, "message": "创建成功"})
    except Exception as e:
        await db.rollback()
        return safe_route_failure(logger, e, operation="create workflow definition", user_message="创建工作流失败，请稍后重试")


@router.put("/definitions/{workflow_id}", response_model=ResultObject)
async def update_workflow(
    workflow_id: int,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.deleted == 0,
            )
        )
        wf = result.scalar_one_or_none()
        if not wf:
            return ResultObject.failed("工作流不存在")

        if "name" in body:
            wf.name = _text(body["name"])
        if "description" in body:
            wf.description = _text(body["description"])
        if "triggerType" in body:
            wf.trigger_type = _text(body["triggerType"])
        if "config" in body:
            wf.config_json = body["config"]
        if "canvas" in body:
            wf.canvas_json = body["canvas"]

        await db.commit()

        # 更新节点
        nodes = body.get("nodes")
        if nodes is not None:
            # 软删除旧节点
            await db.execute(
                sql_update(WorkflowNode).where(
                    WorkflowNode.workflow_id == workflow_id,
                    WorkflowNode.tenant_id == tenant_id,
                ).values(deleted=1)
            )
            for idx, n in enumerate(nodes):
                node_key = _text(n.get("nodeKey") or n.get("id") or f"node_{idx}")
                db_node = WorkflowNode(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    node_key=node_key,
                    node_name=_text(n.get("nodeName") or n.get("name") or node_key),
                    node_type=_text(n.get("nodeType") or n.get("type") or "action"),
                    position_x=_safe_int(n.get("x") or n.get("positionX"), 80),
                    position_y=_safe_int(n.get("y") or n.get("positionY"), 80),
                    config_json=n.get("config") or n.get("params") or {},
                    retry_enabled=1 if n.get("retry") or n.get("retryEnabled") else 0,
                    retry_count=_safe_int(n.get("retryCount"), 0),
                    retry_interval_seconds=_safe_int(n.get("retryIntervalSeconds"), 30),
                    sort_order=idx,
                )
                db.add(db_node)

        # 更新连线
        edges = body.get("edges")
        if edges is not None:
            await db.execute(
                sql_update(WorkflowEdge).where(
                    WorkflowEdge.workflow_id == workflow_id,
                    WorkflowEdge.tenant_id == tenant_id,
                ).values(deleted=1)
            )
            for idx, e in enumerate(edges):
                db_edge = WorkflowEdge(
                    tenant_id=tenant_id,
                    workflow_id=workflow_id,
                    source_node_key=_text(e.get("sourceNodeKey") or e.get("source")),
                    target_node_key=_text(e.get("targetNodeKey") or e.get("target")),
                    condition_expr=_text(e.get("conditionExpr") or e.get("condition") or ""),
                    sort_order=idx,
                )
                db.add(db_edge)

        await db.commit()
        return ResultObject.success({"id": workflow_id, "message": "更新成功"})
    except Exception as e:
        await db.rollback()
        return safe_route_failure(logger, e, operation="update workflow definition", user_message="更新工作流失败，请稍后重试")


@router.delete("/definitions/{workflow_id}", response_model=ResultObject)
async def delete_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.deleted == 0,
            )
        )
        wf = result.scalar_one_or_none()
        if not wf:
            return ResultObject.failed("工作流不存在")

        wf.deleted = 1
        await db.execute(
            sql_update(WorkflowNode).where(
                WorkflowNode.workflow_id == workflow_id,
            ).values(deleted=1)
        )
        await db.execute(
            sql_update(WorkflowEdge).where(
                WorkflowEdge.workflow_id == workflow_id,
            ).values(deleted=1)
        )
        await db.commit()
        return ResultObject.success({"message": "删除成功"})
    except Exception as e:
        return safe_route_failure(logger, e, operation="delete workflow definition", user_message="删除工作流失败，请稍后重试")


@router.post("/definitions/{workflow_id}/publish", response_model=ResultObject)
async def publish_workflow(
    workflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.deleted == 0,
            )
        )
        wf = result.scalar_one_or_none()
        if not wf:
            return ResultObject.failed("工作流不存在")

        # 校验节点和连线
        nodes_res = await db.execute(
            select(WorkflowNode).where(
                WorkflowNode.workflow_id == workflow_id,
                WorkflowNode.deleted == 0,
            )
        )
        nodes = nodes_res.scalars().all()
        if not nodes:
            return ResultObject.failed("工作流没有节点，无法发布")

        edges_res = await db.execute(
            select(WorkflowEdge).where(
                WorkflowEdge.workflow_id == workflow_id,
                WorkflowEdge.deleted == 0,
            )
        )
        edges = edges_res.scalars().all()

        has_trigger = any(n.node_type == "TRIGGER" for n in nodes)
        if not has_trigger:
            return ResultObject.failed("工作流缺少触发节点")

        has_publish = any(n.node_type == "PUBLISH" for n in nodes)
        if not has_publish:
            return ResultObject.failed("工作流缺少发布节点，必须包含发布节点")

        if not edges:
            return ResultObject.failed("工作流节点之间没有连线，请先连接节点")

        wf.status = "published"
        wf.version = (wf.version or 1) + 1
        await db.commit()
        return ResultObject.success({"id": workflow_id, "version": wf.version, "message": "发布成功"})
    except Exception as e:
        return safe_route_failure(logger, e, operation="publish workflow definition", user_message="发布工作流失败，请稍后重试")


# ==================== 工作流执行 ====================


async def _run_workflow_background(
    tenant_id: int,
    workflow_id: int,
    execution_id: int,
    wf_name: str,
    execute_payload: dict,
):
    """
    后台执行工作流：使用独立 DB session，执行完成后更新 execution 记录。
    fire-and-forget：调用方立即返回，不等待此函数完成，避免 HTTP 超时。
    """
    from ....core.database import async_session as _async_session
    from datetime import datetime as _dt2
    import asyncio as _asyncio
    async with _async_session() as bg_db:
        try:
            exec_result = await execute_workflow(bg_db, execute_payload)
            status = exec_result.get("status", "failed")
            node_results = exec_result.get("nodeResults", [])
            success_count = sum(1 for nr in node_results if nr.get("status") == "success")
            failed_count = sum(1 for nr in node_results if nr.get("status") == "failed")
            now_str = _dt2.now().strftime("%Y-%m-%d %H:%M:%S")
            # ★ 使用 default=str 兜底，避免 timeline/nodeResults 内含 datetime 对象导致序列化失败
            def _json_default(o):
                if hasattr(o, "isoformat"):
                    return o.isoformat()
                return str(o)
            output_str = json.dumps({
                "nodeResults": node_results,
                "artifacts": exec_result.get("artifacts", []),
                "timeline": exec_result.get("timeline", []),
            }, ensure_ascii=False, default=_json_default)
            err_msg = _text(exec_result.get("errorMessage") or "")
            # ★ 用 raw SQL 更新（与 execute_workflow 风格一致，避免 ORM session 状态问题）
            await bg_db.execute(text("""
                UPDATE workflow_execution
                SET status=:s, progress=100, finished_time=:ft,
                    error_message=:err, output_json=:o, updated_time=:ft
                WHERE id=:eid
            """), {"s": status, "ft": now_str, "err": err_msg, "o": output_str, "eid": execution_id})
            await bg_db.execute(text("""
                UPDATE workflow_definition
                SET execution_count = COALESCE(execution_count, 0) + 1, updated_time = :ft
                WHERE id = :wid
            """), {"ft": now_str, "wid": workflow_id})
            await bg_db.commit()
            logger.info("[BG-WORKFLOW] 后台执行完成 execution=%s status=%s success=%d failed=%d",
                        execution_id, status, success_count, failed_count)
        except _asyncio.CancelledError:
            try:
                now_str = _dt2.now().strftime("%Y-%m-%d %H:%M:%S")
                await bg_db.execute(text("""
                    UPDATE workflow_execution SET status='failed', progress=100, finished_time=:ft,
                        error_message='工作流执行被取消(外部连接关闭)，已发布商品已保留', updated_time=:ft
                    WHERE id=:eid AND status='running'
                """), {"ft": now_str, "eid": execution_id})
                await bg_db.commit()
            except Exception:
                pass
            logger.warning("[BG-WORKFLOW] 后台执行被取消 execution=%s", execution_id)
        except Exception as e:
            log_route_failure(logger, e, operation="background workflow execution")
            try:
                now_str = _dt2.now().strftime("%Y-%m-%d %H:%M:%S")
                await bg_db.execute(text("""
                    UPDATE workflow_execution SET status='failed', progress=100, finished_time=:ft,
                        error_message=:err, updated_time=:ft
                    WHERE id=:eid
                """), {"ft": now_str, "err": "后台执行异常，请联系管理员并提供执行编号", "eid": execution_id})
                await bg_db.commit()
            except Exception:
                pass


@router.post("/definitions/{workflow_id}/execute", response_model=ResultObject)
async def execute_workflow_definition(
    workflow_id: int,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    执行工作流。
    创建执行记录 → 调用执行器 → 更新执行记录 → 返回结果。
    """
    try:
        tenant_id = _require_tenant(current_user)
        user_id = current_user.get("user_id", 0)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        # 读取工作流定义
        result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.deleted == 0,
            )
        )
        wf = result.scalar_one_or_none()
        if not wf:
            return ResultObject.failed("工作流不存在")

        # 读取节点和连线
        nodes_res = await db.execute(
            select(WorkflowNode).where(
                WorkflowNode.workflow_id == workflow_id,
                WorkflowNode.deleted == 0,
            ).order_by(WorkflowNode.sort_order)
        )
        nodes = nodes_res.scalars().all()

        edges_res = await db.execute(
            select(WorkflowEdge).where(
                WorkflowEdge.workflow_id == workflow_id,
                WorkflowEdge.deleted == 0,
            ).order_by(WorkflowEdge.sort_order)
        )
        edges = edges_res.scalars().all()

        if not nodes:
            return ResultObject.failed("工作流没有节点")

        # 判断是否为测试模式
        is_test = bool(body.get("isTest") or body.get("is_test") or False)
        trigger_mode = _text(body.get("triggerMode") or "manual")
        keywords = body.get("keywords") or []
        input_data = body.get("input") or {}

        # 创建执行记录
        execution_no = _generate_execution_no()
        execution = WorkflowExecution(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            execution_no=execution_no,
            trigger_mode=trigger_mode,
            status="running",
            progress=0,
            error_message="",
            started_time=datetime.now(),
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        execution_id = execution.id

        # 记录开始时间线
        await insert_timeline(db, tenant_id, execution_id, workflow_id, "system", "INFO",
                              "workflow_start", f"工作流触发: {wf.name}",
                              {"isTest": is_test, "triggerMode": trigger_mode})

        # 构造执行器负载
        node_list = [{
            "id": n.node_key,
            "nodeKey": n.node_key,
            "name": n.node_name,
            "nodeName": n.node_name,
            "type": n.node_type,
            "nodeType": n.node_type,
            "config": n.config_json or {},
            "params": n.config_json or {},
            "x": n.position_x,
            "y": n.position_y,
        } for n in nodes]

        edge_list = [{
            "source": e.source_node_key,
            "sourceNodeKey": e.source_node_key,
            "target": e.target_node_key,
            "targetNodeKey": e.target_node_key,
            "condition": e.condition_expr or "",
            "conditionExpr": e.condition_expr or "",
        } for e in edges]

        execute_payload = {
            "tenantId": tenant_id,
            "workflowId": workflow_id,
            "executionId": execution_id,
            "workflow": {
                "id": workflow_id,
                "name": wf.name,
                "nodes": node_list,
                "edges": edge_list,
            },
            "input": {
                "keywords": keywords,
                **input_data,
            },
        }

        # ★ 异步化：立即返回 executionId（status=running），后台 fire-and-forget 执行，
        #   避免同步等待导致 Java 端 HTTP 超时（工作流涉及生图+多商品发布，耗时远超 HTTP 超时）。
        #   前端通过 /executions/{id} 接口轮询执行状态和结果。
        import asyncio as _asyncio
        _asyncio.create_task(_run_workflow_background(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            wf_name=wf.name,
            execute_payload=execute_payload,
        ))
        logger.info("[WORKFLOW] 已提交后台执行 execution=%s workflow=%s", execution_id, wf.name)

        # 构建返回结果：立即返回 running 状态，前端轮询获取最终结果
        return ResultObject.success(WorkflowExecutionDTO(
            id=execution_id,
            execution_no=execution_no,
            workflow_id=workflow_id,
            workflow_name=wf.name,
            trigger_mode=trigger_mode,
            status="running",
            progress=0,
            node_total=len(nodes),
            node_success=0,
            node_failed=0,
            is_test=is_test,
            started_time=str(execution.started_time) if execution.started_time else None,
            finished_time=None,
            duration_ms=0,
            total_duration=0,
            error_message="",
            output={"message": "工作流已提交后台执行，请通过执行详情查看进度和结果", "nodeResults": [], "artifacts": []},
            steps=[],
            log_entries=[{
                "level": "info",
                "nodeName": "system",
                "nodeType": "",
                "message": "工作流已提交后台执行",
                "duration": 0,
                "time": datetime.now().strftime("%H:%M:%S"),
                "detail": "异步执行中，请刷新查看进度",
            }],
        ))

    except Exception as e:
        await db.rollback()
        return safe_route_failure(logger, e, operation="execute workflow", user_message="执行工作流失败，请稍后重试")


# ==================== 执行记录查询 ====================


@router.get("/executions", response_model=ResultObject[WorkflowExecutionListDTO])
async def list_executions(
    workflow_id: Optional[int] = Query(None),
    status: str = Query(""),
    keyword: str = Query(""),
    current: int = Query(1),
    size: int = Query(20),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        current = max(current, 1)
        size = min(max(size, 1), 100)
        offset = (current - 1) * size

        conditions = ["tenant_id = :tenant_id", "deleted = 0"]
        params: dict = {"tenant_id": tenant_id, "limit": size, "offset": offset}

        if workflow_id:
            conditions.append("workflow_id = :workflow_id")
            params["workflow_id"] = workflow_id
        if status:
            conditions.append("status = :status")
            params["status"] = status
        if keyword:
            conditions.append("execution_no LIKE :kw")
            params["kw"] = f"%{keyword}%"

        where_clause = " AND ".join(conditions)

        total_res = await db.execute(text(f"""
            SELECT COUNT(*) FROM workflow_execution WHERE {where_clause}
        """), params)
        total = int(total_res.scalar() or 0)

        rows_res = await db.execute(text(f"""
            SELECT id, workflow_id, execution_no, trigger_mode,
                   status, current_node_key, progress,
                   started_time, finished_time,
                   error_message, created_time
            FROM workflow_execution
            WHERE {where_clause}
            ORDER BY created_time DESC, id DESC
            LIMIT :limit OFFSET :offset
        """), params)
        rows = []
        for r in rows_res.mappings().all():
            d = dict(r)
            d["triggerMode"] = d.pop("trigger_mode", "manual")
            d["currentNode"] = d.pop("current_node_key", "")
            d["isTest"] = False
            rows.append(d)

        return ResultObject.success(WorkflowExecutionListDTO(
            records=rows, current=current, size=size, total=total,
        ))
    except Exception as e:
        return safe_route_failure(logger, e, operation="list workflow executions", user_message="工作流执行记录暂不可用，请稍后重试", code=503)


@router.get("/executions/{execution_id}", response_model=ResultObject[WorkflowExecutionDTO])
async def get_execution_detail(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        result = await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.tenant_id == tenant_id,
                WorkflowExecution.deleted == 0,
            )
        )
        exe = result.scalar_one_or_none()
        if not exe:
            return ResultObject.failed("执行记录不存在")

        # 查询节点日志
        logs_res = await db.execute(
            select(WorkflowNodeLog).where(
                WorkflowNodeLog.execution_id == execution_id,
                WorkflowNodeLog.tenant_id == tenant_id,
                WorkflowNodeLog.deleted == 0,
            ).order_by(WorkflowNodeLog.id)
        )
        logs = logs_res.scalars().all()

        # 查询时间线
        tl_res = await db.execute(
            select(WorkflowTimeline).where(
                WorkflowTimeline.execution_id == execution_id,
                WorkflowTimeline.tenant_id == tenant_id,
                WorkflowTimeline.deleted == 0,
            ).order_by(WorkflowTimeline.id)
        )
        timeline = [dict(r) for r in tl_res.mappings().all()]

        # 查询产物
        art_res = await db.execute(
            select(WorkflowArtifact).where(
                WorkflowArtifact.execution_id == execution_id,
                WorkflowArtifact.tenant_id == tenant_id,
                WorkflowArtifact.deleted == 0,
            ).order_by(WorkflowArtifact.id)
        )
        artifacts = [dict(r) for r in art_res.mappings().all()]

        # 查询状态变量
        sv_res = await db.execute(
            select(WorkflowStateVariable).where(
                WorkflowStateVariable.execution_id == execution_id,
                WorkflowStateVariable.tenant_id == tenant_id,
                WorkflowStateVariable.deleted == 0,
            ).order_by(WorkflowStateVariable.id)
        )
        state_vars = [dict(r) for r in sv_res.mappings().all()]

        output_data = exe.output_json or {}

        return ResultObject.success(WorkflowExecutionDTO(
            id=exe.id,
            execution_no=exe.execution_no,
            workflow_id=exe.workflow_id,
            workflow_name=exe.workflow_name or "",
            trigger_mode=exe.trigger_mode or "manual",
            status=exe.status or "unknown",
            current_node=exe.current_node_key or "",
            progress=exe.progress or 0,
            node_total=exe.node_total or 0,
            node_success=exe.node_success or 0,
            node_failed=exe.node_failed or 0,
            is_test=bool(exe.is_test),
            started_time=str(exe.started_time) if exe.started_time else None,
            finished_time=str(exe.finished_time) if exe.finished_time else None,
            created_time=str(exe.created_time) if exe.created_time else None,
            duration_ms=exe.duration_ms or 0,
            total_duration=exe.duration_ms or 0,
            error_message=exe.error_message or "",
            output=output_data,
            steps=[WorkflowNodeResultDTO(
                node_key=log.node_key,
                node_name=log.node_name or "",
                node_type=log.node_type or "",
                status=log.status or "unknown",
                input=log.input_json or {},
                output=log.output_json or {},
                error_message=log.error_message or "",
                duration_ms=log.duration_ms or 0,
                retry_count=log.retry_count or 0,
                is_skipped=bool(log.is_skipped),
                ai_request_summary=log.ai_request_summary or "",
                ai_response_summary=log.ai_response_summary or "",
                publish_params_summary=log.publish_params_summary or "",
            ) for log in logs],
            timeline=timeline,
            artifacts=artifacts,
            state_variables=state_vars,
            log_entries=[{
                "level": "success" if log.status == "success" else "error",
                "nodeName": log.node_name or log.node_key,
                "nodeType": log.node_type or "",
                "message": log.error_message or ("节点执行成功" if log.status == "success" else ""),
                "duration": log.duration_ms or 0,
                "time": str(log.started_time) if log.started_time else "",
                "detail": json.dumps(log.output_json or {}, ensure_ascii=False)[:500],
            } for log in logs],
        ))
    except Exception as e:
        return safe_route_failure(logger, e, operation="get workflow execution", user_message="查询执行详情失败，请稍后重试")


@router.post("/executions/{execution_id}/terminate", response_model=ResultObject)
async def terminate_execution(
    execution_id: int,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        result = await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.tenant_id == tenant_id,
                WorkflowExecution.deleted == 0,
            )
        )
        exe = result.scalar_one_or_none()
        if not exe:
            return ResultObject.failed("执行记录不存在")

        reason = _text(body.get("reason") or "用户手动终止")
        exe.status = "terminated"
        exe.finished_time = datetime.now()
        exe.error_message = reason
        await db.commit()

        await insert_timeline(db, tenant_id, execution_id, exe.workflow_id, "system",
                              "WARN", "workflow_terminated",
                              f"工作流已终止: {reason}")

        return ResultObject.success({"message": "已终止"})
    except Exception as e:
        return safe_route_failure(logger, e, operation="terminate workflow execution", user_message="终止执行失败，请稍后重试")


@router.post("/executions/{execution_id}/retry-failed-node", response_model=ResultObject)
async def retry_failed_node(
    execution_id: int,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        result = await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.tenant_id == tenant_id,
                WorkflowExecution.deleted == 0,
            )
        )
        exe = result.scalar_one_or_none()
        if not exe:
            return ResultObject.failed("执行记录不存在")

        node_key = _text(body.get("nodeKey") or body.get("node_key") or "")
        if node_key:
            # 更新指定节点日志状态
            await db.execute(
                sql_update(WorkflowNodeLog).where(
                    WorkflowNodeLog.execution_id == execution_id,
                    WorkflowNodeLog.node_key == node_key,
                ).values(
                    status="retrying",
                    retry_count=WorkflowNodeLog.retry_count + 1,
                    updated_time=datetime.now(),
                )
            )

        exe.status = "running"
        exe.error_message = ""
        await db.commit()

        return ResultObject.success({"message": "已重试失败节点", "executionId": execution_id})
    except Exception as e:
        return safe_route_failure(logger, e, operation="retry workflow node", user_message="重试失败节点出错，请稍后重试")


@router.get("/recent-runs", response_model=ResultObject)
async def recent_runs(
    limit: int = Query(10),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        limit = min(max(limit, 1), 50)
        rows_res = await db.execute(text("""
            SELECT e.id as execution_id, e.execution_no, e.workflow_name, e.status,
                   e.duration_ms, e.error_message, e.created_time,
                   COALESCE(pr.title, '') as goods_title,
                   COALESCE(pr.account_id, 0) as account_id
            FROM workflow_execution e
            LEFT JOIN workflow_publish_record pr ON pr.execution_id = e.id AND pr.deleted = 0
            WHERE e.tenant_id = :tenant_id AND e.deleted = 0
            ORDER BY e.created_time DESC, e.id DESC
            LIMIT :limit
        """), {"tenant_id": tenant_id, "limit": limit})
        rows = []
        for r in rows_res.mappings().all():
            d = dict(r)
            # 解析失败节点信息
            failed_node = ""
            if d.get("error_message"):
                failed_node = d["error_message"]
            rows.append(RecentRunDTO(
                execution_no=d.get("execution_no", ""),
                execution_id=d.get("execution_id"),
                workflow_name=d.get("workflow_name", ""),
                status=d.get("status", ""),
                goods_title=d.get("goods_title", ""),
                account_name="",
                duration_ms=_safe_int(d.get("duration_ms"), 0),
                failed_node=failed_node,
                created_time=str(d.get("created_time")) if d.get("created_time") else None,
            ).model_dump())

        return ResultObject.success(rows)
    except Exception as e:
        return safe_route_failure(logger, e, operation="list recent workflow executions", user_message="最近执行记录暂不可用，请稍后重试", code=503)


# ==================== 环节日志 ====================


@router.get("/executions/{execution_id}/logs", response_model=ResultObject)
async def get_execution_logs(
    execution_id: int,
    node_type: str = Query(""),
    status: str = Query(""),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    try:
        conditions = [
            "execution_id = :execution_id",
            "tenant_id = :tenant_id",
            "deleted = 0",
        ]
        params: dict = {"execution_id": execution_id, "tenant_id": tenant_id}

        if node_type:
            conditions.append("node_type = :node_type")
            params["node_type"] = node_type
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions)

        rows_res = await db.execute(text(f"""
            SELECT node_key, node_name, node_type, status, input_json, output_json,
                   error_message, duration_ms, retry_count, is_skipped,
                   ai_request_summary, ai_response_summary, publish_params_summary,
                   started_time, finished_time, created_time
            FROM workflow_node_log
            WHERE {where_clause}
            ORDER BY id ASC
        """), params)

        logs = []
        for r in rows_res.mappings().all():
            d = dict(r)
            logs.append(NodeLogDTO(
                node_key=_text(d.get("node_key", "")),
                node_name=_text(d.get("node_name", "")),
                node_type=_text(d.get("node_type", "")),
                status=_text(d.get("status", "")),
                started_time=str(d.get("started_time")) if d.get("started_time") else None,
                finished_time=str(d.get("finished_time")) if d.get("finished_time") else None,
                duration_ms=_safe_int(d.get("duration_ms"), 0),
                input_params=d.get("input_json") or {},
                output_result=d.get("output_json") or {},
                error_message=_text(d.get("error_message", "")),
                retry_count=_safe_int(d.get("retry_count"), 0),
                next_node="",
                is_skipped=bool(d.get("is_skipped")),
                ai_request_summary=_text(d.get("ai_request_summary", "")),
                ai_response_summary=_text(d.get("ai_response_summary", "")),
                publish_params_summary=_text(d.get("publish_params_summary", "")),
            ).model_dump())

        return ResultObject.success(logs)
    except Exception as e:
        return safe_route_failure(logger, e, operation="list workflow node logs", user_message="工作流环节日志暂不可用，请稍后重试", code=503)


# ==================== AI 服务接口 ====================


@router.post("/ai/screen", response_model=ResultObject)
async def ai_screen_goods(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    AI 筛选商品：
    调用通用 AI 模型，根据商品信息和筛选规则，判断商品是否符合条件。
    """
    try:
        tenant_id = _require_tenant(current_user)
        user_id = _require_billing_user(current_user)
    except ValueError:
        return ResultObject.failed("缺少租户或用户上下文", 400)

    screen_prompt = _text(body.get("screenPrompt") or body.get("screen_prompt") or "")
    if not screen_prompt:
        return ResultObject.validate_failed("筛选规则不能为空")

    title = _text(body.get("title", ""))
    description = _text(body.get("description", ""))
    price = _text(body.get("price", ""))
    image_url = _text(body.get("imageUrl") or body.get("image_url", ""))
    area = _text(body.get("area", ""))
    seller_info = _text(body.get("sellerInfo") or body.get("seller_info", ""))

    user_prompt = f"""
商品标题: {title}
商品描述: {description}
商品价格: {price}
商品图片: {image_url}
商品地区: {area}
卖家信息: {seller_info}

筛选规则: {screen_prompt}

请严格按照 JSON 格式返回结果，不要包含其他内容：
{{"passed": true/false, "reason": "原因", "score": 0-100}}
"""

    billing_request_id = build_request_id("workflow_screen")
    try:
        billing_request_id = await _precheck_text_billing(
            tenant_id=tenant_id,
            user_id=user_id,
            scene="workflow_screen",
            prompt=user_prompt,
        )
    except AiBillingPaymentRequired:
        return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
    except AiBillingError:
        return ResultObject.failed(AiBillingError.user_message, 503)
    except Exception as exc:
        return safe_route_failure(
            logger,
            exc,
            operation="precheck workflow AI screening",
            user_message="AI 计费服务暂不可用，请稍后重试",
            code=503,
        )

    ai_result = await generate_text(
        "workflow_screen",
        "你是闲鱼商品筛选助手。请根据用户填写的筛选规则，判断商品是否符合条件。返回严格的JSON格式。",
        user_prompt,
        0.3,
        request_id=billing_request_id,
    )

    if not ai_result.get("ok"):
        return ResultObject.failed("AI 筛选服务暂不可用，请稍后重试", 503)

    content = _text(ai_result.get("content", ""))
    # 解析 JSON
    try:
        # 尝试从 content 中提取 JSON
        json_start = content.find("{")
        json_end = content.rfind("}")
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end + 1]
            result_data = json.loads(json_str)
        else:
            result_data = {}
    except Exception:
        result_data = {}

    passed = bool(result_data.get("passed", False))
    reason = _text(result_data.get("reason", "AI 筛选无法判断"))
    score = _safe_int(result_data.get("score"), 0)

    try:
        await charge_text_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            scene="workflow_screen",
            provider_name=_text(ai_result.get("provider", "default")),
            model_name=_text(ai_result.get("model", "default")),
            prompt=user_prompt,
            completion=content,
            request_id=billing_request_id,
            raw_usage=ai_result.get("usage"),
        )
    except AiBillingPaymentRequired:
        return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
    except AiBillingError:
        return ResultObject.failed(AiBillingError.user_message, 503)
    except Exception as exc:
        return safe_route_failure(
            logger,
            exc,
            operation="charge workflow AI screening",
            user_message="AI 计费服务暂不可用，本次结果未返回，请稍后重试",
            code=503,
        )

    return ResultObject.success(AiScreenResultDTO(
        passed=passed,
        reason=reason,
        score=score,
    ).model_dump())


@router.post("/ai/rewrite", response_model=ResultObject)
async def ai_rewrite_goods(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    AI 润色商品：
    调用通用 AI 模型，对商品标题和正文进行改写。
    """
    try:
        tenant_id = _require_tenant(current_user)
        user_id = _require_billing_user(current_user)
    except ValueError:
        return ResultObject.failed("缺少租户或用户上下文", 400)

    title = _text(body.get("title", ""))
    description = _text(body.get("description", ""))
    price = _text(body.get("price", ""))
    image_url = _text(body.get("imageUrl") or body.get("image_url", ""))
    style = _text(body.get("style", ""))
    custom_prompt = _text(body.get("customPrompt") or body.get("custom_prompt") or "")
    prompt = _text(body.get("prompt", ""))

    if not title and not description:
        return ResultObject.validate_failed("商品标题和描述不能同时为空")

    # 确定最终使用的 Prompt
    final_prompt = custom_prompt or prompt or "请根据商品的标题和正文，生成适合闲鱼平台的商品标题和描述。"

    system_prompt = "你是闲鱼商品文案改写专家。请根据用户要求的风格和提示，改写商品标题和正文。返回严格JSON格式。"
    # 追加润色强限制（来自后台「通用模型配置」的润色关键词/禁止关键词，前台不可见、不可改）
    try:
        _polish_restriction = await get_polish_keywords_restriction()
        if _polish_restriction:
            system_prompt = system_prompt + "\n" + _polish_restriction
    except Exception as exc:
        log_route_failure(logger, exc, operation="load workflow polish restrictions")
    model_name_for_charge = "default"
    provider_name_for_charge = "default"
    style_prompt = ""
    if style == "口语化":
        style_prompt = "使用口语化、亲切的风格改写。"
    elif style == "简洁":
        style_prompt = "使用简洁明了、重点突出的风格改写。"
    elif style == "吸引眼球":
        style_prompt = "使用有吸引力、能打动人的风格改写。"
    elif style:
        style_prompt = f"使用以下风格改写：{style}"

    user_prompt = f"""
原商品标题: {title}
原商品正文: {description}
商品价格: {price}
商品图片: {image_url}

润色要求: {final_prompt}
{style_prompt}

请严格按照 JSON 格式返回结果：
{{"title": "改写后的商品标题(不超过30字)", "description": "改写后的商品正文", "highlights": ["卖点1", "卖点2", "卖点3"]}}
"""

    try:
        billing_request_id = await _precheck_text_billing(
            tenant_id=tenant_id,
            user_id=user_id,
            scene="workflow_rewrite",
            prompt=user_prompt,
        )
    except AiBillingPaymentRequired:
        return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
    except AiBillingError:
        return ResultObject.failed(AiBillingError.user_message, 503)
    except Exception as exc:
        return safe_route_failure(
            logger,
            exc,
            operation="precheck workflow AI rewrite",
            user_message="AI 计费服务暂不可用，请稍后重试",
            code=503,
        )

    ai_result = await generate_text(
        "workflow_rewrite",
        system_prompt,
        user_prompt,
        0.7,
        request_id=billing_request_id,
    )

    if not ai_result.get("ok"):
        return ResultObject.failed("AI 改写服务暂不可用，请稍后重试", 503)

    content = _text(ai_result.get("content", ""))
    try:
        json_start = content.find("{")
        json_end = content.rfind("}")
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end + 1]
            result_data = json.loads(json_str)
        else:
            result_data = {}
    except Exception:
        result_data = {}

    rewritten_title = _text(result_data.get("title", title))[:30]
    rewritten_desc = _text(result_data.get("description", description))
    highlights = result_data.get("highlights", [])

    if rewritten_title.strip() == title.strip() and rewritten_desc.strip() == description.strip():
        rewritten_title = (f"{style or '已优化'}·" + " ".join(title.split()).strip())[:30]
        rewritten_desc = " ".join(description.split()).strip()
        rewritten_desc = rewritten_desc.replace("标价就是售价，可以直接拍", "价格清晰，拍下即可发货")
        rewritten_desc = rewritten_desc.replace("下单界面", "下单后")
        rewritten_desc = rewritten_desc[:220].strip()
        if rewritten_desc == description.strip():
            rewritten_desc = f"{style or '已优化'}：{rewritten_desc}"
        if not isinstance(highlights, list):
            highlights = []
        highlights = (highlights or []) + ["模型原样返回", "已自动本地改写"]

    # ★ 后置硬兜底：对 AI 输出的标题和正文做禁止词校验+硬过滤
    #   即使模型不遵守 prompt 限制，也确保返回前端的内容绝不包含禁止词。
    try:
        rewritten_title, rewritten_desc, _forbidden_hits = await enforce_polish_restriction(rewritten_title, rewritten_desc)
        if _forbidden_hits:
            if not isinstance(highlights, list):
                highlights = []
            highlights = (highlights or []) + [f"已过滤敏感词: {'、'.join(_forbidden_hits)}"]
    except Exception as exc:
        log_route_failure(logger, exc, operation="enforce workflow polish restrictions")

    try:
        await charge_text_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            scene="workflow_rewrite",
            provider_name=_text(ai_result.get("provider", "default")),
            model_name=_text(ai_result.get("model", "default")),
            prompt=user_prompt,
            completion=content,
            request_id=billing_request_id,
            raw_usage=ai_result.get("usage"),
        )
    except AiBillingPaymentRequired:
        return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
    except AiBillingError:
        return ResultObject.failed(AiBillingError.user_message, 503)
    except Exception as exc:
        return safe_route_failure(
            logger,
            exc,
            operation="charge workflow AI rewrite",
            user_message="AI 计费服务暂不可用，本次结果未返回，请稍后重试",
            code=503,
        )

    return ResultObject.success(AiRewriteResultDTO(
        title=rewritten_title,
        description=rewritten_desc,
        highlights=highlights if isinstance(highlights, list) else [],
    ).model_dump())


@router.post("/ai/generate-images", response_model=ResultObject)
async def ai_generate_images(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    AI 生图：
    调用后台配置的生图模型，生成商品图片。
    """
    try:
        tenant_id = _require_tenant(current_user)
        user_id = current_user.get("user_id", 0)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    # The current provider abstraction only generates text. Returning placeholder
    # URLs here made the UI report paid, generated images that did not exist.
    return ResultObject.failed(
        "AI 生图服务尚未接入真实图片生成提供方，图片未生成且不会扣费",
        503,
    )


@router.post("/ai/extract-keywords", response_model=ResultObject)
async def ai_extract_keywords(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    AI 关键词提取：
    从用户输入的大段文本中，提取适合闲鱼商品搜索的关键词列表。
    """
    try:
        tenant_id = _require_tenant(current_user)
        user_id = _require_billing_user(current_user)
    except ValueError:
        return ResultObject.failed("缺少租户或用户上下文", 400)

    text = _text(body.get("text") or body.get("content") or "")
    if not text or len(text.strip()) < 3:
        return ResultObject.validate_failed("待提取文本不能为空，至少3个字符")

    system_prompt = (
        "你是闲鱼商品搜索关键词提取助手。用户会给你一段包含商品品类、方向、参考信息的文本（可能是表格、列表、段落等任意格式），"
        "请从中提取出所有适合直接用于闲鱼商品搜索的关键词短语。\n\n"
        "提取规则：\n"
        "1. 每个关键词应该是一个完整、独立、可直接搜索的商品/品类短语（如\"PSD源文件\"\"绿色免安装版\"\"无版权音效\"），不要返回单个字或过于宽泛的词。\n"
        "2. 去掉表头、分类名、说明性文字、修饰性连接词（如\"核心大类\"\"细分品类\"\"可直接复制使用\"等），只保留真正的商品关键词。\n"
        "3. 同类合并：例如\"Word/Excel/PPT\"拆分为独立关键词或保持为一个短语均可，但不要重复。\n"
        "4. 关键词数量控制在5-50个之间，按从通用到具体的顺序排列。\n"
        "5. 严格以JSON数组格式返回，不要包含任何解释、markdown标记或其他文字。示例：[\"软件安装包\",\"永久激活码\",\"PSD源文件\"]"
    )

    user_prompt = f"请从以下文本中提取闲鱼商品搜索关键词：\n\n{text}"

    try:
        billing_request_id = await _precheck_text_billing(
            tenant_id=tenant_id,
            user_id=user_id,
            scene="workflow_extract_keywords",
            prompt=user_prompt,
        )
    except AiBillingPaymentRequired:
        return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
    except AiBillingError:
        return ResultObject.failed(AiBillingError.user_message, 503)
    except Exception as exc:
        return safe_route_failure(
            logger,
            exc,
            operation="precheck workflow keyword extraction",
            user_message="AI 计费服务暂不可用，请稍后重试",
            code=503,
        )

    ai_result = await generate_text(
        "workflow_extract_keywords",
        system_prompt,
        user_prompt,
        0.3,
        request_id=billing_request_id,
    )

    if not ai_result.get("ok"):
        logger.warning("AI关键词提取失败: error=%s configured=%s", ai_result.get("error"), ai_result.get("configured"))
        return ResultObject.failed("AI 关键词提取服务暂不可用，请稍后重试")

    content = _text(ai_result.get("content", ""))

    keywords = []
    try:
        json_start = content.find("[")
        json_end = content.rfind("]")
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end + 1]
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                for item in parsed:
                    kw = _text(item).strip()
                    if kw and 2 <= len(kw) <= 30 and kw not in keywords:
                        keywords.append(kw)
    except Exception:
        pass

    if not keywords:
        import re as _re
        for line in content.split("\n"):
            line = line.strip().lstrip("-•·0123456789.)、，,\"'")
            line = line.rstrip(".,，。\"'")
            if 2 <= len(line) <= 30 and not _re.match(r"^(请|注意|返回|结果|关键|提取|以下|说明)", line):
                if line not in keywords:
                    keywords.append(line)
            if len(keywords) >= 50:
                break

    try:
        await charge_text_usage(
            tenant_id=tenant_id,
            user_id=user_id,
            scene="workflow_extract_keywords",
            provider_name=_text(ai_result.get("provider", "default")),
            model_name=_text(ai_result.get("model", "default")),
            prompt=user_prompt,
            completion=content,
            request_id=billing_request_id,
            raw_usage=ai_result.get("usage"),
        )
    except AiBillingPaymentRequired:
        return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
    except AiBillingError:
        return ResultObject.failed(AiBillingError.user_message, 503)
    except Exception as exc:
        return safe_route_failure(
            logger,
            exc,
            operation="charge workflow keyword extraction",
            user_message="AI 计费服务暂不可用，本次结果未返回，请稍后重试",
            code=503,
        )

    if not keywords:
        return ResultObject.failed("AI 未能提取有效关键词，请调整文本后重试", 502)

    return ResultObject.success({"keywords": keywords})


@router.post("/publish", response_model=ResultObject)
async def workflow_publish(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    工作流发布商品：
    复用商机发掘的发布能力，固定库存 999，保持原价。
    """
    try:
        tenant_id = _require_tenant(current_user)
        user_id = current_user.get("user_id", 0)
    except ValueError:
        return ResultObject.failed(TENANT_CONTEXT_REQUIRED_MESSAGE, 400)

    title = _text(body.get("title", ""))
    description = _text(body.get("description", ""))
    price = _text(body.get("price", ""))
    stock = _safe_int(body.get("stock"), 999)
    image_urls = body.get("imageUrls") or body.get("image_urls") or []
    category = _text(body.get("category", ""))
    address = body.get("address") or body.get("location") or {}
    account_id = _safe_int(body.get("accountId") or body.get("account_id"))
    execution_id = _safe_int(body.get("executionId") or body.get("execution_id"))
    is_test = bool(body.get("isTest") or body.get("is_test") or False)

    if not title:
        return ResultObject.validate_failed("商品标题不能为空")
    if not description:
        return ResultObject.validate_failed("商品描述不能为空")
    if not price:
        return ResultObject.validate_failed("商品价格不能为空")
    if not image_urls:
        return ResultObject.validate_failed("至少需要一张图片")
    if not account_id:
        return ResultObject.validate_failed("请选择发布账号")

    if is_test:
        # 测试模式：只校验参数，不真实发布
        publish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = WorkflowPublishRecord(
            tenant_id=tenant_id,
            execution_id=execution_id or 0,
            account_id=account_id,
            title=title,
            description=description,
            price=price,
            stock=stock,
            image_urls=image_urls,
            address_info=address if isinstance(address, dict) else {},
            publish_time=datetime.now(),
            status="dry_run",
        )
        db.add(record)
        await db.commit()

        return ResultObject.success(WorkflowPublishResultDTO(
            success=True,
            goods_id=f"test_{uuid.uuid4().hex[:8]}",
            xianyu_goods_id=f"test_{uuid.uuid4().hex[:8]}",
            publish_time=publish_time,
            account_id=account_id,
            title=title,
            description=description,
            image_urls=image_urls if isinstance(image_urls, list) else [],
            address=address if isinstance(address, dict) else {},
            error_message="",
        ).model_dump())

    # 正式发布：复用 items.py 的发布逻辑
    from ....services.xianyu_goods_sync import XianyuItemPublisher, extract_token_from_cookie
    from ....core.cookie_crypto import decrypt_cookie_if_needed
    from ....models.entities import XianyuAccountAuth

    auth_result = await db.execute(
        select(XianyuAccountAuth).where(
            XianyuAccountAuth.account_id == account_id,
            XianyuAccountAuth.tenant_id == tenant_id,
        )
    )
    auth = auth_result.scalar_one_or_none()
    if not auth or not auth.encrypted_cookie:
        return ResultObject.failed("账号未登录或 Cookie 已失效，请重新登录")

    cookie_str = decrypt_cookie_if_needed(auth.encrypted_cookie)
    token = extract_token_from_cookie(cookie_str)
    if not token:
        return ResultObject.failed("Cookie 中缺少 _m_h5_tk，请重新登录")

    item_data = {
        "title": title,
        "desc": description,
        "imageUrls": image_urls if isinstance(image_urls, list) else [],
        "price": price,
        "quantity": stock,
    }
    if category:
        item_data["category"] = {"catName": category}
    if isinstance(address, dict) and address.get("poiName"):
        item_data["location"] = address

    try:
        publisher = XianyuItemPublisher(cookie_str, tenant_id)
        result = publisher.publish(item_data)
    except Exception as e:
        failure = safe_route_failure(logger, e, operation="publish workflow goods", user_message="发布失败，请稍后重试")
        record = WorkflowPublishRecord(
            tenant_id=tenant_id,
            execution_id=execution_id or 0,
            account_id=account_id,
            title=title,
            description=description,
            price=price,
            stock=stock,
            image_urls=image_urls if isinstance(image_urls, list) else [],
            address_info=address if isinstance(address, dict) else {},
            status="failed",
            error_message=failure.msg,
        )
        db.add(record)
        await db.commit()
        return failure

    if result.get("success"):
        publish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        goods_id = _text(result.get("itemId", ""))
        record = WorkflowPublishRecord(
            tenant_id=tenant_id,
            execution_id=execution_id or 0,
            account_id=account_id,
            title=title,
            description=description,
            price=price,
            stock=stock,
            image_urls=image_urls if isinstance(image_urls, list) else [],
            address_info=address if isinstance(address, dict) else {},
            goods_id=goods_id,
            xianyu_goods_id=goods_id,
            publish_time=datetime.now(),
            status="success",
        )
        db.add(record)
        await db.commit()

        return ResultObject.success(WorkflowPublishResultDTO(
            success=True,
            goods_id=goods_id,
            xianyu_goods_id=goods_id,
            publish_time=publish_time,
            account_id=account_id,
            title=title,
            description=description,
            image_urls=image_urls if isinstance(image_urls, list) else [],
            address=address if isinstance(address, dict) else {},
            error_message="",
        ).model_dump())
    else:
        error_msg = _text(result.get("message", "发布失败"))
        record = WorkflowPublishRecord(
            tenant_id=tenant_id,
            execution_id=execution_id or 0,
            account_id=account_id,
            title=title,
            description=description,
            price=price,
            stock=stock,
            image_urls=image_urls if isinstance(image_urls, list) else [],
            address_info=address if isinstance(address, dict) else {},
            status="failed",
            error_message=error_msg,
        )
        db.add(record)
        await db.commit()
        return ResultObject.failed(f"发布失败: {error_msg}")
