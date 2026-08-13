"""退款关单（退款订单注销）服务单元测试。"""

from unittest.mock import AsyncMock

import pytest

from app.services import refund_cancel_service


def test_split_delivery_blocks_splits_by_separator():
    blocks = refund_cancel_service.split_delivery_blocks("第一块\n---\n第二块")
    assert blocks == ["第一块", "第二块"]


def test_split_delivery_blocks_returns_empty_for_none():
    assert refund_cancel_service.split_delivery_blocks(None) == []
    assert refund_cancel_service.split_delivery_blocks("   ") == []


def test_extract_first_link():
    assert refund_cancel_service.extract_first_link("下载：https://example.com/a 其他") == "https://example.com/a"
    assert refund_cancel_service.extract_first_link("无链接") == ""


@pytest.mark.asyncio
async def test_call_unregister_url_rejects_invalid_url(monkeypatch):
    async def _fail_pin(_url):
        raise ValueError("not public")
    monkeypatch.setattr(
        refund_cancel_service.public_https_outbound_policy,
        "pin_public_https",
        _fail_pin,
    )
    ok, err = await refund_cancel_service._call_unregister_url(
        "https://example.com/x", 30, "内容", "https://example.com/a",
    )
    assert ok is False
    assert "URL 校验失败" in err


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeSession:
    def __init__(self, account_row, order_row=None, record_row=None):
        self._account_row = account_row
        self._order_row = order_row
        self._record_row = record_row
        self.commits = 0
        self.updates = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM xianyu_account" in sql:
            return _FakeResult(row=self._account_row)
        if "FROM xianyu_trade_order" in sql and "is_unregistered" in sql:
            return _FakeResult(row=self._order_row)
        if "FROM delivery_record" in sql:
            return _FakeResult(row=self._record_row)
        if "UPDATE xianyu_trade_order" in sql:
            self.updates.append((sql, params or {}))
            return _FakeResult(row=None)
        raise AssertionError(f"unexpected SQL: {sql}")

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_process_order_unregister_skips_when_disabled(monkeypatch):
    session = _FakeSession(account_row={"refund_cancel_enabled": 0})
    monkeypatch.setattr(refund_cancel_service, "async_session", lambda: session)

    await refund_cancel_service.process_order_unregister(1, 1, "ORDER-1")

    assert session.commits == 0
    assert session.updates == []


@pytest.mark.asyncio
async def test_process_order_unregister_marks_empty_content(monkeypatch):
    session = _FakeSession(
        account_row={"refund_cancel_enabled": 1, "refund_cancel_url": "https://example.com/x", "refund_cancel_timeout": 30},
        order_row={"id": 10, "is_unregistered": 0},
        record_row=None,
    )
    monkeypatch.setattr(refund_cancel_service, "async_session", lambda: session)

    await refund_cancel_service.process_order_unregister(1, 1, "ORDER-1")

    assert session.commits >= 1
    assert session.updates
    sql, params = session.updates[0]
    assert "is_unregistered" in sql
    assert params["order_db_id"] == 10
