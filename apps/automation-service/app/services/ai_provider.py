from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.outbound_network import public_https_outbound_policy

logger = logging.getLogger(__name__)

# 模型配置缓存（避免每次调用都查库）
_model_config_cache: Dict[str, Any] = {}
_model_config_cache_ts: float = 0
_MODEL_CONFIG_TTL = 60  # 缓存 60 秒
_MAX_MESSAGES = 32
_MAX_MESSAGE_CHARS = 128 * 1024
_MAX_TOTAL_MESSAGE_CHARS = 512 * 1024
_MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024


def _normalize_messages(
    system_prompt: str,
    user_prompt: str,
    messages: list[Dict[str, Any]] | None,
) -> tuple[list[Dict[str, str]] | None, str | None]:
    source: list[Dict[str, Any]]
    if messages is None:
        source = [
            {"role": "system", "content": system_prompt or ""},
            {"role": "user", "content": user_prompt or ""},
        ]
    else:
        source = list(messages)
        if system_prompt:
            source = [{"role": "system", "content": system_prompt}] + source
    if len(source) > _MAX_MESSAGES:
        return None, "AI_INPUT_TOO_LARGE"
    normalized: list[Dict[str, str]] = []
    total_chars = 0
    allowed_roles = {"system", "user", "assistant", "tool"}
    for item in source:
        if not isinstance(item, dict):
            return None, "AI_INPUT_INVALID"
        role = str(item.get("role") or "").strip()
        content = item.get("content")
        if role not in allowed_roles or not isinstance(content, str):
            return None, "AI_INPUT_INVALID"
        if len(content) > _MAX_MESSAGE_CHARS:
            return None, "AI_INPUT_TOO_LARGE"
        total_chars += len(content)
        if total_chars > _MAX_TOTAL_MESSAGE_CHARS:
            return None, "AI_INPUT_TOO_LARGE"
        normalized.append({"role": role, "content": content})
    return normalized, None


async def _load_chat_model_config_from_db() -> Optional[Dict[str, Any]]:
    """从 admin_module_record 表读取对话模型配置。

    合并 model-config-chat（模型名、温度等）和 model-config-general（baseUrl、apiKey 等连接信息）。
    model-config-chat 通常只存模型行为参数，连接信息在 model-config-general 中。
    读不到则返回 None，由调用方 fallback 到环境变量。
    """
    global _model_config_cache, _model_config_cache_ts
    import time as _time
    now = _time.time()
    # 缓存命中
    if _model_config_cache and (now - _model_config_cache_ts) < _MODEL_CONFIG_TTL:
        return _model_config_cache or None

    try:
        from sqlalchemy import text
        from app.core.database import async_session
        async with async_session() as db:
            rows = await db.execute(
                text("""
                    SELECT module_key, json_text FROM admin_module_record
                    WHERE module_key IN ('model-config-chat', 'model-config-general') AND deleted = 0
                    ORDER BY id DESC
                """)
            )
            chat_config: Dict[str, Any] | None = None
            general_config: Dict[str, Any] | None = None
            for row_key, row_text in rows.all():
                config = json.loads(row_text) if isinstance(row_text, str) else row_text
                if not isinstance(config, dict):
                    continue
                if row_key == 'model-config-chat' and chat_config is None:
                    chat_config = config
                elif row_key == 'model-config-general' and general_config is None:
                    general_config = config

            if not chat_config and not general_config:
                _model_config_cache = {}
                _model_config_cache_ts = now
                return None

            # 合并：general 提供连接信息（baseUrl/apiKey/enabled），chat 提供模型行为参数
            merged: Dict[str, Any] = {}
            if general_config:
                merged.update(general_config)
            if chat_config:
                merged.update(chat_config)
                # chat 没有连接信息时，保留 general 的
                if not merged.get("baseUrl") and general_config:
                    merged["baseUrl"] = general_config.get("baseUrl", "")
                if not merged.get("apiKey") and general_config:
                    merged["apiKey"] = general_config.get("apiKey", "")
                # chat 没有 modelName 时，用 general 的 defaultModel
                if not merged.get("modelName") and general_config:
                    merged["modelName"] = general_config.get("defaultModel", "")

            _model_config_cache = merged
            _model_config_cache_ts = now
            logger.info(
                "从 admin_module_record 加载模型配置成功: provider=%s model=%s endpointConfigured=%s",
                merged.get("providerName"),
                merged.get("modelName") or merged.get("defaultModel"),
                bool(merged.get("baseUrl")),
            )
            return merged
    except Exception as e:
        logger.debug("读取 admin_module_record 模型配置失败，将使用环境变量: %s", e)
        _model_config_cache = {}
        _model_config_cache_ts = now
        return None


