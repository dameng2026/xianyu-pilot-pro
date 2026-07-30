"""AI 客服自主学习知识库提取服务。

每日 02:00 由 Java core-api 调度触发，扫描近 24h 闲鱼会话，
过滤 AI 成分过多的会话，调 LLM 提取高价值 Q&A，脱敏后入库。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy
from sqlalchemy import text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# 脱敏正则（在 LLM prompt 中也要求脱敏，这里做二次保障）
SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    # 手机号（前后加边界，避免误匹配长数字串中的子串）
    (r"(?<!\d)1[3-9]\d{9}(?!\d)", "[手机号]"),
    # 微信号（字母+数字+_-，长度 6-20，前后加边界）
    (r"(?:微信|vx|vx号|加我)[：:]?\s*[a-zA-Z][a-zA-Z0-9_-]{5,19}", "[联系方式]"),
    # QQ号
    (r"(?:QQ|qq|q号)[：:]?\s*[1-9]\d{4,11}", "[联系方式]"),
    # 邮箱
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[邮箱]"),
    # 身份证
    (r"(?<!\d)\d{17}[\dXx](?!\d)", "[敏感信息]"),
    # 银行卡（前后加边界，避免误匹配订单号等长数字）
    (r"(?<!\d)\d{16,19}(?!\d)", "[敏感信息]"),
    # URL / 链接
    (r"https?://[^\s<>\"']+", "[链接]"),
    # IP 地址
    (r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)", "[IP]"),
]


def sanitize_text(s: str) -> str:
    """对文本做正则脱敏（LLM 已脱敏一次，这里兜底）。"""
    import re
    if not s:
        return s
    out = s
    for pattern, replacement in SENSITIVE_PATTERNS:
        out = re.sub(pattern, replacement, out)
    return out


def md5_hash(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


async def run_learning_job(
    db: AsyncSession,
    config: dict[str, Any],
) -> dict[str, Any]:
    """执行一次学习作业。

    Args:
        db: 数据库 session
        config: 学习配置（来自 application.yml）

    Returns:
        统计结果字典
    """
    batch_id = f"kb-learn-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    started_at = datetime.now()

    stats = {
        "batch_id": batch_id,
        "started_at": started_at.isoformat(),
        "status": "running",
        "total_conversations": 0,
        "kept_conversations": 0,
        "rejected_by_ai_ratio": 0,
        "extracted_items": 0,
        "deduplicated_items": 0,
        "llm_tokens_used": 0,
        "llm_cost_yuan": 0.0,
        "error_message": "",
    }

    try:
        # Step 1+2: 会话扫描与 AI 占比过滤
        conversations = await _scan_and_filter_conversations(db, config, stats)
        if not conversations:
            logger.info("kb-learning batch=%s no conversations to process", batch_id)
            stats["status"] = "success"
            stats["finished_at"] = datetime.now().isoformat()
            return stats

        # Step 3: 加载完整消息
        conv_with_msgs = await _load_conversation_messages(db, conversations)

        # Step 4: LLM 提取（分批并发）
        extracted_items = await _extract_with_llm(
            db, conv_with_msgs, config, stats, batch_id
        )
        stats["extracted_items"] = len(extracted_items)

        # Step 5: 去重入库
        dedup_count = await _dedup_and_store(db, extracted_items, batch_id)
        stats["deduplicated_items"] = dedup_count

        # Step 6: 向量化索引
        await _index_vectors(db)

        stats["status"] = "success"
    except Exception as exc:
        logger.exception("kb-learning batch=%s failed", batch_id)
        stats["status"] = "failed"
        stats["error_message"] = f"{type(exc).__name__}: {exc}"
    finally:
        stats["finished_at"] = datetime.now().isoformat()

    return stats


async def _scan_and_filter_conversations(
    db: AsyncSession,
    config: dict[str, Any],
    stats: dict[str, Any],
) -> list[dict[str, Any]]:
    """Step 1+2: 扫描会话并按 AI 占比过滤。"""
    lookback_hours = int(config.get("lookback_hours", 24))
    min_msgs = int(config.get("min_conversation_messages", 5))
    max_convs = int(config.get("max_conversations_per_run", 500))
    ai_ratio_threshold = float(config.get("ai_ratio_threshold", 0.6))

    cutoff_ms = int((time.time() - lookback_hours * 3600) * 1000)

    # 注意：MySQL 默认 sql_mode=only_full_group_by，SELECT 中所有非聚合列
    # 必须出现在 GROUP BY 中。此处需要 account_id / tenant_id 用于后续 LLM 抽取，
    # 但同一 s_id 下可能存在多账号/多租户（理论上不会，但保险起见用 MAX 聚合）。
    result = await db.execute(text("""
        SELECT s_id,
               MAX(account_id) AS account_id,
               MAX(tenant_id) AS tenant_id,
               COUNT(*) AS msg_count,
               SUM(CASE WHEN is_auto_reply = 1 THEN 1 ELSE 0 END) AS ai_count
        FROM xianyu_chat_message
        WHERE message_time >= :cutoff_ms
          AND deleted = 0
        GROUP BY s_id
        HAVING msg_count >= :min_msgs
        LIMIT :max_convs
    """), {"cutoff_ms": cutoff_ms, "min_msgs": min_msgs, "max_convs": max_convs})

    rows = result.mappings().all()
    stats["total_conversations"] = len(rows)

    kept: list[dict[str, Any]] = []
    for row in rows:
        msg_count = row["msg_count"]
        ai_count = row["ai_count"] or 0
        ai_ratio = ai_count / msg_count if msg_count > 0 else 1.0
        if ai_ratio >= ai_ratio_threshold:
            stats["rejected_by_ai_ratio"] += 1
            continue
        kept.append({
            "s_id": row["s_id"],
            "account_id": row["account_id"],
            "tenant_id": row["tenant_id"],
            "msg_count": msg_count,
            "ai_count": ai_count,
        })
    stats["kept_conversations"] = len(kept)
    return kept


async def _load_conversation_messages(
    db: AsyncSession,
    conversations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Step 3: 加载每个保留会话的完整消息。

    优化：用 IN :s_ids 批量查询，避免 N+1（500 会话 = 500 次 SQL → 1 次 SQL）。
    """
    if not conversations:
        return []
    s_ids = [c["s_id"] for c in conversations]
    result = await db.execute(text("""
        SELECT s_id, sender_user_name, msg_content, content_type,
               is_auto_reply, message_time
        FROM xianyu_chat_message
        WHERE s_id IN :s_ids AND deleted = 0
        ORDER BY s_id, message_time ASC
    """).bindparams(sqlalchemy.bindparam("s_ids", expanding=True)),
    {"s_ids": s_ids})
    # 按 s_id 分组
    by_sid: dict[str, list[dict[str, Any]]] = {}
    for row in result.mappings():
        if row["content_type"] != 1:
            continue
        content = row["msg_content"] or ""
        if not content.strip():
            continue
        by_sid.setdefault(row["s_id"], []).append({
            "sender": row["sender_user_name"] or "",
            "content": content,
            "is_auto_reply": int(row["is_auto_reply"] or 0),
        })
    out: list[dict[str, Any]] = []
    for conv in conversations:
        msgs = by_sid.get(conv["s_id"], [])
        if len(msgs) >= 3:
            out.append({**conv, "messages": msgs})
    return out


