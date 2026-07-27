"""AI 客服 KB 学习作业路由。

由 Java core-api 调度调用，触发一次自主学习作业：
- 扫描近 N 小时内的 AI 客服会话
- 调用通用模型抽取候选知识点
- 去重、合并、回写知识库

鉴权：本路由由 Java core-api 内部调用，依赖 `get_current_user`
该依赖同时支持 JWT 与 X-Internal-Token，Java 调度时会带上服务 token。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....core.response import ResultObject
from ....services.kb_learning_service import run_learning_job
from ..deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kb-learning", tags=["kbLearning"])


# 默认配置（与 application.yml 对齐）
_DEFAULT_CONFIG: dict[str, Any] = {
    "lookback_hours": 24,
    "ai_ratio_threshold": 0.6,
    "min_conversation_messages": 5,
    "max_conversations_per_run": 500,
    "llm_batch_size": 5,
    "llm_concurrency": 3,
    "max_cost_yuan_per_run": 50,
}


@router.post("/run")
async def run_learning(
    config_override: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ResultObject:
    """触发一次学习作业（由 Java core-api 调度调用）。

    Args:
        config_override: 可选，覆盖默认配置的字段子集。

    Returns:
        ResultObject 包裹的学习统计信息。
    """
    config: dict[str, Any] = dict(_DEFAULT_CONFIG)
    if config_override:
        config.update(config_override)

    stats = await run_learning_job(db, config)
    return ResultObject.success(data=stats)