async def _resolve_ai_config() -> Dict[str, Any]:
    """解析 AI 模型配置：优先 admin_module_record，fallback 环境变量。

    返回统一结构：{base_url, api_key, model, enabled, source}
    source: 'db' | 'env'
    """
    db_config = await _load_chat_model_config_from_db()
    if db_config:
        base_url = str(db_config.get("baseUrl") or db_config.get("base_url") or db_config.get("apiBase") or "").strip()
        api_key = str(db_config.get("apiKey") or db_config.get("api_key") or "").strip()
        model = str(db_config.get("model") or db_config.get("modelName") or db_config.get("defaultModel") or "").strip()
        enabled = bool(db_config.get("enabled", True))
        if base_url and api_key and model and enabled:
            return {
                "base_url": base_url,
                "api_key": api_key,
                "model": model,
                "enabled": True,
                "source": "db",
            }

    # Fallback 到环境变量
    base_url = (settings.ai_provider_base_url or "").strip()
    return {
        "base_url": base_url,
        "api_key": (settings.ai_provider_api_key or "").strip(),
        "model": (settings.ai_provider_model or "").strip(),
        "enabled": bool(settings.ai_provider_enabled and base_url and settings.ai_provider_api_key),
        "source": "env",
    }


# 润色强限制：默认始终禁止出现的关键词（即使后台未配置也生效）
_DEFAULT_POLISH_FORBIDDEN_KEYWORDS: list[str] = ["盗版", "破解版", "毕设"]

# 润色关键词限制缓存（与 _load_chat_model_config_from_db 共享 60s TTL，但单独缓存结果字符串）
_polish_restriction_cache: str = ""
_polish_restriction_cache_ts: float = 0


def _parse_keyword_list(raw: Any) -> list[str]:
    """解析关键词输入，支持逗号、中文逗号、顿号、回车分隔。"""
    if not raw:
        return []
    text = str(raw).strip()
    if not text or text.lower() == "none" or text.lower() == "null":
        return []
    import re as _re
    parts = _re.split(r"[,\n\r，、\s]+", text)
    seen: list[str] = []
    for p in parts:
        k = p.strip()
        if k and k not in seen:
            seen.append(k)
    return seen


async def get_polish_keywords_restriction() -> str:
    """读取通用模型配置中的润色关键词/禁止关键词，构建强限制提示词片段。

    返回一个可直接拼接到 system_prompt 或 user_prompt 的字符串。
    禁止关键词默认包含「盗版、破解版、毕设」，即使后台未配置也始终生效；
    管理员可在「后台 → 模型配置 → 通用模型配置」中追加更多禁止词或必含词。
    """
    global _polish_restriction_cache, _polish_restriction_cache_ts
    import time as _time
    now = _time.time()
    if _polish_restriction_cache and (now - _polish_restriction_cache_ts) < _MODEL_CONFIG_TTL:
        return _polish_restriction_cache

    forbidden: list[str] = list(_DEFAULT_POLISH_FORBIDDEN_KEYWORDS)
    required: list[str] = []

    try:
        cfg = await _load_chat_model_config_from_db()
        if cfg:
            # 管理员在通用模型配置中填写的禁止词，追加到默认禁止词之后
            admin_forbidden = _parse_keyword_list(cfg.get("polishForbiddenKeywords"))
            for kw in admin_forbidden:
                if kw not in forbidden:
                    forbidden.append(kw)
            # 管理员填写的必含词
            required = _parse_keyword_list(cfg.get("polishKeywords"))
    except Exception as e:
        logger.debug("读取润色关键词配置失败，使用默认禁止词: %s", e)

    parts: list[str] = []
    if required:
        parts.append(
            "【必须包含的关键词】润色结果（标题和正文）中必须出现以下关键词：" + "、".join(required)
        )
    if forbidden:
        parts.append(
            "【绝对禁止的关键词】润色结果（标题和正文）中绝对不得出现以下关键词及其变体："
            + "、".join(forbidden) + "。若生成内容包含这些词，必须立即重新生成，确保完全不含。"
        )

    restriction = "\n".join(parts)
    _polish_restriction_cache = restriction
    _polish_restriction_cache_ts = now
    return restriction


