"""
RAG 知识库 - SimpleVectorStore 本地向量库
=========================================

实现参考 Spring AI 的 SimpleVectorStore，使用：
1. 文本嵌入：调用 OpenAI 兼容的 /v1/embeddings 接口（默认阿里云 DashScope text-embedding-v3）
2. 存储：JSON 文件持久化（dbdata/vectorstore.json），内存中保存所有向量
3. 检索：余弦相似度（Cosine Similarity），支持按 goodsId 元数据过滤
4. 切片：TokenTextSplitter 简化版（按字符数 + 重叠切片）

与 knowledge_base.py 的关系：
- knowledge_base.py 的 /extract 接口：AI 提取规则文本（已存在）
- rag_service.py 的 /add 接口：将文本切片后向量化并写入向量库
- rag_service.py 的 /query 接口：检索 topK 相关文档片段
- rag_service.py 的 /chat 接口：检索 + AI 生成回复（RAG 完整链路）
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy import text

from ..core.config import settings
from ..core.database import async_session
from ..core.outbound_network import public_https_outbound_policy
from .ai_provider import generate_text

logger = logging.getLogger(__name__)


# ============================================================
# 配置
# ============================================================
DEFAULT_VECTORSTORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "dbdata", "vectorstore.json"
)

# 默认 embedding 模型（与参考项目一致：阿里云 DashScope text-embedding-v3）
DEFAULT_EMBEDDING_MODEL = "text-embedding-v3"
DEFAULT_EMBEDDING_DIM = 1024  # DashScope text-embedding-v3 默认维度

# 文本切片参数
CHUNK_SIZE = 500        # 每个切片约 500 字符（中文）
CHUNK_OVERLAP = 80      # 切片间重叠 80 字符

# 默认检索参数
DEFAULT_TOP_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.3  # 余弦相似度阈值
MAX_EMBEDDING_INPUT_CHARS = 64 * 1024
MAX_EMBEDDING_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_EMBEDDING_DIMENSIONS = 65_536


# ============================================================
# 数据结构
# ============================================================
@dataclass
class VectorDocument:
    """向量文档"""
    id: str                                  # 文档 ID
    content: str                             # 文本内容
    embedding: list[float]                   # 向量
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据（goodsId, createTime, source 等)


@dataclass
class SearchHit:
    """检索命中"""
    id: str
    content: str
    score: float                             # 相似度分数（0-1）
    metadata: dict[str, Any]


# ============================================================
# SimpleVectorStore - 内存 + 文件持久化
# ============================================================
class SimpleVectorStore:
    """简单的向量存储，内存索引 + JSON 文件持久化。

    线程安全：所有写操作加锁，避免并发写入文件冲突。
    余弦相似度计算用纯 Python 实现（适合中小规模，<10万 文档）。
    """

    def __init__(self, file_path: str = DEFAULT_VECTORSTORE_PATH):
        self.file_path = file_path
        self._documents: list[VectorDocument] = []
        self._lock = threading.RLock()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                if os.path.exists(self.file_path):
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for item in data.get("documents", []):
                        self._documents.append(VectorDocument(
                            id=item["id"],
                            content=item["content"],
                            embedding=item["embedding"],
                            metadata=item.get("metadata") or {},
                        ))
                    logger.info("SimpleVectorStore 加载成功: 文档数=%d 路径=%s", len(self._documents), self.file_path)
            except Exception as e:
                logger.error("加载向量库失败", exc_info=True)
                raise RuntimeError("向量库加载失败，现有数据未被覆盖") from e
            self._loaded = True

    def add(self, docs: list[VectorDocument]) -> None:
        """添加文档（不会立即持久化，需调用 save_to_file）"""
        self._ensure_loaded()
        with self._lock:
            self._documents.extend(docs)

    def save_to_file(self) -> None:
        """持久化到文件"""
        self._ensure_loaded()
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                data = {
                    "version": 1,
                    "savedAt": datetime.now().isoformat(),
                    "documents": [
                        {
                            "id": d.id,
                            "content": d.content,
                            "embedding": d.embedding,
                            "metadata": d.metadata,
                        }
                        for d in self._documents
                    ],
                }
                tmp_path = self.file_path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                os.replace(tmp_path, self.file_path)
                logger.info("SimpleVectorStore 已持久化: 文档数=%d", len(self._documents))
            except Exception as e:
                logger.error("持久化向量库失败: %s", e, exc_info=True)
                raise

    def clear(self) -> None:
        """清空所有文档"""
        with self._lock:
            self._documents.clear()
            self._loaded = True

    def delete_by_metadata(self, key: str, value: Any) -> int:
        """按元数据删除文档，返回删除数量"""
        return self.delete_by_metadata_filters({key: value})

    def delete_by_metadata_filters(self, filters: dict[str, Any]) -> int:
        """仅删除同时匹配全部元数据条件的文档。"""
        self._ensure_loaded()
        with self._lock:
            before = len(self._documents)
            self._documents = [
                document
                for document in self._documents
                if not all(document.metadata.get(key) == value for key, value in filters.items())
            ]
            return before - len(self._documents)

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        filter_metadata: Optional[dict[str, Any]] = None,
    ) -> list[SearchHit]:
        """余弦相似度检索

        Args:
            query_embedding: 查询向量
            top_k: 返回前 K 条
            similarity_threshold: 相似度阈值（0-1），低于此值不返回
            filter_metadata: 元数据过滤（如 {"goodsId": "123"}）
        """
        self._ensure_loaded()
        with self._lock:
            docs_snapshot = list(self._documents)

        if not docs_snapshot:
            return []

        # 过滤元数据
        if filter_metadata:
            docs_snapshot = [
                d for d in docs_snapshot
                if all(d.metadata.get(k) == v for k, v in filter_metadata.items())
            ]

        # 计算余弦相似度
        hits: list[SearchHit] = []
        for doc in docs_snapshot:
            score = _cosine_similarity(query_embedding, doc.embedding)
            if score >= similarity_threshold:
                hits.append(SearchHit(
                    id=doc.id,
                    content=doc.content,
                    score=score,
                    metadata=doc.metadata,
                ))

        # 按相似度降序排序，取 top_k
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    def count(self, filter_metadata: Optional[dict[str, Any]] = None) -> int:
        """返回文档总数（可选过滤）"""
        self._ensure_loaded()
        with self._lock:
            if not filter_metadata:
                return len(self._documents)
            return sum(
                1 for d in self._documents
                if all(d.metadata.get(k) == v for k, v in filter_metadata.items())
            )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ============================================================
# 全局单例
# ============================================================
_store: Optional[SimpleVectorStore] = None
_store_lock = threading.Lock()


def get_vector_store() -> SimpleVectorStore:
    """获取全局向量库单例"""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = SimpleVectorStore()
    return _store


# ============================================================
# 文本切片（TokenTextSplitter 简化版）
# ============================================================
def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """按字符数切片，带重叠。

    简化版 TokenTextSplitter：
    - 优先按段落切（\n\n），段落过长再按字符切
    - 切片间保留 overlap 字符的重叠，避免切断语义
    """
    if not text:
        return []
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    # 先按段落分割
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # 如果当前段落本身就超过 chunk_size，按字符切
        if len(para) > chunk_size:
            # 先把 current 收尾
            if current:
                chunks.append(current)
                current = ""
            # 按字符切 para
            for i in range(0, len(para), chunk_size - overlap):
                chunk = para[i:i + chunk_size]
                if chunk:
                    chunks.append(chunk)
                if i + chunk_size >= len(para):
                    break
        else:
            # 拼接到 current
            if len(current) + len(para) + 2 > chunk_size:
                if current:
                    chunks.append(current)
                # 保留 overlap 重叠
                if chunks and overlap > 0:
                    current = chunks[-1][-overlap:] + "\n\n" + para
                else:
                    current = para
            else:
                current = current + "\n\n" + para if current else para

    if current:
        chunks.append(current)

    return chunks


# ============================================================
# Embedding 调用（OpenAI 兼容协议）
# ============================================================
# Embedding 配置缓存（避免每次生成都查库，与 ai_provider._load_chat_model_config_from_db 同款 60s TTL）
_embedding_config_cache: dict[str, str] = {}
_embedding_config_cache_ts: float = 0
_EMBEDDING_CONFIG_TTL = 60


async def _load_embedding_config() -> dict[str, str]:
    """从 admin_module_record 加载 embedding 模型配置。

    优先级：model-config-embedding > model-config-general > 环境变量
    """
    global _embedding_config_cache, _embedding_config_cache_ts
    now = time.time()
    # 缓存命中：直接返回，避免每次生成都查库
    if _embedding_config_cache and (now - _embedding_config_cache_ts) < _EMBEDDING_CONFIG_TTL:
        return dict(_embedding_config_cache)

    try:
        async with async_session() as db:
            rows = await db.execute(
                text("""
                    SELECT module_key, json_text FROM admin_module_record
                    WHERE module_key IN ('model-config-embedding', 'model-config-general') AND deleted = 0
                    ORDER BY id DESC
                """)
            )
            embedding_config = None
            general_config = None
            for row_key, row_text in rows.all():
                config = json.loads(row_text) if isinstance(row_text, str) else row_text
                if not isinstance(config, dict):
                    continue
                if row_key == 'model-config-embedding' and embedding_config is None:
                    embedding_config = config
                elif row_key == 'model-config-general' and general_config is None:
                    general_config = config

            merged: dict[str, Any] = {}
            if general_config:
                merged.update(general_config)
            if embedding_config:
                merged.update(embedding_config)

            base_url = str(merged.get("baseUrl") or merged.get("base_url") or "").strip()
            api_key = str(merged.get("apiKey") or merged.get("api_key") or "").strip()
            model = str(merged.get("modelName") or merged.get("model") or DEFAULT_EMBEDDING_MODEL).strip()

            if not base_url:
                base_url = os.environ.get("EMBEDDING_BASE_URL", "")
            if not api_key:
                api_key = os.environ.get("EMBEDDING_API_KEY", "")
            if not model:
                model = DEFAULT_EMBEDDING_MODEL

            result = {"base_url": base_url, "api_key": api_key, "model": model}
            _embedding_config_cache = dict(result)
            _embedding_config_cache_ts = now
            return result
    except Exception as e:
        logger.warning("加载 embedding 配置失败，使用环境变量 errorType=%s", type(e).__name__)
        # 查询失败不缓存，下次仍会尝试查库
        return {
            "base_url": os.environ.get("EMBEDDING_BASE_URL", ""),
            "api_key": os.environ.get("EMBEDDING_API_KEY", ""),
            "model": os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
        }


async def generate_embedding(text: str) -> list[float]:
    """调用 OpenAI 兼容的 /v1/embeddings 接口生成向量。

    失败时抛 RuntimeError。
    """
    if not text or not text.strip():
        return []
    if len(text) > MAX_EMBEDDING_INPUT_CHARS:
        raise RuntimeError("Embedding input exceeds the supported size")

    config = await _load_embedding_config()
    if not config["base_url"] or not config["api_key"]:
        raise RuntimeError(
            "Embedding 模型未配置：请在后台模型配置中添加 model-config-embedding（包含 baseUrl 和 apiKey），"
            "或设置环境变量 EMBEDDING_BASE_URL / EMBEDDING_API_KEY"
        )

    # 拼接 embeddings 端点
    base_url = config["base_url"].rstrip("/")
    if base_url.endswith("/v1"):
        endpoint = f"{base_url}/embeddings"
    elif "/v1/" in base_url:
        endpoint = f"{base_url}/embeddings"
    else:
        endpoint = f"{base_url}/v1/embeddings"

    payload = {
        "model": config["model"],
        "input": text,
    }
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        target = await public_https_outbound_policy.pin_public_https(endpoint)
    except ValueError as exc:
        raise RuntimeError("Embedding service endpoint failed security validation") from exc

    request_headers = dict(headers)
    request_headers["Host"] = target.host_header
    response_bytes = bytearray()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            async with client.stream(
                "POST",
                target.request_url,
                json=payload,
                headers=request_headers,
                extensions={"sni_hostname": target.sni_hostname},
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError("Embedding service rejected the request")
                chunks = response.aiter_bytes()
                async for chunk in chunks:
                    if len(response_bytes) + len(chunk) > MAX_EMBEDDING_RESPONSE_BYTES:
                        await chunks.aclose()
                        raise RuntimeError("Embedding service response exceeds the supported size")
                    response_bytes.extend(chunk)
    except RuntimeError:
        raise
    except (httpx.HTTPError, OSError) as exc:
        raise RuntimeError("Embedding service is temporarily unavailable") from exc

    try:
        data = json.loads(bytes(response_bytes))
        rows = data.get("data") if isinstance(data, dict) else None
        embedding = rows[0].get("embedding") if isinstance(rows, list) and rows and isinstance(rows[0], dict) else None
        if not isinstance(embedding, list) or not 1 <= len(embedding) <= MAX_EMBEDDING_DIMENSIONS:
            raise ValueError
        normalized = [float(value) for value in embedding if not isinstance(value, bool)]
        if len(normalized) != len(embedding) or any(not math.isfinite(value) for value in normalized):
            raise ValueError
        return normalized
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("Embedding service returned an invalid vector") from exc


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """批量生成向量（顺序调用，避免触发 API 限流）"""
    embeddings: list[list[float]] = []
    for text in texts:
        emb = await generate_embedding(text)
        embeddings.append(emb)
    return embeddings


# ============================================================
# RAG 服务 - 高层 API
# ============================================================
async def add_to_rag(
    content: str,
    tenant_id: int,
    goods_id: Optional[str] = None,
    source: Optional[str] = None,
    extra_metadata: Optional[dict] = None,
) -> dict:
    """将文本切片后向量化并写入向量库。

    Args:
        content: 原始文本内容
        goods_id: 关联的商品 ID（用于检索时过滤）
        source: 来源标识（如文件名）
        extra_metadata: 额外元数据

    Returns:
        {"success": True, "chunkCount": N, "docId": "..."}
    """
    if not tenant_id or int(tenant_id) <= 0:
        return {"success": False, "error": "tenant_id 不能为空"}
    if not content or not content.strip():
        return {"success": False, "error": "内容为空"}

    # 1. 切片
    chunks = split_text(content)
    if not chunks:
        return {"success": False, "error": "切片结果为空"}

    logger.info("RAG 切片完成: 原文长度=%d, 切片数=%d", len(content), len(chunks))

    # 2. 批量向量化
    try:
        embeddings = await generate_embeddings_batch(chunks)
    except Exception as e:
        logger.error("RAG 向量化失败 errorType=%s", type(e).__name__)
        return {"success": False, "error": "向量化服务暂时不可用，请稍后重试"}

    # 3. 写入向量库
    metadata = {
        "goodsId": str(goods_id) if goods_id else "",
        "source": source or "",
        "createTime": datetime.now().isoformat(),
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    metadata["tenantId"] = str(int(tenant_id))

    doc_id_prefix = str(goods_id or source or uuid.uuid4().hex[:8])
    docs: list[VectorDocument] = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        if not emb:
            continue
        doc = VectorDocument(
            id=f"{doc_id_prefix}-{idx}-{uuid.uuid4().hex[:8]}",
            content=chunk,
            embedding=emb,
            metadata={**metadata, "chunkIndex": idx},
        )
        docs.append(doc)

    store = get_vector_store()
    store.add(docs)
    store.save_to_file()

    logger.info("RAG 写入完成: docId=%s, 切片数=%d", doc_id_prefix, len(docs))
    return {
        "success": True,
        "chunkCount": len(docs),
        "docId": doc_id_prefix,
        "goodsId": metadata["goodsId"],
        "source": metadata["source"],
    }


async def query_rag(
    question: str,
    tenant_id: int,
    goods_id: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict:
    """检索与问题相关的知识库片段。

    Returns:
        {
            "success": True,
            "question": "...",
            "hits": [{"id", "content", "score", "metadata"}],
            "total": N,
        }
    """
    if not tenant_id or int(tenant_id) <= 0:
        return {"success": False, "error": "tenant_id 不能为空"}
    if not question or not question.strip():
        return {"success": False, "error": "问题不能为空"}

    # 1. 生成查询向量
    try:
        query_emb = await generate_embedding(question)
    except Exception:
        return {"success": False, "error": "查询向量化服务暂时不可用，请稍后重试"}

    # 2. 检索
    filter_metadata = {"tenantId": str(int(tenant_id))}
    if goods_id:
        filter_metadata["goodsId"] = str(goods_id)
    store = get_vector_store()
    hits = store.similarity_search(
        query_embedding=query_emb,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        filter_metadata=filter_metadata,
    )

    return {
        "success": True,
        "question": question,
        "hits": [
            {
                "id": h.id,
                "content": h.content,
                "score": round(h.score, 4),
                "metadata": h.metadata,
            }
            for h in hits
        ],
        "total": len(hits),
    }


async def chat_by_rag(
    question: str,
    tenant_id: int,
    goods_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict:
    """RAG 完整链路：检索 + AI 生成回复。

    Returns:
        {
            "success": True,
            "answer": "...",
            "hits": [...],
            "aiResult": {...},
        }
    """
    if not tenant_id or int(tenant_id) <= 0:
        return {"success": False, "error": "tenant_id 不能为空"}
    if not question or not question.strip():
        return {"success": False, "error": "问题不能为空"}

    # 1. 检索
    query_result = await query_rag(
        question=question,
        tenant_id=tenant_id,
        goods_id=goods_id,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )
    if not query_result.get("success"):
        return query_result

    hits = query_result.get("hits", [])
    if not hits:
        # 没有命中任何文档，直接调用 AI（无上下文）
        context = ""
    else:
        context = "\n---\n".join(h["content"] for h in hits)

    # 2. 构造 prompt
    if not system_prompt:
        system_prompt = (
            "你是闲鱼客服回复助手。请根据提供的参考资料回答用户问题。"
            "如果参考资料中没有相关信息，请明确告知用户并礼貌地提供帮助。"
            "回答要简洁、专业、礼貌，避免编造信息。"
        )

    user_message = (
        f"参考资料：\n{context}\n\n"
        f"用户问题：{question}\n\n"
        "请根据参考资料回答问题。"
    ) if context else f"用户问题：{question}\n\n请回答用户的问题。"

    # 3. 调用 AI 生成回复
    try:
        ai_result = await generate_text(
            scene="rag_chat",
            system_prompt=system_prompt,
            user_prompt=user_message,
            temperature=0.3,
        )
    except Exception:
        return {"success": False, "error": "AI 生成服务暂时不可用，请稍后重试", "hits": hits}

    if not ai_result.get("ok"):
        return {
            "success": False,
            "error": ai_result.get("error") or "AI 生成失败",
            "hits": hits,
        }

    answer = ai_result.get("content") or ""

    return {
        "success": True,
        "answer": answer,
        "hits": hits,
        "hitCount": len(hits),
        "aiResult": {
            "provider": ai_result.get("provider"),
            "model": ai_result.get("model"),
            "usage": ai_result.get("usage"),
            "requestId": ai_result.get("requestId"),
        },
    }


async def delete_rag_by_goods_id(goods_id: str, tenant_id: int) -> dict:
    """删除指定商品的所有 RAG 文档"""
    if not tenant_id or int(tenant_id) <= 0:
        return {"success": False, "error": "tenant_id 不能为空"}
    if not goods_id:
        return {"success": False, "error": "goods_id 不能为空"}
    store = get_vector_store()
    deleted = store.delete_by_metadata_filters({
        "tenantId": str(int(tenant_id)),
        "goodsId": str(goods_id),
    })
    if deleted > 0:
        store.save_to_file()
    return {"success": True, "deletedCount": deleted, "goodsId": goods_id}


async def get_rag_stats(tenant_id: int) -> dict:
    """获取 RAG 知识库统计信息"""
    if not tenant_id or int(tenant_id) <= 0:
        raise ValueError("tenant_id 不能为空")
    tenant_key = str(int(tenant_id))
    store = get_vector_store()
    total = store.count({"tenantId": tenant_key})
    # 按 goodsId 分组统计
    store._ensure_loaded()
    with store._lock:
        goods_count: dict[str, int] = {}
        for doc in store._documents:
            if doc.metadata.get("tenantId") != tenant_key:
                continue
            gid = str(doc.metadata.get("goodsId") or "")
            if gid:
                goods_count[gid] = goods_count.get(gid, 0) + 1
    return {
        "totalDocuments": total,
        "goodsCount": len(goods_count),
        "goodsBreakdown": goods_count,
        "embeddingModel": DEFAULT_EMBEDDING_MODEL,
    }


# ============================================================
# AI 客服自主学习知识库 - 扩展 API
# ============================================================
async def add_to_rag_for_learning(text: str, metadata: dict) -> None:
    """为学习 KB 添加向量。

    与既有 add_to_rag 区别：
    - metadata 必须含 kb_id / kb_type='learned'
    - 单独的 metadata 标记 source='learned_kb'，避免与系统 KB 混淆

    Args:
        text: 原始文本内容
        metadata: 元数据，必须含 kb_id；可选 kb_type、question、answer、category、score 等
    """
    if not text or not text.strip():
        logger.warning("rag: add_to_rag_for_learning empty text kb_id=%s", metadata.get("kb_id"))
        return
    try:
        # 1. 切片（复用既有 split_text）
        chunks = split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        if not chunks:
            logger.warning("rag: add_to_rag_for_learning empty chunks kb_id=%s", metadata.get("kb_id"))
            return

        # 2. 批量向量化（复用既有 generate_embeddings_batch）
        embeddings = await generate_embeddings_batch(chunks)

        # 3. 构造文档，附加 source='learned_kb' 标记
        kb_id = metadata.get("kb_id")
        base_metadata: dict[str, Any] = {
            **metadata,
            "source": "learned_kb",
            "createTime": datetime.now().isoformat(),
        }
        doc_id_prefix = f"learned-{kb_id or uuid.uuid4().hex[:8]}"
        docs: list[VectorDocument] = []
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            if not emb:
                continue
            docs.append(VectorDocument(
                id=f"{doc_id_prefix}-{idx}-{uuid.uuid4().hex[:8]}",
                content=chunk,
                embedding=emb,
                metadata={**base_metadata, "chunkIndex": idx},
            ))

        # 4. 写入向量库（复用既有 get_vector_store + add + save_to_file）
        store = get_vector_store()
        store.add(docs)
        store.save_to_file()

        logger.info(
            "rag: added learned kb id=%s chunks=%d",
            kb_id, len(docs),
        )
    except Exception:
        logger.exception(
            "rag: add_to_rag_for_learning failed kb_id=%s",
            metadata.get("kb_id"),
        )
        raise


async def search_with_filter(
    query: str,
    kb_ids: list[int],
    top_k: int = 3,
) -> list[dict]:
    """按 kb_ids 过滤的语义检索。

    similarity_search 仅支持 filter_metadata（相等匹配），不支持 filter_fn，
    因此先按 source='learned_kb' 在向量库内过滤缩小范围，再在内存中按 kb_ids 集合过滤。

    Args:
        query: 查询文本
        kb_ids: 限制检索的知识库 ID 列表
        top_k: 返回前 K 条

    Returns:
        [{question, answer, category, score, kb_id, similarity, weighted}, ...]
        按 weighted 降序排列。
    """
    if not kb_ids:
        return []
    if not query or not query.strip():
        return []

    try:
        # 1. 生成查询向量
        vector = await generate_embedding(query)
        if not vector:
            return []

        # 2. 在向量库内按 source 过滤（缩小范围），取 top_k * 3 用于后续内存过滤
        kb_id_set = {int(kb) for kb in kb_ids}
        store = get_vector_store()
        hits = store.similarity_search(
            query_embedding=vector,
            top_k=max(top_k * 3, top_k),
            similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
            filter_metadata={"source": "learned_kb"},
        )

        # 3. 内存中按 kb_ids 集合过滤（similarity_search 不支持 filter_fn）
        filtered: list[tuple[SearchHit, dict]] = []
        for hit in hits:
            meta = hit.metadata or {}
            raw_kb_id = meta.get("kb_id")
            try:
                hit_kb_id = int(raw_kb_id) if raw_kb_id is not None else None
            except (TypeError, ValueError):
                hit_kb_id = None
            if hit_kb_id is None or hit_kb_id not in kb_id_set:
                continue
            filtered.append((hit, meta))

        # 4. 取 Top-K，加权 score
        out: list[dict] = []
        for hit, meta in filtered[:top_k]:
            sim = float(hit.score or 0.0)
            try:
                raw_score = float(meta.get("score", 50))
            except (TypeError, ValueError):
                raw_score = 50.0
            normalized_score = raw_score / 100.0
            weighted = sim * 0.7 + normalized_score * 0.3
            out.append({
                "question": meta.get("question", ""),
                "answer": hit.content,
                "category": meta.get("category", ""),
                "score": raw_score,
                "kb_id": meta.get("kb_id"),
                "similarity": sim,
                "weighted": weighted,
            })

        # 5. 按 weighted 降序
        out.sort(key=lambda x: x["weighted"], reverse=True)
        return out
    except Exception:
        logger.exception("rag: search_with_filter failed kb_ids=%s", kb_ids)
        return []


async def search_with_category_filter(
    query: str,
    kb_ids: list[int],
    category_code: Optional[str] = None,
    top_k: int = 3,
) -> list[dict]:
    """按 category_code 预过滤的语义检索（V1.47 新增）。

    性能优化：
    1. 若 category_code 命中，先在向量库内按 source + category_code 双重过滤缩小范围
       （从百万级压缩到单分类万级以内），再在内存中按 kb_ids 过滤。
    2. 若 category_code 为空或未命中，回退到原有 search_with_filter 逻辑（全库检索）。

    Args:
        query: 查询文本
        kb_ids: 限制检索的知识库 ID 列表（用户启用的 KB）
        category_code: 预定义分类 code（如 stock_query），可选
        top_k: 返回前 K 条

    Returns:
        [{question, answer, category, category_code, score, kb_id, similarity, weighted}, ...]
    """
    if not kb_ids:
        return []
    if not query or not query.strip():
        return []

    # 无 category_code 时回退到原逻辑
    if not category_code:
        return await search_with_filter(query, kb_ids, top_k)

    try:
        # 1. 生成查询向量
        vector = await generate_embedding(query)
        if not vector:
            return []

        # 2. 在向量库内按 source + category_code 双重过滤（核心优化点）
        kb_id_set = {int(kb) for kb in kb_ids}
        store = get_vector_store()
        hits = store.similarity_search(
            query_embedding=vector,
            top_k=max(top_k * 3, top_k),
            similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
            filter_metadata={"source": "learned_kb", "category_code": category_code},
        )

        # 3. 内存中按 kb_ids 集合过滤
        filtered: list[tuple[SearchHit, dict]] = []
        for hit in hits:
            meta = hit.metadata or {}
            raw_kb_id = meta.get("kb_id")
            try:
                hit_kb_id = int(raw_kb_id) if raw_kb_id is not None else None
            except (TypeError, ValueError):
                hit_kb_id = None
            if hit_kb_id is None or hit_kb_id not in kb_id_set:
                continue
            filtered.append((hit, meta))

        # 4. 取 Top-K，加权 score
        out: list[dict] = []
        for hit, meta in filtered[:top_k]:
            sim = float(hit.score or 0.0)
            try:
                raw_score = float(meta.get("score", 50))
            except (TypeError, ValueError):
                raw_score = 50.0
            normalized_score = raw_score / 100.0
            weighted = sim * 0.7 + normalized_score * 0.3
            out.append({
                "question": meta.get("question", ""),
                "answer": hit.content,
                "category": meta.get("category", ""),
                "category_code": meta.get("category_code", ""),
                "score": raw_score,
                "kb_id": meta.get("kb_id"),
                "similarity": sim,
                "weighted": weighted,
            })

        # 5. 若分类预过滤结果不足（< top_k），补充无分类过滤的检索结果
        if len(out) < top_k:
            fallback = await search_with_filter(query, kb_ids, top_k)
            existing_ids = {item["kb_id"] for item in out}
            for item in fallback:
                if item.get("kb_id") not in existing_ids:
                    out.append(item)
                    if len(out) >= top_k:
                        break

        # 6. 按 weighted 降序
        out.sort(key=lambda x: x["weighted"], reverse=True)
        return out[:top_k]
    except Exception:
        logger.exception(
            "rag: search_with_category_filter failed kb_ids=%s category=%s",
            kb_ids, category_code,
        )
        return []


def detect_category_by_keywords(query: str) -> Optional[str]:
    """关键词规则匹配，快速判定查询所属分类（V1.47 新增）。

    用于检索时的分类预过滤：先尝试关键词匹配（毫秒级），
    命中则在该分类内检索；未命中则全库检索。

    Args:
        query: 用户查询文本

    Returns:
        命中的 category_code（如 "stock_query"），未命中返回 None
    """
    if not query:
        return None
    # 关键词表（与 V1.47 预定义分类保持一致）
    CATEGORY_KEYWORDS = {
        "stock_query": ["库存", "有货", "现货", "还有吗", "没货", "缺货", "断货", "在不在"],
        "shipping_track": ["发货", "物流", "快递", "什么时候发", "单号", "运单", "发出", "揽收"],
        "refund_aftersale": ["退款", "退货", "换货", "质量", "坏了", "破损", "不想要", "退钱"],
        "product_consult": ["规格", "材质", "尺寸", "功能", "详情", "什么样", "多大", "多重"],
        "price_discount": ["便宜点", "优惠", "满减", "折扣", "券", "降价", "打折", "少点"],
        "account_login": ["登录", "cookie", "失效", "掉线", "登不上", "扫码", "二维码"],
        "card_key_delivery": ["卡密", "激活码", "虚拟商品", "兑换码"],
        "workflow_config": ["工作流", "节点", "流程", "触发"],
        "scheduled_task": ["定时", "计划任务"],
        "auto_reply": ["自动回复", "模板", "AI回复", "智能回复", "话术"],
        "auto_delivery": ["自动发货", "发货规则"],
        "membership_recharge": ["Token", "充值", "VIP", "会员", "SVP", "余额"],
        "system_usage": ["怎么用", "功能", "操作", "使用", "教程", "怎么操作"],
        "troubleshoot": ["报错", "错误", "不能用", "失败", "异常", "bug", "崩溃"],
    }
    for code, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in query:
                return code
    return None
