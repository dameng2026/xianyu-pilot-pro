"""货源商城商品 AI 分类 API 路由。

提供批量商品自动分类接口：调用项目已有的 AI 模型服务对商品标题+正文进行文本分类，
AI 不可用时降级为关键词匹配规则。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends

from app.api.v1.deps import get_current_user
from app.core.http_failures import safe_route_failure
from app.core.response import ResultObject
from app.services.ai_billing import (
    AiBillingError,
    AiBillingPaymentRequired,
    build_request_id,
    charge_text_usage,
    estimate_text_tokens,
    precheck_ai_usage,
)
from app.services.ai_provider import generate_text

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/mall",
    tags=["mallCategory"],
    dependencies=[Depends(get_current_user)],
)

# 预设分类体系（与前台商品分类一致）
MALL_CATEGORIES: List[str] = [
    "软件工具", "教程资料", "运营营销", "设计素材",
    "编程开发", "考试学习", "其他",
]

# 降级关键词映射（AI 调用失败时使用）
KEYWORD_MAP: Dict[str, List[str]] = {
    "软件工具": ["软件", "工具", "破解", "激活", "安装包", "APP"],
    "教程资料": ["教程", "资料", "课程", "学习", "指南", "手册"],
    "运营营销": ["运营", "营销", "推广", "引流", "小红书", "短视频", "电商"],
    "设计素材": ["设计", "素材", "模板", "PSD", "图标", "字体", "UI"],
    "编程开发": ["编程", "代码", "Python", "Java", "开发", "算法", "程序"],
    "考试学习": ["考试", "考研", "四级", "六级", "公务员", "证书", "题库"],
}

# 单次请求最多分类的商品数量，避免 prompt 过大或滥用
_MAX_PRODUCTS_PER_REQUEST = 50
# 单字段截断长度，控制 AI 输入体积
_MAX_TITLE_CHARS = 200
_MAX_CONTENT_CHARS = 2000
# 关键词降级置信度（低于 AI 置信度）
_KEYWORD_CONFIDENCE = 0.6
# AI 分类默认置信度
_AI_CONFIDENCE = 0.95
# 兜底分类
_FALLBACK_CATEGORY = "其他"


def _require_tenant(current_user: dict) -> int:
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise ValueError("缺少租户上下文")
    return int(tenant_id)


def _require_user(current_user: dict) -> int:
    user_id = current_user.get("user_id")
    if not user_id or int(user_id) <= 0:
        raise ValueError("缺少用户上下文")
    return int(user_id)


def _safe_text(value: Any, limit: int = 500) -> str:
    s = str(value or "").strip()
    return s[:limit]


def _keyword_classify(title: str, content: str) -> tuple[str, float]:
    """关键词匹配降级分类：统计各分类命中次数，取最高分。"""
    text = f"{title} {content}".lower()
    if not text.strip():
        return _FALLBACK_CATEGORY, _KEYWORD_CONFIDENCE

    best_category = _FALLBACK_CATEGORY
    best_hits = 0
    for category, keywords in KEYWORD_MAP.items():
        hits = 0
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower and kw_lower in text:
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best_category = category

    # 无任何命中归为「其他」
    if best_hits == 0:
        return _FALLBACK_CATEGORY, _KEYWORD_CONFIDENCE
    # 命中越多置信度越高，上限 0.8
    confidence = min(0.8, _KEYWORD_CONFIDENCE + 0.05 * (best_hits - 1))
    return best_category, round(confidence, 2)


def _build_classify_prompt(products: List[Dict[str, Any]]) -> str:
    """构造 AI 分类 prompt，要求返回 JSON 数组。"""
    items_text = []
    for idx, product in enumerate(products):
        title = _safe_text(product.get("title"), _MAX_TITLE_CHARS)
        content = _safe_text(product.get("content"), _MAX_CONTENT_CHARS)
        items_text.append(
            f"[{idx}] 标题：{title}\n    正文：{content}"
        )

    catalog = "、".join(MALL_CATEGORIES)
    items_block = "\n".join(items_text)
    return (
        f"以下是一批货源商城商品，请为每个商品从预设分类中选择最匹配的一个。\n"
        f"预设分类：{catalog}\n\n"
        f"商品列表：\n{items_block}\n\n"
        f"请严格返回 JSON 数组，不要包含任何额外说明或 markdown 代码块标记。"
        f"数组中每个元素格式为："
        f'{{"index": <商品序号, "category": "<预设分类名>", "confidence": <0-1之间的置信度>}}\n'
        f"category 必须是预设分类中的一个，confidence 反映你对分类结果的把握程度。"
    )


def _parse_ai_classify_response(content: str, product_count: int) -> List[Optional[Dict[str, Any]]]:
    """从 AI 输出中解析分类 JSON 数组。

    返回一个长度等于 product_count 的列表，每个元素为
    {"category": str, "confidence": float}，解析失败的位置返回 None。
    """
    results: List[Optional[Dict[str, Any]]] = [None] * product_count
    if not content:
        return results

    # 尝试从 content 中提取 JSON 数组
    json_str = ""
    start = content.find("[")
    end = content.rfind("]")
    if start >= 0 and end > start:
        json_str = content[start:end + 1]
    else:
        # 退而求其次尝试单个 JSON 对象
        obj_start = content.find("{")
        obj_end = content.rfind("}")
        if obj_start >= 0 and obj_end > obj_start:
            json_str = "[" + content[obj_start:obj_end + 1] + "]"

    if not json_str:
        return results

    try:
        parsed = json.loads(json_str)
    except (ValueError, TypeError):
        return results

    if not isinstance(parsed, list):
        parsed = [parsed]

    for item in parsed:
        if not isinstance(item, dict):
            continue
        raw_index = item.get("index")
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= product_count:
            continue
        category = str(item.get("category") or "").strip()
        if category not in MALL_CATEGORIES:
            continue
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            confidence = _AI_CONFIDENCE
        # 限制置信度范围
        confidence = max(0.0, min(1.0, confidence))
        results[index] = {"category": category, "confidence": round(confidence, 2)}

    return results


@router.post("/categorize", response_model=ResultObject)
async def categorize_products(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """对一批货源商城商品进行 AI 分类。

    请求体:
    {
        "products": [
            {"id": 1, "title": "ChatGPT提示词大全", "content": "..."},
            ...
        ]
    }

    响应:
    {
        "results": [
            {"id": 1, "category": "软件工具", "confidence": 0.95},
            ...
        ]
    }
    """
    try:
        tenant_id = _require_tenant(current_user)
        user_id = _require_user(current_user)
    except (TypeError, ValueError):
        return ResultObject.failed("缺少租户或用户上下文", 400)

    raw_products = body.get("products")
    if not isinstance(raw_products, list) or not raw_products:
        return ResultObject.validate_failed("products 不能为空")
    if len(raw_products) > _MAX_PRODUCTS_PER_REQUEST:
        return ResultObject.validate_failed(
            f"单次最多分类 {_MAX_PRODUCTS_PER_REQUEST} 个商品"
        )

    # 规范化商品输入，保留原始 id 供响应回填
    products: List[Dict[str, Any]] = []
    for raw in raw_products:
        if not isinstance(raw, dict):
            continue
        product_id = raw.get("id")
        title = _safe_text(raw.get("title"), _MAX_TITLE_CHARS)
        content = _safe_text(raw.get("content"), _MAX_CONTENT_CHARS)
        products.append({
            "id": product_id,
            "title": title,
            "content": content,
        })

    if not products:
        return ResultObject.validate_failed("products 不能为空")

    user_prompt = _build_classify_prompt(products)
    billing_request_id = build_request_id("mall_categorize")

    # AI 计费预检
    try:
        await precheck_ai_usage({
            "tenantId": tenant_id,
            "userId": user_id,
            "scene": "mall_categorize",
            "providerName": "default",
            "modelName": "default",
            "modelType": "chat",
            "promptTokens": estimate_text_tokens(user_prompt),
            "completionTokens": 0,
            "requestId": billing_request_id,
        })
    except AiBillingPaymentRequired:
        return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
    except AiBillingError:
        return ResultObject.failed(AiBillingError.user_message, 503)
    except Exception as exc:
        return safe_route_failure(
            logger,
            exc,
            operation="precheck mall categorize AI usage",
            user_message="AI 计费服务暂不可用，请稍后重试",
            code=503,
        )

    # 调用 AI 分类
    system_prompt = (
        "你是货源商城商品分类助手。请根据商品的标题和正文，"
        "从预设分类中选择最匹配的一个，并返回严格的 JSON 数组。"
    )
    ai_result = await generate_text(
        scene="mall_categorize",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.2,
        request_id=billing_request_id,
    )

    ai_ok = bool(ai_result.get("ok"))
    ai_content = str(ai_result.get("content") or "")
    parsed: List[Optional[Dict[str, Any]]] = []
    if ai_ok:
        parsed = _parse_ai_classify_response(ai_content, len(products))

    # 组装结果：AI 成功的位置用 AI 结果，失败的位置降级为关键词匹配
    results: List[Dict[str, Any]] = []
    for idx, product in enumerate(products):
        parsed_item = parsed[idx] if idx < len(parsed) else None
        if parsed_item:
            category = parsed_item["category"]
            confidence = parsed_item["confidence"]
            source = "ai"
        else:
            category, confidence = _keyword_classify(
                product.get("title", ""), product.get("content", "")
            )
            source = "keyword"
        results.append({
            "id": product.get("id"),
            "category": category,
            "confidence": confidence,
            "source": source,
        })

    # AI 调用成功时计费
    if ai_ok:
        try:
            await charge_text_usage(
                tenant_id=tenant_id,
                user_id=user_id,
                scene="mall_categorize",
                provider_name=str(ai_result.get("provider") or "default"),
                model_name=str(ai_result.get("model") or "default"),
                prompt=user_prompt,
                completion=ai_content,
                request_id=billing_request_id,
                raw_usage=ai_result.get("usage") or {},
            )
        except AiBillingPaymentRequired:
            return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
        except AiBillingError:
            return ResultObject.failed(AiBillingError.user_message, 503)
        except Exception as exc:
            return safe_route_failure(
                logger,
                exc,
                operation="charge mall categorize AI usage",
                user_message="AI 计费服务暂不可用，本次结果未返回，请稍后重试",
                code=503,
            )

    return ResultObject.success({
        "results": results,
        "aiAvailable": ai_ok,
    })