# 润色禁止词列表缓存（与 _polish_restriction_cache 同步 60s TTL，但单独缓存列表）
_polish_forbidden_list_cache: list[str] = []
_polish_forbidden_list_ts: float = 0


async def get_polish_forbidden_keywords() -> list[str]:
    """读取通用模型配置中所有生效的润色禁止词列表（默认 + 后台配置）。

    与 get_polish_keywords_restriction() 共享同一份配置源，但返回纯列表，
    供后置硬校验使用。默认禁止「盗版、破解版、毕设」始终生效，即使后台未配置。
    """
    global _polish_forbidden_list_cache, _polish_forbidden_list_ts
    import time as _time
    now = _time.time()
    if _polish_forbidden_list_cache and (now - _polish_forbidden_list_ts) < _MODEL_CONFIG_TTL:
        return list(_polish_forbidden_list_cache)

    forbidden: list[str] = list(_DEFAULT_POLISH_FORBIDDEN_KEYWORDS)
    try:
        cfg = await _load_chat_model_config_from_db()
        if cfg:
            admin_forbidden = _parse_keyword_list(cfg.get("polishForbiddenKeywords"))
            for kw in admin_forbidden:
                if kw and kw not in forbidden:
                    forbidden.append(kw)
    except Exception as e:
        logger.debug("读取润色禁止词列表失败，使用默认禁止词: %s", e)

    _polish_forbidden_list_cache = list(forbidden)
    _polish_forbidden_list_ts = now
    return forbidden


def validate_polish_output(title: str, body: str, forbidden_keywords: list[str]) -> tuple[list[str], list[str]]:
    """校验标题和正文是否包含禁止词（不区分大小写）。

    返回 (title_hits, body_hits)，分别为命中的禁止词列表（去重保序）。
    """
    if not forbidden_keywords:
        return [], []
    title_lower = str(title or "").lower()
    body_lower = str(body or "").lower()

    def _scan(text_lower: str) -> list[str]:
        hits: list[str] = []
        for kw in forbidden_keywords:
            kw_lower = str(kw or "").strip().lower()
            if kw_lower and kw_lower in text_lower and kw_lower not in [h.lower() for h in hits]:
                hits.append(kw)
        return hits

    return _scan(title_lower), _scan(body_lower)


def mask_forbidden_keywords(text: str, forbidden_keywords: list[str]) -> str:
    """将文本中命中的禁止词替换为等长星号（不区分大小写）。

    作为最终硬兜底，确保即使模型不遵守 prompt 限制，输出也绝不包含禁止词。
    """
    if not text or not forbidden_keywords:
        return text
    result = str(text)
    for kw in forbidden_keywords:
        kw_stripped = str(kw or "").strip()
        if not kw_stripped:
            continue
        # 不区分大小写替换为等长星号
        import re as _re
        pattern = _re.compile(_re.escape(kw_stripped), _re.IGNORECASE)
        result = pattern.sub("*" * len(kw_stripped), result)
    return result


async def enforce_polish_restriction(title: str, body: str) -> tuple[str, str, list[str]]:
    """润色输出的最终硬兜底校验+过滤。

    流程：
    1. 读取所有生效的禁止词；
    2. 校验标题/正文是否命中；
    3. 命中则用等长星号替换对应关键词，确保输出绝对不含禁止词；
    4. 返回 (masked_title, masked_body, all_hits)。

    调用方应在 AI 输出解析完成后、入库/返回前端前调用本函数。
    若 all_hits 非空，调用方可记录日志或在响应中标识"已过滤敏感词"。
    """
    forbidden = await get_polish_forbidden_keywords()
    if not forbidden:
        return title or "", body or "", []
    title_hits, body_hits = validate_polish_output(title, body, forbidden)
    all_hits: list[str] = []
    for kw in title_hits + body_hits:
        if kw not in all_hits:
            all_hits.append(kw)
    if not all_hits:
        return title or "", body or "", []
    masked_title = mask_forbidden_keywords(title or "", forbidden)
    masked_body = mask_forbidden_keywords(body or "", forbidden)
    logger.warning("[POLISH_FORBIDDEN] 命中禁止词 hits=%s 已做硬过滤替换", all_hits)
    return masked_title, masked_body, all_hits