async def _extract_with_llm(
    db: AsyncSession,
    conversations: list[dict[str, Any]],
    config: dict[str, Any],
    stats: dict[str, Any],
    batch_id: str,
) -> list[dict[str, Any]]:
    """Step 4: 分批调 LLM 提取 Q&A。"""
    from app.services.ai_provider import call_llm_for_learning  # 后续 Task 创建

    batch_size = int(config.get("llm_batch_size", 5))
    concurrency = int(config.get("llm_concurrency", 3))
    max_cost = float(config.get("max_cost_yuan_per_run", 50))

    batches = [conversations[i:i + batch_size]
               for i in range(0, len(conversations), batch_size)]

    semaphore = asyncio.Semaphore(concurrency)
    all_items: list[dict[str, Any]] = []

    async def process_batch(b_idx: int, batch: list[dict[str, Any]]):
        async with semaphore:
            try:
                items, tokens_used, cost_yuan = await call_llm_for_learning(
                    db, batch, config
                )
                stats["llm_tokens_used"] += tokens_used
                stats["llm_cost_yuan"] += cost_yuan

                # 成本上限保护
                if stats["llm_cost_yuan"] >= max_cost:
                    logger.warning(
                        "kb-learning batch=%s cost exceeded: %.2f >= %.2f, stopping",
                        batch_id, stats["llm_cost_yuan"], max_cost
                    )
                    return False  # 信号：停止后续批次

                for item in items:
                    # 尝试从 LLM 输出的 conv_index 字段恢复 s_id（1-based 索引）
                    conv_idx = item.pop("conv_index", None)
                    if conv_idx is not None:
                        try:
                            idx = int(conv_idx) - 1
                            if 0 <= idx < len(batch):
                                item["s_id"] = batch[idx]["s_id"]
                            else:
                                item["s_id"] = batch[0]["s_id"]  # 兜底
                        except (ValueError, TypeError):
                            item["s_id"] = batch[0]["s_id"] if len(batch) == 1 else None
                    else:
                        # LLM 未输出 conv_index：单会话批次可准确归因，多会话批次归因到第一条
                        item["s_id"] = batch[0]["s_id"] if len(batch) == 1 else None
                    all_items.append(item)
                return True
            except Exception as exc:
                logger.exception(
                    "kb-learning batch=%s extract batch %d failed",
                    batch_id, b_idx
                )
                stats["error_message"] += f"\nbatch {b_idx}: {exc}"
                return True  # 单批失败不停止

    tasks = [process_batch(i, b) for i, b in enumerate(batches)]
    results = await asyncio.gather(*tasks)
    if False in results:
        logger.warning("kb-learning batch=%s stopped early due to cost limit", batch_id)

    return all_items


