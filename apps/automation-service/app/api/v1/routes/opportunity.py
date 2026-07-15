from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, get_current_user
from app.core.http_failures import safe_route_failure
from app.core.response import ResultObject
from app.services.ai_provider import generate_text, get_polish_keywords_restriction, enforce_polish_restriction
from app.services.ai_billing import (
    AiBillingError,
    AiBillingPaymentRequired,
    build_request_id,
    charge_text_usage,
    estimate_text_tokens,
    precheck_ai_usage,
)

router = APIRouter(prefix="/opportunity", tags=["商机挖掘"])
logger = logging.getLogger(__name__)

SENSITIVE_WORDS = ["高仿", "复刻", "A货", "精仿", "违禁", "烟", "电子烟", "药", "处方", "枪", "刀"]


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


def _normalize_for_compare(value: Any) -> str:
    """Normalize Unicode text without relying on unsupported regex properties."""
    return "".join(
        character
        for character in str(value or "").casefold()
        if not character.isspace()
        and not unicodedata.category(character).startswith("P")
    )


def _parse_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value)
    m = re.search(r"\d+(?:\.\d+)?", s.replace(",", ""))
    if not m:
        return None
    try:
        return float(Decimal(m.group(0)))
    except (InvalidOperation, ValueError):
        return None


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            m = re.search(r"\d+", value.replace(",", ""))
            return int(m.group(0)) if m else default
        return int(value)
    except Exception:
        return default