async def generate_text(scene: str, system_prompt: str, user_prompt: str, temperature: float = 0.7,
                        messages: list[Dict[str, Any]] | None = None,
                        request_id: str | None = None,
                        timeout: int = 60) -> Dict[str, Any]:
    """OpenAI-compatible chat completion wrapper.

    支持传入 messages（多轮对话上下文），若未传则用 system_prompt+user_prompt 构造单轮。
    返回统一结构；Provider 未配置或调用失败时不抛异常，交由业务层兜底。
    timeout 参数控制 HTTP 请求超时（秒），默认 60 秒。
    """
    request_id = str(request_id or uuid.uuid4())[:128]
    normalized_messages, input_error = _normalize_messages(system_prompt, user_prompt, messages)
    cfg = await _resolve_ai_config()
    base_url = (cfg["base_url"] or "").rstrip("/")
    if base_url and not base_url.endswith("/v1"):
        base_url += "/v1"

    result: Dict[str, Any] = {
        "requestId": request_id,
        "scene": scene,
        "provider": "openai-compatible",
        "model": cfg["model"],
        "configured": bool(cfg["enabled"] and base_url and cfg["api_key"]),
        "configSource": cfg["source"],
    }
    if not result["configured"]:
        result.update({
            "ok": False,
            "errorCode": "AI_PROVIDER_NOT_CONFIGURED",
            "error": "AI 服务暂不可用，请稍后重试",
        })
        return result
    if input_error:
        result.update({
            "ok": False,
            "errorCode": input_error,
            "error": "AI 输入内容过长或格式不正确，请精简后重试",
        })
        return result

    try:
        provider_target = await public_https_outbound_policy.pin_public_https(
            f"{base_url}/chat/completions"
        )
    except ValueError:
        result.update({
            "ok": False,
            "errorCode": "AI_PROVIDER_UNSAFE_ENDPOINT",
            "error": "AI 服务端点未通过安全校验，请联系管理员检查配置",
        })
        return result

    payload = {
        "model": cfg["model"],
        "temperature": temperature,
        "messages": normalized_messages,
    }
    max_attempts = 3
    try:
        async with httpx.AsyncClient(
            timeout=max(timeout, 5),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for attempt in range(max_attempts):
                if attempt > 0:
                    await asyncio.sleep(0.05 * attempt)
                try:
                    async with client.stream(
                        "POST",
                        provider_target.request_url,
                        json=payload,
                        headers={
                            "Authorization": f"Bearer {cfg['api_key']}",
                            "Host": provider_target.host_header,
                        },
                        extensions={"sni_hostname": provider_target.sni_hostname},
                    ) as resp:
                        result["httpStatus"] = resp.status_code
                        if resp.status_code < 200 or resp.status_code >= 300:
                            if resp.status_code == 429 or resp.status_code >= 500:
                                if attempt < max_attempts - 1:
                                    continue
                            result.update({
                                "ok": False,
                                "errorCode": "AI_PROVIDER_HTTP_ERROR",
                                "error": "AI 服务请求失败，请稍后重试",
                            })
                            return result
                        response_bytes = bytearray()
                        response_too_large = False
                        response_chunks = resp.aiter_bytes()
                        async for chunk in response_chunks:
                            if len(response_bytes) + len(chunk) > _MAX_PROVIDER_RESPONSE_BYTES:
                                response_too_large = True
                                await response_chunks.aclose()
                                break
                            response_bytes.extend(chunk)
                    if response_too_large:
                        result.update({
                            "ok": False,
                            "errorCode": "AI_RESPONSE_TOO_LARGE",
                            "error": "AI 返回内容过大，本次结果未采用",
                        })
                        return result
                    try:
                        data = json.loads(bytes(response_bytes))
                    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                        result.update({
                            "ok": False,
                            "errorCode": "AI_PROVIDER_INVALID_RESPONSE",
                            "error": "AI 服务返回了无效结果，请稍后重试",
                        })
                        return result
                    if not isinstance(data, dict):
                        result.update({
                            "ok": False,
                            "errorCode": "AI_PROVIDER_INVALID_RESPONSE",
                            "error": "AI 服务返回了无效结果，请稍后重试",
                        })
                        return result
                    choices = data.get("choices") or []
                    content = ""
                    if choices and isinstance(choices[0], dict):
                        message = choices[0].get("message") or {}
                        if isinstance(message, dict):
                            content = str(message.get("content") or choices[0].get("text") or "").strip()
                    if not content:
                        result.update({
                            "ok": False,
                            "errorCode": "AI_PROVIDER_EMPTY_RESPONSE",
                            "error": "AI 服务未返回有效内容，请稍后重试",
                        })
                        return result
                    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                    result.update({"ok": True, "content": content, "usage": usage})
                    return result
                except (httpx.TimeoutException, httpx.TransportError):
                    if attempt < max_attempts - 1:
                        continue
                    break
    except Exception:  # noqa: BLE001
        logger.error("AI provider client failed: scene=%s request_id=%s", scene, request_id)
    result.update({
        "ok": False,
        "errorCode": "AI_PROVIDER_UNAVAILABLE",
        "error": "AI 服务暂不可用，请稍后重试",
    })
    return result


async def _invoke_general_model_for_learning(
    db,
    system_prompt: str,
    user_prompt: str,
    config: dict,
) -> tuple[str, int, float]:
    """调用通用文本模型（按次计费），返回 (response_text, tokens_used, cost_yuan)。

    复用既有的通用模型 HTTP 调用栈（generate_text），scene="kb_learning"。
    通用模型按次计费：默认 0.03 元/次，扣 Token 由 Java AiBillingService 统一处理。
    """
    # 复用既有的 generate_text（内部已处理配置加载、HTTP 调用、重试、错误兜底）
    result = await generate_text(
        scene="kb_learning",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.3,  # 提取任务用低温度，确保 JSON 输出稳定
    )

    if not result.get("ok"):
        logger.warning(
            "kb-learning LLM call failed: errorCode=%s error=%s",
            result.get("errorCode"),
            result.get("error"),
        )
        return "", 0, 0.0

    response_text = str(result.get("content") or "")
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    # 优先 total_tokens；缺失时回退 prompt_tokens + completion_tokens；都没有则 0
    if isinstance(usage.get("total_tokens"), (int, float)):
        tokens_used = int(usage.get("total_tokens"))
    else:
        tokens_used = int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)

    # 通用模型按次计费：默认 0.03 元/次，可由后台 perCallPrice 覆盖
    per_call_price = 0.03
    try:
        cfg_price = float((config or {}).get("perCallPrice", 0))
        if cfg_price > 0:
            per_call_price = cfg_price
    except (TypeError, ValueError):
        pass
    cost_yuan = per_call_price

    return response_text, tokens_used, cost_yuan