async def _dedup_and_store(
    db: AsyncSession,
    items: list[dict[str, Any]],
    batch_id: str,
) -> int:
    """Step 5: 脱敏 + 去重 + 入库。

    性能优化：
    1. 同批次内按 content_hash 去重，避免唯一约束冲突。
    2. 一次性批量查重（SELECT ... WHERE content_hash IN (...)），避免 N+1。
    3. 批量预解析分类（按 category_name 分组，每个唯一分类仅一次 DB 查询）。
    4. 使用 INSERT IGNORE 防御并发场景（uk_learned_kb_hash 唯一约束）。
    """
    # 同批次内去重
    seen_hashes: set[str] = set()
    unique_items: list[dict[str, Any]] = []
    for item in items:
        question = sanitize_text(item.get("question", "").strip())
        answer = sanitize_text(item.get("answer", "").strip())
        if not question or not answer:
            continue
        if len(question) > 1000:
            question = question[:1000]
        h = md5_hash(question + answer)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        item["_q"] = question
        item["_a"] = answer
        item["_hash"] = h
        unique_items.append(item)

    if not unique_items:
        return 0

    # 批量查重：一次 SQL 拿到所有已存在的 hash
    all_hashes = [it["_hash"] for it in unique_items]
    existing_result = await db.execute(
        text("""
            SELECT id, content_hash, source_count, source_conv_ids
            FROM ai_cs_learned_kb
            WHERE content_hash IN :hashes AND deleted = 0
        """).bindparams(sqlalchemy.bindparam("hashes", expanding=True)),
        {"hashes": all_hashes}
    )
    existing_map: dict[str, dict[str, Any]] = {}
    for row in existing_result.mappings():
        existing_map[row["content_hash"]] = dict(row)

    # 批量预解析分类：按 category_code 分组，仅查一次
    # V1.47 改造：LLM 返回 category_code（如 stock_query），兼容旧版 category 字段
    category_codes = set()
    for it in unique_items:
        code = (it.get("category_code") or it.get("category") or "other").strip()[:64]
        category_codes.add(code)
    category_id_map: dict[str, int | None] = {}
    for code in category_codes:
        category_id_map[code] = await _resolve_category_id(db, code)

    stored = 0
    for item in unique_items:
        question = item["_q"]
        answer = item["_a"]
        content_hash = item["_hash"]
        existing_row = existing_map.get(content_hash)

        if existing_row:
            # 累加 source_count，追加 source_conv_ids
            new_count = (existing_row["source_count"] or 1) + 1
            old_ids = json.loads(existing_row["source_conv_ids"] or "[]") \
                if existing_row["source_conv_ids"] else []
            s_id = item.get("s_id")
            if s_id and s_id not in old_ids and len(old_ids) < 20:
                old_ids.append(s_id)
            await db.execute(text("""
                UPDATE ai_cs_learned_kb
                SET source_count = :c, source_conv_ids = :ids, updated_time = NOW()
                WHERE id = :id
            """), {
                "c": new_count,
                "ids": json.dumps(old_ids),
                "id": existing_row["id"],
            })
        else:
            category_code = (item.get("category_code") or item.get("category") or "other").strip()[:64]
            category_id = category_id_map.get(category_code)

            # 使用 INSERT IGNORE 防御并发场景（uk_learned_kb_hash 唯一约束）
            await db.execute(text("""
                INSERT IGNORE INTO ai_cs_learned_kb (
                    category_id, question, answer, tags, source_summary,
                    content_hash, score, review_status, enabled,
                    vector_indexed, source_count, source_conv_ids,
                    learn_batch_id, sensitive_filtered, deleted,
                    created_time, updated_time
                ) VALUES (
                    :cat, :q, :a, :tags, :summary,
                    :h, :score, :review, 1,
                    0, 1, :conv_ids,
                    :batch, 1, 0,
                    NOW(), NOW()
                )
            """), {
                "cat": category_id,
                "q": question,
                "a": answer,
                "tags": (item.get("tags") or "")[:512],
                "summary": (item.get("source_summary") or "")[:500],
                "h": content_hash,
                "score": int(item.get("score", 50)),
                "review": "pending",
                "conv_ids": json.dumps([item["s_id"]] if item.get("s_id") else []),
                "batch": batch_id,
            })
            stored += 1

    await db.commit()
    return stored


