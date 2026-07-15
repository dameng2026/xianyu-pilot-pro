import pytest

from app.api.v1.routes import auto_reply_scope
from app.models.entities import XianyuGoods


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _FakeDb:
    def __init__(self):
        self.added = []
        self.commit_count = 0
        self.refresh_count = 0

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 501
        self.added.append(obj)

    async def commit(self):
        self.commit_count += 1

    async def refresh(self, _obj):
        self.refresh_count += 1


@pytest.mark.anyio
async def test_upsert_goods_scope_row_creates_placeholder_record_when_local_product_missing(monkeypatch):
    db = _FakeDb()

    async def fake_find(*_args, **_kwargs):
        return None

    monkeypatch.setattr(auto_reply_scope, "_find_goods_scope_row", fake_find)

    goods, created = await auto_reply_scope._upsert_goods_scope_row(
        db=db,
        tenant_id=1,
        account_id=9,
        goods_id="123456",
        enabled=True,
        title="会话里的商品",
        image_url="https://img.example.com/goods.png",
    )

    assert created is True
    assert goods.id == 501
    assert goods.tenant_id == 1
    assert goods.account_id == 9
    assert goods.goods_id == "123456"
    assert goods.external_goods_id == "123456"
    assert goods.title == "会话里的商品"
    assert goods.cover_pic == "https://img.example.com/goods.png"
    assert goods.image_url == "https://img.example.com/goods.png"
    assert goods.auto_reply_enabled == 1
    assert db.added == [goods]
    assert db.commit_count == 1
    assert db.refresh_count == 1


@pytest.mark.anyio
async def test_upsert_goods_scope_row_updates_existing_scope_row_without_new_insert(monkeypatch):
    db = _FakeDb()
    existing = XianyuGoods(
        id=88,
        tenant_id=1,
        account_id=9,
        goods_id="",
        external_goods_id="",
        title="",
        cover_pic=None,
        image_url=None,
        auto_reply_enabled=None,
        deleted=0,
    )

    async def fake_find(*_args, **_kwargs):
        return existing

    monkeypatch.setattr(auto_reply_scope, "_find_goods_scope_row", fake_find)

    goods, created = await auto_reply_scope._upsert_goods_scope_row(
        db=db,
        tenant_id=1,
        account_id=9,
        goods_id="654321",
        enabled=False,
        title="补齐标题",
        image_url="https://img.example.com/cover.png",
    )

    assert created is False
    assert goods is existing
    assert goods.id == 88
    assert goods.goods_id == "654321"
    assert goods.external_goods_id == "654321"
    assert goods.title == "补齐标题"
    assert goods.cover_pic == "https://img.example.com/cover.png"
    assert goods.image_url == "https://img.example.com/cover.png"
    assert goods.auto_reply_enabled == 0
    assert db.added == []
    assert db.commit_count == 1
    assert db.refresh_count == 1
