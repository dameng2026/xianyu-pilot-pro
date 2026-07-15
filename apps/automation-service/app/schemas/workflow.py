from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from ..core.camel import CamelModel


# ==================== 工作流定义 ====================

class WorkflowNodeDTO(CamelModel):
    id: str = ""
    node_key: str = ""
    name: str = ""
    node_name: str = ""
    type: str = ""
    node_type: str = ""
    x: int = 80
    y: int = 80
    position_x: int = 80
    position_y: int = 80
    config: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)
    retry: bool = False
    retry_enabled: bool = False
    retry_count: int = 0
    retry_interval_seconds: int = 30
    desc: str = ""


class WorkflowEdgeDTO(CamelModel):
    source: str = ""
    target: str = ""
    source_node_key: str = ""
    target_node_key: str = ""
    condition: str = ""
    condition_expr: str = ""


class WorkflowCanvasDTO(CamelModel):
    zoom: int = 100


class WorkflowDefinitionDTO(CamelModel):
    id: Optional[int] = None
    name: str = "未命名工作流"
    description: str = ""
    trigger_type: str = "manual"
    config: Dict[str, Any] = Field(default_factory=dict)
    canvas: Optional[WorkflowCanvasDTO] = None
    status: str = "draft"
    version: int = 1
    execution_count: int = 0
    nodes: List[WorkflowNodeDTO] = Field(default_factory=list)
    edges: List[WorkflowEdgeDTO] = Field(default_factory=list)
    created_time: Optional[str] = None
    updated_time: Optional[str] = None


class WorkflowDefinitionListDTO(CamelModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)
    current: int = 1
    size: int = 20
    total: int = 0


class WorkflowOverviewDTO(CamelModel):
    workflow_count: int = 0
    enabled_count: int = 0
    today_execution_count: int = 0
    success_rate: float = 0.0


# ==================== 工作流执行 ====================

class WorkflowExecuteReqDTO(CamelModel):
    trigger_mode: str = "manual"
    is_test: bool = False
    keywords: List[str] = Field(default_factory=list)
    input: Dict[str, Any] = Field(default_factory=dict)


class WorkflowNodeResultDTO(CamelModel):
    node_key: str = ""
    node_name: str = ""
    node_type: str = ""
    status: str = "pending"
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    duration_ms: int = 0
    retry_count: int = 0
    is_skipped: bool = False
    ai_request_summary: str = ""
    ai_response_summary: str = ""
    publish_params_summary: str = ""


class WorkflowExecutionDTO(CamelModel):
    id: Optional[int] = None
    workflow_id: Optional[int] = None
    workflow_name: str = ""
    execution_no: str = ""
    trigger_mode: str = "manual"
    status: str = "queued"
    current_node_key: str = ""
    current_node: str = ""
    progress: int = 0
    node_total: int = 0
    node_success: int = 0
    node_failed: int = 0
    is_test: bool = False
    started_time: Optional[str] = None
    finished_time: Optional[str] = None
    created_time: Optional[str] = None
    duration_ms: int = 0
    total_duration: int = 0
    error_message: str = ""
    output: Dict[str, Any] = Field(default_factory=dict)
    steps: List[WorkflowNodeResultDTO] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    state_variables: List[Dict[str, Any]] = Field(default_factory=list)
    log_entries: List[Dict[str, Any]] = Field(default_factory=list)


class WorkflowExecutionListDTO(CamelModel):
    records: List[Dict[str, Any]] = Field(default_factory=list)
    current: int = 1
    size: int = 20
    total: int = 0


# ==================== AI 服务 ====================

class AiScreenReqDTO(CamelModel):
    title: str = ""
    description: str = ""
    price: str = ""
    image_url: str = ""
    area: str = ""
    seller_info: str = ""
    screen_prompt: str = ""


class AiScreenResultDTO(CamelModel):
    passed: bool = False
    reason: str = ""
    score: int = 0


class AiRewriteReqDTO(CamelModel):
    title: str = ""
    description: str = ""
    price: str = ""
    image_url: str = ""
    style: str = ""
    prompt: str = ""
    custom_prompt: str = ""


class AiRewriteResultDTO(CamelModel):
    title: str = ""
    description: str = ""
    highlights: List[str] = Field(default_factory=list)


class AiGenerateImageReqDTO(CamelModel):
    title: str = ""
    description: str = ""
    prompt: str = ""
    image_count: int = 1
    model_key: str = ""


class AiGenerateImageResultDTO(CamelModel):
    images: List[str] = Field(default_factory=list)
    token_cost: int = 0
    model_key: str = ""


# ==================== 发布 ====================

class WorkflowPublishReqDTO(CamelModel):
    execution_id: Optional[int] = None
    account_id: Optional[int] = None
    title: str = ""
    description: str = ""
    price: str = ""
    stock: int = 999
    image_urls: List[str] = Field(default_factory=list)
    category: str = ""
    address: Dict[str, Any] = Field(default_factory=dict)
    is_test: bool = False


class WorkflowPublishResultDTO(CamelModel):
    success: bool = False
    goods_id: str = ""
    xianyu_goods_id: str = ""
    publish_time: str = ""
    account_id: Optional[int] = None
    title: str = ""
    description: str = ""
    image_urls: List[str] = Field(default_factory=list)
    address: Dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""


# ==================== 最近执行 ====================

class RecentRunDTO(CamelModel):
    execution_no: str = ""
    execution_id: Optional[int] = None
    workflow_name: str = ""
    status: str = ""
    goods_title: str = ""
    account_name: str = ""
    duration_ms: int = 0
    failed_node: str = ""
    error_message: str = ""
    created_time: Optional[str] = None


# ==================== 环节日志 ====================

class NodeLogDTO(CamelModel):
    node_key: str = ""
    node_name: str = ""
    node_type: str = ""
    status: str = ""
    started_time: Optional[str] = None
    finished_time: Optional[str] = None
    duration_ms: int = 0
    input_params: Dict[str, Any] = Field(default_factory=dict)
    output_result: Dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    retry_count: int = 0
    next_node: str = ""
    is_skipped: bool = False
    ai_request_summary: str = ""
    ai_response_summary: str = ""
    publish_params_summary: str = ""