async def _resolve_category_id(
    db: AsyncSession,
    name_or_code: str,
) -> int | None:
    """查二级分类 id（V1.49 三级分类改造）。

    V1.49 改造：LLM 必须输出预定义的 68 个二级分类 code 之一，
    函数仅查找已存在的二级分类（parent_id IS NOT NULL），不再新建自定义分类。
    未命中时归到 general_product_consult（交易通用问题-商品咨询）兜底。

    注意：不在此函数内 commit()，由外层 _dedup_and_store 统一提交。
    """
    name_or_code = (name_or_code or "general_product_consult").strip()
    # 1. 优先按 code 查找二级分类（parent_id IS NOT NULL）
    existing = await db.execute(text("""
        SELECT id FROM ai_cs_kb_category
        WHERE code = :c AND parent_id IS NOT NULL AND deleted = 0
        LIMIT 1
    """), {"c": name_or_code})
    row = existing.mappings().first()
    if row:
        return row["id"]

    # 2. 兼容旧版中文分类名：按 name 查找二级分类
    name_hash = md5_hash(name_or_code)
    existing = await db.execute(text("""
        SELECT id FROM ai_cs_kb_category
        WHERE name_hash = :h AND parent_id IS NOT NULL AND deleted = 0
        LIMIT 1
    """), {"h": name_hash})
    row = existing.mappings().first()
    if row:
        return row["id"]

    # 3. 兜底：归到 general_product_consult（V1.49 兜底二级分类）
    #    V1.47 时代的 'other' 已在 V1.49 中被软删，不再使用
    existing = await db.execute(text("""
        SELECT id FROM ai_cs_kb_category
        WHERE code = 'general_product_consult' AND parent_id IS NOT NULL AND deleted = 0
        LIMIT 1
    """))
    row = existing.mappings().first()
    if row:
        return row["id"]

    # 4. 极端兜底：如果连 general_product_consult 都没有，取任意一个二级分类
    existing = await db.execute(text("""
        SELECT id FROM ai_cs_kb_category
        WHERE parent_id IS NOT NULL AND deleted = 0
        ORDER BY sort_order, id LIMIT 1
    """))
    row = existing.mappings().first()
    return row["id"] if row else None


async def _index_vectors(db: AsyncSession) -> None:
    """Step 6: 对 vector_indexed=0 的条目调 rag_service 向量化。

    性能优化：
    1. embedding API 调用（慢操作）用 asyncio.Semaphore 并发，4 并发。
    2. DB 更新串行执行（AsyncSession 不支持跨协程并发），但相对 embedding 是快操作。
    3. 单条失败不影响其他记录。
    """
    from app.services.rag_service import add_to_rag_for_learning

    result = await db.execute(text("""
        SELECT k.id, k.question, k.answer, k.category_id, k.score, c.code AS category_code
        FROM ai_cs_learned_kb k
        LEFT JOIN ai_cs_kb_category c ON k.category_id = c.id
        WHERE k.vector_indexed = 0 AND k.deleted = 0 AND k.enabled = 1
        ORDER BY k.id DESC LIMIT 200
    """))
    rows = result.mappings().all()

    if not rows:
        return

    # 并发限流：embedding API 通常有 QPS 限制，4 并发是较稳妥的折中
    semaphore = asyncio.Semaphore(4)

    async def embed_only(row: dict[str, Any]) -> tuple[dict[str, Any], Exception | None]:
        """仅并发执行 embedding API 调用，DB 更新稍后串行执行。"""
        async with semaphore:
            try:
                text_content = f"Q: {row['question']}\nA: {row['answer']}"
                await add_to_rag_for_learning(
                    text=text_content,
                    metadata={
                        "kb_id": row["id"],
                        "kb_type": "learned",
                        "score": row["score"],
                        "category_id": row["category_id"],
                        "category_code": row["category_code"] or "other",
                    },
                )
                return row, None
            except Exception as exc:
                return row, exc

    # 阶段1：并发 embedding
    results = await asyncio.gather(*[embed_only(dict(r)) for r in rows])

    # 阶段2：串行 DB 更新（AsyncSession 不支持跨协程并发）
    for row, exc in results:
        if exc is None:
            await db.execute(text("""
                UPDATE ai_cs_learned_kb
                SET vector_indexed = 1, vector_error = NULL, updated_time = NOW()
                WHERE id = :id
            """), {"id": row["id"]})
        else:
            await db.execute(text("""
                UPDATE ai_cs_learned_kb
                SET vector_error = :err, updated_time = NOW()
                WHERE id = :id
            """), {"id": row["id"], "err": str(exc)[:255]})

    await db.commit()
