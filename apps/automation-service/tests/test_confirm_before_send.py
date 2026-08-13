"""“先确认发货再发送内容”顺序开关的单元测试。"""

from unittest.mock import AsyncMock

import pytest

from app.services import ws_delivery_handler


class _FakeResult:
    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        if self._row is not None:
            return self._row
        return self._rows[0] if self._rows else None


class _OrderUpdateDB:
    async def execute(self, statement, params=None):
        sql = str(statement)
        if "UPDATE xianyu_trade_order" in sql:
            return _FakeResult(row=None)
        raise AssertionError(f"unexpected SQL: {sql}")


def _base_rule(**overrides):
    rule = {
        "id": 1,
        "confirm_before_send": 1,
        "closed_order_still_send": 0,
        "delivery_timing": ws_delivery_handler.DELIVERY_TIMING_AFTER_PAYMENT,
        "segments": [],
    }
    rule.update(overrides)
    return rule


def test_is_order_closed_error_recognizes_closed_codes():
    assert ws_delivery_handler._is_order_closed_error({"error": "ORDER_CLOSED", "message": ""}) is True
    assert ws_delivery_handler._is_order_closed_error({"error": "ORDER_STATUS_ERROR", "message": ""}) is True
    assert ws_delivery_handler._is_order_closed_error({"error": "BUSY", "message": "平台繁忙"}) is False
    assert ws_delivery_handler._is_order_closed_error(None) is False


@pytest.mark.asyncio
async def test_pre_confirm_allows_card_only_when_order_closed_and_flag(monkeypatch):
    class _NoCallDB:
        async def execute(self, statement, params=None):
            raise AssertionError("订单已关闭补发路径不应执行 SQL")

    monkeypatch.setattr(
        ws_delivery_handler,
        "_detect_bargain_from_message_or_db",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        ws_delivery_handler,
        "_auto_confirm_shipment",
        AsyncMock(return_value={"success": False, "error": "ORDER_CLOSED", "message": "订单已关闭"}),
    )

    should_abort, resolved = await ws_delivery_handler._pre_confirm_shipment_if_enabled(
        db=_NoCallDB(),
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        s_id="sid-1",
        pnm_id="PNM-1",
        buyer_user_id="buyer-1@goofish",
        buyer_user_name="测试买家",
        xy_goods_id="1001",
        buy_quantity=1,
        rule=_base_rule(closed_order_still_send=1),
        trigger_source="payment",
        delivery_type=ws_delivery_handler.MODE_TEXT,
    )

    assert should_abort is False
    assert resolved == "ORDER-001"


@pytest.mark.asyncio
async def test_text_delivery_aborts_when_confirm_before_send_fails(monkeypatch):
    db = _OrderUpdateDB()
    send_delivery = AsyncMock(return_value=(True, False))
    insert_record = AsyncMock()
    safe_insert = AsyncMock()
    notify_failure = AsyncMock()

    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_delivery)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_record)
    monkeypatch.setattr(ws_delivery_handler, "_safe_insert_delivery_record", safe_insert)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_failure)
    monkeypatch.setattr(
        ws_delivery_handler,
        "_detect_bargain_from_message_or_db",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        ws_delivery_handler,
        "_auto_confirm_shipment",
        AsyncMock(return_value={"success": False, "error": "BUSY", "message": "平台繁忙"}),
    )

    await ws_delivery_handler._execute_text_delivery(
        db=db,
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        s_id="sid-1",
        pnm_id="PNM-1",
        buyer_user_id="buyer-1@goofish",
        buyer_user_name="测试买家",
        xy_goods_id="1001",
        buy_quantity=1,
        rule=_base_rule(),
        delivery_content="发货内容",
        trigger_source="payment",
    )

    send_delivery.assert_not_awaited()
    safe_insert.assert_awaited_once()
    assert safe_insert.await_args.kwargs["status"] == 3
    assert "先确认发货失败" in safe_insert.await_args.kwargs["fail_reason"]
    notify_failure.assert_awaited_once()


@pytest.mark.asyncio
async def test_text_delivery_confirms_before_send_then_skips_second_confirm(monkeypatch):
    db = _OrderUpdateDB()
    send_delivery = AsyncMock(return_value=(True, False))
    insert_record = AsyncMock()
    auto_confirm = AsyncMock(return_value={"success": True})

    monkeypatch.setattr(ws_delivery_handler, "_send_delivery_message", send_delivery)
    monkeypatch.setattr(ws_delivery_handler, "_insert_delivery_record", insert_record)
    monkeypatch.setattr(
        ws_delivery_handler,
        "_detect_bargain_from_message_or_db",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(ws_delivery_handler, "_auto_confirm_shipment", auto_confirm)

    await ws_delivery_handler._execute_text_delivery(
        db=db,
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        s_id="sid-1",
        pnm_id="PNM-1",
        buyer_user_id="buyer-1@goofish",
        buyer_user_name="测试买家",
        xy_goods_id="1001",
        buy_quantity=1,
        rule=_base_rule(),
        delivery_content="发货内容",
        trigger_source="payment",
    )

    send_delivery.assert_awaited_once()
    auto_confirm.assert_awaited_once()
    insert_record.assert_awaited_once()
    assert insert_record.await_args.kwargs["status"] == 2


@pytest.mark.asyncio
async def test_kami_delivery_aborts_before_claim_when_confirm_before_send_fails(monkeypatch):
    class _NoCallDB:
        async def execute(self, statement, params=None):
            raise AssertionError("预确认失败时不应继续执行任何 SQL")

    safe_insert = AsyncMock()
    notify_failure = AsyncMock()

    monkeypatch.setattr(ws_delivery_handler, "_has_existing_realtime_delivery", AsyncMock(return_value=False))
    monkeypatch.setattr(ws_delivery_handler, "_safe_insert_delivery_record", safe_insert)
    monkeypatch.setattr(ws_delivery_handler, "_notify_realtime_delivery_failure", notify_failure)
    monkeypatch.setattr(
        ws_delivery_handler,
        "_detect_bargain_from_message_or_db",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        ws_delivery_handler,
        "_auto_confirm_shipment",
        AsyncMock(return_value={"success": False, "error": "BUSY", "message": "平台繁忙"}),
    )

    await ws_delivery_handler._execute_kami_delivery(
        db=_NoCallDB(),
        tenant_id=1,
        account_id=1,
        order_id="ORDER-001",
        s_id="sid-1",
        pnm_id="PNM-1",
        buyer_user_id="buyer-1@goofish",
        buyer_user_name="测试买家",
        xy_goods_id="1001",
        buy_quantity=1,
        rule=_base_rule(),
        card_group_id=10,
        trigger_source="payment",
    )

    safe_insert.assert_awaited_once()
    assert safe_insert.await_args.kwargs["status"] == 3
    assert safe_insert.await_args.kwargs["delivery_type"] == ws_delivery_handler.MODE_KAMI
    notify_failure.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_goods_delivery_rule_reads_confirm_before_send(monkeypatch):
    class _ConfigDB:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "FROM delivery_goods_config" in sql:
                return _FakeResult(row={
                    "id": 1,
                    "goods_id": 100,
                    "config_json": (
                        '{"payDelivery":{"enabled":1,"mode":"text","content":"x",'
                        '"confirmBeforeSend":true}}'
                    ),
                })
            raise AssertionError(f"unexpected SQL: {sql}")

    rule = await ws_delivery_handler._load_goods_delivery_rule(
        db=_ConfigDB(),
        tenant_id=1,
        goods={"id": 100, "title": "测试商品"},
    )

    assert rule is not None
    assert rule["confirm_before_send"] == 1
