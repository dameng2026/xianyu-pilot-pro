"""个人黑名单（发货拦截）单元测试。"""

from unittest.mock import AsyncMock

import pytest

from app.services import ws_delivery_handler


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


@pytest.mark.asyncio
async def test_check_personal_blacklist_returns_reason():
    class _BlacklistDB:
        async def execute(self, statement, params=None):
            return _FakeResult(row={"reason": "恶意退款买家"})

    reason = await ws_delivery_handler._check_personal_blacklist(
        db=_BlacklistDB(),
        tenant_id=1,
        account_id=1,
        buyer_user_id="buyer-1@goofish",
        xy_goods_id="1001",
    )

    assert reason == "恶意退款买家"


@pytest.mark.asyncio
async def test_check_personal_blacklist_returns_none_when_not_hit():
    class _NoHitDB:
        async def execute(self, statement, params=None):
            return _FakeResult(row=None)

    reason = await ws_delivery_handler._check_personal_blacklist(
        db=_NoHitDB(),
        tenant_id=1,
        account_id=1,
        buyer_user_id="buyer-1@goofish",
        xy_goods_id="1001",
    )

    assert reason is None


@pytest.mark.asyncio
async def test_check_personal_blacklist_matches_global_account_entry():
    """account_id=0 的全租户黑名单应命中任意账号。"""
    class _GlobalDB:
        async def execute(self, statement, params=None):
            return _FakeResult(row={"reason": "全局黑名单"})

    reason = await ws_delivery_handler._check_personal_blacklist(
        db=_GlobalDB(),
        tenant_id=1,
        account_id=99,
        buyer_user_id="buyer-1@goofish",
        xy_goods_id="1001",
    )

    assert reason == "全局黑名单"


@pytest.mark.asyncio
async def test_check_personal_blacklist_fails_open():
    class _BrokenDB:
        async def execute(self, statement, params=None):
            raise RuntimeError("db down")

    reason = await ws_delivery_handler._check_personal_blacklist(
        db=_BrokenDB(),
        tenant_id=1,
        account_id=1,
        buyer_user_id="buyer-1@goofish",
        xy_goods_id="1001",
    )

    assert reason is None


@pytest.mark.asyncio
async def test_text_delivery_blocks_blacklisted_buyer(monkeypatch):
    class _NoCallDB:
        async def execute(self, statement, params=None):
            raise AssertionError("黑名单拦截时不应继续执行任何 SQL")

    send_delivery = AsyncMock(return_value=(True, False))
    safe_insert = AsyncMock()
    notify_failure = AsyncMock()

    monkeypatch.setattr(
        ws_delivery_handler,
        "_check_personal_blacklist",
        AsyncMock(return_value="恶意退款买家"),
    )
    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_delivery)
    monkeypatch.setattr(ws_delivery_handler, "_safe_insert_delivery_record", safe_insert)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_failure)

    await ws_delivery_handler._execute_text_delivery(
        db=_NoCallDB(),
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        s_id="sid-1",
        pnm_id="PNM-1",
        buyer_user_id="buyer-1@goofish",
        buyer_user_name="恶意买家",
        xy_goods_id="1001",
        buy_quantity=1,
        rule={"id": 1, "delivery_timing": ws_delivery_handler.DELIVERY_TIMING_AFTER_PAYMENT},
        delivery_content="发货内容",
        trigger_source="payment",
    )

    send_delivery.assert_not_awaited()
    safe_insert.assert_awaited_once()
    assert safe_insert.await_args.kwargs["status"] == 3
    assert "黑名单" in safe_insert.await_args.kwargs["fail_reason"]
    notify_failure.assert_awaited_once()