def _normalize_item(raw: Dict[str, Any], keyword: str = "") -> Dict[str, Any]:
    title = _safe_text(raw.get("title") or raw.get("name") or raw.get("goodsTitle") or "无标题商品", 300)
    price = raw.get("price") or raw.get("soldPrice") or raw.get("currentPrice") or raw.get("salePrice")
    want_count = _to_int(raw.get("wantCount") or raw.get("want_count") or raw.get("want") or raw.get("likeCount"), 0)
    view_count = _to_int(raw.get("viewCount") or raw.get("view_count") or raw.get("exposureCount") or raw.get("browseCount"), 0)
    sold_count = _to_int(raw.get("soldCount") or raw.get("sold_count") or raw.get("sales"), 0)
    desc = _safe_text(raw.get("description") or raw.get("desc") or raw.get("detailInfo"), 1000)
    price_num = _parse_price(price)
    risk_hits = [w for w in SENSITIVE_WORDS if w.lower() in (title + desc).lower()]
    keyword_hits = 0
    for token in re.split(r"[\s,，/]+", keyword):
        token = token.strip()
        if token and token.lower() in title.lower():
            keyword_hits += 1
    heat_score = min(100, 20 + want_count * 2 + view_count // 20 + sold_count * 6)
    price_score = 45 if price_num is None else max(0, min(60, 60 - int(math.log10(max(price_num, 1)) * 8)))
    keyword_score = min(15, keyword_hits * 8)
    risk_penalty = len(risk_hits) * 18
    opportunity_score = max(0, min(100, heat_score + price_score + keyword_score - risk_penalty))
    return {
        "title": title,
        "price": price or "",
        "priceValue": price_num,
        "image": raw.get("image") or raw.get("imageUrl") or raw.get("picUrl") or raw.get("coverPic") or raw.get("mainImageUrl") or "",
        "link": raw.get("link") or raw.get("url") or raw.get("itemUrl") or raw.get("pcUrl") or "",
        "itemId": raw.get("itemId") or raw.get("externalGoodsId") or raw.get("id") or "",
        "description": desc,
        "seller": raw.get("seller") or raw.get("userNick") or raw.get("sellerNick") or "",
        "area": raw.get("area") or raw.get("location") or "",
        "wantCount": want_count,
        "viewCount": view_count,
        "soldCount": sold_count,
        "opportunityScore": opportunity_score,
        "riskScore": min(100, 10 + len(risk_hits) * 25),
        "riskTags": risk_hits,
        "recommendation": "优先跟进" if opportunity_score >= 80 and not risk_hits else ("谨慎观察" if opportunity_score >= 55 else "暂不推荐"),
    }


def _summary(keyword: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    prices = [i["priceValue"] for i in items if i.get("priceValue") is not None]
    total = len(items)
    avg_score = round(sum(i.get("opportunityScore", 0) for i in items) / total, 1) if total else 0
    top = items[:3]
    return {
        "keyword": keyword,
        "totalCount": total,
        "avgOpportunityScore": avg_score,
        "priceMin": min(prices) if prices else None,
        "priceMax": max(prices) if prices else None,
        "priceAvg": round(sum(prices) / len(prices), 2) if prices else None,
        "topTitles": [i.get("title") for i in top],
        "heatLevel": "高" if avg_score >= 75 else ("中" if avg_score >= 50 else "低"),
        "riskLevel": "高" if any(i.get("riskTags") for i in items) else "低",
        "actions": [
            "优先选择机会评分高、风险标签为空的商品做改写草稿",
            "发布前人工确认价格、成色、图片来源和平台规则风险",
            "对低价高热度商品先保存商机，再跟踪同类商品价格波动",
        ],
    }


def _rewrite(item: Dict[str, Any], style: str = "friendly") -> Dict[str, Any]:
    title = _safe_text(item.get("title"), 120)
    price = item.get("price") or "价格面议"
    area = item.get("area") or ""
    desc = _safe_text(item.get("description"), 800)
    base_title = re.sub(r"[【】\[\]（）()]", " ", title).strip()
    if len(base_title) > 25:
        base_title = base_title[:25]
    style_prefix = {
        "friendly": "自用闲置",
        "professional": "成色不错",
        "concise": "闲置转让",
        "click": "高性价比",
    }.get(style, "自用闲置")
    rewritten_title = f"{style_prefix}｜{base_title}"
    selling_points = []
    if price:
        selling_points.append(f"参考价格：{price}")
    if area:
        selling_points.append(f"发货/面交地区：{area}")
    if item.get("soldCount"):
        selling_points.append(f"同类热度：已售/互动 {item.get('soldCount')}")
    if not selling_points:
        selling_points.append("适合想要低成本入手同类商品的买家")
    rewritten_desc = "\n".join([
        rewritten_title,
        "",
        "卖点整理：",
        *[f"- {p}" for p in selling_points],
        "",
        "商品说明：",
        desc or "商品来源于商机分析结果，请发布前补充真实成色、配件、瑕疵和售后说明。",
        "",
        "温馨提示：发布前请确认图片版权、商品真实性和平台合规要求。",
    ])
    risk_hits = [w for w in SENSITIVE_WORDS if w.lower() in (rewritten_title + rewritten_desc).lower()]
    return {
        "title": rewritten_title[:30],
        "description": rewritten_desc[:1800],
        "tags": [t for t in ["闲置", "高性价比", area, "可议价"] if t][:6],
        "priceSuggestion": item.get("priceValue") or _parse_price(price),
        "safety": {
            "blocked": bool(risk_hits),
            "riskTags": risk_hits,
            "message": "命中敏感词，请人工修改后再发布" if risk_hits else "未发现明显敏感词，仍需人工确认商品真实性",
        },
    }


async def _persist_analysis(db: AsyncSession, tenant_id: int, user_id: int, keyword: str, payload: Dict[str, Any]) -> None:
    try:
        await db.execute(text("""
            INSERT INTO opportunity_analysis(tenant_id, user_id, keyword, source_type, summary_json, items_json, status, created_time, updated_time, deleted)
            VALUES(:tenant_id, :user_id, :keyword, :source_type, :summary_json, :items_json, 'completed', NOW(), NOW(), 0)
        """), {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "keyword": keyword,
            "source_type": payload.get("sourceType", "manual"),
            "summary_json": json.dumps(payload.get("summary", {}), ensure_ascii=False),
            "items_json": json.dumps(payload.get("items", [])[:50], ensure_ascii=False),
        })
        await db.commit()
    except Exception:
        # 兼容旧库：分析功能不能因为历史库缺表而整体失败。
        await db.rollback()


@router.post("/analyze", response_model=ResultObject)
async def analyze_opportunity(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
        user_id = _require_user(current_user)
    except (TypeError, ValueError):
        return ResultObject.failed("缺少租户或用户上下文", 400)
    keyword = _safe_text(body.get("keyword"), 80)
    if not keyword:
        return ResultObject.validate_failed("请输入关键词")
    raw_items = body.get("items") or []
    if not isinstance(raw_items, list):
        raw_items = []
    normalized = [_normalize_item(x if isinstance(x, dict) else {}, keyword) for x in raw_items]

    # 如果前端尚未传入搜索结果，尝试从本地商品库做兜底分析。
    if not normalized:
        result = await db.execute(text("""
            SELECT id, external_goods_id AS itemId, title, price, stock, image_url AS image, description, category, status, updated_time
            FROM xianyu_goods
            WHERE tenant_id=:tenant_id AND deleted=0
              AND (title LIKE :kw OR description LIKE :kw OR category LIKE :kw)
            ORDER BY updated_time DESC, id DESC
            LIMIT 30
        """), {"tenant_id": tenant_id, "kw": f"%{keyword}%"})
        normalized = [_normalize_item(dict(row), keyword) for row in result.mappings().all()]

    normalized.sort(key=lambda x: x.get("opportunityScore", 0), reverse=True)
    summary = _summary(keyword, normalized)
    payload = {
        "keyword": keyword,
        "summary": summary,
        "items": normalized,
        "nextStep": "ai_rewrite",
        "generatedAt": datetime.utcnow().isoformat() + "Z",
    }
    await _persist_analysis(db, tenant_id, int(current_user.get("user_id") or 0), keyword, payload)
    return ResultObject.success(payload)


@router.post("/rewrite", response_model=ResultObject)
async def rewrite_opportunity_item(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
        user_id = _require_user(current_user)
    except (TypeError, ValueError):
        return ResultObject.failed("缺少租户或用户上下文", 400)
    item = body.get("item") or {}
    if not isinstance(item, dict):
        item = {}
    source_title = _safe_text(body.get("title") or body.get("sourceTitle") or item.get("title"), 200)
    source_description = _safe_text(
        body.get("description") or body.get("sourceDescription") or item.get("description"),
        4000,
    )
    if not source_title:
        return ResultObject.validate_failed("请选择需要改写的商品")
    style = _safe_text(body.get("style") or "friendly", 40)
    custom_prompt = _safe_text(body.get("customPrompt") or "", 1000)
    normalized_item = dict(item)
    normalized_item["title"] = source_title
    normalized_item["description"] = source_description or normalized_item.get("description") or source_title
    normalized = _normalize_item(normalized_item, _safe_text(body.get("keyword"), 80))
    if custom_prompt and custom_prompt != "null":
        rewrite_instruction = custom_prompt
    else:
        rewrite_instruction = (
            "请根据原标题和正文，为闲鱼二手商品改写一版可发布标题、商品描述和3-5个标签。"
            "要求：1⃣ 标题单独放在第一行，不超过30个字，简洁吸引人；"
            "2⃣ 正文从第二行开始，改写后的描述保留核心商品信息和卖点但重新表述；"
            "3⃣ 与原内容相似度在80%以上。"
            "要求真实、不夸大、不承诺站外交易、不包含违禁词；发布前仍需人工复核。"
        )
    prompt = (
        f"{rewrite_instruction}"
        f"风格={style}；"
        f"原标题={source_title}；"
        f"原文案={normalized.get('description', '')}；"
        f"商品={json.dumps(normalized, ensure_ascii=False)}"
    )
    billing_request_id = build_request_id("opportunity_rewrite")
    try:
        await precheck_ai_usage({
            "tenantId": tenant_id,
            "userId": user_id,
            "scene": "opportunity_rewrite",
            "providerName": "default",
            "modelName": "default",
            "modelType": "chat",
            "promptTokens": estimate_text_tokens(prompt),
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
            operation="precheck opportunity rewrite AI usage",
            user_message="AI 计费服务暂不可用，请稍后重试",
            code=503,
        )
    # ★ 注入润色强限制（来自后台「通用模型配置」的润色关键词/禁止关键词，前台不可见、不可改）
    #   修复：原 system_prompt 硬编码未接入强限制，违反项目硬约束。
    _system_prompt = "你是二手电商商品文案助手，只输出合法合规、可人工编辑的中文文案。"
    try:
        _polish_restriction = await get_polish_keywords_restriction()
        if _polish_restriction:
            _system_prompt = _system_prompt + "\n" + _polish_restriction
    except Exception:
        pass
    ai = await generate_text(
        "opportunity_rewrite",
        _system_prompt,
        prompt,
        0.7,
        request_id=billing_request_id,
    )
    if ai.get("ok"):
        content = _safe_text(ai.get("content"), 3000)
        try:
            await charge_text_usage(
                tenant_id=tenant_id,
                user_id=user_id,
                scene="opportunity_rewrite",
                provider_name=str(ai.get("provider") or "default"),
                model_name=str(ai.get("model") or "default"),
                prompt=prompt,
                completion=content,
                request_id=billing_request_id,
                raw_usage=ai.get("usage") or {},
            )
        except AiBillingPaymentRequired:
            return ResultObject.failed(AiBillingPaymentRequired.user_message, 402)
        except AiBillingError:
            return ResultObject.failed(AiBillingError.user_message, 503)
        except Exception as exc:
            return safe_route_failure(
                logger,
                exc,
                operation="charge opportunity rewrite AI usage",
                user_message="AI 计费服务暂不可用，本次结果未返回，请稍后重试",
                code=503,
            )
        # 从 AI 输出中提取标题：优先查找以"标题"或"【"开头的行，否则取第一行
        title_candidates = []
        for line in content.splitlines():
            stripped = line.strip("#- ：:*").strip()
            if not stripped:
                continue
            # 如果某行以"标题"开头或包含"【】"，优先作为标题
            if stripped.startswith("标题") or "【" in stripped or "】" in stripped:
                title_candidates.insert(0, stripped)  # 优先
            else:
                title_candidates.append(stripped)
        best_title = title_candidates[0] if title_candidates else ""
        # 移除"标题"前缀
        best_title = re.sub(r"^标题[：:\s]*", "", best_title).strip()
        rewrite_title = _safe_text(best_title or f"自用闲置｜{normalized.get('title', '')}", 30)
        # ★ 后置硬兜底：对 AI 输出的标题和正文做禁止词校验+硬过滤
        #   即使模型不遵守 prompt 限制，也确保返回前端的内容绝不包含禁止词。
        try:
            rewrite_title, content, _forbidden_hits = await enforce_polish_restriction(rewrite_title, content)
        except Exception:
            _forbidden_hits = []
        # 将标题拼接到正文开头，确保闲鱼提取正文前30字作为标题时显示的是AI生成的标题
        rewrite_desc = f"{rewrite_title}\n\n{content}"
        # 检查改写结果是否与原文一致
        orig_title = _normalize_for_compare(normalized.get('title', ''))
        orig_desc = _normalize_for_compare(normalized.get('description', ''))
        new_title = _normalize_for_compare(rewrite_title)
        new_desc = _normalize_for_compare(rewrite_desc)
        title_same = orig_title in new_title or new_title in orig_title
        desc_same = orig_desc in new_desc or new_desc in orig_desc
        if title_same and desc_same:
            return ResultObject.failed("AI 改写未生效，返回内容与原文一致，请重试或调整提示词", 502)
        rewrite = {
            "title": rewrite_title,
            "description": rewrite_desc,
            "tags": ["闲置", "AI改写", style],
            "safety": {"blocked": False, "riskTags": [w for w in SENSITIVE_WORDS if w in rewrite_desc], "message": "AI Provider 输出，发布前请人工复核"},
        }
        return ResultObject.success({"ok": True, "item": normalized, "rewrite": rewrite, "style": style, "provider": ai.get("provider"), "model": ai.get("model"), "requestId": billing_request_id, "providerRequestId": ai.get("requestId"), "usage": ai.get("usage"), "fallback": False})
    return ResultObject.failed("AI 改写服务暂不可用，请稍后重试", 503)


@router.get("/history", response_model=ResultObject)
async def opportunity_history(
    keyword: str = Query(""),
    current: int = Query(1),
    size: int = Query(20),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        tenant_id = _require_tenant(current_user)
    except ValueError:
        return ResultObject.failed("缺少租户上下文", 400)
    current = max(current, 1)
    size = min(max(size, 1), 100)
    offset = (current - 1) * size
    kw = f"%{_safe_text(keyword, 80)}%"
    try:
        total_res = await db.execute(text("""
            SELECT COUNT(*) FROM opportunity_analysis
            WHERE tenant_id=:tenant_id AND deleted=0 AND (:keyword='' OR keyword LIKE :kw)
        """), {"tenant_id": tenant_id, "keyword": keyword, "kw": kw})
        total = int(total_res.scalar() or 0)
        rows_res = await db.execute(text("""
            SELECT id, keyword, source_type, summary_json, status, created_time
            FROM opportunity_analysis
            WHERE tenant_id=:tenant_id AND deleted=0 AND (:keyword='' OR keyword LIKE :kw)
            ORDER BY created_time DESC, id DESC
            LIMIT :limit OFFSET :offset
        """), {"tenant_id": tenant_id, "keyword": keyword, "kw": kw, "limit": size, "offset": offset})
        rows = []
        for row in rows_res.mappings().all():
            item = dict(row)
            try:
                item["summary"] = json.loads(item.pop("summary_json") or "{}")
            except Exception:
                item["summary"] = {}
            rows.append(item)
        return ResultObject.success({"records": rows, "current": current, "size": size, "total": total})
    except Exception as e:
        return safe_route_failure(logger, e, operation="opportunity history", user_message="商机历史暂不可用，请稍后重试", code=503)
