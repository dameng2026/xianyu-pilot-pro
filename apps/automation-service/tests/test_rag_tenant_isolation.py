import pytest

from app.services import rag_service


@pytest.mark.asyncio
async def test_rag_add_forces_authenticated_tenant_metadata(monkeypatch, tmp_path):
    store = rag_service.SimpleVectorStore(str(tmp_path / "vectors.json"))

    async def embeddings(_chunks):
        return [[1.0, 0.0]]

    monkeypatch.setattr(rag_service, "generate_embeddings_batch", embeddings)
    monkeypatch.setattr(rag_service, "get_vector_store", lambda: store)

    result = await rag_service.add_to_rag(
        content="tenant one knowledge",
        tenant_id=1,
        goods_id="goods-1",
        extra_metadata={"tenantId": 999},
    )

    assert result["success"] is True
    assert store.count({"tenantId": "1"}) == 1
    assert store.count({"tenantId": "999"}) == 0


@pytest.mark.asyncio
async def test_rag_query_only_returns_authenticated_tenant_documents(monkeypatch, tmp_path):
    store = rag_service.SimpleVectorStore(str(tmp_path / "vectors.json"))
    store.add([
        rag_service.VectorDocument(
            id="tenant-1",
            content="tenant one",
            embedding=[1.0, 0.0],
            metadata={"tenantId": "1", "goodsId": "goods"},
        ),
        rag_service.VectorDocument(
            id="tenant-2",
            content="tenant two",
            embedding=[1.0, 0.0],
            metadata={"tenantId": "2", "goodsId": "goods"},
        ),
    ])

    async def embedding(_text):
        return [1.0, 0.0]

    monkeypatch.setattr(rag_service, "generate_embedding", embedding)
    monkeypatch.setattr(rag_service, "get_vector_store", lambda: store)

    result = await rag_service.query_rag(
        question="question",
        tenant_id=1,
        goods_id="goods",
    )

    assert result["success"] is True
    assert [hit["id"] for hit in result["hits"]] == ["tenant-1"]


@pytest.mark.asyncio
async def test_rag_chat_queries_with_authenticated_tenant(monkeypatch):
    captured = {}

    async def query(**kwargs):
        captured.update(kwargs)
        return {"success": True, "hits": []}

    async def generate_text(**_kwargs):
        return {"ok": True, "content": "answer"}

    monkeypatch.setattr(rag_service, "query_rag", query)
    monkeypatch.setattr(rag_service, "generate_text", generate_text)

    result = await rag_service.chat_by_rag(question="question", tenant_id=8)

    assert result["success"] is True
    assert captured["tenant_id"] == 8


@pytest.mark.asyncio
async def test_rag_delete_only_removes_authenticated_tenant_documents(monkeypatch, tmp_path):
    store = rag_service.SimpleVectorStore(str(tmp_path / "vectors.json"))
    store.add([
        rag_service.VectorDocument(
            id="tenant-1",
            content="tenant one",
            embedding=[1.0],
            metadata={"tenantId": "1", "goodsId": "goods"},
        ),
        rag_service.VectorDocument(
            id="tenant-2",
            content="tenant two",
            embedding=[1.0],
            metadata={"tenantId": "2", "goodsId": "goods"},
        ),
    ])
    monkeypatch.setattr(rag_service, "get_vector_store", lambda: store)

    result = await rag_service.delete_rag_by_goods_id("goods", tenant_id=1)

    assert result["success"] is True
    assert result["deletedCount"] == 1
    assert store.count({"tenantId": "1"}) == 0
    assert store.count({"tenantId": "2"}) == 1


@pytest.mark.asyncio
async def test_rag_stats_only_count_authenticated_tenant_documents(monkeypatch, tmp_path):
    store = rag_service.SimpleVectorStore(str(tmp_path / "vectors.json"))
    store.add([
        rag_service.VectorDocument(
            id="tenant-1",
            content="one",
            embedding=[1.0],
            metadata={"tenantId": "1", "goodsId": "goods-1"},
        ),
        rag_service.VectorDocument(
            id="tenant-2",
            content="two",
            embedding=[1.0],
            metadata={"tenantId": "2", "goodsId": "goods-2"},
        ),
    ])
    monkeypatch.setattr(rag_service, "get_vector_store", lambda: store)

    stats = await rag_service.get_rag_stats(tenant_id=1)

    assert stats["totalDocuments"] == 1
    assert stats["goodsCount"] == 1
    assert stats["goodsBreakdown"] == {"goods-1": 1}
    assert "vectorStorePath" not in stats


def test_corrupt_vector_store_is_not_silently_treated_as_empty(tmp_path):
    path = tmp_path / "vectors.json"
    path.write_text("{not-json", encoding="utf-8")
    store = rag_service.SimpleVectorStore(str(path))

    with pytest.raises(RuntimeError, match="向量库加载失败"):
        store.count()