async def call_llm_for_learning(
    db,
    conversations: list[dict],
    config: dict,
) -> tuple[list[dict], int, float]:
    """调用通用模型提取 Q&A。

    Returns:
        (extracted_items, tokens_used, cost_yuan)
    """
    # 1. 构造对话文本
    conv_blocks = []
    for i, conv in enumerate(conversations, 1):
        msgs_text = "\n".join(
            f"  {'[卖家]' if m['is_auto_reply'] else '[买家]' if not m['is_auto_reply'] else '[卖家]'} {m['sender']}: {m['content']}"
            for m in conv["messages"]
        )
        conv_blocks.append(f"对话 {i}:\n{msgs_text}")
    conversations_text = "\n\n".join(conv_blocks)

    # 2. 构造 prompt
    # V1.49 三级分类：必须从下列 68 个二级分类 code 中选择（不允许自创）
    system_prompt = """你是知识库提取助手。以下是一段真实的买家-卖家对话。
请提取其中有价值的问答对（买家提问 + 卖家优质回复）。

要求:
1. 仅提取能体现真实销售技巧、产品知识、问题解决能力的 Q&A
2. 跳过纯闲聊、问候、表情、无意义对话
3. 对 Q&A 中的敏感信息脱敏:
   - 手机号 → [手机号]
   - 微信号/QQ号 → [联系方式]
   - 收货地址 → [地址]
   - 银行卡/身份证 → [敏感信息]
   - 真实姓名 → [姓名]
4. 为每个 Q&A 进行分类，category_code 必须从以下 68 个二级分类中选择（严禁自创）:

   【交易通用问题】
   - general_stock_query: 库存查询（库存/有货/现货/还有吗/没货/缺货/断货/在不在）
   - general_shipping_track: 发货跟踪（发货/物流/快递/什么时候发/单号/运单/发出/揽收）
   - general_refund_aftersale: 退款售后（退款/退货/换货/质量/坏了/破损/不想要/退钱）
   - general_product_consult: 商品咨询（规格/材质/尺寸/功能/详情/什么样/多大/多重）
   - general_price_discount: 价格优惠（便宜点/优惠/满减/折扣/券/降价/打折/少点）
   - general_account_login: 账号登录（登录/cookie/失效/掉线/登不上/扫码/二维码）

   【服饰鞋包】
   - fashion_men: 男装（男装/衬衫/T恤/外套/裤子/夹克）
   - fashion_women: 女装（女装/连衣裙/半身裙/衬衫/外套/针织）
   - fashion_shoes: 鞋类（鞋/运动鞋/板鞋/皮鞋/拖鞋/靴子）
   - fashion_bags: 箱包（包/背包/手提包/钱包/行李箱/托特包）
   - fashion_accessories: 配饰（配饰/帽子/围巾/皮带/手表/首饰）

   【数码家电】
   - digital_phone: 手机（手机/iPhone/华为/小米/三星/OPPO/vivo）
   - digital_computer: 电脑平板（电脑/笔记本/台式机/平板/MacBook/联想/戴尔）
   - digital_camera: 相机摄影（相机/单反/微单/镜头/摄影/三脚架/GoPro）
   - digital_audio: 音频设备（耳机/音响/音箱/麦克风/AirPods/蓝牙音箱）
   - digital_appliance_home: 家用电器（冰箱/洗衣机/空调/电视/微波炉/电饭煲）
   - digital_smart: 智能设备（智能手表/智能手环/智能音箱/智能家居/平衡车）

   【美妆个护】
   - beauty_skincare: 护肤品（护肤/面霜/精华/面膜/洗面奶/爽肤水/乳液）
   - beauty_makeup: 化妆品（化妆/口红/粉底/眼影/睫毛膏/腮红/BB霜）
   - beauty_perfume: 香水（香水/香氛/淡香水/浓香水/香精/留香）
   - beauty_personal_care: 个人护理（护理/洗发水/沐浴露/牙膏/卫生巾/剃须刀）
   - beauty_tools: 美容工具（美容工具/化妆刷/美容仪/卷发棒/理发器/指甲刀）

   【家居生活】
   - home_furniture: 家具（沙发/床/衣柜/餐桌/椅子/书桌/茶几）
   - home_textile: 家纺（床品/四件套/被子/枕头/毛巾/窗帘/地毯）
   - home_kitchen: 厨房用品（厨具/锅/碗/刀/砧板/餐具/水壶）
   - home_decor: 装饰摆件（装饰/摆件/挂画/花瓶/相框/香薰）
   - home_storage: 收纳整理（收纳/整理/收纳箱/衣架/挂钩/置物架）

   【母婴用品】
   - baby_formula: 奶粉辅食（奶粉/辅食/米粉/果泥/奶粉段/配方奶）
   - baby_diaper: 纸尿裤（纸尿裤/尿不湿/拉拉裤/NB/S/M/L/XL）
   - baby_toys: 玩具书籍（玩具/积木/绘本/故事书/早教/拼图）
   - baby_pregnant: 孕妇用品（孕妇/孕妇装/胎心仪/月子/待产/防辐射）
   - baby_clothes: 婴幼服装（婴儿/宝宝/童装/婴儿服/连体衣/肚兜）

   【运动户外】
   - sports_equipment: 运动器材（哑铃/跑步机/瑜伽/健身/杠铃/拉力器）
   - sports_outdoor_gear: 户外装备（帐篷/睡袋/登山/背包/炉具/登山杖）
   - sports_apparel: 运动服饰（运动服/速干衣/运动裤/运动文胸/瑜伽服）
   - sports_cycling: 骑行装备（自行车/电动车/头盔/骑行服/车灯/车锁）
   - sports_fishing: 垂钓用品（鱼竿/鱼线/鱼饵/鱼钩/渔轮/钓箱）

   【图书教材】
   - books_textbook: 教材教辅（教材/教辅/课本/练习册/试卷/参考书）
   - books_novel: 小说文学（小说/文学/名著/散文/诗集/网络小说）
   - books_magazine: 杂志期刊（杂志/期刊/读者/意林/时尚/国家地理）
   - books_professional: 专业书籍（专业/技术/编程/医学/法律/经管）
   - books_children: 儿童读物（绘本/童话/儿童/启蒙/拼音/故事）

   【艺术品收藏】
   - art_calligraphy: 字画书法（字画/书法/国画/油画/水墨/篆刻）
   - art_stamp_coin: 邮票钱币（邮票/钱币/纪念币/古币/银元/纸币）
   - art_antique: 古董收藏（古董/古玩/瓷器/玉器/青铜/鼻烟壶）
   - art_trendy: 潮玩手办（手办/盲盒/高达/乐高/模型/扭蛋）
   - art_memorabilia: 纪念品（纪念/徽章/门票/球星卡/明信片/绝版）

   【宠物用品】
   - pet_food: 宠物食品（猫粮/狗粮/零食/罐头/主粮/幼猫/成猫）
   - pet_toys: 宠物玩具（逗猫棒/球/飞盘/咬胶/猫爬架/玩具）
   - pet_clothes: 宠物服饰（宠物衣服/牵引绳/项圈/雨衣/鞋子）
   - pet_supplies_misc: 宠物用具（猫砂盆/食盆/笼子/航空箱/牵引）
   - pet_aquarium: 水族用品（鱼缸/鱼食/过滤器/加热棒/造景/热带鱼）

   【汽车用品】
   - auto_decor: 汽车装饰（脚垫/座套/香水/挂件/方向盘套/贴纸）
   - auto_parts: 汽车配件（雨刷/灯泡/轮胎/机油/滤芯/火花塞）
   - auto_electronics: 汽车电子（行车记录仪/导航/倒车雷达/充电器/车载冰箱）
   - auto_motorcycle: 摩托车（摩托车/头盔/骑行服/机车/踏板）
   - auto_bicycle: 自行车（自行车/山地车/公路车/电动车/车锁）

   【手工DIY】
   - handcraft_materials: 手工材料（毛线/布料/串珠/粘土/颜料/画笔）
   - handcraft_products: 手工成品（手作/DIY/定制/手工/礼物/创意）
   - handcraft_knitting: 编织工艺（编织/钩针/毛衣/围巾/玩偶/抱枕）
   - handcraft_ceramic: 陶艺作品（陶艺/陶瓷/手工/花瓶/杯子/摆件）
   - handcraft_wood: 木工作品（木工/木质/手工/家具/摆件/模型）

   【虚拟货源】
   - virtual_software: 软件安装包（安装包/破解/激活/软件/Windows/Office）
   - virtual_deployment: 程序部署服务（部署/代搭/环境/服务器/Docker/Linux/安装）
   - virtual_webdesign: 网页设计（网页/设计/网站/H5/前端/模板/建站）
   - virtual_activation: 激活码（激活码/序列号/授权/License/注册码/兑换码）
   - virtual_ebook: 电子书（电子书/PDF/epub/资料/教程/文档）
   - virtual_template: 设计模板（模板/素材/PSD/PPT/设计/资源/素材库）

   若对话内容无法精准匹配以上 68 个二级分类，使用 general_product_consult 兜底。严禁自创分类名。
5. 为每个 Q&A 生成:
   - category_code: 上方二级分类的 code（如 general_stock_query）
   - score: 0-100 价值评分
   - tags: 3-5 个标签（逗号分隔）
   - source_summary: 一句话摘要
6. 输出严格 JSON 数组格式，无其他文字

输出格式示例:
[{"question":"...","answer":"...","category_code":"general_stock_query","score":80,"tags":"...","source_summary":"..."}]
"""

    user_prompt = f"以下是需要分析的 {len(conversations)} 个对话：\n\n{conversations_text}"

    # 3. 调用通用模型（按次计费）
    response_text, tokens_used, cost_yuan = await _invoke_general_model_for_learning(
        db, system_prompt, user_prompt, config
    )

    # 4. 解析 JSON
    try:
        # 容错：去除可能的 markdown 代码块包装
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        items = json.loads(cleaned)
        if not isinstance(items, list):
            return [], tokens_used, cost_yuan
        return items, tokens_used, cost_yuan
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("kb-learning LLM response not valid JSON: %s", exc)
        return [], tokens_used, cost_yuan
